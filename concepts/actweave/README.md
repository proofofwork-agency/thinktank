# Actweave

**Record, replay, and govern Vercel AI SDK agents in CI — no API keys.**

Record one real run of your agent at the model boundary into a source-controlled JSONL evidence ledger. Replay it through your **real** agent in CI, deterministically and keyless. When your prompt, tools, or tool results drift from the recording, the test **fails with a diff that names the change** — stale fixtures fail loudly instead of passing silently.

```bash
npm install -D actweave
```

Works with `ai` >= 6 (AI SDK). Zero runtime dependencies. ESM, Node >= 20.

## The loop

**1. Record once** (with a real provider, locally):

```ts
import { ToolLoopAgent, stepCountIs, tool } from "ai";
import { createRecorder, recordModel, recordTools } from "actweave/record";
import { writeGoldenLedgerSync } from "actweave/ledger";

const recorder = createRecorder({ deterministic: true });

const agent = new ToolLoopAgent({
  model: recordModel(openai("gpt-5"), recorder), // wrap your real model
  instructions: "Resolve refunds.",
  tools: recordTools({ lookupOrder }, recorder, { risk: { lookupOrder: "read" } }),
  stopWhen: stepCountIs(5),
});

await recorder.run("Can order 123 be refunded?", () => agent.generate({ prompt: "Can order 123 be refunded?" }));

const { events } = await recorder.close();
writeGoldenLedgerSync("test/fixtures/refund-denied.jsonl", events, {
  meta: { scenario: "refund-denied", provider: "openai", modelId: "gpt-5" },
});
```

**2. Commit the fixture.** It is deterministic JSONL — re-recording an unchanged run produces a zero-line git diff.

**3. Replay in CI** — no API key, your real agent code:

```ts
import { it } from "vitest";
import { assertReplayable } from "actweave/replay";

it("replays the recorded refund path", async () => {
  await assertReplayable("test/fixtures/refund-denied.jsonl", {
    agent: (model) =>
      new ToolLoopAgent({
        model, // recorded responses served through your real loop
        instructions: "Resolve refunds.",
        tools: { lookupOrder },
        stopWhen: stepCountIs(5),
      }),
  });
});
```

## Drift fails loudly

Strict replay hashes every model request — prompt, tool definitions, tool results — against the recording. Change your system prompt and the test fails like this:

```text
Replay drift at model call #1:
  recorded sha256:4f0ac6fc59d03c5f80...
  actual   sha256:f79c134b0cf16b797c...
  - prompt[0] (system): text differs:
      recorded: "Resolve refunds."
      actual:   "Resolve refunds. Always offer a coupon."
Hint: the agent's prompt, tools, or tool results changed since this fixture was recorded.
If the change is intentional, re-record the fixture; otherwise this is a regression.
```

The same applies to tool descriptions, input schemas, toolChoice, and — because each step's request contains the previous step's tool results — to **changed tool behavior**. Sampling knobs (temperature, topP, …) are never hashed by default, so tuning them does not invalidate fixtures. A loop that grows or shrinks a step fails with an exhaustion error. Use `mode: "loose"` to tolerate drift and inspect `driftReport()` instead.

## Assert trajectories

```ts
import { check } from "actweave";

check(events) // LedgerEvent[], a recorder, or an AI SDK result
  .completed()
  .noErrors()
  .called("lookupOrder")
  .calledWith("lookupOrder", { orderId: "123" })
  .notCalled("issueRefund")
  .toolCallOrder(["lookupOrder"])
  .eventSequence(["run.started", "model.called", "model.completed", "run.completed"])
  .outputMatches(/cannot be refunded/i)
  .toMatchGolden("test/fixtures/refund-denied.jsonl");
```

Or as vitest matchers:

```ts
import { expect } from "vitest";
import { extendActweaveMatchers } from "actweave/vitest";

extendActweaveMatchers(expect);

expect(events).toBeCompletedRun();
expect(events).toHaveCalledTool("lookupOrder", { orderId: "123" });
await expect("test/fixtures/refund-denied.jsonl").toBeReplayable({ agent: buildAgent });
```

`toMatchGolden` writes the fixture on first run and updates it with `ACTWEAVE_UPDATE_GOLDEN=1`. Volatile fields are handled with `compareRuns(..., { ignorePaths: ["items[*].timestamp"] })` and normalizers instead of exact-JSON brittleness.

## Govern risky tools — with evidence

```ts
import { guardTools } from "actweave/govern";

const tools = guardTools(
  { lookupOrder, issueRefund },
  {
    allowTools: ["lookupOrder", "issueRefund"],
    approve: ["issueRefund"],
    approver: ({ input }) => (input.amount > 500 ? { status: "denied", reason: "exceeds threshold" } : true),
    maxRisk: ["read", "write"],
    sideEffects: "blocked-in-replay",
    budget: { maxToolCalls: 20, maxCostUsd: 0.05 },
  },
  { recorder, risk: { issueRefund: "write" } },
);
```

Every decision leaves ledger evidence (`governance.tool.blocked`, `governance.approval.resolved`, `safety.violation`) that CI asserts:

```ts
check(events).policyEnforced("approval-denied").approvalDenied("issueRefund");
expect(events).toHaveEnforcedPolicy("tool-not-allowed");
```

With `onViolation: "error-result"` the violation is returned as the tool result, so the model's reaction is recorded — and the governed run itself replays keylessly. Tools in `approve` without an `approver` defer to the AI SDK's native `needsApproval` flow.

## What passing proves

| Passing proves                                                       | Does not prove                              |
| -------------------------------------------------------------------- | ------------------------------------------- |
| The recorded decision path still executes through your current agent | A live LLM would choose the same path again |
| Prompt, tool definitions, and tool results match the recording       | Behavior on unseen inputs                   |
| Governance policies enforce as configured, with audit evidence       | Semantic quality of the output              |
| The committed fixture runs without a provider API key                | Latency or cost characteristics             |

Replay is the deterministic bottom layer of an agent testing pyramid. For semantic quality scoring, pair Actweave with an eval tool (LLM-as-judge, scorers); for live drift detection, re-record on a schedule and review the fixture diff.

## When NOT to use Actweave

- You need model-graded quality evals — use an eval framework (evalite, promptfoo, Braintrust, LangSmith) alongside.
- You need a hosted dashboard or observability platform.
- Your agent has no tools and no governance requirements — plain `MockLanguageModelV3` from `ai/test` may be enough.
- You are not on the AI SDK (`LanguageModelV3`) — the generic `createRecorder()` works anywhere, but recording middleware and replay target the AI SDK model boundary. (Mastra 1.0 accepts `LanguageModelV3` models directly; officially tested support is on the roadmap.)

## Docs and example

- [`examples/refund-agent`](examples/refund-agent) — the full loop, runnable **without an API key**: committed fixture, keyless replay through a real `ToolLoopAgent`, trajectory assertions, and a deliberate drift failure. `npm run build && cd examples/refund-agent && npm i && npm test`.
- [`docs/getting-started.md`](docs/getting-started.md) · [`recording`](docs/recording.md) · [`replay-and-drift`](docs/replay-and-drift.md) · [`assertions`](docs/assertions.md) · [`governance`](docs/governance.md) · [`ledger-format`](docs/ledger-format.md) · [`test-suite`](docs/test-suite.md) · [`competitors`](docs/competitors.md)

## API surface

```ts
import { check, checkLedger } from "actweave"; // assertions
import { createRecorder, recordModel, recordTools, recordingMiddleware } from "actweave/record";
import { assertReplayable, replayModel, compareRuns, loadReplayFixture } from "actweave/replay";
import { guardTools, GovernanceViolationError } from "actweave/govern";
import { readGoldenLedgerSync, writeGoldenLedgerSync, InMemoryLedger, JsonlLedgerWriter } from "actweave/ledger";
import { extendActweaveMatchers } from "actweave/vitest";
```

## Fixture format

One run per file: an optional `__golden_meta` line, then one canonical-key-order JSON event per line (`actweave.ledger.v2`). `model.called` events carry the normalized request (hash, prompt, tools, settings); `model.completed` events carry the verbatim response content. Secrets are redacted at write time (responses are stored verbatim for replay fidelity — keep secrets out of prompts). Deterministic mode gives sequence ids and a fixed-epoch clock so diffs stay minimal.

## Versioning

`ai` is an optional peer (>= 6 < 7) used for types only — Actweave never imports it at runtime. The test suite pins an exact `ai` version and CI runs a non-blocking canary against `ai@latest`. Fixtures record `recordedWith` metadata so drift from SDK upgrades is attributable.

License: MIT.

# Getting started

Actweave tests Vercel AI SDK agents by recording one real run and replaying it deterministically in CI without API keys.

## Install

```bash
npm install -D actweave
```

Requirements: `ai` >= 6 in your project, Node >= 20, ESM. Vitest is the supported test runner for the matchers; the core `check()` API works in any runner.

## Record a fixture

Wrap your model with `recordModel` and your tools with `recordTools`, run the agent once with a real provider, and write the golden fixture:

```ts
// scripts/record-fixtures.ts — run locally with your provider key
import { ToolLoopAgent, stepCountIs } from "ai";
import { openai } from "@ai-sdk/openai";
import { createRecorder, recordModel, recordTools } from "actweave/record";
import { writeGoldenLedgerSync } from "actweave/ledger";
import { tools } from "../src/agent-tools.js";

const recorder = createRecorder({ deterministic: true });

const agent = new ToolLoopAgent({
  model: recordModel(openai("gpt-5"), recorder),
  instructions: "Resolve refunds.",
  tools: recordTools(tools, recorder, { risk: { lookupOrder: "read", issueRefund: "write" } }),
  stopWhen: stepCountIs(5),
});

await recorder.run("Can order 123 be refunded?", () => agent.generate({ prompt: "Can order 123 be refunded?" }));
const { events } = await recorder.close();

writeGoldenLedgerSync("test/fixtures/refund-denied.jsonl", events, {
  meta: { scenario: "refund-denied", provider: "openai", modelId: "gpt-5" },
});
```

Review the JSONL diff like any code change, then commit it.

## Replay in CI

```ts
// test/refund.replay.test.ts
import { it } from "vitest";
import { ToolLoopAgent, stepCountIs } from "ai";
import { assertReplayable } from "actweave/replay";
import { tools } from "../src/agent-tools.js";

it("replays the recorded refund path without an API key", async () => {
  await assertReplayable("test/fixtures/refund-denied.jsonl", {
    agent: (model) =>
      new ToolLoopAgent({
        model,
        instructions: "Resolve refunds.",
        tools,
        stopWhen: stepCountIs(5),
      }),
  });
});
```

The agent factory builds your agent exactly as production does — only the model is swapped for the replay model. If your prompt, tools, or tool behavior changed since recording, the test fails with a drift diff naming the change (see [replay-and-drift.md](replay-and-drift.md)).

## Keep going

- [recording.md](recording.md) — streaming, determinism, secrets, approvals
- [replay-and-drift.md](replay-and-drift.md) — strict vs loose, drift anatomy, exhaustion
- [assertions.md](assertions.md) — check(), vitest matchers, golden fixtures
- [governance.md](governance.md) — guardTools policies and evidence
- [ledger-format.md](ledger-format.md) — the JSONL schema reference
- [test-suite.md](test-suite.md) — what this repo's own tests prove and how to run them

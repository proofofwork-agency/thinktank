# Replay and drift

`replayModel(fixture)` implements `LanguageModelV3` and serves the fixture's recorded responses in order — through your **real** agent. `assertReplayable(source, { agent })` is the one-liner that loads the fixture, builds the replay model, runs your agent factory, and verifies the outcome.

## Strict mode (default)

Every incoming model call is normalized and hashed exactly like at record time, then compared to the recorded request. On mismatch, replay throws `ReplayDriftError`:

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

The diff isolates the change: per-message prompt divergence, tool added/removed, `tools[name]: description differs`, `inputSchema differs`, `toolChoice`/`responseFormat` changes. Settings deltas (temperature etc.) are shown informationally but never fail the hash by default.

Because step N+1's request contains step N's tool results, **changed tool behavior is also drift**: if your tool now returns different data for the recorded input, replay fails at the next model call pointing at the tool-result part.

Strict mode requires recorded request hashes — fixtures recorded with `recordModel()` have them. Fixtures derived from AI SDK results (`resultToLedgerEvents`) do not, and strict replay refuses them with instructions.

## Loose mode

`mode: "loose"` serves responses by position regardless of drift and accumulates a `driftReport()`. `assertReplayable` returns the report in its result rather than throwing. Use it for migrations where drift is expected and you want the inventory.

## Exhaustion

- The agent makes **more** model calls than recorded → `ReplayFixtureExhaustedError` immediately (the loop grew a step: new tool round-trip, retry, changed stop condition).
- The agent makes **fewer** calls → `ReplayUnconsumedError` from `assertExhausted()` (the loop shortened).

Both errors say which direction and suggest re-recording if intentional.

## Output comparison

`assertReplayable` compares the agent's final `text` against the fixture's recorded output (the `run.completed` output, falling back to the last recorded text response). Disable with `compareOutput: false`.

## Event-level comparison

For full trajectory equality, pass a recorder and wrap your tools, then compare:

```ts
const replayRecorder = createRecorder({ deterministic: true });
await assertReplayable(fixture, {
  agent: (model) => buildAgent(model, recordTools(tools, replayRecorder)),
  recorder: replayRecorder,
  compare: { ignorePaths: ["fetchedAt"], allowSideEffects: true },
});
```

`compareRuns(expected, actual, options)` is also available directly, with `ignorePaths` (dot paths, `[*]` wildcards) and `normalizers` for volatile fields.

## Streaming

`agent.stream()` works: the replay model synthesizes a canonical chunk sequence (text deltas, tool-call parts, finish with recorded usage) from the consolidated fixture.

## What replay does and does not prove

Replay proves the recorded decision path still executes through your current code, with your current prompt/tools matching the recording, keylessly. It does not prove a live model would decide the same way today — that question needs a fresh recording (re-record and review the fixture diff) or live evals.

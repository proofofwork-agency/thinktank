# Refund agent example

The full Actweave loop on a real `ToolLoopAgent`, runnable **without any API key**: a committed fixture is replayed through the real agent, trajectory assertions run against it, and a prompt change demonstrably fails with a drift diff.

```bash
# from the repo root
npm run build

cd examples/refund-agent
npm install
npm test
```

What's here:

- `src/agent.mjs` — the agent factory (`buildSupportAgent(model)`) used identically by production, recording, and replay; plus the `lookupOrder` tool.
- `fixtures/refund-denied.jsonl` — the committed evidence ledger: one run, deterministic JSONL, hashed model requests, verbatim responses.
- `test/replay.test.ts` — `assertReplayable` (keyless replay), `check()` trajectory assertions, vitest matchers, and a deliberate drift failure showing the diff that names the changed prompt.
- `scripts/record.mjs` — re-records the fixture (`npm run record`). By default it records from a scripted model so everything stays keyless; the header comment shows the one-line swap to record from a live provider instead.

The recording path is identical either way — real agent loop, real tool execution, real recorder. Only the model behind `recordModel()` differs.

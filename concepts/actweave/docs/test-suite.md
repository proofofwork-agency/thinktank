# Test Suite

## Running Tests

```bash
npm test                # All unit + integration tests
npx vitest run test/integration  # Integration tests only
npm run verify          # typecheck + lint + test + legacy-name check
npm run test:coverage   # Coverage report
npm run pack:check      # Package integrity
```

After building at root, run the example suite:

```bash
cd examples/refund-agent && npm i && npm test
```

Tests require no API keys. Fixtures are generated deterministically in-test (or committed, like the example's); the only key-gated step is recording the dogfood fixture once.

## Layout

**Unit tests** (`test/*.test.ts`): Pure ledger, check, and diff modules.

**Integration tests** (`test/integration/*.test.ts`): Real `ai` package (exact-pinned devDependency `ai@6.0.199`) using `MockLanguageModelV3` with scripted model responses in **function form** (not array form, due to off-by-one in ai@6.0.199).

## Test Files

| File                                        | What It Proves                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test/ledger.test.ts`                       | JSONL append-safe write/read, schema validation, redaction of secrets, payload truncation with attachments, lifecycle validation, BOM parsing, handoff traces with multiple run IDs, summary fixture generation.                                                                                                                               |
| `test/golden.test.ts`                       | Deterministic recording produces byte-identical fixtures across runs; recorder uses sequence IDs + fixed epoch clock; golden JSONL meta line format; re-writes are byte-stable; event key ordering is canonical; v1 fixtures rejected.                                                                                                         |
| `test/normalize.test.ts`                    | Request hashing ignores sampling settings/headers/providerOptions by default (opt-in via `hashSettings`); hash changes on prompt, tool description/schema, toolChoice, and responseFormat differences; tool order insensitive; string and object tool-call inputs hash identically; `$schema` markers stripped; settings recorded for display. |
| `test/check.test.ts`                        | `check()` accepts events, recorders, or AI SDK result objects; output/duration assertions; golden matching (write-on-first, drift detection); vitest matchers (`toBeCompletedRun`, `toHaveCalledTool`, etc.); `resultToLedgerEvents` marks derived events.                                                                                     |
| `test/replay-compare.test.ts`               | `compareRuns` passes identical runs, fails on tool output drift, `ignorePaths` with wildcards, `normalizers` rewrite outputs, side-effectful calls flagged unless allowed.                                                                                                                                                                     |
| `test/integration/aisdk-spike.test.ts`      | **Load-bearing**: middleware fires once per ToolLoopAgent loop step; tool schemas arrive as JSON Schema in params. If this fails after `ai` upgrade, recorder design must be revisited first.                                                                                                                                                  |
| `test/integration/record.test.ts`           | `recordModel` + `recordTools` capture the canonical event sequence with hashed requests and verbatim responses; tool events correlate by `toolCallId`; re-records are byte-identical; secrets in tool outputs are redacted; streamed runs consolidate at stream end; provider errors become `model.failed`.                                    |
| `test/integration/replay.test.ts`           | The flagship loop: keyless replay reproduces the trajectory through a real `ToolLoopAgent`; instruction/tool-description/schema/tool-output changes each fail with a named drift; loop growth/shrink fails with exhaustion errors; loose mode reports instead of throwing; streaming replay works; strict mode refuses hash-less fixtures.     |
| `test/integration/govern.test.ts`           | `guardTools` enforces allowlists, risk levels, budgets, and step caps with ledger evidence; inline approver approves/denies deterministically; native `needsApproval` deferral; `error-result` mode feeds violations to the model and the governed run stays recordable and replayable; replay-only side-effect blocking.                      |
| `test/integration/dogfood-replay.test.ts`   | Skips if fixture absent; after human records once (`npm run record:dogfood` with provider key), CI replays keylessly forever. Asserts trajectory shape and hashed model calls.                                                                                                                                                                 |
| `examples/refund-agent/test/replay.test.ts` | Example agent replay via `assertReplayable`; asserts trajectory with `check()` and vitest matchers; detects prompt drift (demonstrates the point).                                                                                                                                                                                             |

## The Spike's Role

`test/integration/aisdk-spike.test.ts` pins two architectural assumptions:

1. Middleware (`wrapLanguageModel`) fires once per ToolLoopAgent loop step.
2. Tool schemas arrive as JSON Schema objects in `params.tools[].inputSchema`.

If it fails after bumping `ai`, the middleware-based recorder design needs review before trusting other integration tests.

## Dogfood Suite

`test/integration/dogfood-replay.test.ts` skips itself while `test/fixtures/dogfood/refund-denied.jsonl` is absent. A human records it once:

```bash
npm run record:dogfood  # requires OPENAI_COMPAT_* env vars
```

After commit, CI replays it keylessly forever — a real-provider-shaped fixture exercising the whole stack on every run. Review the JSONL diff before committing a re-record.

## CI Matrix

- **Verify job** (fail-fast false): Node 20.x, 22.x, 24.x run `npm run verify`.
- **Node 22.x only**: Format check, coverage, package check.
- **Non-blocking ai-canary**: Reinstalls `ai@latest`, reruns integration tests as early-warning signal.

## Conventions for New Tests

- Use `deterministic: true` on recorders so fixtures are byte-stable.
- Integration tests script model responses, never call providers.
- Drift-message changes (in `src/replay/diff.ts`) should be read by a human before committing, not just substring-asserted.
- Model responses stored verbatim; everything else redacted.

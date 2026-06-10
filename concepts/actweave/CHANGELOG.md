# Changelog

## 0.2.0

Initial release of Actweave as a testing library for Vercel AI SDK agents: record, replay, and govern agents in CI without API keys.

- **`actweave/record`** — `recordModel()` wraps any `LanguageModelV3` (`doGenerate`/`doStream`) and records normalized, sha256-hashed requests plus verbatim responses; `recordingMiddleware()` for `wrapLanguageModel`; `recordTools()` records tool execution correlated by `toolCallId`; `createRecorder()` is the framework-agnostic escape hatch.
- **`actweave/replay`** — `replayModel()` serves recorded responses through your real agent, keyless. Strict mode (default) fails with a structured drift diff when prompt, tool definitions, or tool results diverge from the recording; loose mode accumulates `driftReport()`. Exhaustion errors when the loop grows or shrinks. `assertReplayable()` is the one-liner CI test. `compareRuns()` supports `ignorePaths` wildcards and normalizers.
- **`actweave/check` + `actweave/vitest`** — unified `check()` over events, recorders, or AI SDK results; trajectory, output, lifecycle, and policy assertions; `toMatchGolden` with `ACTWEAVE_UPDATE_GOLDEN=1`; vitest matchers including async `toBeReplayable`.
- **`actweave/govern`** — `guardTools()` enforces allowlists, risk caps, side-effect blocking (incl. replay-only), step/cost budgets, and approval gates before tool execution, leaving audit evidence events in the ledger; inline approver for CI determinism or native `needsApproval` deferral; `onViolation: "error-result"` keeps governed runs recordable and replayable.
- **`actweave/ledger`** — schema `actweave.ledger.v2` with first-class model request capture, deterministic mode (sequence ids, fixed-epoch clock → byte-identical re-records), canonical key-order serialization shared by live ledgers and golden fixtures, golden meta lines, redaction and payload limits. Files with the unreleased legacy `actweave.ledger.v1` schema are rejected with a re-record message.
- Zero runtime dependencies; `ai` >= 6 < 7 as an optional peer (types only); Node >= 20; ESM.

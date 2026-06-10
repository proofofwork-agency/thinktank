# Contributing

Actweave is intentionally small: a testing library with **zero runtime dependencies** that records, replays, and governs AI SDK agents. Keep it that way.

## Local checks

```bash
npm run verify        # typecheck + lint + tests + legacy-name check
npm run format:check  # prettier
npm run test:coverage
npm run pack:check    # package contents + every subpath importable from the tarball
```

## Ground rules

- **No runtime dependencies.** The `ai` package is an optional peer used for types only; `recordModel`/`replayModel` work structurally against the `LanguageModelV3` spec. `@ai-sdk/provider` types are erased at build time.
- The integration tests pin an exact `ai` version (devDependency). If you bump it, run `test/integration/aisdk-spike.test.ts` first — it pins the architectural assumptions (middleware fires per loop step; tool schemas arrive as JSON Schema). If the spike fails, the recorder design needs review before anything else.
- Determinism is a feature: anything that writes fixtures must produce byte-identical output for identical input (see `deterministic` mode). New event fields go through the canonical key order in `src/ledger/index.ts`.
- Drift messages are the product. Changes to `src/replay/diff.ts` should be reviewed by reading the failure output as a human, not just by asserting substrings.
- Model responses are stored verbatim for replay fidelity; everything else is redacted. Do not weaken redaction.
- Add focused tests: unit tests next to the module, integration tests under `test/integration/` running against the real `ai` package with scripted `MockLanguageModelV3` function-form responses (the array form is off-by-one upstream).
- Update the relevant `docs/` page and the README when changing public behavior.

## Recording the dogfood fixture

`test/fixtures/dogfood/` is recorded once with a real provider (`node scripts/record-dogfood.mjs` after `npm run build`; requires `OPENAI_COMPAT_*` env vars) and replayed keylessly in CI. Review the JSONL diff before committing a re-record.

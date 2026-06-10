# Recording

Recording happens at the `LanguageModelV3` boundary. `recordModel(model, recorder)` wraps `doGenerate`/`doStream`; every model call emits `model.called` (with the normalized, hashed request) and `model.completed` (with the verbatim response content). `recordTools(tools, recorder)` wraps each tool's `execute` and emits `tool.called` / `tool.completed` / `tool.failed`, correlated by the SDK's `toolCallId` — parallel tool calls stay distinct.

```ts
const recorder = createRecorder({ deterministic: true });
const model = recordModel(openai("gpt-5"), recorder);
const tools = recordTools(myTools, recorder, { risk: { sendEmail: "network" } });
```

If you prefer the SDK's middleware composition, `recordingMiddleware(recorder)` is the same recorder as a `LanguageModelV3Middleware` for `wrapLanguageModel({ model, middleware })`.

## The run wrapper

`recorder.run(input, fn)` brackets the run with `run.started` / `run.completed` (or `run.failed`), and records the result's `.text` as the run output:

```ts
await recorder.run("Can order 123 be refunded?", () => agent.generate({ prompt: "Can order 123 be refunded?" }));
```

## Determinism

`deterministic: true` gives sequence event ids (`evt-1`, `evt-2`, …), a fixed-epoch clock, and a stable runId. Re-recording an unchanged run produces a **byte-identical** file; a changed tool output produces a minimal diff. Options: `deterministic: { epoch, stepMs, runId }`.

## What gets hashed

Each `model.called` request stores a `sha256:` hash over the semantic core: the normalized prompt (roles + text/tool-call/tool-result parts, `providerOptions` dropped), tool definitions (sorted by name; `$schema` stripped from JSON Schemas), `toolChoice`, and `responseFormat`. Sampling settings (`temperature`, `topP`, `maxOutputTokens`, …) are recorded under `request.settings` for diff display but excluded from the hash — pass `{ hashSettings: true }` to both `recordModel` and replay if you want them strict.

## Streaming

`doStream` is teed: chunks flow to your app unchanged while the recorder consolidates them (text deltas merged, tool calls kept, finish part captured) into the same shape as a non-streamed response. Fixtures store consolidated responses only — chunk timing and granularity are intentionally out of scope. The `model.completed` event is appended when the stream finishes; an abandoned stream leaves a dangling `model.called`, which lifecycle validation flags.

## Secrets

Ledger writes redact sensitive keys (`authorization`, `api_key`, `token`, …) and token-shaped strings in inputs, outputs, payloads, and the stored request. **Model responses are stored verbatim** so replay feeds back exactly what the model said — keep secrets out of prompts and responses. Oversized payloads are truncated with attachment references.

## Approvals

AI SDK tool approvals (`needsApproval`) are SDK-side: the model sees an approval request part and, after your code resolves it, a response part in the next prompt. Recordings capture both model calls as ordinary calls; replay works as long as the test resolves approvals the same way. A divergent approval decision changes the next request and fails strict replay — which is the correct outcome. Known upstream gap: `dynamicTool` + `needsApproval` (vercel/ai#11434); `guardTools`' inline approver covers dynamic tools.

## Raw provider responses

`createRecorder({ includeRawResponses: true })` stores the full provider response under `modelResponse.raw` for debugging. Off by default — it bloats fixtures and is not needed for replay.

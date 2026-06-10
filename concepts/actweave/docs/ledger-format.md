# Ledger format (actweave.ledger.v2)

One run per JSONL file. An optional golden meta line, then one event per line in canonical key order — live ledgers (`JsonlLedgerWriter`) and golden fixtures serialize identically, so the same events are always byte-identical.

## Golden meta line

```json
{
  "__golden_meta": true,
  "schema": "actweave.golden.v2",
  "provider": "openai",
  "modelId": "gpt-5",
  "scenario": "refund-denied"
}
```

`recordedAt` is omitted by default so unchanged re-records produce zero-line diffs (`includeTimestamp: true` to opt in). `recordedWith` may carry `ai`/`actweave` versions.

## Event shape

Canonical key order: `schemaVersion, id, runId, traceId, seq, timestamp, type, parentRunId, callId, actor, name, replay, request, input, output, payload, metadata, error, modelResponse, redaction, attachments`.

Core fields:

- `schemaVersion`: `"actweave.ledger.v2"` (v1 fixtures are rejected with a re-record message; v1 was never published)
- `seq`: strictly increasing per file; `id` unique; one `traceId` per file
- `type`: `run.started|run.completed|run.failed`, `model.called|model.completed|model.failed`, `tool.called|tool.completed|tool.failed`, `governance.*`, `safety.violation`
- `callId`: pairs start/end events (model steps; tool calls use the SDK `toolCallId`)
- `replay`: `{ kind: "model"|"tool"|"handoff", sideEffect?: boolean }` on completion events

## Model request capture (`model.called`)

```jsonc
"request": {
  "hash": "sha256:…",          // over prompt + tools + toolChoice + responseFormat
  "provider": "openai", "modelId": "gpt-5",
  "prompt": [ { "role": "system", "content": "…" }, … ],   // normalized, providerOptions dropped
  "tools": [ { "name": "lookupOrder", "description": "…", "inputSchema": { … } } ], // sorted, $schema stripped
  "toolChoice": { … },
  "responseFormat": { … },
  "settings": { "temperature": 0 }  // recorded for diffs, NOT hashed by default
}
```

Tool-call inputs are normalized to parsed objects (responses carry stringified JSON; prompts carry objects — both hash identically). File parts are stored as content digests, never inline binary.

## Model response capture (`model.completed`)

```jsonc
"modelResponse": {
  "content": [ { "type": "tool-call", "toolCallId": "…", "toolName": "…", "input": "{\"orderId\":\"123\"}" } ],
  "finishReason": "tool-calls",        // unified reason
  "usage": { "inputTokens": 10, "outputTokens": 5, "totalTokens": 15 },
  "provider": "openai"
}
```

`content` is stored **verbatim** (not redacted) so replay feeds back exactly what the model produced. `raw` is included only with `includeRawResponses: true`.

## Determinism

`deterministic: true` → ids `evt-<n>`, timestamps from epoch `2020-01-01T00:00:00.000Z` advancing 1ms per event, runId `"run"`. Configurable via `{ epoch, stepMs, runId }`.

## Redaction and limits

Inputs/outputs/payloads are sanitized at write time: sensitive keys and token-shaped strings become `[REDACTED]` (recorded under `redaction`), oversized strings are truncated with `attachments` references, oversized events drop payloads with `event-limit` markers.

## Validation

`parseJsonlLedger` / `readJsonlLedger` validate schema, sequence, and uniqueness. `validateLedgerLifecycle` additionally checks start/complete pairing, single terminal event per run, and error payloads on `*.failed` events.

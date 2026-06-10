import { isRecord } from "../internal/guards.js";
import { LEDGER_SCHEMA_VERSION, type JsonValue, type LedgerEvent } from "../ledger/index.js";

export type ResultToLedgerOptions = {
  runId?: string;
  agentName?: string;
  input?: string;
};

export function looksLikeAiSdkResult(value: unknown): boolean {
  return isRecord(value) && (Array.isArray(value.steps) || typeof value.text === "string");
}

/**
 * Derive ledger events from an AI SDK GenerateTextResult-like object (steps[],
 * toolCalls/toolResults, text). Derived events carry no request hashes —
 * they support assertions, not strict replay; record with recordModel() for
 * replayable fixtures.
 */
export function resultToLedgerEvents(result: unknown, options: ResultToLedgerOptions = {}): LedgerEvent[] {
  if (!isRecord(result)) {
    throw new Error("resultToLedgerEvents: expected an AI SDK result object");
  }

  const runId = options.runId ?? "derived-run";
  const events: LedgerEvent[] = [];
  let seq = 0;

  const push = (event: Omit<LedgerEvent, "schemaVersion" | "id" | "runId" | "traceId" | "seq" | "timestamp">): void => {
    seq += 1;
    events.push({
      schemaVersion: LEDGER_SCHEMA_VERSION,
      id: `derived-${seq}`,
      runId,
      traceId: runId,
      seq,
      timestamp: new Date(Date.UTC(2020, 0, 1, 0, 0, 0, seq)).toISOString(),
      ...event,
      metadata: { ...(event.metadata ?? {}), derivedFrom: "ai-sdk-result" },
    });
  };

  push({
    type: "run.started",
    ...(options.agentName ? { actor: options.agentName, name: options.agentName } : {}),
    ...(options.input !== undefined ? { input: options.input } : {}),
  });

  const steps = Array.isArray(result.steps) ? result.steps : [result];
  let stepIndex = 0;
  for (const step of steps) {
    stepIndex += 1;
    if (!isRecord(step)) {
      continue;
    }
    const modelCallId = `${runId}:model:${stepIndex}`;
    push({ type: "model.called", callId: modelCallId, payload: { step: stepIndex } });
    push({
      type: "model.completed",
      callId: modelCallId,
      replay: { kind: "model", sideEffect: false },
      output: typeof step.text === "string" && step.text.length > 0 ? step.text : undefined,
      payload: { step: stepIndex },
      modelResponse: {
        content: deriveContent(step),
        finishReason: deriveFinishReason(step.finishReason),
      },
    });

    const toolCalls = Array.isArray(step.toolCalls) ? step.toolCalls : [];
    const toolResults = Array.isArray(step.toolResults) ? step.toolResults : [];
    for (const call of toolCalls) {
      if (!isRecord(call)) {
        continue;
      }
      const name = stringField(call.toolName) ?? stringField(call.name);
      if (!name) {
        continue;
      }
      const callId = stringField(call.toolCallId) ?? `${runId}:tool:${stepIndex}:${name}`;
      const input = (call.input ?? call.args) as JsonValue | undefined;
      push({ type: "tool.called", callId, name, input, payload: { step: stepIndex } });

      const match = toolResults.find((item) => isRecord(item) && stringField(item.toolCallId) === call.toolCallId);
      if (isRecord(match)) {
        push({
          type: "tool.completed",
          callId,
          name,
          replay: { kind: "tool", sideEffect: false },
          input,
          output: (match.output ?? match.result) as JsonValue | undefined,
          payload: { step: stepIndex },
        });
      }
    }
  }

  push({
    type: "run.completed",
    output: typeof result.text === "string" ? result.text : undefined,
  });

  return events;
}

function deriveContent(step: Record<string, unknown>): JsonValue {
  const content: JsonValue[] = [];
  if (typeof step.text === "string" && step.text.length > 0) {
    content.push({ type: "text", text: step.text });
  }
  const toolCalls = Array.isArray(step.toolCalls) ? step.toolCalls : [];
  for (const call of toolCalls) {
    if (isRecord(call)) {
      content.push({
        type: "tool-call",
        toolCallId: stringField(call.toolCallId) ?? "",
        toolName: stringField(call.toolName) ?? "",
        input: JSON.stringify(call.input ?? call.args ?? {}),
      });
    }
  }
  return content;
}

function deriveFinishReason(finishReason: unknown): string | undefined {
  if (typeof finishReason === "string") {
    return finishReason;
  }
  if (isRecord(finishReason) && typeof finishReason.unified === "string") {
    return finishReason.unified;
  }
  return undefined;
}

function stringField(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

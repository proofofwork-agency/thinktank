import type {
  LanguageModelV3,
  LanguageModelV3CallOptions,
  LanguageModelV3GenerateResult,
  LanguageModelV3Middleware,
  LanguageModelV3StreamPart,
  LanguageModelV3Usage,
} from "@ai-sdk/provider";
import { isRecord } from "../internal/guards.js";
import type { LedgerModelUsage } from "../ledger/index.js";
import { toLedgerModelRequest, type NormalizeRequestOptions } from "./normalize.js";
import type { LedgerRecorder, ModelResponseCapture } from "./recorder.js";

export type RecordModelOptions = NormalizeRequestOptions;

/**
 * Wrap a LanguageModelV3 so every doGenerate/doStream call is recorded into
 * the ledger: model.called carries the normalized+hashed request, and
 * model.completed carries the verbatim response content. The wrapped model is
 * a drop-in replacement — pass it to your real agent.
 */
export function recordModel(
  model: LanguageModelV3,
  recorder: LedgerRecorder,
  options: RecordModelOptions = {},
): LanguageModelV3 {
  return {
    specificationVersion: model.specificationVersion,
    provider: model.provider,
    modelId: model.modelId,
    get supportedUrls() {
      return model.supportedUrls;
    },
    doGenerate: async (callOptions: LanguageModelV3CallOptions) => {
      const step = recorder.beginModelStep();
      await recorder.modelCalled(step, undefined, undefined, toLedgerModelRequest(callOptions, model, options));
      try {
        const result = await model.doGenerate(callOptions);
        await recorder.modelCompleted(step, captureGenerateResult(result, model));
        return result;
      } catch (error) {
        await recorder.modelFailed(step, error);
        throw error;
      }
    },
    doStream: async (callOptions: LanguageModelV3CallOptions) => {
      const step = recorder.beginModelStep();
      await recorder.modelCalled(step, undefined, undefined, toLedgerModelRequest(callOptions, model, options));
      let result: Awaited<ReturnType<LanguageModelV3["doStream"]>>;
      try {
        result = await model.doStream(callOptions);
      } catch (error) {
        await recorder.modelFailed(step, error);
        throw error;
      }
      const parts: LanguageModelV3StreamPart[] = [];
      const recordingStream = result.stream.pipeThrough(
        new TransformStream<LanguageModelV3StreamPart, LanguageModelV3StreamPart>({
          transform(part, controller) {
            parts.push(part);
            controller.enqueue(part);
          },
          flush: async () => {
            await recorder.modelCompleted(step, consolidateStreamParts(parts, model));
          },
        }),
      );
      return { ...result, stream: recordingStream };
    },
  };
}

/**
 * The same recorder as recordModel, packaged as LanguageModelV3 middleware
 * for users who prefer wrapLanguageModel({ model, middleware }).
 */
export function recordingMiddleware(
  recorder: LedgerRecorder,
  options: RecordModelOptions = {},
): LanguageModelV3Middleware {
  return {
    specificationVersion: "v3",
    wrapGenerate: async ({ doGenerate, params, model }) => {
      const step = recorder.beginModelStep();
      await recorder.modelCalled(step, undefined, undefined, toLedgerModelRequest(params, model, options));
      try {
        const result = await doGenerate();
        await recorder.modelCompleted(step, captureGenerateResult(result, model));
        return result;
      } catch (error) {
        await recorder.modelFailed(step, error);
        throw error;
      }
    },
    wrapStream: async ({ doStream, params, model }) => {
      const step = recorder.beginModelStep();
      await recorder.modelCalled(step, undefined, undefined, toLedgerModelRequest(params, model, options));
      let result: Awaited<ReturnType<LanguageModelV3["doStream"]>>;
      try {
        result = await doStream();
      } catch (error) {
        await recorder.modelFailed(step, error);
        throw error;
      }
      const parts: LanguageModelV3StreamPart[] = [];
      const recordingStream = result.stream.pipeThrough(
        new TransformStream<LanguageModelV3StreamPart, LanguageModelV3StreamPart>({
          transform(part, controller) {
            parts.push(part);
            controller.enqueue(part);
          },
          flush: async () => {
            await recorder.modelCompleted(step, consolidateStreamParts(parts, model));
          },
        }),
      );
      return { ...result, stream: recordingStream };
    },
  };
}

function captureGenerateResult(
  result: LanguageModelV3GenerateResult,
  model: { provider?: string },
): ModelResponseCapture {
  return {
    content: result.content,
    finishReason: unifiedFinishReason(result.finishReason),
    usage: usageCapture(result.usage),
    provider: model.provider,
    raw: result,
  };
}

/**
 * Consolidate a streamed response into the same shape doGenerate returns:
 * text/reasoning deltas merged into whole parts, complete tool calls kept,
 * finishReason and usage taken from the finish part.
 */
export function consolidateStreamParts(
  parts: readonly LanguageModelV3StreamPart[],
  model: { provider?: string },
): ModelResponseCapture {
  const content: unknown[] = [];
  const textBuffers = new Map<string, { type: "text" | "reasoning"; text: string }>();
  let finishReason: string | undefined;
  let usage: LedgerModelUsage | undefined;

  for (const part of parts) {
    const record = part as Record<string, unknown>;
    switch (part.type) {
      case "text-start":
        textBuffers.set(String(record.id ?? ""), { type: "text", text: "" });
        break;
      case "reasoning-start":
        textBuffers.set(String(record.id ?? ""), { type: "reasoning", text: "" });
        break;
      case "text-delta":
      case "reasoning-delta": {
        const buffer = textBuffers.get(String(record.id ?? ""));
        if (buffer) {
          buffer.text += String(record.delta ?? "");
        }
        break;
      }
      case "text-end":
      case "reasoning-end": {
        const id = String(record.id ?? "");
        const buffer = textBuffers.get(id);
        if (buffer) {
          content.push({ type: buffer.type, text: buffer.text });
          textBuffers.delete(id);
        }
        break;
      }
      case "tool-call":
      case "tool-result":
      case "tool-approval-request":
      case "file":
      case "source":
        content.push(part);
        break;
      case "finish":
        finishReason = unifiedFinishReason(record.finishReason);
        usage = usageCapture(record.usage);
        break;
      default:
        break;
    }
  }

  for (const buffer of textBuffers.values()) {
    content.push({ type: buffer.type, text: buffer.text });
  }

  return {
    content,
    finishReason,
    usage,
    provider: model.provider,
  };
}

function unifiedFinishReason(finishReason: unknown): string | undefined {
  if (typeof finishReason === "string") {
    return finishReason;
  }
  if (isRecord(finishReason) && typeof finishReason.unified === "string") {
    return finishReason.unified;
  }
  return undefined;
}

/**
 * V3 usage is nested ({ inputTokens: { total, ... }, outputTokens: { total, ... } });
 * capture flat totals, tolerating already-flat shapes from older fixtures or mocks.
 */
function usageCapture(usage: LanguageModelV3Usage | unknown): LedgerModelUsage | undefined {
  if (!isRecord(usage)) {
    return undefined;
  }
  const capture: LedgerModelUsage = {};
  const input = tokenTotal(usage.inputTokens);
  const output = tokenTotal(usage.outputTokens);
  if (input !== undefined) capture.inputTokens = input;
  if (output !== undefined) capture.outputTokens = output;
  if (typeof usage.totalTokens === "number") {
    capture.totalTokens = usage.totalTokens;
  } else if (input !== undefined && output !== undefined) {
    capture.totalTokens = input + output;
  }
  return Object.keys(capture).length > 0 ? capture : undefined;
}

function tokenTotal(value: unknown): number | undefined {
  if (typeof value === "number") {
    return value;
  }
  if (isRecord(value) && typeof value.total === "number") {
    return value.total;
  }
  return undefined;
}

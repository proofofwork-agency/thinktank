import type {
  LanguageModelV3,
  LanguageModelV3CallOptions,
  LanguageModelV3Content,
  LanguageModelV3FinishReason,
  LanguageModelV3GenerateResult,
  LanguageModelV3StreamPart,
  LanguageModelV3Usage,
} from "@ai-sdk/provider";
import { isRecord } from "../internal/guards.js";
import type { LedgerModelResponse, LedgerModelUsage } from "../ledger/index.js";
import { normalizeRequest, type NormalizedRequest } from "../record/normalize.js";
import { formatDrift, requestDiff, settingsDiff, type RequestDrift } from "./diff.js";
import type { ReplayFixture, ReplayFixtureModelCall } from "./fixture.js";

export type ReplayMode = "strict" | "loose";

export type ReplayModelOptions = {
  /**
   * strict (default): every model call must match the recorded request hash;
   * drift throws ReplayDriftError. loose: responses are served by position
   * and drift is accumulated in driftReport().
   */
  mode?: ReplayMode;
  /** Match the hashSettings option used when recording, if any. */
  hashSettings?: boolean;
};

export class ReplayDriftError extends Error {
  readonly step: number;
  readonly expectedHash?: string;
  readonly actualHash: string;
  readonly drift: RequestDrift;

  constructor(drift: RequestDrift) {
    super(formatDrift(drift));
    this.name = "ReplayDriftError";
    this.step = drift.step;
    this.expectedHash = drift.expectedHash;
    this.actualHash = drift.actualHash;
    this.drift = drift;
  }
}

export class ReplayFixtureExhaustedError extends Error {
  readonly recordedCalls: number;
  readonly unmatchedRequest: NormalizedRequest;

  constructor(recordedCalls: number, unmatchedRequest: NormalizedRequest) {
    super(
      [
        `Replay fixture exhausted: the agent made more model calls than the fixture contains (${recordedCalls} recorded).`,
        `Unmatched request hash: ${unmatchedRequest.hash}`,
        "Hint: the agent loop grew a step (new tool round-trip, retry, or changed stop condition). Re-record the fixture if this is intentional.",
      ].join("\n"),
    );
    this.name = "ReplayFixtureExhaustedError";
    this.recordedCalls = recordedCalls;
    this.unmatchedRequest = unmatchedRequest;
  }
}

export class ReplayUnconsumedError extends Error {
  readonly consumed: number;
  readonly recorded: number;

  constructor(consumed: number, recorded: number) {
    super(
      [
        `Replay incomplete: the agent consumed ${consumed} of ${recorded} recorded model responses.`,
        "Hint: the agent loop shortened (a tool round-trip disappeared or a stop condition fired earlier). Re-record the fixture if this is intentional.",
      ].join("\n"),
    );
    this.name = "ReplayUnconsumedError";
    this.consumed = consumed;
    this.recorded = recorded;
  }
}

export interface ReplayLanguageModel extends LanguageModelV3 {
  /** Marker used by governance ("blocked-in-replay") and tooling. */
  readonly actweaveReplay: true;
  /** Number of recorded responses not yet served. */
  remaining(): number;
  /** Drift collected so far (loose mode; strict throws instead). */
  driftReport(): RequestDrift[];
  /** Throw ReplayUnconsumedError if recorded responses were left unserved. */
  assertExhausted(): void;
}

export function isReplayModel(model: unknown): model is ReplayLanguageModel {
  return isRecord(model) && model.actweaveReplay === true;
}

/**
 * Build a LanguageModelV3 that serves the fixture's recorded responses
 * through the user's real agent — keyless, deterministic CI replay. In
 * strict mode each incoming request is hashed and compared to the recorded
 * request, so prompt/tool/tool-result drift fails with a structured diff
 * instead of silently passing.
 */
export function replayModel(fixture: ReplayFixture, options: ReplayModelOptions = {}): ReplayLanguageModel {
  const mode: ReplayMode = options.mode ?? "strict";
  const calls = fixture.modelCalls;

  if (mode === "strict") {
    const missingHashes = calls.filter((call) => !call.request?.hash);
    if (missingHashes.length > 0) {
      throw new Error(
        [
          `Strict replay requires recorded request hashes, but ${missingHashes.length} of ${calls.length} model calls have none.`,
          'Record the fixture with recordModel() from actweave/record, or use mode: "loose".',
        ].join("\n"),
      );
    }
  }

  let cursor = 0;
  const drift: RequestDrift[] = [];

  function nextCall(callOptions: LanguageModelV3CallOptions): ReplayFixtureModelCall {
    const actual = normalizeRequest(callOptions, { hashSettings: options.hashSettings });
    if (cursor >= calls.length) {
      throw new ReplayFixtureExhaustedError(calls.length, actual);
    }
    const recorded = calls[cursor];
    cursor += 1;

    if (recorded.request?.hash && recorded.request.hash !== actual.hash) {
      const entry: RequestDrift = {
        step: recorded.step,
        expectedHash: recorded.request.hash,
        actualHash: actual.hash,
        differences: requestDiff(recorded.request, actual),
        settingsDifferences: settingsDiff(recorded.request, actual),
      };
      if (mode === "strict") {
        throw new ReplayDriftError(entry);
      }
      drift.push(entry);
    }
    return recorded;
  }

  return {
    actweaveReplay: true,
    specificationVersion: "v3",
    provider: "actweave-replay",
    modelId: fixture.meta?.modelId ?? calls[0]?.request?.modelId ?? "replay",
    supportedUrls: {},
    remaining() {
      return calls.length - cursor;
    },
    driftReport() {
      return [...drift];
    },
    assertExhausted() {
      if (cursor < calls.length) {
        throw new ReplayUnconsumedError(cursor, calls.length);
      }
    },
    doGenerate: async (callOptions: LanguageModelV3CallOptions) => {
      const recorded = nextCall(callOptions);
      return toGenerateResult(recorded.response);
    },
    doStream: async (callOptions: LanguageModelV3CallOptions) => {
      const recorded = nextCall(callOptions);
      return { stream: synthesizeStream(recorded.response) };
    },
  };
}

function toGenerateResult(response: LedgerModelResponse): LanguageModelV3GenerateResult {
  return {
    content: contentParts(response),
    finishReason: toV3FinishReason(response.finishReason),
    usage: toV3Usage(response.usage),
    warnings: [],
  };
}

/**
 * Synthesize a canonical chunk sequence from a consolidated recorded
 * response. Chunk granularity/timing is intentionally not reproduced —
 * fixtures store consolidated responses only.
 */
function synthesizeStream(response: LedgerModelResponse): ReadableStream<LanguageModelV3StreamPart> {
  const parts: LanguageModelV3StreamPart[] = [{ type: "stream-start", warnings: [] }];
  let textIndex = 0;

  for (const part of contentParts(response)) {
    if (isRecord(part) && (part.type === "text" || part.type === "reasoning")) {
      const id = `replay-${part.type}-${textIndex++}`;
      if (part.type === "text") {
        parts.push(
          { type: "text-start", id },
          { type: "text-delta", id, delta: String(part.text ?? "") },
          { type: "text-end", id },
        );
      } else {
        parts.push(
          { type: "reasoning-start", id },
          { type: "reasoning-delta", id, delta: String(part.text ?? "") },
          { type: "reasoning-end", id },
        );
      }
      continue;
    }
    parts.push(part as LanguageModelV3StreamPart);
  }

  parts.push({
    type: "finish",
    finishReason: toV3FinishReason(response.finishReason),
    usage: toV3Usage(response.usage),
  });

  return new ReadableStream<LanguageModelV3StreamPart>({
    start(controller) {
      for (const part of parts) {
        controller.enqueue(part);
      }
      controller.close();
    },
  });
}

function contentParts(response: LedgerModelResponse): LanguageModelV3Content[] {
  return Array.isArray(response.content) ? (response.content as unknown as LanguageModelV3Content[]) : [];
}

function toV3FinishReason(finishReason: string | undefined): LanguageModelV3FinishReason {
  const unified = finishReason ?? "stop";
  return {
    unified: isUnifiedFinishReason(unified) ? unified : "other",
    raw: finishReason,
  };
}

function isUnifiedFinishReason(value: string): value is LanguageModelV3FinishReason["unified"] {
  return ["stop", "length", "content-filter", "tool-calls", "error", "other"].includes(value);
}

function toV3Usage(usage: LedgerModelUsage | undefined): LanguageModelV3Usage {
  return {
    inputTokens: {
      total: usage?.inputTokens,
      noCache: undefined,
      cacheRead: undefined,
      cacheWrite: undefined,
    },
    outputTokens: {
      total: usage?.outputTokens,
      text: undefined,
      reasoning: undefined,
    },
  };
}

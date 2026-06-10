import { createId } from "../internal/ids.js";
import { isRecord } from "../internal/guards.js";
import {
  buildLedgerSummary,
  InMemoryLedger,
  JsonlLedgerWriter,
  type LedgerDeterministicOptions,
  type LedgerEvent,
  type LedgerEventInput,
  type LedgerModelRequest,
  type LedgerModelUsage,
  type LedgerPayloadLimit,
  type LedgerSummary,
  type LedgerWriter,
} from "../ledger/index.js";

export type RecorderToolRisk = "read" | "write" | "network" | "handoff" | "remote" | "unknown" | string;

/**
 * Captured model response in provider-agnostic shape: `content` is the
 * content-part array (text / tool-call parts), as produced at the
 * LanguageModelV3 boundary.
 */
export type ModelResponseCapture = {
  content?: unknown;
  finishReason?: string;
  usage?: LedgerModelUsage;
  provider?: string;
  raw?: unknown;
};

export type CreateRecorderOptions = {
  runId?: string;
  traceId?: string;
  parentRunId?: string;
  ledgerPath?: string;
  now?: () => Date;
  ids?: () => string;
  payloadLimit?: Partial<LedgerPayloadLimit>;
  /**
   * Deterministic ids/clock/runId so re-recording the same run produces
   * byte-identical fixtures. See LedgerWriterOptions.deterministic.
   */
  deterministic?: boolean | LedgerDeterministicOptions;
  /** Store raw provider responses inside modelResponse.raw (off by default). */
  includeRawResponses?: boolean;
};

export type LedgerRecorderCloseResult = {
  events: LedgerEvent[];
  summary: LedgerSummary;
};

export type RecorderRunOptions<T> = {
  agentName?: string;
  /** Select what to record as run.completed output. Defaults to `.text` for AI SDK results and the value itself for strings. */
  output?: (result: T) => unknown;
};

export interface LedgerRecorder {
  readonly runId: string;
  readonly traceId: string;
  /** Advance and return the model-step counter. Called once per model invocation. */
  beginModelStep(): number;
  /** Current model step (minimum 1). Tool events between model calls attach here. */
  currentStep(): number;
  /** Wrap a run: emits run.started, executes fn, then run.completed or run.failed. */
  run<T>(input: unknown, fn: () => Promise<T> | T, options?: RecorderRunOptions<T>): Promise<T>;
  runStarted(input: unknown, agentName?: string, metadata?: Record<string, unknown>): Promise<LedgerEvent>;
  modelCalled(
    step: number,
    modelInput?: unknown,
    metadata?: Record<string, unknown>,
    request?: LedgerModelRequest,
  ): Promise<LedgerEvent>;
  modelCompleted(
    step: number,
    response: ModelResponseCapture,
    metadata?: Record<string, unknown>,
  ): Promise<LedgerEvent>;
  modelFailed(step: number, error: unknown, metadata?: Record<string, unknown>): Promise<LedgerEvent>;
  toolCalled(
    step: number,
    name: string,
    input?: unknown,
    risk?: RecorderToolRisk,
    metadata?: Record<string, unknown>,
    callId?: string,
  ): Promise<LedgerEvent>;
  toolCompleted(
    step: number,
    name: string,
    output?: unknown,
    metadata?: Record<string, unknown>,
    callId?: string,
  ): Promise<LedgerEvent>;
  toolFailed(
    step: number,
    name: string,
    error: unknown,
    metadata?: Record<string, unknown>,
    callId?: string,
  ): Promise<LedgerEvent>;
  runCompleted(output?: unknown, metadata?: Record<string, unknown>): Promise<LedgerEvent>;
  runFailed(error: unknown, metadata?: Record<string, unknown>): Promise<LedgerEvent>;
  append(event: LedgerEventInput): Promise<LedgerEvent>;
  events(): readonly LedgerEvent[];
  summary(): LedgerSummary;
  close(): Promise<LedgerRecorderCloseResult>;
}

type CallState = {
  callId: string;
  input?: unknown;
  risk?: RecorderToolRisk;
};

class DefaultLedgerRecorder implements LedgerRecorder {
  readonly runId: string;
  readonly traceId: string;

  private readonly options: CreateRecorderOptions;
  private readonly modelCalls = new Map<number, string>();
  private readonly toolCalls = new Map<string, CallState>();
  private backing?: LedgerWriter;
  private stepCounter = 0;

  constructor(options: CreateRecorderOptions = {}) {
    const deterministic = options.deterministic
      ? options.deterministic === true
        ? {}
        : options.deterministic
      : undefined;
    this.runId = options.runId ?? deterministic?.runId ?? (deterministic ? "run" : createId("run"));
    this.traceId = options.traceId ?? (deterministic ? this.runId : createId("trace"));
    this.options = options;
    if (!options.ledgerPath) {
      this.backing = new InMemoryLedger(this.writerOptions());
    }
  }

  beginModelStep(): number {
    return ++this.stepCounter;
  }

  currentStep(): number {
    return Math.max(1, this.stepCounter);
  }

  async run<T>(input: unknown, fn: () => Promise<T> | T, options?: RecorderRunOptions<T>): Promise<T> {
    await this.runStarted(input, options?.agentName);
    try {
      const result = await fn();
      await this.runCompleted(options?.output ? options.output(result) : defaultRunOutput(result));
      return result;
    } catch (error) {
      await this.runFailed(error);
      throw error;
    }
  }

  async runStarted(input: unknown, agentName?: string, metadata?: Record<string, unknown>): Promise<LedgerEvent> {
    return this.append(
      ledgerInput({
        type: "run.started",
        actor: agentName,
        name: agentName,
        input,
        payload: { agent: agentName, input, parentRunId: this.options.parentRunId },
        metadata,
      }),
    );
  }

  async modelCalled(
    step: number,
    modelInput?: unknown,
    metadata?: Record<string, unknown>,
    request?: LedgerModelRequest,
  ): Promise<LedgerEvent> {
    const callId = this.modelCallId(step);
    return this.append(
      ledgerInput({
        type: "model.called",
        callId,
        input: modelInput,
        request,
        payload: { step },
        metadata,
      }),
    );
  }

  async modelCompleted(
    step: number,
    response: ModelResponseCapture,
    metadata?: Record<string, unknown>,
  ): Promise<LedgerEvent> {
    return this.append(
      ledgerInput({
        type: "model.completed",
        callId: this.modelCallId(step),
        replay: { kind: "model", sideEffect: false },
        output: textFromContent(response.content),
        payload: { step },
        metadata,
        modelResponse: {
          content: response.content,
          finishReason: response.finishReason,
          usage: response.usage,
          provider: response.provider,
          ...(this.options.includeRawResponses && response.raw !== undefined ? { raw: response.raw } : {}),
        },
      }),
    );
  }

  async modelFailed(step: number, error: unknown, metadata?: Record<string, unknown>): Promise<LedgerEvent> {
    return this.append(
      ledgerInput({
        type: "model.failed",
        callId: this.modelCallId(step),
        replay: { kind: "model", sideEffect: false },
        payload: { step },
        metadata,
        error,
      }),
    );
  }

  async toolCalled(
    step: number,
    name: string,
    input?: unknown,
    risk: RecorderToolRisk = "unknown",
    metadata?: Record<string, unknown>,
    callId?: string,
  ): Promise<LedgerEvent> {
    const resolvedCallId = callId ?? this.toolCallId(step, name);
    this.toolCalls.set(toolKey(step, name, callId), { callId: resolvedCallId, input, risk });
    return this.append(
      ledgerInput({
        type: "tool.called",
        callId: resolvedCallId,
        name,
        input,
        payload: { step, risk },
        metadata,
      }),
    );
  }

  async toolCompleted(
    step: number,
    name: string,
    output?: unknown,
    metadata?: Record<string, unknown>,
    callId?: string,
  ): Promise<LedgerEvent> {
    const state = this.toolCallState(step, name, callId);
    return this.append(
      ledgerInput({
        type: "tool.completed",
        callId: state.callId,
        name,
        replay: { kind: "tool", sideEffect: isSideEffectRisk(state.risk) },
        input: state.input,
        output,
        payload: { step, risk: state.risk },
        metadata,
      }),
    );
  }

  async toolFailed(
    step: number,
    name: string,
    error: unknown,
    metadata?: Record<string, unknown>,
    callId?: string,
  ): Promise<LedgerEvent> {
    const state = this.toolCallState(step, name, callId);
    return this.append(
      ledgerInput({
        type: "tool.failed",
        callId: state.callId,
        name,
        replay: { kind: "tool", sideEffect: isSideEffectRisk(state.risk) },
        input: state.input,
        payload: { step, risk: state.risk },
        metadata,
        error,
      }),
    );
  }

  async runCompleted(output?: unknown, metadata?: Record<string, unknown>): Promise<LedgerEvent> {
    return this.append(
      ledgerInput({
        type: "run.completed",
        output,
        metadata,
      }),
    );
  }

  async runFailed(error: unknown, metadata?: Record<string, unknown>): Promise<LedgerEvent> {
    return this.append(
      ledgerInput({
        type: "run.failed",
        metadata,
        error,
      }),
    );
  }

  async append(event: LedgerEventInput): Promise<LedgerEvent> {
    const backing = await this.ensureBacking();
    return backing.append({
      ...event,
      runId: event.runId ?? this.runId,
      traceId: event.traceId ?? this.traceId,
      parentRunId: event.parentRunId ?? this.options.parentRunId,
    });
  }

  events(): readonly LedgerEvent[] {
    return this.backing?.events() ?? [];
  }

  summary(): LedgerSummary {
    return this.backing?.summary() ?? buildLedgerSummary([]);
  }

  async close(): Promise<LedgerRecorderCloseResult> {
    if (this.backing) {
      await this.backing.close();
    }
    const events = [...this.events()];
    return {
      events,
      summary: buildLedgerSummary(events),
    };
  }

  private async ensureBacking(): Promise<LedgerWriter> {
    if (this.backing) {
      return this.backing;
    }
    if (!this.options.ledgerPath) {
      throw new Error("Recorder has no backing ledger.");
    }
    this.backing = await JsonlLedgerWriter.open(this.options.ledgerPath, this.writerOptions());
    return this.backing;
  }

  private writerOptions() {
    return {
      runId: this.runId,
      traceId: this.traceId,
      parentRunId: this.options.parentRunId,
      now: this.options.now,
      ids: this.options.ids,
      payloadLimit: this.options.payloadLimit,
      deterministic: this.options.deterministic,
    };
  }

  private modelCallId(step: number): string {
    const existing = this.modelCalls.get(step);
    if (existing) {
      return existing;
    }
    const callId = [this.runId, "model", step].join(":");
    this.modelCalls.set(step, callId);
    return callId;
  }

  private toolCallId(step: number, name: string): string {
    return [this.runId, "tool", step, name].join(":");
  }

  private toolCallState(step: number, name: string, callId?: string): CallState {
    const key = toolKey(step, name, callId);
    const state = this.toolCalls.get(key);
    if (state) {
      return state;
    }
    const fallback = {
      callId: callId ?? this.toolCallId(step, name),
      risk: "unknown",
    };
    this.toolCalls.set(key, fallback);
    return fallback;
  }
}

export function createRecorder(options?: CreateRecorderOptions): LedgerRecorder {
  return new DefaultLedgerRecorder(options);
}

function toolKey(step: number, name: string, callId?: string): string {
  return callId ?? `${step}:${name}`;
}

function isSideEffectRisk(risk: RecorderToolRisk | undefined): boolean {
  return risk !== "read";
}

function textFromContent(content: unknown): unknown {
  if (typeof content === "string") {
    return content;
  }
  if (Array.isArray(content)) {
    const text = content
      .filter((part) => isRecord(part) && part.type === "text" && typeof part.text === "string")
      .map((part) => (part as { text: string }).text)
      .join("");
    return text.length > 0 ? text : undefined;
  }
  return undefined;
}

function defaultRunOutput(result: unknown): unknown {
  if (typeof result === "string") {
    return result;
  }
  if (isRecord(result) && typeof result.text === "string") {
    return result.text;
  }
  return undefined;
}

function ledgerInput(event: { type: string; [key: string]: unknown }): LedgerEventInput {
  return event as LedgerEventInput;
}

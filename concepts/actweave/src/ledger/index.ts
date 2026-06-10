import { mkdir, readFile, rename, unlink, writeFile } from "node:fs/promises";
import { createWriteStream } from "node:fs";
import { dirname } from "node:path";
import { randomUUID } from "node:crypto";
import type { Writable } from "node:stream";
import { isRecord } from "../internal/guards.js";
import type { JsonPrimitive, JsonValue } from "../internal/json.js";

export const LEDGER_SCHEMA_VERSION = "actweave.ledger.v2" as const;
export const SUMMARY_SCHEMA_VERSION = "actweave.summary.v2" as const;
const LEGACY_LEDGER_SCHEMA_VERSION = "actweave.ledger.v1";

export type { JsonPrimitive, JsonValue } from "../internal/json.js";
// Golden fixture I/O ships on the same subpath; the module cycle is safe
// because golden.js only references these exports inside function bodies.
export { GOLDEN_SCHEMA_VERSION, readGoldenLedgerSync, writeGoldenLedgerSync } from "./golden.js";
export type { GoldenLedger, GoldenMeta, WriteGoldenOptions } from "./golden.js";
export type LedgerReplayKind = "model" | "tool" | "handoff";

export type LedgerModelUsage = {
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
};

/**
 * Captured model response. `content` is the provider-agnostic content-part
 * array (text / tool-call parts). Responses are stored verbatim so replay can
 * feed them back exactly; they are intentionally NOT redacted.
 */
export type LedgerModelResponse = {
  content?: JsonValue;
  finishReason?: string;
  usage?: LedgerModelUsage;
  provider?: string;
  raw?: unknown;
};

export type LedgerModelRequestTool = {
  name: string;
  description?: string;
  inputSchema?: JsonValue;
};

/**
 * Normalized model request captured on model.called events. `hash` covers the
 * semantic core (prompt, tools, toolChoice, responseFormat); `settings` holds
 * sampling knobs recorded for diff display only.
 */
export type LedgerModelRequest = {
  hash: string;
  provider?: string;
  modelId?: string;
  prompt?: JsonValue;
  tools?: LedgerModelRequestTool[];
  toolChoice?: JsonValue;
  responseFormat?: JsonValue;
  settings?: Record<string, JsonValue>;
};

export interface LedgerAttachmentRef {
  id: string;
  bytes: number;
  mediaType?: string;
  path?: string;
  reason: "payload-limit" | "event-limit";
}

export interface LedgerRedaction {
  paths: string[];
  count: number;
}

export interface LedgerPayloadLimit {
  maxStringBytes: number;
  maxEventBytes: number;
}

export interface LedgerEvent {
  schemaVersion: typeof LEDGER_SCHEMA_VERSION;
  id: string;
  runId: string;
  traceId: string;
  seq: number;
  timestamp: string;
  type: string;
  parentRunId?: string;
  callId?: string;
  actor?: string;
  name?: string;
  replay?: {
    kind: LedgerReplayKind;
    mode?: "capture" | "mock" | "rerun";
    sideEffect?: boolean;
  };
  request?: LedgerModelRequest;
  input?: JsonValue;
  output?: JsonValue;
  payload?: JsonValue;
  metadata?: Record<string, JsonValue>;
  error?: {
    message: string;
    name?: string;
    stack?: string;
    code?: string;
  };
  modelResponse?: LedgerModelResponse;
  redaction?: LedgerRedaction;
  attachments?: LedgerAttachmentRef[];
}

export type LedgerEventInput = Omit<
  Partial<LedgerEvent>,
  | "schemaVersion"
  | "id"
  | "seq"
  | "timestamp"
  | "redaction"
  | "attachments"
  | "input"
  | "output"
  | "payload"
  | "metadata"
  | "error"
  | "modelResponse"
> & {
  type: string;
  input?: unknown;
  output?: unknown;
  payload?: unknown;
  metadata?: Record<string, unknown>;
  error?: unknown;
  modelResponse?: unknown;
  request?: LedgerModelRequest;
};

export type LedgerDeterministicOptions = {
  epoch?: string;
  stepMs?: number;
  runId?: string;
};

export interface LedgerWriterOptions {
  runId?: string;
  traceId?: string;
  parentRunId?: string;
  now?: () => Date;
  ids?: () => string;
  payloadLimit?: Partial<LedgerPayloadLimit>;
  /**
   * Deterministic mode: sequence-based event ids and a fixed epoch clock so
   * re-recording the same run produces byte-identical JSONL (git-diff
   * hygiene). Explicit `now`/`ids`/`runId` options still take precedence.
   */
  deterministic?: boolean | LedgerDeterministicOptions;
}

export interface LedgerSummary {
  schemaVersion: typeof SUMMARY_SCHEMA_VERSION;
  sourceSchemaVersion: typeof LEDGER_SCHEMA_VERSION;
  runId: string;
  traceId: string;
  parentRunId?: string;
  eventCount: number;
  startedAt?: string;
  endedAt?: string;
  eventTypes: Record<string, number>;
  calls: Array<{
    callId?: string;
    kind?: LedgerReplayKind;
    type: string;
    name?: string;
    timestamp: string;
    sideEffect?: boolean;
  }>;
  errors: Array<{
    eventId: string;
    type: string;
    message: string;
  }>;
  redactions: {
    count: number;
    paths: string[];
  };
  attachments: LedgerAttachmentRef[];
}

export interface LedgerValidationIssue {
  line?: number;
  path: string;
  message: string;
}

export interface LedgerValidationResult {
  ok: boolean;
  events: LedgerEvent[];
  issues: LedgerValidationIssue[];
}

export interface LedgerWriter {
  readonly runId: string;
  readonly traceId: string;
  append(event: LedgerEventInput): Promise<LedgerEvent>;
  events(): readonly LedgerEvent[];
  summary(): LedgerSummary;
  close(): Promise<void>;
}

const DEFAULT_PAYLOAD_LIMIT: LedgerPayloadLimit = {
  maxStringBytes: 16 * 1024,
  maxEventBytes: 128 * 1024,
};

const DEFAULT_DETERMINISTIC_EPOCH = "2020-01-01T00:00:00.000Z";

const CANONICAL_KEY_ORDER = [
  "schemaVersion",
  "id",
  "runId",
  "traceId",
  "seq",
  "timestamp",
  "type",
  "parentRunId",
  "callId",
  "actor",
  "name",
  "replay",
  "request",
  "input",
  "output",
  "payload",
  "metadata",
  "error",
  "modelResponse",
  "redaction",
  "attachments",
] as const;

/**
 * Canonical single-line serialization with a fixed key order. Live JSONL
 * ledgers and committed golden fixtures share this serialization so the same
 * events are always byte-identical.
 */
export function canonicalEventLine(event: LedgerEvent): string {
  const source = event as unknown as Record<string, unknown>;
  const ordered: Record<string, unknown> = {};
  for (const key of CANONICAL_KEY_ORDER) {
    if (source[key] !== undefined) {
      ordered[key] = source[key];
    }
  }
  for (const key of Object.keys(source).sort()) {
    if (!(key in ordered) && source[key] !== undefined) {
      ordered[key] = source[key];
    }
  }
  return JSON.stringify(ordered);
}

function resolveDeterministic(options: LedgerWriterOptions):
  | {
      epoch: string;
      stepMs: number;
      runId?: string;
    }
  | undefined {
  if (!options.deterministic) {
    return undefined;
  }
  const config = options.deterministic === true ? {} : options.deterministic;
  return {
    epoch: config.epoch ?? DEFAULT_DETERMINISTIC_EPOCH,
    stepMs: config.stepMs ?? 1,
    runId: config.runId,
  };
}

export class InMemoryLedger implements LedgerWriter {
  readonly runId: string;
  readonly traceId: string;

  private readonly parentRunId?: string;
  private readonly now: () => Date;
  private readonly ids: () => string;
  private readonly payloadLimit: LedgerPayloadLimit;
  private readonly written: LedgerEvent[] = [];
  private seq = 0;

  constructor(options: LedgerWriterOptions = {}) {
    const deterministic = resolveDeterministic(options);
    this.runId = options.runId ?? deterministic?.runId ?? (deterministic ? "run" : randomUUID());
    this.traceId = options.traceId ?? this.runId;
    this.parentRunId = options.parentRunId;
    if (deterministic) {
      const epochMs = Date.parse(deterministic.epoch);
      if (Number.isNaN(epochMs)) {
        throw new Error(`Invalid deterministic epoch: ${deterministic.epoch}`);
      }
      let clockTick = 0;
      let idTick = 0;
      this.now = options.now ?? (() => new Date(epochMs + deterministic.stepMs * clockTick++));
      this.ids = options.ids ?? (() => `evt-${++idTick}`);
    } else {
      this.now = options.now ?? (() => new Date());
      this.ids = options.ids ?? randomUUID;
    }
    this.payloadLimit = { ...DEFAULT_PAYLOAD_LIMIT, ...options.payloadLimit };
  }

  async append(event: LedgerEventInput): Promise<LedgerEvent> {
    const prepared = prepareLedgerEvent(event, {
      ids: this.ids,
      now: this.now,
      parentRunId: this.parentRunId,
      payloadLimit: this.payloadLimit,
      runId: this.runId,
      seq: ++this.seq,
      traceId: this.traceId,
    });
    this.written.push(prepared);
    return prepared;
  }

  events(): readonly LedgerEvent[] {
    return this.written;
  }

  summary(): LedgerSummary {
    return buildLedgerSummary(this.written);
  }

  async close(): Promise<void> {
    return undefined;
  }
}

export class JsonlLedgerWriter implements LedgerWriter {
  readonly runId: string;
  readonly traceId: string;

  private readonly memory: InMemoryLedger;
  private readonly stream: Writable;
  private closed = false;

  private constructor(path: string, options: LedgerWriterOptions = {}) {
    this.memory = new InMemoryLedger(options);
    this.runId = this.memory.runId;
    this.traceId = this.memory.traceId;
    this.stream = createWriteStream(path, { flags: "a", encoding: "utf8" });
  }

  static async open(path: string, options: LedgerWriterOptions = {}): Promise<JsonlLedgerWriter> {
    await mkdir(dirname(path), { recursive: true });
    return new JsonlLedgerWriter(path, options);
  }

  async append(event: LedgerEventInput): Promise<LedgerEvent> {
    if (this.closed) {
      throw new Error("Cannot append to a closed ledger writer");
    }
    const prepared = await this.memory.append(event);
    await writeLine(this.stream, `${canonicalEventLine(prepared)}\n`);
    return prepared;
  }

  events(): readonly LedgerEvent[] {
    return this.memory.events();
  }

  summary(): LedgerSummary {
    return this.memory.summary();
  }

  async close(): Promise<void> {
    if (this.closed) {
      return;
    }
    this.closed = true;
    await new Promise<void>((resolve, reject) => {
      this.stream.end((error?: Error | null) => {
        if (error) {
          reject(error);
        } else {
          resolve();
        }
      });
    });
  }
}

export async function readJsonlLedger(path: string): Promise<LedgerValidationResult> {
  const content = await readFile(path, "utf8");
  return parseJsonlLedger(content);
}

export function parseJsonlLedger(content: string): LedgerValidationResult {
  const events: LedgerEvent[] = [];
  const issues: LedgerValidationIssue[] = [];
  const lines = content.replace(/^\uFEFF/, "").split(/\r?\n/);

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line.trim()) {
      continue;
    }
    try {
      const parsed = JSON.parse(line) as unknown;
      if (isGoldenMetaLine(parsed)) {
        continue;
      }
      const result = validateLedgerEvent(parsed);
      if (result.ok && result.event) {
        events.push(result.event);
      } else {
        issues.push(...result.issues.map((issue) => ({ ...issue, line: index + 1 })));
      }
    } catch (error) {
      issues.push({
        line: index + 1,
        path: "$",
        message: error instanceof Error ? error.message : "Invalid JSONL line",
      });
    }
  }

  return validateLedgerEvents(events, issues);
}

function isGoldenMetaLine(value: unknown): boolean {
  return isRecord(value) && value.__golden_meta === true;
}

export function validateLedgerEvents(
  events: readonly LedgerEvent[],
  baseIssues: LedgerValidationIssue[] = [],
): LedgerValidationResult {
  const issues = [...baseIssues];
  let previousTraceId: string | undefined;
  let previousSeq = 0;
  const eventIds = new Set<string>();

  events.forEach((event, index) => {
    const result = validateLedgerEvent(event);
    issues.push(...result.issues.map((issue) => ({ ...issue, line: index + 1 })));

    if (previousTraceId && event.traceId !== previousTraceId) {
      issues.push({ line: index + 1, path: "traceId", message: "All events in a ledger must share one traceId" });
    }
    if (event.seq <= previousSeq) {
      issues.push({ line: index + 1, path: "seq", message: "Event sequence must be strictly increasing" });
    }
    if (eventIds.has(event.id)) {
      issues.push({ line: index + 1, path: "id", message: "Event id must be unique" });
    }
    previousTraceId = event.traceId;
    previousSeq = event.seq;
    eventIds.add(event.id);
  });

  return {
    ok: issues.length === 0,
    events: [...events],
    issues,
  };
}

export function validateLedgerLifecycle(events: readonly LedgerEvent[]): LedgerValidationResult {
  const base = validateLedgerEvents(events);
  const issues = [...base.issues];
  const sorted = [...base.events].sort((left, right) => left.seq - right.seq);
  const eventsByRun = new Map<string, LedgerEvent[]>();

  sorted.forEach((event) => {
    const runEvents = eventsByRun.get(event.runId) ?? [];
    runEvents.push(event);
    eventsByRun.set(event.runId, runEvents);
  });

  for (const [runId, runEvents] of eventsByRun) {
    const hasStarted = runEvents.some((event) => event.type === "run.started");
    const terminals = runEvents.filter((event) => event.type === "run.completed" || event.type === "run.failed");

    if (!hasStarted && runEvents.some((event) => event.type.startsWith("run."))) {
      const first = runEvents[0];
      issues.push({
        line: first ? sorted.indexOf(first) + 1 : undefined,
        path: "type",
        message: `Run ${runId} has run events but no run.started event`,
      });
    }

    if (terminals.length > 1) {
      for (const terminal of terminals.slice(1)) {
        issues.push({
          line: sorted.indexOf(terminal) + 1,
          path: "type",
          message: `Run ${runId} has more than one terminal event`,
        });
      }
    }
  }

  const startedCalls = new Map<string, LedgerEvent>();
  for (const event of sorted) {
    const startKind = lifecycleStartKind(event.type);
    const endKind = lifecycleEndKind(event.type);
    const callKey = lifecycleCallKey(event, startKind ?? endKind);

    if (event.type.endsWith(".failed") && !event.error && !payloadHasError(event.payload)) {
      issues.push({
        line: sorted.indexOf(event) + 1,
        path: "error",
        message: `${event.type} must include error details`,
      });
    }

    if (startKind && callKey) {
      if (startedCalls.has(callKey)) {
        issues.push({
          line: sorted.indexOf(event) + 1,
          path: "callId",
          message: `Call ${callKey} has more than one start event`,
        });
      }
      startedCalls.set(callKey, event);
    }

    if (endKind && callKey) {
      if (!startedCalls.has(callKey)) {
        issues.push({
          line: sorted.indexOf(event) + 1,
          path: "callId",
          message: `${event.type} occurred before its start event`,
        });
      } else {
        startedCalls.delete(callKey);
      }
    }
  }

  for (const [callKey, event] of startedCalls) {
    issues.push({
      line: sorted.indexOf(event) + 1,
      path: "callId",
      message: `Call ${callKey} started but did not finish`,
    });
  }

  return {
    ok: issues.length === 0,
    events: [...base.events],
    issues,
  };
}

function lifecycleStartKind(type: string): LedgerReplayKind | undefined {
  if (type === "model.called") return "model";
  if (type === "tool.called") return "tool";
  if (type === "handoff.requested") return "handoff";
  return undefined;
}

function lifecycleEndKind(type: string): LedgerReplayKind | undefined {
  if (type === "model.completed" || type === "model.failed") return "model";
  if (type === "tool.completed" || type === "tool.failed") return "tool";
  if (type === "handoff.completed" || type === "handoff.failed") return "handoff";
  return undefined;
}

function lifecycleCallKey(event: LedgerEvent, kind: LedgerReplayKind | undefined): string | undefined {
  if (!kind) {
    return undefined;
  }
  return event.callId ?? [event.runId, kind, event.name ?? "unknown"].join(":");
}

function payloadHasError(payload: JsonValue | undefined): boolean {
  return isRecord(payload) && "error" in payload;
}

export function validateLedgerEvent(value: unknown): {
  ok: boolean;
  event?: LedgerEvent;
  issues: LedgerValidationIssue[];
} {
  const issues: LedgerValidationIssue[] = [];
  if (!isRecord(value)) {
    return { ok: false, issues: [{ path: "$", message: "Ledger event must be an object" }] };
  }

  requireString(value, "schemaVersion", issues);
  requireString(value, "id", issues);
  requireString(value, "runId", issues);
  requireString(value, "traceId", issues);
  requireString(value, "timestamp", issues);
  requireString(value, "type", issues);

  if (value.schemaVersion !== LEDGER_SCHEMA_VERSION) {
    issues.push({
      path: "schemaVersion",
      message:
        value.schemaVersion === LEGACY_LEDGER_SCHEMA_VERSION
          ? `${LEGACY_LEDGER_SCHEMA_VERSION} fixtures are not supported; re-record with actweave v2`
          : `Expected ${LEDGER_SCHEMA_VERSION}`,
    });
  }
  if (typeof value.seq !== "number" || !Number.isSafeInteger(value.seq) || value.seq < 1) {
    issues.push({ path: "seq", message: "seq must be a positive safe integer" });
  }
  if (typeof value.timestamp === "string" && Number.isNaN(Date.parse(value.timestamp))) {
    issues.push({ path: "timestamp", message: "timestamp must be an ISO date string" });
  }
  if ("request" in value && value.request !== undefined) {
    if (!isRecord(value.request) || typeof value.request.hash !== "string" || value.request.hash.length === 0) {
      issues.push({ path: "request", message: "request must include a non-empty string hash" });
    }
  }
  if ("redaction" in value && !isLedgerRedaction(value.redaction)) {
    issues.push({ path: "redaction", message: "redaction must contain paths and count" });
  }
  if ("attachments" in value && !isLedgerAttachments(value.attachments)) {
    issues.push({ path: "attachments", message: "attachments must be attachment refs" });
  }

  return {
    ok: issues.length === 0,
    event: issues.length === 0 ? (value as unknown as LedgerEvent) : undefined,
    issues,
  };
}

export function buildLedgerSummary(events: readonly LedgerEvent[]): LedgerSummary {
  if (events.length === 0) {
    return {
      schemaVersion: SUMMARY_SCHEMA_VERSION,
      sourceSchemaVersion: LEDGER_SCHEMA_VERSION,
      runId: "",
      traceId: "",
      eventCount: 0,
      eventTypes: {},
      calls: [],
      errors: [],
      redactions: { count: 0, paths: [] },
      attachments: [],
    };
  }

  const sorted = [...events].sort((left, right) => left.seq - right.seq);
  const eventTypes: Record<string, number> = {};
  const redactionPaths = new Set<string>();
  const attachments: LedgerAttachmentRef[] = [];
  let redactionCount = 0;

  for (const event of sorted) {
    eventTypes[event.type] = (eventTypes[event.type] ?? 0) + 1;
    if (event.redaction) {
      redactionCount += event.redaction.count;
      for (const path of event.redaction.paths) {
        redactionPaths.add(path);
      }
    }
    if (event.attachments) {
      attachments.push(...event.attachments);
    }
  }

  return {
    schemaVersion: SUMMARY_SCHEMA_VERSION,
    sourceSchemaVersion: LEDGER_SCHEMA_VERSION,
    runId: sorted[0].runId,
    traceId: sorted[0].traceId,
    parentRunId: sorted[0].parentRunId,
    eventCount: sorted.length,
    startedAt: sorted[0].timestamp,
    endedAt: sorted.at(-1)?.timestamp,
    eventTypes,
    calls: sorted
      .filter((event) => event.callId || event.replay)
      .map((event) => ({
        callId: event.callId,
        kind: event.replay?.kind,
        type: event.type,
        name: event.name,
        timestamp: event.timestamp,
        sideEffect: event.replay?.sideEffect,
      })),
    errors: sorted
      .filter((event) => event.error)
      .map((event) => ({
        eventId: event.id,
        type: event.type,
        message: event.error?.message ?? "Unknown error",
      })),
    redactions: {
      count: redactionCount,
      paths: [...redactionPaths].sort(),
    },
    attachments,
  };
}

export async function writeLedgerSummary(path: string, events: readonly LedgerEvent[]): Promise<LedgerSummary> {
  const summary = buildLedgerSummary(events);
  await mkdir(dirname(path), { recursive: true });
  const temporaryPath = `${path}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(temporaryPath, `${JSON.stringify(summary, null, 2)}\n`, "utf8");
  try {
    await rename(temporaryPath, path);
  } catch (error) {
    try {
      await unlink(temporaryPath);
    } catch {
      // ignore cleanup failure
    }
    throw error;
  }
  return summary;
}

function prepareLedgerEvent(
  event: LedgerEventInput,
  context: {
    ids: () => string;
    now: () => Date;
    parentRunId?: string;
    payloadLimit: LedgerPayloadLimit;
    runId: string;
    seq: number;
    traceId: string;
  },
): LedgerEvent {
  const redaction = { paths: [] as string[], count: 0 };
  const attachments: LedgerAttachmentRef[] = [];
  const prepared: LedgerEvent = {
    schemaVersion: LEDGER_SCHEMA_VERSION,
    id: context.ids(),
    runId: event.runId ?? context.runId,
    traceId: event.traceId ?? context.traceId,
    seq: context.seq,
    timestamp: context.now().toISOString(),
    type: event.type,
    ...((event.parentRunId ?? context.parentRunId) ? { parentRunId: event.parentRunId ?? context.parentRunId } : {}),
    ...(event.callId ? { callId: event.callId } : {}),
    ...(event.actor ? { actor: event.actor } : {}),
    ...(event.name ? { name: event.name } : {}),
    ...(event.replay ? { replay: event.replay } : {}),
    ...(event.modelResponse ? { modelResponse: event.modelResponse } : {}),
  };

  if (event.request !== undefined) {
    const sanitized = sanitizeValue(
      event.request,
      "request",
      redaction,
      attachments,
      context.payloadLimit,
      context.ids,
    );
    prepared.request = sanitized as unknown as LedgerModelRequest;
  }

  assignSanitized(prepared, "input", event.input, redaction, attachments, context.payloadLimit, context.ids);
  assignSanitized(prepared, "output", event.output, redaction, attachments, context.payloadLimit, context.ids);
  assignSanitized(prepared, "payload", event.payload, redaction, attachments, context.payloadLimit, context.ids);
  assignSanitized(prepared, "metadata", event.metadata, redaction, attachments, context.payloadLimit, context.ids);
  if (event.error !== undefined) {
    prepared.error = normalizeError(event.error);
  }

  let eventBytes = byteLength(prepared);
  if (eventBytes > context.payloadLimit.maxEventBytes) {
    for (const key of ["payload", "input", "output", "metadata"] as const) {
      const value = prepared[key];
      if (value === undefined) {
        continue;
      }
      attachments.push({
        id: context.ids(),
        bytes: byteLength(value),
        reason: "event-limit",
      });
      prepared[key] = { __actweave: "omitted", reason: "event-limit" };
      eventBytes = byteLength(prepared);
      if (eventBytes <= context.payloadLimit.maxEventBytes) {
        break;
      }
    }
  }

  if (redaction.count > 0) {
    prepared.redaction = {
      count: redaction.count,
      paths: [...new Set(redaction.paths)].sort(),
    };
  }
  if (attachments.length > 0) {
    prepared.attachments = attachments;
  }

  const validation = validateLedgerEvent(prepared);
  if (!validation.ok) {
    throw new Error(`Invalid ledger event: ${validation.issues.map((issue) => issue.message).join(", ")}`);
  }

  return prepared;
}

function assignSanitized(
  event: LedgerEvent,
  key: "input" | "output" | "payload" | "metadata",
  value: unknown,
  redaction: { paths: string[]; count: number },
  attachments: LedgerAttachmentRef[],
  payloadLimit: LedgerPayloadLimit,
  ids: () => string,
): void {
  if (value === undefined) {
    return;
  }
  const sanitized = sanitizeValue(value, key, redaction, attachments, payloadLimit, ids);
  if (key === "metadata") {
    event.metadata = isRecord(sanitized) ? (sanitized as Record<string, JsonValue>) : { value: sanitized };
    return;
  }
  event[key] = sanitized;
}

function sanitizeValue(
  value: unknown,
  path: string,
  redaction: { paths: string[]; count: number },
  attachments: LedgerAttachmentRef[],
  payloadLimit: LedgerPayloadLimit,
  ids: () => string,
): JsonValue {
  if (value === null || typeof value === "number" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "bigint") {
    return value.toString();
  }
  if (typeof value === "string") {
    if (looksSensitiveString(value)) {
      redaction.paths.push(path);
      redaction.count += 1;
      return "[REDACTED]";
    }
    return limitString(value, path, attachments, payloadLimit, ids);
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (value instanceof Error) {
    return normalizeError(value) as unknown as JsonValue;
  }
  if (Array.isArray(value)) {
    return value.map((item, index) =>
      sanitizeValue(item, `${path}[${index}]`, redaction, attachments, payloadLimit, ids),
    );
  }
  if (isRecord(value)) {
    const output: Record<string, JsonValue> = {};
    for (const [key, child] of Object.entries(value)) {
      const childPath = `${path}.${key}`;
      if (isSensitiveKey(key)) {
        redaction.paths.push(childPath);
        redaction.count += 1;
        output[key] = "[REDACTED]";
      } else {
        output[key] = sanitizeValue(child, childPath, redaction, attachments, payloadLimit, ids);
      }
    }
    return output;
  }
  if (typeof value === "symbol") {
    return `[Symbol: ${(value as symbol).description ?? ""}]`;
  }
  return String(value);
}

function limitString(
  value: string,
  path: string,
  attachments: LedgerAttachmentRef[],
  payloadLimit: LedgerPayloadLimit,
  ids: () => string,
): JsonValue {
  const bytes = Buffer.byteLength(value, "utf8");
  if (bytes <= payloadLimit.maxStringBytes) {
    return value;
  }

  attachments.push({
    id: ids(),
    bytes,
    reason: "payload-limit",
  });

  return {
    __actweave: "truncated",
    path,
    bytes,
    preview: [...value].slice(0, Math.min(256, Math.ceil(payloadLimit.maxStringBytes / 4))).join(""),
  };
}

function normalizeError(error: unknown): LedgerEvent["error"] {
  if (error instanceof Error) {
    return {
      message: error.message,
      name: error.name,
      stack: error.stack,
      code: "code" in error ? String((error as Record<string, unknown>).code) : undefined,
    };
  }
  if (isRecord(error)) {
    const message = typeof error.message === "string" ? error.message : JSON.stringify(error);
    return {
      message,
      ...(typeof error.name === "string" ? { name: error.name } : {}),
      ...(typeof error.stack === "string" ? { stack: error.stack } : {}),
      ...(error.code !== undefined ? { code: String(error.code) } : {}),
    };
  }
  return {
    message: String(error),
  };
}

function isSensitiveKey(key: string): boolean {
  return /^(authorization|proxy-authorization|cookie|set-cookie|x-api-key|api[-_]?key|token|access[-_]?token|refresh[-_]?token|secret|password|passwd|private[-_]?key|client[-_]?secret)$/i.test(
    key,
  );
}

function looksSensitiveString(value: string): boolean {
  return (
    /\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}/i.test(value) ||
    /\b(sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9_]{12,})\b/.test(value)
  );
}

function requireString(value: Record<string, unknown>, path: string, issues: LedgerValidationIssue[]): void {
  if (typeof value[path] !== "string" || value[path].length === 0) {
    issues.push({ path, message: `${path} must be a non-empty string` });
  }
}

function isLedgerRedaction(value: unknown): value is LedgerRedaction {
  return (
    isRecord(value) &&
    typeof value.count === "number" &&
    Array.isArray(value.paths) &&
    value.paths.every((path) => typeof path === "string")
  );
}

function isLedgerAttachments(value: unknown): value is LedgerAttachmentRef[] {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        isRecord(item) &&
        typeof item.id === "string" &&
        typeof item.bytes === "number" &&
        (item.reason === "payload-limit" || item.reason === "event-limit"),
    )
  );
}

function byteLength(value: unknown): number {
  return Buffer.byteLength(JSON.stringify(value), "utf8");
}

async function writeLine(stream: Writable, line: string): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const done = (error?: Error | null) => {
      if (error) {
        reject(error);
      } else {
        resolve();
      }
    };
    if (!stream.write(line, "utf8", done)) {
      return;
    }
    stream.once("drain", resolve);
    stream.once("error", reject);
  });
}

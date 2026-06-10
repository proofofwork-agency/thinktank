import { readFile } from "node:fs/promises";
import { isRecord } from "../internal/guards.js";
import {
  parseJsonlLedger,
  validateLedgerLifecycle,
  type LedgerEvent,
  type LedgerModelRequest,
  type LedgerModelResponse,
} from "../ledger/index.js";
import type { GoldenMeta } from "../ledger/golden.js";

export type ReplayFixtureModelCall = {
  step: number;
  callId?: string;
  request?: LedgerModelRequest;
  response: LedgerModelResponse;
};

export type ReplayFixture = {
  events: LedgerEvent[];
  modelCalls: ReplayFixtureModelCall[];
  meta?: GoldenMeta;
  /** run.started input, when the fixture was recorded with recorder.run(). */
  input?: unknown;
  /** run.completed output, when present. */
  runOutput?: unknown;
};

export type ReplayFixtureSource = string | readonly LedgerEvent[] | ReplayFixture;

export class ReplayFixtureError extends Error {
  readonly issues: string[];

  constructor(message: string, issues: string[] = []) {
    super(issues.length > 0 ? `${message}\n${issues.map((issue) => `  - ${issue}`).join("\n")}` : message);
    this.name = "ReplayFixtureError";
    this.issues = issues;
  }
}

export function isReplayFixture(value: unknown): value is ReplayFixture {
  return isRecord(value) && Array.isArray(value.events) && Array.isArray(value.modelCalls);
}

/**
 * Load and validate a replay fixture from a JSONL path or an event array.
 * Pairs model.called/model.completed by callId into the ordered model-call
 * script that replayModel() serves.
 */
export async function loadReplayFixture(source: ReplayFixtureSource): Promise<ReplayFixture> {
  if (isReplayFixture(source)) {
    return source;
  }

  let events: LedgerEvent[];
  let meta: GoldenMeta | undefined;

  if (typeof source === "string") {
    const content = await readFile(source, "utf8");
    meta = extractMeta(content);
    const parsed = parseJsonlLedger(content);
    if (!parsed.ok) {
      throw new ReplayFixtureError(
        `Replay fixture ${source} failed validation`,
        parsed.issues.map((issue) => `${issue.path}${issue.line ? ` (line ${issue.line})` : ""}: ${issue.message}`),
      );
    }
    events = parsed.events;
  } else {
    const validated = validateLedgerLifecycle(source);
    if (!validated.ok) {
      throw new ReplayFixtureError(
        "Replay fixture events failed lifecycle validation",
        validated.issues.map((issue) => `${issue.path}: ${issue.message}`),
      );
    }
    events = validated.events;
  }

  const modelCalls = pairModelCalls(events);

  return {
    events,
    modelCalls,
    ...(meta ? { meta } : {}),
    input: events.find((event) => event.type === "run.started")?.input,
    runOutput: events.find((event) => event.type === "run.completed")?.output,
  };
}

function pairModelCalls(events: readonly LedgerEvent[]): ReplayFixtureModelCall[] {
  const calls: ReplayFixtureModelCall[] = [];
  const pendingByCallId = new Map<string, { step: number; request?: LedgerModelRequest }>();
  const issues: string[] = [];
  let stepCounter = 0;

  for (const event of events) {
    if (event.type === "model.called") {
      stepCounter += 1;
      pendingByCallId.set(event.callId ?? `step-${stepCounter}`, {
        step: stepCounter,
        request: event.request,
      });
    }
    if (event.type === "model.completed") {
      const key = event.callId ?? `step-${stepCounter}`;
      const pending = pendingByCallId.get(key);
      pendingByCallId.delete(key);
      if (!event.modelResponse || event.modelResponse.content === undefined) {
        issues.push(
          `model.completed (callId ${event.callId ?? "unknown"}) has no modelResponse.content — re-record this fixture with recordModel() from actweave/record`,
        );
        continue;
      }
      calls.push({
        step: pending?.step ?? stepCounter,
        callId: event.callId,
        request: pending?.request,
        response: event.modelResponse,
      });
    }
  }

  if (issues.length > 0) {
    throw new ReplayFixtureError("Replay fixture is missing recorded model responses", issues);
  }
  if (calls.length === 0) {
    throw new ReplayFixtureError(
      "Replay fixture contains no model.completed events with recorded responses — record a run with recordModel() first",
    );
  }

  return calls;
}

function extractMeta(content: string): GoldenMeta | undefined {
  for (const line of content.replace(/^\uFEFF/, "").split(/\r?\n/)) {
    if (!line.trim()) {
      continue;
    }
    try {
      const parsed = JSON.parse(line) as unknown;
      if (isRecord(parsed) && parsed.__golden_meta === true) {
        const { __golden_meta: _marker, ...rest } = parsed;
        return rest as GoldenMeta;
      }
    } catch {
      return undefined;
    }
    return undefined;
  }
  return undefined;
}

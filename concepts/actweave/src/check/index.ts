import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { containsOrdered, matchesPartial, sameJson } from "../internal/compare.js";
import {
  buildLedgerSummary,
  parseJsonlLedger,
  validateLedgerLifecycle,
  type LedgerEvent,
  type LedgerSummary,
  type LedgerValidationResult,
} from "../ledger/index.js";
import { readGoldenLedgerSync, writeGoldenLedgerSync, type WriteGoldenOptions } from "../ledger/golden.js";
import { looksLikeAiSdkResult, resultToLedgerEvents } from "./result.js";

export type LedgerCheckSource = string | readonly LedgerEvent[];

/** Anything check() can assert over: events, a recorder, or an AI SDK result. */
export type CheckSource = readonly LedgerEvent[] | { events(): readonly LedgerEvent[] } | unknown;

export type MatchGoldenOptions = {
  /** Comparison options forwarded to compareLedgerEvents. */
  allowSideEffects?: boolean;
  compareOutputs?: boolean;
  /** Golden write options used when creating or updating the fixture. */
  write?: WriteGoldenOptions;
};

export type LedgerCheck = {
  completed(): LedgerCheck;
  called(toolName: string): LedgerCheck;
  notCalled(toolName: string): LedgerCheck;
  calledTimes(toolName: string, count: number): LedgerCheck;
  calledWith(toolName: string, expectedInput: unknown | ((input: unknown) => boolean)): LedgerCheck;
  hasEvent(type: string): LedgerCheck;
  eventSequence(types: readonly string[]): LedgerCheck;
  toolCallOrder(toolNames: readonly string[]): LedgerCheck;
  noErrors(): LedgerCheck;
  validLifecycle(): LedgerCheck;
  outputContains(text: string): LedgerCheck;
  outputMatches(pattern: RegExp): LedgerCheck;
  /** Wall-clock duration check — meaningless for deterministic recordings. */
  durationBelow(milliseconds: number): LedgerCheck;
  /** Assert a governance.tool.blocked / safety.violation event, optionally with a specific code. */
  policyEnforced(code?: string): LedgerCheck;
  /** Assert an approval for the given tool was resolved as denied. */
  approvalDenied(toolName: string): LedgerCheck;
  /**
   * Compare against a committed golden fixture. Writes the fixture when it
   * does not exist yet; set ACTWEAVE_UPDATE_GOLDEN=1 to rewrite it.
   */
  toMatchGolden(path: string, options?: MatchGoldenOptions): LedgerCheck;
};

/**
 * Unified assertion entry point: accepts a ledger event array, anything with
 * an events() method (recorders, ledgers), or an AI SDK result object
 * (converted via resultToLedgerEvents).
 */
export function check(source: CheckSource): LedgerCheck {
  return checkLedger(resolveCheckSource(source));
}

export function resolveCheckSource(source: CheckSource): readonly LedgerEvent[] {
  if (Array.isArray(source)) {
    return source as readonly LedgerEvent[];
  }
  if (source && typeof source === "object" && typeof (source as { events?: unknown }).events === "function") {
    return (source as { events(): readonly LedgerEvent[] }).events();
  }
  if (looksLikeAiSdkResult(source)) {
    return resultToLedgerEvents(source);
  }
  throw new Error(
    "check(): unsupported source — pass LedgerEvent[], a recorder/ledger with events(), or an AI SDK result",
  );
}

export type LedgerMatchOptions = {
  allowSideEffects?: boolean;
  compareOutputs?: boolean;
};

export type LedgerMatchDiff = {
  pass: boolean;
  eventTypes: SequenceDiff<string>;
  toolCallSequence: SequenceDiff<string>;
  toolCallInputs: ValueSequenceDiff;
  toolOutputs: ValueSequenceDiff;
  runOutput: ValueDiff;
  errors: SequenceDiff<string>;
  issues: string[];
};

export type SequenceDiff<T> = {
  pass: boolean;
  expected: T[];
  actual: T[];
  message?: string;
};

export type ValueSequenceDiff = {
  pass: boolean;
  expected: unknown[];
  actual: unknown[];
  mismatches: Array<{ index: number; expected: unknown; actual: unknown }>;
  message?: string;
};

export type ValueDiff = {
  pass: boolean;
  expected: unknown;
  actual: unknown;
  message?: string;
};

function fail(message: string): never {
  throw new Error(`Actweave ledger check failed: ${message}`);
}

export async function loadLedgerEvents(source: LedgerCheckSource): Promise<LedgerValidationResult> {
  if (typeof source !== "string") {
    return validateLedgerLifecycle(source);
  }
  const content = await readFile(source, "utf8");
  const parsed = parseJsonlLedger(content);
  const lifecycle = validateLedgerLifecycle(parsed.events);
  return {
    ok: parsed.ok && lifecycle.ok,
    events: lifecycle.events,
    issues: [...parsed.issues, ...lifecycle.issues],
  };
}

export function checkLedger(events: readonly LedgerEvent[]): LedgerCheck {
  return {
    completed() {
      if (!events.some((event) => event.type === "run.completed")) {
        fail(`expected a run.completed event.`);
      }
      return this;
    },
    called(toolName) {
      if (!hasToolCall(events, toolName)) {
        fail(`expected tool "${toolName}" to be called.`);
      }
      return this;
    },
    notCalled(toolName) {
      if (hasToolCall(events, toolName)) {
        fail(`expected tool "${toolName}" not to be called.`);
      }
      return this;
    },
    calledTimes(toolName, count) {
      const actual = toolCalls(events, toolName).length;
      if (actual !== count) {
        fail(`expected tool "${toolName}" to be called ${count} times, received ${actual}.`);
      }
      return this;
    },
    calledWith(toolName, expectedInput) {
      const calls = toolCalls(events, toolName);
      if (!calls.some((event) => matchesPartial(event.input, expectedInput))) {
        fail(
          `expected tool "${toolName}" to be called with matching input.\n  actual inputs: ${JSON.stringify(calls.map((call) => call.input))}`,
        );
      }
      return this;
    },
    hasEvent(type) {
      if (!events.some((event) => event.type === type)) {
        fail(`expected event "${type}" to be emitted.`);
      }
      return this;
    },
    eventSequence(types) {
      const actual = events.map((event) => event.type);
      if (!containsOrdered(actual, types)) {
        fail(`expected event sequence ${JSON.stringify(types)} in ${JSON.stringify(actual)}.`);
      }
      return this;
    },
    toolCallOrder(toolNames) {
      const actual = toolCalls(events).map((event) => event.name ?? "");
      if (!containsOrdered(actual, toolNames)) {
        fail(`expected tool call order ${JSON.stringify(toolNames)} in ${JSON.stringify(actual)}.`);
      }
      return this;
    },
    noErrors() {
      const errors = events.filter((event) => event.error || event.type.endsWith(".failed"));
      if (errors.length > 0) {
        fail(`expected ledger to have no errors, received ${errors.length} error events.`);
      }
      return this;
    },
    validLifecycle() {
      const validation = validateLedgerLifecycle(events);
      if (!validation.ok) {
        fail(`expected valid event lifecycle, received ${validation.issues.map((issue) => issue.message).join("; ")}.`);
      }
      return this;
    },
    outputContains(text) {
      const output = runOutputFrom(events);
      if (typeof output !== "string" || !output.includes(text)) {
        fail(`expected run output to contain ${JSON.stringify(text)}, received ${JSON.stringify(output)}.`);
      }
      return this;
    },
    outputMatches(pattern) {
      const output = runOutputFrom(events);
      if (typeof output !== "string" || !pattern.test(output)) {
        fail(`expected run output to match ${pattern}, received ${JSON.stringify(output)}.`);
      }
      return this;
    },
    durationBelow(milliseconds) {
      if (events.length === 0) {
        fail("expected events to measure duration, received an empty ledger.");
      }
      const first = Date.parse(events[0].timestamp);
      const last = Date.parse(events[events.length - 1].timestamp);
      const duration = last - first;
      if (!(duration < milliseconds)) {
        fail(`expected run duration below ${milliseconds}ms, received ${duration}ms.`);
      }
      return this;
    },
    policyEnforced(code) {
      const blocked = events.filter(
        (event) => event.type === "governance.tool.blocked" || event.type === "safety.violation",
      );
      if (blocked.length === 0) {
        fail("expected a governance.tool.blocked or safety.violation event.");
      }
      if (code !== undefined && !blocked.some((event) => payloadCode(event) === code)) {
        fail(
          `expected a policy violation with code ${JSON.stringify(code)}, received [${blocked
            .map((event) => JSON.stringify(payloadCode(event)))
            .join(", ")}].`,
        );
      }
      return this;
    },
    approvalDenied(toolName) {
      const denied = events.some(
        (event) =>
          event.type === "governance.approval.resolved" &&
          event.name === toolName &&
          isRecordPayload(event.payload) &&
          event.payload.status === "denied",
      );
      if (!denied) {
        fail(`expected approval for tool "${toolName}" to be denied.`);
      }
      return this;
    },
    toMatchGolden(path, options = {}) {
      const update = process.env.ACTWEAVE_UPDATE_GOLDEN === "1";
      if (update || !existsSync(path)) {
        writeGoldenLedgerSync(path, events, options.write);
        return this;
      }
      const golden = readGoldenLedgerSync(path);
      if (!golden.validation.ok) {
        fail(
          `golden fixture ${path} failed validation: ${golden.validation.issues.map((issue) => issue.message).join("; ")}.`,
        );
      }
      const diff = compareLedgerEvents(golden.events, events, {
        allowSideEffects: options.allowSideEffects,
        compareOutputs: options.compareOutputs,
      });
      if (!diff.pass) {
        fail(
          `run does not match golden fixture ${path}:\n${diff.issues.map((issue) => `  - ${issue}`).join("\n")}\n  (set ACTWEAVE_UPDATE_GOLDEN=1 to update)`,
        );
      }
      return this;
    },
  };
}

function payloadCode(event: LedgerEvent): string | undefined {
  return isRecordPayload(event.payload) && typeof event.payload.code === "string" ? event.payload.code : undefined;
}

function isRecordPayload(payload: unknown): payload is Record<string, unknown> {
  return typeof payload === "object" && payload !== null && !Array.isArray(payload);
}

export async function assertLedgerMatches(
  expectedSource: LedgerCheckSource,
  actualSource: LedgerCheckSource,
  options: LedgerMatchOptions = {},
): Promise<void> {
  const expected = await loadLedgerEvents(expectedSource);
  const actual = await loadLedgerEvents(actualSource);
  const issues = ledgerValidationIssues("expected", expected).concat(ledgerValidationIssues("actual", actual));
  if (issues.length > 0) {
    throw new Error(`Actweave ledger match failed:\n${issues.map((issue) => `  - ${issue}`).join("\n")}`);
  }

  const diff = compareLedgerEvents(expected.events, actual.events, options);
  if (!diff.pass) {
    throw new Error(`Actweave ledger match failed:\n${diff.issues.map((issue) => `  - ${issue}`).join("\n")}`);
  }
}

export function compareLedgerEvents(
  expected: readonly LedgerEvent[],
  actual: readonly LedgerEvent[],
  options: LedgerMatchOptions = {},
): LedgerMatchDiff {
  const eventTypes = sequenceDiff(
    expected.map((event) => event.type),
    actual.map((event) => event.type),
    "Event type sequence differs",
  );
  const toolCallSequence = sequenceDiff(
    toolCalls(expected).map((event) => event.name ?? ""),
    toolCalls(actual).map((event) => event.name ?? ""),
    "Tool call sequence differs",
  );
  const toolCallInputs = valueSequenceDiff(
    toolCalls(expected).map((event) => event.input),
    toolCalls(actual).map((event) => event.input),
    "Tool call inputs differ",
  );
  const toolOutputs = valueSequenceDiff(
    toolCompletions(expected).map((event) => event.output),
    toolCompletions(actual).map((event) => event.output),
    "Tool outputs differ",
  );
  const runOutput = valueDiff(runOutputFrom(expected), runOutputFrom(actual), "Run output differs");
  const errors = sequenceDiff(errorMessages(expected), errorMessages(actual), "Replay errors differ");

  const issues = [
    eventTypes.message,
    toolCallSequence.message,
    toolCallInputs.message,
    ...(options.compareOutputs === false ? [] : [toolOutputs.message, runOutput.message]),
    errors.message,
    ...(options.allowSideEffects === true ? [] : sideEffectIssues(actual)),
  ].filter((issue): issue is string => Boolean(issue));

  return {
    pass: issues.length === 0,
    eventTypes,
    toolCallSequence,
    toolCallInputs,
    toolOutputs,
    runOutput,
    errors,
    issues,
  };
}

export function ledgerSummary(events: readonly LedgerEvent[]): LedgerSummary {
  return buildLedgerSummary(events);
}

function ledgerValidationIssues(label: string, validation: LedgerValidationResult): string[] {
  return validation.ok ? [] : validation.issues.map((issue) => `${label} ledger: ${issue.message}`);
}

function hasToolCall(events: readonly LedgerEvent[], toolName: string): boolean {
  return toolCalls(events, toolName).length > 0;
}

function toolCalls(events: readonly LedgerEvent[], toolName?: string): LedgerEvent[] {
  return events.filter((event) => event.type === "tool.called" && (!toolName || event.name === toolName));
}

function toolCompletions(events: readonly LedgerEvent[]): LedgerEvent[] {
  return events.filter((event) => event.type === "tool.completed");
}

function runOutputFrom(events: readonly LedgerEvent[]): unknown {
  return events.find((event) => event.type === "run.completed")?.output;
}

function errorMessages(events: readonly LedgerEvent[]): string[] {
  return events.filter((event) => event.error).map((event) => event.error?.message ?? "");
}

function sideEffectIssues(events: readonly LedgerEvent[]): string[] {
  return events
    .filter((event) => event.replay?.sideEffect)
    .map((event) => `side-effectful call '${event.name ?? event.type}' found; pass allowSideEffects: true to permit`);
}

function sequenceDiff<T>(expected: T[], actual: T[], message: string): SequenceDiff<T> {
  const pass = expected.length === actual.length && expected.every((value, index) => Object.is(value, actual[index]));
  return {
    pass,
    expected,
    actual,
    ...(pass ? {} : { message: `${message}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}` }),
  };
}

function valueSequenceDiff(expected: unknown[], actual: unknown[], message: string): ValueSequenceDiff {
  const mismatches: Array<{ index: number; expected: unknown; actual: unknown }> = [];
  const length = Math.min(expected.length, actual.length);
  for (let index = 0; index < length; index += 1) {
    if (!sameJson(expected[index], actual[index])) {
      mismatches.push({ index, expected: expected[index], actual: actual[index] });
    }
  }
  const pass = expected.length === actual.length && mismatches.length === 0;
  return {
    pass,
    expected,
    actual,
    mismatches,
    ...(pass ? {} : { message: `${message} at ${mismatches.length} position(s)` }),
  };
}

function valueDiff(expected: unknown, actual: unknown, message: string): ValueDiff {
  const pass = sameJson(expected, actual);
  return {
    pass,
    expected,
    actual,
    ...(pass ? {} : { message: `${message}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}` }),
  };
}

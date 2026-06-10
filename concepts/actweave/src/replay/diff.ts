import { isRecord } from "../internal/guards.js";
import { sameJson, stableStringify } from "../internal/compare.js";
import type { LedgerModelRequest } from "../ledger/index.js";
import type { NormalizedRequest } from "../record/normalize.js";

export type RequestDrift = {
  step: number;
  expectedHash?: string;
  actualHash: string;
  differences: string[];
  /** Sampling-knob deltas — informational, never part of the hash by default. */
  settingsDifferences: string[];
};

/**
 * Human-oriented structural diff between the recorded request and the live
 * request. This message is the product: when a fixture drifts, the developer
 * should learn from the error text exactly what changed — prompt text, a tool
 * description, a schema, toolChoice — without opening the fixture.
 */
export function requestDiff(expected: LedgerModelRequest | undefined, actual: NormalizedRequest): string[] {
  if (!expected) {
    return ["fixture has no recorded request for this step (recorded before request capture existed)"];
  }
  const differences: string[] = [];

  diffPrompts(asArray(expected.prompt), asArray(actual.prompt), differences);
  diffTools(expected.tools ?? [], actual.tools ?? [], differences);

  if (!sameJson(expected.toolChoice, actual.toolChoice)) {
    differences.push(`toolChoice differs: recorded ${short(expected.toolChoice)}, actual ${short(actual.toolChoice)}`);
  }
  if (!sameJson(expected.responseFormat, actual.responseFormat)) {
    differences.push(
      `responseFormat differs: recorded ${short(expected.responseFormat)}, actual ${short(actual.responseFormat)}`,
    );
  }

  if (differences.length === 0) {
    differences.push(
      "request core differs but no field-level difference was isolated — compare the fixture's recorded request manually",
    );
  }
  return differences;
}

export function settingsDiff(expected: LedgerModelRequest | undefined, actual: NormalizedRequest): string[] {
  const expectedSettings = expected?.settings ?? {};
  const actualSettings = actual.settings ?? {};
  const keys = new Set([...Object.keys(expectedSettings), ...Object.keys(actualSettings)]);
  const lines: string[] = [];
  for (const key of [...keys].sort()) {
    if (!sameJson(expectedSettings[key], actualSettings[key])) {
      lines.push(`settings.${key}: recorded ${short(expectedSettings[key])}, actual ${short(actualSettings[key])}`);
    }
  }
  return lines;
}

export function formatDrift(drift: RequestDrift): string {
  const lines = [
    `Replay drift at model call #${drift.step}:`,
    `  recorded ${drift.expectedHash ?? "(no hash)"}`,
    `  actual   ${drift.actualHash}`,
    ...drift.differences.map((difference) => indentDifference(difference)),
  ];
  if (drift.settingsDifferences.length > 0) {
    lines.push("  settings differences (informational, not hashed):");
    lines.push(...drift.settingsDifferences.map((difference) => `    ${difference}`));
  }
  lines.push(
    "Hint: the agent's prompt, tools, or tool results changed since this fixture was recorded.",
    "If the change is intentional, re-record the fixture; otherwise this is a regression.",
  );
  return lines.join("\n");
}

function indentDifference(difference: string): string {
  return difference
    .split("\n")
    .map((line, index) => (index === 0 ? `  - ${line}` : `    ${line}`))
    .join("\n");
}

function diffPrompts(expected: unknown[], actual: unknown[], differences: string[]): void {
  if (expected.length !== actual.length) {
    differences.push(`prompt: message count differs: recorded ${expected.length}, actual ${actual.length}`);
  }
  const length = Math.min(expected.length, actual.length);
  for (let index = 0; index < length; index += 1) {
    const expectedMessage = expected[index];
    const actualMessage = actual[index];
    if (sameJson(expectedMessage, actualMessage)) {
      continue;
    }
    const role = messageRole(expectedMessage) ?? messageRole(actualMessage) ?? "unknown";
    if (messageRole(expectedMessage) !== messageRole(actualMessage)) {
      differences.push(
        `prompt[${index}]: role differs: recorded ${short(messageRole(expectedMessage))}, actual ${short(messageRole(actualMessage))}`,
      );
      continue;
    }
    differences.push(...diffMessageContent(index, role, expectedMessage, actualMessage));
  }
  if (actual.length > expected.length) {
    const extra = actual.slice(expected.length).map((message) => messageRole(message) ?? "unknown");
    differences.push(
      `prompt: actual run has ${actual.length - expected.length} extra message(s): [${extra.join(", ")}]`,
    );
  } else if (expected.length > actual.length) {
    const missing = expected.slice(actual.length).map((message) => messageRole(message) ?? "unknown");
    differences.push(`prompt: actual run is missing recorded message(s): [${missing.join(", ")}]`);
  }
}

function diffMessageContent(index: number, role: string, expected: unknown, actual: unknown): string[] {
  const expectedContent = messageContent(expected);
  const actualContent = messageContent(actual);

  if (typeof expectedContent === "string" || typeof actualContent === "string") {
    return [
      `prompt[${index}] (${role}): text differs:\n  recorded: ${short(expectedContent)}\n  actual:   ${short(actualContent)}`,
    ];
  }

  const expectedParts = asArray(expectedContent);
  const actualParts = asArray(actualContent);
  const lines: string[] = [];
  if (expectedParts.length !== actualParts.length) {
    lines.push(
      `prompt[${index}] (${role}): part count differs: recorded ${expectedParts.length}, actual ${actualParts.length}`,
    );
  }
  const length = Math.min(expectedParts.length, actualParts.length);
  for (let partIndex = 0; partIndex < length; partIndex += 1) {
    const expectedPart = expectedParts[partIndex];
    const actualPart = actualParts[partIndex];
    if (sameJson(expectedPart, actualPart)) {
      continue;
    }
    const partType = partTypeOf(expectedPart) ?? partTypeOf(actualPart) ?? "unknown";
    lines.push(
      `prompt[${index}] (${role}) part[${partIndex}] (${partType}) differs:\n  recorded: ${short(expectedPart)}\n  actual:   ${short(actualPart)}`,
    );
  }
  if (lines.length === 0) {
    lines.push(`prompt[${index}] (${role}) differs`);
  }
  return lines;
}

function diffTools(
  expected: ReadonlyArray<{ name: string }>,
  actual: ReadonlyArray<{ name: string }>,
  differences: string[],
): void {
  const expectedByName = new Map(expected.map((tool) => [tool.name, tool]));
  const actualByName = new Map(actual.map((tool) => [tool.name, tool]));

  const added = [...actualByName.keys()].filter((name) => !expectedByName.has(name));
  const removed = [...expectedByName.keys()].filter((name) => !actualByName.has(name));
  if (added.length > 0) {
    differences.push(`tools: added [${added.join(", ")}]`);
  }
  if (removed.length > 0) {
    differences.push(`tools: removed [${removed.join(", ")}]`);
  }

  for (const [name, expectedTool] of expectedByName) {
    const actualTool = actualByName.get(name);
    if (!actualTool || sameJson(expectedTool, actualTool)) {
      continue;
    }
    const expectedRecord = expectedTool as Record<string, unknown>;
    const actualRecord = actualTool as Record<string, unknown>;
    if (!sameJson(expectedRecord.description, actualRecord.description)) {
      differences.push(
        `tools[${name}]: description differs:\n  recorded: ${short(expectedRecord.description)}\n  actual:   ${short(actualRecord.description)}`,
      );
    }
    if (!sameJson(expectedRecord.inputSchema, actualRecord.inputSchema)) {
      differences.push(`tools[${name}]: inputSchema differs`);
    }
  }
}

function messageRole(message: unknown): string | undefined {
  return isRecord(message) && typeof message.role === "string" ? message.role : undefined;
}

function messageContent(message: unknown): unknown {
  return isRecord(message) ? message.content : undefined;
}

function partTypeOf(part: unknown): string | undefined {
  return isRecord(part) && typeof part.type === "string" ? part.type : undefined;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

const MAX_SHORT = 160;

function short(value: unknown): string {
  const text = typeof value === "string" ? JSON.stringify(value) : stableStringify(value);
  if (text === undefined) {
    return "undefined";
  }
  return text.length > MAX_SHORT ? `${text.slice(0, MAX_SHORT)}… (${text.length} chars)` : text;
}

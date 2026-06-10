import { isRecord } from "../internal/guards.js";
import { compareLedgerEvents, type LedgerMatchDiff } from "../check/index.js";
import type { LedgerEvent } from "../ledger/index.js";

export type CompareRunsNormalizers = {
  toolInput?: (input: unknown, context: { name?: string; index: number }) => unknown;
  toolOutput?: (output: unknown, context: { name?: string; index: number }) => unknown;
  runOutput?: (output: unknown) => unknown;
};

export type CompareRunsOptions = {
  /**
   * Dot paths pruned from tool inputs, tool outputs, and the run output on
   * BOTH sides before comparison, e.g. "createdAt", "items[*].timestamp".
   * This is the escape hatch for legitimately volatile fields.
   */
  ignorePaths?: string[];
  normalizers?: CompareRunsNormalizers;
  compareOutputs?: boolean;
  allowSideEffects?: boolean;
};

/**
 * Compare two recorded runs (fixture vs replay/live) at the trajectory level:
 * event types, tool call sequence/inputs/outputs, run output, and errors —
 * with volatile-field pruning instead of bare exact-JSON equality.
 */
export function compareRuns(
  expected: readonly LedgerEvent[],
  actual: readonly LedgerEvent[],
  options: CompareRunsOptions = {},
): LedgerMatchDiff {
  const transform = makeTransform(options);
  return compareLedgerEvents(expected.map(transform), actual.map(transform), {
    compareOutputs: options.compareOutputs,
    allowSideEffects: options.allowSideEffects,
  });
}

function makeTransform(options: CompareRunsOptions): (event: LedgerEvent, index: number) => LedgerEvent {
  const ignore = (options.ignorePaths ?? []).map(parsePath);
  let toolIndex = -1;

  const clean = (value: unknown): unknown => {
    let output = value;
    for (const path of ignore) {
      output = prunePath(output, path);
    }
    return output;
  };

  return (event) => {
    if (event.type === "tool.called") {
      toolIndex += 1;
      const input = options.normalizers?.toolInput
        ? options.normalizers.toolInput(event.input, { name: event.name, index: toolIndex })
        : event.input;
      return { ...event, input: clean(input) as LedgerEvent["input"] };
    }
    if (event.type === "tool.completed") {
      const output = options.normalizers?.toolOutput
        ? options.normalizers.toolOutput(event.output, { name: event.name, index: toolIndex })
        : event.output;
      return { ...event, output: clean(output) as LedgerEvent["output"] };
    }
    if (event.type === "run.completed") {
      const output = options.normalizers?.runOutput ? options.normalizers.runOutput(event.output) : event.output;
      return { ...event, output: clean(output) as LedgerEvent["output"] };
    }
    return event;
  };
}

type PathSegment = string | { wildcard: true };

function parsePath(path: string): PathSegment[] {
  return path
    .replace(/\[\*\]/g, ".*")
    .split(".")
    .filter((segment) => segment.length > 0)
    .map((segment) => (segment === "*" ? { wildcard: true as const } : segment));
}

function prunePath(value: unknown, segments: PathSegment[]): unknown {
  if (segments.length === 0) {
    return undefined;
  }
  const [head, ...rest] = segments;

  if (typeof head !== "string") {
    if (Array.isArray(value)) {
      return rest.length === 0 ? [] : value.map((item) => prunePath(item, rest));
    }
    if (isRecord(value)) {
      const output: Record<string, unknown> = {};
      for (const [key, child] of Object.entries(value)) {
        const pruned = rest.length === 0 ? undefined : prunePath(child, rest);
        if (pruned !== undefined || rest.length > 0) {
          output[key] = pruned;
        }
      }
      return output;
    }
    return value;
  }

  if (!isRecord(value)) {
    return value;
  }
  if (!(head in value)) {
    return value;
  }
  if (rest.length === 0) {
    const { [head]: _removed, ...kept } = value;
    return kept;
  }
  return { ...value, [head]: prunePath(value[head], rest) };
}

import { isRecord } from "./guards.js";

export function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }
  if (isRecord(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

export function sameJson(left: unknown, right: unknown): boolean {
  return stableStringify(left) === stableStringify(right);
}

export function matchesPartial(actual: unknown, expected: unknown): boolean {
  if (typeof expected === "function") {
    return Boolean((expected as (input: unknown) => boolean)(actual));
  }
  if (Object.is(actual, expected)) {
    return true;
  }
  if (Array.isArray(expected)) {
    return Array.isArray(actual) && expected.every((item, index) => matchesPartial(actual[index], item));
  }
  if (isRecord(expected)) {
    if (!isRecord(actual)) {
      return false;
    }
    return Object.entries(expected).every(([key, value]) => matchesPartial(actual[key], value));
  }
  return false;
}

export function containsOrdered<T>(actual: readonly T[], expected: readonly T[]): boolean {
  let index = 0;
  for (const item of actual) {
    if (sameJson(item, expected[index])) {
      index += 1;
      if (index === expected.length) {
        return true;
      }
    }
  }
  return expected.length === 0;
}

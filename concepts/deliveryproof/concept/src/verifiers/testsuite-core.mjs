// Pure testsuite replay logic. This file contains no worker_threads code so it
// can be imported both by the main verifier and by the worker process.

/**
 * Deep structural equality for JSON-like values (objects, arrays, primitives).
 * Object key order does not matter; array order does.
 * @param {*} a
 * @param {*} b
 * @returns {boolean}
 */
export function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a === 'number' && typeof b === 'number' && Number.isNaN(a) && Number.isNaN(b)) {
    return true;
  }
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') {
    return false;
  }
  const aIsArr = Array.isArray(a);
  const bIsArr = Array.isArray(b);
  if (aIsArr !== bIsArr) return false;
  if (aIsArr) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (!deepEqual(a[i], b[i])) return false;
    }
    return true;
  }
  const aKeys = Object.keys(a);
  const bKeys = Object.keys(b);
  if (aKeys.length !== bKeys.length) return false;
  for (const key of aKeys) {
    if (!Object.prototype.hasOwnProperty.call(b, key)) return false;
    if (!deepEqual(a[key], b[key])) return false;
  }
  return true;
}

/**
 * Compute the reference result for a supported op. Throws on unknown op or bad input.
 * @param {string} op
 * @param {*} input
 * @returns {*}
 */
export function computeReference(op, input) {
  switch (op) {
    case 'sort': {
      requireArray(op, input);
      return [...input].sort((x, y) => {
        if (typeof x === 'number' && typeof y === 'number') return x - y;
        return x < y ? -1 : x > y ? 1 : 0;
      });
    }
    case 'sum': {
      requireArray(op, input);
      let total = 0;
      for (const n of input) {
        if (typeof n !== 'number' || Number.isNaN(n)) {
          throw new Error(`op "sum" requires an array of numbers; found ${typeof n}`);
        }
        total += n;
      }
      return total;
    }
    case 'unique': {
      requireArray(op, input);
      const seen = new Set();
      const out = [];
      for (const item of input) {
        const key = `${typeof item}:${String(item)}`;
        if (!seen.has(key)) {
          seen.add(key);
          out.push(item);
        }
      }
      return out;
    }
    case 'reverse': {
      requireArray(op, input);
      return [...input].reverse();
    }
    default:
      throw new Error(`unsupported op "${op}" (expected sort|sum|unique|reverse)`);
  }
}

/**
 * @param {string} op
 * @param {*} input
 */
function requireArray(op, input) {
  if (!Array.isArray(input)) {
    throw new Error(`op "${op}" requires an array input`);
  }
}

/**
 * @param {{ op: string, input: *, actual: * }} task
 * @returns {{ ok: true, expected: *, matched: boolean } | { ok: false, reason: string }}
 */
export function replayTestsuiteTask({ op, input, actual }) {
  try {
    const expected = computeReference(op, input);
    return { ok: true, expected, matched: deepEqual(expected, actual) };
  } catch (err) {
    return { ok: false, reason: err instanceof Error ? err.message : String(err) };
  }
}

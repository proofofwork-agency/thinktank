// Canonical encoding and hashing.
//
// Every object the protocol commits to is hashed through exactly one encoder so
// that two independent implementations agree byte-for-byte. Determinism here is
// load-bearing: a commitment id that depends on key order would let a promisor
// re-encode the same promise into a different identity.

import { createHash } from 'node:crypto';

/**
 * Canonical JSON: sorted keys, no insignificant whitespace, no undefined, and
 * no non-finite numbers. Rejects anything it cannot encode unambiguously
 * rather than silently coercing it.
 */
export function canonicalize(value) {
  return encode(value, new Set());
}

function encode(value, seen) {
  if (value === null) return 'null';

  const type = typeof value;

  if (type === 'boolean') return value ? 'true' : 'false';

  if (type === 'number') {
    if (!Number.isFinite(value)) {
      throw new TypeError(`canonicalize: non-finite number (${value})`);
    }
    // Reject -0 so it cannot alias 0 across encoders.
    return Object.is(value, -0) ? '0' : JSON.stringify(value);
  }

  if (type === 'bigint') {
    throw new TypeError('canonicalize: bigint is not encodable; use integer units');
  }

  if (type === 'string') return JSON.stringify(value);

  if (type === 'undefined' || type === 'function' || type === 'symbol') {
    throw new TypeError(`canonicalize: ${type} is not encodable`);
  }

  if (seen.has(value)) throw new TypeError('canonicalize: circular reference');
  seen.add(value);

  let out;
  if (Array.isArray(value)) {
    out = `[${value.map((item) => encode(item, seen)).join(',')}]`;
  } else {
    const keys = Object.keys(value).sort();
    const parts = [];
    for (const key of keys) {
      const entry = value[key];
      // Absent and explicitly-undefined must encode identically, so we drop both.
      if (entry === undefined) continue;
      parts.push(`${JSON.stringify(key)}:${encode(entry, seen)}`);
    }
    out = `{${parts.join(',')}}`;
  }

  seen.delete(value);
  return out;
}

/** sha256 over the canonical encoding, hex. */
export function digest(value) {
  return createHash('sha256').update(canonicalize(value), 'utf8').digest('hex');
}

/** Domain-separated digest, so a commitment can never be replayed as a receipt. */
export function domainDigest(domain, value) {
  if (typeof domain !== 'string' || domain.length === 0) {
    throw new TypeError('domainDigest: domain must be a non-empty string');
  }
  return createHash('sha256')
    .update(`vouch/v1/${domain}\n`, 'utf8')
    .update(canonicalize(value), 'utf8')
    .digest('hex');
}

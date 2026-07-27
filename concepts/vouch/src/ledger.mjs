// Append-only, hash-chained event ledger.
//
// The ledger is the only place protocol state is written. Everything else in
// this package is a pure fold over it, which is what lets any third party
// replay the market from the event log and land on the same trust oracle.

import { domainDigest } from './canonical.mjs';

const GENESIS = '0'.repeat(64);

export class Ledger {
  #entries = [];

  /** Hash of the most recent entry, or the all-zero genesis hash. */
  get head() {
    return this.#entries.length === 0 ? GENESIS : this.#entries.at(-1).hash;
  }

  get length() {
    return this.#entries.length;
  }

  /**
   * Append an event. `seq` and `prev` are assigned by the ledger, never by the
   * caller, so a caller cannot forge position in the chain.
   */
  append(type, payload) {
    if (typeof type !== 'string' || type.length === 0) {
      throw new TypeError('ledger.append: type must be a non-empty string');
    }
    if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) {
      throw new TypeError('ledger.append: payload must be a plain object');
    }

    const seq = this.#entries.length;
    const prev = this.head;
    const body = { type, seq, prev, payload };
    const hash = domainDigest('ledger-entry', body);
    const entry = Object.freeze({ ...body, payload: Object.freeze({ ...payload }), hash });

    this.#entries.push(entry);
    return entry;
  }

  /** All entries, oldest first. */
  entries() {
    return [...this.#entries];
  }

  /** Entries of a given type. */
  byType(type) {
    return this.#entries.filter((entry) => entry.type === type);
  }

  /**
   * Recompute the chain. Returns {valid, brokenAt} so a verifier can point at
   * the first tampered entry rather than just saying "no".
   */
  verify() {
    let prev = GENESIS;
    for (const entry of this.#entries) {
      const recomputed = domainDigest('ledger-entry', {
        type: entry.type,
        seq: entry.seq,
        prev: entry.prev,
        payload: entry.payload,
      });
      if (entry.prev !== prev || recomputed !== entry.hash) {
        return { valid: false, brokenAt: entry.seq };
      }
      prev = entry.hash;
    }
    return { valid: true, brokenAt: null };
  }

  /** Serialize to JSONL for offline replay. */
  toJSONL() {
    return this.#entries.map((entry) => JSON.stringify(entry)).join('\n');
  }
}

export { GENESIS };

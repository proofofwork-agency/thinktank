// Replay/nonce registry for settlement attempts.
//
// The key deliberately excludes contract.id. A replay with the same parties,
// rail, settlement authority, and nonce under a different contract id is still
// a replay risk and must be rejected.
//
// Reservation happens before funds are authorized, so any attempt burns the
// nonce whether the final decision is capture or refund. Retrying after a
// failed/refunded attempt requires a fresh nonce.

import { appendFileSync, closeSync, fsyncSync, mkdirSync, openSync, readFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { sha256hex } from '../protocol/canonical.mjs';
import { assertNoPrototypePollutionKeys, clockFrom } from '../protocol/runtime.mjs';
import { assertReservableState, assertReplayTransition } from './replay-transitions.mjs';

export const REPLAY_STORE_INTERFACE = Object.freeze({
  name: 'durable-replay-store',
  trustRoot: 'caller-supplied durable storage with atomic uniqueness for replay keys',
  proves: 'a nonce/replay key has been reserved once and then advanced through explicit settlement states',
  doesNotProve: 'cross-process atomicity unless the concrete store provides it, such as a database unique constraint',
  requiredMethods: Object.freeze(['reserve({ key, fingerprint, state, at })', 'mark(key, state, at)', 'get(key)']),
  implemented: false,
});

/**
 * @param {Object} [opts]
 * @param {string} [opts.logPath]
 * @param {boolean} [opts.fsync]
 * @param {{ reserve: Function, mark: Function, get: Function }} [opts.store]
 */
export function createNonceRegistry(opts = {}) {
  const now = clockFrom(opts);
  const store = opts.store ?? createWalReplayStore({ logPath: opts.logPath, fsync: opts.fsync });
  assertReplayStore(store);

  return {
    /**
     * @param {Object} args
     * @param {import('../protocol/types.mjs').DeliveryContract} args.contract
     * @param {string} args.settlementKeyId
     */
    reserve({ contract, settlementKeyId }) {
      const key = nonceKey({ contract, settlementKeyId });
      const fingerprint = nonceFingerprint(contract);
      store.reserve({ key, fingerprint, state: 'reserved', at: now() });
      return key;
    },

    /**
     * @param {string} key
     * @param {string} state
     */
    mark(key, state) {
      store.mark(key, state, now());
    },

    get(key) {
      return store.get(key);
    },

    _debugEntries() {
      return typeof store._debugEntries === 'function' ? store._debugEntries() : [];
    },
  };
}

/**
 * Create the default in-process Map + append-only JSONL replay store.
 *
 * This store is durable across restarts when logPath is set, but it has no
 * cross-process lock. Use the ReplayStore interface for database-backed stores
 * where concurrent double-reserve is enforced by an atomic unique constraint.
 *
 * @param {Object} [opts]
 * @param {string} [opts.logPath]
 * @param {boolean} [opts.fsync]
 */
export function createWalReplayStore({ logPath, fsync = false } = {}) {
  /** @type {Map<string, { fingerprint: string, state: string, at: number }>} */
  const entries = new Map();
  if (logPath) {
    mkdirSync(dirname(logPath), { recursive: true });
    replay();
  }

  return {
    /**
     * @param {{ key: string, fingerprint: string, state?: string, at?: number }} args
     */
    reserve({ key, fingerprint, state = 'reserved', at = Date.now() }) {
      assertReplayRecordFields({ key, fingerprint, state, at });
      assertReservableState(state);
      const prior = entries.get(key);
      if (prior) {
        if (prior.fingerprint !== fingerprint) {
          throw new Error(`nonce replay conflict for key ${key}`);
        }
        throw new Error(`nonce replay for key ${key}; state=${prior.state}`);
      }
      const record = { type: 'reserve', key, fingerprint, state, at };
      append(record);
      apply(record);
      return key;
    },

    /**
     * @param {string} key
     * @param {string} state
     * @param {number} [at]
     */
    mark(key, state, at = Date.now()) {
      if (typeof key !== 'string' || key.length === 0) throw new Error('replay store mark requires key');
      if (typeof state !== 'string' || state.length === 0) throw new Error('replay store mark requires state');
      if (typeof at !== 'number' || !Number.isFinite(at)) throw new Error('replay store mark requires finite at');
      const prior = entries.get(key);
      if (!prior) throw new Error(`nonce registry cannot mark unknown key ${key}`);
      assertReplayTransition(prior.state, state, key);
      if (prior.state === state) return; // idempotent retry, no WAL append
      const record = { type: 'mark', key, fingerprint: prior.fingerprint, state, at };
      append(record);
      apply(record);
    },

    get(key) {
      const entry = entries.get(key);
      return entry ? { ...entry } : null;
    },

    _debugEntries() {
      return Array.from(entries.entries()).map(([key, value]) => [key, { ...value }]);
    },
  };

  function replay() {
    let text = '';
    try {
      text = readFileSync(logPath, 'utf8');
    } catch (err) {
      if (err && err.code === 'ENOENT') return;
      throw err;
    }
    for (const [index, line] of text.split(/\n/).entries()) {
      if (!line.trim()) continue;
      let record;
      try {
        record = JSON.parse(line);
      } catch (err) {
        throw new Error(`nonce registry corrupt WAL line ${index + 1}: ${err.message}`);
      }
      try {
        assertNoPrototypePollutionKeys(record, `WAL line ${index + 1}`);
      } catch (err) {
        throw new Error(`nonce registry unsafe WAL line ${index + 1}: ${err.message}`);
      }
      apply(record);
    }
  }

  /**
   * @param {Object} record
   */
  function append(record) {
    if (!logPath) return;
    const line = `${JSON.stringify(record)}\n`;
    if (!fsync) {
      appendFileSync(logPath, line, 'utf8');
      return;
    }
    const fd = openSync(logPath, 'a');
    try {
      appendFileSync(fd, line, 'utf8');
      fsyncSync(fd);
    } finally {
      closeSync(fd);
    }
  }

  /**
   * @param {Object} record
   */
  function apply(record) {
    // Replay/runtime records must carry well-formed fields. WAL replay reaches
    // this path with attacker-influenced JSON, so validate before mutating state.
    assertReplayRecordFields({
      key: record.key,
      fingerprint: record.fingerprint,
      state: record.state,
      at: record.at,
    });
    if (record.type === 'reserve') {
      const prior = entries.get(record.key);
      if (prior && prior.fingerprint !== record.fingerprint) {
        throw new Error(`nonce registry WAL conflict for key ${record.key}`);
      }
      // A reserve record must create 'reserved'. A tampered WAL line claiming a
      // reservation was born 'captured' would fabricate a settlement on restart.
      assertReservableState(record.state);
    } else if (record.type === 'mark') {
      // A 'mark' may only ADVANCE an existing reservation. A lone mark record
      // (no prior reserve) must never synthesize replay state — otherwise a
      // tampered WAL line could fabricate a captured/settled nonce after restart.
      const prior = entries.get(record.key);
      if (!prior) {
        throw new Error(`nonce registry WAL mark before reserve for key ${record.key}`);
      }
      if (prior.fingerprint !== record.fingerprint) {
        throw new Error(`nonce registry WAL mark fingerprint mismatch for key ${record.key}`);
      }
      // Replay is fed by on-disk records, so the transition rules must hold here
      // too: a tampered log must not be able to regress a terminal back to
      // 'reserved' (freeing the nonce for reuse) or flip captured <-> refunded.
      assertReplayTransition(prior.state, record.state, record.key);
    } else {
      throw new Error(`nonce registry unknown record type ${JSON.stringify(record.type)}`);
    }
    entries.set(record.key, {
      fingerprint: record.fingerprint,
      state: record.state,
      at: record.at,
    });
  }
}

function assertReplayStore(store) {
  if (!store || typeof store !== 'object') throw new TypeError('createNonceRegistry: store must be an object');
  for (const method of ['reserve', 'mark', 'get']) {
    if (typeof store[method] !== 'function') {
      throw new TypeError(`createNonceRegistry: store.${method} must be a function`);
    }
  }
}

function assertReplayRecordFields({ key, fingerprint, state, at }) {
  if (typeof key !== 'string' || key.length === 0) throw new Error('replay store reserve requires key');
  if (typeof fingerprint !== 'string' || fingerprint.length === 0) throw new Error('replay store reserve requires fingerprint');
  if (typeof state !== 'string' || state.length === 0) throw new Error('replay store reserve requires state');
  if (typeof at !== 'number' || !Number.isFinite(at)) throw new Error('replay store reserve requires finite at');
}

/**
 * @param {Object} args
 * @param {import('../protocol/types.mjs').DeliveryContract} args.contract
 * @param {string} args.settlementKeyId
 */
export function nonceKey({ contract, settlementKeyId }) {
  return sha256hex({
    protocolVersion: contract.protocolVersion,
    settlementKeyId,
    buyer: contract.buyer,
    seller: contract.seller,
    railId: contract.railId,
    nonce: contract.nonce,
  });
}

/**
 * @param {import('../protocol/types.mjs').DeliveryContract} contract
 */
function nonceFingerprint(contract) {
  const { id, ...withoutId } = contract;
  return sha256hex(withoutId);
}

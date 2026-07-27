// sqlite-replay-store.mjs — a replay store with REAL cross-process atomicity.
//
// Why this exists: the bundled WAL store (./nonce-registry.mjs) is durable
// across restarts but holds its uniqueness check in an in-process Map. Two
// processes pointed at the same log will therefore BOTH reserve the same nonce
// — each one's `entries` Map is empty of the other's write — and the same
// contract can settle twice. REPLAY_STORE_INTERFACE has always documented that
// real atomicity needs "a database unique constraint"; this is that store.
//
// The uniqueness guarantee is not ours: it is the PRIMARY KEY on `key`. The
// second INSERT fails inside SQLite, under its file lock, whichever process it
// came from. We never read-then-write, because that pattern is exactly the race.
//
// Uses node:sqlite (built into Node 22+). Deliberately NOT better-sqlite3:
// `npm run verify:deps` asserts this package ships exactly one runtime
// dependency, and a replay store is not worth spending it on.

import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

/**
 * Create a durable, cross-process-atomic replay store.
 *
 * @param {Object} opts
 * @param {string} opts.dbPath Path to the SQLite file. Use ':memory:' for tests
 *   (single-process only — an in-memory DB has nothing to be atomic *across*).
 * @returns {{ reserve: Function, mark: Function, get: Function, close: Function, _debugEntries: Function }}
 */
export function createSqliteReplayStore({ dbPath } = {}) {
  if (typeof dbPath !== 'string' || dbPath.length === 0) {
    throw new TypeError('createSqliteReplayStore: dbPath is required');
  }
  if (dbPath !== ':memory:') {
    mkdirSync(dirname(dbPath), { recursive: true });
  }

  const db = new DatabaseSync(dbPath);
  // WAL journaling so a concurrent reader does not block the writer holding the
  // reservation lock. busy_timeout makes a contended writer wait for the lock
  // rather than immediately throwing SQLITE_BUSY and looking like a conflict.
  db.exec('PRAGMA journal_mode = WAL');
  db.exec('PRAGMA busy_timeout = 5000');
  db.exec(`
    CREATE TABLE IF NOT EXISTS replay_keys (
      key         TEXT PRIMARY KEY,
      fingerprint TEXT NOT NULL,
      state       TEXT NOT NULL,
      at          INTEGER NOT NULL
    )
  `);

  const insert = db.prepare(
    'INSERT INTO replay_keys (key, fingerprint, state, at) VALUES (?, ?, ?, ?)',
  );
  const selectOne = db.prepare('SELECT key, fingerprint, state, at FROM replay_keys WHERE key = ?');
  const updateState = db.prepare('UPDATE replay_keys SET state = ?, at = ? WHERE key = ? AND fingerprint = ?');
  const selectAll = db.prepare('SELECT key, fingerprint, state, at FROM replay_keys ORDER BY key');

  return {
    /**
     * Reserve a replay key. Atomic: the PRIMARY KEY constraint decides the
     * winner, so exactly one of N concurrent callers succeeds.
     * @param {{ key: string, fingerprint: string, state?: string, at?: number }} args
     */
    reserve({ key, fingerprint, state = 'reserved', at = Date.now() }) {
      assertFields({ key, fingerprint, state, at });
      try {
        insert.run(key, fingerprint, state, at);
      } catch (err) {
        // The insert lost the race (or this is a plain replay). Read the winner
        // back purely to produce a useful message — the decision was already
        // made by the constraint, not by this read.
        const prior = selectOne.get(key);
        if (prior) {
          if (prior.fingerprint !== fingerprint) {
            throw new Error(`nonce replay conflict for key ${key}`);
          }
          throw new Error(`nonce replay for key ${key}; state=${prior.state}`);
        }
        throw err;
      }
      return key;
    },

    /**
     * Advance an existing reservation. Never creates one: a mark without a
     * prior reserve would fabricate settled state for a nonce nobody reserved.
     * @param {string} key
     * @param {string} state
     * @param {number} [at]
     */
    mark(key, state, at = Date.now()) {
      if (typeof key !== 'string' || key.length === 0) throw new Error('replay store mark requires key');
      if (typeof state !== 'string' || state.length === 0) throw new Error('replay store mark requires state');
      if (typeof at !== 'number' || !Number.isFinite(at)) throw new Error('replay store mark requires finite at');
      const prior = selectOne.get(key);
      if (!prior) throw new Error(`nonce registry cannot mark unknown key ${key}`);
      const result = updateState.run(state, at, key, prior.fingerprint);
      if (result.changes !== 1) {
        throw new Error(`nonce registry could not advance key ${key}`);
      }
    },

    /**
     * @param {string} key
     * @returns {{ fingerprint: string, state: string, at: number }|null}
     */
    get(key) {
      const row = selectOne.get(key);
      if (!row) return null;
      return { fingerprint: row.fingerprint, state: row.state, at: Number(row.at) };
    },

    close() {
      db.close();
    },

    _debugEntries() {
      return selectAll.all().map((row) => [
        row.key,
        { fingerprint: row.fingerprint, state: row.state, at: Number(row.at) },
      ]);
    },
  };
}

/**
 * @param {{ key: *, fingerprint: *, state: *, at: * }} fields
 */
function assertFields({ key, fingerprint, state, at }) {
  if (typeof key !== 'string' || key.length === 0) throw new Error('replay store reserve requires key');
  if (typeof fingerprint !== 'string' || fingerprint.length === 0) throw new Error('replay store reserve requires fingerprint');
  if (typeof state !== 'string' || state.length === 0) throw new Error('replay store reserve requires state');
  if (typeof at !== 'number' || !Number.isFinite(at)) throw new Error('replay store reserve requires finite at');
}

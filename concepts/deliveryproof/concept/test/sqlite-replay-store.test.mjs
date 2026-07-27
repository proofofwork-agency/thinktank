// sqlite-replay-store.test.mjs
//
// The interface conformance suite runs in ONE process, so it cannot actually
// distinguish a real atomic store from the in-process WAL store — both pass it.
// The test that matters here is the last one: two separate OS processes racing
// for the same nonce. That is the case the WAL store loses and this store wins.

import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { registerReplayStoreConformance } from '../src/testing/replay-store-conformance.mjs';
import { createSqliteReplayStore } from '../src/engine/sqlite-replay-store.mjs';
import { createNonceRegistry, createWalReplayStore } from '../src/engine/nonce-registry.mjs';

const STORE_URL = new URL('../src/engine/sqlite-replay-store.mjs', import.meta.url);

function tmpDb(label) {
  return join(mkdtempSync(join(tmpdir(), `dp-sqlite-${label}-`)), 'replay.db');
}

// Same suite the WAL store is held to.
registerReplayStoreConformance(test, assert, {
  name: 'sqlite replay store passes replay-store conformance',
  supportsRestart: true,
  createStore: ({ caseName, phase, previousStore }) => {
    // 'restart' must reopen the SAME file — that is what makes it a restart.
    if (phase === 'restart' && previousStore) return createSqliteReplayStore({ dbPath: previousStore._dbPath });
    const dbPath = tmpDb(caseName);
    const store = createSqliteReplayStore({ dbPath });
    store._dbPath = dbPath;
    return store;
  },
});

test('the nonce registry accepts it as a drop-in store', () => {
  const registry = createNonceRegistry({ store: createSqliteReplayStore({ dbPath: tmpDb('registry') }) });
  const contract = {
    protocolVersion: 'deliveryproof/0.4-jcs1',
    id: 'c1',
    buyer: 'b',
    seller: 's',
    railId: 'escrow-mock',
    nonce: 'n1',
  };
  const key = registry.reserve({ contract, settlementKeyId: 'sk1' });
  assert.equal(registry.get(key).state, 'reserved');
  registry.mark(key, 'captured');
  assert.equal(registry.get(key).state, 'captured');
  // Same nonce again is a replay, regardless of contract id.
  assert.throws(
    () => registry.reserve({ contract: { ...contract, id: 'c2' }, settlementKeyId: 'sk1' }),
    /nonce replay/,
  );
});

// ---------------------------------------------------------------------------
// The actual point: cross-PROCESS atomicity
// ---------------------------------------------------------------------------

/**
 * Reserve the same key from `n` separate OS processes that all fire at the same
 * wall-clock instant.
 *
 * The barrier matters. Running the children sequentially (execFileSync) proves
 * only durability: process 2 starts after process 1 has already committed, so
 * even a non-atomic store looks correct. Every child here opens its store, then
 * spins until a shared start time before writing — so they contend for real.
 */
async function raceProcesses(script, storePath, n = 8) {
  const startAt = Date.now() + 750;
  const children = Array.from({ length: n }, () =>
    new Promise((resolve) => {
      const child = spawn(process.execPath, ['-e', script, storePath, String(startAt)], {
        stdio: ['ignore', 'pipe', 'pipe'],
      });
      let out = '';
      child.stdout.on('data', (chunk) => { out += chunk; });
      child.on('close', () => resolve(out.trim() || 'ERROR'));
      child.on('error', () => resolve('ERROR'));
    }));
  return Promise.all(children);
}

/** Child-side barrier: open the store first, then all fire together. */
const BARRIER = `
  const startAt = Number(process.argv[2]);
  while (Date.now() < startAt) { /* spin to the shared instant */ }
`;

test('sqlite store: exactly one of 8 concurrent PROCESSES wins the same nonce', async () => {
  const dbPath = tmpDb('crossproc');
  const script = `
    const { createSqliteReplayStore } = await import(${JSON.stringify(STORE_URL.href)});
    const store = createSqliteReplayStore({ dbPath: process.argv[1] });
    ${BARRIER}
    try {
      store.reserve({ key: 'contended-nonce', fingerprint: 'fp', state: 'reserved', at: 1 });
      console.log('WON');
    } catch {
      console.log('LOST');
    }
  `;
  const results = await raceProcesses(script, dbPath);
  const won = results.filter((r) => r === 'WON').length;
  // Only the SAFETY property is asserted. "Exactly one winner" must hold on
  // every scheduling; how the other seven fail (LOST vs a transient error) is
  // scheduling-dependent and deliberately not asserted, so this test can never
  // fail in the safe direction.
  assert.equal(won, 1, `exactly one process may reserve a nonce, got ${won} (${results.join(',')})`);
});

// The gap the sqlite store closes, proved WITHOUT a timing race.
//
// Each store instance loads the log once at construction. Two instances built
// before either writes therefore hold the same (empty) view — which is exactly
// the state two OS processes are in when they start concurrently. Modelling it
// with two instances makes the outcome deterministic instead of scheduling-
// dependent, so this documents the gap without a flaky test.

test('WAL store: two instances sharing one log BOTH reserve the same nonce', () => {
  const logPath = join(mkdtempSync(join(tmpdir(), 'dp-wal-gap-')), 'replay.jsonl');
  const rec = { key: 'contended-nonce', fingerprint: 'fp', state: 'reserved', at: 1 };

  const processA = createWalReplayStore({ logPath, fsync: true });
  const processB = createWalReplayStore({ logPath, fsync: true });

  processA.reserve(rec);
  // Not a bug report against the WAL store — REPLAY_STORE_INTERFACE already
  // states it has no cross-process lock. Asserted so nobody deletes the sqlite
  // store later believing the WAL store was always sufficient.
  assert.doesNotThrow(
    () => processB.reserve(rec),
    'the WAL store has no cross-process lock: this double-reserve is the documented gap',
  );
});

test('sqlite store: two instances sharing one file cannot both reserve', () => {
  const dbPath = tmpDb('gap');
  const rec = { key: 'contended-nonce', fingerprint: 'fp', state: 'reserved', at: 1 };

  const processA = createSqliteReplayStore({ dbPath });
  const processB = createSqliteReplayStore({ dbPath });

  processA.reserve(rec);
  // The PRIMARY KEY decides this, inside SQLite, under its file lock.
  assert.throws(() => processB.reserve(rec), /nonce replay/);
});

test('WAL and sqlite stores agree on single-process semantics', () => {
  const wal = createWalReplayStore({});
  const sqlite = createSqliteReplayStore({ dbPath: ':memory:' });
  const rec = { key: 'k', fingerprint: 'f', state: 'reserved', at: 1 };
  for (const store of [wal, sqlite]) {
    store.reserve(rec);
    assert.throws(() => store.reserve(rec), /nonce replay/);
    assert.throws(() => store.reserve({ ...rec, fingerprint: 'other' }), /nonce replay conflict/);
    assert.throws(() => store.mark('nope', 'captured', 2), /cannot mark unknown key/);
    assert.equal(store.get('missing'), null);
  }
});

test('mark cannot fabricate state for a key that was never reserved', () => {
  const store = createSqliteReplayStore({ dbPath: ':memory:' });
  assert.throws(() => store.mark('never-reserved', 'captured', 2), /cannot mark unknown key/);
  assert.equal(store.get('never-reserved'), null);
});

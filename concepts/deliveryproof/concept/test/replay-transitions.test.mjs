// replay-transitions.test.mjs — the replay-key state machine.
//
// Adversarial review found that `mark(key, state, at)` authenticated nothing but
// the key, so any caller knowing the deterministic key could advance ANOTHER
// party's row, use an arbitrary state, and then REGRESS it — freeing the nonce.
// Observed: A reserves (k, reserved); B marks it captured; A marks it back to
// reserved. `reserve({ state: 'captured' })` also succeeded outright.
//
// The mark() signature is fixed by the ReplayStore conformance contract, so a
// capability token is not available. Transitions are made monotonic instead,
// which removes every transition an attacker would want. Both stores are held to
// this identically — a divergence between them would be its own bug.

import test from 'node:test';
import assert from 'node:assert/strict';
import { appendFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { createWalReplayStore } from '../src/engine/nonce-registry.mjs';
import { createSqliteReplayStore } from '../src/engine/sqlite-replay-store.mjs';
import {
  assertReplayTransition,
  assertReservableState,
  INITIAL_REPLAY_STATE,
  TERMINAL_REPLAY_STATES,
} from '../src/engine/replay-transitions.mjs';

function walPath() {
  return join(mkdtempSync(join(tmpdir(), 'dp-trans-wal-')), 'replay.jsonl');
}
function dbPath() {
  return join(mkdtempSync(join(tmpdir(), 'dp-trans-db-')), 'replay.db');
}

/** Both implementations, exercised through the same assertions. */
const STORES = [
  ['wal', () => createWalReplayStore({ logPath: walPath() })],
  ['sqlite', () => createSqliteReplayStore({ dbPath: dbPath() })],
];

const rec = { key: 'k1', fingerprint: 'fp1', state: 'reserved', at: 1 };

for (const [name, make] of STORES) {
  test(`${name}: a reservation cannot be created already settled`, () => {
    const store = make();
    for (const terminal of TERMINAL_REPLAY_STATES) {
      assert.throws(
        () => store.reserve({ ...rec, key: `k-${terminal}`, state: terminal }),
        /cannot be created already settled/,
      );
    }
  });

  test(`${name}: a terminal state cannot be regressed to reserved`, () => {
    const store = make();
    store.reserve(rec);
    store.mark(rec.key, 'captured', 2);
    // The exact PoC: mark it back to 'reserved', freeing the nonce for reuse.
    assert.throws(() => store.mark(rec.key, 'reserved', 3), /state must be one of/);
    assert.equal(store.get(rec.key).state, 'captured');
  });

  test(`${name}: one terminal cannot flip to the other`, () => {
    const store = make();
    store.reserve(rec);
    store.mark(rec.key, 'captured', 2);
    assert.throws(() => store.mark(rec.key, 'refunded', 3), /is terminal and cannot become/);
    assert.equal(store.get(rec.key).state, 'captured');
  });

  test(`${name}: an invented state is rejected`, () => {
    const store = make();
    store.reserve(rec);
    assert.throws(() => store.mark(rec.key, 'settled-trust-me', 2), /state must be one of/);
    assert.equal(store.get(rec.key).state, 'reserved');
  });

  test(`${name}: re-marking the SAME terminal stays idempotent`, () => {
    // Retry safety must survive the new rules — a settlement that retries its
    // own mark must not blow up.
    const store = make();
    store.reserve(rec);
    store.mark(rec.key, 'refunded', 2);
    assert.doesNotThrow(() => store.mark(rec.key, 'refunded', 3));
    assert.equal(store.get(rec.key).state, 'refunded');
  });

  test(`${name}: the normal settlement path still works`, () => {
    const store = make();
    store.reserve(rec);
    assert.equal(store.get(rec.key).state, INITIAL_REPLAY_STATE);
    store.mark(rec.key, 'captured', 2);
    assert.equal(store.get(rec.key).state, 'captured');
  });
}

test('a tampered WAL cannot regress a terminal across a restart', () => {
  // The on-disk path is fed by attacker-influenceable records, so the rules must
  // hold on replay too — otherwise an appended line frees a spent nonce.
  const logPath = walPath();
  const first = createWalReplayStore({ logPath });
  first.reserve(rec);
  first.mark(rec.key, 'captured', 2);

  appendFileSync(
    logPath,
    `${JSON.stringify({ type: 'mark', key: rec.key, fingerprint: rec.fingerprint, state: 'reserved', at: 3 })}\n`,
    'utf8',
  );

  assert.throws(() => createWalReplayStore({ logPath }), /state must be one of/);
});

test('a tampered WAL cannot fabricate a reservation born captured', () => {
  const logPath = walPath();
  createWalReplayStore({ logPath }); // create the file
  appendFileSync(
    logPath,
    `${JSON.stringify({ type: 'reserve', key: 'forged', fingerprint: 'fp', state: 'captured', at: 1 })}\n`,
    'utf8',
  );
  assert.throws(() => createWalReplayStore({ logPath }), /cannot be created already settled/);
});

test('the transition helpers are directly enforceable', () => {
  assert.throws(() => assertReservableState('captured'), /cannot be created already settled/);
  assert.doesNotThrow(() => assertReservableState('reserved'));
  assert.doesNotThrow(() => assertReplayTransition('reserved', 'captured', 'k'));
  assert.doesNotThrow(() => assertReplayTransition('captured', 'captured', 'k'));
  assert.throws(() => assertReplayTransition('captured', 'reserved', 'k'), /state must be one of/);
  assert.throws(() => assertReplayTransition('refunded', 'captured', 'k'), /is terminal/);
});

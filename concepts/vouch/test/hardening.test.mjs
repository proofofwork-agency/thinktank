// Regression suite for the adversarial review (Codex, 2026-07-27).
//
// Every test here corresponds to a concrete attack that WORKED against the
// first cut of the protocol. They are kept as named findings rather than
// folded into the main suite, because the interesting fact about each one is
// that it was once exploitable.

import test from 'node:test';
import assert from 'node:assert/strict';

import { createCommitment } from '../src/commitment.mjs';
import { createVouchMarket } from '../src/protocol.mjs';
import { attestationAdapter } from '../src/evidence.mjs';
import { replayOracle } from '../src/oracle.mjs';

const VERIFIER = { kind: 'attestation' };

function market() {
  return createVouchMarket({ adapters: [attestationAdapter] });
}

function commit(overrides = {}) {
  return createCommitment({
    promisor: 'agent',
    beneficiary: 'buyer',
    feeAmount: 0,
    exposureAmount: 100,
    bondAmount: 0,
    verifier: VERIFIER,
    deadline: 1_000,
    nonce: 'n',
    ...overrides,
  });
}

// FINDING 1 (critical) — a zero premium made the colluding pair end flat
// rather than down, so "strictly unprofitable" was false at premium = 0.
test('finding 1: a zero premium is refused', () => {
  const m = market();
  m.deposit('agent', 100);
  m.deposit('buyer', 100);
  m.deposit('underwriter', 100);
  const c = commit({ bondAmount: 100 });
  m.open(c, { actor: 'agent' });

  assert.throws(
    () => m.quote({
      commitmentId: c.commitmentId,
      underwriter: 'underwriter',
      coverageAmount: 100,
      premiumAmount: 0,
      expiresAt: 500,
    }),
    /premiumAmount must be greater than zero/,
  );
});

// FINDING 1b (critical) — with underwriter === promisor the three roles
// collapse to two and subrogation just moves value back to its source, so the
// premium never leaves the colluding pair.
test('finding 1b: the promisor cannot underwrite its own commitment', () => {
  const m = market();
  m.deposit('agent', 500);
  m.deposit('buyer', 500);
  const c = commit({ bondAmount: 100 });
  m.open(c, { actor: 'agent' });

  assert.throws(
    () => m.quote({
      commitmentId: c.commitmentId,
      underwriter: 'agent',
      coverageAmount: 100,
      premiumAmount: 5,
      expiresAt: 500,
    }),
    /post a bond instead/,
  );
});

// FINDING 2 (critical) — anyone could open a commitment naming a victim as
// promisor, lock the victim's bond, attest failure, and confiscate it.
test('finding 2: opening a commitment requires the promisor', () => {
  const m = market();
  m.deposit('victim', 100);
  const c = commit({ promisor: 'victim', beneficiary: 'attacker', bondAmount: 100 });

  assert.throws(() => m.open(c, { actor: 'attacker' }), /must be authorized by the promisor/);
  assert.throws(() => m.open(c), /must be authorized by the promisor/);
  assert.equal(m.balance('victim').locked, 0, 'victim bond was never locked');
});

// FINDING 2b (critical) — anyone could bind an arbitrarily expensive quote
// against a victim beneficiary, draining them into a colluding underwriter.
test('finding 2b: binding requires the beneficiary', () => {
  const m = market();
  m.deposit('agent', 100);
  m.deposit('buyer', 100);
  m.deposit('underwriter', 100);

  const c = commit({ exposureAmount: 100, bondAmount: 100 });
  m.open(c, { actor: 'agent' });
  const q = m.quote({
    commitmentId: c.commitmentId,
    underwriter: 'underwriter',
    coverageAmount: 1,
    premiumAmount: 100, // would drain the buyer entirely
    expiresAt: 500,
  });

  assert.throws(() => m.bind(q.quoteId, { actor: 'underwriter' }), /must be accepted by the beneficiary/);
  assert.equal(m.balance('buyer').total, 100, 'buyer funds untouched');
});

// FINDING 3 (critical) — `recovered` was a caller parameter, so passing 0 on a
// fully-refunded job manufactured a residual loss that did not exist.
test('finding 3: recovery is derived from the commitment, not the caller', () => {
  const m = market();
  m.deposit('agent', 100);
  m.deposit('buyer', 100);
  m.deposit('underwriter', 100);

  // Fee equals exposure: escrow refunds everything, so residual loss is zero.
  const c = commit({ feeAmount: 100, exposureAmount: 100, bondAmount: 100 });
  m.open(c, { actor: 'agent' });
  const q = m.quote({
    commitmentId: c.commitmentId,
    underwriter: 'underwriter',
    coverageAmount: 100,
    premiumAmount: 5,
    expiresAt: 500,
  });
  m.bind(q.quoteId, { actor: 'buyer' });

  // The old hole: settle(id, ev, {recovered: 0}). The parameter is gone, and a
  // stray third argument must not change the arithmetic.
  const result = m.settle(c.commitmentId, { delivered: false }, { recovered: 0 });

  assert.equal(result.payout, 0, 'nothing is owed when escrow already made the buyer whole');
  assert.equal(result.subrogated, 0, 'the bond is not confiscated');
  assert.equal(m.balance('agent').total, 100, 'promisor keeps its bond');
});

// FINDING 4 (critical) — 100 self-dealt, unbonded, unpoliced jobs bought a 98%
// score for free, and with it a cheap quote on a million of real exposure.
test('finding 4: free self-dealt jobs earn no reputation', () => {
  const m = market();
  m.deposit('buyer', 1_000);

  for (let i = 0; i < 100; i += 1) {
    const c = commit({ promisor: 'sybil', exposureAmount: 1, nonce: `farm-${i}` });
    m.open(c, { actor: 'sybil' });
    m.settle(c.commitmentId, { delivered: true });
  }

  const oracle = replayOracle(m.ledger);
  assert.deepEqual(
    oracle.history('sybil'),
    { delivered: 0, failed: 0 },
    'uncovered outcomes must not count toward reputation',
  );
  // Still priced as a complete unknown, which is the correct answer.
  assert.ok(oracle.fairPremium('sybil', 1_000_000) >= 1_000_000);
});

// FINDING 5 (high) — a rival could be griefed by opening fake failing
// commitments in their name. Opening now needs their authorization, and even
// then an unpoliced failure carries no reputational weight.
test('finding 5: unpoliced failures cannot grief a score', () => {
  const m = market();
  m.deposit('buyer', 1_000);

  for (let i = 0; i < 10; i += 1) {
    const c = commit({ promisor: 'victim', exposureAmount: 1, nonce: `grief-${i}` });
    m.open(c, { actor: 'victim' });
    m.settle(c.commitmentId, { delivered: false });
  }

  const oracle = replayOracle(m.ledger);
  assert.deepEqual(oracle.history('victim'), { delivered: 0, failed: 0 });
});

// FINDING 6 (high) — bind() locked the underwriter's collateral before moving
// the premium, so a beneficiary who could not pay stranded that collateral
// with no policy in existence to release it.
test('finding 6: a failed bind strands no collateral', () => {
  const m = market();
  m.deposit('agent', 100);
  m.deposit('underwriter', 200);
  m.deposit('buyer', 1); // cannot afford the premium

  const c = commit({ exposureAmount: 100, bondAmount: 100 });
  m.open(c, { actor: 'agent' });
  const q = m.quote({
    commitmentId: c.commitmentId,
    underwriter: 'underwriter',
    coverageAmount: 100,
    premiumAmount: 50,
    expiresAt: 500,
  });

  assert.throws(() => m.bind(q.quoteId, { actor: 'buyer' }), /insufficient balance/);
  assert.equal(m.balance('underwriter').locked, 0, 'no collateral left locked');
  assert.equal(m.balance('underwriter').available, 200, 'collateral fully reusable');

  // And the underwriter can still write a policy someone can actually pay for.
  m.deposit('buyer', 100);
  const q2 = m.quote({
    commitmentId: c.commitmentId,
    underwriter: 'underwriter',
    coverageAmount: 100,
    premiumAmount: 50,
    expiresAt: 500,
  });
  m.bind(q2.quoteId, { actor: 'buyer' });
  assert.equal(m.balance('underwriter').locked, 100);
});

// CONVERGENT CONSTRAINT — cover beyond the bond is refused by default.
//
// Economics, insurance law, and prudential logic independently land on the
// same rule, so it is the default rather than a recommendation.
test('cover beyond the promisor bond is refused by default', () => {
  const m = market();
  m.deposit('agent', 1_000);
  m.deposit('buyer', 1_000);
  m.deposit('underwriter', 1_000);

  const c = commit({ exposureAmount: 100, bondAmount: 40 });
  m.open(c, { actor: 'agent' });

  assert.throws(
    () => m.quote({
      commitmentId: c.commitmentId,
      underwriter: 'underwriter',
      coverageAmount: 100, // more than the 40 bonded
      premiumAmount: 5,
      expiresAt: 500,
    }),
    /only writes fully collateralized cover/,
  );

  // Cover up to the bond is fine.
  const ok = m.quote({
    commitmentId: c.commitmentId,
    underwriter: 'underwriter',
    coverageAmount: 40,
    premiumAmount: 5,
    expiresAt: 500,
  });
  m.bind(ok.quoteId, { actor: 'buyer' });
  assert.equal(m.coverageRegime(c.commitmentId), 'collateralized');
});

test('the reputational regime is available only by explicit opt-in', () => {
  const m = createVouchMarket({ adapters: [attestationAdapter], allowReputational: true });
  m.deposit('agent', 1_000);
  m.deposit('buyer', 1_000);
  m.deposit('underwriter', 1_000);

  const c = commit({ exposureAmount: 100, bondAmount: 40 });
  m.open(c, { actor: 'agent' });
  const q = m.quote({
    commitmentId: c.commitmentId,
    underwriter: 'underwriter',
    coverageAmount: 100,
    premiumAmount: 5,
    expiresAt: 500,
  });
  m.bind(q.quoteId, { actor: 'buyer' });

  assert.equal(m.coverageRegime(c.commitmentId), 'reputational');
});

// Reputation is only earned where capital was at risk — the positive case, so
// the fix above is not just "nothing ever counts".
test('policy-backed outcomes do count toward reputation', () => {
  const m = market();
  m.deposit('agent', 10_000);
  m.deposit('buyer', 10_000);
  m.deposit('underwriter', 10_000);

  for (let i = 0; i < 5; i += 1) {
    const c = commit({ exposureAmount: 100, bondAmount: 100, nonce: `real-${i}` });
    m.open(c, { actor: 'agent' });
    const q = m.quote({
      commitmentId: c.commitmentId,
      underwriter: 'underwriter',
      coverageAmount: 100,
      premiumAmount: 5,
      expiresAt: 500,
    });
    m.bind(q.quoteId, { actor: 'buyer' });
    m.settle(c.commitmentId, { delivered: true });
  }

  assert.deepEqual(replayOracle(m.ledger).history('agent'), { delivered: 5, failed: 0 });
});

// Core invariants: encoding, ledger integrity, money safety, oracle behaviour.

import test from 'node:test';
import assert from 'node:assert/strict';

import { canonicalize, digest, domainDigest } from '../src/canonical.mjs';
import { Ledger } from '../src/ledger.mjs';
import { createCommitment, commitmentIdOf } from '../src/commitment.mjs';
import { createTrustOracle } from '../src/oracle.mjs';
import { mulDivCeil, priceFromProbability, subAmount } from '../src/units.mjs';
import { attestationAdapter, createAdapter } from '../src/evidence.mjs';

test('canonical encoding is key-order independent', () => {
  assert.equal(canonicalize({ b: 1, a: 2 }), canonicalize({ a: 2, b: 1 }));
  assert.equal(digest({ b: 1, a: 2 }), digest({ a: 2, b: 1 }));
});

test('canonical encoding rejects what it cannot encode unambiguously', () => {
  assert.throws(() => canonicalize({ x: NaN }), /non-finite/);
  assert.throws(() => canonicalize({ x: Infinity }), /non-finite/);
  assert.throws(() => canonicalize({ x: 1n }), /bigint/);
  const circular = {};
  circular.self = circular;
  assert.throws(() => canonicalize(circular), /circular/);
});

test('absent and undefined fields encode identically', () => {
  assert.equal(canonicalize({ a: 1, b: undefined }), canonicalize({ a: 1 }));
});

test('domain separation stops a commitment being replayed as another object', () => {
  const value = { a: 1 };
  assert.notEqual(domainDigest('commitment', value), domainDigest('badge', value));
});

test('an intact ledger verifies and entries are chained', () => {
  const ledger = new Ledger();
  ledger.append('a', { n: 1 });
  ledger.append('b', { n: 2 });
  ledger.append('c', { n: 3 });

  assert.deepEqual(ledger.verify(), { valid: true, brokenAt: null });

  const entries = ledger.entries();
  assert.equal(entries[0].prev, '0'.repeat(64), 'first entry chains to genesis');
  assert.equal(entries[1].prev, entries[0].hash);
  assert.equal(entries[2].prev, entries[1].hash);
  assert.equal(ledger.head, entries[2].hash);
});

test('a tampered payload cannot reproduce its original entry hash', () => {
  const ledger = new Ledger();
  ledger.append('settled', { outcome: 'failed' });
  const original = ledger.entries()[0];

  // Recompute the entry hash the way verify() does, with a flipped payload.
  const forgedHash = domainDigest('ledger-entry', {
    type: original.type,
    seq: original.seq,
    prev: original.prev,
    payload: { outcome: 'delivered' },
  });

  assert.notEqual(forgedHash, original.hash, 'rewriting an outcome must break the chain');
});

test('ledger entries are frozen against in-place mutation', () => {
  const ledger = new Ledger();
  ledger.append('settled', { outcome: 'failed' });
  const entry = ledger.entries()[0];

  assert.throws(() => {
    'use strict';
    entry.payload.outcome = 'delivered';
  }, TypeError);
  assert.equal(ledger.verify().valid, true);
});

test('commitment id is bound to its contents', () => {
  const base = {
    promisor: 'a',
    beneficiary: 'b',
    feeAmount: 10,
    exposureAmount: 100,
    bondAmount: 0,
    verifier: { kind: 'attestation' },
    deadline: 10,
    nonce: 'n',
  };
  const commitment = createCommitment(base);
  assert.equal(commitmentIdOf(commitment), commitment.commitmentId);

  const altered = { ...commitment, exposureAmount: 1_000_000 };
  assert.notEqual(commitmentIdOf(altered), commitment.commitmentId);
});

test('a party cannot promise to itself', () => {
  assert.throws(
    () => createCommitment({
      promisor: 'same',
      beneficiary: 'same',
      feeAmount: 0,
      exposureAmount: 100,
      verifier: { kind: 'attestation' },
      deadline: 10,
      nonce: 'n',
    }),
    /must be distinct/,
  );
});

test('money arithmetic refuses to go negative or lose precision', () => {
  assert.throws(() => subAmount(1, 2), /underflow/);
  // Exact at a scale that overflows a double product.
  assert.equal(mulDivCeil(4_996_000_000, 8_470_000, 100_000_000), 423_161_200);
  // Rounds up, always against the underwriter.
  assert.equal(mulDivCeil(1, 1, 3), 1);
  assert.equal(priceFromProbability(1_000_000, 0.01, 0), 10_000);
});

test('an unknown agent prices higher than a proven one', () => {
  const oracle = createTrustOracle();
  for (let i = 0; i < 200; i += 1) oracle.observe('proven', true);

  const unknownPremium = oracle.fairPremium('unknown', 1_000_000);
  const provenPremium = oracle.fairPremium('proven', 1_000_000);

  assert.ok(unknownPremium > provenPremium, 'ignorance must cost more than evidence');
  // No history => the posterior is wide enough that cover is not economic.
  assert.ok(unknownPremium >= 1_000_000, 'an unknown agent is uninsurable unbonded');
});

test('more evidence narrows the posterior and lowers the price', () => {
  const thin = createTrustOracle();
  const thick = createTrustOracle();
  for (let i = 0; i < 10; i += 1) thin.observe('a', true);
  for (let i = 0; i < 500; i += 1) thick.observe('a', true);

  assert.ok(thick.fairPremium('a', 1_000_000) < thin.fairPremium('a', 1_000_000));
  assert.ok(thick.posterior('a').stdDev < thin.posterior('a').stdDev);
});

test('failures raise the price monotonically', () => {
  const oracle = createTrustOracle();
  for (let i = 0; i < 100; i += 1) oracle.observe('a', true);
  const before = oracle.fairPremium('a', 1_000_000);
  oracle.observe('a', false);
  assert.ok(oracle.fairPremium('a', 1_000_000) > before);
});

test('an adapter returning nonsense is rejected rather than defaulted', () => {
  const rogue = createAdapter('rogue', () => ({ outcome: 'maybe', reason: 'x' }));
  assert.throws(() => rogue.decide({}, {}), /outcome must be/);

  const silent = createAdapter('silent', () => ({ outcome: 'delivered' }));
  assert.throws(() => silent.decide({}, {}), /reason must be/);
});

test('adapters are deterministic on the same bytes', () => {
  const evidence = { delivered: false, reason: 'wrong-city' };
  const first = attestationAdapter.decide({}, evidence);
  const second = attestationAdapter.decide({}, evidence);
  assert.deepEqual(first, second);
});

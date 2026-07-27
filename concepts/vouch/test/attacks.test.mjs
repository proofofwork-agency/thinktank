// The adversarial suite. These are the claims the concept lives or dies on,
// so they are asserted numerically rather than argued in prose.

import test from 'node:test';
import assert from 'node:assert/strict';

import { createCommitment } from '../src/commitment.mjs';
import { createVouchMarket } from '../src/protocol.mjs';
import { attestationAdapter } from '../src/evidence.mjs';
import { mintBadge, verifyBadge } from '../src/badge.mjs';

const VERIFIER = { kind: 'attestation' };

function scenario({
  bondAmount,
  coverageAmount,
  premiumAmount,
  exposureAmount = 1_000_000,
  feeAmount = 50_000,
  allowReputational = false,
}) {
  const market = createVouchMarket({ adapters: [attestationAdapter], allowReputational });

  market.deposit('agent', bondAmount + 10_000);
  market.deposit('buyer', 500_000);
  market.deposit('underwriter', coverageAmount + 10_000);

  const commitment = createCommitment({
    promisor: 'agent',
    beneficiary: 'buyer',
    feeAmount,
    exposureAmount,
    bondAmount,
    verifier: VERIFIER,
    deadline: 100,
    nonce: 'n1',
  });

  // Snapshot before anything is bound: the premium leaves the buyer's account
  // during bind(), so a window that opens afterwards would miss the very cost
  // that makes collusion unprofitable.
  const initialJoint = market.balance('agent').total + market.balance('buyer').total;

  market.open(commitment, { actor: commitment.promisor });
  const quote = market.quote({
    commitmentId: commitment.commitmentId,
    underwriter: 'underwriter',
    coverageAmount,
    premiumAmount,
    expiresAt: 50,
  });
  market.bind(quote.quoteId, { actor: 'buyer' });

  return { market, commitment, initialJoint };
}

function jointWealth(market, parties) {
  return parties.reduce((sum, party) => sum + market.balance(party).total, 0);
}

test('collusion is strictly unprofitable when coverage is fully bonded', () => {
  const premiumAmount = 20_000;
  const { market, commitment, initialJoint } = scenario({
    bondAmount: 1_000_000,
    coverageAmount: 950_000,
    premiumAmount,
  });

  assert.equal(market.coverageRegime(commitment.commitmentId), 'collateralized');

  // Have the agent fail on purpose — the best case available to a colluding
  // buyer and seller.
  const before = initialJoint;
  const result = market.settle(commitment.commitmentId, { delivered: false, reason: 'deliberate' });
  const after = jointWealth(market, ['agent', 'buyer']);

  assert.equal(result.outcome, 'failed');
  // Payout is capped at the loss not already refunded by escrow.
  assert.equal(result.payout, commitment.exposureAmount - commitment.feeAmount);
  // Subrogation claws the entire payout back out of the promisor's bond.
  assert.equal(result.subrogated, result.payout);

  // The pair is down exactly the premium they paid. Collusion burns money.
  assert.equal(after - before, -premiumAmount);
  assert.ok(after < before, 'colluding pair must not profit');
});

test('the reputational regime is profitable to collude against, and says so', () => {
  // Honesty check: vouch does not claim collusion-resistance it cannot deliver.
  // When cover exceeds the bond, the uncovered part is a real underwriter risk.
  const premiumAmount = 20_000;
  const { market, commitment, initialJoint } = scenario({
    bondAmount: 100_000,
    coverageAmount: 950_000,
    premiumAmount,
    allowReputational: true, // refused by default; opted into here to prove why
  });

  assert.equal(market.coverageRegime(commitment.commitmentId), 'reputational');

  const before = initialJoint;
  const result = market.settle(commitment.commitmentId, { delivered: false, reason: 'deliberate' });
  const after = jointWealth(market, ['agent', 'buyer']);

  assert.equal(result.subrogated, 100_000, 'recovery is bounded by the bond');
  // Exposed amount = payout - bond, less the premium burnt.
  assert.equal(after - before, result.payout - premiumAmount - 100_000);
  assert.ok(after > before, 'this regime is genuinely exposed — the label is not decorative');
});

test('honest delivery returns all capital and keeps the premium', () => {
  const premiumAmount = 20_000;
  const { market, commitment } = scenario({
    bondAmount: 1_000_000,
    coverageAmount: 950_000,
    premiumAmount,
  });

  const result = market.settle(commitment.commitmentId, { delivered: true, reason: 'shipped' });

  assert.equal(result.outcome, 'delivered');
  assert.equal(result.payout, 0);
  assert.equal(market.balance('underwriter').locked, 0, 'collateral released');
  assert.equal(market.balance('agent').locked, 0, 'bond released');
  // Underwriter is up the premium; buyer is down the premium.
  assert.equal(market.balance('underwriter').total, 950_000 + 10_000 + premiumAmount);
  assert.equal(market.balance('buyer').total, 500_000 - premiumAmount);
});

test('an underwriter cannot pledge the same collateral twice', () => {
  const market = createVouchMarket({ adapters: [attestationAdapter] });
  market.deposit('agent', 200_000);
  market.deposit('buyer', 200_000);
  market.deposit('underwriter', 100_000); // only enough for one policy

  const ids = ['a', 'b'].map((nonce) => {
    const commitment = createCommitment({
      promisor: 'agent',
      beneficiary: 'buyer',
      feeAmount: 0,
      exposureAmount: 100_000,
      bondAmount: 100_000,
      verifier: VERIFIER,
      deadline: 100,
      nonce,
    });
    market.open(commitment, { actor: commitment.promisor });
    return commitment.commitmentId;
  });

  const first = market.quote({
    commitmentId: ids[0],
    underwriter: 'underwriter',
    coverageAmount: 100_000,
    premiumAmount: 1_000,
    expiresAt: 50,
  });
  market.bind(first.quoteId, { actor: 'buyer' });

  const second = market.quote({
    commitmentId: ids[1],
    underwriter: 'underwriter',
    coverageAmount: 100_000,
    premiumAmount: 1_000,
    expiresAt: 50,
  });

  // Quoting is free; binding is what must fail.
  assert.throws(() => market.bind(second.quoteId, { actor: 'buyer' }), /insufficient collateral/);
});

test('over-insurance is refused, so a policy cannot become a wager', () => {
  const market = createVouchMarket({ adapters: [attestationAdapter] });
  market.deposit('buyer', 100_000);
  market.deposit('underwriter', 500_000);

  const commitment = createCommitment({
    promisor: 'agent',
    beneficiary: 'buyer',
    feeAmount: 0,
    exposureAmount: 100_000,
    bondAmount: 0,
    verifier: VERIFIER,
    deadline: 100,
    nonce: 'over',
  });
  market.open(commitment, { actor: commitment.promisor });

  assert.throws(
    () => market.quote({
      commitmentId: commitment.commitmentId,
      underwriter: 'underwriter',
      coverageAmount: 200_000,
      premiumAmount: 1_000,
      expiresAt: 50,
    }),
    /exceeds declared exposure/,
  );
});

test('a beneficiary cannot underwrite itself', () => {
  const market = createVouchMarket({ adapters: [attestationAdapter] });
  market.deposit('buyer', 500_000);

  const commitment = createCommitment({
    promisor: 'agent',
    beneficiary: 'buyer',
    feeAmount: 0,
    exposureAmount: 100_000,
    bondAmount: 0,
    verifier: VERIFIER,
    deadline: 100,
    nonce: 'self',
  });
  market.open(commitment, { actor: commitment.promisor });

  assert.throws(
    () => market.quote({
      commitmentId: commitment.commitmentId,
      underwriter: 'buyer',
      coverageAmount: 100_000,
      premiumAmount: 1_000,
      expiresAt: 50,
    }),
    /cannot underwrite its own commitment/,
  );
});

test('expired quotes cannot be bound, so quote spam cannot grief capital', () => {
  const market = createVouchMarket({ adapters: [attestationAdapter] });
  market.deposit('agent', 100_000);
  market.deposit('buyer', 100_000);
  market.deposit('underwriter', 100_000);

  const commitment = createCommitment({
    promisor: 'agent',
    beneficiary: 'buyer',
    feeAmount: 0,
    exposureAmount: 100_000,
    bondAmount: 100_000,
    verifier: VERIFIER,
    deadline: 100,
    nonce: 'exp',
  });
  market.open(commitment, { actor: commitment.promisor });

  const quote = market.quote({
    commitmentId: commitment.commitmentId,
    underwriter: 'underwriter',
    coverageAmount: 100_000,
    premiumAmount: 1_000,
    expiresAt: 10,
  });

  // No capital is locked merely by quoting.
  assert.equal(market.balance('underwriter').locked, 0);

  market.advanceTo(11);
  assert.throws(() => market.bind(quote.quoteId, { actor: 'buyer' }), /expired/);
});

test('double settlement is rejected', () => {
  const { market, commitment } = scenario({
    bondAmount: 100_000,
    coverageAmount: 100_000,
    premiumAmount: 1_000,
  });
  market.settle(commitment.commitmentId, { delivered: true });
  assert.throws(
    () => market.settle(commitment.commitmentId, { delivered: false }),
    /already settled/,
  );
});

test('a badge cannot be inflated without the ledger agreeing', () => {
  const { market, commitment } = scenario({
    bondAmount: 100_000,
    coverageAmount: 100_000,
    premiumAmount: 1_000,
  });
  market.settle(commitment.commitmentId, { delivered: false });

  const honest = mintBadge(market.ledger, 'agent');
  assert.equal(verifyBadge(market.ledger, honest).valid, true);

  const forged = { ...honest, scoreBasisPoints: 9_999 };
  const check = verifyBadge(market.ledger, forged);
  assert.equal(check.valid, false);
  assert.equal(check.claimed, 9_999);
  assert.equal(check.actual, honest.scoreBasisPoints);
});

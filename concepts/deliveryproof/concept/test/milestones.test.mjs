import test from 'node:test';
import assert from 'node:assert/strict';

import { generateKeypair } from '../src/protocol/crypto.mjs';
import {
  compileMilestoneContracts,
  settleMilestones,
  verifyMilestoneAggregate,
} from '../src/engine/milestones.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { builtinReplayVerifier } from '../src/verifiers/builtin-replay.mjs';

const settlementKey = generateKeypair();

function schedule() {
  return {
    id: 'schedule_1',
    buyer: 'buyer________',
    seller: 'seller_______',
    intent: 'two-part computation',
    totalPrice: { amount: 10, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'per-milestone-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'schedule-nonce',
    createdAt: Date.now(),
    milestones: [
      {
        id: 'sort',
        intent: 'sort array',
        deliverableType: 'application/json',
        predicate: { kind: 'builtin-replay', params: { op: 'sort', input: [5, 3, 9, 1] } },
        price: { amount: 4, currency: 'USDC' },
      },
      {
        id: 'sum',
        intent: 'sum array',
        deliverableType: 'application/json',
        predicate: { kind: 'builtin-replay', params: { op: 'sum', input: [1, 2, 3] } },
        price: { amount: 6, currency: 'USDC' },
      },
    ],
  };
}

test('compileMilestoneContracts creates independent child contracts and nonces', () => {
  const contracts = compileMilestoneContracts(schedule());
  assert.equal(contracts.length, 2);
  assert.equal(contracts[0].price.amount, 4);
  assert.equal(contracts[1].price.amount, 6);
  assert.notEqual(contracts[0].id, contracts[1].id);
  assert.notEqual(contracts[0].nonce, contracts[1].nonce);
  assert.equal(contracts[0].milestone.scheduleId, 'schedule_1');
});

test('milestone settlement releases passed children and refunds failed children', async () => {
  const aggregate = await settleMilestones({
    schedule: schedule(),
    produceEvidence: (_contract, index) => ({ output: index === 0 ? [1, 3, 5, 9] : 999 }),
    selectVerifier: () => builtinReplayVerifier,
    createRail: () => createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });

  assert.equal(aggregate.totalAmount, 10);
  assert.equal(aggregate.releasedAmount, 4);
  assert.equal(aggregate.refundedAmount, 6);
  assert.equal(aggregate.complete, false);
  assert.deepEqual(aggregate.children.map((c) => c.decision), ['release', 'refund']);
  assert.equal(verifyMilestoneAggregate(aggregate, settlementKey.publicKey), true);
});

test('milestone settlement can fully release when all children pass', async () => {
  const aggregate = await settleMilestones({
    schedule: schedule(),
    produceEvidence: (_contract, index) => ({ output: index === 0 ? [1, 3, 5, 9] : 6 }),
    selectVerifier: () => builtinReplayVerifier,
    createRail: () => createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });

  assert.equal(aggregate.releasedAmount, 10);
  assert.equal(aggregate.refundedAmount, 0);
  assert.equal(aggregate.complete, true);
  assert.equal(verifyMilestoneAggregate(aggregate, settlementKey.publicKey), true);
});

test('milestone aggregate verification rejects receipt tampering', async () => {
  const aggregate = await settleMilestones({
    schedule: schedule(),
    produceEvidence: (_contract, index) => ({ output: index === 0 ? [1, 3, 5, 9] : 6 }),
    selectVerifier: () => builtinReplayVerifier,
    createRail: () => createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });

  aggregate.children[0].receipt.decision = 'refund';
  assert.equal(verifyMilestoneAggregate(aggregate, settlementKey.publicKey), false);
});

test('milestone aggregate verification rejects unsigned amount tampering', async () => {
  const aggregate = await settleMilestones({
    schedule: schedule(),
    produceEvidence: (_contract, index) => ({ output: index === 0 ? [1, 3, 5, 9] : 6 }),
    selectVerifier: () => builtinReplayVerifier,
    createRail: () => createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });

  aggregate.children[0].amount = 9;
  aggregate.releasedAmount = 15;
  aggregate.totalAmount = 15;
  assert.equal(verifyMilestoneAggregate(aggregate, settlementKey.publicKey), false);
});

test('milestone aggregate verification binds to the exact schedule', async () => {
  const s = schedule();
  const aggregate = await settleMilestones({
    schedule: s,
    produceEvidence: (_contract, index) => ({ output: index === 0 ? [1, 3, 5, 9] : 6 }),
    selectVerifier: () => builtinReplayVerifier,
    createRail: () => createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });

  assert.equal(verifyMilestoneAggregate(aggregate, settlementKey.publicKey, { schedule: s }), true);

  const different = schedule();
  different.milestones[1].predicate = { kind: 'builtin-replay', params: { op: 'sum', input: [10, 20] } };
  assert.equal(verifyMilestoneAggregate(aggregate, settlementKey.publicKey, { schedule: different }), false);
});

test('milestone aggregate verification rejects truncated schedule rollups', async () => {
  const s = schedule();
  const aggregate = await settleMilestones({
    schedule: s,
    produceEvidence: (_contract, index) => ({ output: index === 0 ? [1, 3, 5, 9] : 6 }),
    selectVerifier: () => builtinReplayVerifier,
    createRail: () => createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });

  aggregate.children = [aggregate.children[0]];
  aggregate.childCount = 1;
  aggregate.releasedAmount = aggregate.children[0].amount;
  aggregate.refundedAmount = 0;
  aggregate.totalAmount = aggregate.children[0].amount;
  assert.equal(verifyMilestoneAggregate(aggregate, settlementKey.publicKey, { schedule: s }), false);
});

test('milestone aggregate verification rejects reordered children', async () => {
  const s = schedule();
  const aggregate = await settleMilestones({
    schedule: s,
    produceEvidence: (_contract, index) => ({ output: index === 0 ? [1, 3, 5, 9] : 6 }),
    selectVerifier: () => builtinReplayVerifier,
    createRail: () => createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });

  aggregate.children.reverse();
  assert.equal(verifyMilestoneAggregate(aggregate, settlementKey.publicKey, { schedule: s }), false);
});

test('milestone aggregate verification rejects substituted child receipts', async () => {
  const s = schedule();
  const aggregate = await settleMilestones({
    schedule: s,
    produceEvidence: (_contract, index) => ({ output: index === 0 ? [1, 3, 5, 9] : 6 }),
    selectVerifier: () => builtinReplayVerifier,
    createRail: () => createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });
  const otherSchedule = schedule();
  otherSchedule.id = 'schedule_2';
  otherSchedule.nonce = 'schedule-nonce-2';
  const otherAggregate = await settleMilestones({
    schedule: otherSchedule,
    produceEvidence: (_contract, index) => ({ output: index === 0 ? [1, 3, 5, 9] : 6 }),
    selectVerifier: () => builtinReplayVerifier,
    createRail: () => createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });

  aggregate.children[1] = otherAggregate.children[1];
  aggregate.releasedAmount = aggregate.children[0].amount + aggregate.children[1].amount;
  assert.equal(verifyMilestoneAggregate(aggregate, settlementKey.publicKey, { schedule: s }), false);
});

test('milestone aggregate verification rejects scheduleHash mismatch', async () => {
  const s = schedule();
  const aggregate = await settleMilestones({
    schedule: s,
    produceEvidence: (_contract, index) => ({ output: index === 0 ? [1, 3, 5, 9] : 6 }),
    selectVerifier: () => builtinReplayVerifier,
    createRail: () => createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });

  aggregate.scheduleHash = '0'.repeat(64);
  assert.equal(verifyMilestoneAggregate(aggregate, settlementKey.publicKey, { schedule: s }), false);
});

test('milestone accounting rejects non-integer or mismatched totals', () => {
  assert.throws(
    () => compileMilestoneContracts({ ...schedule(), totalPrice: { amount: 9, currency: 'USDC' } }),
    /sum exactly/,
  );
  const bad = schedule();
  bad.milestones[0].price.amount = 4.5;
  assert.throws(() => compileMilestoneContracts(bad), /integer/);
});

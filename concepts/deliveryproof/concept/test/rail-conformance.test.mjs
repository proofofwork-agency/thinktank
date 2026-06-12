import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomUUID } from 'node:crypto';

import { sha256hex } from '../src/protocol/canonical.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { createDurableEscrowRail } from '../src/rails/durable-rail.mjs';
import { runRailConformance } from '../src/testing/rail-conformance.mjs';

function tempLog(t) {
  const dir = mkdtempSync(join(tmpdir(), 'deliveryproof-rail-conformance-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return join(dir, 'rail.jsonl');
}

test('rail conformance: mock escrow rail passes', async () => {
  const result = await runRailConformance({
    createRail: ({ settlementPublicKey }) => createMockEscrowRail({ settlementPublicKey, logger: false }),
    supportsRestart: false,
  });
  assert.equal(result.ok, true, describeCases(result));
  assert.equal(result.cases.some((entry) => entry.name === 'status-after-restart'), false);
});

test('rail conformance: durable escrow rail passes including restart', async (t) => {
  const logPath = tempLog(t);
  const result = await runRailConformance({
    createRail: ({ settlementPublicKey }) => createDurableEscrowRail({ logPath, settlementPublicKey }),
    supportsRestart: true,
  });
  assert.equal(result.ok, true, describeCases(result));
  assert.equal(result.cases.some((entry) => entry.name === 'status-after-restart' && entry.ok), true);
});

test('rail conformance: broken refund-capture stub fails the safety case', async () => {
  const result = await runRailConformance({
    createRail: () => createBrokenRefundCaptureRail(),
    supportsRestart: false,
  });
  assert.equal(result.ok, false);
  assert.equal(result.cases.find((entry) => entry.name === 'no-capture-on-refund-decision')?.ok, false);
});

function describeCases(result) {
  return result.cases
    .map((entry) => entry.ok ? `PASS ${entry.name}` : `FAIL ${entry.name}: ${entry.error}`)
    .join('\n');
}

function createBrokenRefundCaptureRail() {
  const railId = 'broken-refund-capture';
  const holds = new Map();
  const terminals = new Map();

  function authorize(contract) {
    const hold = {
      holdId: randomUUID(),
      contractId: contract.id,
      contractHash: sha256hex(contract),
      railId,
      amount: contract.price.amount,
      currency: contract.price.currency,
      state: 'held',
      history: [{ state: 'held', at: Date.now() }],
    };
    holds.set(hold.holdId, hold);
    return clone(hold);
  }

  function status(holdOrId) {
    return clone(resolve(holdOrId));
  }

  function capture(holdOrId, receipt) {
    const hold = resolve(holdOrId);
    if (receipt?.decision === 'refund' && receipt.verdict?.ok === false) {
      assertReceiptMatchesHold(hold, receipt, 'refund', railId);
      return terminalize(hold, receipt, 'captured');
    }
    if (receipt?.decision !== 'release') {
      throw new Error('[broken-rail] capture requires release');
    }
    assertReceiptMatchesHold(hold, receipt, 'release', railId);
    return terminalize(hold, receipt, 'captured');
  }

  function refund(holdOrId, receipt) {
    const hold = resolve(holdOrId);
    if (receipt?.decision !== 'refund') {
      throw new Error('[broken-rail] refund requires refund');
    }
    assertReceiptMatchesHold(hold, receipt, 'refund', railId);
    return terminalize(hold, receipt, 'refunded');
  }

  function resolve(holdOrId) {
    const holdId = typeof holdOrId === 'string' ? holdOrId : holdOrId?.holdId;
    const hold = holds.get(holdId);
    if (!hold) throw new Error(`[broken-rail] unknown hold ${holdId}`);
    return hold;
  }

  function terminalize(hold, receipt, targetState) {
    const receiptHash = sha256hex(receipt);
    const prior = terminals.get(hold.holdId);
    if (prior) {
      if (prior.receiptHash === receiptHash && hold.state === targetState) return clone(hold);
      throw new Error(`[broken-rail] conflicting terminal settlement for hold ${hold.holdId}`);
    }
    if (hold.state !== 'held') throw new Error(`[broken-rail] hold ${hold.holdId} is already ${hold.state}`);
    hold.state = targetState;
    hold.history.push({ state: targetState, at: Date.now(), receiptRef: receipt.signature.slice(0, 16) });
    terminals.set(hold.holdId, { receiptHash });
    return clone(hold);
  }

  return { id: railId, authorize, capture, refund, status, health: () => ({ ok: true, railId }) };
}

function assertReceiptMatchesHold(hold, receipt, expectedDecision, railId) {
  const mismatches = [];
  if (receipt.decision !== expectedDecision) mismatches.push('decision');
  if (receipt.holdId !== hold.holdId) mismatches.push('holdId');
  if (receipt.contractId !== hold.contractId) mismatches.push('contractId');
  if (receipt.contractHash !== hold.contractHash) mismatches.push('contractHash');
  if (receipt.railId !== railId) mismatches.push('railId');
  if (receipt.amount !== hold.amount) mismatches.push('amount');
  if (receipt.currency !== hold.currency) mismatches.push('currency');
  if (mismatches.length) throw new Error(`[broken-rail] receipt mismatch: ${mismatches.join(', ')}`);
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

// test/reason.test.mjs
// deliveryReceiptToEvaluatorCall must be a faithful projection of core's
// toErc8183EvaluatorResult.
//
// SCOPE / HONESTY: pure projection test — NO chain, NO RPC, NO keys, NO live tx.
// reason.mjs is the single seam that turns a settled DeliveryProof receipt into the
// evaluator verb (complete=release / reject=refund) and the bytes32 attestation
// `reason` digest. This test pins it to core's own projection so the two never
// drift: same action, same stringified jobId, same reason word, for both decisions
// and both hash algorithms — and it inherits core's refusal to project an
// internally contradictory receipt. TESTNET / LOCAL ONLY.

import test from 'node:test';
import assert from 'node:assert/strict';

import { toErc8183EvaluatorResult, canonicalize, sha256hex, keccak256 } from 'deliveryproof';
import { deliveryReceiptToEvaluatorCall } from '../src/reason.mjs';

/**
 * Build a minimal, internally-consistent receipt body (unsigned is fine — reason
 * projection does not authenticate; it only reads decision + verdict + content).
 * @param {'release'|'refund'} decision
 * @returns {Object}
 */
function receiptFor(decision) {
  return {
    protocolVersion: 'deliveryproof/0.4-jcs1',
    contractId: 'contract_reason',
    contractHash: sha256hex({ contract: 'reason' }),
    railId: 'erc8183-base',
    holdId: 'erc8183:local:0xlocal:job-reason',
    amount: 5,
    currency: 'USDC',
    verdict: { ok: decision === 'release', tier: 'A', verifier: 'reason-test', reason: 'fixture', checkedAt: 2 },
    evidenceHash: sha256hex({ evidence: decision }),
    routeDecision: null,
    decision,
    issuedAt: 3,
  };
}

test('release decision projects to complete, refund to reject', () => {
  const releaseCall = deliveryReceiptToEvaluatorCall(receiptFor('release'), 'job-42');
  const refundCall = deliveryReceiptToEvaluatorCall(receiptFor('refund'), 'job-42');
  assert.equal(releaseCall.action, 'complete');
  assert.equal(refundCall.action, 'reject');
});

test('parity with toErc8183EvaluatorResult: action, jobId, reason (sha256 default)', () => {
  for (const decision of ['release', 'refund']) {
    const receipt = receiptFor(decision);
    const jobId = 7; // numeric on purpose — both sides must stringify identically.
    const core = toErc8183EvaluatorResult(receipt, { jobId });
    const adapter = deliveryReceiptToEvaluatorCall(receipt, jobId);
    assert.equal(adapter.action, core.action, `action parity for ${decision}`);
    assert.equal(adapter.jobId, core.jobId, `jobId parity for ${decision}`);
    assert.equal(adapter.jobId, '7', 'jobId must be stringified');
    assert.equal(adapter.reason, core.reason, `reason parity for ${decision}`);
    // reason is the 0x-prefixed sha256 of the receipt by default.
    assert.equal(adapter.reason, `0x${sha256hex(receipt)}`);
  }
});

test('parity under keccak256: reason is the 0x-prefixed keccak of the canonical receipt', () => {
  const receipt = receiptFor('release');
  const core = toErc8183EvaluatorResult(receipt, { jobId: 'job-keccak', hashAlg: 'keccak256' });
  const adapter = deliveryReceiptToEvaluatorCall(receipt, 'job-keccak', { hashAlg: 'keccak256' });
  assert.equal(adapter.reason, core.reason);
  assert.equal(adapter.reason, `0x${keccak256(canonicalize(receipt))}`);
  // sha256 and keccak256 reasons must differ (proves the alg is actually honored).
  const sha = deliveryReceiptToEvaluatorCall(receipt, 'job-keccak');
  assert.notEqual(adapter.reason, sha.reason);
});

test('the projected result drops hashAlg (single bytes32 reason for the contract)', () => {
  const adapter = deliveryReceiptToEvaluatorCall(receiptFor('release'), 'job-1');
  assert.deepEqual(Object.keys(adapter).sort(), ['action', 'jobId', 'reason']);
  assert.equal('hashAlg' in adapter, false);
});

test('inherits core refusal to project an internally contradictory receipt', () => {
  // decision says release but verdict.ok is false — core throws, so the adapter
  // (which delegates) must throw too. A contradictory receipt must never become an
  // ERC-8183 complete()/reject() projection.
  const contradictory = { ...receiptFor('release'), verdict: { ok: false, tier: 'A', verifier: 'x', reason: 'no', checkedAt: 2 } };
  assert.throws(() => deliveryReceiptToEvaluatorCall(contradictory, 'job-x'), TypeError);
});

test('a receipt without a decision string is rejected by the projection', () => {
  assert.throws(() => deliveryReceiptToEvaluatorCall({ verdict: { ok: true } }, 'job-x'), TypeError);
});

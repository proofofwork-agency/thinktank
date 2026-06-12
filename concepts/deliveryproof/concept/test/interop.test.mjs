// test/interop.test.mjs
// Tests for the thin ERC-8004 / ERC-8183 receipt export adapters.
import test from 'node:test';
import assert from 'node:assert/strict';

import { canonicalize, sha256hex } from '../src/protocol/canonical.mjs';
import { keccak256 } from '../src/protocol/keccak.mjs';
import { generateKeypair } from '../src/protocol/crypto.mjs';
import { settle } from '../src/engine/deliveryproof.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { testsuiteVerifier } from '../src/verifiers/testsuite.mjs';
import {
  encodeErc8004ValidationAbi,
  encodeErc8183EvaluatorAbi,
  toErc8004ValidationPayload,
  toErc8183EvaluatorResult,
} from '../src/interop/index.mjs';

const settlementKey = generateKeypair();

function sortContract() {
  return {
    id: 'contract_interop_1',
    buyer: 'buyer________',
    seller: 'seller_______',
    intent: 'sort array ascending',
    deliverableType: 'compute',
    predicate: { kind: 'testsuite', params: { op: 'sort', input: [5, 3, 9, 1] } },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'nonce-interop-1',
    createdAt: 0,
  };
}

async function settleWith(output) {
  return settle({
    contract: sortContract(),
    produceEvidence: () => ({ output }),
    verifier: testsuiteVerifier,
    rail: createMockEscrowRail(),
    settlementKey,
  });
}

test('ERC-8004: a passing receipt maps to response=100 with bound hashes', async () => {
  const { receipt } = await settleWith([1, 3, 5, 9]); // correct -> release
  const payload = toErc8004ValidationPayload(receipt);
  assert.equal(payload.response, 100);
  assert.equal(payload.requestHash, `0x${receipt.contractHash}`);
  assert.equal(payload.responseHash, `0x${sha256hex(receipt)}`);
  assert.equal(payload.tag, 'deliveryproof/testsuite/tier-A');
  assert.equal(payload.hashAlg, 'sha256');
  assert.equal(payload.responseURI, '');
});

test('ERC-8004: keccak256 mode is opt-in and includes ABI-shaped args', async () => {
  const { receipt } = await settleWith([1, 3, 5, 9]);
  const payload = toErc8004ValidationPayload(receipt, {
    hashAlg: 'keccak256',
    responseURI: 'ipfs://receipt',
    includeAbi: true,
  });
  assert.equal(payload.hashAlg, 'keccak256');
  assert.equal(payload.requestHash, `0x${keccak256(receipt.contractHash)}`);
  assert.equal(payload.responseHash, `0x${keccak256(canonicalize(receipt))}`);
  assert.equal(payload.abi.signature, 'validationResponse(bytes32,uint8,string,bytes32,string)');
  assert.equal(payload.abi.encodedArgs, encodeErc8004ValidationAbi(payload));
});

test('ERC-8004: a failing receipt maps to response=0', async () => {
  const { receipt } = await settleWith([9, 5, 3, 1]); // wrong -> refund
  const payload = toErc8004ValidationPayload(receipt, { responseURI: 'ipfs://evidence' });
  assert.equal(payload.response, 0);
  assert.equal(payload.responseURI, 'ipfs://evidence');
  assert.equal(payload.requestHash, `0x${receipt.contractHash}`);
});

test('ERC-8183: a release receipt maps to complete; a refund receipt maps to reject', async () => {
  const ok = await settleWith([1, 3, 5, 9]);
  const bad = await settleWith([9, 5, 3, 1]);

  const completeRes = toErc8183EvaluatorResult(ok.receipt, { jobId: 'job-1' });
  assert.equal(completeRes.action, 'complete');
  assert.equal(completeRes.jobId, 'job-1');
  assert.equal(completeRes.reason, `0x${sha256hex(ok.receipt)}`);

  const rejectRes = toErc8183EvaluatorResult(bad.receipt, { jobId: 'job-1' });
  assert.equal(rejectRes.action, 'reject');
});

test('ERC-8183: keccak256 mode is opt-in and includes ABI-shaped result', async () => {
  const { receipt } = await settleWith([1, 3, 5, 9]);
  const result = toErc8183EvaluatorResult(receipt, {
    jobId: 'job-1',
    hashAlg: 'keccak256',
    includeAbi: true,
  });
  assert.equal(result.hashAlg, 'keccak256');
  assert.equal(result.reason, `0x${keccak256(canonicalize(receipt))}`);
  assert.equal(result.abi.signature, 'DeliveryProofEvaluatorResult(string,string,bytes32)');
  assert.equal(result.abi.encodedArgs, encodeErc8183EvaluatorAbi(result));
});

test('ERC-8183: jobId defaults to the receipt contractId when not supplied', async () => {
  const { receipt } = await settleWith([1, 3, 5, 9]);
  const res = toErc8183EvaluatorResult(receipt);
  assert.equal(res.jobId, receipt.contractId);
});

test('interop adapters reject malformed receipts', () => {
  assert.throws(() => toErc8004ValidationPayload({}), /DeliveryReceipt with a verdict/);
  assert.throws(() => toErc8183EvaluatorResult({}), /DeliveryReceipt with a decision/);
  assert.throws(() => toErc8004ValidationPayload({ verdict: { ok: true } }, { hashAlg: 'sha3-256' }), /unsupported/);
  assert.throws(() => toErc8183EvaluatorResult({ decision: 'release' }, { hashAlg: 'sha3-256' }), /unsupported/);
});

test('interop is pure: the same receipt always projects identically', async () => {
  const { receipt } = await settleWith([1, 3, 5, 9]);
  assert.deepEqual(toErc8004ValidationPayload(receipt), toErc8004ValidationPayload(receipt));
  assert.deepEqual(toErc8183EvaluatorResult(receipt), toErc8183EvaluatorResult(receipt));
});

test('ERC-8004 ABI argument encoding matches a fixed vector', () => {
  const encoded = encodeErc8004ValidationAbi({
    requestHash: `0x${'00'.repeat(32)}`,
    response: 100,
    responseURI: '',
    responseHash: `0x${'11'.repeat(32)}`,
    tag: '',
  });
  assert.equal(encoded, [
    '0x',
    '00'.repeat(32),
    word(100),
    word(160),
    '11'.repeat(32),
    word(192),
    word(0),
    word(0),
  ].join(''));
});

test('ERC-8183 ABI argument encoding matches a fixed vector', () => {
  const encoded = encodeErc8183EvaluatorAbi({
    action: 'complete',
    jobId: '',
    reason: `0x${'22'.repeat(32)}`,
  });
  assert.equal(encoded, [
    '0x',
    word(96),
    word(160),
    '22'.repeat(32),
    word(8),
    '636f6d706c657465'.padEnd(64, '0'),
    word(0),
  ].join(''));
});

function word(value) {
  return BigInt(value).toString(16).padStart(64, '0');
}

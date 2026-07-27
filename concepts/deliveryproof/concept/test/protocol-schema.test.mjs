import test from 'node:test';
import assert from 'node:assert/strict';

import { PROTOCOL_VERSION, sha256hex } from '../src/protocol/canonical.mjs';
import {
  assertContract,
  assertEvidence,
  assertReceipt,
  assertVerdict,
  validateContract,
} from '../src/protocol/schema.mjs';

function validContract() {
  return {
    protocolVersion: PROTOCOL_VERSION,
    id: 'c1',
    buyer: 'buyer',
    seller: 'seller',
    intent: 'test',
    deliverableType: 'compute',
    predicate: { kind: 'builtin-replay', params: { op: 'sum', input: [1, 2] } },
    price: { amount: 1, currency: 'USDC' },
    sla: { deadlineMs: 1000 },
    refundRule: 'refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'n1',
    createdAt: 1,
  };
}

function validVerdict() {
  return { ok: true, tier: 'A', verifier: 'builtin-replay', reason: 'ok', checkedAt: 2 };
}

test('protocol schema accepts valid core wire records', () => {
  const contract = validContract();
  const evidence = {
    protocolVersion: PROTOCOL_VERSION,
    contractId: contract.id,
    nonce: contract.nonce,
    output: 3,
    outputHash: sha256hex(3),
    producedAt: 2,
  };
  const verdict = validVerdict();
  const receipt = {
    protocolVersion: PROTOCOL_VERSION,
    contractId: contract.id,
    contractHash: sha256hex(contract),
    railId: contract.railId,
    holdId: 'h1',
    amount: 1,
    currency: 'USDC',
    verdict,
    evidenceHash: sha256hex(evidence),
    routeDecision: null,
    lifecycle: [{ state: 'decision', at: 3, decision: 'release' }],
    nonceRegistryKey: null,
    decision: 'release',
    signerKeyId: 'abc',
    issuedAt: 3,
    signature: 'sig',
  };

  assert.doesNotThrow(() => assertContract(contract));
  assert.doesNotThrow(() => assertEvidence(evidence));
  assert.doesNotThrow(() => assertVerdict(verdict));
  assert.doesNotThrow(() => assertReceipt(receipt));
});

test('protocol schema rejects missing or wrong protocolVersion', () => {
  const missing = validContract();
  delete missing.protocolVersion;
  assert.equal(validateContract(missing).ok, false);

  const wrong = { ...validContract(), protocolVersion: 'deliveryproof/old' };
  assert.throws(() => assertContract(wrong), /protocolVersion/);
});

test('protocol schema rejects non-canonical JSON values in evidence', () => {
  assert.throws(
    () => assertEvidence({
      protocolVersion: PROTOCOL_VERSION,
      contractId: 'c1',
      nonce: 'n1',
      output: { bad: undefined },
      outputHash: 'abc',
      producedAt: 1,
    }),
    /canonical JSON/,
  );
});

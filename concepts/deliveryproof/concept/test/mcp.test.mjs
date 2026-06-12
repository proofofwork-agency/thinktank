import test from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';

import { canonicalize, sha256hex } from '../src/protocol/canonical.mjs';
import { generateKeypair, keyId, sign } from '../src/protocol/crypto.mjs';
import { paidToolWithDeliveryProof } from '../src/mcp/paidToolWithDeliveryProof.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { testsuiteVerifier } from '../src/verifiers/testsuite.mjs';
import { transcriptVerifier } from '../src/verifiers/transcript.mjs';
import { verifyReceipt } from '../src/engine/deliveryproof.mjs';

const settlementKey = generateKeypair();

function baseContract({ seller, predicate }) {
  return {
    id: `contract_${randomUUID()}`,
    buyer: 'buyer________',
    seller: keyId(seller.publicKey),
    intent: 'paid MCP tool call',
    deliverableType: 'application/json',
    predicate,
    price: { amount: 3, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: randomUUID(),
    createdAt: 0,
  };
}

test('paidToolWithDeliveryProof: testsuite verifier captures on verified output', async () => {
  const seller = generateKeypair();
  const rail = createMockEscrowRail();
  const paidSort = paidToolWithDeliveryProof({
    tool: (input) => [...input].sort((a, b) => a - b),
    makeContract: (input) => baseContract({
      seller,
      predicate: { kind: 'testsuite', params: { op: 'sort', input } },
    }),
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });

  const result = await paidSort([5, 3, 9, 1]);
  assert.equal(result.verdict.ok, true);
  assert.equal(result.receipt.decision, 'release');
  assert.equal(result.hold.state, 'captured');
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);
});

test('paidToolWithDeliveryProof: transcript verifier works end-to-end with makeEvidence attestation', async () => {
  const seller = generateKeypair();
  const rail = createMockEscrowRail();
  const paidTranscriptTool = paidToolWithDeliveryProof({
    tool: () => ({ answer: 42 }),
    makeContract: () => baseContract({
      seller,
      predicate: { kind: 'transcript', params: {} },
    }),
    makeEvidence: ({ contract, output }) => {
      const outputHash = sha256hex(output);
      const message = canonicalize({ contractId: contract.id, nonce: contract.nonce, outputHash });
      return {
        attestations: [
          {
            signerKeyId: keyId(seller.publicKey),
            publicKey: seller.publicKey,
            signature: sign(seller.privateKey, message),
          },
        ],
      };
    },
    verifier: transcriptVerifier,
    rail,
    settlementKey,
  });

  const result = await paidTranscriptTool({});
  assert.equal(result.verdict.ok, true);
  assert.equal(result.receipt.decision, 'release');
  assert.equal(result.hold.state, 'captured');
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);
});

test('paidToolWithDeliveryProof: transcript verifier refunds when attestation is absent', async () => {
  const seller = generateKeypair();
  const rail = createMockEscrowRail();
  const paidTranscriptTool = paidToolWithDeliveryProof({
    tool: () => ({ answer: 42 }),
    makeContract: () => baseContract({
      seller,
      predicate: { kind: 'transcript', params: {} },
    }),
    verifier: transcriptVerifier,
    rail,
    settlementKey,
  });

  const result = await paidTranscriptTool({});
  assert.equal(result.verdict.ok, false);
  assert.match(result.verdict.reason, /attestations\[0\] is required/);
  assert.equal(result.receipt.decision, 'refund');
  assert.equal(result.hold.state, 'refunded');
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);
});

test('paidToolWithDeliveryProof: default wrapper registry rejects nonce replay', async () => {
  const seller = generateKeypair();
  const rail = createMockEscrowRail();
  const fixedContract = baseContract({
    seller,
    predicate: { kind: 'testsuite', params: { op: 'sort', input: [2, 1] } },
  });
  const paidSort = paidToolWithDeliveryProof({
    tool: (input) => [...input].sort((a, b) => a - b),
    makeContract: () => fixedContract,
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });

  const first = await paidSort([2, 1]);
  assert.equal(first.verdict.ok, true);
  assert.equal(typeof first.receipt.nonceRegistryKey, 'string');
  await assert.rejects(() => paidSort([2, 1]), /nonce replay/);
});

test('paidToolWithDeliveryProof: strictRouting requires an explicit route decision', async () => {
  const seller = generateKeypair();
  const rail = createMockEscrowRail();
  const paidSort = paidToolWithDeliveryProof({
    tool: (input) => [...input].sort((a, b) => a - b),
    makeContract: (input) => baseContract({
      seller,
      predicate: { kind: 'testsuite', params: { op: 'sort', input } },
    }),
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
    strictRouting: true,
  });

  await assert.rejects(() => paidSort([2, 1]), /strictRouting requires a routeDecision/);
});

test('paidToolWithDeliveryProof: makeEvidence cannot silently replace tool output by default', async () => {
  const seller = generateKeypair();
  const rail = createMockEscrowRail();
  const paidSort = paidToolWithDeliveryProof({
    tool: () => [9, 1],
    makeContract: () => baseContract({
      seller,
      predicate: { kind: 'testsuite', params: { op: 'sort', input: [2, 1] } },
    }),
    makeEvidence: () => ({ output: [1, 2] }),
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });

  const result = await paidSort([2, 1]);
  assert.equal(result.verdict.ok, false);
  assert.match(result.verdict.reason, /may not override output/);
  assert.equal(result.receipt.decision, 'refund');
});

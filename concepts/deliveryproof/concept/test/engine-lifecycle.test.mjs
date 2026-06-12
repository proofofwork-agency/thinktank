import test from 'node:test';
import assert from 'node:assert/strict';

import { sha256hex } from '../src/protocol/canonical.mjs';
import { generateKeypair } from '../src/protocol/crypto.mjs';
import { settle, verifyReceipt } from '../src/engine/deliveryproof.mjs';
import { createNonceRegistry, nonceKey } from '../src/engine/nonce-registry.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { testsuiteVerifier } from '../src/verifiers/testsuite.mjs';

const settlementKey = generateKeypair();

function sortContract(extra = {}) {
  return {
    id: 'contract_lifecycle_1',
    buyer: 'buyer________',
    seller: 'seller_______',
    intent: 'sort array ascending',
    deliverableType: 'application/json',
    predicate: { kind: 'testsuite', params: { op: 'sort', input: [5, 3, 9, 1] } },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 1000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'nonce-lifecycle-1',
    createdAt: 10_000,
    ...extra,
  };
}

test('lifecycle events and nonce registry key are signed into the receipt', async () => {
  let clock = 10_100;
  const registry = createNonceRegistry();
  const result = await settle({
    contract: sortContract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9], producedAt: clock }),
    verifier: testsuiteVerifier,
    rail: createMockEscrowRail(),
    settlementKey,
    nonceRegistry: registry,
    now: () => clock++,
  });

  assert.equal(result.verdict.ok, true);
  assert.equal(result.receipt.decision, 'release');
  assert.equal(typeof result.receipt.nonceRegistryKey, 'string');
  assert.ok(result.receipt.lifecycle.some((e) => e.state === 'nonce-reserved'));
  assert.ok(result.receipt.lifecycle.some((e) => e.state === 'verified' && e.ok === true));
  assert.ok(result.receipt.lifecycle.some((e) => e.state === 'decision' && e.decision === 'release'));
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);

  const tampered = structuredClone(result.receipt);
  tampered.lifecycle[0].state = 'forged';
  assert.equal(verifyReceipt(tampered, settlementKey.publicKey), false);
  assert.equal(registry.get(result.receipt.nonceRegistryKey).state, 'captured');
});

test('SLA deadline is engine-enforced and refunds without running the producer', async () => {
  let producerCalled = false;
  const result = await settle({
    contract: sortContract(),
    produceEvidence: () => {
      producerCalled = true;
      return { output: [1, 3, 5, 9] };
    },
    verifier: testsuiteVerifier,
    rail: createMockEscrowRail(),
    settlementKey,
    now: () => 11_500,
  });

  assert.equal(producerCalled, false);
  assert.equal(result.verdict.ok, false);
  assert.match(result.verdict.reason, /SLA deadline exceeded before delivery/);
  assert.equal(result.receipt.decision, 'refund');
  assert.equal(result.hold.state, 'refunded');
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);
});

test('settle passes an AbortSignal to producers before the deadline', async () => {
  let seenSignal;
  const result = await settle({
    contract: sortContract(),
    produceEvidence: (_contract, { signal }) => {
      seenSignal = signal;
      return { output: [1, 3, 5, 9] };
    },
    verifier: testsuiteVerifier,
    rail: createMockEscrowRail(),
    settlementKey,
    now: () => 10_100,
  });

  assert.equal(result.verdict.ok, true);
  assert.ok(seenSignal instanceof AbortSignal);
  assert.equal(seenSignal.aborted, false);
});

test('nonce registry rejects replay even when only contract.id changes', async () => {
  const registry = createNonceRegistry();
  const first = await settle({
    contract: sortContract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: testsuiteVerifier,
    rail: createMockEscrowRail(),
    settlementKey,
    nonceRegistry: registry,
    now: () => 10_100,
  });
  assert.equal(first.verdict.ok, true);

  await assert.rejects(
    () => settle({
      contract: sortContract({ id: 'contract_lifecycle_2' }),
      produceEvidence: () => ({ output: [1, 3, 5, 9] }),
      verifier: testsuiteVerifier,
      rail: createMockEscrowRail(),
      settlementKey,
      nonceRegistry: registry,
      now: () => 10_100,
    }),
    /nonce replay/,
  );

  await assert.rejects(
    () => settle({
      contract: sortContract({ id: 'contract_lifecycle_3', price: { amount: 9, currency: 'USDC' } }),
      produceEvidence: () => ({ output: [1, 3, 5, 9] }),
      verifier: testsuiteVerifier,
      rail: createMockEscrowRail(),
      settlementKey,
      nonceRegistry: registry,
      now: () => 10_100,
    }),
    /nonce replay conflict/,
  );
});

test('nonceKey excludes contract id but includes parties, rail, settlement key, and nonce', async () => {
  const registry = createNonceRegistry();
  const contract = sortContract({ id: 'contract_A' });
  const result = await settle({
    contract,
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: testsuiteVerifier,
    rail: createMockEscrowRail(),
    settlementKey,
    nonceRegistry: registry,
    now: () => 10_100,
  });

  const normalized = { protocolVersion: 'deliveryproof/0.4-jcs1', ...contract };
  const sameReplayKey = nonceKey({ contract: { ...normalized, id: 'contract_B' }, settlementKeyId: result.receipt.signerKeyId });
  const differentBuyerKey = nonceKey({ contract: { ...normalized, buyer: 'other-buyer' }, settlementKeyId: result.receipt.signerKeyId });

  assert.match(result.receipt.nonceRegistryKey, /^[0-9a-f]{64}$/);
  assert.equal(result.receipt.nonceRegistryKey, sameReplayKey);
  assert.notEqual(result.receipt.nonceRegistryKey, differentBuyerKey);
});

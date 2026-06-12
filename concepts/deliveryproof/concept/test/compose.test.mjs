import test from 'node:test';
import assert from 'node:assert/strict';

import { sha256hex } from '../src/protocol/canonical.mjs';
import { generateKeypair, keyId } from '../src/protocol/crypto.mjs';
import { settle, verifyReceipt } from '../src/engine/deliveryproof.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { routeVerifier } from '../src/router/policy.mjs';
import { verifiers, composeVerifier } from '../src/verifiers/index.mjs';

const settlementKey = generateKeypair();

function evidenceFor(output) {
  return {
    contractId: 'c_compose',
    nonce: 'n_compose',
    output,
    outputHash: sha256hex(output),
    producedAt: 0,
  };
}

function composeContract(params) {
  return {
    protocolVersion: 'deliveryproof/0.4-jcs1',
    id: 'c_compose',
    buyer: 'buyer________',
    seller: 'seller_______',
    intent: 'composed verification',
    deliverableType: 'application/json',
    predicate: { kind: 'compose', params },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'n_compose',
    createdAt: 0,
  };
}

test('compose verifier: all mode passes only when every child verifier passes', async () => {
  const output = [1, 3, 5, 9];
  const contract = composeContract({
    mode: 'all',
    verifiers: [
      {
        kind: 'schema',
        params: { schema: { type: 'array', items: { type: 'number' } } },
      },
      {
        kind: 'hash',
        params: { expectedHash: sha256hex(output) },
      },
    ],
  });

  const verdict = await composeVerifier.verify(contract, evidenceFor(output));
  assert.equal(verdict.ok, true);
  assert.equal(verdict.verifier, 'compose');
  assert.equal(verdict.trace.length, 2);
  assert.deepEqual(verdict.trace.map((t) => [t.verifier, t.ok]), [['schema', true], ['hash', true]]);
});

test('compose verifier: all mode fails and preserves child trace', async () => {
  const contract = composeContract({
    mode: 'all',
    verifiers: [
      {
        kind: 'schema',
        params: { schema: { type: 'array', items: { type: 'number' } } },
      },
      {
        kind: 'hash',
        params: { expectedHash: sha256hex([1, 3, 5, 9]) },
      },
    ],
  });

  const verdict = await composeVerifier.verify(contract, evidenceFor([9, 5, 3, 1]));
  assert.equal(verdict.ok, false);
  assert.deepEqual(verdict.trace.map((t) => [t.verifier, t.ok]), [['schema', true], ['hash', false]]);
  assert.match(verdict.reason, /1\/2 child verifiers passed/);
});

test('compose verifier: any and threshold modes use explicit predicate algebra', async () => {
  const anyVerdict = await composeVerifier.verify(
    composeContract({
      mode: 'any',
      verifiers: [
        { kind: 'hash', params: { expectedHash: sha256hex({ no: 'match' }) } },
        { kind: 'schema', params: { schema: { type: 'array', items: { type: 'number' } } } },
      ],
    }),
    evidenceFor([9, 5, 3, 1]),
  );
  assert.equal(anyVerdict.ok, true);

  const thresholdVerdict = await composeVerifier.verify(
    composeContract({
      mode: 'threshold',
      threshold: 2,
      verifiers: [
        { kind: 'hash', params: { expectedHash: sha256hex([9, 5, 3, 1]) } },
        { kind: 'schema', params: { schema: { type: 'array', items: { type: 'number' } } } },
        { kind: 'testsuite', params: { op: 'sort', input: [5, 3, 9, 1] } },
      ],
    }),
    evidenceFor([9, 5, 3, 1]),
  );
  assert.equal(thresholdVerdict.ok, true);
  assert.equal(thresholdVerdict.trace.filter((t) => t.ok).length, 2);
});

test('router: explicit compose contracts cannot be bypassed by low-assurance schema', () => {
  const contract = composeContract({
    mode: 'all',
    verifiers: [
      { kind: 'schema', params: { schema: { type: 'array', items: { type: 'number' } } } },
      { kind: 'testsuite', params: { op: 'sort', input: [5, 3, 9, 1] } },
    ],
  });

  const { verifier, routeDecision } = routeVerifier(contract, {
    policy: { minAssurance: 1 },
  });
  assert.equal(verifier, verifiers.compose);
  assert.equal(routeDecision.selected, 'compose');
  assert.equal(routeDecision.deliverableType, 'composite');
  assert.equal(routeDecision.selectedAssurance, 3);
  assert.deepEqual(routeDecision.candidatesConsidered, ['compose']);
});

test('router: compose assurance is derived from child verifier profiles', () => {
  const anyContract = composeContract({
    mode: 'any',
    verifiers: [
      { kind: 'schema', params: {} },
      { kind: 'testsuite', params: { op: 'sort', input: [5, 3, 9, 1] } },
    ],
  });
  assert.equal(routeVerifier(anyContract, { policy: { minAssurance: 1 } }).routeDecision.selectedAssurance, 1);
  assert.throws(() => routeVerifier(anyContract, { policy: { minAssurance: 3 } }), /no verifier meets required assurance/);

  const thresholdContract = composeContract({
    mode: 'threshold',
    threshold: 2,
    verifiers: [
      { kind: 'schema', params: {} },
      { kind: 'hash', params: {} },
      { kind: 'testsuite', params: { op: 'sort', input: [5, 3, 9, 1] } },
    ],
  });
  assert.equal(routeVerifier(thresholdContract, { policy: { minAssurance: 2 } }).routeDecision.selectedAssurance, 2);
});

test('settle: compose trace is signed into the receipt and tamper-evident', async () => {
  const output = [1, 3, 5, 9];
  const contract = composeContract({
    mode: 'all',
    verifiers: [
      { kind: 'schema', params: { schema: { type: 'array', items: { type: 'number' } } } },
      { kind: 'hash', params: { expectedHash: sha256hex(output) } },
    ],
  });
  const route = routeVerifier(contract, { policy: { minAssurance: 1 } });
  const result = await settle({
    contract,
    produceEvidence: () => ({ output }),
    verifier: route.verifier,
    routeDecision: route.routeDecision,
    rail: createMockEscrowRail(),
    settlementKey,
  });
  assert.equal(result.verdict.ok, true);
  assert.equal(result.receipt.verdict.trace.length, 2);
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);

  const tampered = structuredClone(result.receipt);
  tampered.verdict.trace[0].ok = false;
  assert.equal(verifyReceipt(tampered, settlementKey.publicKey), false);
});

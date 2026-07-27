import test from 'node:test';
import assert from 'node:assert/strict';

import { sha256hex } from '../src/protocol/canonical.mjs';
import { generateKeypair, keyId, sign } from '../src/protocol/crypto.mjs';
import { settle, verifyReceipt } from '../src/engine/deliveryproof.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { routeVerifier } from '../src/router/policy.mjs';
import { getVerifier, signedOracleVerifier } from '../src/verifiers/index.mjs';
import { buildSignedOracleAttestation, getTierBInterface } from '../src/verifiers/tier-b/index.mjs';

const settlementKey = generateKeypair();

function tamperBase64(value) {
  return `${value[0] === 'A' ? 'B' : 'A'}${value.slice(1)}`;
}

function base({ attester = generateKeypair(), output = { weather: 'rain' } } = {}) {
  const contract = {
    protocolVersion: 'deliveryproof/0.4-jcs1',
    id: 'c_oracle',
    buyer: 'buyer________',
    seller: 'seller_______',
    intent: 'prove a named source said a weather fact',
    deliverableType: 'application/json',
    predicate: {
      kind: 'signed-oracle',
      params: {
        allowedAttesterKeyIds: [keyId(attester.publicKey)],
        source: 'weather.example',
        claimType: 'weather-report',
        maxAgeMs: 60_000,
      },
    },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'n_oracle',
    createdAt: Date.now(),
  };
  const evidence = {
    protocolVersion: 'deliveryproof/0.4-jcs1',
    contractId: contract.id,
    nonce: contract.nonce,
    output,
    outputHash: sha256hex(output),
    producedAt: Date.now(),
  };
  evidence.attestations = [
    buildSignedOracleAttestation({
      contract,
      evidence,
      source: 'weather.example',
      claim: { type: 'weather-report', city: 'Amsterdam' },
      attesterKey: attester,
      signFn: sign,
    }),
  ];
  return { contract, evidence, attester };
}

test('signed-oracle: passes a valid Ed25519 provenance statement', () => {
  const { contract, evidence, attester } = base();
  const verdict = signedOracleVerifier.verify(contract, evidence);
  assert.equal(verdict.ok, true);
  assert.equal(verdict.tier, 'B');
  assert.equal(verdict.provenance.signerKeyId, keyId(attester.publicKey));
  assert.equal(verdict.provenance.source, 'weather.example');
  assert.match(verdict.reason, /attester said/);
});

test('signed-oracle: rejects replay across contract, nonce, or outputHash', () => {
  const { contract, evidence } = base();
  assert.equal(signedOracleVerifier.verify({ ...contract, id: 'other_contract' }, evidence).ok, false);
  assert.match(signedOracleVerifier.verify({ ...contract, id: 'other_contract' }, evidence).reason, /contract binding/);

  const wrongNonce = structuredClone(evidence);
  wrongNonce.attestations[0].statement.nonce = 'other_nonce';
  assert.equal(signedOracleVerifier.verify(contract, wrongNonce).ok, false);

  const wrongOutput = structuredClone(evidence);
  wrongOutput.output = { weather: 'sun' };
  wrongOutput.outputHash = sha256hex(wrongOutput.output);
  assert.equal(signedOracleVerifier.verify(contract, wrongOutput).ok, false);
});

test('signed-oracle: rejects unauthorized signer and tampered signatures', () => {
  const allowed = generateKeypair();
  const stranger = generateKeypair();
  const { contract, evidence } = base({ attester: allowed });
  const strangerEvidence = structuredClone(evidence);
  strangerEvidence.attestations = [
    buildSignedOracleAttestation({
      contract,
      evidence,
      source: 'weather.example',
      claim: { type: 'weather-report', city: 'Amsterdam' },
      attesterKey: stranger,
      signFn: sign,
    }),
  ];
  assert.equal(signedOracleVerifier.verify(contract, strangerEvidence).ok, false);
  assert.match(signedOracleVerifier.verify(contract, strangerEvidence).reason, /not allowed/);

  const tampered = structuredClone(evidence);
  tampered.attestations[0].signature = tamperBase64(tampered.attestations[0].signature);
  assert.equal(signedOracleVerifier.verify(contract, tampered).ok, false);
});

test('signed-oracle: rejects wrong source, wrong claim type, and stale statements', () => {
  const { contract, evidence } = base();
  const wrongSource = structuredClone(evidence);
  wrongSource.attestations[0].statement.source = 'other.example';
  assert.equal(signedOracleVerifier.verify(contract, wrongSource).ok, false);

  const wrongType = structuredClone(evidence);
  wrongType.attestations[0].statement.claim.type = 'stock-price';
  assert.equal(signedOracleVerifier.verify(contract, wrongType).ok, false);

  const stale = structuredClone(evidence);
  stale.attestations[0].statement.producedAt = Date.now() - 120_000;
  assert.equal(signedOracleVerifier.verify(contract, stale).ok, false);
});

test('signed-oracle: route + settle signs provenance into the receipt', async () => {
  const { contract, evidence } = base();
  const route = routeVerifier(contract, { policy: { deliverableType: 'provenance', minAssurance: 2 } });
  assert.equal(route.verifier, getVerifier('signed-oracle'));
  assert.equal(route.routeDecision.selected, 'signed-oracle');

  const result = await settle({
    contract,
    produceEvidence: () => evidence,
    verifier: route.verifier,
    routeDecision: route.routeDecision,
    rail: createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });
  assert.equal(result.verdict.ok, true);
  assert.equal(result.verdict.tier, 'B');
  assert.equal(result.receipt.decision, 'release');
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);

  const tampered = structuredClone(result.receipt);
  tampered.verdict.provenance.source = 'evil.example';
  assert.equal(verifyReceipt(tampered, settlementKey.publicKey), false);
});

test('Tier-B interfaces are explicit descriptors, not fake crypto implementations', () => {
  const tee = getTierBInterface('tee');
  const zktls = getTierBInterface('zktls');
  const zk = getTierBInterface('zk');
  for (const descriptor of [tee, zktls, zk]) {
    assert.equal(descriptor.implemented, false);
    assert.ok(descriptor.proves.includes('outputHash') || descriptor.proves.includes('origin'));
    assert.ok(descriptor.doesNotProve.length > 0);
    assert.ok(descriptor.requiredBindings.includes('contractId'));
    assert.ok(descriptor.requiredBindings.includes('nonce'));
    assert.ok(descriptor.requiredBindings.includes('outputHash'));
  }
  assert.throws(() => getTierBInterface('magic'), /unknown Tier-B interface/);
});

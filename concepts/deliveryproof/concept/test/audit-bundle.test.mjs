import test from 'node:test';
import assert from 'node:assert/strict';

import { canonicalize, sha256hex } from '../src/protocol/canonical.mjs';
import { generateKeypair } from '../src/protocol/crypto.mjs';
import { settle } from '../src/engine/deliveryproof.mjs';
import { buildAuditBundle } from '../src/operability/audit-bundle.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { builtinReplayVerifier } from '../src/verifiers/builtin-replay.mjs';

const settlementKey = generateKeypair();

function contract(extra = {}) {
  return {
    id: 'contract_audit_bundle_1',
    buyer: 'buyer________',
    seller: 'seller_______',
    intent: 'sort array ascending',
    deliverableType: 'application/json',
    predicate: { kind: 'builtin-replay', params: { op: 'sort', input: [5, 3, 9, 1] } },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'nonce-audit-bundle-1',
    createdAt: Date.now(),
    ...extra,
  };
}

async function settled() {
  const rail = createMockEscrowRail({ logger: false, settlementPublicKey: settlementKey.publicKey });
  const result = await settle({
    contract: contract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: builtinReplayVerifier,
    rail,
    settlementKey,
  });
  return { ...result, railStatus: rail.status(result.hold.holdId) };
}

test('audit bundle round-trips a real settled receipt', async () => {
  const result = await settled();
  const bundle = buildAuditBundle({
    receipt: result.receipt,
    contract: result.contract,
    evidence: result.evidence,
    railStatus: result.railStatus,
  });

  assert.equal(bundle.kind, 'deliveryproof-audit-bundle');
  assert.equal(bundle.receipt.hash, sha256hex(result.receipt));
  assert.equal(bundle.contract.hash, sha256hex(result.contract));
  assert.equal(bundle.evidence.hash, sha256hex(result.evidence));
  assert.equal(bundle.railStatus.hash, sha256hex(result.railStatus));
  assert.equal(bundle.receipt.contractHash, result.receipt.contractHash);
  assert.equal(bundle.receipt.evidenceHash, result.receipt.evidenceHash);
  assert.equal(bundle.receipt.routeDecision, result.receipt.routeDecision);
  assert.deepEqual(bundle.receipt.verdict, result.receipt.verdict);
  assert.equal(bundle.receipt.signerKeyId, result.receipt.signerKeyId);
  assert.equal(bundle.receipt.decision, 'release');
  assert.equal(bundle.railStatus.state, 'captured');
  assert.deepEqual(bundle.checks, {
    contractHashMatchesReceipt: true,
    evidenceHashMatchesReceipt: true,
    evidenceContractIdMatchesReceipt: true,
    railStatusPresent: true,
    railHoldMatchesReceipt: true,
    railContractIdMatchesReceipt: true,
    railContractHashMatchesReceipt: true,
    railRailIdMatchesReceipt: true,
    railAmountMatchesReceipt: true,
    railCurrencyMatchesReceipt: true,
    railStateMatchesDecision: true,
  });
  const { canonicalHash, canonicalBytes, ...canonicalBody } = bundle;
  assert.equal(canonicalHash, sha256hex(canonicalBody));
  assert.equal(canonicalBytes, canonicalize(canonicalBody).length);
  assert.equal(Number.isSafeInteger(bundle.canonicalBytes), true);
});

test('audit bundle detects tampering of receipt-bound contract, evidence, and rail fields', async () => {
  const result = await settled();

  const contractTamper = buildAuditBundle({
    receipt: result.receipt,
    contract: { ...result.contract, price: { amount: 6, currency: 'USDC' } },
    evidence: result.evidence,
    railStatus: result.railStatus,
  });
  assert.equal(contractTamper.checks.contractHashMatchesReceipt, false);

  const evidenceTamper = buildAuditBundle({
    receipt: result.receipt,
    contract: result.contract,
    evidence: { ...result.evidence, output: [9, 5, 3, 1], outputHash: sha256hex([9, 5, 3, 1]) },
    railStatus: result.railStatus,
  });
  assert.equal(evidenceTamper.checks.evidenceHashMatchesReceipt, false);

  const receiptTamper = buildAuditBundle({
    receipt: { ...result.receipt, contractHash: sha256hex({ forged: true }) },
    contract: result.contract,
    evidence: result.evidence,
    railStatus: result.railStatus,
  });
  assert.equal(receiptTamper.checks.contractHashMatchesReceipt, false);

  const railTamper = buildAuditBundle({
    receipt: result.receipt,
    contract: result.contract,
    evidence: result.evidence,
    railStatus: { ...result.railStatus, state: 'refunded' },
  });
  assert.equal(railTamper.checks.railStateMatchesDecision, false);

  const railContractHashTamper = buildAuditBundle({
    receipt: result.receipt,
    contract: result.contract,
    evidence: result.evidence,
    railStatus: { ...result.railStatus, contractHash: sha256hex({ forged: true }) },
  });
  assert.equal(railContractHashTamper.checks.railContractHashMatchesReceipt, false);
});

test('audit bundle handles absent optional railStatus', async () => {
  const result = await settled();
  const bundle = buildAuditBundle({
    receipt: result.receipt,
    contract: result.contract,
    evidence: result.evidence,
  });

  assert.equal(bundle.railStatus, null);
  assert.equal(bundle.checks.railStatusPresent, false);
  assert.equal(bundle.checks.railHoldMatchesReceipt, null);
  assert.equal(bundle.checks.railContractHashMatchesReceipt, null);
  assert.equal(bundle.checks.railStateMatchesDecision, null);
  assert.equal(typeof canonicalize(bundle), 'string');
});

// test/helpers/receipts.mjs
// Signed-receipt + contract fixtures for the adapter unit tests, mirroring
// makeReceipt/makeContract in deliveryproof/concept/src/testing/rail-conformance.mjs.
//
// SCOPE / HONESTY: test fixtures only. NO chain, NO RPC, NO live tx. These build
// REAL canonicalized, REAL-signed DeliveryProof receipts (via the core
// generateKeypair/sign/canonicalize/keyId) so the rail's verifyReceipt() and
// 7-field binding run against genuine signatures, not stubs — the tests exercise
// the production verification path, not a bypass. TESTNET / LOCAL ONLY.

import { canonicalize, sha256hex, generateKeypair, sign, keyId } from 'deliveryproof';

export const TEST_PROTOCOL_VERSION = 'deliveryproof/0.4-jcs1';

/**
 * @returns {{ publicKey: string, privateKey: string }}
 */
export function makeSettlementKey() {
  return generateKeypair();
}

/**
 * Build a DeliveryContract whose price (5/USDC) matches the in-memory client's
 * auto-provisioned funded job, so a hold binds cleanly. railId is bound to the
 * rail so receipts produced from it satisfy the rail's railId check.
 *
 * @param {{ id: string }} rail
 * @param {string} label
 * @param {Object} [overrides]
 * @returns {Object}
 */
export function makeContract(rail, label, overrides = {}) {
  return {
    protocolVersion: TEST_PROTOCOL_VERSION,
    id: `contract_${slug(label)}`,
    buyer: 'buyer_unit',
    seller: 'seller_unit',
    intent: `rail unit ${label}`,
    deliverableType: 'application/json',
    predicate: { kind: 'testsuite', params: { op: 'identity' } },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: rail.id,
    nonce: `nonce_${slug(label)}`,
    createdAt: 1,
    idempotencyKey: `rail-unit:${rail.id}:${slug(label)}`,
    ...overrides,
  };
}

/**
 * Build a REAL-signed DeliveryProof receipt bound to a contract + hold. `patch`
 * tampers a single field AFTER the signed body is assembled-but-before signing for
 * binding fields, or replaces fields for contradiction tests; the signature always
 * covers the final body so signature verification itself stays valid (the rail must
 * reject on BINDING/consistency grounds, not because the signature broke).
 *
 * @param {Object} args
 * @param {Object} args.contract
 * @param {{ holdId: string, amount: *, currency: string }} args.hold
 * @param {'release'|'refund'} args.decision
 * @param {{ publicKey: string, privateKey: string }} args.settlementKey
 * @param {Object} [args.patch]
 * @returns {Object} a signed receipt
 */
export function makeReceipt({ contract, hold, decision, settlementKey, patch = {} }) {
  const evidence = { contractId: contract.id, output: { ok: decision === 'release' } };
  const verdict = {
    ok: decision === 'release',
    tier: 'A',
    verifier: 'rail-unit',
    reason: decision === 'release' ? 'fixture passed' : 'fixture failed',
    checkedAt: 2,
  };
  const unsigned = {
    protocolVersion: TEST_PROTOCOL_VERSION,
    contractId: contract.id,
    contractHash: sha256hex(contract),
    railId: contract.railId,
    holdId: hold.holdId,
    amount: hold.amount,
    currency: hold.currency,
    verdict,
    evidenceHash: sha256hex(evidence),
    routeDecision: null,
    lifecycle: [
      { state: 'authorizing', at: 1 },
      { state: 'held', at: 1, holdId: hold.holdId },
      { state: 'decision', at: 2, decision },
    ],
    nonceRegistryKey: null,
    decision,
    signerKeyId: keyId(settlementKey.publicKey),
    issuedAt: 3,
    ...patch,
  };
  return {
    ...unsigned,
    signature: sign(settlementKey.privateKey, canonicalize(unsigned)),
  };
}

function slug(value) {
  return String(value).replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '').toLowerCase();
}

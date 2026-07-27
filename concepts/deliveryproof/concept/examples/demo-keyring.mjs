// examples/demo-keyring.mjs
//
// Shows v0.9 verification-only key rotation. Receipts are still signed by the
// settlement key used in settle(); verifyReceipt can now verify against a PEM
// string, a public-key array, or a keyring. This does not thread a signer through
// settlement and does not re-sign old receipts.
//
//   Run: node examples/demo-keyring.mjs

import {
  createInMemoryKeyring,
  createMockEscrowRail,
  generateKeypair,
  keyId,
  settle,
  builtinReplayVerifier,
  verifyReceipt,
} from '../src/index.mjs';

const HEAVY = '='.repeat(74);
const LINE = '-'.repeat(74);

function kv(label, value) {
  console.log('  ' + String(label).padEnd(32) + ': ' + value);
}

const oldSettlementKey = generateKeypair();
const newSettlementKey = generateKeypair();
const seller = generateKeypair();
const buyer = generateKeypair();

const contract = {
  id: 'dc_keyring_demo',
  buyer: keyId(buyer.publicKey),
  seller: keyId(seller.publicKey),
  intent: 'sort array ascending',
  deliverableType: 'application/json',
  predicate: { kind: 'builtin-replay', params: { op: 'sort', input: [5, 3, 9, 1] } },
  price: { amount: 5, currency: 'USDC' },
  sla: { deadlineMs: 60000 },
  refundRule: 'full-refund-on-fail',
  railId: 'escrow-mock',
  nonce: 'nonce-keyring-demo',
  createdAt: Date.now(), // real timestamp: an epoch-0 contract is long past its SLA deadline
};

console.log('\n' + HEAVY);
console.log('  DeliveryProof v0.9.1 — receipt verification with keyrings');
console.log(HEAVY);
console.log(`
  A receipt signed before rotation should remain verifiable after the operator
  publishes a keyring containing old and new settlement public keys. This is
  verification-only rotation: no KMS, no signer injection, and no receipt rewrite.
`);

const result = await settle({
  contract,
  produceEvidence: () => ({ output: [1, 3, 5, 9] }),
  verifier: builtinReplayVerifier,
  rail: createMockEscrowRail({ settlementPublicKey: oldSettlementKey.publicKey }),
  settlementKey: oldSettlementKey,
});

const keyring = createInMemoryKeyring([oldSettlementKey.publicKey, newSettlementKey.publicKey]);
const stranger = generateKeypair();
const unknownSignerReceipt = {
  ...result.receipt,
  signerKeyId: keyId(stranger.publicKey),
};

console.log(LINE);
console.log('  Rotation verification');
console.log(LINE);
kv('receipt signerKeyId', result.receipt.signerKeyId);
kv('old keyId', keyId(oldSettlementKey.publicKey));
kv('new keyId', keyId(newSettlementKey.publicKey));
kv('PEM string verifies?', verifyReceipt(result.receipt, oldSettlementKey.publicKey));
kv('{ keys: [old,new] } verifies?', verifyReceipt(result.receipt, {
  keys: [oldSettlementKey.publicKey, newSettlementKey.publicKey],
}));
kv('{ keyring } verifies?', verifyReceipt(result.receipt, { keyring }));
kv('new key alone verifies?', verifyReceipt(result.receipt, { keys: [newSettlementKey.publicKey] }));
kv('unknown signerKeyId verifies?', verifyReceipt(unknownSignerReceipt, { keyring }));

console.log('\n' + HEAVY);
console.log('  Takeaway: old receipts survive public-key rotation without re-signing.');
console.log('  Unknown signer ids and wrong keys return false, not throws.');
console.log(HEAVY + '\n');

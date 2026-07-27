import test from 'node:test';
import assert from 'node:assert/strict';

import { canonicalize, sha256hex } from '../src/protocol/canonical.mjs';
import { generateKeypair, keyId, sign } from '../src/protocol/crypto.mjs';
import { createInMemoryKeyring } from '../src/protocol/signer.mjs';
import { settle, verifyReceipt } from '../src/engine/deliveryproof.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { builtinReplayVerifier } from '../src/verifiers/builtin-replay.mjs';

function sortContract() {
  return {
    id: 'contract_keyring_1',
    buyer: 'buyer________',
    seller: 'seller_______',
    intent: 'sort array ascending',
    deliverableType: 'application/json',
    predicate: { kind: 'builtin-replay', params: { op: 'sort', input: [5, 3, 9, 1] } },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'nonce-keyring-1',
    createdAt: 0,
  };
}

async function settledWith(settlementKey) {
  return settle({
    contract: sortContract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: builtinReplayVerifier,
    rail: createMockEscrowRail({ logger: false, settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });
}

test('verifyReceipt keyring verifies rotated keys without mutating receipt bytes', async () => {
  const active = generateKeypair();
  const next = generateKeypair();
  const result = await settledWith(active);
  const before = canonicalize(result.receipt);

  assert.equal(verifyReceipt(result.receipt, { keys: [next.publicKey, active.publicKey] }), true);
  assert.equal(verifyReceipt(result.receipt, { keyring: createInMemoryKeyring([next.publicKey, active.publicKey]) }), true);
  assert.equal(canonicalize(result.receipt), before);
});

test('verifyReceipt keyring returns false for unknown signerKeyId and empty keyrings', async () => {
  const active = generateKeypair();
  const stranger = generateKeypair();
  const result = await settledWith(active);
  const unknownSigner = { ...result.receipt, signerKeyId: keyId(stranger.publicKey) };

  assert.equal(verifyReceipt(unknownSigner, { keys: [active.publicKey] }), false);
  assert.equal(verifyReceipt(result.receipt, { keys: [] }), false);
  assert.equal(verifyReceipt(result.receipt, { keyring: createInMemoryKeyring([]) }), false);
});

test('verifyReceipt keyring returns false for tampered signatures under a known keyId', async () => {
  const active = generateKeypair();
  const result = await settledWith(active);
  const tampered = { ...result.receipt, evidenceHash: sha256hex({ forged: true }) };

  assert.equal(verifyReceipt(tampered, { keys: [active.publicKey] }), false);
  assert.doesNotThrow(() => verifyReceipt(tampered, { keys: [active.publicKey] }));
});

test('verifyReceipt keyring handles duplicate keyIds deterministically', async () => {
  const active = generateKeypair();
  const next = generateKeypair();
  const result = await settledWith(active);
  const keyring = createInMemoryKeyring([next.publicKey, active.publicKey, active.publicKey]);

  assert.deepEqual(keyring.get(keyId(active.publicKey)), [active.publicKey, active.publicKey]);
  assert.equal(verifyReceipt(result.receipt, { keyring }), true);
});

test('verifyReceipt keyring scans keys when direct keyId lookup is empty', async () => {
  const active = generateKeypair();
  const result = await settledWith(active);
  const keyring = {
    keys: [active.publicKey],
    get: () => [],
  };
  assert.equal(verifyReceipt(result.receipt, { keyring }), true);
});

test('verifyReceipt keyring arms are false-not-throw for malformed trust inputs', async () => {
  const active = generateKeypair();
  const result = await settledWith(active);

  assert.equal(verifyReceipt(result.receipt, {}), false);
  assert.equal(verifyReceipt(result.receipt, { keyring: { keys: [active.publicKey], get: () => { throw new Error('boom'); } } }), false);
  assert.equal(verifyReceipt({ ...result.receipt, signature: undefined }, { keys: [active.publicKey] }), false);
});

test('verifyReceipt PEM string path still verifies receipts signed by settle', async () => {
  const active = generateKeypair();
  const result = await settledWith(active);
  const before = canonicalize(result.receipt);
  assert.equal(verifyReceipt(result.receipt, active.publicKey), true);
  assert.equal(verifyReceipt({ ...result.receipt, signature: 'not-valid' }, active.publicKey), false);
  assert.equal(canonicalize(result.receipt), before);
});

test('verifyReceipt keyring can verify a receipt signed by a later rotation key', async () => {
  const old = generateKeypair();
  const active = generateKeypair();
  const result = await settledWith(active);
  assert.equal(verifyReceipt(result.receipt, { keys: [old.publicKey, active.publicKey] }), true);

  const { signature: _oldSignature, ...unsigned } = result.receipt;
  const resigned = {
    ...unsigned,
    signerKeyId: keyId(old.publicKey),
  };
  const signature = sign(old.privateKey, canonicalize(resigned));
  assert.equal(verifyReceipt({ ...resigned, signature }, { keys: [old.publicKey, active.publicKey] }), true);
});

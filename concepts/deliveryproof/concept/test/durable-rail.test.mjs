import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

import { canonicalize, sha256hex } from '../src/protocol/canonical.mjs';
import { generateKeypair, keyId, sign } from '../src/protocol/crypto.mjs';
import { settle, verifyReceipt } from '../src/engine/deliveryproof.mjs';
import { createDurableEscrowRail } from '../src/rails/durable-rail.mjs';
import { builtinReplayVerifier } from '../src/verifiers/builtin-replay.mjs';

const settlementKey = generateKeypair();
const durableContractCreatedAt = Date.now();

function withWal(t) {
  const dir = mkdtempSync(join(tmpdir(), 'deliveryproof-durable-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return join(dir, 'rail.jsonl');
}

function contract(extra = {}) {
  return {
    protocolVersion: 'deliveryproof/0.4-jcs1',
    id: 'contract_durable_1',
    buyer: 'buyer________',
    seller: 'seller_______',
    intent: 'sort array ascending',
    deliverableType: 'application/json',
    predicate: { kind: 'builtin-replay', params: { op: 'sort', input: [5, 3, 9, 1] } },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-durable',
    nonce: 'nonce-durable-1',
    createdAt: durableContractCreatedAt,
    idempotencyKey: 'auth-key-1',
    ...extra,
  };
}

function receipt(decision, extra = {}) {
  const { signingKey = settlementKey, ...receiptExtra } = extra;
  const unsignedReceipt = {
    protocolVersion: 'deliveryproof/0.4-jcs1',
    contractId: 'contract_durable_1',
    contractHash: sha256hex(contract()),
    railId: 'escrow-durable',
    holdId: extra.holdId ?? 'hold_1',
    amount: 5,
    currency: 'USDC',
    verdict: {
      ok: decision === 'release',
      tier: 'A',
      verifier: 'builtin-replay',
      reason: decision,
      checkedAt: 1,
    },
    evidenceHash: sha256hex({ output: [1, 3, 5, 9] }),
    routeDecision: null,
    lifecycle: [],
    nonceRegistryKey: null,
    decision,
    signerKeyId: keyId(settlementKey.publicKey),
    issuedAt: 2,
    ...receiptExtra,
  };
  return {
    ...unsignedReceipt,
    signature: sign(signingKey.privateKey, canonicalize(unsignedReceipt)),
  };
}

test('durable rail: authorize is idempotent and rejects fingerprint conflicts', (t) => {
  const logPath = withWal(t);
  const rail = createDurableEscrowRail({ logPath, settlementPublicKey: settlementKey.publicKey });
  const first = rail.authorize(contract());
  const again = rail.authorize(contract());
  assert.equal(again.holdId, first.holdId);
  assert.equal(again.state, 'held');

  assert.throws(
    () => rail.authorize(contract({ price: { amount: 6, currency: 'USDC' } })),
    /idempotency conflict/,
  );

  const recovered = createDurableEscrowRail({ logPath, settlementPublicKey: settlementKey.publicKey });
  const afterRestart = recovered.authorize(contract());
  assert.equal(afterRestart.holdId, first.holdId);
  assert.equal(recovered.status(first.holdId).state, 'held');
});

test('durable rail: terminal settlement is idempotent and rejects conflicting receipts', (t) => {
  const rail = createDurableEscrowRail({
    logPath: withWal(t),
    settlementPublicKey: settlementKey.publicKey,
  });
  const hold = rail.authorize(contract());
  const release = receipt('release', {
    holdId: hold.holdId,
    settlementAttemptId: 'settle-attempt-1',
  });

  const captured = rail.capture(hold, release);
  assert.equal(captured.state, 'captured');
  const replay = rail.capture(hold, release);
  assert.deepEqual(replay, captured);

  assert.throws(
    () => rail.capture(hold, receipt('release', {
      holdId: hold.holdId,
      settlementAttemptId: 'settle-attempt-1',
      issuedAt: 3,
    })),
    /idempotency conflict/,
  );
  assert.throws(
    () => rail.refund(hold, receipt('refund', { holdId: hold.holdId, settlementAttemptId: 'settle-attempt-2' })),
    /conflicting terminal settlement/,
  );
});

test('durable rail: terminal settlement rejects receipts not bound to the hold', (t) => {
  const rail = createDurableEscrowRail({
    logPath: withWal(t),
    settlementPublicKey: settlementKey.publicKey,
  });
  const hold = rail.authorize(contract());
  const release = receipt('release', { holdId: hold.holdId });

  assert.throws(
    () => rail.capture(hold, { ...release, holdId: 'wrong-hold' }),
    /receipt does not match hold.*holdId/,
  );
  assert.throws(
    () => rail.capture(hold, { ...release, railId: 'escrow-mock' }),
    /receipt does not match hold.*railId/,
  );
  assert.throws(
    () => rail.capture(hold, { ...release, contractHash: sha256hex({ forged: true }) }),
    /receipt does not match hold.*contractHash/,
  );
  assert.equal(rail.status(hold.holdId).state, 'held');
});

test('durable rail: default signature verification rejects forged direct receipts', (t) => {
  const rail = createDurableEscrowRail({ logPath: withWal(t), settlementPublicKey: settlementKey.publicKey });
  const hold = rail.authorize(contract());
  const forged = receipt('release', { holdId: hold.holdId, signingKey: generateKeypair() });

  assert.throws(
    () => rail.capture(hold, forged),
    /signature failed verification/,
  );
  assert.equal(rail.status(hold.holdId).state, 'held');
});

test('durable rail: WAL recovery preserves terminal state across restarts', (t) => {
  const logPath = withWal(t);
  const rail = createDurableEscrowRail({ logPath, settlementPublicKey: settlementKey.publicKey });
  const hold = rail.authorize(contract());
  const release = receipt('release', { holdId: hold.holdId });
  rail.capture(hold, release);

  const recovered = createDurableEscrowRail({ logPath, settlementPublicKey: settlementKey.publicKey });
  assert.equal(recovered.status(hold.holdId).state, 'captured');
  assert.equal(recovered.capture(hold.holdId, release).state, 'captured');
});

test('durable rail: settle() composes with the durable adapter and recovers final hold', async (t) => {
  const logPath = withWal(t);
  const rail = createDurableEscrowRail({ logPath, settlementPublicKey: settlementKey.publicKey });
  const result = await settle({
    contract: contract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: builtinReplayVerifier,
    rail,
    settlementKey,
  });

  assert.equal(result.verdict.ok, true);
  assert.equal(result.receipt.decision, 'release');
  assert.equal(result.hold.state, 'captured');
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);

  const recovered = createDurableEscrowRail({ logPath, settlementPublicKey: settlementKey.publicKey });
  assert.equal(recovered.status(result.hold.holdId).state, 'captured');
});

test('durable rail: corrupt WAL lines fail closed on startup', (t) => {
  const logPath = withWal(t);
  writeFileSync(logPath, '{not json}\n', 'utf8');
  assert.throws(
    () => createDurableEscrowRail({ logPath, settlementPublicKey: settlementKey.publicKey }),
    /corrupt WAL line/,
  );
});

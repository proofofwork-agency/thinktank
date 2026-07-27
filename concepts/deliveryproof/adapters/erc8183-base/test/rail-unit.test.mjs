// test/rail-unit.test.mjs
// White-box unit tests for createErc8183Rail's money-safety gates.
//
// SCOPE / HONESTY: drives the real rail over the in-memory (FAKE) client only — NO
// chain, NO wallet, NO RPC, NO keys, NO live tx. Every receipt here is a REAL,
// canonically-signed DeliveryProof receipt (see helpers/receipts.mjs), so the
// 7-field binding, verdict<->decision consistency, and reconcile-via-getJob
// idempotency are exercised on the production verification path. These cover the
// gates runRailConformance asserts plus the chain-specific reconcile behavior the
// generic suite cannot reach (a job that is already Completed/Rejected on-chain).
// TESTNET / LOCAL ONLY — no mainnet, no real funds, no autonomous live tx.

import test from 'node:test';
import assert from 'node:assert/strict';

import { sha256hex } from 'deliveryproof';
import {
  createErc8183Rail,
  createInMemoryErc8183Client,
  JobStatus,
  Erc8183NotSettleableError,
  Erc8183RailError,
} from '../src/index.mjs';
import { makeSettlementKey, makeContract, makeReceipt } from './helpers/receipts.mjs';

/**
 * Build a rail + in-memory client. Returns both so a test can seed job state.
 * @param {Object} [railOpts]
 */
function makeRail(railOpts = {}) {
  const client = createInMemoryErc8183Client();
  // Since v0.10 a settlement key is mandatory unless the caller opts out. Tests
  // that exercise job-state mechanics rather than receipt authenticity take the
  // opt-out; any test passing settlementPublicKey overrides it below.
  const rail = createErc8183Rail({ client, allowUnsignedReceipts: true, ...railOpts });
  return { rail, client };
}

test('authorize throws Erc8183NotSettleableError when the job is not Submitted (Open)', async () => {
  const { rail, client } = makeRail();
  const contract = makeContract(rail, 'authorize-open');
  // Pre-seed the resolved jobId in an Open (non-Submitted) status. The resolver
  // falls back to idempotencyKey, so seed that exact key.
  client.seedJob(contract.idempotencyKey, { status: JobStatus.Open });

  await assert.rejects(
    () => rail.authorize(contract),
    (err) => {
      assert.ok(err instanceof Erc8183NotSettleableError, `expected Erc8183NotSettleableError, got ${err}`);
      assert.equal(err.status, JobStatus.Open);
      return true;
    },
  );
});

test('authorize also refuses a Funded job (only Submitted is settleable)', async () => {
  const { rail, client } = makeRail();
  const contract = makeContract(rail, 'authorize-funded');
  client.seedJob(contract.idempotencyKey, { status: JobStatus.Funded });
  await assert.rejects(() => rail.authorize(contract), Erc8183NotSettleableError);
});

test('capture reconciles to an idempotent no-tx captured Hold when the job is already Completed', async () => {
  const settlementKey = makeSettlementKey();
  const { rail } = makeRail({ settlementPublicKey: settlementKey.publicKey, requireSignature: true });
  const contract = makeContract(rail, 'reconcile-completed');
  const hold = await rail.authorize(contract);
  const release = makeReceipt({ contract, hold, decision: 'release', settlementKey });

  // First capture flips the in-memory job Submitted -> Completed.
  const first = await rail.capture(hold, release);
  assert.equal(first.state, 'captured');

  // Second capture of the SAME receipt: the in-memory client would THROW on a
  // second complete(), so a no-tx reconcile (read Completed, return captured) is
  // the ONLY way this can succeed. It proves idempotency comes from getJob, not a
  // lenient fake.
  const replay = await rail.capture(hold, release);
  assert.equal(replay.state, 'captured');
  assert.equal(replay.holdId, hold.holdId);

  const status = await rail.status(hold.holdId);
  assert.equal(status.state, 'captured');
});

test('refund of an already-Completed job is a hard conflict (never silently flips money)', async () => {
  const settlementKey = makeSettlementKey();
  const { rail } = makeRail({ settlementPublicKey: settlementKey.publicKey, requireSignature: true });
  const contract = makeContract(rail, 'conflict-completed-then-refund');
  const hold = await rail.authorize(contract);
  const release = makeReceipt({ contract, hold, decision: 'release', settlementKey });
  const refund = makeReceipt({ contract, hold, decision: 'refund', settlementKey });

  await rail.capture(hold, release); // job -> Completed

  await assert.rejects(
    () => rail.refund(hold, refund),
    (err) => {
      assert.ok(err instanceof Erc8183RailError, `expected Erc8183RailError, got ${err}`);
      assert.match(err.message, /conflict/i);
      return true;
    },
  );
  // The job stays Completed/captured — the conflict did not refund anything.
  assert.equal((await rail.status(hold.holdId)).state, 'captured');
});

test('capture of an already-Rejected job is a hard conflict', async () => {
  const settlementKey = makeSettlementKey();
  const { rail } = makeRail({ settlementPublicKey: settlementKey.publicKey, requireSignature: true });
  const contract = makeContract(rail, 'conflict-rejected-then-capture');
  const hold = await rail.authorize(contract);
  const release = makeReceipt({ contract, hold, decision: 'release', settlementKey });
  const refund = makeReceipt({ contract, hold, decision: 'refund', settlementKey });

  await rail.refund(hold, refund); // job -> Rejected

  await assert.rejects(() => rail.capture(hold, release), /conflict/i);
  assert.equal((await rail.status(hold.holdId)).state, 'refunded');
});

test('refund reconciles to an idempotent no-tx refunded Hold when already Rejected', async () => {
  const settlementKey = makeSettlementKey();
  const { rail } = makeRail({ settlementPublicKey: settlementKey.publicKey, requireSignature: true });
  const contract = makeContract(rail, 'reconcile-rejected');
  const hold = await rail.authorize(contract);
  const refund = makeReceipt({ contract, hold, decision: 'refund', settlementKey });

  const first = await rail.refund(hold, refund);
  assert.equal(first.state, 'refunded');
  const replay = await rail.refund(hold, refund);
  assert.equal(replay.state, 'refunded');
  assert.equal((await rail.status(hold.holdId)).state, 'refunded');
});

test('7-field binding: capture rejects a receipt with ANY single tampered field', async () => {
  const settlementKey = makeSettlementKey();
  // Tamper one field at a time. Each value is wrong vs the authorized binding:
  //   decision      -> refund (capture expects release; rejected at the decision gate)
  //   holdId        -> a foreign hold id
  //   contractId    -> a foreign contract id
  //   contractHash  -> a hash of different bytes
  //   railId        -> a foreign rail id
  //   amount        -> 999 (funded job is 5)
  //   currency      -> EUR (funded job is USDC)
  const tampers = [
    ['decision', 'refund'],
    ['holdId', 'erc8183:local:0xlocal:not-this-job'],
    ['contractId', 'wrong-contract'],
    ['contractHash', sha256hex({ forged: true })],
    ['railId', 'wrong-rail'],
    ['amount', 999],
    ['currency', 'EUR'],
  ];

  for (const [field, value] of tampers) {
    const { rail } = makeRail({ settlementPublicKey: settlementKey.publicKey, requireSignature: true });
    const contract = makeContract(rail, `binding-${field}`);
    const hold = await rail.authorize(contract);
    const receipt = makeReceipt({ contract, hold, decision: 'release', settlementKey, patch: { [field]: value } });

    await assert.rejects(
      () => rail.capture(hold, receipt),
      (err) => {
        assert.ok(err instanceof Erc8183RailError, `tampered ${field}: expected Erc8183RailError, got ${err}`);
        return true;
      },
      `capture must reject a receipt with tampered ${field}`,
    );
    // The hold remains held; nothing settled.
    assert.equal((await rail.status(hold.holdId)).state, 'held', `hold must stay held after tampered ${field}`);
  }
});

test('verdict consistency: capture rejects a release receipt whose verdict.ok is false', async () => {
  const settlementKey = makeSettlementKey();
  const { rail } = makeRail({ settlementPublicKey: settlementKey.publicKey, requireSignature: true });
  const contract = makeContract(rail, 'contradictory-verdict');
  const hold = await rail.authorize(contract);
  // decision stays 'release' (passes the decision gate) but verdict.ok is forced
  // false — an internally contradictory receipt the engine never emits. The rail
  // must refuse to pay on it at the money layer.
  const receipt = makeReceipt({
    contract,
    hold,
    decision: 'release',
    settlementKey,
    patch: { verdict: { ok: false, tier: 'A', verifier: 'rail-unit', reason: 'forced contradiction', checkedAt: 2 } },
  });

  await assert.rejects(
    () => rail.capture(hold, receipt),
    (err) => {
      assert.ok(err instanceof Erc8183RailError);
      assert.match(err.message, /contradict|verdict/i);
      return true;
    },
  );
  assert.equal((await rail.status(hold.holdId)).state, 'held');
});

test('decision gate: capture refuses a refund-decision receipt and refund refuses a release receipt', async () => {
  const settlementKey = makeSettlementKey();
  const { rail } = makeRail({ settlementPublicKey: settlementKey.publicKey, requireSignature: true });
  const contract = makeContract(rail, 'decision-gate');
  const hold = await rail.authorize(contract);
  const release = makeReceipt({ contract, hold, decision: 'release', settlementKey });
  const refund = makeReceipt({ contract, hold, decision: 'refund', settlementKey });

  await assert.rejects(() => rail.capture(hold, refund), /decision must be release/i);
  await assert.rejects(() => rail.refund(hold, release), /decision must be refund/i);
  assert.equal((await rail.status(hold.holdId)).state, 'held');
});

test('cross-hold replay: a receipt minted for one hold cannot capture a different hold', async () => {
  const settlementKey = makeSettlementKey();
  const { rail } = makeRail({ settlementPublicKey: settlementKey.publicKey, requireSignature: true });
  const contractA = makeContract(rail, 'cross-hold-a');
  const contractB = makeContract(rail, 'cross-hold-b');
  const holdA = await rail.authorize(contractA);
  const holdB = await rail.authorize(contractB);
  const receiptA = makeReceipt({ contract: contractA, hold: holdA, decision: 'release', settlementKey });

  await assert.rejects(() => rail.capture(holdB, receiptA), Erc8183RailError);
  assert.equal((await rail.status(holdB.holdId)).state, 'held');
});

test('signature enforcement: requireSignature rejects a receipt signed by a foreign key', async () => {
  const settlementKey = makeSettlementKey();
  const foreignKey = makeSettlementKey();
  const { rail } = makeRail({ settlementPublicKey: settlementKey.publicKey, requireSignature: true });
  const contract = makeContract(rail, 'foreign-signature');
  const hold = await rail.authorize(contract);
  // Build a fully-consistent receipt but sign it with a DIFFERENT key.
  const forged = makeReceipt({ contract, hold, decision: 'release', settlementKey: foreignKey });

  await assert.rejects(
    () => rail.capture(hold, forged),
    (err) => {
      assert.match(err.message, /signature/i);
      return true;
    },
  );
  assert.equal((await rail.status(hold.holdId)).state, 'held');
});

test('construction without a settlementPublicKey fails closed (v0.10 default)', () => {
  const client = createInMemoryErc8183Client();
  // Pre-0.10 this only threw when requireSignature was explicitly set. Now the
  // absence of a key is itself the error: the unsafe configuration must be
  // chosen deliberately, not inherited by default.
  assert.throws(
    () => createErc8183Rail({ client }),
    /settlementPublicKey is required/,
  );
  assert.throws(
    () => createErc8183Rail({ client, requireSignature: true }),
    /settlementPublicKey is required/,
  );
  // The explicit opt-out is the only way through without a key.
  assert.ok(createErc8183Rail({ client, allowUnsignedReceipts: true }));
});

test('restart without re-authorize: capture FAILS CLOSED (binding is never derived from the receipt)', async () => {
  // Money-safety regression. The contract-identity binding is remembered in-memory
  // at authorize and is NEVER reconstructed from the receipt being settled. After a
  // "restart" (a fresh rail sharing the prior client's job Map but with no cached
  // binding), a capture MUST fail closed instead of trusting the receipt's own
  // contractId/contractHash — otherwise a forged receipt with the right holdId +
  // live amount/currency could release escrow.
  const settlementKey = makeSettlementKey();
  const client = createInMemoryErc8183Client();
  const rail1 = createErc8183Rail({ client, settlementPublicKey: settlementKey.publicKey, requireSignature: true });
  const contract = makeContract(rail1, 'restart-rebind');
  const hold = await rail1.authorize(contract); // binding cached on rail1 only
  const release = makeReceipt({ contract, hold, decision: 'release', settlementKey });

  // "Restart": a new rail inherits the same client (job survives) but never saw authorize.
  const rail2 = createErc8183Rail({
    previousRail: rail1,
    settlementPublicKey: settlementKey.publicKey,
    requireSignature: true,
  });

  await assert.rejects(
    () => rail2.capture(hold, release),
    (err) => {
      assert.ok(err instanceof Erc8183RailError, `expected Erc8183RailError, got ${err}`);
      assert.match(err.message, /no authorized binding/i);
      return true;
    },
    'capture after restart without re-authorize must fail closed',
  );
  // The job is untouched — still Submitted/held.
  assert.equal((await rail2.status(hold.holdId)).state, 'held');

  // The correct, safe flow: re-authorize on rail2 (re-present the funding contract),
  // which re-establishes the authoritative binding; only then does capture succeed.
  await rail2.authorize(contract);
  const settled = await rail2.capture(hold, release);
  assert.equal(settled.state, 'captured');
});

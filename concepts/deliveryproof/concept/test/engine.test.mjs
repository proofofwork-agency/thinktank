import test from 'node:test';
import assert from 'node:assert/strict';

import { canonicalize, sha256hex, sha256utf8 } from '../src/protocol/canonical.mjs';
import { generateKeypair, keyId, sign } from '../src/protocol/crypto.mjs';
import { assertReceiptMeetsPolicy, settle, verifyReceipt } from '../src/engine/deliveryproof.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { testsuiteVerifier } from '../src/verifiers/testsuite.mjs';
import { hashVerifier } from '../src/verifiers/hash.mjs';
import { schemaVerifier } from '../src/verifiers/schema.mjs';
import { datasetVerifier } from '../src/verifiers/dataset.mjs';

const settlementKey = generateKeypair();

/** A sort contract used by several scenarios. */
function sortContract() {
  return {
    id: 'contract_sort_1',
    buyer: 'buyer________',
    seller: 'seller_______',
    intent: 'sort array ascending',
    deliverableType: 'application/json',
    predicate: { kind: 'testsuite', params: { op: 'sort', input: [5, 3, 9, 1] } },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'nonce-sort-1',
    createdAt: 0,
  };
}

function mockRailReceiptFor(hold, decision, extra = {}) {
  return {
    protocolVersion: 'deliveryproof/0.4-jcs1',
    contractId: hold.contractId,
    contractHash: hold.contractHash,
    railId: hold.railId,
    holdId: hold.holdId,
    amount: hold.amount,
    currency: hold.currency,
    verdict: {
      ok: decision === 'release',
      tier: 'A',
      verifier: 'testsuite',
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
    signature: `${decision}-signature`,
    ...extra,
  };
}

test('e2e release: honest seller -> verdict ok -> escrow captured', async () => {
  const rail = createMockEscrowRail();
  const contract = sortContract();
  const result = await settle({
    contract,
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });

  assert.equal(result.verdict.ok, true);
  assert.equal(result.receipt.decision, 'release');
  assert.equal(result.hold.state, 'captured');
  // Engine binds evidence to the contract.
  assert.equal(result.evidence.contractId, contract.id);
  assert.equal(result.evidence.nonce, contract.nonce);
  assert.equal(result.evidence.outputHash, sha256hex(result.evidence.output));
  // Rail status agrees with the returned hold.
  assert.equal(rail.status(result.hold.holdId).state, 'captured');
  // Receipt names the settlement authority.
  assert.equal(result.receipt.signerKeyId, keyId(settlementKey.publicKey));
  // Receipt commits to the exact contract terms, not just an opaque contract id.
  assert.equal(result.receipt.contractHash, sha256hex(result.contract));
  assert.equal(result.receipt.holdId, result.hold.holdId);
  assert.equal(result.receipt.amount, contract.price.amount);
  assert.equal(result.receipt.currency, contract.price.currency);
});

test('e2e refund: wrong output -> verdict fail -> escrow refunded (seller NOT paid)', async () => {
  const rail = createMockEscrowRail();
  const contract = sortContract();
  const result = await settle({
    contract,
    produceEvidence: () => ({ output: [9, 5, 3, 1] }), // cheating / wrong
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });

  assert.equal(result.verdict.ok, false);
  assert.equal(result.receipt.decision, 'refund');
  assert.equal(result.hold.state, 'refunded');
  assert.notEqual(result.hold.state, 'captured');
  assert.equal(rail.status(result.hold.holdId).state, 'refunded');
});

test('receipt signature verifies under the settlement public key', async () => {
  const rail = createMockEscrowRail();
  const result = await settle({
    contract: sortContract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });
  assert.equal(typeof result.receipt.signature, 'string');
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);
});

test('verifyReceipt fails when the receipt is tampered', async () => {
  const rail = createMockEscrowRail();
  const result = await settle({
    contract: sortContract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });
  const receipt = result.receipt;
  assert.equal(verifyReceipt(receipt, settlementKey.publicKey), true);

  // Tamper the decision: a release receipt forged to look like... still release,
  // but flip a verdict field that is covered by the signature.
  const tamperedDecision = { ...receipt, decision: 'refund' };
  assert.equal(verifyReceipt(tamperedDecision, settlementKey.publicKey), false);

  // Tamper the verdict body (e.g. forge ok=false -> true semantics).
  const tamperedVerdict = { ...receipt, verdict: { ...receipt.verdict, ok: false } };
  assert.equal(verifyReceipt(tamperedVerdict, settlementKey.publicKey), false);

  // Tamper the evidenceHash.
  const tamperedEvidence = { ...receipt, evidenceHash: sha256hex('forged') };
  assert.equal(verifyReceipt(tamperedEvidence, settlementKey.publicKey), false);

  // Tamper the contractHash: receipt must be tied to exact contract terms.
  const tamperedContractHash = { ...receipt, contractHash: sha256hex({ forged: true }) };
  assert.equal(verifyReceipt(tamperedContractHash, settlementKey.publicKey), false);

  // Original still verifies (tampered copies did not mutate it).
  assert.equal(verifyReceipt(receipt, settlementKey.publicKey), true);
});

test('verifyReceipt fails under a different public key', async () => {
  const rail = createMockEscrowRail();
  const result = await settle({
    contract: sortContract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });
  const stranger = generateKeypair();
  assert.equal(verifyReceipt(result.receipt, stranger.publicKey), false);
});

test('verifyReceipt fails when signerKeyId does not match the verification key', async () => {
  const rail = createMockEscrowRail();
  const result = await settle({
    contract: sortContract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });

  const forgedSigner = { ...result.receipt, signerKeyId: keyId(generateKeypair().publicKey) };
  assert.equal(verifyReceipt(forgedSigner, settlementKey.publicKey), false);
});

test('verifyReceipt rejects signed receipts whose decision contradicts verdict.ok', async () => {
  const rail = createMockEscrowRail();
  const result = await settle({
    contract: sortContract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });
  const { signature: _oldSignature, ...unsigned } = result.receipt;
  const contradictory = {
    ...unsigned,
    decision: 'release',
    verdict: { ...unsigned.verdict, ok: false, reason: 'contradictory signed fixture' },
  };
  const signature = sign(settlementKey.privateKey, canonicalize(contradictory));
  assert.equal(verifyReceipt({ ...contradictory, signature }, settlementKey.publicKey), false);
});

test('assertReceiptMeetsPolicy enforces optional production integration policy', async () => {
  const rail = createMockEscrowRail();
  const result = await settle({
    contract: sortContract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });

  assert.equal(assertReceiptMeetsPolicy(result.receipt, { expectedRailId: 'escrow-mock' }), true);
  assert.throws(
    () => assertReceiptMeetsPolicy(result.receipt, { requireRouteDecision: true }),
    /routeDecision/,
  );
  assert.throws(
    () => assertReceiptMeetsPolicy(result.receipt, { expectedVerifier: 'dataset' }),
    /expected verifier dataset/,
  );
});

test('settle rejects a mismatched settlement keypair before authorizing funds', async () => {
  const publicHalf = generateKeypair();
  const privateHalf = generateKeypair();
  let authorized = false;
  const rail = {
    id: sortContract().railId,
    authorize() {
      authorized = true;
      throw new Error('authorize should not run');
    },
    capture() {},
    refund() {},
  };

  await assert.rejects(
    settle({
      contract: sortContract(),
      produceEvidence: () => ({ output: [1, 3, 5, 9] }),
      verifier: testsuiteVerifier,
      rail,
      settlementKey: { publicKey: publicHalf.publicKey, privateKey: privateHalf.privateKey },
    }),
    /settlementKey public\/private keypair is invalid/,
  );
  assert.equal(authorized, false);
});

test('settle rejects non-canonical contract extras before authorizing funds', async () => {
  let authorized = false;
  const rail = {
    id: sortContract().railId,
    authorize() {
      authorized = true;
      throw new Error('authorize should not run');
    },
    capture() {},
    refund() {},
  };

  await assert.rejects(
    settle({
      contract: { ...sortContract(), extra: undefined },
      produceEvidence: () => ({ output: [1, 3, 5, 9] }),
      verifier: testsuiteVerifier,
      rail,
      settlementKey,
    }),
    /undefined/,
  );
  assert.equal(authorized, false);
});

test('settle rejects rail adapter mismatch before authorizing funds', async () => {
  let authorized = false;
  const rail = {
    id: 'wrong-rail',
    authorize() {
      authorized = true;
      throw new Error('authorize should not run');
    },
    capture() {},
    refund() {},
  };

  await assert.rejects(
    settle({
      contract: sortContract(),
      produceEvidence: () => ({ output: [1, 3, 5, 9] }),
      verifier: testsuiteVerifier,
      rail,
      settlementKey,
    }),
    /contract\.railId escrow-mock does not match rail adapter wrong-rail/,
  );
  assert.equal(authorized, false);
});

test('verifyReceipt returns false when signature is absent', () => {
  const unsigned = {
    contractId: 'c',
    verdict: { ok: true, tier: 'A', verifier: 'x', reason: 'r', checkedAt: 0 },
    evidenceHash: sha256hex('e'),
    decision: 'release',
    signerKeyId: keyId(settlementKey.publicKey),
    issuedAt: 0,
  };
  assert.equal(verifyReceipt(unsigned, settlementKey.publicKey), false);
});

// --- THE CRITICAL INVARIANT: verify gates settlement -------------------------

test('CRITICAL: a failing verdict NEVER yields a captured hold', async () => {
  // A rail that THROWS if capture is ever attempted. If any code path tried to
  // capture (pay the seller) on a failing verdict, this test would throw.
  function guardRail() {
    const inner = createMockEscrowRail();
    return {
      id: inner.id,
      authorize: (c) => inner.authorize(c),
      capture: () => {
        throw new Error('INVARIANT VIOLATION: capture() called on a failing verdict');
      },
      refund: (h, r) => inner.refund(h, r),
      status: (id) => inner.status(id),
    };
  }

  // Drive a guaranteed-fail through each objective verifier kind.
  const failCases = [
    {
      verifier: testsuiteVerifier,
      contract: sortContract(),
      output: [9, 5, 3, 1], // wrong sort
    },
    {
      verifier: hashVerifier,
      contract: {
        ...sortContract(),
        id: 'contract_hash_fail',
        predicate: { kind: 'hash', params: { expectedHash: sha256hex('the-right-thing') } },
      },
      output: 'the-WRONG-thing',
    },
    {
      verifier: schemaVerifier,
      contract: {
        ...sortContract(),
        id: 'contract_schema_fail',
        predicate: {
          kind: 'schema',
          params: { schema: { type: 'object', required: ['mustExist'], properties: {} } },
        },
      },
      output: { somethingElse: true }, // missing required prop
    },
  ];

  for (const fc of failCases) {
    const result = await settle({
      contract: fc.contract,
      produceEvidence: () => ({ output: fc.output }),
      verifier: fc.verifier,
      rail: guardRail(),
      settlementKey,
    });
    assert.equal(result.verdict.ok, false, `expected fail for ${fc.verifier.name}`);
    assert.equal(result.receipt.decision, 'refund', `expected refund for ${fc.verifier.name}`);
    // The hold must be refunded and must NEVER be captured.
    assert.equal(result.hold.state, 'refunded', `expected refunded for ${fc.verifier.name}`);
    assert.notEqual(result.hold.state, 'captured');
    assert.ok(
      !result.hold.history.some((h) => h.state === 'captured'),
      `hold history must contain no 'captured' entry for ${fc.verifier.name}`,
    );
  }
});

test('CRITICAL: the mock rail itself refuses to capture on a refund receipt', () => {
  // Defense in depth: even if a caller mis-routed, capture() must reject a
  // receipt whose decision is not 'release'.
  const rail = createMockEscrowRail();
  const hold = rail.authorize(sortContract());
  assert.throws(
    () => rail.capture(hold, { decision: 'refund', signature: 'x'.repeat(32) }),
    /refusing to capture/,
  );
  // Hold remains held, never captured.
  assert.equal(rail.status(hold.holdId).state, 'held');
});

test('mock rail refuses receipts that are not bound to the exact hold', () => {
  const rail = createMockEscrowRail();
  const hold = rail.authorize(sortContract());
  const release = mockRailReceiptFor(hold, 'release');

  assert.throws(
    () => rail.capture(hold, { ...release, holdId: 'other-hold' }),
    /receipt does not match hold.*holdId/,
  );
  assert.throws(
    () => rail.capture(hold, { ...release, amount: hold.amount + 1 }),
    /receipt does not match hold.*amount/,
  );
  assert.throws(
    () => rail.capture(hold, { ...release, contractHash: sha256hex({ forged: true }) }),
    /receipt does not match hold.*contractHash/,
  );
  assert.equal(rail.status(hold.holdId).state, 'held');
});

test('mock rail can require receipt signature verification on direct terminalization', () => {
  const rail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
  const hold = rail.authorize(sortContract());
  const forged = mockRailReceiptFor(hold, 'release');

  assert.throws(
    () => rail.capture(hold, forged),
    /signature failed verification/,
  );
  assert.equal(rail.status(hold.holdId).state, 'held');
});

test('CRITICAL: produceEvidence exception after authorize becomes refund, not stranded hold', async () => {
  const rail = createMockEscrowRail();
  const result = await settle({
    contract: sortContract(),
    produceEvidence: () => {
      throw new Error('seller tool crashed');
    },
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });

  assert.equal(result.verdict.ok, false);
  assert.match(result.verdict.reason, /seller tool crashed/);
  assert.equal(result.receipt.decision, 'refund');
  assert.equal(result.hold.state, 'refunded');
  assert.equal(rail.status(result.hold.holdId).state, 'refunded');
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);
});

test('CRITICAL: verifier exception after authorize becomes refund, not stranded hold', async () => {
  const rail = createMockEscrowRail();
  const explodingVerifier = {
    name: 'explode',
    tier: 'A',
    verify: () => {
      throw new Error('verifier crashed');
    },
  };
  const result = await settle({
    contract: sortContract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: explodingVerifier,
    rail,
    settlementKey,
  });

  assert.equal(result.verdict.ok, false);
  assert.match(result.verdict.reason, /verifier crashed/);
  assert.equal(result.receipt.decision, 'refund');
  assert.equal(result.hold.state, 'refunded');
  assert.equal(rail.status(result.hold.holdId).state, 'refunded');
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);
});

test('mock rail: recapture is idempotent only for the same receipt', () => {
  const rail = createMockEscrowRail();
  const hold = rail.authorize(sortContract());
  const releaseReceipt = mockRailReceiptFor(hold, 'release');
  const refundReceipt = mockRailReceiptFor(hold, 'refund');

  const captured = rail.capture(hold, releaseReceipt);
  assert.equal(captured.state, 'captured');
  assert.equal(captured.history.length, 2);

  const replayed = rail.capture(hold, releaseReceipt);
  assert.equal(replayed.state, 'captured');
  assert.equal(replayed.history.length, 2);
  assert.equal(rail.health().terminals, 1);

  assert.throws(() => rail.refund(hold, refundReceipt), /conflicting terminal settlement/);
  assert.equal(rail.capture(hold, releaseReceipt).state, 'captured');
  assert.throws(
    () => rail.capture(hold, { ...releaseReceipt, signature: 'different-signature' }),
    /conflicting terminal settlement/,
  );
  assert.throws(
    () => rail.capture(hold, { ...releaseReceipt, holdId: 'wrong-hold' }),
    /receipt does not match hold.*holdId/,
  );
  assert.throws(
    () => rail.capture(hold, refundReceipt),
    /refusing to capture/,
  );
  assert.equal(rail.status(hold.holdId).state, 'captured');

  const refundFirstRail = createMockEscrowRail();
  const refundFirstHold = refundFirstRail.authorize(sortContract());
  const refundFirstReceipt = mockRailReceiptFor(refundFirstHold, 'refund');
  const refundFirstRelease = mockRailReceiptFor(refundFirstHold, 'release');
  assert.equal(refundFirstRail.refund(refundFirstHold, refundFirstReceipt).state, 'refunded');
  assert.throws(
    () => refundFirstRail.capture(refundFirstHold, refundFirstRelease),
    /conflicting terminal settlement/,
  );
  assert.equal(refundFirstRail.status(refundFirstHold.holdId).state, 'refunded');
});

// --- dataset verifier end-to-end (deep tabular correctness gates settlement) -

/** A small, fully-determined dataset table {id, region, revenue}. */
function datasetRows(n) {
  const regions = ['us', 'eu', 'apac'];
  const rows = [];
  for (let i = 0; i < n; i++) {
    rows.push({ id: i + 1, region: regions[i % regions.length], revenue: (i % 10) + 1 });
  }
  return rows;
}

/** Dataset commitment used to derive the verifier-side sample seed. */
function datasetHashFor(rows) {
  return sha256hex(rows);
}

/** Recompute the committed sample digest (matches dataset.mjs selection). */
function datasetSampleDigest(rows, nonce, k) {
  const seed = sha256utf8(`${nonce}|${datasetHashFor(rows)}`);
  const keyed = rows.map((row, i) => ({ i, key: sha256utf8(`${seed}:${i}`) }));
  keyed.sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : a.i - b.i));
  const selected = keyed.slice(0, Math.min(k, keyed.length)).map((e) => rows[e.i]);
  return sha256hex(selected);
}

/** A dataset contract committing columns, rowCount, unique key, sample-hash, and sum(revenue). */
function datasetContract(n) {
  const rows = datasetRows(n);
  const nonce = 'nonce-dataset-1';
  const k = 4;
  const sum = rows.reduce((acc, r) => acc + r.revenue, 0);
  return {
    id: 'contract_dataset_1',
    buyer: 'buyer________',
    seller: 'seller_______',
    intent: 'deliver a cleaned customer dataset',
    deliverableType: 'application/json',
    predicate: {
      kind: 'dataset',
      params: {
        format: 'json',
        columns: [
          { name: 'id', type: 'number', required: true, nullable: false, range: { min: 1 } },
          { name: 'region', type: 'string', required: true, nullable: false, domain: ['us', 'eu', 'apac'] },
          { name: 'revenue', type: 'number', required: true, nullable: false, range: { min: 0 }, maxNullRate: 0 },
        ],
        rowCount: { min: n, max: n },
        uniqueKeys: [['id']],
        sample: { k, sampleDigest: datasetSampleDigest(rows, nonce, k) },
        aggregates: [{ column: 'revenue', op: 'sum', expected: sum }],
      },
    },
    price: { amount: 50, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce,
    createdAt: 0,
  };
}

test('e2e dataset release: correct dataset -> verdict ok -> escrow captured', async () => {
  const rail = createMockEscrowRail();
  const contract = datasetContract(30);
  const result = await settle({
    contract,
    produceEvidence: () => ({ output: datasetRows(30) }),
    verifier: datasetVerifier,
    rail,
    settlementKey,
  });

  assert.equal(result.verdict.ok, true);
  assert.equal(result.verdict.verifier, 'dataset');
  assert.equal(result.receipt.decision, 'release');
  assert.equal(result.hold.state, 'captured');
  // Receipt still binds the exact settlement terms.
  assert.equal(result.receipt.contractHash, sha256hex(result.contract));
  assert.equal(result.receipt.holdId, result.hold.holdId);
  assert.equal(result.receipt.amount, 50);
  assert.equal(result.receipt.currency, 'USDC');
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);
});

test('e2e dataset refund: schema-valid but corrupt dataset -> verdict fail -> refunded (capture never invoked)', async () => {
  const rail = createMockEscrowRail();
  const contract = datasetContract(30);
  // Deliver a dataset that is perfectly SHAPED (right columns + types + row count)
  // but whose revenue was silently corrupted: sum(revenue) is wrong and the
  // verifier-selected sample no longer matches the committed digest.
  const corrupt = datasetRows(30).map((r) => ({ ...r, revenue: r.revenue + 1 }));

  // The same corrupt deliverable passes the SHALLOW schema verifier (shape only).
  const shapeOnly = {
    predicate: {
      kind: 'schema',
      params: {
        schema: {
          type: 'array',
          items: {
            type: 'object',
            required: ['id', 'region', 'revenue'],
            properties: { id: { type: 'number' }, region: { type: 'string' }, revenue: { type: 'number' } },
          },
        },
      },
    },
  };
  assert.equal(schemaVerifier.verify(shapeOnly, { output: corrupt }).ok, true);

  const result = await settle({
    contract,
    produceEvidence: () => ({ output: corrupt }),
    verifier: datasetVerifier,
    rail,
    settlementKey,
  });

  assert.equal(result.verdict.ok, false);
  assert.equal(result.receipt.decision, 'refund');
  assert.equal(result.hold.state, 'refunded');
  assert.notEqual(result.hold.state, 'captured');
  assert.ok(
    !result.hold.history.some((h) => h.state === 'captured'),
    'a deep-fail dataset must produce no captured history entry',
  );
  assert.equal(rail.status(result.hold.holdId).state, 'refunded');
  // Receipt still binds the exact settlement terms on the refund path.
  assert.equal(result.receipt.contractHash, sha256hex(result.contract));
  assert.equal(result.receipt.holdId, result.hold.holdId);
  assert.equal(result.receipt.amount, 50);
  assert.equal(result.receipt.currency, 'USDC');
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);
});

// --- v0.2: routeDecision is bound into the signed receipt -------------------
test('routeDecision is bound into the signed receipt and is tamper-evident', async () => {
  const { routeVerifier } = await import('../src/router/policy.mjs');
  const rail = createMockEscrowRail();
  const contract = sortContract();
  const { verifier, routeDecision } = routeVerifier(contract, {
    policy: { deliverableType: 'compute', minAssurance: 3 },
  });
  assert.equal(routeDecision.selected, 'testsuite');

  const result = await settle({
    contract,
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier,
    rail,
    settlementKey,
    routeDecision,
  });

  // The decision is carried on the receipt and covered by the signature.
  assert.deepEqual(result.receipt.routeDecision, routeDecision);
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);

  // Tampering the routeDecision invalidates the signature.
  const tampered = {
    ...result.receipt,
    routeDecision: { ...routeDecision, selected: 'schema' },
  };
  assert.equal(verifyReceipt(tampered, settlementKey.publicKey), false);
});

test('settle rejects a routeDecision that does not match the injected verifier', async () => {
  const { routeDecision } = await import('../src/router/policy.mjs').then(({ routeVerifier }) =>
    routeVerifier(sortContract(), { policy: { deliverableType: 'compute', minAssurance: 3 } }),
  );
  let authorized = false;
  const rail = {
    id: sortContract().railId,
    authorize() {
      authorized = true;
      throw new Error('authorize should not run');
    },
    capture() {},
    refund() {},
  };

  await assert.rejects(
    settle({
      contract: sortContract(),
      produceEvidence: () => ({ output: [1, 3, 5, 9] }),
      verifier: schemaVerifier,
      rail,
      settlementKey,
      routeDecision,
    }),
    /routeDecision selected testsuite but verifier is schema/,
  );
  assert.equal(authorized, false);
});

test('receipt.routeDecision defaults to null and still verifies when no router is used', async () => {
  const rail = createMockEscrowRail();
  const result = await settle({
    contract: sortContract(),
    produceEvidence: () => ({ output: [1, 3, 5, 9] }),
    verifier: testsuiteVerifier,
    rail,
    settlementKey,
  });
  assert.equal(result.receipt.routeDecision, null);
  assert.equal(verifyReceipt(result.receipt, settlementKey.publicKey), true);
});

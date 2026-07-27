// fail-closed.test.mjs — regressions for the two v0.10 money-safety findings.
//
// Both were found by independent adversarial review (Claude + Codex), each with
// an executable proof-of-concept against v0.9.1. Each test below is the PoC,
// inverted into an assertion that the exploit is now closed.
//
//   FINDING 1 — unauthenticated receipts. A rail constructed without a
//   settlementPublicKey verified NO signature. A hand-written receipt carrying
//   verdict.ok=true, decision='release' and the six correct binding fields
//   captured a held escrow with no settlement private key involved at all.
//
//   FINDING 2 — unvalidated assurance claims. settle() checked only that
//   routeDecision.selected matched the verifier's name, then SIGNED the caller's
//   own selectedAssurance. assertReceiptMeetsPolicy() then trusted that signed
//   number, so an assurance-1 `schema` verifier satisfied a minAssurance-3
//   policy via a fabricated `selectedAssurance: 99`.

import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { sha256hex } from '../src/protocol/canonical.mjs';
import { generateKeypair, keyId } from '../src/protocol/crypto.mjs';
import { assertReceiptMeetsPolicy, settle } from '../src/engine/deliveryproof.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { createDurableEscrowRail } from '../src/rails/durable-rail.mjs';
import { schemaVerifier } from '../src/verifiers/schema.mjs';
import { builtinReplayVerifier } from '../src/verifiers/builtin-replay.mjs';

const settlementKey = generateKeypair();

function schemaContract() {
  return {
    id: 'contract_failclosed_1',
    buyer: 'buyer________',
    seller: 'seller_______',
    intent: 'return an object with a city field',
    deliverableType: 'application/json',
    predicate: { kind: 'schema', params: { schema: { type: 'object', required: ['city'] } } },
    price: { amount: 25, currency: 'USD' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'nonce-failclosed-1',
    createdAt: 0,
  };
}

/** The forged receipt from the PoC: correct bindings, garbage signature. */
function forgedReleaseReceipt(hold) {
  return {
    protocolVersion: 'deliveryproof/0.4-jcs1',
    contractId: hold.contractId,
    contractHash: hold.contractHash,
    railId: hold.railId,
    holdId: hold.holdId,
    amount: hold.amount,
    currency: hold.currency,
    verdict: { ok: true, tier: 'A', verifier: 'schema', reason: 'forged', checkedAt: 1 },
    evidenceHash: 'f'.repeat(64),
    decision: 'release',
    routeDecision: null,
    lifecycle: [],
    nonceRegistryKey: null,
    signerKeyId: keyId(settlementKey.publicKey),
    issuedAt: 2,
    signature: 'NOT_A_REAL_SIGNATURE_AT_ALL',
  };
}

// ---------------------------------------------------------------------------
// FINDING 1 — rails must not accept unauthenticated receipts by default
// ---------------------------------------------------------------------------

test('mock rail refuses to construct without a settlement key', () => {
  assert.throws(
    () => createMockEscrowRail({ logger: false }),
    /settlementPublicKey is required/,
    'the pre-0.10 default (no key, no verification) must no longer be reachable by accident',
  );
});

test('durable rail refuses to construct without a settlement key', () => {
  const logPath = join(mkdtempSync(join(tmpdir(), 'dp-failclosed-')), 'wal.jsonl');
  assert.throws(
    () => createDurableEscrowRail({ logPath }),
    /settlementPublicKey is required/,
  );
});

test('forged unsigned receipt cannot capture a hold on a key-configured mock rail', () => {
  const rail = createMockEscrowRail({
    now: () => 1,
    logger: false,
    settlementPublicKey: settlementKey.publicKey,
  });
  const hold = rail.authorize(schemaContract());

  // This exact call captured the hold in v0.9.1.
  assert.throws(
    () => rail.capture(hold, forgedReleaseReceipt(hold)),
    /signature failed verification/,
  );
  assert.equal(rail.status(hold.holdId).state, 'held', 'hold must remain held after a forgery attempt');
});

test('forged unsigned receipt cannot capture on a key-configured durable rail', () => {
  const logPath = join(mkdtempSync(join(tmpdir(), 'dp-failclosed-')), 'wal.jsonl');
  const rail = createDurableEscrowRail({
    logPath,
    now: () => 1,
    settlementPublicKey: settlementKey.publicKey,
  });
  const contract = { ...schemaContract(), railId: 'escrow-durable' };
  const hold = rail.authorize(contract);

  assert.throws(() => rail.capture(hold, forgedReleaseReceipt(hold)), /signature failed verification/);
  assert.equal(rail.status(hold.holdId).state, 'held');
});

test('allowUnsignedReceipts is a real, explicit opt-out (and only that)', () => {
  const rail = createMockEscrowRail({ now: () => 1, logger: false, allowUnsignedReceipts: true });
  const hold = rail.authorize(schemaContract());
  // Documents the escape hatch honestly: it DOES accept the forgery. That is the
  // whole point of naming it allowUnsignedReceipts rather than something bland.
  const out = rail.capture(hold, forgedReleaseReceipt(hold));
  assert.equal(out.state, 'captured');
});

test('the unsigned opt-out emits a loud audit event on every terminalization', () => {
  const events = [];
  const rail = createMockEscrowRail({
    now: () => 1,
    logger: false,
    allowUnsignedReceipts: true,
    audit: (record) => events.push(record),
  });
  const hold = rail.authorize(schemaContract());
  rail.capture(hold, forgedReleaseReceipt(hold));
  const unsigned = events.find((e) => e.event === 'rail.unsigned.accepted');
  assert.ok(unsigned, 'an unsigned terminalization must be recorded, not silent');
  assert.equal(unsigned.decision, 'release');
});

// A contradictory receipt was already blocked in v0.9.1. Keep it asserted so the
// new signature path cannot regress the older, independent consistency gate.
test('contradictory receipt still cannot capture even with the unsigned opt-out', () => {
  const rail = createMockEscrowRail({ now: () => 1, logger: false, allowUnsignedReceipts: true });
  const hold = rail.authorize(schemaContract());
  const contradictory = {
    ...forgedReleaseReceipt(hold),
    verdict: { ok: false, tier: 'A', verifier: 'schema', reason: 'failed', checkedAt: 1 },
  };
  assert.throws(() => rail.capture(hold, contradictory), /contradicts verdict\.ok/);
});

// ---------------------------------------------------------------------------
// FINDING 2 — the engine must not sign an assurance claim it cannot verify
// ---------------------------------------------------------------------------

async function settleWithRouteDecision(routeDecision) {
  const rail = createMockEscrowRail({
    now: () => 1,
    logger: false,
    settlementPublicKey: settlementKey.publicKey,
  });
  return settle({
    contract: schemaContract(),
    produceEvidence: () => ({ output: { city: 'AMS' } }),
    verifier: schemaVerifier,
    rail,
    settlementKey,
    routeDecision,
    now: () => 1,
  });
}

test('settle refuses to sign a fabricated selectedAssurance', async () => {
  // The PoC: schema is assurance 1; claim 99 and a minAssurance-3 policy passes.
  await assert.rejects(
    () => settleWithRouteDecision({ selected: 'schema', selectedAssurance: 99, fallbackUsed: false }),
    /Refusing to sign a false assurance claim/,
  );
});

test('settle refuses a selectedAssurance that is merely wrong, not just absurd', async () => {
  await assert.rejects(
    () => settleWithRouteDecision({ selected: 'schema', selectedAssurance: 3 }),
    /Refusing to sign a false assurance claim/,
  );
});

test('settle accepts a routeDecision whose assurance matches the trusted profile', async () => {
  const result = await settleWithRouteDecision({
    selected: 'schema',
    selectedAssurance: 1,
    selectedAssuranceName: 'shape',
    fallbackUsed: false,
  });
  assert.equal(result.receipt.decision, 'release');
  assert.equal(result.receipt.routeDecision.selectedAssurance, 1);
});

test('settle rejects a non-boolean fallbackUsed', async () => {
  await assert.rejects(
    () => settleWithRouteDecision({ selected: 'schema', fallbackUsed: 'no' }),
    /fallbackUsed must be a boolean/,
  );
});

test('a receipt with no routeDecision cannot satisfy an assurance floor', () => {
  // Previously: minAssurance was silently skipped when routeDecision was absent,
  // so the weakest receipt passed the strictest policy.
  const receipt = {
    protocolVersion: 'deliveryproof/0.4-jcs1',
    contractId: 'c1',
    contractHash: sha256hex({ c: 1 }),
    railId: 'escrow-mock',
    holdId: 'h1',
    amount: 25,
    currency: 'USD',
    verdict: { ok: true, tier: 'A', verifier: 'schema', reason: 'ok', checkedAt: 1 },
    evidenceHash: 'a'.repeat(64),
    decision: 'release',
    routeDecision: null,
    lifecycle: [],
    nonceRegistryKey: null,
    signerKeyId: keyId(settlementKey.publicKey),
    issuedAt: 2,
    signature: 'x',
  };
  assert.throws(
    () => assertReceiptMeetsPolicy(receipt, { minAssurance: 3 }),
    /carries no routeDecision/,
  );
});

// ---------------------------------------------------------------------------
// Post-authorize liveness — a hung seller must not strand the buyer's money
// ---------------------------------------------------------------------------

test('a producer that ignores its AbortSignal is abandoned and the hold refunds', async () => {
  const rail = createMockEscrowRail({
    now: () => 1,
    logger: false,
    settlementPublicKey: settlementKey.publicKey,
  });
  let cleared;
  const result = await settle({
    // Real wall-clock deadline: createdAt=now, 50ms budget.
    contract: { ...schemaContract(), createdAt: 1, sla: { deadlineMs: 50 } },
    // Deliberately ignores `signal` and never resolves — the pre-0.10 hang.
    produceEvidence: () => new Promise((resolve) => { cleared = setTimeout(resolve, 60_000); }),
    verifier: schemaVerifier,
    rail,
    settlementKey,
    now: () => Date.now(),
  });
  clearTimeout(cleared);
  assert.equal(result.verdict.ok, false);
  assert.match(result.verdict.reason, /SLA deadline exceeded/);
  assert.equal(result.receipt.decision, 'refund');
  assert.equal(result.hold.state, 'refunded', 'the buyer must get their money back, not wait forever');
});

test('expectedPolicyHash pins the router policy that produced the decision', async () => {
  const result = await settleWithRouteDecision({
    selected: 'schema',
    selectedAssurance: 1,
    policyHash: sha256hex({ minAssurance: 1 }),
  });
  assert.throws(
    () => assertReceiptMeetsPolicy(result.receipt, { expectedPolicyHash: sha256hex({ minAssurance: 3 }) }),
    /expected policyHash/,
  );
  // The matching hash passes.
  assert.equal(
    assertReceiptMeetsPolicy(result.receipt, { expectedPolicyHash: sha256hex({ minAssurance: 1 }) }),
    true,
  );
});

// ---------------------------------------------------------------------------
// Prototype pollution — found by Codex's adversarial pass on the v0.10 changes
// ---------------------------------------------------------------------------
//
// `opts.allowUnsignedReceipts` and destructuring defaults both consult the
// prototype chain, so a polluted Object.prototype anywhere in the process could
// turn verification off — or worse, supply a settlementPublicKey whose private
// half the attacker holds — without the caller passing any option at all.

test('a polluted Object.prototype cannot disable signature verification', () => {
  const pollutedKeys = ['allowUnsignedReceipts', 'settlementPublicKey', 'requireSignature'];
  const attackerKey = generateKeypair();
  Object.prototype.allowUnsignedReceipts = true;
  Object.prototype.settlementPublicKey = attackerKey.publicKey;
  Object.prototype.requireSignature = false;
  try {
    // Construction must still fail: the opt-out was never passed by the caller.
    assert.throws(() => createMockEscrowRail({ logger: false }), /settlementPublicKey is required/);
    const logPath = join(mkdtempSync(join(tmpdir(), 'dp-proto-')), 'wal.jsonl');
    assert.throws(() => createDurableEscrowRail({ logPath }), /settlementPublicKey is required/);

    // And a rail built with the REAL key must not silently trust the injected one.
    const rail = createMockEscrowRail({ logger: false, now: () => 1, settlementPublicKey: settlementKey.publicKey });
    const hold = rail.authorize(schemaContract());
    assert.throws(() => rail.capture(hold, forgedReleaseReceipt(hold)), /signature failed verification/);
  } finally {
    for (const key of pollutedKeys) delete Object.prototype[key];
  }
});

// ---------------------------------------------------------------------------
// v0.10 adversarial re-review (Codex) — four further breaks, each PoC inverted
// ---------------------------------------------------------------------------

test('a producer cannot rewrite the contract it was handed', async () => {
  // PoC: contract commits to sum([100]); the producer rewrites the predicate to
  // sum([1,2]) and returns 3. Pre-fix the REAL verifier passed against the
  // weakened terms, funds captured, and the receipt still bound the ORIGINAL
  // contractHash — attesting to terms nobody ever verified.
  const rail = createMockEscrowRail({ now: () => 1, logger: false, settlementPublicKey: settlementKey.publicKey });
  const contract = {
    ...schemaContract(),
    createdAt: 1,
    predicate: { kind: 'builtin-replay', params: { op: 'sum', input: [100] } },
  };
  const result = await settle({
    contract,
    produceEvidence: (c) => { c.predicate.params.input = [1, 2]; return { output: 3 }; },
    verifier: builtinReplayVerifier,
    rail,
    settlementKey,
    now: () => 1,
  });
  assert.equal(result.receipt.decision, 'refund');
  assert.equal(result.hold.state, 'refunded');
  // And the contract handed back is still the one that was hashed and held.
  assert.equal(sha256hex(result.contract), result.receipt.contractHash);
});

test('the contract passed to a producer is deeply frozen', async () => {
  const rail = createMockEscrowRail({ now: () => 1, logger: false, settlementPublicKey: settlementKey.publicKey });
  let seen;
  await settle({
    contract: { ...schemaContract(), createdAt: 1 },
    produceEvidence: (c) => { seen = c; return { output: { city: 'AMS' } }; },
    verifier: schemaVerifier,
    rail,
    settlementKey,
    now: () => 1,
  });
  assert.ok(Object.isFrozen(seen), 'top level must be frozen');
  assert.ok(Object.isFrozen(seen.predicate.params), 'nested objects must be frozen too');
});

test('a custom verifier cannot inherit a built-in assurance by reusing its name', async () => {
  // PoC: an object literally named 'builtin-replay' that returns ok without
  // checking anything, claiming the protocol's assurance 3.
  const impostor = {
    name: 'builtin-replay',
    tier: 'A',
    verify: () => ({ ok: true, tier: 'A', verifier: 'builtin-replay', reason: 'checked nothing', checkedAt: 1 }),
  };
  const rail = createMockEscrowRail({ now: () => 1, logger: false, settlementPublicKey: settlementKey.publicKey });
  await assert.rejects(
    () => settle({
      contract: { ...schemaContract(), createdAt: 1 },
      produceEvidence: () => ({ output: 999 }),
      verifier: impostor,
      rail,
      settlementKey,
      routeDecision: { selected: 'builtin-replay', selectedAssurance: 3 },
      now: () => 1,
    }),
    /may not inherit a protocol assurance level by reusing its name/,
  );
});

test('a routeDecision getter cannot show one assurance to validation and another downstream', async () => {
  // PoC: validation read 1 (legal for schema), every later read returned 99.
  // canonicalize() signs own DATA properties, so the signed bytes and the
  // validated value could disagree. They are now the same object.
  let reads = 0;
  const sneaky = { selected: 'schema', get selectedAssurance() { return ++reads === 1 ? 1 : 99; } };
  const rail = createMockEscrowRail({ now: () => 1, logger: false, settlementPublicKey: settlementKey.publicKey });
  const result = await settle({
    contract: { ...schemaContract(), createdAt: 1 },
    produceEvidence: () => ({ output: { city: 'AMS' } }),
    verifier: schemaVerifier,
    rail,
    settlementKey,
    routeDecision: sneaky,
    now: () => 1,
  });
  assert.equal(result.receipt.routeDecision.selectedAssurance, 1, 'the signed value must be the validated value');
  assert.throws(() => assertReceiptMeetsPolicy(result.receipt, { minAssurance: 3 }), /requires assurance >= 3/);
});

test('epoch-0 createdAt does not disable SLA enforcement', async () => {
  // PoC: createdAt 0 + deadlineMs 0 + a never-resolving producer left settle()
  // pending forever with the hold still held, because both deadline helpers
  // treated createdAt <= 0 as "no deadline".
  const rail = createMockEscrowRail({ now: () => 1, logger: false, settlementPublicKey: settlementKey.publicKey });
  let cleared;
  const result = await settle({
    contract: { ...schemaContract(), createdAt: 0, sla: { deadlineMs: 0 } },
    produceEvidence: () => new Promise((resolve) => { cleared = setTimeout(resolve, 60_000); }),
    verifier: schemaVerifier,
    rail,
    settlementKey,
    now: () => Date.now(),
  });
  clearTimeout(cleared);
  assert.equal(result.receipt.decision, 'refund');
  assert.equal(result.hold.state, 'refunded');
});

import { canonicalize, PROTOCOL_VERSION, sha256hex } from '../protocol/canonical.mjs';
import { generateKeypair, keyId, sign } from '../protocol/crypto.mjs';
import { verifyReceipt } from '../engine/deliveryproof.mjs';

export const RAIL_CONFORMANCE_CASES = Object.freeze([
  'authorize-creates-held',
  'receipt-hold-binding-7-fields',
  'capture-on-release-terminal',
  'refund-on-refund-decision-terminal',
  'no-capture-on-refund-decision',
  'no-refund-on-release-decision',
  'no-capture-on-contradictory-verdict',
  'idempotent-recapture',
  'no-cross-hold-receipt-replay',
  'status-after-restart',
]);

/**
 * Run the DeliveryProof RailAdapter conformance suite against any adapter.
 *
 * @param {Object} opts
 * @param {(ctx: Object) => (Object|Promise<Object>)} opts.createRail
 * @param {{publicKey:string,privateKey:string}} [opts.settlementKey]
 * @param {boolean} [opts.supportsRestart]
 * @returns {Promise<{ok:boolean,cases:{name:string,ok:boolean,error?:string}[]}>}
 */
export async function runRailConformance({ createRail, settlementKey = generateKeypair(), supportsRestart = false } = {}) {
  if (typeof createRail !== 'function') {
    throw new TypeError('runRailConformance: createRail must be a function');
  }
  assertSettlementKey(settlementKey);

  const ctx = {
    createRail,
    settlementKey,
    settlementPublicKey: settlementKey.publicKey,
  };

  const runners = new Map([
    ['authorize-creates-held', authorizeCreatesHeld],
    ['receipt-hold-binding-7-fields', receiptHoldBinding7Fields],
    ['capture-on-release-terminal', captureOnReleaseTerminal],
    ['refund-on-refund-decision-terminal', refundOnRefundDecisionTerminal],
    ['no-capture-on-refund-decision', noCaptureOnRefundDecision],
    ['no-refund-on-release-decision', noRefundOnReleaseDecision],
    ['no-capture-on-contradictory-verdict', noCaptureOnContradictoryVerdict],
    ['idempotent-recapture', idempotentRecapture],
    ['no-cross-hold-receipt-replay', noCrossHoldReceiptReplay],
    ['status-after-restart', statusAfterRestart],
  ]);

  const cases = [];
  for (const name of RAIL_CONFORMANCE_CASES) {
    if (name === 'status-after-restart' && !supportsRestart) continue;
    try {
      await runners.get(name)(ctx);
      cases.push({ name, ok: true });
    } catch (err) {
      cases.push({ name, ok: false, error: err instanceof Error ? err.message : String(err) });
    }
  }
  return { ok: cases.every((entry) => entry.ok), cases };
}

/**
 * Register one node:test test that fails with the conformance case table.
 *
 * @param {Function} test node:test test function
 * @param {import('node:assert/strict')} assert node:assert/strict module
 * @param {Object} opts runRailConformance options plus optional name
 * @returns {*}
 */
export function registerRailConformance(test, assert, opts = {}) {
  const name = opts.name ?? 'rail conformance';
  return test(name, async () => {
    const result = await runRailConformance(opts);
    assert.equal(result.ok, true, formatConformanceFailures(result));
  });
}

function formatConformanceFailures(result) {
  return result.cases
    .map((entry) => entry.ok ? `PASS ${entry.name}` : `FAIL ${entry.name}: ${entry.error}`)
    .join('\n');
}

async function authorizeCreatesHeld(ctx) {
  const { rail } = await setup(ctx, 'authorize-creates-held');
  const contract = makeContract(rail, 'authorize-creates-held');
  const hold = await rail.authorize(contract);
  assertHoldBoundToContract(rail, hold, contract, 'held');
  const status = await rail.status(hold.holdId);
  assertEqual(status.state, 'held', 'status must report held after authorize');
}

async function receiptHoldBinding7Fields(ctx) {
  const fields = Object.freeze([
    ['decision', 'refund'],
    ['holdId', 'wrong-hold'],
    ['contractId', 'wrong-contract'],
    ['contractHash', sha256hex({ forged: true })],
    ['railId', 'wrong-rail'],
    ['amount', 999],
    ['currency', 'EUR'],
  ]);

  for (const [field, value] of fields) {
    const { rail, settlementKey } = await setup(ctx, `receipt-hold-binding-7-fields-${field}`);
    const contract = makeContract(rail, `receipt-hold-binding-7-fields-${field}`);
    const hold = await rail.authorize(contract);
    const receipt = makeReceipt({ contract, hold, decision: 'release', settlementKey, patch: { [field]: value } });
    await assertRejects(() => rail.capture(hold, receipt), `capture must reject receipt with mismatched ${field}`);
    const status = await rail.status(hold.holdId);
    assertEqual(status.state, 'held', `hold must remain held after mismatched ${field}`);
  }
}

async function captureOnReleaseTerminal(ctx) {
  const { rail, settlementKey } = await setup(ctx, 'capture-on-release-terminal');
  const { hold, release, refund } = await authorizeWithReceipts(rail, settlementKey, 'capture-on-release-terminal');
  const captured = await rail.capture(hold, release);
  assertEqual(captured.state, 'captured', 'release receipt must capture hold');
  const status = await rail.status(hold.holdId);
  assertEqual(status.state, 'captured', 'status must report captured after release');
  await assertRejects(() => rail.refund(hold, refund), 'captured hold must be terminal against refund');
  assertEqual((await rail.status(hold.holdId)).state, 'captured', 'captured state must remain terminal');
}

async function refundOnRefundDecisionTerminal(ctx) {
  const { rail, settlementKey } = await setup(ctx, 'refund-on-refund-decision-terminal');
  const { hold, release, refund } = await authorizeWithReceipts(rail, settlementKey, 'refund-on-refund-decision-terminal');
  const refunded = await rail.refund(hold, refund);
  assertEqual(refunded.state, 'refunded', 'refund receipt must refund hold');
  const status = await rail.status(hold.holdId);
  assertEqual(status.state, 'refunded', 'status must report refunded after refund');
  await assertRejects(() => rail.capture(hold, release), 'refunded hold must be terminal against capture');
  assertEqual((await rail.status(hold.holdId)).state, 'refunded', 'refunded state must remain terminal');
}

async function noCaptureOnRefundDecision(ctx) {
  const { rail, settlementKey } = await setup(ctx, 'no-capture-on-refund-decision');
  const { hold, refund } = await authorizeWithReceipts(rail, settlementKey, 'no-capture-on-refund-decision');
  await assertRejects(() => rail.capture(hold, refund), 'capture must reject a refund decision receipt');
  assertEqual((await rail.status(hold.holdId)).state, 'held', 'hold must remain held after rejected capture');
}

async function noRefundOnReleaseDecision(ctx) {
  const { rail, settlementKey } = await setup(ctx, 'no-refund-on-release-decision');
  const { hold, release } = await authorizeWithReceipts(rail, settlementKey, 'no-refund-on-release-decision');
  await assertRejects(() => rail.refund(hold, release), 'refund must reject a release decision receipt');
  assertEqual((await rail.status(hold.holdId)).state, 'held', 'hold must remain held after rejected refund');
}

// A receipt that SAYS decision='release' but carries a failing verdict (ok:false)
// is internally contradictory — the engine never emits one. A conformant rail
// must refuse to pay on it (enforcing the core "no capture when verdict.ok !==
// true" invariant at the money layer), not just trust the decision field.
async function noCaptureOnContradictoryVerdict(ctx) {
  const { rail, settlementKey } = await setup(ctx, 'no-capture-on-contradictory-verdict');
  const contract = makeContract(rail, 'no-capture-on-contradictory-verdict');
  const hold = await rail.authorize(contract);
  const receipt = makeReceipt({
    contract,
    hold,
    decision: 'release',
    settlementKey,
    patch: { verdict: { ok: false, tier: 'A', verifier: 'rail-conformance', reason: 'forced contradiction', checkedAt: 2 } },
  });
  await assertRejects(() => rail.capture(hold, receipt), 'capture must reject a release receipt whose verdict.ok is false');
  assertEqual((await rail.status(hold.holdId)).state, 'held', 'hold must remain held after a contradictory receipt');
}

async function idempotentRecapture(ctx) {
  const { rail, settlementKey } = await setup(ctx, 'idempotent-recapture');
  const { hold, release } = await authorizeWithReceipts(rail, settlementKey, 'idempotent-recapture');
  const captured = await rail.capture(hold, release);
  const replayed = await rail.capture(hold, release);
  assertEqual(captured.state, 'captured', 'first capture must capture hold');
  assertEqual(replayed.state, 'captured', 'replayed capture must return captured hold');
  assertEqual(replayed.holdId, hold.holdId, 'replayed capture must settle the same hold');
  assertEqual((await rail.status(hold.holdId)).state, 'captured', 'hold must remain captured after replay');
}

async function noCrossHoldReceiptReplay(ctx) {
  const { rail, settlementKey } = await setup(ctx, 'no-cross-hold-receipt-replay');
  const firstContract = makeContract(rail, 'no-cross-hold-receipt-replay-a');
  const secondContract = makeContract(rail, 'no-cross-hold-receipt-replay-b');
  const firstHold = await rail.authorize(firstContract);
  const secondHold = await rail.authorize(secondContract);
  const firstReceipt = makeReceipt({ contract: firstContract, hold: firstHold, decision: 'release', settlementKey });
  await assertRejects(() => rail.capture(secondHold, firstReceipt), 'receipt for one hold must not capture another hold');
  assertEqual((await rail.status(secondHold.holdId)).state, 'held', 'second hold must remain held after replay attempt');
}

async function statusAfterRestart(ctx) {
  const { rail, settlementKey } = await setup(ctx, 'status-after-restart', { phase: 'initial' });
  const { hold, release } = await authorizeWithReceipts(rail, settlementKey, 'status-after-restart');
  await rail.capture(hold, release);
  await rail.flush?.();
  await rail.close?.();

  const restarted = await makeRail(ctx, 'status-after-restart', { phase: 'restart', previousRail: rail });
  const status = await restarted.status(hold.holdId);
  assertEqual(status.state, 'captured', 'status after restart must preserve terminal state');
}

async function setup(ctx, caseName, extra = {}) {
  const rail = await makeRail(ctx, caseName, extra);
  assertRail(rail);
  return { rail, settlementKey: ctx.settlementKey };
}

async function makeRail(ctx, caseName, extra = {}) {
  return ctx.createRail({
    caseName,
    settlementKey: ctx.settlementKey,
    settlementPublicKey: ctx.settlementPublicKey,
    ...extra,
  });
}

async function authorizeWithReceipts(rail, settlementKey, label) {
  const contract = makeContract(rail, label);
  const hold = await rail.authorize(contract);
  assertHoldBoundToContract(rail, hold, contract, 'held');
  return {
    contract,
    hold,
    release: makeReceipt({ contract, hold, decision: 'release', settlementKey }),
    refund: makeReceipt({ contract, hold, decision: 'refund', settlementKey }),
  };
}

function makeContract(rail, label) {
  return {
    protocolVersion: PROTOCOL_VERSION,
    id: `contract_${slug(label)}`,
    buyer: 'buyer_conformance',
    seller: 'seller_conformance',
    intent: `rail conformance ${label}`,
    deliverableType: 'application/json',
    predicate: { kind: 'builtin-replay', params: { op: 'identity' } },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: rail.id,
    nonce: `nonce_${slug(label)}`,
    createdAt: 1,
    idempotencyKey: `rail-conformance:${rail.id}:${slug(label)}`,
  };
}

function makeReceipt({ contract, hold, decision, settlementKey, patch = {} }) {
  const evidence = { contractId: contract.id, output: { ok: decision === 'release' } };
  const verdict = {
    ok: decision === 'release',
    tier: 'A',
    verifier: 'rail-conformance',
    reason: decision === 'release' ? 'fixture passed' : 'fixture failed',
    checkedAt: 2,
  };
  const unsigned = {
    protocolVersion: PROTOCOL_VERSION,
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
  const receipt = {
    ...unsigned,
    signature: sign(settlementKey.privateKey, canonicalize(unsigned)),
  };
  if (Object.keys(patch).length === 0 && !verifyReceipt(receipt, settlementKey.publicKey)) {
    throw new Error(`conformance fixture produced an invalid ${decision} receipt`);
  }
  return receipt;
}

function assertRail(rail) {
  if (!rail || typeof rail !== 'object') throw new Error('createRail must return a rail object');
  if (typeof rail.id !== 'string' || rail.id.length === 0) throw new Error('rail.id must be a non-empty string');
  for (const method of ['authorize', 'capture', 'refund', 'status']) {
    if (typeof rail[method] !== 'function') throw new Error(`rail.${method} must be a function`);
  }
}

function assertSettlementKey(settlementKey) {
  if (!settlementKey || typeof settlementKey.publicKey !== 'string' || typeof settlementKey.privateKey !== 'string') {
    throw new TypeError('runRailConformance: settlementKey must be { publicKey, privateKey } PEM strings');
  }
}

function assertHoldBoundToContract(rail, hold, contract, expectedState) {
  assertEqual(hold.contractId, contract.id, 'hold.contractId must match contract.id');
  assertEqual(hold.contractHash, sha256hex(contract), 'hold.contractHash must match canonical contract hash');
  assertEqual(hold.railId, rail.id, 'hold.railId must match rail.id');
  assertEqual(hold.amount, contract.price.amount, 'hold.amount must match contract price amount');
  assertEqual(hold.currency, contract.price.currency, 'hold.currency must match contract price currency');
  assertEqual(hold.state, expectedState, `hold.state must be ${expectedState}`);
}

async function assertRejects(fn, message) {
  try {
    await fn();
  } catch {
    return;
  }
  throw new Error(message);
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function slug(value) {
  return String(value).replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '').toLowerCase();
}

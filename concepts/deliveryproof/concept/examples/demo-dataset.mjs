// examples/demo-dataset.mjs
//
// DeliveryProof — the DATASET money shot (Node v22+).
//
//   Run:  node examples/demo-dataset.mjs
//
// THE POINT (one screen):
//   An agent pays 50 USDC for a "cleaned customer dataset." The signed contract
//   commits exactly what "delivered" means: the columns and their types, the row
//   count, a verifier-seeded SAMPLE HASH, a UNIQUE KEY, and an AGGREGATE
//   INVARIANT sum(revenue).
//
//   The seller delivers a dataset that is perfectly SHAPED — right columns, right
//   primitive types, right row count — but whose `revenue` values were silently
//   corrupted. That deliverable PASSES a shallow check (HTTP 2xx + JSON-schema
//   shape — exactly what shipped escrow products like PayCrow and x402+escrow
//   leave to the developer), so on that path the funds RELEASE and the cheater
//   is paid.
//
//   The SAME deliverable then runs through DeliveryProof's DEEP dataset verifier
//   (Tier A, objective): the router selects the deep dataset verifier, which
//   catches a duplicate unique key and would also catch the changed aggregate /
//   sample digest -> verdict ok=false -> settle() REFUNDS. capture() is never
//   called.
//
//   Unlike the array-sort money shot in demo-compute.mjs (Scenario 4), this is a
//   realistic, multi-dimensional, high-value dataset and exercises a genuinely
//   NEW verifier kind ('dataset') — gating settlement on objective DATASET
//   correctness, which no shipped rail does.
//
// Honest framing: this composes with payment rails, it does not replace them.
// The rail still answers "allowed to pay?"; DeliveryProof answers "did the
// counterparty deliver a CORRECT dataset?" and gates capture/refund on the answer.

import { generateKeypair, keyId } from '../src/protocol/crypto.mjs';
import { canonicalize, sha256hex, sha256utf8 } from '../src/protocol/canonical.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { settle, verifyReceipt } from '../src/engine/deliveryproof.mjs';
import { routeVerifier } from '../src/router/policy.mjs';

// --- pretty-printing helpers (no deps; same style as demo-compute.mjs) -------

const LINE = '─'.repeat(74);
const HEAVY = '═'.repeat(74);

function banner(title) {
  console.log('\n' + HEAVY);
  console.log('  ' + title);
  console.log(HEAVY);
}

function section(title) {
  console.log('\n' + LINE);
  console.log('  ' + title);
  console.log(LINE);
}

function kv(label, value) {
  console.log('  ' + String(label).padEnd(22) + ': ' + value);
}

function yn(b) {
  return b ? 'YES' : 'NO';
}

// --- the deliverable: a "cleaned customer dataset" ---------------------------

const ROW_COUNT = 1000;
const SAMPLE_K = 12;
const CONTRACT_NONCE = 'nonce-dataset-demo';

/**
 * Build the canonical, correct dataset the buyer expects. Every value is fully
 * determined so the demo is deterministic: revenue is a fixed function of the row
 * index, and the buyer can therefore commit an exact sum and sample-hash.
 * @returns {Array<{id:number, region:string, revenue:number, churned:boolean}>}
 */
function buildCleanDataset() {
  const regions = ['us', 'eu', 'apac', 'latam'];
  const rows = [];
  for (let i = 0; i < ROW_COUNT; i++) {
    rows.push({
      id: i + 1,
      region: regions[i % regions.length],
      revenue: 100 + (i % 50), // 100..149, deterministic
      churned: i % 7 === 0,
    });
  }
  return rows;
}

/** Dataset commitment used to derive the verifier-side sample seed. */
function datasetHashFor(rows) {
  return sha256hex(rows);
}

/** Deterministic verifier-seeded sample digest — identical logic to dataset.mjs. */
function sampleDigestFor(rows, nonce, k) {
  const seed = sha256utf8(`${nonce}|${datasetHashFor(rows)}`);
  const keyed = rows.map((row, i) => ({ i, key: sha256utf8(`${seed}:${i}`) }));
  keyed.sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : a.i - b.i));
  const selected = keyed.slice(0, Math.min(k, keyed.length)).map((e) => rows[e.i]);
  return sha256hex(selected);
}

/** Sum a numeric column. */
function sumColumn(rows, column) {
  return rows.reduce((acc, r) => acc + r[column], 0);
}

// --- parties -----------------------------------------------------------------

banner('DeliveryProof — DATASET money shot: shallow PAYS, deep REFUNDS');

console.log(`
  An agent buys a "cleaned customer dataset" for 50 USDC. The contract commits
  what DELIVERED means: columns + types, exactly ${ROW_COUNT} rows, a unique id,
  a verifier-seeded sample hash, and the invariant sum(revenue) == <committed>.

  The seller ships a dataset with the RIGHT SHAPE but a duplicated customer id
  and silently CORRUPTED revenue. Watch a low-risk policy route to a shallow
  shape-check and pay the cheater, then watch a high-risk policy route to the
  deep dataset verifier on the SAME bytes and refund.
`);

const buyer = generateKeypair();
const sellerCheating = generateKeypair();
const settlementKey = generateKeypair();

kv('buyer keyId', keyId(buyer.publicKey));
kv('seller(cheat)', keyId(sellerCheating.publicKey));
kv('settlement auth', keyId(settlementKey.publicKey));

// --- the committed contract spec (computed from the CLEAN dataset) -----------

const cleanRows = buildCleanDataset();
const committedSum = sumColumn(cleanRows, 'revenue');
const committedDigest = sampleDigestFor(cleanRows, CONTRACT_NONCE, SAMPLE_K);

/** The dataset spec the buyer signs into the contract. */
const datasetParams = {
  format: 'json',
  columns: [
    { name: 'id', type: 'number', required: true, nullable: false, range: { min: 1 } },
    { name: 'region', type: 'string', required: true, nullable: false, domain: ['us', 'eu', 'apac', 'latam'] },
    { name: 'revenue', type: 'number', required: true, nullable: false, range: { min: 0, max: 100000 }, maxNullRate: 0 },
    { name: 'churned', type: 'boolean', required: true, nullable: false },
  ],
  rowCount: { min: ROW_COUNT, max: ROW_COUNT },
  uniqueKeys: [['id']],
  sample: { k: SAMPLE_K, sampleDigest: committedDigest },
  aggregates: [{ column: 'revenue', op: 'sum', expected: committedSum }],
};

// Build a contract for a given predicate (shape mirrors demo-compute.mjs).
function makeContract({ predicate, railId }) {
  return {
    id: 'dc_dataset_demo',
    buyer: keyId(buyer.publicKey),
    seller: keyId(sellerCheating.publicKey),
    intent: 'deliver a cleaned customer dataset (1000 rows)',
    deliverableType: 'application/json',
    predicate,
    price: { amount: 50, currency: 'USDC' },
    sla: { deadlineMs: 60_000 },
    refundRule: 'full-refund-on-failed-delivery',
    railId,
    nonce: CONTRACT_NONCE,
    createdAt: Date.now(),
  };
}

// --- the corrupt deliverable: right shape, wrong content ---------------------

// Right columns, right types, right row count — but one id is duplicated and
// revenue is bumped by 1 on a subset of rows. Shape checks do not see either
// content problem; deep dataset correctness does.
const corruptRows = buildCleanDataset().map((r, i) => {
  const corrupted = i % 3 === 0 ? { ...r, revenue: r.revenue + 1 } : { ...r };
  if (i === 37) corrupted.id = 3;
  return corrupted;
});
const corruptSum = sumColumn(corruptRows, 'revenue');

// The seller's tool: it always returns the corrupt-but-well-formed dataset.
const produceCorrupt = () => {
  console.log(
    `\n  [seller-cheat] delivering ${corruptRows.length} rows ` +
      '(correct columns/types/row-count, revenue silently corrupted)',
  );
  return { output: corruptRows };
};

// --- 1) SHALLOW verifier (schema/shape) — what competitors ship --------------

const shallowRail = createMockEscrowRail();
const shallowContract = makeContract({
  predicate: {
    kind: 'schema',
    params: {
      schema: {
        type: 'array',
        items: {
          type: 'object',
          required: ['id', 'region', 'revenue', 'churned'],
          properties: {
            id: { type: 'number' },
            region: { type: 'string' },
            revenue: { type: 'number' },
            churned: { type: 'boolean' },
          },
        },
      },
    },
  },
  railId: shallowRail.id,
});
const shallowRoute = routeVerifier(shallowContract, {
  policy: { deliverableType: 'dataset', minAssurance: 1 },
});

section('SHALLOW verifier: JSON-schema shape only ("right columns + types?")');
kv('router policy', 'deliverableType=dataset, minAssurance=1');
kv('router selected', shallowRoute.routeDecision.selected);
kv('verifier', 'schema  (what PayCrow / x402+escrow-style checks do)');
const shallowResult = await settle({
  contract: shallowContract,
  produceEvidence: produceCorrupt,
  verifier: shallowRoute.verifier,
  rail: shallowRail,
  settlementKey,
  routeDecision: shallowRoute.routeDecision,
});
kv('predicate met?', yn(shallowResult.verdict.ok));
kv('reason', shallowResult.verdict.reason);
kv('decision', shallowResult.receipt.decision.toUpperCase());
kv('seller paid?', yn(shallowResult.hold.state === 'captured'));
console.log('  >> A shallow shape-check PAYS for a corrupt dataset. This is the status quo.');

// --- 2) DEEP verifier (dataset correctness) — DeliveryProof ------------------

const deepRail = createMockEscrowRail();
const deepContract = makeContract({
  predicate: { kind: 'dataset', params: datasetParams },
  railId: deepRail.id,
});
const deepRoute = routeVerifier(deepContract, {
  policy: { deliverableType: 'dataset', minAssurance: 3 },
});

section('DEEP verifier: router selects dataset correctness (unique key + sample + sum)');
kv('router policy', 'deliverableType=dataset, minAssurance=3');
kv('router selected', deepRoute.routeDecision.selected);
kv('verifier', 'dataset  (DeliveryProof Tier A — objective dataset correctness)');
kv('committed sum(revenue)', String(committedSum));
kv('delivered sum(revenue)', String(corruptSum));
kv('unique key', 'id must be unique');
kv('committed sampleDigest', committedDigest.slice(0, 24) + '…');
const deepResult = await settle({
  contract: deepContract,
  produceEvidence: produceCorrupt,
  verifier: deepRoute.verifier,
  rail: deepRail,
  settlementKey,
  routeDecision: deepRoute.routeDecision,
});
kv('predicate met?', yn(deepResult.verdict.ok));
kv('reason', deepResult.verdict.reason);
if (deepResult.verdict.diff) kv('structured diff', JSON.stringify(deepResult.verdict.diff));
kv('decision', deepResult.receipt.decision.toUpperCase());
kv('seller paid?', yn(deepResult.hold.state === 'captured'));
console.log('  >> The deep dataset check REFUNDS. Same bytes, money saved.');

// --- side-by-side + live invariants -----------------------------------------

section('SIDE BY SIDE — the SAME deliverable, judged two ways');
console.log(
  '  Shallow (2xx + JSON-schema shape, what PayCrow/x402-escrow pays): ' +
    `${shallowResult.verdict.ok ? 'PASS' : 'FAIL'} -> ${shallowResult.receipt.decision.toUpperCase()}`,
);
console.log(
  '  DeliveryProof deep dataset correctness:                          ' +
    `${deepResult.verdict.ok ? 'PASS' : 'FAIL'} (router-selected deep verifier) -> ` +
    `${deepResult.receipt.decision.toUpperCase()}`,
);
console.log('\n  This is precisely the data deliverable a shallow rail wrongly pays.');

// Assert the money shot live: shallow captured AND deep refunded. Also assert
// the deep refund left NO captured history entry (capture provably un-invoked).
const shallowCaptured = shallowResult.hold.state === 'captured';
const deepRefunded = deepResult.hold.state === 'refunded';
const deepNeverCaptured = !deepResult.hold.history.some((h) => h.state === 'captured');

if (!(shallowCaptured && deepRefunded && deepNeverCaptured)) {
  throw new Error(
    'DATASET MONEY-SHOT BROKEN: expected shallow=captured AND deep=refunded (capture never invoked)',
  );
}

// Receipts must be valid, verifiable signatures over the exact terms.
const shallowReceiptOk = verifyReceipt(shallowResult.receipt, settlementKey.publicKey);
const deepReceiptOk = verifyReceipt(deepResult.receipt, settlementKey.publicKey);
if (!shallowReceiptOk || !deepReceiptOk) {
  console.error('\n[FATAL] a receipt signature failed to verify');
  process.exit(1);
}

banner('RESULT');
kv('shallow decision', shallowResult.receipt.decision.toUpperCase() + ' (cheater PAID)');
kv('deep decision', deepResult.receipt.decision.toUpperCase() + ' (buyer made whole)');
kv('both receipts valid?', yn(shallowReceiptOk && deepReceiptOk));
console.log(`
  DeliveryProof gates settlement on OBJECTIVE dataset correctness — row count,
  required/nullable fields, type/domain/range/null-rate, unique keys, a
  verifier-seeded sample hash, and aggregate invariants — none of which a shipped
  "allowed-to-pay" rail checks. The signed receipt also commits the router's
  routeDecision, so a downgrade from dataset->schema is tamper-evident.
  It composes with x402 / AP2 / Stripe MPP; it does not compete with them.
`);

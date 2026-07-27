// examples/demo-compute.mjs
//
// DeliveryProof — self-contained, runnable demo (Node v22+).
//
//   Run:  node examples/demo-compute.mjs
//
// THESIS DEMONSTRATED HERE:
//   Existing agent-payment rails prove "the agent was ALLOWED to pay".
//   They do NOT prove "the counterparty actually DELIVERED what was agreed".
//   DeliveryProof binds a payment to an explicit *delivery predicate*,
//   verifies the deliverable, emits a signed DeliveryReceipt, and only then
//   RELEASES funds (capture) or REFUNDS them (buyer made whole).
//
//   Verify gates settlement. There is NO path that pays the seller when the
//   delivery predicate fails.
//
// Three scenarios:
//   1. HAPPY      — honest seller delivers correct output -> RELEASE (captured).
//   2. REFUND     — cheating seller delivers wrong output -> REFUND.
//   3. TRANSCRIPT — nonce-bound signed transcript passes; then we tamper one
//                   byte of the output and watch the same verifier reject it.
//
// All cryptography, escrow, and verification is real code (Node built-ins);
// only the *settlement rail* is an in-memory mock standing in for a real
// x402 / Stripe MPP / AP2 adapter.

import { randomUUID } from 'node:crypto';

import { generateKeypair, sign, keyId } from '../src/protocol/crypto.mjs';
import { canonicalize, sha256hex } from '../src/protocol/canonical.mjs';
import { getVerifier } from '../src/verifiers/index.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { settle, verifyReceipt } from '../src/engine/deliveryproof.mjs';

// ---------------------------------------------------------------------------
// Small pretty-printing helpers (no deps).
// ---------------------------------------------------------------------------

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
  console.log('  ' + String(label).padEnd(20) + ': ' + value);
}

function j(value) {
  return JSON.stringify(value);
}

function yn(b) {
  return b ? 'YES' : 'NO';
}

// Build a DeliveryContract per the protocol's documented shape.
function makeContract({ buyer, seller, intent, deliverableType, predicate, price, railId }) {
  return {
    id: 'dc_' + randomUUID(),
    buyer: keyId(buyer.publicKey),
    seller: keyId(seller.publicKey),
    intent,
    deliverableType,
    predicate,
    price,
    sla: { deadlineMs: 30_000 },
    refundRule: 'full-refund-on-failed-delivery',
    railId,
    nonce: randomUUID(),
    createdAt: Date.now(),
  };
}

// Pretty summary of a settle() result.
function reportSettlement(result, { delivered, settlementKey }) {
  const { verdict, receipt, hold } = result;

  section('VERDICT (delivery verification)');
  kv('verifier', verdict.verifier);
  kv('tier', verdict.tier + '  (A = objective, no third-party trust)');
  kv('predicate met?', yn(verdict.ok));
  kv('reason', verdict.reason);

  section('RECEIPT (signed by settlement authority)');
  kv('decision', receipt.decision.toUpperCase());
  kv('signer keyId', receipt.signerKeyId);
  kv('evidenceHash', receipt.evidenceHash.slice(0, 24) + '…');
  kv('signature', receipt.signature.slice(0, 24) + '…');
  const receiptValid = verifyReceipt(receipt, settlementKey.publicKey);
  kv('receipt signature ok?', yn(receiptValid));

  section('ESCROW HOLD (settlement rail)');
  kv('holdId', hold.holdId);
  kv('amount', hold.amount + ' ' + hold.currency);
  kv('final state', hold.state.toUpperCase());
  kv('seller actually paid?', yn(hold.state === 'captured'));

  // The core invariant, asserted live in the demo so it is impossible to miss.
  if (!verdict.ok && hold.state === 'captured') {
    throw new Error(
      'INVARIANT VIOLATION: seller was paid despite a failed delivery verdict!'
    );
  }

  return {
    delivered,
    decision: receipt.decision,
    sellerPaid: hold.state === 'captured',
    receiptValid,
  };
}

// ---------------------------------------------------------------------------
// Key setup. Four independent parties / authorities.
// ---------------------------------------------------------------------------

banner('DeliveryProof — verified-delivery-gated settlement (PoC demo)');

console.log(`
  Landscape, in one line:
    Rails (x402 / AP2 / Stripe MPP / card networks)  ->  "ALLOWED to pay"
    DeliveryProof (this)                             ->  "DID the seller DELIVER?"

  Below, the *same* payment is gated on a *delivery predicate*. Watch the
  decision flip from RELEASE to REFUND purely because the deliverable changed.
`);

const buyer = generateKeypair();
const sellerHonest = generateKeypair();
const sellerCheating = generateKeypair();
const settlementKey = generateKeypair(); // settlement authority signs receipts

kv('buyer keyId', keyId(buyer.publicKey));
kv('seller(honest)', keyId(sellerHonest.publicKey));
kv('seller(cheat)', keyId(sellerCheating.publicKey));
kv('settlement auth', keyId(settlementKey.publicKey));

const results = {};

// ---------------------------------------------------------------------------
// SCENARIO 1 — HAPPY PATH: honest seller, correct output, RELEASE.
//
// Predicate: builtin-replay { op:'sort', input:[5,3,9,1] }  (Tier A: objective
// replay — the verifier RE-COMPUTES the sort and deep-equals the delivery).
// ---------------------------------------------------------------------------

banner('SCENARIO 1 — HAPPY PATH (honest delivery -> RELEASE)');

{
  const rail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
  const verifier = getVerifier('builtin-replay');

  const contract = makeContract({
    buyer,
    seller: sellerHonest,
    intent: 'sort array ascending',
    deliverableType: 'application/json',
    predicate: { kind: 'builtin-replay', params: { op: 'sort', input: [5, 3, 9, 1] } },
    price: { amount: 5, currency: 'USDC' },
    railId: rail.id,
  });

  section('CONTRACT');
  kv('id', contract.id);
  kv('intent', contract.intent);
  kv('predicate', contract.predicate.kind + ' ' + j(contract.predicate.params));
  kv('price', contract.price.amount + ' ' + contract.price.currency);
  kv('seller', 'HONEST (' + keyId(sellerHonest.publicKey) + ')');

  // Honest seller: actually performs the agreed computation.
  const produceEvidence = async (c) => {
    const output = [...c.predicate.params.input].sort((a, b) => a - b);
    console.log('\n  [seller-honest] delivering output: ' + j(output));
    return {
      contractId: c.id,
      nonce: c.nonce,
      output,
      outputHash: sha256hex(output),
      producedAt: Date.now(),
    };
  };

  const result = await settle({
    contract,
    produceEvidence,
    verifier,
    rail,
    settlementKey,
  });

  results['1. Happy (correct sort)'] = reportSettlement(result, {
    delivered: true,
    settlementKey,
  });
}

// ---------------------------------------------------------------------------
// SCENARIO 2 — REFUND: SAME contract terms, cheating seller, wrong output.
//
// The objective-replay verifier recomputes the correct sort and finds the
// delivered array does not match -> verdict fails -> REFUND. Seller is NOT paid.
// ---------------------------------------------------------------------------

banner('SCENARIO 2 — CHEATING DELIVERY (wrong output -> REFUND)');

{
  const rail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
  const verifier = getVerifier('builtin-replay');

  const contract = makeContract({
    buyer,
    seller: sellerCheating,
    intent: 'sort array ascending',
    deliverableType: 'application/json',
    predicate: { kind: 'builtin-replay', params: { op: 'sort', input: [5, 3, 9, 1] } },
    price: { amount: 5, currency: 'USDC' },
    railId: rail.id,
  });

  section('CONTRACT');
  kv('id', contract.id);
  kv('intent', contract.intent);
  kv('predicate', contract.predicate.kind + ' ' + j(contract.predicate.params));
  kv('price', contract.price.amount + ' ' + contract.price.currency);
  kv('seller', 'CHEATING (' + keyId(sellerCheating.publicKey) + ')');

  // Cheating seller: returns descending (wrong) but still tries to get paid.
  const produceEvidence = async (c) => {
    const wrong = [...c.predicate.params.input].sort((a, b) => b - a); // 9,5,3,1
    console.log('\n  [seller-cheat] delivering output: ' + j(wrong) + '  (NOT ascending!)');
    return {
      contractId: c.id,
      nonce: c.nonce,
      output: wrong,
      outputHash: sha256hex(wrong),
      producedAt: Date.now(),
    };
  };

  const result = await settle({
    contract,
    produceEvidence,
    verifier,
    rail,
    settlementKey,
  });

  results['2. Cheat (wrong sort)'] = reportSettlement(result, {
    delivered: false,
    settlementKey,
  });
}

// ---------------------------------------------------------------------------
// SCENARIO 3 — TRANSCRIPT: nonce-bound signed attestation, then tamper.
//
// Here the deliverable is verified by a *signed, nonce-bound transcript*:
// the seller signs canonical({ contractId, nonce, outputHash }). The verifier
// checks (a) the signature, (b) attestation nonce == contract.nonce (replay
// binding), (c) outputHash == sha256hex(output) (output binding).
//
// First we run it clean -> PASS -> RELEASE.
// Then we flip ONE byte of the output and re-run -> the outputHash no longer
// matches the signed transcript -> verifier REJECTS -> REFUND.
// ---------------------------------------------------------------------------

banner('SCENARIO 3 — SIGNED TRANSCRIPT (pass), then TAMPER (reject)');

// Helper: an honest transcript-signing seller. `mutate` lets us corrupt the
// delivered output AFTER it has been signed, to simulate tampering in flight.
function makeTranscriptEvidenceProducer(sellerKey, { mutate = false } = {}) {
  return async (c) => {
    // The honest computed output the seller signs over.
    const trueOutput = [...c.predicate.params.input].sort((a, b) => a - b);
    const signedHash = sha256hex(trueOutput);

    // Seller signs a nonce-bound transcript over the TRUE output hash.
    const transcript = canonicalize({
      contractId: c.id,
      nonce: c.nonce,
      outputHash: signedHash,
    });
    const signature = sign(sellerKey.privateKey, transcript);

    // What is actually delivered. If tampering, flip a byte of the output so
    // it no longer matches the signed hash.
    let deliveredOutput = trueOutput;
    if (mutate) {
      deliveredOutput = [...trueOutput];
      deliveredOutput[0] = deliveredOutput[0] + 1; // single-byte corruption
      console.log('\n  [tamper] output mutated AFTER signing: ' +
        j(trueOutput) + '  ->  ' + j(deliveredOutput));
    } else {
      console.log('\n  [seller] delivering signed output: ' + j(deliveredOutput));
    }

    return {
      contractId: c.id,
      nonce: c.nonce,
      output: deliveredOutput,
      outputHash: sha256hex(deliveredOutput),
      attestations: [
        {
          signerKeyId: keyId(sellerKey.publicKey),
          publicKey: sellerKey.publicKey,
          signature,
        },
      ],
      producedAt: Date.now(),
    };
  };
}

// --- 3a: clean transcript -> PASS -> RELEASE -------------------------------
{
  const rail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
  const verifier = getVerifier('transcript');

  const contract = makeContract({
    buyer,
    seller: sellerHonest,
    intent: 'sort array ascending (transcript-attested)',
    deliverableType: 'application/json',
    predicate: { kind: 'transcript', params: {} },
    price: { amount: 7, currency: 'USDC' },
    railId: rail.id,
  });
  // Reuse the builtin-replay input shape so the producer can compute the output.
  contract.predicate.params.input = [5, 3, 9, 1];

  section('CONTRACT (3a — clean transcript)');
  kv('id', contract.id);
  kv('intent', contract.intent);
  kv('predicate', contract.predicate.kind + ' (nonce-bound signed attestation)');
  kv('nonce', contract.nonce);
  kv('price', contract.price.amount + ' ' + contract.price.currency);

  const result = await settle({
    contract,
    produceEvidence: makeTranscriptEvidenceProducer(sellerHonest, { mutate: false }),
    verifier,
    rail,
    settlementKey,
  });

  results['3a. Transcript (clean)'] = reportSettlement(result, {
    delivered: true,
    settlementKey,
  });
}

// --- 3b: tampered output -> signature/hash mismatch -> REJECT -> REFUND -----
{
  const rail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
  const verifier = getVerifier('transcript');

  const contract = makeContract({
    buyer,
    seller: sellerHonest,
    intent: 'sort array ascending (transcript-attested)',
    deliverableType: 'application/json',
    predicate: { kind: 'transcript', params: {} },
    price: { amount: 7, currency: 'USDC' },
    railId: rail.id,
  });
  contract.predicate.params.input = [5, 3, 9, 1];

  section('CONTRACT (3b — tampered output, same signature)');
  kv('id', contract.id);
  kv('intent', contract.intent);
  kv('predicate', contract.predicate.kind + ' (nonce-bound signed attestation)');
  kv('nonce', contract.nonce);
  kv('price', contract.price.amount + ' ' + contract.price.currency);

  const result = await settle({
    contract,
    produceEvidence: makeTranscriptEvidenceProducer(sellerHonest, { mutate: true }),
    verifier,
    rail,
    settlementKey,
  });

  results['3b. Transcript (tampered)'] = reportSettlement(result, {
    delivered: false,
    settlementKey,
  });
}

// ---------------------------------------------------------------------------
// SCENARIO 4 — THE MONEY SHOT: shallow verification PAYS, deep verification REFUNDS.
//
// This is the whole competitive thesis in one screen. A cheating seller delivers
// [9,5,3,1] for "sort ascending". That output is a perfectly VALID array of
// numbers — so a SHALLOW verifier (HTTP 2xx + JSON-schema shape, which is what
// shipped escrow products like PayCrow do, and what Coinbase x402+Escrow leaves
// to the developer) ACCEPTS it and PAYS the cheater.
//
// DeliveryProof's DEEP verifier (Tier A objective replay) re-executes the sort,
// sees [9,5,3,1] != [1,3,5,9], and REFUNDS. Same deliverable, opposite outcome.
// Schema-valid != correct. THIS is the gap nobody else closes.
// ---------------------------------------------------------------------------

banner('SCENARIO 4 — MONEY SHOT: shallow verifier PAYS, deep verifier REFUNDS');

{
  // The same wrong deliverable, judged two ways.
  const wrongOutput = [9, 5, 3, 1]; // valid number[], but NOT ascending sort

  console.log(`
  A cheating seller is paid 10 USDC to "sort [5,3,9,1] ascending".
  It delivers ${j(wrongOutput)} — a structurally valid array of numbers,
  but the WRONG answer. Watch two verifiers judge the SAME deliverable:
`);

  // Shared producer: delivers the wrong-but-well-formed output.
  const produceWrong = async (c) => {
    console.log('  [seller-cheat] delivering output: ' + j(wrongOutput) +
      '  (valid number[], wrong order)');
    return {
      contractId: c.id,
      nonce: c.nonce,
      output: wrongOutput,
      outputHash: sha256hex(wrongOutput),
      producedAt: Date.now(),
    };
  };

  // --- 4a: SHALLOW verifier (schema/shape) — what competitors ship -----------
  const shallowRail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
  const shallowContract = makeContract({
    buyer,
    seller: sellerCheating,
    intent: 'sort array ascending',
    deliverableType: 'application/json',
    predicate: { kind: 'schema', params: { schema: { type: 'array', items: { type: 'number' } } } },
    price: { amount: 10, currency: 'USDC' },
    railId: shallowRail.id,
  });

  section('4a — SHALLOW verifier: schema/shape only ("is it a number array?")');
  kv('verifier', 'schema  (what PayCrow / x402+Escrow-style checks do)');
  const shallowResult = await settle({
    contract: shallowContract,
    produceEvidence: produceWrong,
    verifier: getVerifier('schema'),
    rail: shallowRail,
    settlementKey,
  });
  kv('predicate met?', yn(shallowResult.verdict.ok));
  kv('reason', shallowResult.verdict.reason);
  kv('decision', shallowResult.receipt.decision.toUpperCase());
  kv('seller paid?', yn(shallowResult.hold.state === 'captured'));
  console.log('  >> A shallow check PAYS the cheater. This is the status quo.');

  // --- 4b: DEEP verifier (objective replay) — DeliveryProof -------------------
  const deepRail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
  const deepContract = makeContract({
    buyer,
    seller: sellerCheating,
    intent: 'sort array ascending',
    deliverableType: 'application/json',
    predicate: { kind: 'builtin-replay', params: { op: 'sort', input: [5, 3, 9, 1] } },
    price: { amount: 10, currency: 'USDC' },
    railId: deepRail.id,
  });

  section('4b — DEEP verifier: objective replay ("re-run the sort, compare")');
  kv('verifier', 'builtin-replay  (DeliveryProof Tier A — re-executes the work)');
  const deepResult = await settle({
    contract: deepContract,
    produceEvidence: produceWrong,
    verifier: getVerifier('builtin-replay'),
    rail: deepRail,
    settlementKey,
  });
  kv('predicate met?', yn(deepResult.verdict.ok));
  kv('reason', deepResult.verdict.reason);
  kv('decision', deepResult.receipt.decision.toUpperCase());
  kv('seller paid?', yn(deepResult.hold.state === 'captured'));
  console.log('  >> The deep check REFUNDS. Same deliverable, money saved.');

  // The point, asserted live so the demo fails loudly if the gap ever closes.
  if (!(shallowResult.hold.state === 'captured' && deepResult.hold.state === 'refunded')) {
    throw new Error('MONEY-SHOT BROKEN: expected shallow=captured, deep=refunded');
  }

  results['4a. Money-shot (shallow/schema)'] = {
    delivered: false,
    decision: shallowResult.receipt.decision,
    sellerPaid: shallowResult.hold.state === 'captured',
    receiptValid: verifyReceipt(shallowResult.receipt, settlementKey.publicKey),
  };
  results['4b. Money-shot (deep/re-exec)'] = {
    delivered: false,
    decision: deepResult.receipt.decision,
    sellerPaid: deepResult.hold.state === 'captured',
    receiptValid: verifyReceipt(deepResult.receipt, settlementKey.publicKey),
  };
}

// ---------------------------------------------------------------------------
// SUMMARY TABLE
// ---------------------------------------------------------------------------

banner('SUMMARY');

const rows = Object.entries(results);
const col1 = Math.max(24, ...rows.map(([k]) => k.length));

const header =
  '  ' +
  'scenario'.padEnd(col1) +
  ' | ' + 'delivered?'.padEnd(11) +
  ' | ' + 'decision'.padEnd(9) +
  ' | ' + 'seller paid?';
console.log('\n' + header);
console.log('  ' + '-'.repeat(header.length - 2));

for (const [name, r] of rows) {
  console.log(
    '  ' +
    name.padEnd(col1) +
    ' | ' + (r.delivered ? 'correct' : 'WRONG').padEnd(11) +
    ' | ' + r.decision.toUpperCase().padEnd(9) +
    ' | ' + (r.sellerPaid ? 'YES' : 'no')
  );
}

console.log(`
  Read it top to bottom:
    • When the deliverable matched the predicate  -> RELEASE, seller paid.
    • When it did NOT (wrong output, or tampered)  -> REFUND, seller NOT paid.

  The payment authorization never changed — what changed was whether DELIVERY
  was actually proven. That gap is exactly what DeliveryProof closes, and it is
  exactly what "allowed-to-pay" rails leave open.

  Honest framing: this turns HIDDEN trust into EXPLICIT, TIERED trust. The
  objective-replay (Tier A) verifier above needs no third party; a real system
  would also use Tier B (zkTLS/TEE/oracle: proves "a source SAID X") and Tier C
  (subjective AI-quality) verifiers, each with weaker guarantees. DeliveryProof
  does not abolish trust — it makes it composable and auditable.
`);

// Non-zero exit if a real invariant was violated. The engine invariant
// (no capture when the VERDICT fails) is asserted live inside reportSettlement
// and in the money-shot block; here we just require every receipt to be a valid,
// verifiable signature. NOTE: scenario 4a is *supposed* to release on a wrong-but-
// schema-valid deliverable — that is the shallow-verifier gap we are exposing, not
// an engine bug — so we do NOT flag release-on-incorrect here.
const broke = rows.find(([, r]) => !r.receiptValid);
if (broke) {
  console.error('\n[FATAL] a receipt signature failed to verify: ' + broke[0]);
  process.exit(1);
}

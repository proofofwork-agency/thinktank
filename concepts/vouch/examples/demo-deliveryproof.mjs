// THE money-shot: why vouch is not DeliveryProof.
//
//   Run: node examples/demo-deliveryproof.mjs
//
// A buyer pays 4 USDC for a market signal and trades 5,000 USDC on the answer.
// The agent returns schema-valid but factually wrong data. DeliveryProof does
// its job perfectly: the deep verifier catches it and refunds the 4 USDC fee.
//
// The buyer is still out 4,996 USDC.
//
// That residual is the whole reason vouch exists. DeliveryProof answers "did it
// happen?" and returns your fee. vouch answers "who eats the loss?" and returns
// your loss — using a third party's capital, priced ex ante by a market.
//
// DeliveryProof is the oracle here, not a competitor: its signed refund receipt
// IS the machine-checkable trigger vouch settles on. Bill of lading, then
// marine insurance.

import {
  createCommitment,
  createVouchMarket,
  createDeliveryProofAdapter,
  attestationAdapter,
  mintBadge,
  renderBadgeMarkdown,
  replayOracle,
} from '../src/index.mjs';

const DP_PATH = '../../deliveryproof/concept/src/index.mjs';

let dp;
try {
  dp = await import(DP_PATH);
} catch (error) {
  console.error(`\n  Could not load DeliveryProof from ${DP_PATH}`);
  console.error(`  (${error.message})`);
  console.error('  DeliveryProof is an optional composition — vouch core has no dependency on it.');
  console.error('  Run `node examples/demo-underwrite.mjs` for the standalone flow.\n');
  process.exit(0);
}

const USDC = 1_000_000; // micro-USDC, so all money stays integer
const HEAVY = '═'.repeat(74);
const LINE = '─'.repeat(74);
const kv = (k, v) => console.log('  ' + String(k).padEnd(26) + ': ' + v);
const usd = (n) => `${(n / USDC).toLocaleString('en-US', { maximumFractionDigits: 2 })} USDC`;

const seller = dp.generateKeypair();
const buyer = dp.generateKeypair();
const settlementKey = dp.generateKeypair();

console.log('\n' + HEAVY);
console.log('  vouch × DeliveryProof — the fee is refunded, the loss is not');
console.log(HEAVY);

// ---------------------------------------------------------------------------
// 1. DeliveryProof settles the delivery question.
// ---------------------------------------------------------------------------
const contract = {
  id: 'dc_signal_demo',
  buyer: dp.keyId(buyer.publicKey),
  seller: dp.keyId(seller.publicKey),
  intent: 'paid market signal: Amsterdam spot reading, fresh',
  deliverableType: 'api-response',
  predicate: {
    kind: 'api-response',
    params: {
      request: { method: 'GET', url: 'https://api.example.com/weather?city=Amsterdam' },
      status: { min: 200, max: 299 },
      contentType: 'application/json',
      fields: [
        { path: 'city', equals: 'Amsterdam' },
        { path: 'temperature', type: 'number', min: -90, max: 60 },
      ],
      freshnessMs: 60_000,
    },
  },
  price: { amount: 4, currency: 'USDC' },
  sla: { deadlineMs: 60_000 },
  refundRule: 'full-refund-on-fail',
  railId: 'escrow-mock',
  nonce: 'nonce-vouch-demo',
  createdAt: Date.now(),
};

// Schema-valid, factually wrong: the classic failure a shape check waves through.
const transcript = {
  contractId: contract.id,
  nonce: contract.nonce,
  request: { method: 'GET', url: 'https://api.example.com/weather?city=Amsterdam' },
  response: {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    body: { city: 'London', temperature: 21 },
  },
  producedAt: contract.createdAt,
};

const rail = dp.createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
const { verifier, routeDecision } = dp.routeVerifier(contract, {
  policy: { deliverableType: 'api-response', minAssurance: 3 },
});

const settled = await dp.settle({
  contract,
  produceEvidence: () => ({ output: transcript }),
  verifier,
  rail,
  settlementKey,
  routeDecision,
});

console.log('\n' + LINE);
console.log('  STEP 1 — DeliveryProof: did the agent deliver?');
console.log(LINE);
kv('delivered', 'city=London (asked for Amsterdam)');
kv('predicate met?', settled.verdict.ok ? 'YES' : 'NO');
kv('decision', settled.receipt.decision.toUpperCase());
kv('fee refunded', usd(4 * USDC));
console.log('\n  DeliveryProof worked exactly as designed. The buyer has their 4 USDC back.');

// ---------------------------------------------------------------------------
// 2. The gap DeliveryProof does not close.
// ---------------------------------------------------------------------------
const FEE = 4 * USDC;
const EXPOSURE = 5_000 * USDC;

console.log('\n' + LINE);
console.log('  STEP 2 — the residual');
console.log(LINE);
kv('fee recovered by escrow', usd(FEE));
kv('trade sized on the signal', usd(EXPOSURE));
kv('buyer still out', usd(EXPOSURE - FEE));
console.log('\n  A refund is not a remedy. No escrow protocol can close this, because');
console.log('  escrow only ever holds the fee. Closing it needs someone else\'s capital.');

// ---------------------------------------------------------------------------
// 3. vouch: a stranger's capital, priced ex ante, settled by that same receipt.
// ---------------------------------------------------------------------------
const market = createVouchMarket({
  adapters: [createDeliveryProofAdapter(dp), attestationAdapter],
});
// A little over EXPOSURE: the history below bonds every job, and the one that
// fails has its bond subrogated away, so the agent needs headroom.
market.deposit('signal-agent', EXPOSURE + 1_000);
market.deposit('buyer', 300 * USDC);
market.deposit('underwriter', EXPOSURE);

// Settle that history through the market itself, so the badge later has a real
// ledger to replay. A badge is strictly ledger-derived: an agent cannot import
// a reputation it did not earn here.
for (let i = 0; i < 200; i += 1) {
  const warmup = createCommitment({
    promisor: 'signal-agent',
    beneficiary: 'buyer',
    feeAmount: 0,
    exposureAmount: 1,
    bondAmount: 1, // fully bonded: the only regime this market writes
    verifier: { kind: 'attestation' },
    deadline: 1_000,
    nonce: `history-${i}`,
  });
  market.open(warmup, { actor: 'signal-agent' });
  // Each carries a real policy: only outcomes an underwriter staked capital on
  // count toward reputation, so a record cannot be manufactured for free.
  const covered = market.quote({
    commitmentId: warmup.commitmentId,
    underwriter: 'underwriter',
    coverageAmount: 1,
    premiumAmount: 1,
    expiresAt: 900,
  });
  market.bind(covered.quoteId, { actor: 'buyer' });
  market.settle(warmup.commitmentId, { delivered: i !== 137 });
}

// Price the cover off the ledger's own settled history — 200 jobs, one miss.
const oracle = replayOracle(market.ledger);
const premium = oracle.fairPremium('signal-agent', EXPOSURE - FEE);
const scoreBefore = oracle.scoreBasisPoints('signal-agent');

const commitment = createCommitment({
  promisor: 'signal-agent',
  beneficiary: 'buyer',
  feeAmount: FEE,
  exposureAmount: EXPOSURE,
  bondAmount: EXPOSURE,
  verifier: { kind: 'deliveryproof', contractHash: settled.receipt.contractHash },
  deadline: 1_000,
  nonce: contract.nonce,
});

market.open(commitment, { actor: 'signal-agent' });
const quote = market.quote({
  commitmentId: commitment.commitmentId,
  underwriter: 'underwriter',
  coverageAmount: EXPOSURE - FEE,
  premiumAmount: premium,
  expiresAt: 500,
});
market.bind(quote.quoteId, { actor: 'buyer' });

console.log('\n' + LINE);
console.log('  STEP 3 — vouch: cover bought BEFORE the work, priced by the oracle');
console.log(LINE);
kv('agent score', `${(oracle.scoreBasisPoints('signal-agent') / 100).toFixed(1)}%`);
kv('cover bought', usd(EXPOSURE - FEE));
kv('premium paid', usd(premium));
kv('regime', market.coverageRegime(commitment.commitmentId));

// The SAME signed receipt DeliveryProof produced is the settlement trigger.
const result = market.settle(
  commitment.commitmentId,
  { receipt: settled.receipt, settlementPublicKey: settlementKey.publicKey },
);

console.log('\n' + LINE);
console.log('  STEP 4 — settlement, from the same signed receipt');
console.log(LINE);
kv('outcome', result.outcome.toUpperCase());
kv('proof', result.reason);
kv('paid to buyer', usd(result.payout));
kv('recovered from agent bond', usd(result.subrogated));
kv('underwriter net', usd(premium - result.payout + result.subrogated));

console.log('\n  The buyer is whole. The underwriter is up the premium and down nothing,');
console.log('  because subrogation took the payout out of the agent\'s bond. The agent');
console.log('  paid for its own failure — which is what makes deliberate failure a');
console.log('  losing strategy rather than a free option.');

// ---------------------------------------------------------------------------
// 4. The byproduct.
// ---------------------------------------------------------------------------
const replayed = replayOracle(market.ledger);
const badge = mintBadge(market.ledger, 'signal-agent', { exposure: EXPOSURE - FEE });

console.log('\n' + LINE);
console.log('  STEP 5 — the byproduct nobody had to build');
console.log(LINE);
kv('settled history', JSON.stringify(replayed.history('signal-agent')));
kv('score before this job', `${(scoreBefore / 100).toFixed(2)}%`);
kv('score after', `${(replayed.scoreBasisPoints('signal-agent') / 100).toFixed(2)}%`);
kv('cover now costs', usd(replayed.fairPremium('signal-agent', EXPOSURE - FEE)));
kv('was', usd(premium));
console.log('\n  ' + renderBadgeMarkdown(badge));
console.log('\n  The failure repriced the agent in the same ledger that paid out on it.');
console.log('  Nobody adjudicated that. It is a fold over settled outcomes.');
console.log('\n  AMMs were built to swap tokens and produced a price oracle. vouch is built');
console.log('  to move risk and produces a live, collateral-backed delivery score — one');
console.log('  nobody operates, because it is a pure replay of the ledger.\n');
console.log(HEAVY + '\n');

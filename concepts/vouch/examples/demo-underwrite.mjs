// The standalone flow: no DeliveryProof, no chain, no network.
//
//   Run: node examples/demo-underwrite.mjs
//
// Shows the thing that makes the market self-correcting: the cost of being an
// unknown agent. Nobody screens applicants and nobody is banned. Uncertainty is
// simply priced, and the price is what an underwriter should charge given how
// little the ledger knows.

import {
  createCommitment,
  createVouchMarket,
  attestationAdapter,
  replayOracle,
  mintBadge,
  renderBadgeMarkdown,
  renderBadgeSVG,
} from '../src/index.mjs';

const HEAVY = '═'.repeat(74);
const LINE = '─'.repeat(74);
const kv = (k, v) => console.log('  ' + String(k).padEnd(26) + ': ' + v);

const EXPOSURE = 1_000_000;

const market = createVouchMarket({ adapters: [attestationAdapter] });
market.deposit('buyer', 5_000_000);
market.deposit('underwriter', 20_000_000);
market.deposit('veteran', 5_000_000);
market.deposit('rookie', 5_000_000);
market.deposit('flaky', 5_000_000);

console.log('\n' + HEAVY);
console.log('  vouch — the price of being unknown');
console.log(HEAVY);

// Build settled history for two agents; the rookie gets none.
// Every history-building job carries a real policy. Reputation is only earned
// where capital was at risk — otherwise an agent could mint a spotless record
// out of free self-dealt jobs and buy cheap cover on the strength of it.
let nonce = 0;
function runJob(agent, delivered) {
  const commitment = createCommitment({
    promisor: agent,
    beneficiary: 'buyer',
    feeAmount: 0,
    exposureAmount: 1,
    bondAmount: 1, // fully bonded: the only regime this market writes
    verifier: { kind: 'attestation' },
    deadline: 100_000,
    nonce: `job-${nonce++}`,
  });
  market.open(commitment, { actor: agent });
  const covered = market.quote({
    commitmentId: commitment.commitmentId,
    underwriter: 'underwriter',
    coverageAmount: 1,
    premiumAmount: 1,
    expiresAt: 99_999,
  });
  market.bind(covered.quoteId, { actor: 'buyer' });
  market.settle(commitment.commitmentId, { delivered });
}

for (let i = 0; i < 150; i += 1) runJob('veteran', true);
for (let i = 0; i < 60; i += 1) runJob('flaky', i % 5 !== 0); // ~20% failure

const oracle = replayOracle(market.ledger);

console.log('\n' + LINE);
console.log('  What it costs to cover 1,000,000 of exposure on each agent');
console.log(LINE);
for (const agent of ['veteran', 'rookie', 'flaky']) {
  const { delivered, failed } = oracle.history(agent);
  const premium = oracle.fairPremium(agent, EXPOSURE);
  const rate = ((premium / EXPOSURE) * 10_000).toFixed(0);
  kv(
    agent,
    `${delivered}✓/${failed}✗  score ${(oracle.scoreBasisPoints(agent) / 100).toFixed(1)}%  ` +
      `premium ${premium.toLocaleString('en-US')} (${rate} bps)`,
  );
}

console.log(`
  Read the rookie's number carefully: the premium is LARGER than the cover.
  With no record the posterior is maximally wide, so an unknown agent is
  effectively uninsurable on someone else's capital — not because it is
  presumed dishonest, but because nobody knows anything yet.

  That is not a dead end, it is the on-ramp. The rookie posts its own bond and
  buys 'collateralized' cover, which is collusion-proof and therefore cheap to
  underwrite, until it has a record worth pricing. No application, no approval,
  no listing, no permission — just capital, and then history.

  The flaky agent is not banned either. It is simply expensive, by exactly the
  amount its own history implies.
`);

// A real policy, end to end.
console.log(LINE);
console.log('  One covered job, settled');
console.log(LINE);

const commitment = createCommitment({
  promisor: 'veteran',
  beneficiary: 'buyer',
  feeAmount: 10_000,
  exposureAmount: EXPOSURE,
  bondAmount: EXPOSURE,
  verifier: { kind: 'attestation' },
  deadline: 100_000,
  nonce: 'headline',
});
market.open(commitment, { actor: 'veteran' });

const premium = oracle.fairPremium('veteran', EXPOSURE - commitment.feeAmount);
const quote = market.quote({
  commitmentId: commitment.commitmentId,
  underwriter: 'underwriter',
  coverageAmount: EXPOSURE - commitment.feeAmount,
  premiumAmount: premium,
  expiresAt: 99_999,
});
market.bind(quote.quoteId, { actor: 'buyer' });

kv('cover', (EXPOSURE - commitment.feeAmount).toLocaleString('en-US'));
kv('premium', premium.toLocaleString('en-US'));
kv('regime', market.coverageRegime(commitment.commitmentId));
kv('underwriter at risk', market.exposureOf('underwriter').toLocaleString('en-US'));

const result = market.settle(commitment.commitmentId, { delivered: true, reason: 'shipped' });
kv('outcome', result.outcome.toUpperCase());
kv('underwriter at risk after', market.exposureOf('underwriter').toLocaleString('en-US'));

// The ledger is the whole state; check it has not been tampered with.
const integrity = market.ledger.verify();
console.log('\n' + LINE);
console.log('  Ledger + badge');
console.log(LINE);
kv('entries', market.ledger.length);
kv('chain valid', integrity.valid ? 'YES' : `NO (broken at ${integrity.brokenAt})`);

const badge = mintBadge(market.ledger, 'veteran', { exposure: EXPOSURE });
console.log('\n  ' + renderBadgeMarkdown(badge));
console.log('\n  SVG (paste anywhere, no external fetch):');
console.log('  ' + renderBadgeSVG(badge).slice(0, 96) + '…');
console.log('\n' + HEAVY + '\n');

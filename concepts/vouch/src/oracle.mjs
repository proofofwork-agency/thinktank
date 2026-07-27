// The trust oracle — the public good that falls out of the market.
//
// AMMs were built to swap tokens and produced a price oracle as a side effect.
// vouch is built to transfer risk and produces this as a side effect: a live,
// collateral-backed probability that any given agent delivers. Nobody has to
// run it or vote on it; it is a pure fold over settled outcomes.
//
// The estimator is a Beta-Bernoulli posterior with a Jeffreys prior. That
// choice does real work beyond statistical taste: an agent with no history
// gets a *wide* posterior, so the conservative quote an underwriter prices off
// is expensive. New agents are not assumed guilty, they are assumed unknown,
// and the cost of being unknown is exactly the cost of the uncertainty. That
// is what prices out adverse selection instead of trying to detect it.

import { priceFromProbability } from './units.mjs';

// Jeffreys prior Beta(1/2, 1/2), scaled to integers to keep the fold exact.
const PRIOR_ALPHA = 0.5;
const PRIOR_BETA = 0.5;

// ~97.7th percentile of the normal; underwriters quote off the upper tail.
const DEFAULT_Z = 2;

export function createTrustOracle() {
  /** @type {Map<string, {delivered: number, failed: number}>} */
  const history = new Map();

  function recordFor(agent) {
    let record = history.get(agent);
    if (!record) {
      record = { delivered: 0, failed: 0 };
      history.set(agent, record);
    }
    return record;
  }

  return Object.freeze({
    /** Fold one settled outcome in. Only settled outcomes count. */
    observe(agent, delivered) {
      if (typeof agent !== 'string' || agent.length === 0) {
        throw new TypeError('oracle.observe: agent must be a non-empty string');
      }
      if (typeof delivered !== 'boolean') {
        throw new TypeError('oracle.observe: delivered must be a boolean');
      }
      const record = recordFor(agent);
      if (delivered) record.delivered += 1;
      else record.failed += 1;
      return this;
    },

    history(agent) {
      const record = history.get(agent) ?? { delivered: 0, failed: 0 };
      return { delivered: record.delivered, failed: record.failed };
    },

    agents() {
      return [...history.keys()];
    },

    /**
     * Posterior distribution of this agent's failure probability.
     * Beta(alpha, beta) with alpha counting failures, beta counting deliveries.
     */
    posterior(agent) {
      const { delivered, failed } = this.history(agent);
      const alpha = failed + PRIOR_ALPHA;
      const beta = delivered + PRIOR_BETA;
      const n = alpha + beta;
      const mean = alpha / n;
      const variance = (alpha * beta) / (n * n * (n + 1));
      return { alpha, beta, mean, stdDev: Math.sqrt(variance), observations: delivered + failed };
    },

    /** Point estimate: posterior mean failure probability. */
    failureProbability(agent) {
      return this.posterior(agent).mean;
    },

    /**
     * Conservative failure probability an underwriter should quote off:
     * the upper end of the posterior. Wide posterior (no history) => high
     * number => expensive premium, which is the correct price of ignorance.
     */
    conservativeFailureProbability(agent, z = DEFAULT_Z) {
      const { mean, stdDev } = this.posterior(agent);
      return Math.min(1, Math.max(0, mean + z * stdDev));
    },

    /** Delivery score in basis points — the number a badge displays. */
    scoreBasisPoints(agent) {
      return Math.round((1 - this.conservativeFailureProbability(agent)) * 10_000);
    },

    /**
     * The reference premium for covering `exposure` on this agent.
     * Underwriters are free to quote anything; this is the anchor the market
     * converges toward, and the number that makes the oracle legible.
     */
    fairPremium(agent, exposure, loadBasisPoints = 1_000) {
      return priceFromProbability(
        exposure,
        this.conservativeFailureProbability(agent),
        loadBasisPoints,
      );
    },
  });
}

/**
 * Replay an oracle from settlement events, so any third party holding the
 * ledger derives the identical scores. This is the property that makes the
 * oracle a public good rather than a service somebody operates.
 */
export function replayOracle(ledger) {
  const oracle = createTrustOracle();
  for (const entry of ledger.byType('settled')) {
    // Only outcomes where capital was genuinely at risk count.
    //
    // Without this the whole premise collapses: an agent could open a hundred
    // self-dealt commitments with exposure=1, no bond and no policy, settle
    // them all "delivered" for free, and walk away with a 98% score and a
    // cheap quote on a million of real exposure. Reputation that costs nothing
    // to manufacture is not reputation. Requiring a bound policy means every
    // observation in this fold was one an underwriter staked collateral on and
    // a beneficiary paid a premium for.
    //
    // It also closes the mirror attack: you cannot grief a rival's score by
    // opening fake failing commitments in their name, because no underwriter
    // ever bound them.
    if (entry.payload.policyId === null || entry.payload.policyId === undefined) continue;
    oracle.observe(entry.payload.promisor, entry.payload.outcome === 'delivered');
  }
  return oracle;
}

// The market and the settlement engine.
//
// Three rules carry all the economic weight here; everything else is
// bookkeeping.
//
//   1. INDEMNITY, NOT WAGER. A payout is capped at the loss actually declared
//      and paid for, minus whatever escrow already returned. You cannot profit
//      from a failure, only be made whole. This is the line between insurance
//      and a prediction market, and it is why a beneficiary has no reason to
//      want the failure.
//
//   2. SUBROGATION. When the underwriter pays, it acquires the beneficiary's
//      claim against the promisor and recovers from the promisor's bond. This
//      is what makes deliberate failure expensive for the promisor rather than
//      free. Without it, a buyer and a seller can collude to drain underwriters.
//
//   3. NO REHYPOTHECATION. Locked collateral is locked. An underwriter cannot
//      pledge the same capital behind two promises, so headline coverage is
//      always backed by capital that exists.

import { Ledger } from './ledger.mjs';
import { commitmentIdOf } from './commitment.mjs';
import { OUTCOME, createAdapterRegistry } from './evidence.mjs';
import { addAmount, assertAmount, assertPositiveAmount, subAmount } from './units.mjs';
import { domainDigest } from './canonical.mjs';

export function createVouchMarket({
  adapters = [],
  ledger = new Ledger(),
  clock = 0,
  // Coverage beyond the promisor's bond is refused by default.
  //
  // Three independent lines of reasoning converge on this. Economically, the
  // collusion result only holds while coverage <= bond. Legally, a fully
  // bonded and subrogated guarantee — where the obligor funds its own payout
  // and the underwriter nets ~zero risk — is the weakest candidate for "third
  // party risk transfer", i.e. regulated insurance. Prudentially, pre-funded
  // cover answers the solvency question by construction rather than by
  // promising a balance sheet exists.
  //
  // The cost is real and worth naming: no leverage. An underwriter can only
  // cover what it has locked. That is narrower than the permissionless dream
  // and it is the version that survives all three lenses.
  allowReputational = false,
} = {}) {
  const registry = Array.isArray(adapters) ? createAdapterRegistry(adapters) : adapters;

  /** @type {Map<string, {available: number, locked: number}>} */
  const accounts = new Map();
  /** @type {Map<string, object>} */
  const commitments = new Map();
  /** @type {Map<string, object>} */
  const quotes = new Map();
  /** @type {Map<string, object>} */
  const policies = new Map();
  /** @type {Set<string>} */
  const settled = new Set();

  let now = clock;

  function account(party) {
    let acct = accounts.get(party);
    if (!acct) {
      acct = { available: 0, locked: 0 };
      accounts.set(party, acct);
    }
    return acct;
  }

  function lock(party, amount) {
    const acct = account(party);
    if (acct.available < amount) {
      throw new Error(
        `insufficient collateral for ${party}: needs ${amount}, has ${acct.available} available`,
      );
    }
    acct.available = subAmount(acct.available, amount);
    acct.locked = addAmount(acct.locked, amount);
  }

  function unlock(party, amount) {
    const acct = account(party);
    if (acct.locked < amount) throw new Error(`cannot unlock ${amount} for ${party}: only ${acct.locked} locked`);
    acct.locked = subAmount(acct.locked, amount);
    acct.available = addAmount(acct.available, amount);
  }

  /** Move locked capital out of one party and into another's available balance. */
  function payFromLocked(from, to, amount) {
    if (amount === 0) return;
    const src = account(from);
    if (src.locked < amount) throw new Error(`cannot pay ${amount} from ${from}: only ${src.locked} locked`);
    src.locked = subAmount(src.locked, amount);
    const dst = account(to);
    dst.available = addAmount(dst.available, amount);
  }

  function transfer(from, to, amount) {
    if (amount === 0) return;
    const src = account(from);
    if (src.available < amount) {
      throw new Error(`insufficient balance for ${from}: needs ${amount}, has ${src.available}`);
    }
    src.available = subAmount(src.available, amount);
    const dst = account(to);
    dst.available = addAmount(dst.available, amount);
  }

  const market = {
    ledger,

    get time() {
      return now;
    },

    advanceTo(t) {
      if (!Number.isSafeInteger(t) || t < now) throw new TypeError('advanceTo: time must move forward');
      now = t;
      return market;
    },

    /** Fund a party's collateral account. */
    deposit(party, amount) {
      assertPositiveAmount(amount, 'deposit amount');
      const acct = account(party);
      acct.available = addAmount(acct.available, amount);
      ledger.append('deposit', { party, amount });
      return market;
    },

    balance(party) {
      const acct = account(party);
      return { available: acct.available, locked: acct.locked, total: acct.available + acct.locked };
    },

    /**
     * Register a commitment and lock the promisor's bond.
     *
     * The bond is the promisor's own skin in the game. It is what subrogation
     * recovers against, so it is also what determines whether coverage is
     * collusion-proof (see `coverageRegime`).
     */
    open(commitment, { actor } = {}) {
      if (commitmentIdOf(commitment) !== commitment.commitmentId) {
        throw new Error('open: commitmentId does not match its contents');
      }
      // Authorization is modelled as an explicit actor. Without it anyone could
      // open a commitment naming a victim as promisor, lock the victim's bond,
      // attest failure, and confiscate it. Production replaces this with a
      // signature over the commitment id; the check is the same shape.
      if (actor !== commitment.promisor) {
        throw new Error(
          `open: must be authorized by the promisor (${commitment.promisor}), got ${String(actor)}`,
        );
      }
      if (commitments.has(commitment.commitmentId)) {
        throw new Error(`open: commitment ${commitment.commitmentId} already open`);
      }
      if (commitment.deadline <= now) throw new Error('open: deadline is already in the past');

      if (commitment.bondAmount > 0) lock(commitment.promisor, commitment.bondAmount);
      commitments.set(commitment.commitmentId, commitment);
      ledger.append('opened', {
        commitmentId: commitment.commitmentId,
        promisor: commitment.promisor,
        beneficiary: commitment.beneficiary,
        exposureAmount: commitment.exposureAmount,
        bondAmount: commitment.bondAmount,
      });
      return commitment.commitmentId;
    },

    /**
     * An underwriter offers cover. Anyone may quote on anyone: this is the
     * gatekeeper that falls. No licence, no listing, no relationship with the
     * promisor is required.
     */
    quote({ commitmentId, underwriter, coverageAmount, premiumAmount, expiresAt }) {
      const commitment = commitments.get(commitmentId);
      if (!commitment) throw new Error(`quote: unknown commitment ${commitmentId}`);

      assertPositiveAmount(coverageAmount, 'coverageAmount');
      // A zero premium makes the collusion result false: the colluding pair
      // ends flat instead of down, so "strictly unprofitable" stops holding.
      assertPositiveAmount(premiumAmount, 'premiumAmount');
      if (typeof underwriter !== 'string' || underwriter.length === 0) {
        throw new TypeError('quote: underwriter must be a non-empty party id');
      }
      if (underwriter === commitment.promisor) {
        // Self-underwriting collapses the three roles into two: subrogation
        // moves value from the promisor back to itself, so the premium never
        // actually leaves the colluding pair. A promisor backing its own
        // promise is a bond, and bondAmount is where that belongs.
        throw new Error('quote: promisor cannot underwrite its own commitment; post a bond instead');
      }
      // Over-insurance turns indemnity back into a wager, so it is refused.
      if (coverageAmount > commitment.exposureAmount) {
        throw new Error(
          `quote: coverage ${coverageAmount} exceeds declared exposure ${commitment.exposureAmount}`,
        );
      }
      if (underwriter === commitment.beneficiary) {
        // The beneficiary insuring itself is a no-op that would only serve to
        // manufacture a fake premium print in the oracle.
        throw new Error('quote: beneficiary cannot underwrite its own commitment');
      }
      if (!Number.isSafeInteger(expiresAt) || expiresAt <= now) {
        throw new TypeError('quote: expiresAt must be a future logical time');
      }

      // Checked last, so the specific validation errors above stay the ones a
      // caller sees first.
      if (!allowReputational && coverageAmount > commitment.bondAmount) {
        throw new Error(
          `quote: coverage ${coverageAmount} exceeds the promisor bond ${commitment.bondAmount}; ` +
            'this market only writes fully collateralized cover. ' +
            'Raise the bond, or construct the market with allowReputational: true and accept the collusion exposure.',
        );
      }

      const quoteId = domainDigest('quote', {
        commitmentId,
        underwriter,
        coverageAmount,
        premiumAmount,
        expiresAt,
        seq: ledger.length,
      });
      const quote = Object.freeze({
        quoteId,
        commitmentId,
        underwriter,
        coverageAmount,
        premiumAmount,
        expiresAt,
      });
      quotes.set(quoteId, quote);
      ledger.append('quoted', { ...quote });
      return quote;
    },

    /**
     * The beneficiary accepts a quote. Only now is collateral locked, which is
     * what stops quote-spam from griefing an underwriter's balance sheet.
     */
    bind(quoteId, { actor } = {}) {
      const quote = quotes.get(quoteId);
      if (!quote) throw new Error(`bind: unknown quote ${quoteId}`);
      if (quote.expiresAt <= now) throw new Error(`bind: quote ${quoteId} expired at ${quote.expiresAt}`);

      const commitment = commitments.get(quote.commitmentId);
      // Only the beneficiary pays for cover. Otherwise anyone could bind an
      // arbitrarily expensive quote against a victim's balance and drain it
      // straight into a colluding underwriter.
      if (actor !== commitment.beneficiary) {
        throw new Error(
          `bind: must be accepted by the beneficiary (${commitment.beneficiary}), got ${String(actor)}`,
        );
      }
      if (policies.has(quote.commitmentId)) {
        throw new Error(`bind: commitment ${quote.commitmentId} already covered`);
      }
      if (settled.has(quote.commitmentId)) throw new Error('bind: commitment already settled');

      // Preflight both legs before moving anything. Locking first and then
      // discovering the beneficiary cannot pay strands the underwriter's
      // collateral with no policy to release it.
      if (account(quote.underwriter).available < quote.coverageAmount) {
        throw new Error(
          `insufficient collateral for ${quote.underwriter}: needs ${quote.coverageAmount}, has ${account(quote.underwriter).available} available`,
        );
      }
      if (account(commitment.beneficiary).available < quote.premiumAmount) {
        throw new Error(
          `insufficient balance for ${commitment.beneficiary}: needs ${quote.premiumAmount}, has ${account(commitment.beneficiary).available}`,
        );
      }

      lock(quote.underwriter, quote.coverageAmount);
      transfer(commitment.beneficiary, quote.underwriter, quote.premiumAmount);

      const policy = Object.freeze({
        policyId: domainDigest('policy', { quoteId, boundAt: now }),
        commitmentId: quote.commitmentId,
        underwriter: quote.underwriter,
        coverageAmount: quote.coverageAmount,
        premiumAmount: quote.premiumAmount,
        boundAt: now,
      });
      policies.set(quote.commitmentId, policy);
      ledger.append('bound', { ...policy });
      return policy;
    },

    /**
     * Whether this commitment's cover is fully backed by the promisor's own
     * bond. In the `collateralized` regime, subrogation recovers the entire
     * payout from the promisor, so a colluding buyer/seller pair strictly
     * loses money — see test/attacks.test.mjs for the proof.
     */
    coverageRegime(commitmentId) {
      const commitment = commitments.get(commitmentId);
      const policy = policies.get(commitmentId);
      if (!commitment || !policy) return null;
      return policy.coverageAmount <= commitment.bondAmount ? 'collateralized' : 'reputational';
    },

    /**
     * Settle against evidence.
     *
     * `recovered` is what the beneficiary already got back from escrow. It
     * defaults to the fee, because DeliveryProof refunds the fee on a failing
     * verdict, and paying it a second time here would be double recovery — the
     * exact leak that makes collusion profitable.
     */
    settle(commitmentId, evidence) {
      const commitment = commitments.get(commitmentId);
      if (!commitment) throw new Error(`settle: unknown commitment ${commitmentId}`);
      if (settled.has(commitmentId)) throw new Error(`settle: ${commitmentId} already settled`);

      const adapter = registry.resolve(commitment.verifier.kind);
      const { outcome, reason } = adapter.decide(commitment, evidence);

      const policy = policies.get(commitmentId) ?? null;
      let payout = 0;
      let subrogated = 0;

      if (outcome === OUTCOME.DELIVERED) {
        if (policy) unlock(policy.underwriter, policy.coverageAmount);
        if (commitment.bondAmount > 0) unlock(commitment.promisor, commitment.bondAmount);
      } else {
        // Recovery is derived from the commitment, never supplied by whoever
        // calls settle. As a caller parameter it was a hole straight through
        // rule 1: passing recovered=0 on a fully-refunded job manufactures a
        // residual loss that does not exist and confiscates the bond for it.
        const alreadyRecovered = commitment.feeAmount;

        // Rule 1: indemnity, capped at the unrecovered part of declared loss.
        const residualLoss = Math.max(0, commitment.exposureAmount - alreadyRecovered);

        if (policy) {
          payout = Math.min(policy.coverageAmount, residualLoss);
          payFromLocked(policy.underwriter, commitment.beneficiary, payout);
          unlock(policy.underwriter, subAmount(policy.coverageAmount, payout));

          // Rule 2: subrogation. The underwriter steps into the beneficiary's
          // shoes and recovers from the bond it just made good on.
          subrogated = Math.min(payout, commitment.bondAmount);
          payFromLocked(commitment.promisor, policy.underwriter, subrogated);
          unlock(commitment.promisor, subAmount(commitment.bondAmount, subrogated));
        } else if (commitment.bondAmount > 0) {
          // Uninsured: the bond still answers to the beneficiary directly.
          const direct = Math.min(commitment.bondAmount, residualLoss);
          payFromLocked(commitment.promisor, commitment.beneficiary, direct);
          unlock(commitment.promisor, subAmount(commitment.bondAmount, direct));
        }
      }

      settled.add(commitmentId);
      const record = {
        commitmentId,
        promisor: commitment.promisor,
        beneficiary: commitment.beneficiary,
        outcome,
        reason,
        payout,
        subrogated,
        policyId: policy?.policyId ?? null,
        underwriter: policy?.underwriter ?? null,
        premiumAmount: policy?.premiumAmount ?? 0,
      };
      ledger.append('settled', record);
      return Object.freeze(record);
    },

    commitment(id) {
      return commitments.get(id) ?? null;
    },

    policy(id) {
      return policies.get(id) ?? null;
    },

    /** Total capital an underwriter has at risk right now. */
    exposureOf(underwriter) {
      return account(underwriter).locked;
    },
  };

  return market;
}

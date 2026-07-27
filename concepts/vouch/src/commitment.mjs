// The commitment: a promise someone else can underwrite.
//
// Note the two separate amounts. `feeAmount` is what the beneficiary pays the
// promisor for the work; escrow (DeliveryProof) already governs that. What
// vouch insures is `exposureAmount`: the beneficiary's *consequential* loss if
// the work does not arrive. Refunding a $5 API fee is not a remedy when the
// missed call cost $5,000. Those are different numbers and only the second one
// is a risk anybody needs to buy.

import { domainDigest } from './canonical.mjs';
import { assertAmount, assertPositiveAmount } from './units.mjs';

/**
 * Create a commitment.
 *
 * `exposureAmount` is declared ex ante and the premium is priced on it. That
 * ordering is deliberate: a beneficiary who inflates their exposure pays for
 * the inflation up front, and one who understates it is underpaid at
 * settlement. Loss cannot be re-valued after the fact, which is what stops
 * "declare the loss once you know you're collecting".
 */
export function createCommitment({
  promisor,
  beneficiary,
  feeAmount,
  exposureAmount,
  bondAmount = 0,
  verifier,
  deadline,
  nonce,
}) {
  assertParty(promisor, 'promisor');
  assertParty(beneficiary, 'beneficiary');

  if (promisor === beneficiary) {
    // Otherwise a single party could manufacture loss against itself and
    // harvest an underwriter's collateral with no counterparty at all.
    throw new TypeError('commitment: promisor and beneficiary must be distinct parties');
  }

  assertAmount(feeAmount, 'feeAmount');
  assertPositiveAmount(exposureAmount, 'exposureAmount');
  assertAmount(bondAmount, 'bondAmount');

  if (!verifier || typeof verifier !== 'object' || typeof verifier.kind !== 'string') {
    throw new TypeError('commitment: verifier must be an object with a string kind');
  }
  if (!Number.isSafeInteger(deadline)) {
    throw new TypeError('commitment: deadline must be a safe integer logical time');
  }
  if (typeof nonce !== 'string' || nonce.length === 0) {
    throw new TypeError('commitment: nonce must be a non-empty string');
  }

  const body = {
    promisor,
    beneficiary,
    feeAmount,
    exposureAmount,
    bondAmount,
    verifier: Object.freeze({ ...verifier }),
    deadline,
    nonce,
  };

  return Object.freeze({ ...body, commitmentId: domainDigest('commitment', body) });
}

function assertParty(value, label) {
  if (typeof value !== 'string' || value.length === 0) {
    throw new TypeError(`commitment: ${label} must be a non-empty party id`);
  }
}

/** Recompute a commitment id, for third parties checking one they were handed. */
export function commitmentIdOf(commitment) {
  const {
    promisor,
    beneficiary,
    feeAmount,
    exposureAmount,
    bondAmount,
    verifier,
    deadline,
    nonce,
  } = commitment;
  return domainDigest('commitment', {
    promisor,
    beneficiary,
    feeAmount,
    exposureAmount,
    bondAmount,
    verifier,
    deadline,
    nonce,
  });
}

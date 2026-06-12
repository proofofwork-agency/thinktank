// src/verifiers/hash.mjs
// Tier A verifier: the delivered output must hash to a pre-agreed expected hash.
//
// predicate.params = { expectedHash: <lowercase hex sha256 of the agreed output> }
//
// This is the strongest possible binding when the buyer already knows exactly what
// bytes they want: ok iff sha256hex(evidence.output) === expectedHash. Fully objective,
// no third-party trust (Tier A).

import { sha256hex } from '../protocol/canonical.mjs';
import { checkedAt } from '../protocol/runtime.mjs';

/** @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('../protocol/types.mjs').DeliveryEvidence} DeliveryEvidence */
/** @typedef {import('../protocol/types.mjs').Verdict} Verdict */

const NAME = 'hash';
const TIER = 'A';

/**
 * @type {import('../protocol/types.mjs').Verifier}
 */
export const hashVerifier = {
  name: NAME,
  tier: TIER,
  /**
   * @param {DeliveryContract} contract
   * @param {DeliveryEvidence} evidence
   * @returns {Verdict}
   */
  verify(contract, evidence, opts = {}) {
    const at = checkedAt(opts);
    const expectedHash = contract?.predicate?.params?.expectedHash;
    if (typeof expectedHash !== 'string' || expectedHash.length === 0) {
      return {
        ok: false,
        tier: TIER,
        verifier: NAME,
        reason: 'contract.predicate.params.expectedHash (hex string) is required for the hash verifier',
        checkedAt: at,
      };
    }
    const actualHash = sha256hex(evidence?.output);
    const expected = expectedHash.toLowerCase();
    if (actualHash !== expected) {
      return {
        ok: false,
        tier: TIER,
        verifier: NAME,
        reason: `output hash mismatch: expected ${expected}, got ${actualHash}`,
        checkedAt: at,
      };
    }
    return {
      ok: true,
      tier: TIER,
      verifier: NAME,
      reason: `output hash matches expected (${actualHash})`,
      checkedAt: at,
    };
  },
};

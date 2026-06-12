// src/verifiers/testsuite.mjs
// Tier A verifier (the strongest "objective replay" verifier).
//
// The verifier RE-EXECUTES a reference computation from the contract predicate and
// deep-equals the result against the delivered output. Since v0.4, replay runs in
// a worker thread with wall-clock timeout and V8 resource limits. This bounds the
// verifier's own deterministic replay work; it is not a sandbox for arbitrary
// seller JavaScript.
//
// predicate.params = {
//   op: 'sort'|'sum'|'unique'|'reverse',
//   input: any,
//   timeoutMs?: number,
//   maxInputBytes?: number,
//   maxDepth?: number
// }
//   sort    -> ascending sort of a numeric/comparable array (stable, by value)
//   sum     -> numeric sum of an array of numbers
//   unique  -> de-duplicated array preserving first-seen order
//   reverse -> reversed array

import { runTestsuiteReplay } from './testsuite-runner.mjs';
import { checkedAt } from '../protocol/runtime.mjs';

/** @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('../protocol/types.mjs').DeliveryEvidence} DeliveryEvidence */
/** @typedef {import('../protocol/types.mjs').Verdict} Verdict */

const NAME = 'testsuite';
const TIER = 'A';

/**
 * @type {import('../protocol/types.mjs').Verifier}
 */
export const testsuiteVerifier = {
  name: NAME,
  tier: TIER,
  /**
   * @param {DeliveryContract} contract
   * @param {DeliveryEvidence} evidence
   * @returns {Promise<Verdict>}
   */
  async verify(contract, evidence, opts = {}) {
    const at = checkedAt(opts);
    const params = contract?.predicate?.params;
    const op = params?.op;
    if (typeof op !== 'string') {
      return {
        ok: false,
        tier: TIER,
        verifier: NAME,
        reason: 'contract.predicate.params.op (string) is required for the testsuite verifier',
        checkedAt: at,
      };
    }

    let result;
    try {
      result = await runTestsuiteReplay(
        { op, input: params.input, actual: evidence?.output },
        {
          timeoutMs: params.timeoutMs,
          maxInputBytes: params.maxInputBytes,
          maxDepth: params.maxDepth,
        },
      );
    } catch (err) {
      return {
        ok: false,
        tier: TIER,
        verifier: NAME,
        reason: `testsuite sandbox failed: ${err instanceof Error ? err.message : String(err)}`,
        checkedAt: at,
      };
    }

    if (!result.ok) {
      return {
        ok: false,
        tier: TIER,
        verifier: NAME,
        reason: `could not compute reference result: ${result.reason}`,
        checkedAt: at,
      };
    }

    if (result.matched) {
      return {
        ok: true,
        tier: TIER,
        verifier: NAME,
        reason: `re-executed op "${op}" in a bounded worker and output matched the reference result`,
        checkedAt: at,
      };
    }
    return {
      ok: false,
      tier: TIER,
      verifier: NAME,
      reason: `re-executed op "${op}" in a bounded worker: output ${JSON.stringify(evidence?.output)} != reference ${JSON.stringify(result.expected)}`,
      checkedAt: at,
    };
  },
};

// src/reason.mjs
// DeliveryProof receipt -> ERC-8183 evaluator call (action + jobId + reason word).
//
// SCOPE / HONESTY: pure projection. NO contracts, NO wallet, NO provider/RPC URL,
// NO private keys, NO on-chain submission. This is the single place the rail turns
// a settled DeliveryProof receipt into the two pieces of ERC-8183 evaluator input
// it needs — the verb (complete=release / reject=refund) and the attestation
// `reason` word (a receipt digest, sha256 by default or keccak256 for an EVM-native
// bytes32). It delegates entirely to core's toErc8183EvaluatorResult, which itself
// refuses to project an internally contradictory receipt (decision vs verdict.ok).
// It does NOT authenticate the receipt: the rail still verifyReceipt()s against the
// settlement key before any transition. TESTNET / LOCAL ONLY — no mainnet, no real
// funds, no autonomous live tx.

import { toErc8183EvaluatorResult } from 'deliveryproof';

/** @typedef {import('deliveryproof').DeliveryReceipt} DeliveryReceipt */

/**
 * Project a settled DeliveryProof receipt onto the ERC-8183 evaluator call the
 * rail will dispatch for `jobId`.
 *
 *   receipt.decision === 'release' -> { action: 'complete', ... }  (release escrow)
 *   receipt.decision === 'refund'  -> { action: 'reject',   ... }  (refund client)
 *   reason = '0x<digest(receipt)>'  (sha256 by default; keccak256 when requested)
 *
 * The `jobId` argument is authoritative: the rail resolved it from the on-chain job
 * the hold attached to, so it is passed through to core (which would otherwise fall
 * back to receipt.contractId). We always coerce it to a string for a stable call.
 *
 * @param {DeliveryReceipt} receipt   A settled, decision-bearing DeliveryProof receipt.
 * @param {string|number|bigint} jobId The ERC-8183 job id this receipt settles.
 * @param {{ hashAlg?: 'sha256'|'keccak256' }} [opts] Reason digest algorithm.
 * @returns {{ action: 'complete'|'reject', jobId: string, reason: string }}
 *   The evaluator verb, the (stringified) job id, and the 0x-prefixed reason word.
 *   The core result's hashAlg is intentionally dropped here: the contract takes a
 *   single bytes32 reason and the rail records hashAlg separately if it audits it.
 */
export function deliveryReceiptToEvaluatorCall(receipt, jobId, opts) {
  const result = toErc8183EvaluatorResult(receipt, {
    jobId,
    hashAlg: opts?.hashAlg,
  });
  return {
    action: result.action,
    jobId: result.jobId,
    reason: result.reason,
  };
}

// src/interop/erc8183.mjs
// THIN interop export: DeliveryReceipt -> ERC-8183 evaluator decision.
//
// ERC-8183 ("Agentic Commerce") standardizes a Job with escrowed budget and three
// roles — Client, Provider, Evaluator — where ONLY the evaluator may call
// `complete(jobId)` (release escrow) or `reject(jobId)` (refund). The spec
// deliberately treats the Evaluator as "any address capable of calling
// complete or reject" and leaves the verification METHOD undefined; `reason` is an
// optional attestation hash.
//
// DeliveryProof is a concrete, deep, objective Evaluator for that slot: its
// settlement decision (release/refund) maps one-to-one onto complete/reject, and
// its signed receipt provides the attestation `reason`.
//
// SCOPE / HONESTY: pure projection. NO contracts, NO wallet, NO provider/RPC URL,
// NO private keys, and NO on-chain submission. SHA-256 remains the default for
// backward compatibility; opt-in keccak256 mode emits an EVM-native digest word
// and ABI-encoded argument bytes only.

import { canonicalize, sha256hex } from '../protocol/canonical.mjs';
import { keccak256 } from '../protocol/keccak.mjs';
import { encodeAbiParameters } from './abi.mjs';

/** @typedef {import('../protocol/types.mjs').DeliveryReceipt} DeliveryReceipt */

/**
 * Project a DeliveryReceipt onto an ERC-8183 evaluator decision.
 *
 * Mapping:
 *   action = receipt.decision === 'release' ? 'complete' : 'reject'
 *   jobId  = opts.jobId ?? receipt.contractId   (8183 keys by jobId; we pass it through)
 *   reason = 0x<sha256(receipt)>                 (optional attestation hash)
 *
 * @param {DeliveryReceipt} receipt
 * @param {{ jobId?: string, hashAlg?: 'sha256'|'keccak256', includeAbi?: boolean }} [opts]
 * @returns {{ action: 'complete'|'reject', jobId: string, reason: string, hashAlg: string, abi?: Object }}
 */
export function toErc8183EvaluatorResult(receipt, opts = {}) {
  if (!receipt || typeof receipt !== 'object' || typeof receipt.decision !== 'string') {
    throw new TypeError('toErc8183EvaluatorResult: a DeliveryReceipt with a decision is required');
  }
  assertReceiptConsistentForInterop(receipt, 'toErc8183EvaluatorResult');
  const action = receipt.decision === 'release' ? 'complete' : 'reject';
  const jobId = opts.jobId != null ? String(opts.jobId) : String(receipt.contractId ?? '');
  const hashAlg = normalizeHashAlg(opts.hashAlg);
  const result = {
    action,
    jobId,
    reason: `0x${hashInteropValue(receipt, hashAlg)}`,
    hashAlg,
  };
  if (opts.includeAbi === true) {
    result.abi = {
      signature: 'DeliveryProofEvaluatorResult(string,string,bytes32)',
      types: ERC8183_RESULT_TYPES,
      encodedArgs: encodeErc8183EvaluatorAbi(result),
    };
  }
  return result;
}

const ERC8183_RESULT_TYPES = Object.freeze(['string', 'string', 'bytes32']);

/**
 * Encode the ERC-8183 evaluator projection as ABI tuple bytes.
 *
 * This is not ERC-8183 calldata and has no selector. A production adapter still
 * owns the real contract ABI, signer, provider, and submission policy.
 *
 * @param {{ action:string, jobId:string, reason:string }} result
 * @returns {string}
 */
export function encodeErc8183EvaluatorAbi(result) {
  return encodeAbiParameters(ERC8183_RESULT_TYPES, [
    result.action,
    result.jobId,
    result.reason,
  ]);
}

function normalizeHashAlg(hashAlg) {
  if (hashAlg === undefined || hashAlg === 'sha256') return 'sha256';
  if (hashAlg === 'keccak256') return 'keccak256';
  throw new TypeError('unsupported ERC-8183 hashAlg');
}

function hashInteropValue(value, hashAlg) {
  if (hashAlg === 'sha256') return sha256hex(value);
  if (hashAlg === 'keccak256') return keccak256(canonicalize(value));
  throw new TypeError('unsupported ERC-8183 hashAlg');
}

/**
 * Refuse to project an internally contradictory receipt onto a chain-facing
 * evaluator decision. A receipt whose decision disagrees with verdict.ok (e.g.
 * decision='release' with verdict.ok=false) must never become an ERC-8183
 * complete()/reject() projection. This is a CONSISTENCY gate, not authentication:
 * a caller posting on-chain should still verifyReceipt() against the settlement
 * key first. It fires only when BOTH fields are present and they contradict.
 * @param {{ decision?: string, verdict?: { ok?: boolean } }} receipt
 * @param {string} fn
 */
function assertReceiptConsistentForInterop(receipt, fn) {
  const ok = receipt && receipt.verdict ? receipt.verdict.ok : undefined;
  const decision = receipt ? receipt.decision : undefined;
  if (typeof ok === 'boolean' && typeof decision === 'string') {
    const expected = ok ? 'release' : 'refund';
    if (decision !== expected) {
      throw new TypeError(`${fn}: receipt.decision '${decision}' contradicts verdict.ok=${ok} (expected '${expected}')`);
    }
  }
}

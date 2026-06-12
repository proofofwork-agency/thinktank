// src/interop/erc8004.mjs
// THIN interop export: DeliveryReceipt -> ERC-8004 ValidationRegistry payload.
//
// ERC-8004 ("Trustless Agents") standardizes WHERE a validation verdict is
// anchored on-chain, but deliberately leaves HOW correctness is judged
// undefined — its ValidationRegistry just records a score + hashes + a tag:
//
//   validationResponse(bytes32 requestHash, uint8 response,
//                      string responseURI, bytes32 responseHash, string tag)
//   "response is 0..100, usable as binary (0 failed / 100 passed) or a spectrum"
//
// DeliveryProof is exactly the missing piece: the DEEP, objective verdict that
// fills that undefined evaluator slot. This module maps a signed DeliveryReceipt
// onto the ValidationRegistry call SHAPE so a DeliveryProof verdict can be posted
// as ERC-8004 validation evidence.
//
// SCOPE / HONESTY: this is a pure payload PROJECTION. There are NO contracts,
// NO wallet, NO chain calls, NO private keys, and NO on-chain submission here.
// SHA-256 remains the default for backward compatibility. Opt-in keccak256 mode
// emits EVM-native digest words and ABI-encoded argument bytes only.

import { canonicalize, sha256hex } from '../protocol/canonical.mjs';
import { keccak256 } from '../protocol/keccak.mjs';
import { encodeAbiParameters } from './abi.mjs';

/** @typedef {import('../protocol/types.mjs').DeliveryReceipt} DeliveryReceipt */

/**
 * Present a 64-char sha256 hex digest as an EVM-style 0x-prefixed 32-byte word.
 * (Structural only — see the hashAlg note above.)
 * @param {string} hex
 * @returns {string}
 */
function as0x(hex) {
  return hex.startsWith('0x') ? hex : `0x${hex}`;
}

const ERC8004_VALIDATION_TYPES = Object.freeze(['bytes32', 'uint8', 'string', 'bytes32', 'string']);

/**
 * Project a DeliveryReceipt onto ERC-8004 ValidationRegistry.validationResponse args.
 *
 * Mapping:
 *   requestHash  = receipt.contractHash         (identifies the validated work)
 *   response     = receipt.verdict.ok ? 100 : 0 (binary pass/fail on the 0..100 scale)
 *   responseHash = sha256(receipt)              (the signed receipt IS the evidence)
 *   responseURI  = opts.responseURI ?? ''       (optional off-chain evidence pointer)
 *   tag          = `deliveryproof/<verifier>/tier-<tier>`
 *
 * @param {DeliveryReceipt} receipt
 * @param {{ responseURI?: string, hashAlg?: 'sha256'|'keccak256', includeAbi?: boolean }} [opts]
 * @returns {{
 *   requestHash: string, response: number, responseURI: string,
 *   responseHash: string, tag: string, hashAlg: string, abi?: Object
 * }}
 */
export function toErc8004ValidationPayload(receipt, opts = {}) {
  if (!receipt || typeof receipt !== 'object' || !receipt.verdict) {
    throw new TypeError('toErc8004ValidationPayload: a DeliveryReceipt with a verdict is required');
  }
  assertReceiptConsistentForInterop(receipt, 'toErc8004ValidationPayload');
  const response = receipt.verdict.ok === true ? 100 : 0;
  const tier = receipt.verdict.tier ?? '?';
  const verifier = receipt.verdict.verifier ?? 'unknown';
  const hashAlg = normalizeHashAlg(opts.hashAlg);
  const payload = {
    requestHash: as0x(hashInteropValue(receipt.contractHash, hashAlg)),
    response,
    responseURI: typeof opts.responseURI === 'string' ? opts.responseURI : '',
    responseHash: as0x(hashInteropValue(receipt, hashAlg)),
    tag: `deliveryproof/${verifier}/tier-${tier}`,
    hashAlg,
  };
  if (opts.includeAbi === true) {
    payload.abi = {
      signature: 'validationResponse(bytes32,uint8,string,bytes32,string)',
      types: ERC8004_VALIDATION_TYPES,
      encodedArgs: encodeErc8004ValidationAbi(payload),
    };
  }
  return payload;
}

/**
 * Encode the ERC-8004 projection arguments as Ethereum ABI bytes.
 *
 * This is argument encoding only, not calldata: no selector, no provider, no
 * signer, and no submission helper.
 *
 * @param {{ requestHash:string, response:number, responseURI:string, responseHash:string, tag:string }} payload
 * @returns {string}
 */
export function encodeErc8004ValidationAbi(payload) {
  return encodeAbiParameters(ERC8004_VALIDATION_TYPES, [
    payload.requestHash,
    payload.response,
    payload.responseURI,
    payload.responseHash,
    payload.tag,
  ]);
}

function normalizeHashAlg(hashAlg) {
  if (hashAlg === undefined || hashAlg === 'sha256') return 'sha256';
  if (hashAlg === 'keccak256') return 'keccak256';
  throw new TypeError('unsupported ERC-8004 hashAlg');
}

function hashInteropValue(value, hashAlg) {
  if (hashAlg === 'sha256') return typeof value === 'string' ? value : sha256hex(value);
  if (hashAlg === 'keccak256') return keccak256(typeof value === 'string' ? value : canonicalize(value));
  throw new TypeError('unsupported ERC-8004 hashAlg');
}

/**
 * Refuse to project an internally contradictory receipt onto a chain-facing
 * payload. A receipt whose decision disagrees with verdict.ok (e.g.
 * decision='release' with verdict.ok=false) must never become an ERC-8004
 * success/failure projection. This is a CONSISTENCY gate, not authentication:
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

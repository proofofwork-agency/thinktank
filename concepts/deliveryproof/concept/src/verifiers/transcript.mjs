// src/verifiers/transcript.mjs
// Tier A verifier: a nonce-bound, Ed25519-signed transcript of the delivery.
//
// The seller (or an attesting party) signs a canonical statement binding the
// contract id, the contract nonce, and the output hash:
//
//   message = canonicalize({ contractId, nonce, outputHash })
//
// evidence.attestations[0] = { signerKeyId, publicKey (PEM), signature (base64) }
// contract.predicate.params.allowedSignerKeyIds may list accepted signer key ids;
// if omitted, the contracted seller key id is the only accepted signer.
//
// The verdict is ok iff:
//   1) outputHash in the signed statement === sha256hex(evidence.output)   (output binding)
//   2) the signed statement nonce === contract.nonce                       (replay binding)
//   3) the Ed25519 signature verifies over the canonical statement         (authenticity)
//   4) the signer is the contracted seller or explicitly allowed attester  (identity)
//
// This is Tier A because the check is purely cryptographic over data the protocol
// already holds: the signature is verified locally against the provided public key.
// Trusting that the contract's seller/allowed signer ids are the right identity is
// still a predicate-authorship trust point, but the verifier enforces that binding.

import { canonicalize, sha256hex } from '../protocol/canonical.mjs';
import { verify as verifySig, keyId } from '../protocol/crypto.mjs';
import { checkedAt } from '../protocol/runtime.mjs';

/** @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('../protocol/types.mjs').DeliveryEvidence} DeliveryEvidence */
/** @typedef {import('../protocol/types.mjs').Verdict} Verdict */

const NAME = 'transcript';
const TIER = 'A';

/**
 * @type {import('../protocol/types.mjs').Verifier}
 */
export const transcriptVerifier = {
  name: NAME,
  tier: TIER,
  /**
   * @param {DeliveryContract} contract
   * @param {DeliveryEvidence} evidence
   * @returns {Verdict}
   */
  verify(contract, evidence, opts = {}) {
    const at = checkedAt(opts);

    const attestations = evidence?.attestations;
    if (!Array.isArray(attestations) || attestations.length === 0) {
      return fail('evidence.attestations[0] is required for the transcript verifier', at);
    }
    const att = attestations[0];
    if (!att || typeof att !== 'object') {
      return fail('evidence.attestations[0] is not an object', at);
    }
    const { publicKey, signature, signerKeyId } = att;
    if (typeof publicKey !== 'string' || publicKey.length === 0) {
      return fail('attestation is missing publicKey (PEM)', at);
    }
    if (typeof signature !== 'string' || signature.length === 0) {
      return fail('attestation is missing signature (base64)', at);
    }

    // (1) Output binding: the statement must commit to THIS output.
    const outputHash = sha256hex(evidence?.output);

    // (2) Replay binding: the statement is bound to the contract nonce.
    const nonce = contract?.nonce;
    if (typeof nonce !== 'string' || nonce.length === 0) {
      return fail('contract.nonce is required to bind the transcript', at);
    }

    const derivedSignerKeyId = keyId(publicKey);

    // If the attestation advertises a signerKeyId, it must match the supplied key.
    if (signerKeyId !== undefined) {
      if (signerKeyId !== derivedSignerKeyId) {
        return fail(
          `attestation signerKeyId ${signerKeyId} does not match its publicKey (keyId ${derivedSignerKeyId})`,
          at,
        );
      }
    }

    const allowedSignerKeyIds = Array.isArray(contract?.predicate?.params?.allowedSignerKeyIds)
      && contract.predicate.params.allowedSignerKeyIds.length > 0
      ? contract.predicate.params.allowedSignerKeyIds
      : (typeof contract?.seller === 'string' && contract.seller.length > 0 ? [contract.seller] : []);

    if (allowedSignerKeyIds.length === 0) {
      return fail(
        'contract.seller or predicate.params.allowedSignerKeyIds is required to bind the transcript signer',
        at,
      );
    }
    if (!allowedSignerKeyIds.includes(derivedSignerKeyId)) {
      return fail(
        `attestation signer ${derivedSignerKeyId} is not authorized for this contract`,
        at,
      );
    }

    // (3) Authenticity: verify the signature over the canonical bound statement.
    const message = canonicalize({
      contractId: contract?.id,
      nonce,
      outputHash,
    });

    const sigOk = verifySig(publicKey, message, signature);
    if (!sigOk) {
      return fail(
        'signature does not verify over canonical({contractId, nonce, outputHash}) — tampered or wrong key',
        at,
      );
    }

    return {
      ok: true,
      tier: TIER,
      verifier: NAME,
      reason: `valid nonce-bound transcript: authorized signer ${derivedSignerKeyId} verifies and binds contract ${contract?.id} / nonce ${nonce} / outputHash ${outputHash}`,
      checkedAt: at,
    };
  },
};

/**
 * Build a failing Verdict with a reason.
 * @param {string} reason
 * @param {number} checkedAt
 * @returns {Verdict}
 */
function fail(reason, checkedAt) {
  return { ok: false, tier: TIER, verifier: NAME, reason, checkedAt };
}

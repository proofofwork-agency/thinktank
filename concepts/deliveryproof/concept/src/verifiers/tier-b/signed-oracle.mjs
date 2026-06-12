// Runnable Tier-B provenance example: signed oracle attestation.
//
// This verifier uses real Ed25519 signatures over a provenance statement:
//   canonical({ contractId, nonce, outputHash, source, claim, producedAt })
//
// It proves only that an allowed attester signed that statement. It does NOT
// prove the external-world claim is true. This is intentionally Tier B: useful
// provenance, weaker than Tier A objective recomputation.

import { canonicalize, sha256hex } from '../../protocol/canonical.mjs';
import { keyId, verify as verifySig } from '../../protocol/crypto.mjs';
import { checkedAt as checkedAtFrom, clockFrom } from '../../protocol/runtime.mjs';

/** @typedef {import('../../protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('../../protocol/types.mjs').DeliveryEvidence} DeliveryEvidence */
/** @typedef {import('../../protocol/types.mjs').Verdict} Verdict */

const NAME = 'signed-oracle';
const TIER = 'B';

/**
 * @type {import('../../protocol/types.mjs').Verifier}
 */
export const signedOracleVerifier = {
  name: NAME,
  tier: TIER,
  /**
   * @param {DeliveryContract} contract
   * @param {DeliveryEvidence} evidence
   * @returns {Verdict}
   */
  verify(contract, evidence, opts = {}) {
    const checkedAt = checkedAtFrom(opts);
    const params = contract?.predicate?.params ?? {};
    const attestations = evidence?.attestations;
    if (!Array.isArray(attestations) || attestations.length === 0) {
      return fail('evidence.attestations[0] is required for signed-oracle provenance', checkedAt);
    }
    const att = attestations[0];
    const statement = att?.statement;
    if (!statement || typeof statement !== 'object') {
      return fail('attestation.statement object is required', checkedAt);
    }
    const publicKey = att.publicKey;
    const signature = att.signature;
    if (typeof publicKey !== 'string' || publicKey.length === 0) return fail('attestation.publicKey is required', checkedAt);
    if (typeof signature !== 'string' || signature.length === 0) return fail('attestation.signature is required', checkedAt);

    const derivedSignerKeyId = keyId(publicKey);
    if (att.signerKeyId !== undefined && att.signerKeyId !== derivedSignerKeyId) {
      return fail(`attestation signerKeyId ${att.signerKeyId} does not match publicKey ${derivedSignerKeyId}`, checkedAt);
    }
    const allowed = Array.isArray(params.allowedAttesterKeyIds) ? params.allowedAttesterKeyIds : [];
    if (allowed.length === 0) {
      return fail('predicate.params.allowedAttesterKeyIds is required for signed-oracle provenance', checkedAt);
    }
    if (!allowed.includes(derivedSignerKeyId)) {
      return fail(`attester ${derivedSignerKeyId} is not allowed for this contract`, checkedAt);
    }

    const outputHash = sha256hex(evidence?.output);
    const bindingError = bindingMismatch(contract, statement, outputHash);
    if (bindingError) return fail(bindingError, checkedAt);

    if (typeof params.source === 'string' && statement.source !== params.source) {
      return fail(`source mismatch: expected ${params.source}, got ${String(statement.source)}`, checkedAt);
    }
    if (typeof params.claimType === 'string' && statement.claim?.type !== params.claimType) {
      return fail(`claim type mismatch: expected ${params.claimType}, got ${String(statement.claim?.type)}`, checkedAt);
    }
    if (typeof params.maxAgeMs === 'number' && Number.isFinite(params.maxAgeMs)) {
      const producedAt = Number(statement.producedAt);
      if (!Number.isFinite(producedAt)) return fail('statement.producedAt must be finite when maxAgeMs is set', checkedAt);
      if (Math.abs(checkedAt - producedAt) > params.maxAgeMs) {
        return fail(`oracle statement is stale by maxAgeMs=${params.maxAgeMs}`, checkedAt);
      }
    }

    const sigOk = verifySig(publicKey, canonicalize(statement), signature);
    if (!sigOk) {
      return fail('oracle signature does not verify over canonical(statement)', checkedAt);
    }

    return {
      ok: true,
      tier: TIER,
      verifier: NAME,
      reason: `valid signed provenance from ${derivedSignerKeyId}: attester said ${describeClaim(statement.claim)} for source ${statement.source}`,
      provenance: {
        interface: 'signed-oracle',
        signerKeyId: derivedSignerKeyId,
        source: statement.source,
        claim: statement.claim,
        statementHash: sha256hex(statement),
      },
      checkedAt,
    };
  },
};

/**
 * @param {Object} args
 * @param {DeliveryContract} args.contract
 * @param {DeliveryEvidence} args.evidence
 * @param {string} args.source
 * @param {Object} args.claim
 * @param {{ publicKey: string, privateKey: string }} args.attesterKey
 * @param {(privateKey: string, message: string) => string} args.signFn
 * @param {() => number} [args.now]
 * @returns {Object}
 */
export function buildSignedOracleAttestation({ contract, evidence, source, claim, attesterKey, signFn, now = Date.now }) {
  const readNow = clockFrom({ now });
  const statement = {
    contractId: contract.id,
    nonce: contract.nonce,
    outputHash: sha256hex(evidence.output),
    source,
    claim,
    producedAt: typeof evidence.producedAt === 'number' ? evidence.producedAt : readNow(),
  };
  return {
    signerKeyId: keyId(attesterKey.publicKey),
    publicKey: attesterKey.publicKey,
    statement,
    signature: signFn(attesterKey.privateKey, canonicalize(statement)),
  };
}

/**
 * @param {DeliveryContract} contract
 * @param {Object} statement
 * @param {string} outputHash
 */
function bindingMismatch(contract, statement, outputHash) {
  if (statement.contractId !== contract?.id) return 'contract binding mismatch';
  if (statement.nonce !== contract?.nonce) return 'nonce binding mismatch';
  if (statement.outputHash !== outputHash) return 'outputHash binding mismatch';
  return null;
}

/**
 * @param {*} claim
 */
function describeClaim(claim) {
  if (!claim || typeof claim !== 'object') return 'a claim';
  return claim.type ? `${claim.type}` : 'a claim';
}

/**
 * @param {string} reason
 * @param {number} checkedAt
 * @returns {Verdict}
 */
function fail(reason, checkedAt) {
  return { ok: false, tier: TIER, verifier: NAME, reason, checkedAt };
}

// src/verifiers/index.mjs
// Verifier registry. All built-in verifiers are Tier A (objective, no third-party trust).
//
// A real deployment would also register Tier-B verifiers (ZK proofs, TEE attestations,
// zkTLS oracles — "source said X") and Tier-C verifiers (subjective/semantic AI quality
// scoring). Those are intentionally NOT implemented in this PoC; see SPEC.md.

import { schemaVerifier } from './schema.mjs';
import { hashVerifier } from './hash.mjs';
import { testsuiteVerifier } from './testsuite.mjs';
import { transcriptVerifier } from './transcript.mjs';
import { datasetVerifier } from './dataset.mjs';
import { datasetMerkleSampleVerifier } from './dataset-merkle-sample.mjs';
import { apiResponseVerifier } from './api-response.mjs';
import { documentVerifier } from './document.mjs';
import { composeVerifier } from './compose.mjs';
import { signedOracleVerifier } from './tier-b/signed-oracle.mjs';

/** @typedef {import('../protocol/types.mjs').Verifier} Verifier */

/**
 * Registry keyed by predicate kind / verifier name.
 * @type {{ schema: Verifier, hash: Verifier, testsuite: Verifier, transcript: Verifier, dataset: Verifier, 'dataset-merkle-sample': Verifier, 'api-response': Verifier, document: Verifier, compose: Verifier, 'signed-oracle': Verifier }}
 */
export const verifiers = {
  schema: schemaVerifier,
  hash: hashVerifier,
  testsuite: testsuiteVerifier,
  transcript: transcriptVerifier,
  dataset: datasetVerifier,
  'dataset-merkle-sample': datasetMerkleSampleVerifier,
  'api-response': apiResponseVerifier,
  document: documentVerifier,
  compose: composeVerifier,
  'signed-oracle': signedOracleVerifier,
};

/**
 * Look up a verifier by name (matches predicate.kind). Throws on unknown name.
 * @param {string} name
 * @returns {Verifier}
 */
export function getVerifier(name) {
  const v = verifiers[name];
  if (!v) {
    const known = Object.keys(verifiers).join(', ');
    throw new Error(`unknown verifier "${name}" (known verifiers: ${known})`);
  }
  return v;
}

export { schemaVerifier, hashVerifier, testsuiteVerifier, transcriptVerifier, datasetVerifier, datasetMerkleSampleVerifier, apiResponseVerifier, documentVerifier, composeVerifier, signedOracleVerifier };

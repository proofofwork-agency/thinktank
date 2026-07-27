// src/verifiers/index.mjs
// Verifier registry. All built-in verifiers are Tier A (objective, no third-party trust).
//
// A real deployment would also register Tier-B verifiers (ZK proofs, TEE attestations,
// zkTLS oracles — "source said X") and Tier-C verifiers (subjective/semantic AI quality
// scoring). Those are intentionally NOT implemented in this PoC; see SPEC.md.

import { schemaVerifier } from './schema.mjs';
import { hashVerifier } from './hash.mjs';
import { builtinReplayVerifier, testsuiteVerifier } from './builtin-replay.mjs';
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
 * `testsuite` is a deprecated compatibility alias for `builtin-replay`.
 * @type {Record<string, Verifier>}
 */
export const verifiers = Object.freeze({
  schema: schemaVerifier,
  hash: hashVerifier,
  'builtin-replay': builtinReplayVerifier,
  testsuite: builtinReplayVerifier,
  transcript: transcriptVerifier,
  dataset: datasetVerifier,
  'dataset-merkle-sample': datasetMerkleSampleVerifier,
  'api-response': apiResponseVerifier,
  document: documentVerifier,
  compose: composeVerifier,
  'signed-oracle': signedOracleVerifier,
});

// FREEZE THE BUILT-INS.
//
// The engine grants a protocol assurance level only when the injected verifier is
// the built-in BY OBJECT IDENTITY (see assertRouteDecisionMatchesVerifier). That
// check is worth nothing if the thing it compares against can be replaced or
// rewritten, and adversarial review pointed at exactly that: `verifiers.dataset =
// evil` makes the impostor pass identity, and `datasetVerifier.verify = evil`
// keeps identity intact while swapping the behaviour — including AFTER the check
// has already run, since verification happens later in settle().
//
// Freezing the registry stops the first; freezing each verifier stops the second.
// Both are shallow freezes of stateless objects, which is all that is needed:
// the verifiers hold no mutable state, only a name, a tier, and a method.
for (const verifier of new Set(Object.values(verifiers))) {
  Object.freeze(verifier);
}

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

export {
  schemaVerifier,
  hashVerifier,
  builtinReplayVerifier,
  /** @deprecated Use builtinReplayVerifier. */
  testsuiteVerifier,
  transcriptVerifier,
  datasetVerifier,
  datasetMerkleSampleVerifier,
  apiResponseVerifier,
  documentVerifier,
  composeVerifier,
  signedOracleVerifier,
};

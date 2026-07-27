// src/router/profiles.mjs
// The TRUSTED verifier capability table.
//
// This is a LEAF module on purpose: it imports nothing. Both the router
// (./policy.mjs, which selects a verifier) and the engine
// (../engine/deliveryproof.mjs, which re-derives a routeDecision before signing
// it) need this table, and neither may take a dependency on the other.
//
// Why it lives outside the verifiers themselves: a verifier must not be able to
// advertise a stronger assurance or a cheaper cost than it actually provides.
// The numbers are declared HERE, by the protocol, not by the thing being rated.
//
//   assurance: how strong the objective guarantee is
//     1 = shape only (structural / JSON-schema — the shallow foil)
//     2 = integrity (content hash / signed nonce-bound transcript)
//     3 = deep objective correctness (deterministic re-execution / dataset
//         content / document structure)
//   cost: relative cost to run (cheaper preferred when sufficient)
//   kinds: deliverable kinds the verifier applies to ('*' = any)

const BUILTIN_REPLAY_PROFILE = { assurance: 3, cost: 4, kinds: ['compute'] };

export const VERIFIER_PROFILES = Object.freeze({
  schema: { assurance: 1, cost: 1, kinds: ['*'] },
  hash: { assurance: 2, cost: 2, kinds: ['*'] },
  transcript: { assurance: 2, cost: 3, kinds: ['*'] },
  'builtin-replay': BUILTIN_REPLAY_PROFILE,
  // Deprecated compatibility alias for existing contracts.
  testsuite: BUILTIN_REPLAY_PROFILE,
  dataset: { assurance: 3, cost: 5, kinds: ['dataset'] },
  'dataset-merkle-sample': { assurance: 3, cost: 2, kinds: ['dataset-merkle-sample'] },
  'api-response': { assurance: 3, cost: 4, kinds: ['api-response'] },
  document: { assurance: 3, cost: 4, kinds: ['document'] },
  // Placeholder; routeVerifier derives compose assurance/cost from children for
  // an explicit predicate.kind === 'compose' contract.
  compose: { assurance: 1, cost: 6, kinds: ['composite'] },
  'signed-oracle': { assurance: 2, cost: 3, kinds: ['provenance', 'api-response', '*'] },
});

// Freeze each profile and its kinds list too. A frozen table whose ROWS are
// mutable is not a trusted table: `VERIFIER_PROFILES.schema.assurance = 3` would
// otherwise make the engine re-derive — and then sign — an assurance of 3 for the
// shallow foil. Same class of defect as a mutable verifier registry.
for (const profile of Object.values(VERIFIER_PROFILES)) {
  Object.freeze(profile);
  Object.freeze(profile.kinds);
}

/** Human-readable names for assurance levels (for routeDecision/readability). */
export const ASSURANCE_NAMES = Object.freeze({ 1: 'shape', 2: 'integrity', 3: 'deep-correctness' });

/**
 * Derive compose assurance from child verifier profiles so the router reports
 * the guarantee actually implied by the predicate algebra.
 *
 * Per the v0.4 design:
 *   all       -> max child assurance (all predicates must pass, so the strongest
 *                child guarantee is included in the composite result)
 *   any       -> min child assurance (only one child must pass)
 *   threshold -> kth-lowest child assurance, where k = threshold
 *
 * @param {import('../protocol/types.mjs').DeliveryContract} contract
 * @param {Object} profiles
 * @returns {{ assurance: number, cost: number, kinds: string[] }}
 */
export function deriveComposeProfile(contract, profiles = VERIFIER_PROFILES) {
  const params = contract?.predicate?.params;
  if (!params || typeof params !== 'object' || !Array.isArray(params.verifiers) || params.verifiers.length === 0) {
    return { assurance: 1, cost: VERIFIER_PROFILES.compose.cost, kinds: ['composite'] };
  }
  const children = params.verifiers;
  const assurances = [];
  let cost = 1;
  for (const child of children) {
    if (!child || typeof child.kind !== 'string' || child.kind === 'compose') {
      return { assurance: 1, cost: VERIFIER_PROFILES.compose.cost, kinds: ['composite'] };
    }
    const profile = profiles[child.kind];
    if (!profile) {
      return { assurance: 1, cost: VERIFIER_PROFILES.compose.cost, kinds: ['composite'] };
    }
    assurances.push(profile.assurance);
    cost += profile.cost;
  }
  assurances.sort((a, b) => a - b);
  const mode = params.mode ?? 'all';
  let assurance;
  if (mode === 'any') {
    assurance = assurances[0];
  } else if (mode === 'threshold') {
    const threshold = Number.isInteger(params.threshold) ? params.threshold : 1;
    assurance = assurances[Math.max(0, Math.min(assurances.length - 1, threshold - 1))];
  } else {
    assurance = assurances[assurances.length - 1];
  }
  return { assurance, cost, kinds: ['composite'] };
}

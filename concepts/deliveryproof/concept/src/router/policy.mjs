// src/router/policy.mjs
// Verifier ROUTER / policy engine.
//
// The differentiator is not just "a deep verifier exists" — it is choosing the
// CHEAPEST verifier that is still STRONG ENOUGH for what the contract declares,
// and recording WHY in an auditable, signable decision. Crucially the router
// NEVER silently downgrades: if no verifier meets the required assurance and the
// policy did not explicitly allow a fallback, it THROWS rather than quietly
// settling with a weaker check.
//
// This module is pure and rail-independent: it reads only the contract + a policy
// + a static capability table, and returns the chosen verifier plus a structured
// routeDecision. The engine binds that routeDecision into the SIGNED receipt, so
// the routing choice is tamper-evident alongside the verdict.
//
// Router policy helper: reuses ../protocol/canonical.mjs only.

import { sha256hex } from '../protocol/canonical.mjs';
import { verifiers as defaultRegistry } from '../verifiers/index.mjs';
import { emitAudit, normalizeAuditSink } from '../operability/index.mjs';

// The trusted capability table now lives in ./profiles.mjs — a leaf module, so
// the engine can re-derive a routeDecision from the same numbers without taking
// a dependency on the router. Imported for local use AND re-exported so the
// public API (src/index.mjs) is unchanged.
import { VERIFIER_PROFILES, ASSURANCE_NAMES, deriveComposeProfile } from './profiles.mjs';

export { VERIFIER_PROFILES, ASSURANCE_NAMES, deriveComposeProfile };

const NON_BYPASSABLE_PREDICATE_KINDS = new Set(['compose', 'signed-oracle', 'dataset-merkle-sample']);

/**
 * @typedef {Object} VerifierPolicy
 * @property {string} [deliverableType]  e.g. 'dataset' | 'compute' | 'any' (default 'any')
 * @property {number} minAssurance       required minimum assurance level (1..3)
 * @property {boolean} [fallbackAllowed]  if true, a weaker-than-required verifier MAY be
 *                                        selected when nothing qualifies (recorded explicitly);
 *                                        if false/absent, routeVerifier THROWS instead of downgrading
 * @property {number} [maxCost]           optional cost ceiling
 */

/**
 * @typedef {Object} RouteDecision
 * @property {string} selected             chosen verifier kind
 * @property {number} selectedAssurance    its assurance level
 * @property {string} selectedAssuranceName
 * @property {string} deliverableType
 * @property {number} minAssurance
 * @property {boolean} fallbackUsed
 * @property {string[]} candidatesConsidered
 * @property {{name:string, reason:string}[]} rejected
 * @property {string} policyHash           sha256hex(policy) — binds the policy to the decision
 */

/**
 * Choose the cheapest sufficient verifier for a contract under a policy.
 *
 * @param {import('../protocol/types.mjs').DeliveryContract} contract
 * @param {Object} opts
 * @param {VerifierPolicy} opts.policy
 * @param {Object} [opts.registry]   verifier registry (defaults to built-ins)
 * @param {Object} [opts.profiles]   capability profiles (defaults to VERIFIER_PROFILES)
 * @param {import('../operability/index.mjs').AuditSink|Function|null} [opts.audit] Optional best-effort audit sink.
 * @param {() => number} [opts.now] Optional audit clock.
 * @returns {{ verifier: import('../protocol/types.mjs').Verifier, routeDecision: RouteDecision }}
 * @throws {Error} if no verifier meets minAssurance and policy.fallbackAllowed !== true
 */
export function routeVerifier(contract, { policy, registry = defaultRegistry, profiles = VERIFIER_PROFILES, audit = null, now } = {}) {
  if (!policy || typeof policy !== 'object') {
    throw new TypeError('routeVerifier: a policy { minAssurance, deliverableType? } is required');
  }
  const auditSink = normalizeAuditSink(audit);
  const explicitKind = contract?.predicate?.kind;
  const explicitCompose = explicitKind === 'compose';
  const forcedPredicateKind = NON_BYPASSABLE_PREDICATE_KINDS.has(explicitKind) ? explicitKind : null;
  const deliverableType = typeof policy.deliverableType === 'string'
    ? policy.deliverableType
    : explicitCompose ? 'composite' : 'any';
  const minAssurance = typeof policy.minAssurance === 'number' ? policy.minAssurance : 1;
  const fallbackAllowed = policy.fallbackAllowed === true;
  const maxCost = typeof policy.maxCost === 'number' ? policy.maxCost : Infinity;
  const policyForHash = { deliverableType, minAssurance, fallbackAllowed };
  if (Number.isFinite(maxCost)) policyForHash.maxCost = maxCost;
  const policyHash = sha256hex(policyForHash);

  const effectiveProfiles = explicitCompose
    ? { ...profiles, compose: deriveComposeProfile(contract, profiles) }
    : profiles;

  // Only consider verifier KINDS that are both in the registry AND have a profile.
  // Some predicate kinds are security-significant and must not be routed around
  // by a broad/low-assurance policy. If the buyer wrote a composition or
  // provenance predicate, the router must select that verifier or reject.
  const known = forcedPredicateKind
    ? (registry[forcedPredicateKind] && effectiveProfiles[forcedPredicateKind] ? [forcedPredicateKind] : [])
    : Object.keys(effectiveProfiles).filter((kind) => registry[kind]);

  const rejected = [];
  const eligibleForType = [];
  for (const kind of known) {
    const p = effectiveProfiles[kind];
    const typeOk = p.kinds.includes('*') || p.kinds.includes(deliverableType);
    if (!typeOk) {
      rejected.push({ name: kind, reason: `does not handle deliverableType "${deliverableType}"` });
      continue;
    }
    if (p.cost > maxCost) {
      rejected.push({ name: kind, reason: `cost ${p.cost} exceeds maxCost ${maxCost}` });
      continue;
    }
    eligibleForType.push(kind);
  }

  // Candidates that meet the required assurance.
  const sufficient = eligibleForType.filter((kind) => effectiveProfiles[kind].assurance >= minAssurance);
  for (const kind of eligibleForType) {
    if (effectiveProfiles[kind].assurance < minAssurance) {
      rejected.push({
        name: kind,
        reason: `assurance ${effectiveProfiles[kind].assurance} (${ASSURANCE_NAMES[effectiveProfiles[kind].assurance]}) below required ${minAssurance} (${ASSURANCE_NAMES[minAssurance]})`,
      });
    }
  }

  // Cheapest-sufficient selection. Tie-break: higher assurance, then name.
  const pickCheapest = (kinds) =>
    [...kinds].sort((a, b) => {
      const pa = effectiveProfiles[a];
      const pb = effectiveProfiles[b];
      if (pa.cost !== pb.cost) return pa.cost - pb.cost;
      if (pa.assurance !== pb.assurance) return pb.assurance - pa.assurance;
      return a < b ? -1 : a > b ? 1 : 0;
    })[0];

  let selected;
  let fallbackUsed = false;

  if (sufficient.length > 0) {
    selected = pickCheapest(sufficient);
  } else {
    // NEVER silently downgrade. Only fall back if the policy explicitly opted in.
    if (!fallbackAllowed) {
      emitAudit(auditSink, 'router.route.failed', {
        deliverableType,
        minAssurance,
        candidatesConsidered: eligibleForType,
        policyHash,
        reason: 'no sufficient verifier',
      }, { now });
      throw new Error(
        `routeVerifier: no verifier meets required assurance ${minAssurance} (${ASSURANCE_NAMES[minAssurance] ?? minAssurance}) ` +
          `for deliverableType "${deliverableType}", and policy.fallbackAllowed is not true. ` +
          `Refusing to settle on a weaker check. Considered: [${eligibleForType.join(', ') || 'none'}].`,
      );
    }
    if (eligibleForType.length === 0) {
      emitAudit(auditSink, 'router.route.failed', {
        deliverableType,
        minAssurance,
        candidatesConsidered: eligibleForType,
        policyHash,
        reason: 'no verifier handles deliverable type',
      }, { now });
      throw new Error(
        `routeVerifier: no verifier handles deliverableType "${deliverableType}" at all (even with fallback). ` +
          `Known kinds: [${known.join(', ')}].`,
      );
    }
    // Fallback = strongest available (highest assurance, then cheapest), explicitly flagged.
    selected = [...eligibleForType].sort((a, b) => {
      const pa = effectiveProfiles[a];
      const pb = effectiveProfiles[b];
      if (pa.assurance !== pb.assurance) return pb.assurance - pa.assurance;
      if (pa.cost !== pb.cost) return pa.cost - pb.cost;
      return a < b ? -1 : a > b ? 1 : 0;
    })[0];
    fallbackUsed = true;
  }

  const routeDecision = {
    selected,
    selectedAssurance: effectiveProfiles[selected].assurance,
    selectedAssuranceName: ASSURANCE_NAMES[effectiveProfiles[selected].assurance],
    deliverableType,
    minAssurance,
    fallbackUsed,
    candidatesConsidered: eligibleForType,
    rejected,
    policyHash,
  };

  emitAudit(auditSink, 'router.route.selected', {
    selected,
    selectedAssurance: routeDecision.selectedAssurance,
    deliverableType,
    minAssurance,
    fallbackUsed,
    policyHash,
  }, { now });

  return { verifier: registry[selected], routeDecision };
}

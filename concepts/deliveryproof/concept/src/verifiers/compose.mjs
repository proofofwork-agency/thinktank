// Multi-verifier predicate composition.
//
// `compose` is itself a normal Verifier. It wraps existing verifiers under a
// small predicate algebra (all/any/threshold) and returns a signed-in-receipt
// trace of every child verdict. The engine does not need special cases.

import { schemaVerifier } from './schema.mjs';
import { hashVerifier } from './hash.mjs';
import { testsuiteVerifier } from './testsuite.mjs';
import { transcriptVerifier } from './transcript.mjs';
import { datasetVerifier } from './dataset.mjs';
import { apiResponseVerifier } from './api-response.mjs';
import { documentVerifier } from './document.mjs';
import { checkedAt as checkedAtFrom } from '../protocol/runtime.mjs';

/** @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('../protocol/types.mjs').DeliveryEvidence} DeliveryEvidence */
/** @typedef {import('../protocol/types.mjs').Verdict} Verdict */
/** @typedef {import('../protocol/types.mjs').Verifier} Verifier */

const NAME = 'compose';
const DEFAULT_MODE = 'all';

const DEFAULT_REGISTRY = {
  schema: schemaVerifier,
  hash: hashVerifier,
  testsuite: testsuiteVerifier,
  transcript: transcriptVerifier,
  dataset: datasetVerifier,
  'api-response': apiResponseVerifier,
  document: documentVerifier,
};

/**
 * @type {Verifier}
 */
export const composeVerifier = {
  name: NAME,
  tier: 'A',
  /**
   * @param {DeliveryContract} contract
   * @param {DeliveryEvidence} evidence
   * @returns {Promise<Verdict>}
   */
  async verify(contract, evidence, opts = {}) {
    return verifyComposition(contract, evidence, opts);
  },
};

/**
 * @param {DeliveryContract} contract
 * @param {DeliveryEvidence} evidence
 * @param {{ registry?: Record<string, Verifier>, now?: () => number }} [options]
 * @returns {Promise<Verdict>}
 */
export async function verifyComposition(contract, evidence, { registry = DEFAULT_REGISTRY, now } = {}) {
  const checkedAt = checkedAtFrom({ now });
  const params = contract?.predicate?.params;
  const configError = validateParams(params);
  if (configError) {
    return failed(`invalid compose predicate: ${configError}`, [], checkedAt);
  }

  const mode = params.mode ?? DEFAULT_MODE;
  const children = params.verifiers;
  const trace = [];

  for (let index = 0; index < children.length; index++) {
    const child = children[index];
    const verifier = registry[child.kind];
    if (!verifier || typeof verifier.verify !== 'function') {
      return failed(`unknown child verifier "${child.kind}" at index ${index}`, trace, checkedAt);
    }
    if (child.kind === NAME) {
      return failed('nested compose verifiers are not supported in v0.4', trace, checkedAt);
    }
    const childContract = {
      ...contract,
      predicate: {
        kind: child.kind,
        params: child.params ?? {},
      },
    };
    try {
      const verdict = await verifier.verify(childContract, evidence, { now });
      trace.push(traceEntry(index, child.kind, verdict));
    } catch (err) {
      trace.push({
        index,
        verifier: child.kind,
        ok: false,
        tier: verifier.tier ?? 'A',
        reason: `child verifier threw: ${err instanceof Error ? err.message : String(err)}`,
      });
    }
  }

  const passCount = trace.filter((v) => v.ok).length;
  const required = mode === 'threshold' ? params.threshold : mode === 'any' ? 1 : children.length;
  const ok = passCount >= required;
  const tier = weakestTier(trace);
  return {
    ok,
    tier,
    verifier: NAME,
    reason: ok
      ? `compose ${mode}: ${passCount}/${children.length} child verifiers passed (required ${required})`
      : `compose ${mode}: ${passCount}/${children.length} child verifiers passed (required ${required})`,
    trace,
    checkedAt,
  };
}

/**
 * @param {*} params
 * @returns {string|null}
 */
function validateParams(params) {
  if (!params || typeof params !== 'object') return 'params object is required';
  const mode = params.mode ?? DEFAULT_MODE;
  if (!['all', 'any', 'threshold'].includes(mode)) {
    return 'mode must be all, any, or threshold';
  }
  if (!Array.isArray(params.verifiers) || params.verifiers.length === 0) {
    return 'verifiers must be a non-empty array';
  }
  if (params.verifiers.length > 16) {
    return 'verifiers is capped at 16 children';
  }
  for (let i = 0; i < params.verifiers.length; i++) {
    const child = params.verifiers[i];
    if (!child || typeof child !== 'object') return `verifiers[${i}] must be an object`;
    if (typeof child.kind !== 'string' || child.kind.length === 0) {
      return `verifiers[${i}].kind must be a non-empty string`;
    }
    if (child.params !== undefined && (child.params === null || typeof child.params !== 'object' || Array.isArray(child.params))) {
      return `verifiers[${i}].params must be an object when present`;
    }
  }
  if (mode === 'threshold') {
    if (!Number.isInteger(params.threshold) || params.threshold < 1 || params.threshold > params.verifiers.length) {
      return 'threshold must be an integer in [1, verifiers.length]';
    }
  }
  return null;
}

/**
 * @param {string} reason
 * @param {Object[]} trace
 * @param {number} checkedAt
 * @returns {Verdict}
 */
function failed(reason, trace, checkedAt) {
  return {
    ok: false,
    tier: 'A',
    verifier: NAME,
    reason,
    trace,
    checkedAt,
  };
}

/**
 * @param {number} index
 * @param {string} kind
 * @param {Verdict} verdict
 */
function traceEntry(index, kind, verdict) {
  return {
    index,
    verifier: kind,
    ok: verdict.ok === true,
    tier: verdict.tier ?? 'A',
    reason: String(verdict.reason ?? ''),
    ...(verdict.diff ? { diff: verdict.diff } : {}),
  };
}

/**
 * @param {Object[]} trace
 * @returns {'A'|'B'|'C'}
 */
function weakestTier(trace) {
  const rank = { A: 1, B: 2, C: 3 };
  let weakest = 'A';
  for (const item of trace) {
    if (rank[item.tier] > rank[weakest]) weakest = item.tier;
  }
  return weakest;
}

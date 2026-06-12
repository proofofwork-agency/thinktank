// test/router.test.mjs
// Tests for the verifier router / policy engine.
import test from 'node:test';
import assert from 'node:assert/strict';

import { routeVerifier, VERIFIER_PROFILES } from '../src/router/policy.mjs';
import { verifiers } from '../src/verifiers/index.mjs';

const datasetContract = { id: 'c1', nonce: 'n1', predicate: { kind: 'dataset', params: {} } };
const datasetMerkleSampleContract = {
  id: 'c2',
  nonce: 'n2',
  predicate: {
    kind: 'dataset-merkle-sample',
    params: {
      merkleRoot: '0'.repeat(64),
      rowCount: 0,
      k: 0,
      columns: [{ name: 'id', type: 'string' }],
    },
  },
};

test('router selects the cheapest verifier that meets the required assurance', () => {
  // A low-assurance policy on an 'any' deliverable should pick the cheapest (schema).
  const { verifier, routeDecision } = routeVerifier(datasetContract, {
    policy: { deliverableType: 'any', minAssurance: 1 },
  });
  assert.equal(routeDecision.selected, 'schema');
  assert.equal(verifier, verifiers.schema);
  assert.equal(routeDecision.selectedAssurance, 1);
  assert.equal(routeDecision.fallbackUsed, false);
  assert.match(routeDecision.policyHash, /^[0-9a-f]{64}$/);
});

test('router selects the deep dataset verifier for a dataset deliverable at deep assurance', () => {
  const { verifier, routeDecision } = routeVerifier(datasetContract, {
    policy: { deliverableType: 'dataset', minAssurance: 3 },
  });
  assert.equal(routeDecision.selected, 'dataset');
  assert.equal(verifier, verifiers.dataset);
  assert.equal(routeDecision.selectedAssurance, 3);
  // schema/hash/transcript must appear as rejected for being below required assurance.
  const rejectedNames = routeDecision.rejected.map((r) => r.name);
  assert.ok(rejectedNames.includes('schema'), 'schema should be rejected as too weak');
});

test('router selects dataset-merkle-sample only for explicit partial Merkle policies', () => {
  const { verifier, routeDecision } = routeVerifier(datasetMerkleSampleContract, {
    policy: { deliverableType: 'dataset-merkle-sample', minAssurance: 3 },
  });
  assert.equal(routeDecision.selected, 'dataset-merkle-sample');
  assert.equal(verifier, verifiers['dataset-merkle-sample']);
  assert.equal(routeDecision.selectedAssurance, 3);
});

test('router does NOT select dataset-merkle-sample for a generic dataset policy', () => {
  const { verifier, routeDecision } = routeVerifier(datasetContract, {
    policy: { deliverableType: 'dataset', minAssurance: 3 },
  });
  assert.equal(routeDecision.selected, 'dataset');
  assert.equal(verifier, verifiers.dataset);
  assert.ok(
    routeDecision.rejected.some((r) => r.name === 'dataset-merkle-sample' && /does not handle deliverableType "dataset"/.test(r.reason)),
    'partial Merkle verifier must not satisfy full dataset policies',
  );
});

test('router NEVER silently downgrades: throws when nothing meets assurance and fallback is off', () => {
  // Require deep correctness for a 'compute' deliverable but exclude the deep verifiers
  // via maxCost so only shallow ones remain -> must throw, not downgrade.
  assert.throws(
    () => routeVerifier(datasetContract, {
      policy: { deliverableType: 'compute', minAssurance: 3, maxCost: 1 },
    }),
    /no verifier meets required assurance/,
  );
});

test('router downgrades ONLY when fallbackAllowed is explicitly true, and flags it', () => {
  const { routeDecision } = routeVerifier(datasetContract, {
    policy: { deliverableType: 'any', minAssurance: 3, maxCost: 1, fallbackAllowed: true },
  });
  // Only schema (cost 1) is within maxCost; it is below assurance 3, so fallback must engage.
  assert.equal(routeDecision.fallbackUsed, true);
  assert.equal(routeDecision.selected, 'schema');
});

test('router throws when no verifier handles the deliverable type at all', () => {
  assert.throws(
    () => routeVerifier(datasetContract, {
      policy: { deliverableType: 'dataset', minAssurance: 3 },
      // a registry/profile set where dataset is unavailable
      registry: { schema: verifiers.schema },
      profiles: { schema: VERIFIER_PROFILES.schema },
    }),
    /no verifier meets required assurance|no verifier handles/,
  );
});

test('policyHash is stable for the same policy and differs for different policies', () => {
  const a = routeVerifier(datasetContract, { policy: { deliverableType: 'dataset', minAssurance: 3 } });
  const b = routeVerifier(datasetContract, { policy: { deliverableType: 'dataset', minAssurance: 3 } });
  const c = routeVerifier(datasetContract, { policy: { deliverableType: 'dataset', minAssurance: 1 } });
  assert.equal(a.routeDecision.policyHash, b.routeDecision.policyHash);
  assert.notEqual(a.routeDecision.policyHash, c.routeDecision.policyHash);
});

test('routeVerifier requires a policy', () => {
  assert.throws(() => routeVerifier(datasetContract, {}), /policy/);
});

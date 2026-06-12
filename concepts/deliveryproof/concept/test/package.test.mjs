import test from 'node:test';
import assert from 'node:assert/strict';

import {
  PROTOCOL_VERSION,
  keccak256,
  settle,
  verifyReceipt,
  assertReceiptMeetsPolicy,
  routeVerifier,
  createNonceRegistry,
  createWalReplayStore,
  REPLAY_STORE_INTERFACE,
  SIGNER_INTERFACE,
  KEYRING_INTERFACE,
  createInMemoryKeyring,
  AUDIT_BUNDLE_VERSION,
  buildAuditBundle,
  verifiers,
  datasetVerifier,
  datasetMerkleSampleVerifier,
  verifyInclusionSample,
  selectSampleIndices,
  createDurableEscrowRail,
  createMockEscrowRail,
  runRailConformance,
  registerRailConformance,
  RAIL_CONFORMANCE_CASES,
  runReplayStoreConformance,
  registerReplayStoreConformance,
  REPLAY_STORE_CONFORMANCE_CASES,
  merkleRoot,
  DeliveryProofValidationError,
  validateDeliveryProofConfig,
  deliveryProofHealthcheck,
  gracefulShutdown,
  encodeErc8004ValidationAbi,
  encodeErc8183EvaluatorAbi,
} from 'deliveryproof';

test('package: root export exposes the supported public API surface', () => {
  assert.equal(PROTOCOL_VERSION, 'deliveryproof/0.4-jcs1');
  assert.equal(typeof keccak256, 'function');
  assert.equal(typeof settle, 'function');
  assert.equal(typeof verifyReceipt, 'function');
  assert.equal(typeof assertReceiptMeetsPolicy, 'function');
  assert.equal(typeof routeVerifier, 'function');
  assert.equal(typeof createNonceRegistry, 'function');
  assert.equal(typeof createWalReplayStore, 'function');
  assert.equal(REPLAY_STORE_INTERFACE.requiredMethods.includes('get(key)'), true);
  assert.equal(SIGNER_INTERFACE.requiredMethods.includes('sign(message)'), true);
  assert.equal(KEYRING_INTERFACE.requiredMethods.includes('get(keyId)'), true);
  assert.equal(typeof createInMemoryKeyring, 'function');
  assert.equal(AUDIT_BUNDLE_VERSION, 'deliveryproof/audit-bundle/0.1');
  assert.equal(typeof buildAuditBundle, 'function');
  assert.equal(verifiers.dataset, datasetVerifier);
  assert.equal(verifiers['dataset-merkle-sample'], datasetMerkleSampleVerifier);
  assert.equal(typeof verifyInclusionSample, 'function');
  assert.equal(typeof selectSampleIndices, 'function');
  assert.equal(typeof createDurableEscrowRail, 'function');
  assert.equal(typeof createMockEscrowRail, 'function');
  assert.equal(typeof runRailConformance, 'function');
  assert.equal(typeof registerRailConformance, 'function');
  assert.equal(Array.isArray(RAIL_CONFORMANCE_CASES), true);
  assert.equal(typeof runReplayStoreConformance, 'function');
  assert.equal(typeof registerReplayStoreConformance, 'function');
  assert.equal(Array.isArray(REPLAY_STORE_CONFORMANCE_CASES), true);
  assert.equal(typeof merkleRoot, 'function');
  assert.equal(typeof DeliveryProofValidationError, 'function');
  assert.equal(typeof validateDeliveryProofConfig, 'function');
  assert.equal(typeof deliveryProofHealthcheck, 'function');
  assert.equal(typeof gracefulShutdown, 'function');
  assert.equal(typeof encodeErc8004ValidationAbi, 'function');
  assert.equal(typeof encodeErc8183EvaluatorAbi, 'function');
});

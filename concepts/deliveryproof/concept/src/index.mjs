// Public DeliveryProof API barrel.
//
// Import from the package root for production use:
//   import { settle, verifyReceipt, assertReceiptMeetsPolicy, datasetVerifier } from 'deliveryproof';
//
// Submodule paths under src/ are implementation files and are not part of the
// package exports contract unless promoted here.

/** @typedef {import('./protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('./protocol/types.mjs').DeliveryEvidence} DeliveryEvidence */
/** @typedef {import('./protocol/types.mjs').Verdict} Verdict */
/** @typedef {import('./protocol/types.mjs').DeliveryReceipt} DeliveryReceipt */
/** @typedef {import('./protocol/types.mjs').Hold} Hold */
/** @typedef {import('./protocol/types.mjs').Verifier} Verifier */
/** @typedef {import('./protocol/types.mjs').RailAdapter} RailAdapter */
/** @typedef {import('./protocol/types.mjs').DeliveryPredicate} DeliveryPredicate */
/** @typedef {import('./protocol/types.mjs').DatasetSpec} DatasetSpec */
/** @typedef {import('./protocol/types.mjs').DatasetMerkleSampleSpec} DatasetMerkleSampleSpec */
/** @typedef {import('./protocol/types.mjs').DatasetMerkleSampleEvidence} DatasetMerkleSampleEvidence */
/** @typedef {import('./protocol/types.mjs').ApiResponseSpec} ApiResponseSpec */
/** @typedef {import('./protocol/types.mjs').DocumentSpec} DocumentSpec */

export { settle, verifyReceipt, assertReceiptMeetsPolicy } from './engine/deliveryproof.mjs';
export { compileMilestoneContracts, settleMilestones, verifyMilestoneAggregate } from './engine/milestones.mjs';
export { createNonceRegistry, createWalReplayStore, nonceKey, REPLAY_STORE_INTERFACE } from './engine/nonce-registry.mjs';

export { routeVerifier, deriveComposeProfile, VERIFIER_PROFILES, ASSURANCE_NAMES } from './router/policy.mjs';

export {
  verifiers,
  getVerifier,
  schemaVerifier,
  hashVerifier,
  testsuiteVerifier,
  transcriptVerifier,
  datasetVerifier,
  datasetMerkleSampleVerifier,
  apiResponseVerifier,
  documentVerifier,
  composeVerifier,
  signedOracleVerifier,
} from './verifiers/index.mjs';
export { verifyInclusionSample } from './verifiers/dataset-merkle-sample.mjs';
export { verifyComposition } from './verifiers/compose.mjs';
export { runTestsuiteReplay, defaultTestsuiteWorkerPath } from './verifiers/testsuite-runner.mjs';
export { buildSignedOracleAttestation, TIER_B_INTERFACE_DESCRIPTORS, getTierBInterface } from './verifiers/tier-b/index.mjs';

export { createMockEscrowRail } from './rails/escrow-mock.mjs';
export { createDurableEscrowRail } from './rails/durable-rail.mjs';
export { runRailConformance, registerRailConformance, RAIL_CONFORMANCE_CASES } from './testing/rail-conformance.mjs';
export { runReplayStoreConformance, registerReplayStoreConformance, REPLAY_STORE_CONFORMANCE_CASES } from './testing/replay-store-conformance.mjs';

export {
  normalizeAuditSink,
  emitAudit,
  normalizeLogger,
  logBoundary,
  validateDeliveryProofConfig,
  assertDeliveryProofConfig,
  deliveryProofHealthcheck,
  gracefulShutdown,
} from './operability/index.mjs';
export { AUDIT_BUNDLE_VERSION, buildAuditBundle } from './operability/audit-bundle.mjs';

export {
  toErc8004ValidationPayload,
  encodeErc8004ValidationAbi,
  toErc8183EvaluatorResult,
  encodeErc8183EvaluatorAbi,
} from './interop/index.mjs';
export { paidToolWithDeliveryProof } from './mcp/paidToolWithDeliveryProof.mjs';

export { PROTOCOL_VERSION, CANONICALIZATION, canonicalize, sha256jcs, sha256utf8, sha256bytes, sha256hex } from './protocol/canonical.mjs';
export { keccak256 } from './protocol/keccak.mjs';
export { generateKeypair, sign, verify, keyId } from './protocol/crypto.mjs';
export { SIGNER_INTERFACE, KEYRING_INTERFACE, createInMemoryKeyring } from './protocol/signer.mjs';
export { DeliveryProofError, DeliveryProofValidationError, DeliveryProofConfigurationError, DeliveryProofRailError } from './protocol/errors.mjs';
export { validateContract, validateEvidence, validateVerdict, validateReceipt, assertContract, assertEvidence, assertVerdict, assertReceipt } from './protocol/schema.mjs';
export { merkleLeafHash, merkleNodeHash, emptyMerkleRoot, sortedMerkleLeaves, merkleRoot, buildMerkleTree, buildMerkleProof, verifyMerkleProof } from './protocol/merkle.mjs';
export { selectSampleIndices } from './protocol/merkle-sample.mjs';

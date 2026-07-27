// vouch — permissionless surety for machine work.
//
// Public surface. Everything here is Node built-ins only; the DeliveryProof
// composition is injected by the caller rather than imported, so this package
// has no dependency on DeliveryProof's release cadence.

export const PROTOCOL_VERSION = 'vouch/v1';

export { canonicalize, digest, domainDigest } from './canonical.mjs';
export {
  assertAmount,
  assertPositiveAmount,
  addAmount,
  subAmount,
  mulDivCeil,
  priceFromProbability,
} from './units.mjs';
export { Ledger, GENESIS } from './ledger.mjs';
export { createCommitment, commitmentIdOf } from './commitment.mjs';
export {
  OUTCOME,
  createAdapter,
  createAdapterRegistry,
  createDeliveryProofAdapter,
  attestationAdapter,
} from './evidence.mjs';
export { createVouchMarket } from './protocol.mjs';
export { createTrustOracle, replayOracle } from './oracle.mjs';
export {
  mintBadge,
  verifyBadge,
  tierOf,
  formatScore,
  premiumRateBasisPoints,
  renderBadgeSVG,
  renderBadgeMarkdown,
  renderMCPFragment,
} from './badge.mjs';

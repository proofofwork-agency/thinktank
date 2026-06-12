import { canonicalize, sha256hex } from '../protocol/canonical.mjs';

export const AUDIT_BUNDLE_VERSION = 'deliveryproof/audit-bundle/0.1';

/**
 * Build a local, inspectable audit bundle from already-existing artifacts.
 *
 * This does not create a new proof, contact telemetry, or alter settlement.
 * It collates the receipt, contract, evidence, and optional rail status hashes
 * so operators can re-check the bindings already present in signed receipts.
 *
 * @param {Object} args
 * @param {import('../protocol/types.mjs').DeliveryReceipt} args.receipt
 * @param {import('../protocol/types.mjs').DeliveryContract} args.contract
 * @param {import('../protocol/types.mjs').DeliveryEvidence} args.evidence
 * @param {import('../protocol/types.mjs').Hold|null} [args.railStatus]
 * @returns {Object}
 */
export function buildAuditBundle({ receipt, contract, evidence, railStatus = null } = {}) {
  assertObject(receipt, 'receipt');
  assertObject(contract, 'contract');
  assertObject(evidence, 'evidence');
  if (railStatus !== null) assertObject(railStatus, 'railStatus');

  const contractHash = sha256hex(contract);
  const evidenceHash = sha256hex(evidence);
  const receiptHash = sha256hex(receipt);
  const railStatusHash = railStatus === null ? null : sha256hex(railStatus);
  const railDecisionState = stateForDecision(receipt.decision);
  const checks = {
    contractHashMatchesReceipt: receipt.contractHash === contractHash,
    evidenceHashMatchesReceipt: receipt.evidenceHash === evidenceHash,
    evidenceContractIdMatchesReceipt: evidence.contractId === receipt.contractId,
    railStatusPresent: railStatus !== null,
    railHoldMatchesReceipt: railStatus === null ? null : railStatus.holdId === receipt.holdId,
    railContractIdMatchesReceipt: railStatus === null ? null : railStatus.contractId === receipt.contractId,
    railContractHashMatchesReceipt: railStatus === null ? null : railStatus.contractHash === receipt.contractHash,
    railRailIdMatchesReceipt: railStatus === null ? null : railStatus.railId === receipt.railId,
    railAmountMatchesReceipt: railStatus === null ? null : railStatus.amount === receipt.amount,
    railCurrencyMatchesReceipt: railStatus === null ? null : railStatus.currency === receipt.currency,
    railStateMatchesDecision: railStatus === null ? null : railStatus.state === railDecisionState,
  };

  const bundle = {
    protocolVersion: AUDIT_BUNDLE_VERSION,
    kind: 'deliveryproof-audit-bundle',
    purpose: 'inspection-aid',
    caveat: 'collates existing signed receipt bindings and hashes; it is not a new proof or telemetry record',
    receipt: {
      hash: receiptHash,
      contractId: receipt.contractId,
      contractHash: receipt.contractHash,
      evidenceHash: receipt.evidenceHash,
      railId: receipt.railId,
      holdId: receipt.holdId,
      amount: receipt.amount,
      currency: receipt.currency,
      routeDecision: receipt.routeDecision,
      verdict: receipt.verdict,
      signerKeyId: receipt.signerKeyId,
      decision: receipt.decision,
      issuedAt: receipt.issuedAt,
    },
    contract: {
      id: contract.id,
      hash: contractHash,
      receiptHash: receipt.contractHash,
    },
    evidence: {
      contractId: evidence.contractId,
      hash: evidenceHash,
      receiptHash: receipt.evidenceHash,
      outputHash: evidence.outputHash,
      producedAt: evidence.producedAt,
    },
    railStatus: railStatus === null ? null : {
      hash: railStatusHash,
      holdId: railStatus.holdId,
      contractId: railStatus.contractId,
      contractHash: railStatus.contractHash,
      railId: railStatus.railId,
      amount: railStatus.amount,
      currency: railStatus.currency,
      state: railStatus.state,
      expectedStateForDecision: railDecisionState,
    },
    checks,
  };

  return {
    ...bundle,
    canonicalHash: sha256hex(bundle),
    canonicalBytes: canonicalize(bundle).length,
  };
}

function stateForDecision(decision) {
  if (decision === 'release') return 'captured';
  if (decision === 'refund') return 'refunded';
  return null;
}

function assertObject(value, name) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError(`buildAuditBundle: ${name} must be an object`);
  }
}

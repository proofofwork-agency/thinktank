// deliveryproof.mjs — the settlement orchestrator.
//
// settle() binds a payment hold to VERIFIED DELIVERY: it authorizes a hold,
// produces evidence, runs the verifier, signs a DeliveryReceipt, and then
// captures (pays seller) ONLY on a passing verdict, otherwise refunds the buyer.
//
// CRITICAL INVARIANT: there is NO code path that captures/pays the seller when
// verdict.ok === false. Verification gates settlement. This is enforced twice:
//   (1) decision is derived solely from verdict.ok;
//   (2) the capture branch is additionally guarded by an explicit assert.
//
// Core settlement engine. Crypto/hash helpers live under ./protocol/*.
import { canonicalize, PROTOCOL_VERSION, sha256hex } from '../protocol/canonical.mjs';
import { assertContract, assertEvidence, assertReceipt, assertVerdict } from '../protocol/schema.mjs';
import { sign, verify, keyId } from '../protocol/crypto.mjs';
import { createInMemoryKeyring } from '../protocol/signer.mjs';
import { DeliveryProofConfigurationError, DeliveryProofValidationError } from '../protocol/errors.mjs';
import { clockFrom } from '../protocol/runtime.mjs';
import { emitAudit, normalizeAuditSink } from '../operability/index.mjs';

/**
 * @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract
 * @typedef {import('../protocol/types.mjs').DeliveryEvidence} DeliveryEvidence
 * @typedef {import('../protocol/types.mjs').Verdict} Verdict
 * @typedef {import('../protocol/types.mjs').DeliveryReceipt} DeliveryReceipt
 * @typedef {import('../protocol/types.mjs').Verifier} Verifier
 * @typedef {import('../protocol/types.mjs').RailAdapter} RailAdapter
 * @typedef {import('../protocol/types.mjs').Hold} Hold
 */

/**
 * Run the full verified-delivery settlement for a single contract.
 *
 * Flow:
 *   1) hold = await rail.authorize(contract)           // money escrowed
 *   2) evidence = await produceEvidence(contract)      // seller delivers
 *      - normalized so outputHash = sha256hex(output), nonce = contract.nonce,
 *        contractId = contract.id
 *   3) verdict = await verifier.verify(contract, evidence) // objective/tiered check
 *   4) decision = verdict.ok ? 'release' : 'refund'    // verdict gates settlement
 *   5) receipt signed over canonical(receipt-without-signature)
 *   6) release -> rail.capture(hold, receipt); refund -> rail.refund(hold, receipt)
 *   7) return { contract, evidence, verdict, receipt, hold }
 *
 * @param {Object} args
 * @param {DeliveryContract} args.contract
 * @param {(contract: DeliveryContract) => (DeliveryEvidence | Promise<DeliveryEvidence>)} args.produceEvidence
 * @param {Verifier} args.verifier
 * @param {RailAdapter} args.rail
 * @param {{ publicKey: string, privateKey: string }} args.settlementKey  PEM keypair of the settlement authority
 * @param {Object} [args.nonceRegistry] Optional replay registry.
 * @param {() => number} [args.now] Optional clock for deterministic tests.
 * @param {import('../operability/index.mjs').AuditSink|Function|null} [args.audit] Optional best-effort audit sink.
 * @returns {Promise<{ contract: DeliveryContract, evidence: DeliveryEvidence, verdict: Verdict, receipt: DeliveryReceipt, hold: Hold }>}
 */
export async function settle({ contract, produceEvidence, verifier, rail, settlementKey, routeDecision = null, nonceRegistry = null, now = Date.now, audit = null } = {}) {
  const readNow = clockFrom({ now });
  const auditSink = normalizeAuditSink(audit);
  if (!contract || typeof contract !== 'object') {
    throw new DeliveryProofValidationError('settle: contract is required');
  }
  if (typeof produceEvidence !== 'function') {
    throw new DeliveryProofConfigurationError('settle: produceEvidence must be a function');
  }
  if (!verifier || typeof verifier.verify !== 'function') {
    throw new DeliveryProofConfigurationError('settle: verifier with a verify() method is required');
  }
  if (!rail || typeof rail.authorize !== 'function' ||
      typeof rail.capture !== 'function' || typeof rail.refund !== 'function') {
    throw new DeliveryProofConfigurationError('settle: rail adapter with authorize/capture/refund is required');
  }
  assertRouteDecisionMatchesVerifier(routeDecision, verifier);
  if (!settlementKey || !settlementKey.publicKey || !settlementKey.privateKey) {
    throw new DeliveryProofConfigurationError('settle: settlementKey { publicKey, privateKey } (PEM) is required');
  }

  const normalizedContract = { protocolVersion: PROTOCOL_VERSION, ...contract };
  assertContract(normalizedContract);
  assertRailMatchesContract(normalizedContract, rail);
  assertSettlementKeypair(settlementKey);
  const contractHash = sha256hex(normalizedContract);
  const settlementKeyId = keyId(settlementKey.publicKey);
  const auditOpts = { now: readNow };
  emitAudit(auditSink, 'engine.settle.started', {
    contractId: normalizedContract.id,
    verifier: verifier.name ?? 'unknown',
    railId: normalizedContract.railId ?? rail.id,
  }, auditOpts);
  const lifecycle = [];
  const mark = (state, extra = {}) => {
    lifecycle.push({ state, at: readNow(), ...extra });
  };

  let nonceRegistryKey = null;
  if (nonceRegistry) {
    nonceRegistryKey = nonceRegistry.reserve({ contract: normalizedContract, settlementKeyId });
    mark('nonce-reserved', { nonceRegistryKey });
    emitAudit(auditSink, 'engine.nonce.reserved', { contractId: normalizedContract.id, nonceRegistryKey }, auditOpts);
  }

  // 1) Authorize the hold — money is escrowed before any delivery happens.
  mark('authorizing');
  const hold = await rail.authorize(normalizedContract);
  mark('held', { holdId: hold.holdId });
  emitAudit(auditSink, 'engine.hold.authorized', { contractId: normalizedContract.id, holdId: hold.holdId }, auditOpts);

  /** @type {DeliveryEvidence} */
  let evidence;
  /** @type {Verdict} */
  let verdict;

  try {
    enforceDeadline(normalizedContract, readNow(), 'before delivery');
    // 2) Produce evidence (the seller's tool runs here). Normalize the evidence so
    //    its integrity fields are authoritative regardless of what the producer set.
    const { signal, cancel } = makeAbortSignal(normalizedContract, readNow);
    mark('delivery-started');
    let produced;
    try {
      produced = await produceEvidence(normalizedContract, { signal });
    } finally {
      cancel();
    }
    enforceDeadline(normalizedContract, readNow(), 'after delivery');
    mark('evidence-produced');
    if (!produced || typeof produced !== 'object') {
      throw new DeliveryProofValidationError('settle: produceEvidence must resolve to a DeliveryEvidence object');
    }
    evidence = {
      ...produced,
      protocolVersion: PROTOCOL_VERSION,
      contractId: normalizedContract.id,
      nonce: normalizedContract.nonce,
      outputHash: sha256hex(produced.output),
      producedAt: typeof produced.producedAt === 'number' ? produced.producedAt : readNow(),
    };
    assertEvidence(evidence);
    emitAudit(auditSink, 'engine.evidence.produced', {
      contractId: normalizedContract.id,
      outputHash: evidence.outputHash,
    }, auditOpts);

    // 3) Verify delivery against the contract predicate. The verifier is injected;
    //    the engine never reaches into ./verifiers directly.
    mark('verification-started');
    verdict = await verifier.verify(normalizedContract, evidence, { now: readNow });
    if (!verdict || typeof verdict.ok !== 'boolean') {
      throw new DeliveryProofValidationError('settle: verifier.verify must return a Verdict with a boolean ok');
    }
    assertVerdict(verdict);
    mark('verified', { ok: verdict.ok, verifier: verdict.verifier });
    emitAudit(auditSink, 'engine.verdict.checked', {
      contractId: normalizedContract.id,
      ok: verdict.ok,
      verifier: verdict.verifier,
    }, auditOpts);
  } catch (err) {
    // Once funds are held, delivery/verification exceptions are failed delivery,
    // not process exits: create a negative verdict and refund the hold.
    const reason = err instanceof Error ? err.message : String(err);
    evidence = evidence ?? {
      protocolVersion: PROTOCOL_VERSION,
      contractId: normalizedContract.id,
      nonce: normalizedContract.nonce,
      output: null,
      outputHash: sha256hex(null),
      logs: [`delivery/verification exception: ${reason}`],
      producedAt: readNow(),
    };
    verdict = {
      ok: false,
      tier: verifier.tier ?? 'A',
      verifier: verifier.name ?? 'unknown',
      reason: `delivery/verification exception: ${reason}`,
      checkedAt: readNow(),
    };
    assertEvidence(evidence);
    assertVerdict(verdict);
    mark('verified', { ok: false, verifier: verdict.verifier });
    emitAudit(auditSink, 'engine.verdict.exception', {
      contractId: normalizedContract.id,
      verifier: verdict.verifier,
      reason: verdict.reason,
    }, auditOpts);
  }

  // 4) Decision is derived SOLELY from the verdict. A failing verdict can only
  //    ever produce 'refund'.
  const decision = verdict.ok ? 'release' : 'refund';
  mark('decision', { decision });
  mark('receipt-signing');

  // 5) Build and sign the receipt. The signature covers the canonical form of the
  //    receipt WITHOUT its own signature field.
  const unsignedReceipt = {
    protocolVersion: PROTOCOL_VERSION,
    contractId: normalizedContract.id,
    contractHash,
    railId: normalizedContract.railId ?? rail.id,
    holdId: hold.holdId,
    amount: hold.amount,
    currency: hold.currency,
    verdict,
    evidenceHash: sha256hex(evidence),
    decision,
    // Optional verifier-routing decision, bound into the SIGNED receipt so the
    // choice of verifier (and the policy that drove it) is tamper-evident
    // alongside the verdict. null when the caller selected a verifier directly.
    routeDecision: routeDecision ?? null,
    lifecycle: lifecycle.map((entry) => ({ ...entry })),
    nonceRegistryKey,
    signerKeyId: settlementKeyId,
    issuedAt: readNow(),
  };
  assertReceipt(unsignedReceipt, { requireSignature: false });
  const signature = sign(settlementKey.privateKey, canonicalize(unsignedReceipt));
  /** @type {DeliveryReceipt} */
  const receipt = { ...unsignedReceipt, signature };
  assertReceipt(receipt);
  emitAudit(auditSink, 'engine.receipt.signed', {
    contractId: normalizedContract.id,
    holdId: hold.holdId,
    decision,
  }, auditOpts);

  // 6) Settle. Capture (pay seller) is reachable ONLY through the release branch,
  //    and is additionally guarded so it is impossible to capture on a non-ok
  //    verdict even if upstream logic were ever changed.
  if (decision === 'release') {
    if (verdict.ok !== true) {
      // Defense-in-depth: should be unreachable given step 4.
      throw new Error('settle: refusing to capture — verdict.ok is not true');
    }
    await rail.capture(hold, receipt);
    emitAudit(auditSink, 'engine.rail.captured', { contractId: normalizedContract.id, holdId: hold.holdId }, auditOpts);
  } else {
    await rail.refund(hold, receipt);
    emitAudit(auditSink, 'engine.rail.refunded', { contractId: normalizedContract.id, holdId: hold.holdId }, auditOpts);
  }
  if (nonceRegistry && nonceRegistryKey) nonceRegistry.mark(nonceRegistryKey, decision === 'release' ? 'captured' : 'refunded');

  // 7) Return the full settlement record. We re-read the hold from the rail so the
  //    returned hold reflects its post-settlement state.
  const finalHold = typeof rail.status === 'function' ? await rail.status(hold.holdId) : hold;
  emitAudit(auditSink, 'engine.settle.completed', {
    contractId: normalizedContract.id,
    holdId: finalHold.holdId,
    decision,
    holdState: finalHold.state,
  }, auditOpts);

  return { contract: normalizedContract, evidence, verdict, receipt, hold: finalHold };
}

/**
 * @param {DeliveryContract} contract
 * @param {number} at
 * @param {string} phase
 */
function enforceDeadline(contract, at, phase) {
  const deadlineMs = contract?.sla?.deadlineMs;
  if (typeof deadlineMs !== 'number' || !Number.isFinite(deadlineMs)) return;
  if (typeof contract.createdAt !== 'number' || contract.createdAt <= 0) return;
  const deadlineAt = contract.createdAt + deadlineMs;
  if (at > deadlineAt) {
    throw new Error(`SLA deadline exceeded ${phase}: now ${at} > deadline ${deadlineAt}`);
  }
}

/**
 * @param {DeliveryContract} contract
 * @param {() => number} now
 */
function makeAbortSignal(contract, now) {
  const controller = new AbortController();
  const deadlineMs = contract?.sla?.deadlineMs;
  if (typeof deadlineMs !== 'number' || !Number.isFinite(deadlineMs)) {
    return { signal: controller.signal, cancel: () => {} };
  }
  if (typeof contract.createdAt !== 'number' || contract.createdAt <= 0) {
    return { signal: controller.signal, cancel: () => {} };
  }
  const remaining = Math.max(0, contract.createdAt + deadlineMs - now());
  const timer = setTimeout(() => controller.abort(new Error('SLA deadline exceeded')), remaining);
  timer.unref?.();
  return { signal: controller.signal, cancel: () => clearTimeout(timer) };
}

/**
 * Verify a DeliveryReceipt's signature against the settlement authority's public key.
 * Recomputes canonical(receipt-without-signature) and checks the Ed25519 signature.
 *
 * @param {DeliveryReceipt} receipt
 * @param {string|{keys?: string[], keyring?: {keys?: string[], get?: Function}}} trust
 * @returns {boolean}
 */
export function verifyReceipt(receipt, trust) {
  if (typeof trust === 'string') {
    return verifyReceiptSingle(receipt, trust);
  }
  return verifyReceiptWithKeyring(receipt, trust);
}

function verifyReceiptSingle(receipt, settlementPublicKeyPem) {
  if (!receipt || typeof receipt !== 'object' || typeof receipt.signature !== 'string') {
    return false;
  }
  const valid = validateReceiptForVerify(receipt);
  if (!valid) return false;
  if (!receiptDecisionMatchesVerdict(receipt)) return false;
  if (receipt.signerKeyId !== keyId(settlementPublicKeyPem)) return false;
  const { signature, ...unsignedReceipt } = receipt;
  return verify(settlementPublicKeyPem, canonicalize(unsignedReceipt), signature);
}

function verifyReceiptWithKeyring(receipt, trust) {
  try {
    if (!receipt || typeof receipt !== 'object' || typeof receipt.signature !== 'string') {
      return false;
    }
    const keyring = normalizeReceiptKeyring(trust);
    if (!keyring) return false;
    const signerKeyId = typeof receipt.signerKeyId === 'string' ? receipt.signerKeyId : '';
    const direct = signerKeyId && typeof keyring.get === 'function' ? keyring.get(signerKeyId) : [];
    const tried = new Set();
    for (const pem of normalizeKeyList(direct)) {
      tried.add(pem);
      if (verifyReceiptSingle(receipt, pem)) return true;
    }
    for (const pem of normalizeKeyList(keyring.keys)) {
      if (tried.has(pem)) continue;
      if (verifyReceiptSingle(receipt, pem)) return true;
    }
    return false;
  } catch {
    return false;
  }
}

function normalizeReceiptKeyring(trust) {
  if (!trust || typeof trust !== 'object') return null;
  if (Array.isArray(trust.keys)) return createInMemoryKeyring(trust.keys);
  if (trust.keyring && typeof trust.keyring === 'object') return trust.keyring;
  return null;
}

function normalizeKeyList(value) {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.filter((pem) => typeof pem === 'string');
  return [];
}

/**
 * Validate a receipt against optional production-integration policy. This is
 * intentionally separate from verifyReceipt(): direct library users may choose
 * their verifier/rail explicitly, while production wrappers can require a routed
 * decision, disallow fallback, or pin expected rail/verifier values.
 *
 * @param {DeliveryReceipt} receipt
 * @param {{
 *   requireRouteDecision?: boolean,
 *   allowFallback?: boolean,
 *   minAssurance?: number,
 *   expectedVerifier?: string,
 *   expectedRailId?: string,
 *   requireNonceRegistry?: boolean
 * }} [policy]
 * @returns {true}
 */
export function assertReceiptMeetsPolicy(receipt, policy = {}) {
  assertReceipt(receipt);
  if (!receiptDecisionMatchesVerdict(receipt)) {
    throw new DeliveryProofValidationError('receipt decision does not match verdict.ok');
  }
  if (policy.requireRouteDecision === true && (receipt.routeDecision === null || typeof receipt.routeDecision !== 'object')) {
    throw new DeliveryProofValidationError('receipt policy requires a signed routeDecision');
  }
  if (policy.allowFallback === false && receipt.routeDecision?.fallbackUsed === true) {
    throw new DeliveryProofValidationError('receipt policy disallows verifier fallback');
  }
  if (Number.isSafeInteger(policy.minAssurance) && receipt.routeDecision) {
    const selectedAssurance = receipt.routeDecision.selectedAssurance;
    if (!Number.isSafeInteger(selectedAssurance) || selectedAssurance < policy.minAssurance) {
      throw new DeliveryProofValidationError(`receipt policy requires assurance >= ${policy.minAssurance}`);
    }
  }
  if (typeof policy.expectedVerifier === 'string' && receipt.verdict?.verifier !== policy.expectedVerifier) {
    throw new DeliveryProofValidationError(`receipt policy expected verifier ${policy.expectedVerifier}`);
  }
  if (typeof policy.expectedRailId === 'string' && receipt.railId !== policy.expectedRailId) {
    throw new DeliveryProofValidationError(`receipt policy expected railId ${policy.expectedRailId}`);
  }
  if (policy.requireNonceRegistry === true && typeof receipt.nonceRegistryKey !== 'string') {
    throw new DeliveryProofValidationError('receipt policy requires nonceRegistryKey');
  }
  return true;
}

function receiptDecisionMatchesVerdict(receipt) {
  if (receipt.decision === 'release') return receipt.verdict?.ok === true;
  if (receipt.decision === 'refund') return receipt.verdict?.ok === false;
  return false;
}

function assertSettlementKeypair(settlementKey) {
  const message = 'deliveryproof.settlement-key.self-test';
  try {
    const signature = sign(settlementKey.privateKey, message);
    if (!verify(settlementKey.publicKey, message, signature)) {
      throw new Error('public/private key mismatch');
    }
  } catch (err) {
    throw new DeliveryProofConfigurationError(`settle: settlementKey public/private keypair is invalid: ${err.message}`);
  }
}

function assertRouteDecisionMatchesVerifier(routeDecision, verifier) {
  if (routeDecision === null || routeDecision === undefined) return;
  if (typeof routeDecision !== 'object' || Array.isArray(routeDecision)) {
    throw new DeliveryProofConfigurationError('settle: routeDecision must be an object or null');
  }
  if (typeof routeDecision.selected !== 'string' || routeDecision.selected.length === 0) {
    throw new DeliveryProofConfigurationError('settle: routeDecision.selected must be a non-empty string');
  }
  if (routeDecision.selected !== verifier.name) {
    throw new DeliveryProofConfigurationError(
      `settle: routeDecision selected ${routeDecision.selected} but verifier is ${verifier.name ?? 'unknown'}`,
    );
  }
}

function assertRailMatchesContract(contract, rail) {
  if (typeof rail.id === 'string' && rail.id.length > 0 && contract.railId !== rail.id) {
    throw new DeliveryProofConfigurationError(
      `settle: contract.railId ${contract.railId} does not match rail adapter ${rail.id}`,
    );
  }
}

function validateReceiptForVerify(receipt) {
  try {
    assertReceipt(receipt);
    return true;
  } catch {
    return false;
  }
}

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
// Leaf module (imports nothing) holding the TRUSTED verifier capability table.
// The engine re-derives a routeDecision's assurance from it before signing, so
// a caller cannot have the engine sign an assurance claim it made up.
import { VERIFIER_PROFILES, ASSURANCE_NAMES, deriveComposeProfile } from '../router/profiles.mjs';
// Imported for OBJECT-IDENTITY comparison only — never to select or run a
// verifier (the verifier is always injected; see settle()). Identity is what
// stops an arbitrary object named `dataset` from inheriting `dataset` assurance.
import { verifiers as builtInVerifiers } from '../verifiers/index.mjs';

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
  if (!settlementKey || !settlementKey.publicKey || !settlementKey.privateKey) {
    throw new DeliveryProofConfigurationError('settle: settlementKey { publicKey, privateKey } (PEM) is required');
  }
  // Bind the verifier's method NOW, before any seller code has run.
  //
  // `verifier.verify` was previously resolved at call time — after
  // produceEvidence(). A seller could therefore pass the identity check with the
  // real verifier and then, from inside its own producer, assign
  // `datasetVerifier.verify = () => ({ ok: true })` before the lookup happened.
  // The built-ins are frozen, which closes that for them; binding here closes it
  // for CUSTOM verifiers too, and does not depend on anyone remembering to freeze.
  const boundVerify = verifier.verify.bind(verifier);

  // Deep-CLONE then deep-FREEZE. The same object reference is handed to
  // rail.authorize(), then to produceEvidence() (the SELLER'S code), and only
  // then to verifier.verify(). Without this, a malicious producer mutates the
  // predicate it was handed — weakening it — and the verifier checks the WEAKENED
  // terms while contractHash still commits to the original. The receipt would
  // attest to terms nobody verified. Cloning first means freezing cannot reach
  // back into the caller's own object; freezing means a mutation attempt throws
  // and lands in the catch below as a failed delivery -> refund.
  const normalizedContract = deepFreeze(structuredClone({ protocolVersion: PROTOCOL_VERSION, ...contract }));
  assertContract(normalizedContract);
  // Normalize the routeDecision to plain own data properties BEFORE validating
  // it, and sign that same normalized value. Otherwise the value validated here
  // (which follows getters and the prototype chain) is not the value
  // canonicalize() signs (own enumerable data properties only) — so a getter
  // could return a legal assurance during validation and something else to a
  // downstream policy read.
  const safeRouteDecision = normalizeRouteDecision(routeDecision);
  // Runs after normalization because a `compose` routeDecision's assurance is
  // re-derived from the contract's child predicates.
  assertRouteDecisionMatchesVerifier(safeRouteDecision, verifier, normalizedContract);
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
    const { signal, expired, cancel } = makeAbortSignal(normalizedContract, readNow);
    mark('delivery-started');
    let produced;
    try {
      // Race the deadline. A cooperative producer observes `signal` and returns;
      // an uncooperative one is abandoned here rather than holding the buyer's
      // funds open indefinitely. Either way the catch below turns it into a
      // negative verdict and the hold is refunded.
      const delivery = produceEvidence(normalizedContract, { signal });
      produced = expired ? await Promise.race([delivery, expired]) : await delivery;
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
    verdict = await boundVerify(normalizedContract, evidence, { now: readNow });
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
    routeDecision: safeRouteDecision,
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
  // `< 0` not `<= 0`: epoch 0 is a VALID timestamp that the schema accepts, and
  // treating it as "no deadline" silently disabled SLA enforcement entirely —
  // a never-resolving producer then held the buyer's funds forever.
  if (!Number.isFinite(contract.createdAt) || contract.createdAt < 0) return;
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
    return { signal: controller.signal, expired: null, cancel: () => {} };
  }
  // See enforceDeadline: epoch 0 is valid, and must not disable the deadline.
  if (!Number.isFinite(contract.createdAt) || contract.createdAt < 0) {
    return { signal: controller.signal, expired: null, cancel: () => {} };
  }
  const remaining = Math.max(0, contract.createdAt + deadlineMs - now());
  // `expired` is what actually ENFORCES the deadline. Aborting the signal only
  // *asks* the producer to stop; a producer that ignores its AbortSignal would
  // otherwise leave settle() pending forever with the buyer's money held. The
  // caller races this promise against produceEvidence so an unresponsive seller
  // becomes a failed delivery (negative verdict -> refund), not a stranded hold.
  let timer;
  const expired = new Promise((_resolve, reject) => {
    timer = setTimeout(() => {
      const err = new Error('SLA deadline exceeded during delivery');
      controller.abort(err);
      reject(err);
    }, remaining);
    timer.unref?.();
  });
  // Nothing observes `expired` unless the race does; keep Node from treating a
  // post-cancel rejection as unhandled.
  expired.catch(() => {});
  return { signal: controller.signal, expired, cancel: () => clearTimeout(timer) };
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
 *   expectedPolicyHash?: string,
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
  if (policy.allowFallback === false && ownProp(receipt.routeDecision, 'fallbackUsed') === true) {
    throw new DeliveryProofValidationError('receipt policy disallows verifier fallback');
  }
  if (Number.isSafeInteger(policy.minAssurance)) {
    // A receipt with NO routeDecision carries no assurance claim at all, so it
    // cannot satisfy an assurance floor. Previously this branch was skipped when
    // routeDecision was absent, which meant the weakest possible receipt passed
    // the strictest possible policy.
    if (!receipt.routeDecision || typeof receipt.routeDecision !== 'object') {
      throw new DeliveryProofValidationError(
        `receipt policy requires assurance >= ${policy.minAssurance} but the receipt carries no routeDecision`,
      );
    }
    const selectedAssurance = ownProp(receipt.routeDecision, 'selectedAssurance');
    if (!Number.isSafeInteger(selectedAssurance) || selectedAssurance < policy.minAssurance) {
      throw new DeliveryProofValidationError(`receipt policy requires assurance >= ${policy.minAssurance}`);
    }
  }
  if (typeof policy.expectedPolicyHash === 'string') {
    // Pin the exact router policy that produced this decision. Without this, a
    // receipt routed under a permissive policy is indistinguishable from one
    // routed under the strict policy the consumer believes was in force.
    const carried = ownProp(receipt.routeDecision, 'policyHash');
    if (carried !== policy.expectedPolicyHash) {
      throw new DeliveryProofValidationError(
        `receipt policy expected policyHash ${policy.expectedPolicyHash} but receipt carries ` +
          `${carried ?? 'none'}`,
      );
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

/**
 * Read an OWN data property, ignoring the prototype chain.
 *
 * Policy decisions must be made from what the receipt actually SIGNED.
 * canonicalize() serializes own enumerable properties, so anything reached
 * through the prototype chain is, by definition, not in the signed bytes. A
 * polluted Object.prototype otherwise let a receipt whose signed routeDecision
 * was `{}` — carrying no assurance claim at all — satisfy `minAssurance: 3`.
 *
 * @param {*} obj
 * @param {string} key
 * @returns {*} the own value, or undefined
 */
function ownProp(obj, key) {
  if (obj === null || typeof obj !== 'object') return undefined;
  return Object.hasOwn(obj, key) ? obj[key] : undefined;
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

/**
 * Recursively freeze an object graph in place. Safe only on a value we own —
 * always clone first, or freezing would reach into the caller's object.
 * @template T
 * @param {T} value
 * @returns {T}
 */
function deepFreeze(value) {
  if (value === null || typeof value !== 'object') return value;
  Object.freeze(value);
  for (const key of Object.keys(value)) deepFreeze(value[key]);
  return value;
}

/**
 * Reduce a caller-supplied routeDecision to plain own DATA properties.
 *
 * structuredClone drops the prototype and materializes getters into fixed
 * values, so the object validated here is byte-identical to the one signed.
 * Without it, validation reads through getters and the prototype chain while
 * canonicalize() serializes only own enumerable data properties — meaning the
 * checked value and the signed value can differ.
 *
 * @param {*} routeDecision
 * @returns {Object|null}
 */
function normalizeRouteDecision(routeDecision) {
  if (routeDecision === null || routeDecision === undefined) return null;
  if (typeof routeDecision !== 'object' || Array.isArray(routeDecision)) {
    throw new DeliveryProofConfigurationError('settle: routeDecision must be an object or null');
  }
  let normalized;
  try {
    normalized = structuredClone({ ...routeDecision });
  } catch (err) {
    throw new DeliveryProofConfigurationError(
      `settle: routeDecision must be plain cloneable data: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
  // Prove it can be SIGNED, here, before any money moves.
  //
  // structuredClone happily preserves values canonicalize() rejects — Infinity,
  // BigInt, Date, Map. Without this check such a routeDecision passed validation,
  // the rail authorized a hold, the seller delivered, and canonicalize() then threw
  // during receipt signing — which happens AFTER the delivery try/catch. The
  // result was a stranded hold: buyer's funds locked, no receipt, no capture, no
  // refund. Failing here costs the caller an error; failing there costs them money.
  try {
    canonicalize(normalized);
  } catch (err) {
    throw new DeliveryProofConfigurationError(
      `settle: routeDecision must be canonicalizable protocol JSON (it is signed into the receipt): ` +
        `${err instanceof Error ? err.message : String(err)}`,
    );
  }
  return normalized;
}

function assertRouteDecisionMatchesVerifier(routeDecision, verifier, contract) {
  if (routeDecision === null || routeDecision === undefined) return;
  if (typeof routeDecision !== 'object' || Array.isArray(routeDecision)) {
    throw new DeliveryProofConfigurationError('settle: routeDecision must be an object or null');
  }
  if (typeof routeDecision.selected !== 'string' || routeDecision.selected.length === 0) {
    throw new DeliveryProofConfigurationError('settle: routeDecision.selected must be a non-empty string');
  }
  const selected = ownProp(routeDecision, 'selected');
  // Name equality OR registry identity. The identity arm exists for deprecated
  // aliases: `testsuite` and `builtin-replay` are the same frozen object, so a
  // legacy route selecting `testsuite` is legitimate even though the object's
  // own name is `builtin-replay`. Identity is the stronger claim anyway — if the
  // registry maps this key to exactly this object, the key names this verifier.
  if (selected !== verifier.name && builtInVerifiers[selected] !== verifier) {
    throw new DeliveryProofConfigurationError(
      `settle: routeDecision selected ${selected} but verifier is ${verifier.name ?? 'unknown'}`,
    );
  }
  // The engine SIGNS this routeDecision into the receipt, and downstream policy
  // (assertReceiptMeetsPolicy) makes release decisions from its assurance
  // number. So the number must come from the trusted profile table, never from
  // the caller: otherwise an assurance-1 `schema` verifier can be settled with a
  // hand-written `selectedAssurance: 99` and satisfy a `minAssurance: 3` policy.
  // A signed lie is still a lie — tamper-EVIDENT is not the same as CHECKED.
  // `compose` is special: the router derives its assurance from the child
  // verifiers named in the contract predicate, not from the placeholder row in
  // the table. Re-derive it the same way rather than exempting it from checking.
  // Own-property reads here too: the validated value must be the signed value.
  const profile = ownProp(routeDecision, 'selected') === 'compose'
    ? deriveComposeProfile(contract)
    : VERIFIER_PROFILES[routeDecision.selected];
  // The profile table is keyed by NAME, so name equality alone lets any injected
  // object called `dataset` inherit the protocol's dataset assurance. Require
  // OBJECT IDENTITY with the built-in registry entry before signing a
  // protocol-defined assurance. A custom verifier may still run — it just may
  // not wear a protocol assurance number it did not earn.
  const isBuiltIn = builtInVerifiers[routeDecision.selected] === verifier;
  if (profile && isBuiltIn) {
    assertClaimMatchesProfile(routeDecision, 'selectedAssurance', profile.assurance);
    assertClaimMatchesProfile(routeDecision, 'selectedAssuranceName', ASSURANCE_NAMES[profile.assurance]);
  } else if (ownProp(routeDecision, 'selectedAssurance') !== undefined
             || ownProp(routeDecision, 'selectedAssuranceName') !== undefined) {
    // Either no trusted profile exists for this kind, or one does but the
    // verifier is not the built-in that earned it. Both are unverifiable
    // assurance claims, and the engine will not sign one.
    throw new DeliveryProofConfigurationError(
      profile
        ? `settle: routeDecision.selected "${routeDecision.selected}" names a built-in verifier, but the ` +
          'supplied verifier is not that built-in. A custom verifier may not inherit a protocol assurance ' +
          'level by reusing its name. Omit selectedAssurance, or supply the built-in verifier.'
        : `settle: cannot verify routeDecision.selectedAssurance for "${routeDecision.selected}" — ` +
          'no trusted verifier profile exists. Pass a routeDecision produced by routeVerifier(), or omit selectedAssurance.',
    );
  }
  const fallbackUsed = ownProp(routeDecision, 'fallbackUsed');
  if (fallbackUsed !== undefined && typeof fallbackUsed !== 'boolean') {
    throw new DeliveryProofConfigurationError('settle: routeDecision.fallbackUsed must be a boolean when present');
  }
}

/**
 * @param {Object} routeDecision
 * @param {string} field
 * @param {*} trusted
 */
function assertClaimMatchesProfile(routeDecision, field, trusted) {
  const claimed = ownProp(routeDecision, field);
  if (claimed === undefined) return;
  if (claimed !== trusted) {
    throw new DeliveryProofConfigurationError(
      `settle: routeDecision.${field} claims ${JSON.stringify(claimed)} but the trusted profile for ` +
        `"${routeDecision.selected}" is ${JSON.stringify(trusted)}. Refusing to sign a false assurance claim.`,
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

// src/mcp/paidToolWithDeliveryProof.mjs
//
// Models an MCP paid tool whose payment releases ONLY on verified delivery.
//
// A normal "paid MCP tool" (or paid HTTP endpoint) proves the caller was ALLOWED
// to pay, then runs and returns output. DeliveryProof inverts the trust: the
// seller's tool runs to PRODUCE EVIDENCE, the evidence is verified against an
// explicit delivery predicate, and only a passing verdict captures the payment.
// A failing verdict refunds the buyer. There is no code path here that pays the
// seller without a passing verdict — that gate lives in settle().
//
// Local wrapper only: no network server, SDK dependency, or hosted service.

import { settle } from '../engine/deliveryproof.mjs';
import { createNonceRegistry } from '../engine/nonce-registry.mjs';
import { sha256hex } from '../protocol/canonical.mjs';
import { clockFrom } from '../protocol/runtime.mjs';

/**
 * Wrap a seller tool so its payment settles only on verified delivery.
 *
 * @param {object} args
 * @param {(input: any) => Promise<any> | any} args.tool
 *   The seller's MCP tool / paid endpoint: maps an input to an output (the
 *   deliverable). May be sync or async.
 * @param {(args: { input: any, contract: import('../protocol/types.mjs').DeliveryContract, output: any }) => (Partial<import('../protocol/types.mjs').DeliveryEvidence> | Promise<Partial<import('../protocol/types.mjs').DeliveryEvidence>>)} [args.makeEvidence]
 *   Optional evidence hook. Use this when a verifier needs proof material in
 *   addition to raw output, such as transcript signatures, TEE quotes, zkTLS
 *   proofs, logs, or other attestations. The wrapper still binds contractId,
 *   nonce, and outputHash through settle().
 * @param {(input: any) => import('../protocol/types.mjs').DeliveryContract} args.makeContract
 *   Builds the DeliveryContract for a given call input. The contract carries the
 *   predicate, price, nonce, rail id, etc. — i.e. what "delivered" means.
 * @param {import('../protocol/types.mjs').Verifier} args.verifier
 *   The verifier that turns evidence into a Verdict (objective Tier-A here).
 * @param {import('../protocol/types.mjs').RailAdapter} args.rail
 *   The settlement rail (authorize/capture/refund/status).
 * @param {{ publicKey: string, privateKey: string }} args.settlementKey
 *   PEM keypair of the settlement authority that signs the DeliveryReceipt.
 * @param {Object|false|null} [args.nonceRegistry]
 *   Replay registry. Defaults to an in-memory registry for this wrapper
 *   instance; pass false/null only for tests or explicitly replay-tolerant demos.
 * @param {Object|((contract: import('../protocol/types.mjs').DeliveryContract) => Object|null)} [args.routeDecision]
 *   Optional signed routing decision. Strict production wrappers can require it.
 * @param {boolean} [args.strictRouting]
 *   When true, reject calls that do not provide a routeDecision.
 * @param {boolean} [args.allowOutputOverride]
 *   Defaults false. When false, makeEvidence may add proof material but may not
 *   replace the raw tool output that DeliveryProof verifies.
 * @param {() => number} [args.now]
 *   Optional clock for deterministic tests.
 * @returns {(input: any) => Promise<{
 *   contract: import('../protocol/types.mjs').DeliveryContract,
 *   evidence: import('../protocol/types.mjs').DeliveryEvidence,
 *   verdict: import('../protocol/types.mjs').Verdict,
 *   receipt: import('../protocol/types.mjs').DeliveryReceipt,
 *   hold: import('../protocol/types.mjs').Hold
 * }>}
 *   An async function: given a call input, builds the contract, runs the tool to
 *   produce evidence, verifies it, and settles. Resolves to the full
 *   settle-result { contract, evidence, verdict, receipt, hold }.
 */
export function paidToolWithDeliveryProof({
  tool,
  makeContract,
  makeEvidence,
  verifier,
  rail,
  settlementKey,
  nonceRegistry = createNonceRegistry(),
  routeDecision = null,
  strictRouting = false,
  allowOutputOverride = false,
  now: nowOption,
}) {
  const now = clockFrom({ now: nowOption });
  const replayRegistry = nonceRegistry === false ? null : nonceRegistry;
  if (typeof tool !== 'function') {
    throw new TypeError('paidToolWithDeliveryProof: tool must be a function (input) => output');
  }
  if (typeof makeContract !== 'function') {
    throw new TypeError('paidToolWithDeliveryProof: makeContract must be a function (input) => contract');
  }
  if (makeEvidence !== undefined && typeof makeEvidence !== 'function') {
    throw new TypeError('paidToolWithDeliveryProof: makeEvidence must be a function when provided');
  }
  if (!verifier || typeof verifier.verify !== 'function') {
    throw new TypeError('paidToolWithDeliveryProof: verifier must implement verify(contract, evidence)');
  }
  if (!rail || typeof rail.authorize !== 'function') {
    throw new TypeError('paidToolWithDeliveryProof: rail must be a RailAdapter');
  }
  if (!settlementKey || !settlementKey.publicKey || !settlementKey.privateKey) {
    throw new TypeError('paidToolWithDeliveryProof: settlementKey must be a { publicKey, privateKey } PEM pair');
  }
  if (replayRegistry !== null && (!replayRegistry || typeof replayRegistry.reserve !== 'function')) {
    throw new TypeError('paidToolWithDeliveryProof: nonceRegistry must implement reserve/mark or be false/null');
  }
  if (routeDecision !== null && routeDecision !== undefined && typeof routeDecision !== 'object' && typeof routeDecision !== 'function') {
    throw new TypeError('paidToolWithDeliveryProof: routeDecision must be an object, function, or null');
  }
  if (typeof allowOutputOverride !== 'boolean') {
    throw new TypeError('paidToolWithDeliveryProof: allowOutputOverride must be boolean when provided');
  }

  return async function paidCall(input) {
    // Build the per-call contract: this declares the delivery predicate, price,
    // nonce, and rail the settlement is bound to.
    const contract = makeContract(input);
    if (!contract || typeof contract !== 'object') {
      throw new TypeError('paidToolWithDeliveryProof: makeContract must return a DeliveryContract object');
    }
    const selectedRouteDecision = typeof routeDecision === 'function'
      ? routeDecision(contract)
      : routeDecision;
    if (strictRouting && (selectedRouteDecision === null || selectedRouteDecision === undefined)) {
      throw new TypeError('paidToolWithDeliveryProof: strictRouting requires a routeDecision');
    }

    // Adapt the seller tool into a produceEvidence(contract) function. We run the
    // tool to get its output (the deliverable), then package it as Delivery
    // evidence bound to the contract's nonce, with the output hash precomputed.
    // If makeEvidence is supplied, it can add verifier-specific material such as
    // transcript signatures while keeping the raw tool output path unambiguous.
    // settle() re-normalizes outputHash/nonce/contractId, so this stays canonical
    // even if a tool returned a pre-shaped evidence-like object.
    const produceEvidence = async (boundContract) => {
      const output = await tool(input);
      const extra = makeEvidence
        ? await makeEvidence({ input, contract: boundContract, output })
        : {};
      if (extra !== undefined && (extra === null || typeof extra !== 'object')) {
        throw new TypeError('paidToolWithDeliveryProof: makeEvidence must return an object when provided');
      }
      const overridesOutput = extra && Object.prototype.hasOwnProperty.call(extra, 'output');
      if (overridesOutput && !allowOutputOverride) {
        throw new TypeError('paidToolWithDeliveryProof: makeEvidence may not override output unless allowOutputOverride is true');
      }
      const finalOutput = overridesOutput ? extra.output : output;
      return {
        ...extra,
        contractId: boundContract.id,
        nonce: boundContract.nonce,
        output: finalOutput,
        outputHash: sha256hex(finalOutput),
        producedAt: extra?.producedAt ?? now(),
      };
    };

    // settle() runs the full verified-delivery state machine:
    //   authorize -> produceEvidence -> verify -> decide -> sign receipt ->
    //   capture (release) on verdict.ok, else refund.
    // The pay-only-on-verified-delivery guarantee is enforced inside settle().
    return settle({
      contract,
      produceEvidence,
      verifier,
      rail,
      settlementKey,
      routeDecision: selectedRouteDecision ?? null,
      nonceRegistry: replayRegistry,
      now,
    });
  };
}

/**
 * Mock escrow RailAdapter for DeliveryProof.
 *
 * This is the pluggable SETTLEMENT SEAM. In production this same RailAdapter
 * interface is implemented by a real settlement rail:
 *   - Coinbase x402   (authorize = sign payment authz / open channel; capture = settle on-chain; refund = release/no-capture)
 *   - Stripe MPP      (authorize = PaymentIntent w/ manual capture hold; capture = capture(); refund = cancel/refund())
 *   - Google AP2      (authorize = bind mandate; capture = execute mandate; refund = void mandate)
 *
 * Here we keep everything in-memory and deterministic so the PoC runs with
 * plain `node` with local process state. The escrow enforces
 * a strict state machine so that NO code path can pay the seller (capture)
 * unless the signed DeliveryReceipt says decision === 'release'. The verifier
 * gates settlement upstream; this rail re-enforces it at the money layer.
 *
 *   State machine:
 *
 *        authorize()                  capture(receipt.decision==='release')
 *     ─────────────►  held  ──────────────────────────────────────────►  captured  (terminal: seller paid)
 *                       │
 *                       │  refund(receipt.decision==='refund')
 *                       └──────────────────────────────────────────────►  refunded  (terminal: buyer refunded)
 *
 *   'captured' and 'refunded' are terminal. Re-capturing, re-funding, or
 *   crossing transitions throws.
 *
 * @typedef {import('../protocol/types.mjs').RailAdapter} RailAdapter
 * @typedef {import('../protocol/types.mjs').Hold} Hold
 * @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract
 * @typedef {import('../protocol/types.mjs').DeliveryReceipt} DeliveryReceipt
 */

import { randomUUID } from 'node:crypto';
import { sha256hex } from '../protocol/canonical.mjs';
import { clockFrom } from '../protocol/runtime.mjs';
import { verifyReceipt } from '../engine/deliveryproof.mjs';
import { emitAudit, normalizeAuditSink, normalizeLogger, logBoundary } from '../operability/index.mjs';

/** Rail identifier for this adapter. */
const RAIL_ID = 'escrow-mock';

/**
 * Pull the short receipt reference recorded in hold history.
 * Mirrors the spec: receiptRef = receipt.signature.slice(0, 16).
 * Falls back gracefully if a receipt has no signature (defensive only).
 * @param {DeliveryReceipt} receipt
 * @returns {string}
 */
function receiptRefOf(receipt) {
  const sig = receipt && typeof receipt.signature === 'string' ? receipt.signature : '';
  return sig.slice(0, 16);
}

/**
 * Create an in-memory mock escrow RailAdapter.
 *
 * Each adapter instance owns its own private Map of holds, keyed by holdId,
 * so multiple rails (or test cases) never share state.
 *
 * @param {{ now?: () => number, audit?: import('../operability/index.mjs').AuditSink|Function|null, logger?: Object|Function|null|false, settlementPublicKey?: string, allowUnsignedReceipts?: boolean, requireSignature?: boolean }} [opts]
 *   settlementPublicKey is REQUIRED unless allowUnsignedReceipts is true.
 *   requireSignature is a deprecated no-op: verification is now the default.
 * @returns {RailAdapter & { id: string }}
 */
export function createMockEscrowRail(rawOpts = {}) {
  // Read options from a null-prototype OWN-property copy. Plain `opts.x` walks
  // the prototype chain, so a polluted Object.prototype elsewhere in the process
  // could inject `allowUnsignedReceipts: true` (disabling verification) or even a
  // `settlementPublicKey` the attacker holds the private half of — without the
  // caller passing either. Spreading own enumerable properties severs that.
  const opts = { __proto__: null, ...rawOpts };
  const now = clockFrom(opts);
  const auditSink = normalizeAuditSink(opts.audit);
  const logger = normalizeLogger(opts.logger, console);
  const settlementPublicKey = typeof opts.settlementPublicKey === 'string' ? opts.settlementPublicKey : null;
  // FAIL-CLOSED BY DEFAULT (v0.10). A settlement key is REQUIRED so every
  // terminalization verifies the receipt signature. Without one, the rail
  // authenticates nothing: a hand-crafted receipt carrying verdict.ok=true,
  // decision='release' and the six correct binding fields captures a hold with
  // no settlement private key involved at all. That was the pre-0.10 default.
  //
  // `allowUnsignedReceipts: true` restores the old behaviour for demos and
  // fixtures. It is deliberately loud: the name states the consequence.
  //
  // `requireSignature` is retained as a no-op alias — signature verification is
  // now the default, so setting it changes nothing.
  const allowUnsignedReceipts = opts.allowUnsignedReceipts === true;
  if (settlementPublicKey === null && !allowUnsignedReceipts) {
    throw new TypeError(
      'createMockEscrowRail: settlementPublicKey is required so terminalization verifies receipt signatures. ' +
        'Pass allowUnsignedReceipts: true to opt out — UNSAFE: without a key any forged receipt with matching ' +
        'binding fields can capture a hold.',
    );
  }
  /** @type {Map<string, Hold>} */
  const holds = new Map();
  /** @type {Map<string, { receiptHash: string, decision: 'release'|'refund' }>} */
  const terminals = new Map();

  /**
   * One-line transition trace, e.g.
   *   [escrow] hold 1a2b3c4d held->captured (amount 5 USDC)
   * @param {Hold} hold
   * @param {Hold['state']} from
   * @param {Hold['state']} to
   */
  function trace(hold, from, to) {
    // Show only a short prefix of the holdId to keep the line scannable.
    const shortId = String(hold.holdId).slice(0, 8);
    logBoundary(logger, 'log', `[escrow] hold ${shortId} ${from}->${to} (amount ${hold.amount} ${hold.currency})`);
  }

  /**
   * Look up a hold by its id or by a Hold object, and assert it belongs to
   * this rail instance. Callers may pass either a holdId string or the Hold
   * returned by authorize(); we always operate on the canonical stored copy.
   * @param {string | Hold} holdOrId
   * @returns {Hold}
   */
  function resolve(holdOrId) {
    const holdId =
      typeof holdOrId === 'string'
        ? holdOrId
        : holdOrId && typeof holdOrId === 'object'
          ? holdOrId.holdId
          : undefined;
    if (!holdId) {
      throw new Error('[escrow] missing holdId');
    }
    const hold = holds.get(holdId);
    if (!hold) {
      throw new Error(`[escrow] unknown hold ${holdId}`);
    }
    return hold;
  }

  return {
    id: RAIL_ID,

    /**
     * Open an escrow hold for a contract's price. The funds are "held":
     * neither the seller nor the buyer controls them until a signed receipt
     * drives capture (seller paid) or refund (buyer refunded).
     * @param {DeliveryContract} contract
     * @returns {Hold}
     */
    authorize(contract) {
      if (!contract || typeof contract !== 'object') {
        throw new Error('[escrow] authorize requires a contract');
      }
      if (!contract.price || typeof contract.price !== 'object') {
        throw new Error('[escrow] contract is missing price');
      }
      const at = now();
      /** @type {Hold} */
      const hold = {
        holdId: randomUUID(),
        contractId: contract.id,
        contractHash: sha256hex(contract),
        railId: RAIL_ID,
        amount: contract.price.amount,
        currency: contract.price.currency,
        state: 'held',
        history: [{ state: 'held', at }],
      };
      holds.set(hold.holdId, hold);
      // Trace the creation as a transition into 'held' (no prior state).
      logBoundary(logger, 'log', `[escrow] hold ${String(hold.holdId).slice(0, 8)} ->held (amount ${hold.amount} ${hold.currency})`);
      emitAudit(auditSink, 'rail.authorized', {
        railId: RAIL_ID,
        holdId: hold.holdId,
        contractId: contract.id,
      }, { now });
      return hold;
    },

    /**
     * Capture the hold — pay the seller. Only legal when the receipt's
     * decision is 'release' AND the hold is currently 'held'. This is the
     * critical money-safety guard: a failing verdict yields a 'refund' receipt,
     * which can never reach this path.
     * @param {string | Hold} holdOrId
     * @param {DeliveryReceipt} receipt
     * @returns {Hold}
     */
    capture(holdOrId, receipt) {
      const hold = resolve(holdOrId);
      if (!receipt || receipt.decision !== 'release') {
        throw new Error(
          `[escrow] refusing to capture hold ${hold.holdId}: receipt.decision must be 'release' (got ${
            receipt ? JSON.stringify(receipt.decision) : 'no receipt'
          })`,
        );
      }
      assertReceiptDecisionConsistent(receipt);
      assertReceiptMatchesHold(hold, receipt, 'release');
      assertReceiptSignature(receipt);
      const receiptHash = sha256hex(receipt);
      const prior = terminals.get(hold.holdId);
      if (prior) {
        if (prior.decision === 'release' && prior.receiptHash === receiptHash && hold.state === 'captured') {
          return hold;
        }
        throw new Error(`[escrow] conflicting terminal settlement for hold ${hold.holdId}`);
      }
      if (hold.state !== 'held') {
        throw new Error(
          `[escrow] cannot capture hold ${hold.holdId}: state is '${hold.state}', expected 'held'`,
        );
      }
      const from = hold.state;
      hold.state = 'captured';
      hold.history.push({ state: 'captured', at: now(), receiptRef: receiptRefOf(receipt) });
      terminals.set(hold.holdId, { receiptHash, decision: 'release' });
      trace(hold, from, 'captured');
      emitAudit(auditSink, 'rail.captured', { railId: RAIL_ID, holdId: hold.holdId, decision: receipt.decision }, { now });
      return hold;
    },

    /**
     * Refund the hold — return funds to the buyer. Only legal when the
     * receipt's decision is 'refund' AND the hold is currently 'held'.
     * @param {string | Hold} holdOrId
     * @param {DeliveryReceipt} receipt
     * @returns {Hold}
     */
    refund(holdOrId, receipt) {
      const hold = resolve(holdOrId);
      if (!receipt || receipt.decision !== 'refund') {
        throw new Error(
          `[escrow] refusing to refund hold ${hold.holdId}: receipt.decision must be 'refund' (got ${
            receipt ? JSON.stringify(receipt.decision) : 'no receipt'
          })`,
        );
      }
      assertReceiptDecisionConsistent(receipt);
      assertReceiptMatchesHold(hold, receipt, 'refund');
      assertReceiptSignature(receipt);
      const receiptHash = sha256hex(receipt);
      const prior = terminals.get(hold.holdId);
      if (prior) {
        if (prior.decision === 'refund' && prior.receiptHash === receiptHash && hold.state === 'refunded') {
          return hold;
        }
        throw new Error(`[escrow] conflicting terminal settlement for hold ${hold.holdId}`);
      }
      if (hold.state !== 'held') {
        throw new Error(
          `[escrow] cannot refund hold ${hold.holdId}: state is '${hold.state}', expected 'held'`,
        );
      }
      const from = hold.state;
      hold.state = 'refunded';
      hold.history.push({ state: 'refunded', at: now(), receiptRef: receiptRefOf(receipt) });
      terminals.set(hold.holdId, { receiptHash, decision: 'refund' });
      trace(hold, from, 'refunded');
      emitAudit(auditSink, 'rail.refunded', { railId: RAIL_ID, holdId: hold.holdId, decision: receipt.decision }, { now });
      return hold;
    },

    /**
     * Read the current hold record (canonical stored copy).
     * @param {string | Hold} holdOrId
     * @returns {Hold}
     */
    status(holdOrId) {
      return resolve(holdOrId);
    },

    health() {
      return { ok: true, railId: RAIL_ID, holds: holds.size, terminals: terminals.size };
    },
  };

  function assertReceiptSignature(receipt) {
    if (settlementPublicKey === null) {
      // Only reachable under an explicit allowUnsignedReceipts opt-out (the
      // constructor throws otherwise). Decision/verdict consistency and the
      // 7-field binding are still enforced above, but receipt AUTHENTICITY is
      // not checked on this path — so say so, loudly, on every terminalization.
      emitAudit(auditSink, 'rail.unsigned.accepted', {
        railId: RAIL_ID,
        holdId: receipt?.holdId ?? null,
        decision: receipt?.decision ?? null,
        reason: 'allowUnsignedReceipts is set; receipt signature was NOT verified',
      }, { now });
      return;
    }
    if (!verifyReceipt(receipt, settlementPublicKey)) {
      throw new Error('[escrow] receipt signature failed verification');
    }
  }
}

/**
 * Rail terminalization must only accept a receipt for the exact hold it is
 * settling. The engine signs these fields; the rail re-checks them before any
 * terminal state transition so a receipt cannot be replayed across holds.
 * @param {Hold & { contractHash?: string, railId?: string }} hold
 * @param {DeliveryReceipt} receipt
 * @param {'release'|'refund'} expectedDecision
 */
function assertReceiptMatchesHold(hold, receipt, expectedDecision) {
  const mismatches = [];
  if (receipt.decision !== expectedDecision) mismatches.push('decision');
  if (receipt.holdId !== hold.holdId) mismatches.push('holdId');
  if (receipt.contractId !== hold.contractId) mismatches.push('contractId');
  if (receipt.contractHash !== hold.contractHash) mismatches.push('contractHash');
  if (receipt.railId !== RAIL_ID) mismatches.push('railId');
  if (receipt.amount !== hold.amount) mismatches.push('amount');
  if (receipt.currency !== hold.currency) mismatches.push('currency');
  if (mismatches.length) {
    throw new Error(`[escrow] receipt does not match hold ${hold.holdId}: ${mismatches.join(', ')}`);
  }
}

/**
 * Re-enforce the engine's core money-safety invariant at the rail layer: a
 * receipt's settlement decision MUST agree with its verdict — release iff
 * verdict.ok===true, refund iff verdict.ok===false. This blocks a forged,
 * internally contradictory receipt (e.g. decision='release' with
 * verdict.ok=false) from capturing a hold even when signature verification is
 * not configured, so "no capture when verdict.ok !== true" holds at the money
 * layer and not only inside settle().
 * @param {DeliveryReceipt} receipt
 */
function assertReceiptDecisionConsistent(receipt) {
  const verdict = receipt && receipt.verdict;
  if (!verdict || typeof verdict.ok !== 'boolean') {
    throw new Error('[escrow] receipt is missing a boolean verdict.ok');
  }
  const expected = verdict.ok ? 'release' : 'refund';
  if (receipt.decision !== expected) {
    throw new Error(`[escrow] receipt decision '${receipt.decision}' contradicts verdict.ok=${verdict.ok} (expected '${expected}')`);
  }
}

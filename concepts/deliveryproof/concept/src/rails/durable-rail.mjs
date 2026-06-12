// Durable local RailAdapter with idempotency and append-only JSONL recovery.
//
// This adapter is deliberately scoped: it gives DeliveryProof exactly-once LOCAL
// terminalization across process restarts for a mock hold ledger. It does not
// claim universal exactly-once money movement across an external payment rail;
// a production adapter would carry these idempotency keys into Stripe/x402/AP2.

import { appendFileSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { randomUUID } from 'node:crypto';
import { sha256hex } from '../protocol/canonical.mjs';
import { assertNoPrototypePollutionKeys, clockFrom } from '../protocol/runtime.mjs';
import { verifyReceipt } from '../engine/deliveryproof.mjs';
import { emitAudit, normalizeAuditSink } from '../operability/index.mjs';

/** @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('../protocol/types.mjs').DeliveryReceipt} DeliveryReceipt */
/** @typedef {import('../protocol/types.mjs').Hold} Hold */
/** @typedef {import('../protocol/types.mjs').RailAdapter} RailAdapter */

const RAIL_ID = 'escrow-durable';

/**
 * @param {Object} args
 * @param {string} args.logPath Append-only JSONL write-ahead log path.
 * @param {() => number} [args.now] Optional clock for deterministic tests.
 * @param {import('../operability/index.mjs').AuditSink|Function|null} [args.audit] Optional best-effort audit sink.
 * @param {string} [args.settlementPublicKey] Optional key that makes direct
 *   rail terminalization verify receipt signatures before changing state.
 * @returns {RailAdapter & { id: string, compact: () => void, flush: () => true, close: () => {closed:true}, health: () => Object, _debugState: () => Object }}
 */
export function createDurableEscrowRail({ logPath, now: nowOption, audit = null, settlementPublicKey = null, requireSignature = false } = {}) {
  const now = clockFrom({ now: nowOption });
  const auditSink = normalizeAuditSink(audit);
  if (!logPath || typeof logPath !== 'string') {
    throw new TypeError('createDurableEscrowRail: logPath is required');
  }
  // Opt-in fail-closed mode for production (mirrors createMockEscrowRail).
  if (requireSignature === true && (settlementPublicKey === null || settlementPublicKey === undefined)) {
    throw new TypeError('createDurableEscrowRail: requireSignature is set but no settlementPublicKey was provided');
  }
  mkdirSync(dirname(logPath), { recursive: true });
  let closed = false;

  /** @type {Map<string, Hold>} */
  const holds = new Map();
  /** @type {Map<string, { fingerprint: string, holdId: string }>} */
  const authorizations = new Map();
  /** @type {Map<string, { receiptHash: string, holdId: string, decision: string, hold: Hold }>} */
  const terminals = new Map();

  replayLog();

  return {
    id: RAIL_ID,

    /**
     * Authorize a durable hold. If contract.idempotencyKey is present, the same
     * key and same contract fingerprint returns the same recovered hold; the
     * same key with different contract terms rejects.
     * @param {DeliveryContract & { idempotencyKey?: string }} contract
     * @returns {Hold}
     */
    authorize(contract) {
      assertOpen('authorize');
      assertContractForRail(contract);
      const key = contract.idempotencyKey ?? `contract:${contract.id}`;
      const fingerprint = contractFingerprint(contract);
      const prior = authorizations.get(key);
      if (prior) {
        if (prior.fingerprint !== fingerprint) {
          throw new Error(`[durable-rail] idempotency conflict for authorize key ${key}`);
        }
        return cloneHold(requiredHold(holds, prior.holdId));
      }

      /** @type {Hold} */
      const hold = {
        holdId: randomUUID(),
        contractId: contract.id,
        contractHash: sha256hex(contract),
        railId: RAIL_ID,
        amount: contract.price.amount,
        currency: contract.price.currency,
        state: 'held',
        history: [{ state: 'held', at: now(), operationKey: key }],
      };
      appendRecord({ type: 'authorize', idempotencyKey: key, fingerprint, hold });
      applyAuthorize({ idempotencyKey: key, fingerprint, hold });
      emitAudit(auditSink, 'rail.authorized', {
        railId: RAIL_ID,
        holdId: hold.holdId,
        contractId: contract.id,
        idempotencyKey: key,
      }, { now });
      return cloneHold(hold);
    },

    /**
     * @param {string | Hold} holdOrId
     * @param {DeliveryReceipt & { settlementAttemptId?: string }} receipt
     * @returns {Hold}
     */
    capture(holdOrId, receipt) {
      assertOpen('capture');
      return terminalize(holdOrId, receipt, 'release', 'captured');
    },

    /**
     * @param {string | Hold} holdOrId
     * @param {DeliveryReceipt & { settlementAttemptId?: string }} receipt
     * @returns {Hold}
     */
    refund(holdOrId, receipt) {
      assertOpen('refund');
      return terminalize(holdOrId, receipt, 'refund', 'refunded');
    },

    /**
     * @param {string | Hold} holdOrId
     * @returns {Hold}
     */
    status(holdOrId) {
      return cloneHold(resolveHold(holdOrId));
    },

    compact() {
      assertOpen('compact');
      const snapshot = {
        type: 'snapshot',
        holds: Array.from(holds.values()),
        authorizations: Array.from(authorizations.entries()),
        terminals: Array.from(terminals.entries()),
      };
      writeFileSync(`${logPath}.tmp`, `${JSON.stringify(snapshot)}\n`, 'utf8');
      renameSync(`${logPath}.tmp`, logPath);
      emitAudit(auditSink, 'rail.compacted', { railId: RAIL_ID, holds: holds.size, terminals: terminals.size }, { now });
    },

    flush() {
      // All WAL writes are synchronous appendFileSync/writeFileSync calls. This
      // method gives operators a uniform shutdown hook without changing IO mode.
      emitAudit(auditSink, 'rail.flushed', { railId: RAIL_ID, closed }, { now });
      return true;
    },

    close() {
      if (!closed) {
        closed = true;
        emitAudit(auditSink, 'rail.closed', { railId: RAIL_ID }, { now });
      }
      return { closed: true };
    },

    health() {
      return {
        ok: true,
        railId: RAIL_ID,
        closed,
        holds: holds.size,
        authorizations: authorizations.size,
        terminals: terminals.size,
      };
    },

    _debugState() {
      return {
        holds: Array.from(holds.values()).map(cloneHold),
        authorizations: Array.from(authorizations.entries()),
        terminals: Array.from(terminals.entries()),
        closed,
      };
    },
  };

  function assertOpen(operation) {
    if (closed) throw new Error(`[durable-rail] cannot ${operation}: rail is closed`);
  }

  /**
   * @param {string | Hold} holdOrId
   * @param {DeliveryReceipt & { settlementAttemptId?: string }} receipt
   * @param {'release'|'refund'} expectedDecision
   * @param {'captured'|'refunded'} targetState
   */
  function terminalize(holdOrId, receipt, expectedDecision, targetState) {
    const hold = resolveHold(holdOrId);
    if (!receipt || receipt.decision !== expectedDecision) {
      throw new Error(`[durable-rail] refusing ${targetState}: receipt.decision must be ${expectedDecision}`);
    }
    assertReceiptDecisionConsistent(receipt);
    assertReceiptMatchesHold(hold, receipt, expectedDecision);
    assertReceiptSignature(receipt);
    const receiptHash = sha256hex(receipt);
    const operationKey = receipt.settlementAttemptId ?? `${hold.holdId}:${receipt.decision}:${receiptHash}`;
    const prior = terminals.get(operationKey);
    if (prior) {
      if (prior.holdId !== hold.holdId || prior.receiptHash !== receiptHash || prior.decision !== receipt.decision) {
        throw new Error(`[durable-rail] idempotency conflict for terminal key ${operationKey}`);
      }
      return cloneHold(prior.hold);
    }
    if (hold.state !== 'held') {
      const existing = Array.from(terminals.values()).find((t) => t.holdId === hold.holdId);
      if (existing && (existing.receiptHash !== receiptHash || existing.decision !== receipt.decision)) {
        throw new Error(`[durable-rail] conflicting terminal settlement for hold ${hold.holdId}`);
      }
      throw new Error(`[durable-rail] hold ${hold.holdId} is already ${hold.state}`);
    }

    const next = cloneHold(hold);
    next.state = targetState;
    next.history.push({
      state: targetState,
      at: now(),
      receiptRef: receiptRefOf(receipt),
      operationKey,
    });
    appendRecord({ type: 'terminal', operationKey, receiptHash, decision: receipt.decision, hold: next });
    applyTerminal({ operationKey, receiptHash, decision: receipt.decision, hold: next });
    emitAudit(auditSink, `rail.${targetState}`, {
      railId: RAIL_ID,
      holdId: next.holdId,
      decision: receipt.decision,
      operationKey,
    }, { now });
    return cloneHold(next);
  }

  function assertReceiptSignature(receipt) {
    if (settlementPublicKey === null || settlementPublicKey === undefined) {
      // Back-compat demo path; requireSignature forces a key at construction.
      // Decision/verdict consistency is still enforced above.
      return;
    }
    if (typeof settlementPublicKey !== 'string' || !verifyReceipt(receipt, settlementPublicKey)) {
      throw new Error('[durable-rail] receipt signature failed verification');
    }
  }

  /**
   * @param {*} record
   */
  function appendRecord(record) {
    appendFileSync(logPath, `${JSON.stringify(record)}\n`, 'utf8');
  }

  /**
   * @param {string | Hold} holdOrId
   */
  function resolveHold(holdOrId) {
    return requiredHold(holds, holdIdOf(holdOrId));
  }

  function replayLog() {
    let text = '';
    try {
      text = readFileSync(logPath, 'utf8');
    } catch (err) {
      if (err && err.code === 'ENOENT') return;
      throw err;
    }
    for (const [index, line] of text.split(/\n/).entries()) {
      if (!line.trim()) continue;
      let record;
      try {
        record = JSON.parse(line);
      } catch (err) {
        throw new Error(`[durable-rail] corrupt WAL line ${index + 1}: ${err.message}`);
      }
      try {
        assertNoPrototypePollutionKeys(record, `WAL line ${index + 1}`);
      } catch (err) {
        throw new Error(`[durable-rail] unsafe WAL line ${index + 1}: ${err.message}`);
      }
      applyRecord(record);
    }
  }

  /**
   * @param {*} record
   */
  function applyRecord(record) {
    if (record.type === 'snapshot') {
      holds.clear();
      authorizations.clear();
      terminals.clear();
      for (const hold of record.holds ?? []) holds.set(hold.holdId, cloneHold(hold));
      for (const [key, value] of record.authorizations ?? []) authorizations.set(key, value);
      for (const [key, value] of record.terminals ?? []) {
        terminals.set(key, { ...value, hold: cloneHold(value.hold) });
      }
      return;
    }
    if (record.type === 'authorize') {
      applyAuthorize(record);
      return;
    }
    if (record.type === 'terminal') {
      applyTerminal(record);
      return;
    }
    throw new Error(`[durable-rail] unknown WAL record type ${JSON.stringify(record.type)}`);
  }

  /**
   * @param {{ idempotencyKey: string, fingerprint: string, hold: Hold }} record
   */
  function applyAuthorize(record) {
    const existing = authorizations.get(record.idempotencyKey);
    if (existing && existing.fingerprint !== record.fingerprint) {
      throw new Error(`[durable-rail] WAL authorize conflict for key ${record.idempotencyKey}`);
    }
    authorizations.set(record.idempotencyKey, {
      fingerprint: record.fingerprint,
      holdId: record.hold.holdId,
    });
    holds.set(record.hold.holdId, cloneHold(record.hold));
  }

  /**
   * @param {{ operationKey: string, receiptHash: string, decision: string, hold: Hold }} record
   */
  function applyTerminal(record) {
    const existing = terminals.get(record.operationKey);
    if (existing && (existing.receiptHash !== record.receiptHash || existing.decision !== record.decision)) {
      throw new Error(`[durable-rail] WAL terminal conflict for key ${record.operationKey}`);
    }
    const current = holds.get(record.hold.holdId);
    if (current && current.state !== 'held' && current.state !== record.hold.state) {
      throw new Error(`[durable-rail] WAL conflicting terminal state for hold ${record.hold.holdId}`);
    }
    const next = cloneHold(record.hold);
    holds.set(next.holdId, next);
    terminals.set(record.operationKey, {
      receiptHash: record.receiptHash,
      holdId: next.holdId,
      decision: record.decision,
      hold: cloneHold(next),
    });
  }
}

/**
 * @param {DeliveryContract & { idempotencyKey?: string }} contract
 */
function assertContractForRail(contract) {
  if (!contract || typeof contract !== 'object') {
    throw new Error('[durable-rail] authorize requires a contract');
  }
  if (!contract.id || !contract.price || typeof contract.price !== 'object') {
    throw new Error('[durable-rail] contract is missing id or price');
  }
}

/**
 * @param {DeliveryContract & { idempotencyKey?: string }} contract
 */
function contractFingerprint(contract) {
  const { idempotencyKey, ...fingerprinted } = contract;
  return sha256hex(fingerprinted);
}

/**
 * @param {string | Hold} holdOrId
 */
function holdIdOf(holdOrId) {
  if (typeof holdOrId === 'string') return holdOrId;
  if (holdOrId && typeof holdOrId === 'object' && typeof holdOrId.holdId === 'string') {
    return holdOrId.holdId;
  }
  throw new Error('[durable-rail] missing holdId');
}

/**
 * @param {Map<string, Hold>} map
 * @param {string} holdId
 */
function requiredHold(map, holdId) {
  const hold = map.get(holdId);
  if (!hold) {
    throw new Error(`[durable-rail] unknown hold ${holdId}`);
  }
  return hold;
}

/**
 * @param {DeliveryReceipt} receipt
 */
function receiptRefOf(receipt) {
  const sig = receipt && typeof receipt.signature === 'string' ? receipt.signature : '';
  return sig.slice(0, 16);
}

/**
 * @param {Hold} hold
 * @returns {Hold}
 */
function cloneHold(hold) {
  return JSON.parse(JSON.stringify(hold));
}

/**
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
    throw new Error(`[durable-rail] receipt does not match hold ${hold.holdId}: ${mismatches.join(', ')}`);
  }
}

/**
 * Re-enforce the engine's core money-safety invariant at the rail layer: a
 * receipt's settlement decision MUST agree with its verdict — release iff
 * verdict.ok===true, refund iff verdict.ok===false. Blocks a forged, internally
 * contradictory receipt from terminalizing a hold even when signature
 * verification is not configured.
 * @param {DeliveryReceipt} receipt
 */
function assertReceiptDecisionConsistent(receipt) {
  const verdict = receipt && receipt.verdict;
  if (!verdict || typeof verdict.ok !== 'boolean') {
    throw new Error('[durable-rail] receipt is missing a boolean verdict.ok');
  }
  const expected = verdict.ok ? 'release' : 'refund';
  if (receipt.decision !== expected) {
    throw new Error(`[durable-rail] receipt decision '${receipt.decision}' contradicts verdict.ok=${verdict.ok} (expected '${expected}')`);
  }
}

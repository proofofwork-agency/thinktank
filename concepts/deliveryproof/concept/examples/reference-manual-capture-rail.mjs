#!/usr/bin/env node

// Reference manual-capture RailAdapter.
//
// This example is a MOCK adapter over a pure in-process gateway function. It
// performs no network calls, reads no secrets, and exists only to show how a
// real manual-capture payment adapter can be checked with the conformance suite.

import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { sha256hex } from '../src/protocol/canonical.mjs';
import { verifyReceipt } from '../src/engine/deliveryproof.mjs';
import { runRailConformance } from '../src/testing/rail-conformance.mjs';

const RAIL_ID = 'reference-manual-capture';

export function createReferenceManualCaptureRail({ settlementPublicKey = null } = {}) {
  const ledger = new Map();
  const terminals = new Map();

  function gateway(command, payload) {
    if (command === 'authorize') {
      const hold = {
        holdId: `ref_hold_${randomUUID()}`,
        contractId: payload.contract.id,
        contractHash: sha256hex(payload.contract),
        railId: RAIL_ID,
        amount: payload.contract.price.amount,
        currency: payload.contract.price.currency,
        state: 'held',
        history: [{ state: 'held', at: Date.now() }],
      };
      ledger.set(hold.holdId, hold);
      return clone(hold);
    }

    if (command === 'status') {
      return clone(requiredHold(payload.holdId));
    }

    if (command === 'terminalize') {
      const hold = requiredHold(payload.holdId);
      const receiptHash = sha256hex(payload.receipt);
      const prior = terminals.get(hold.holdId);
      if (prior) {
        if (prior.receiptHash === receiptHash && prior.targetState === payload.targetState) {
          return clone(hold);
        }
        throw new Error(`[reference-rail] conflicting terminal settlement for hold ${hold.holdId}`);
      }
      if (hold.state !== 'held') {
        throw new Error(`[reference-rail] hold ${hold.holdId} is already ${hold.state}`);
      }
      hold.state = payload.targetState;
      hold.history.push({ state: payload.targetState, at: Date.now(), receiptRef: payload.receipt.signature.slice(0, 16) });
      terminals.set(hold.holdId, { receiptHash, targetState: payload.targetState });
      return clone(hold);
    }

    throw new Error(`[reference-rail] unknown gateway command ${command}`);
  }

  function requiredHold(holdOrId) {
    const holdId = typeof holdOrId === 'string' ? holdOrId : holdOrId?.holdId;
    if (!holdId) throw new Error('[reference-rail] missing holdId');
    const hold = ledger.get(holdId);
    if (!hold) throw new Error(`[reference-rail] unknown hold ${holdId}`);
    return hold;
  }

  function terminalize(holdOrId, receipt, expectedDecision, targetState) {
    const hold = requiredHold(holdOrId);
    if (!receipt || receipt.decision !== expectedDecision) {
      throw new Error(`[reference-rail] refusing ${targetState}: receipt.decision must be ${expectedDecision}`);
    }
    assertReceiptMatchesHold(hold, receipt, expectedDecision);
    if (settlementPublicKey !== null && !verifyReceipt(receipt, settlementPublicKey)) {
      throw new Error('[reference-rail] receipt signature failed verification');
    }
    return gateway('terminalize', { holdId: hold.holdId, receipt, targetState });
  }

  return {
    id: RAIL_ID,
    authorize(contract) {
      if (!contract || typeof contract !== 'object') throw new Error('[reference-rail] authorize requires a contract');
      if (!contract.price || typeof contract.price !== 'object') throw new Error('[reference-rail] contract is missing price');
      return gateway('authorize', { contract });
    },
    capture(holdOrId, receipt) {
      return terminalize(holdOrId, receipt, 'release', 'captured');
    },
    refund(holdOrId, receipt) {
      return terminalize(holdOrId, receipt, 'refund', 'refunded');
    },
    status(holdOrId) {
      return gateway('status', { holdId: typeof holdOrId === 'string' ? holdOrId : holdOrId?.holdId });
    },
    health() {
      return { ok: true, railId: RAIL_ID, holds: ledger.size, terminals: terminals.size };
    },
  };
}

function assertReceiptMatchesHold(hold, receipt, expectedDecision) {
  const mismatches = [];
  if (receipt.decision !== expectedDecision) mismatches.push('decision');
  if (receipt.holdId !== hold.holdId) mismatches.push('holdId');
  if (receipt.contractId !== hold.contractId) mismatches.push('contractId');
  if (receipt.contractHash !== hold.contractHash) mismatches.push('contractHash');
  if (receipt.railId !== hold.railId) mismatches.push('railId');
  if (receipt.amount !== hold.amount) mismatches.push('amount');
  if (receipt.currency !== hold.currency) mismatches.push('currency');
  if (mismatches.length) {
    throw new Error(`[reference-rail] receipt does not match hold ${hold.holdId}: ${mismatches.join(', ')}`);
  }
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

async function main() {
  const result = await runRailConformance({
    createRail: ({ settlementPublicKey }) => createReferenceManualCaptureRail({ settlementPublicKey }),
  });
  for (const entry of result.cases) {
    console.log(`${entry.ok ? 'PASS' : 'FAIL'} ${entry.name}${entry.error ? `: ${entry.error}` : ''}`);
  }
  if (!result.ok) process.exitCode = 1;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await main();
}

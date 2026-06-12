// Milestone / partial-delivery composition.
//
// This module does NOT add fractional capture/refund to settle(). Instead it
// compiles a schedule into independent child contracts, settles each child with
// the normal verified-delivery engine, and aggregates child receipts. That keeps
// the core money-safety invariant simple: every unit of released money still has
// a normal DeliveryReceipt whose decision came from verdict.ok.

import { PROTOCOL_VERSION, sha256hex } from '../protocol/canonical.mjs';
import { clockFrom } from '../protocol/runtime.mjs';
import { settle, verifyReceipt } from './deliveryproof.mjs';

/**
 * @param {Object} schedule
 * @returns {Object[]}
 */
export function compileMilestoneContracts(schedule) {
  validateSchedule(schedule);
  const totalAmount = schedule.totalPrice.amount;
  const allocated = schedule.milestones.reduce((sum, m) => sum + m.price.amount, 0);
  if (allocated !== totalAmount) {
    throw new Error(`milestone prices must sum exactly to totalPrice.amount (${allocated} != ${totalAmount})`);
  }
  return schedule.milestones.map((m, index) => ({
    id: `${schedule.id}:m${index + 1}:${m.id}`,
    buyer: schedule.buyer,
    seller: schedule.seller,
    intent: `${schedule.intent} / milestone ${index + 1}: ${m.intent}`,
    deliverableType: m.deliverableType,
    predicate: m.predicate,
    price: m.price,
    sla: m.sla ?? schedule.sla,
    refundRule: schedule.refundRule ?? 'per-milestone-refund-on-fail',
    railId: schedule.railId,
    nonce: `${schedule.nonce}:m${index + 1}:${m.id}`,
    createdAt: schedule.createdAt,
    milestone: {
      scheduleId: schedule.id,
      milestoneId: m.id,
      index,
      count: schedule.milestones.length,
    },
  }));
}

/**
 * Settle every milestone independently and aggregate the child receipts.
 *
 * @param {Object} args
 * @param {Object} args.schedule
 * @param {(milestoneContract: Object, index: number) => (Object|Promise<Object>)} args.produceEvidence
 * @param {(milestoneContract: Object, index: number) => Object} args.selectVerifier
 * @param {(milestoneContract: Object, index: number) => Object} args.createRail
 * @param {{ publicKey: string, privateKey: string }} args.settlementKey
 * @param {Object} [args.nonceRegistry]
 * @param {() => number} [args.now]
 */
export async function settleMilestones({
  schedule,
  produceEvidence,
  selectVerifier,
  createRail,
  settlementKey,
  nonceRegistry = null,
  now = Date.now,
}) {
  const readNow = clockFrom({ now });
  if (typeof produceEvidence !== 'function') throw new TypeError('settleMilestones: produceEvidence function is required');
  if (typeof selectVerifier !== 'function') throw new TypeError('settleMilestones: selectVerifier function is required');
  if (typeof createRail !== 'function') throw new TypeError('settleMilestones: createRail function is required');
  const contracts = compileMilestoneContracts(schedule);
  const children = [];

  for (let index = 0; index < contracts.length; index++) {
    const contract = contracts[index];
    const result = await settle({
      contract,
      produceEvidence: () => produceEvidence(contract, index),
      verifier: selectVerifier(contract, index),
      rail: createRail(contract, index),
      settlementKey,
      nonceRegistry,
      now: readNow,
    });
    children.push({
      milestoneId: contract.milestone.milestoneId,
      contractId: result.contract.id,
      contractHash: result.receipt.contractHash,
      receiptHash: sha256hex(result.receipt),
      decision: result.receipt.decision,
      ok: result.verdict.ok,
      amount: result.receipt.amount,
      currency: result.receipt.currency,
      receipt: result.receipt,
    });
  }

  const releasedAmount = children
    .filter((c) => c.decision === 'release')
    .reduce((sum, c) => sum + c.amount, 0);
  const refundedAmount = children
    .filter((c) => c.decision === 'refund')
    .reduce((sum, c) => sum + c.amount, 0);
  const aggregate = {
    scheduleId: schedule.id,
    scheduleHash: sha256hex(schedule),
    childCount: children.length,
    currency: schedule.totalPrice.currency,
    totalAmount: schedule.totalPrice.amount,
    releasedAmount,
    refundedAmount,
    complete: children.every((c) => c.decision === 'release'),
    children,
  };
  if (releasedAmount + refundedAmount !== schedule.totalPrice.amount) {
    throw new Error('milestone accounting invariant failed: released + refunded != total');
  }
  return aggregate;
}

/**
 * Two modes:
 *   - verifyMilestoneAggregate(aggregate, key) proves each child receipt is
 *     valid and the aggregate's internal accounting matches those receipts.
 *   - verifyMilestoneAggregate(aggregate, key, { schedule }) additionally
 *     proves completeness and order: scheduleHash, childCount, milestone ids,
 *     child contract ids, and child contract hashes must match the contracts
 *     re-derived from the schedule. Use this schedule-bound mode when
 *     truncation/reordering/substitution is in scope.
 *
 * @param {Object} aggregate
 * @param {string} settlementPublicKey
 * @param {{ schedule?: Object }} [opts] Optional schedule-bound verification.
 */
export function verifyMilestoneAggregate(aggregate, settlementPublicKey, opts = {}) {
  if (!aggregate || typeof aggregate !== 'object' || !Array.isArray(aggregate.children)) return false;
  const schedule = opts?.schedule && typeof opts.schedule === 'object' ? opts.schedule : null;
  let expectedContracts = null;
  if (schedule !== null) {
    try {
      expectedContracts = compileMilestoneContracts(schedule);
    } catch {
      return false;
    }
    if (aggregate.scheduleHash !== sha256hex(schedule)) return false;
    if (aggregate.scheduleId !== schedule.id) return false;
    if (aggregate.childCount !== expectedContracts.length) return false;
  }
  if (aggregate.childCount !== aggregate.children.length) return false;

  let released = 0;
  let refunded = 0;
  for (const [index, child] of aggregate.children.entries()) {
    if (expectedContracts !== null) {
      const expectedContract = expectedContracts[index];
      if (!expectedContract) return false;
      const expectedContractHash = sha256hex({ protocolVersion: PROTOCOL_VERSION, ...expectedContract });
      if (child.milestoneId !== expectedContract.milestone.milestoneId) return false;
      if (child.contractId !== expectedContract.id) return false;
      if (child.contractHash !== expectedContractHash) return false;
      if (child.receipt?.contractId !== expectedContract.id) return false;
      if (child.receipt?.contractHash !== expectedContractHash) return false;
    }
    if (!verifyReceipt(child.receipt, settlementPublicKey)) return false;
    if (sha256hex(child.receipt) !== child.receiptHash) return false;
    if (child.decision !== child.receipt.decision) return false;
    if (child.amount !== child.receipt.amount) return false;
    if (child.currency !== child.receipt.currency) return false;
    if (child.decision === 'release') released += child.receipt.amount;
    else if (child.decision === 'refund') refunded += child.receipt.amount;
    else return false;
  }
  return (
    released === aggregate.releasedAmount &&
    refunded === aggregate.refundedAmount &&
    released + refunded === aggregate.totalAmount
  );
}

/**
 * @param {Object} schedule
 */
function validateSchedule(schedule) {
  if (!schedule || typeof schedule !== 'object') throw new TypeError('milestone schedule is required');
  for (const field of ['id', 'buyer', 'seller', 'intent', 'railId', 'nonce']) {
    if (typeof schedule[field] !== 'string' || schedule[field].length === 0) {
      throw new TypeError(`milestone schedule.${field} must be a non-empty string`);
    }
  }
  if (!schedule.totalPrice || typeof schedule.totalPrice.amount !== 'number' || !Number.isInteger(schedule.totalPrice.amount)) {
    throw new TypeError('milestone schedule.totalPrice.amount must be an integer amount');
  }
  if (typeof schedule.totalPrice.currency !== 'string' || schedule.totalPrice.currency.length === 0) {
    throw new TypeError('milestone schedule.totalPrice.currency is required');
  }
  if (!Array.isArray(schedule.milestones) || schedule.milestones.length === 0) {
    throw new TypeError('milestone schedule.milestones must be a non-empty array');
  }
  for (const [index, m] of schedule.milestones.entries()) {
    if (!m || typeof m !== 'object') throw new TypeError(`milestone ${index} must be an object`);
    if (typeof m.id !== 'string' || m.id.length === 0) throw new TypeError(`milestone ${index}.id is required`);
    if (!m.price || typeof m.price.amount !== 'number' || !Number.isInteger(m.price.amount)) {
      throw new TypeError(`milestone ${index}.price.amount must be an integer`);
    }
    if (m.price.currency !== schedule.totalPrice.currency) {
      throw new Error(`milestone ${index}.price.currency must match totalPrice.currency`);
    }
    if (!m.predicate || typeof m.predicate !== 'object') throw new TypeError(`milestone ${index}.predicate is required`);
  }
}

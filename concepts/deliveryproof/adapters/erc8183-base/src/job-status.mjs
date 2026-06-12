// src/job-status.mjs
// ERC-8183 Job lifecycle status <-> DeliveryProof Hold state mapping.
//
// SCOPE / HONESTY: pure enum + total mapping functions. NO contracts, NO wallet,
// NO RPC, NO keys, NO on-chain submission. ERC-8183 ("Agentic Commerce") models a
// Job with an escrowed budget whose lifecycle is:
//   Open -> Funded -> Submitted -> Completed | Rejected | Expired
// The DeliveryProof evaluator may act ONLY on a Submitted job. This module is the
// single source of truth for that lifecycle and for projecting a Job status onto
// the Hold state machine (held -> captured | refunded) the core protocol expects.
// TESTNET / LOCAL ONLY — no mainnet, no real funds, no autonomous live tx.

import { Erc8183RailError } from './errors.mjs';

/**
 * The complete, frozen ERC-8183 Job status enum.
 * @typedef {'Open'|'Funded'|'Submitted'|'Completed'|'Rejected'|'Expired'} JobStatusValue
 */
export const JobStatus = Object.freeze({
  Open: 'Open',
  Funded: 'Funded',
  Submitted: 'Submitted',
  Completed: 'Completed',
  Rejected: 'Rejected',
  Expired: 'Expired',
});

/** @type {ReadonlySet<string>} */
const KNOWN_STATUSES = new Set(Object.values(JobStatus));

/**
 * Map an ERC-8183 Job status to the DeliveryProof Hold state.
 *
 *   Open | Funded | Submitted -> 'held'      (escrow live, not yet terminalized)
 *   Completed                  -> 'captured'  (escrow released to provider)
 *   Rejected | Expired         -> 'refunded'  (escrow returned to client)
 *
 * Expired maps to 'refunded' because an expired ERC-8183 job returns its escrowed
 * budget to the client — the same money outcome as an explicit rejection.
 *
 * @param {JobStatusValue|string} status
 * @returns {'held'|'captured'|'refunded'}
 */
export function mapJobStatusToHoldState(status) {
  switch (status) {
    case JobStatus.Open:
    case JobStatus.Funded:
    case JobStatus.Submitted:
      return 'held';
    case JobStatus.Completed:
      return 'captured';
    case JobStatus.Rejected:
    case JobStatus.Expired:
      return 'refunded';
    default:
      throw new Erc8183RailError(
        `mapJobStatusToHoldState: unknown ERC-8183 job status ${JSON.stringify(status)}`,
      );
  }
}

/**
 * True only when a job is in a state the DeliveryProof evaluator may act on.
 * Per ERC-8183 the evaluator may call complete()/reject() ONLY on a Submitted
 * job; Open/Funded are not ready and terminal states are already settled.
 *
 * @param {JobStatusValue|string} status
 * @returns {boolean}
 */
export function isSettleable(status) {
  return status === JobStatus.Submitted;
}

/**
 * True when a job has reached a terminal ERC-8183 state and can no longer be
 * acted on by the evaluator (Completed, Rejected, or Expired).
 *
 * @param {JobStatusValue|string} status
 * @returns {boolean}
 */
export function isTerminal(status) {
  return (
    status === JobStatus.Completed ||
    status === JobStatus.Rejected ||
    status === JobStatus.Expired
  );
}

/**
 * Narrow an arbitrary value to a known ERC-8183 Job status string.
 *
 * @param {unknown} status
 * @returns {status is JobStatusValue}
 */
export function isJobStatus(status) {
  return typeof status === 'string' && KNOWN_STATUSES.has(status);
}

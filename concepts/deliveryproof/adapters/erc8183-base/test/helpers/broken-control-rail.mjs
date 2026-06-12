// test/helpers/broken-control-rail.mjs
// A DELIBERATELY-BROKEN control RailAdapter — the negative control for the
// conformance suite. NOT a product surface; never exported from src/.
//
// SCOPE / HONESTY: this is test scaffolding only. NO chain, NO wallet, NO RPC, NO
// keys, NO live tx. Its entire purpose is to be WRONG in the exact ways a real
// rail must not be, so that runRailConformance FAILS against it. If the suite were
// to pass this rail, the suite's assertions would be theater. The two layers of
// brokenness here mirror the two enforcement layers the real rail provides:
//   (1) a LENIENT fake client that lets a SECOND complete()/reject() succeed and
//       ignores the Submitted-only rule (the opposite of the strict in-memory
//       client, whose strictness forces real idempotency);
//   (2) a CREDULOUS rail wrapper that trusts receipt.decision blindly — no 7-field
//       receipt<->hold binding, no verdict<->decision consistency check, no live
//       reconcile/idempotency. It will happily pay on a tampered or contradictory
//       receipt, and will replay one hold's receipt against another hold.
// TESTNET / LOCAL ONLY — and not even that: this is a pure in-memory fake.

import { sha256hex } from 'deliveryproof';
import { JobStatus, mapJobStatusToHoldState } from '../../src/job-status.mjs';

/**
 * A lenient fake ERC-8183 client: the anti-pattern the real in-memory client
 * refuses to be. getJob auto-provisions a funded Submitted job; complete/reject
 * IGNORE the current status (no Submitted-only guard) and NEVER throw on a second
 * terminal transition — they just overwrite the status. This is what lets the
 * credulous rail double-settle and flip terminals, which the suite must catch.
 *
 * @param {Map<string, { jobId: string, status: string, amount: number, currency: string }>} [jobs]
 * @returns {{ getJob: Function, complete: Function, reject: Function, _jobs: () => Map<string, any> }}
 */
function createLenientClient(jobs = new Map()) {
  function getJob(jobIdInput) {
    const jobId = String(jobIdInput);
    let job = jobs.get(jobId);
    if (!job) {
      job = { jobId, status: JobStatus.Submitted, amount: 5, currency: 'USDC' };
      jobs.set(jobId, job);
    }
    return { ...job };
  }
  function complete(jobIdInput) {
    const jobId = String(jobIdInput);
    // No status guard, no throw-on-terminal: blindly mark Completed every time.
    const job = jobs.get(jobId) ?? { jobId, amount: 5, currency: 'USDC' };
    job.status = JobStatus.Completed;
    jobs.set(jobId, job);
    return { txRef: `broken:complete:${jobId}`, status: job.status };
  }
  function reject(jobIdInput) {
    const jobId = String(jobIdInput);
    // No status guard, no throw-on-terminal: blindly mark Rejected every time —
    // even flipping a previously Completed job, which is the cardinal sin.
    const job = jobs.get(jobId) ?? { jobId, amount: 5, currency: 'USDC' };
    job.status = JobStatus.Rejected;
    jobs.set(jobId, job);
    return { txRef: `broken:reject:${jobId}`, status: job.status };
  }
  return {
    getJob,
    complete,
    reject,
    _jobs() {
      return jobs;
    },
  };
}

/**
 * Build the broken control rail. It deliberately OMITS every money-safety gate the
 * real createErc8183Rail enforces, so the conformance suite has something that must
 * fail. A restart inherits the prior rail's lenient client (shared job Map) so the
 * status-after-restart case can at least run; correctness elsewhere is the point.
 *
 * @param {{ previousRail?: { _client?: () => any } }} [opts]
 * @returns {{ id: string, authorize: Function, capture: Function, refund: Function, status: Function, _client: () => any }}
 */
export function createBrokenControlRail({ previousRail } = {}) {
  const id = 'erc8183-broken-control';
  const client =
    previousRail && typeof previousRail._client === 'function'
      ? previousRail._client()
      : createLenientClient();

  function holdIdFor(jobId) {
    return `erc8183-broken:${jobId}`;
  }
  function jobIdFromHold(holdOrId) {
    const holdId = typeof holdOrId === 'string' ? holdOrId : holdOrId?.holdId;
    const prefix = 'erc8183-broken:';
    return typeof holdId === 'string' && holdId.startsWith(prefix)
      ? holdId.slice(prefix.length)
      : String(holdId);
  }
  function resolveJobId(contract) {
    return String(contract?.idempotencyKey ?? contract?.id ?? '');
  }

  return {
    id,
    authorize(contract) {
      const jobId = resolveJobId(contract);
      const job = client.getJob(jobId);
      const state = mapJobStatusToHoldState(job.status);
      return {
        holdId: holdIdFor(jobId),
        contractId: contract.id,
        contractHash: sha256hex(contract),
        railId: id,
        amount: job.amount,
        currency: job.currency,
        state,
        history: [{ state, at: 0, jobId }],
      };
    },
    // BROKEN: trusts receipt.decision blindly. No 7-field binding check, no
    // verdict-consistency check, no live reconcile, no idempotency. It will pay on
    // a tampered receipt (wrong holdId/amount/currency), on a contradictory receipt
    // (decision=release but verdict.ok=false), and will replay across holds.
    capture(holdOrId, receipt) {
      const jobId = jobIdFromHold(holdOrId);
      const tx = client.complete(jobId, { reason: '0x00' });
      return {
        holdId: holdIdFor(jobId),
        contractId: receipt?.contractId ?? null,
        contractHash: receipt?.contractHash ?? null,
        railId: id,
        amount: receipt?.amount,
        currency: receipt?.currency,
        state: 'captured',
        history: [{ state: 'captured', at: 0, jobId, txRef: tx.txRef }],
      };
    },
    refund(holdOrId, receipt) {
      const jobId = jobIdFromHold(holdOrId);
      const tx = client.reject(jobId, { reason: '0x00' });
      return {
        holdId: holdIdFor(jobId),
        contractId: receipt?.contractId ?? null,
        contractHash: receipt?.contractHash ?? null,
        railId: id,
        amount: receipt?.amount,
        currency: receipt?.currency,
        state: 'refunded',
        history: [{ state: 'refunded', at: 0, jobId, txRef: tx.txRef }],
      };
    },
    status(holdOrId) {
      const jobId = jobIdFromHold(holdOrId);
      const job = client.getJob(jobId);
      return {
        holdId: holdIdFor(jobId),
        contractId: null,
        contractHash: null,
        railId: id,
        amount: job.amount,
        currency: job.currency,
        state: mapJobStatusToHoldState(job.status),
        history: [{ state: mapJobStatusToHoldState(job.status), at: 0, jobId }],
      };
    },
    _client() {
      return client;
    },
  };
}

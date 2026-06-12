// src/clients/in-memory.mjs
// In-process Erc8183Client over a plain Map of jobs — the test/CI seam.
//
// SCOPE / HONESTY: this is a FAKE evaluator backend, not a chain. It holds NO
// wallet, NO RPC URL, NO private keys, and submits NOTHING on-chain; "txRef"
// values are synthetic in-memory references, not transaction hashes. It exists so
// the rail and runRailConformance can exercise the full evaluator surface
// (getJob -> complete/reject) deterministically and offline. It models ERC-8183
// evaluator semantics FAITHFULLY on purpose: complete()/reject() are valid ONLY
// on a Submitted job, and a SECOND terminal transition THROWS rather than
// silently succeeding. That strictness is the point — it forces the rail's
// idempotency to come from reconcile-via-getJob (read the terminal job, return
// the settled Hold with no tx), never from a lenient fake that quietly re-pays.
// The adapter is the ERC-8183 EVALUATOR only: it never funds, custodies, or
// submits a job; here getJob auto-provisions an already-funded Submitted job so
// callers have something to evaluate, which is a TEST convenience, not custody.
// TESTNET / LOCAL ONLY — no mainnet, no real funds, no autonomous live tx.

import { JobStatus, isSettleable } from '../job-status.mjs';
import { Erc8183NotSettleableError, Erc8183RailError } from '../errors.mjs';

/**
 * Default escrow terms used when getJob auto-provisions an unknown job. These
 * mirror runRailConformance's makeContract (price 5 / USDC) so a contract routed
 * through the rail binds cleanly to the synthesized job's amount/currency.
 */
const DEFAULT_AMOUNT = 5;
const DEFAULT_CURRENCY = 'USDC';

/**
 * @typedef {Object} InMemoryJob
 * @property {string} jobId
 * @property {import('../job-status.mjs').JobStatusValue|string} status
 * @property {number|string|bigint} amount
 * @property {string} currency
 * @property {string|null} reason         Last evaluator attestation word (if any).
 * @property {string|null} settledTxRef   Synthetic tx ref of the terminal call.
 * @property {string|null} deliverableHash Optional submitted-deliverable digest.
 */

/**
 * Create an in-process Erc8183Client backed by a Map of jobs.
 *
 * getJob on an UNKNOWN jobId auto-creates a Submitted, pre-funded job (so a fresh
 * conformance run always has a Submitted job to evaluate). complete/reject move a
 * Submitted job to Completed/Rejected and THROW on any non-Submitted job. The
 * backing Map is exposed (opts.jobs to inject one, and `jobs`/`_jobs()` to read
 * it) so a single instance — or two instances sharing one Map — survives a
 * simulated restart.
 *
 * @param {Object} [opts]
 * @param {Map<string, InMemoryJob>} [opts.jobs] Shared backing store. Reusing the
 *   same Map across two client instances simulates a restart against one chain.
 * @param {boolean} [opts.autoCreate=true] Auto-provision unknown jobs as Submitted.
 * @param {number|string|bigint} [opts.defaultAmount=5] Escrow amount for auto jobs.
 * @param {string} [opts.defaultCurrency="USDC"] Escrow currency for auto jobs.
 * @param {() => number} [opts.now=Date.now] Clock for synthetic tx refs.
 * @returns {import('../client-interface.mjs').Erc8183Client & {
 *   jobs: Map<string, InMemoryJob>,
 *   _jobs: () => Map<string, InMemoryJob>,
 *   seedJob: (jobId: string|number, init?: Object) => InMemoryJob,
 *   listJobs: () => InMemoryJob[],
 * }}
 */
export function createInMemoryErc8183Client(opts = {}) {
  if (opts === null || typeof opts !== 'object') {
    throw new Erc8183RailError('createInMemoryErc8183Client: opts must be an object when provided');
  }
  const jobs = resolveJobsMap(opts.jobs);
  const autoCreate = opts.autoCreate !== false;
  const defaultAmount = opts.defaultAmount ?? DEFAULT_AMOUNT;
  const defaultCurrency = opts.defaultCurrency ?? DEFAULT_CURRENCY;
  const now = typeof opts.now === 'function' ? opts.now : Date.now;

  /**
   * Read a job. Auto-provisions an already-funded Submitted job for an unknown id
   * (unless autoCreate is disabled, in which case an unknown id is a not-found
   * condition the caller's rail surfaces as Erc8183JobNotFoundError). Returns a
   * shallow VIEW clone so callers cannot mutate the store by reference.
   *
   * @param {string|number|bigint} jobIdInput
   * @returns {import('../client-interface.mjs').Erc8183JobView & InMemoryJob}
   */
  function getJob(jobIdInput) {
    const jobId = normalizeJobId(jobIdInput);
    let job = jobs.get(jobId);
    if (!job) {
      if (!autoCreate) {
        // Surface a structured "not found" the rail maps to Erc8183JobNotFoundError.
        // We throw the base rail error here (the seam does not import the
        // not-found subclass); the rail's getJob wrapper owns the typed mapping.
        throw new Erc8183RailError(`[erc8183-in-memory] no such job ${jobId}`);
      }
      job = makeSubmittedJob(jobId, defaultAmount, defaultCurrency);
      jobs.set(jobId, job);
    }
    return viewOf(job);
  }

  /**
   * Evaluator releases escrow to the provider: Submitted -> Completed.
   * THROWS Erc8183NotSettleableError if the job is not Submitted (including a
   * second complete on an already-terminal job). This strictness forces rail
   * idempotency to come from reconcile-via-getJob, not a lenient fake.
   *
   * @param {string|number|bigint} jobIdInput
   * @param {{ reason?: string, optParams?: string }} [args]
   * @returns {import('../client-interface.mjs').Erc8183TxResult}
   */
  function complete(jobIdInput, args = {}) {
    return transition(jobIdInput, args, JobStatus.Completed, 'complete');
  }

  /**
   * Evaluator refunds the client: Submitted -> Rejected.
   * THROWS Erc8183NotSettleableError if the job is not Submitted (including a
   * second reject on an already-terminal job).
   *
   * @param {string|number|bigint} jobIdInput
   * @param {{ reason?: string, optParams?: string }} [args]
   * @returns {import('../client-interface.mjs').Erc8183TxResult}
   */
  function reject(jobIdInput, args = {}) {
    return transition(jobIdInput, args, JobStatus.Rejected, 'reject');
  }

  /**
   * Shared Submitted-only state transition for complete/reject. Never
   * auto-creates: a state-changing call against an unknown job is a hard error,
   * because the evaluator must read a real funded job before acting.
   *
   * @param {string|number|bigint} jobIdInput
   * @param {{ reason?: string, optParams?: string }} args
   * @param {import('../job-status.mjs').JobStatusValue} targetStatus
   * @param {'complete'|'reject'} op
   * @returns {import('../client-interface.mjs').Erc8183TxResult}
   */
  function transition(jobIdInput, args, targetStatus, op) {
    const jobId = normalizeJobId(jobIdInput);
    const job = jobs.get(jobId);
    if (!job) {
      throw new Erc8183NotSettleableError(
        `[erc8183-in-memory] cannot ${op} job ${jobId}: no such job (evaluator must read a funded job first)`,
        { jobId },
      );
    }
    if (!isSettleable(job.status)) {
      // Evaluator-only + Submitted-only: a non-Submitted job (Open/Funded not
      // ready; Completed/Rejected/Expired already terminal) is unsettleable. A
      // SECOND terminal transition lands here and THROWS, by design.
      throw new Erc8183NotSettleableError(
        `[erc8183-in-memory] cannot ${op} job ${jobId}: status is ${String(job.status)}, evaluator may act only on a Submitted job`,
        { jobId, status: String(job.status) },
      );
    }
    const reason = args && args.reason !== undefined ? args.reason : null;
    const txRef = synthTxRef(op, jobId, now);
    job.status = targetStatus;
    job.reason = reason;
    job.settledTxRef = txRef;
    return { txRef, status: job.status };
  }

  /**
   * Seed (or overwrite) a job in a chosen status — a unit-test helper so a test
   * can stage Open/Funded/Completed/Rejected/Expired jobs that getJob would never
   * auto-create. Defaults to a funded Submitted job. Returns a VIEW clone.
   *
   * @param {string|number|bigint} jobIdInput
   * @param {Partial<InMemoryJob>} [init]
   * @returns {InMemoryJob}
   */
  function seedJob(jobIdInput, init = {}) {
    if (init === null || typeof init !== 'object') {
      throw new Erc8183RailError('[erc8183-in-memory] seedJob: init must be an object when provided');
    }
    const jobId = normalizeJobId(jobIdInput);
    const status = init.status !== undefined ? init.status : JobStatus.Submitted;
    const job = {
      jobId,
      status,
      amount: init.amount !== undefined ? init.amount : defaultAmount,
      currency: init.currency !== undefined ? init.currency : defaultCurrency,
      reason: init.reason !== undefined ? init.reason : null,
      settledTxRef: init.settledTxRef !== undefined ? init.settledTxRef : null,
      deliverableHash: init.deliverableHash !== undefined ? init.deliverableHash : null,
    };
    jobs.set(jobId, job);
    return viewOf(job);
  }

  /**
   * Snapshot every job as a VIEW clone (no live references into the store).
   * @returns {InMemoryJob[]}
   */
  function listJobs() {
    return Array.from(jobs.values()).map(viewOf);
  }

  return {
    getJob,
    complete,
    reject,
    seedJob,
    listJobs,
    // Backing store is intentionally exposed so a shared instance — or two
    // instances constructed with the same Map — survives a simulated restart.
    jobs,
    _jobs() {
      return jobs;
    },
  };
}

/**
 * @param {Map<string, InMemoryJob>|undefined} provided
 * @returns {Map<string, InMemoryJob>}
 */
function resolveJobsMap(provided) {
  if (provided === undefined) return new Map();
  if (!(provided instanceof Map)) {
    throw new Erc8183RailError('createInMemoryErc8183Client: opts.jobs must be a Map when provided');
  }
  return provided;
}

/**
 * Normalize any jobId shape to the canonical string key. The rail keys holds by a
 * stringified jobId, so the store must too — otherwise getJob(5) and getJob("5")
 * would address different jobs and a restart lookup could miss.
 *
 * @param {string|number|bigint} jobIdInput
 * @returns {string}
 */
function normalizeJobId(jobIdInput) {
  if (jobIdInput === null || jobIdInput === undefined) {
    throw new Erc8183RailError('[erc8183-in-memory] jobId is required');
  }
  const t = typeof jobIdInput;
  if (t !== 'string' && t !== 'number' && t !== 'bigint') {
    throw new Erc8183RailError(`[erc8183-in-memory] jobId must be a string, number, or bigint (got ${t})`);
  }
  const jobId = String(jobIdInput);
  if (jobId.length === 0) {
    throw new Erc8183RailError('[erc8183-in-memory] jobId must be a non-empty string');
  }
  return jobId;
}

/**
 * @param {string} jobId
 * @param {number|string|bigint} amount
 * @param {string} currency
 * @returns {InMemoryJob}
 */
function makeSubmittedJob(jobId, amount, currency) {
  return {
    jobId,
    status: JobStatus.Submitted,
    amount,
    currency,
    reason: null,
    settledTxRef: null,
    deliverableHash: null,
  };
}

/**
 * Build a defensive shallow VIEW of a stored job so callers can never mutate the
 * Map's contents by holding the returned object.
 *
 * @param {InMemoryJob} job
 * @returns {InMemoryJob}
 */
function viewOf(job) {
  return {
    jobId: job.jobId,
    status: job.status,
    amount: job.amount,
    currency: job.currency,
    reason: job.reason ?? null,
    settledTxRef: job.settledTxRef ?? null,
    deliverableHash: job.deliverableHash ?? null,
  };
}

/**
 * Synthetic, clearly-not-a-chain transaction reference. The `mem:` prefix is a
 * deliberate tell that no real transaction occurred.
 *
 * @param {'complete'|'reject'} op
 * @param {string} jobId
 * @param {() => number} now
 * @returns {string}
 */
function synthTxRef(op, jobId, now) {
  return `mem:${op}:${jobId}:${now()}`;
}

// src/errors.mjs
// Typed error hierarchy for the ERC-8183 (Agentic Commerce) RailAdapter.
//
// SCOPE / HONESTY: pure error classes. NO contracts, NO wallet, NO RPC, NO keys,
// NO on-chain submission. These exist so callers can distinguish "this job is not
// in a state DeliveryProof may evaluate" (Erc8183NotSettleableError) from "the job
// does not exist" (Erc8183JobNotFoundError) from "the injected client is wrong"
// (Erc8183ClientError) without string-matching messages. The adapter is the
// ERC-8183 EVALUATOR only: it never funds, custodies, or submits a job. TESTNET /
// LOCAL ONLY — no mainnet, no real funds, no autonomous live transactions.

/**
 * Base class for every error raised by this adapter. Catch this to handle any
 * adapter-originated failure; catch a subclass for a specific condition.
 */
export class Erc8183RailError extends Error {
  /**
   * @param {string} message
   * @param {{ cause?: unknown }} [options]
   */
  constructor(message, options) {
    super(message, options);
    this.name = 'Erc8183RailError';
  }
}

/**
 * Raised when an ERC-8183 evaluator action is attempted against a job whose
 * on-chain status is not `Submitted`. The evaluator may act ONLY on a Submitted
 * job (complete/reject release or refund the already-funded escrow); Open/Funded
 * jobs are not yet ready, and Completed/Rejected/Expired jobs are terminal.
 */
export class Erc8183NotSettleableError extends Erc8183RailError {
  /**
   * @param {string} message
   * @param {{ cause?: unknown, jobId?: string, status?: string }} [options]
   */
  constructor(message, options) {
    super(message, options);
    this.name = 'Erc8183NotSettleableError';
    if (options && options.jobId !== undefined) this.jobId = options.jobId;
    if (options && options.status !== undefined) this.status = options.status;
  }
}

/**
 * Raised when `getJob(jobId)` cannot locate a job for the supplied id. The
 * adapter never creates or funds jobs; an absent job is an operator/config error,
 * not something the evaluator may paper over.
 */
export class Erc8183JobNotFoundError extends Erc8183RailError {
  /**
   * @param {string} message
   * @param {{ cause?: unknown, jobId?: string }} [options]
   */
  constructor(message, options) {
    super(message, options);
    this.name = 'Erc8183JobNotFoundError';
    if (options && options.jobId !== undefined) this.jobId = options.jobId;
  }
}

/**
 * Raised when the injected Erc8183Client is malformed (missing getJob/complete/
 * reject) or when a client method fails in a way the adapter cannot interpret as
 * a job-state condition. Wrap the underlying failure via `{ cause }`.
 */
export class Erc8183ClientError extends Erc8183RailError {
  /**
   * @param {string} message
   * @param {{ cause?: unknown }} [options]
   */
  constructor(message, options) {
    super(message, options);
    this.name = 'Erc8183ClientError';
  }
}

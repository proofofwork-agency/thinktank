// src/client-interface.mjs
// The Erc8183Client seam: a thin, transport-agnostic interface over the real
// ERC-8183 evaluator entry points, plus the human-readable contract ABI.
//
// SCOPE / HONESTY: this module defines a SHAPE and validates it. It holds NO
// wallet, NO RPC URL, NO private keys, and submits NOTHING on-chain. The adapter
// is the ERC-8183 EVALUATOR only — it reads a job and, for an already-funded
// Submitted job, calls complete (release) or reject (refund). It NEVER funds,
// custodies, or submits a job. There is no canonical/blessed ERC-8183 contract
// address: address + chainId + rpcUrl are always operator config supplied to a
// concrete client (see ./clients/in-memory.mjs and ./clients/viem.mjs).
// TESTNET / LOCAL ONLY — no mainnet, no real funds, no autonomous live tx.

import { Erc8183ClientError } from './errors.mjs';

/**
 * Human-readable ERC-8183 evaluator ABI fragment, in the form viem/ethers accept.
 *
 * Only the evaluator-relevant surface is declared: the two state-changing calls
 * the evaluator is permitted to make (complete = release escrow to provider,
 * reject = refund the client), the read used to reconcile job state (getJob),
 * and the lifecycle events a client may use to observe transitions. `reason` is
 * the optional ERC-8183 attestation hash word (here a DeliveryProof receipt
 * digest); `optParams` carries any contract-specific extra calldata.
 *
 * @type {ReadonlyArray<string>}
 */
export const ERC8183_JOB_ABI = Object.freeze([
  // Evaluator-only state transitions on a Submitted job.
  'function complete(uint256 jobId, bytes32 reason, bytes optParams)',
  'function reject(uint256 jobId, bytes32 reason, bytes optParams)',
  // Read used to reconcile on-chain job state into a Hold.
  'function getJob(uint256 jobId) view returns (uint8 status, address client, address provider, address evaluator, uint256 amount, address currency, bytes32 deliverableHash)',
  // Lifecycle events (observation only; the evaluator emits Completed/Rejected).
  'event JobOpened(uint256 indexed jobId, address indexed client)',
  'event JobFunded(uint256 indexed jobId, uint256 amount, address currency)',
  'event JobSubmitted(uint256 indexed jobId, bytes32 deliverableHash)',
  'event JobCompleted(uint256 indexed jobId, address indexed evaluator, bytes32 reason)',
  'event JobRejected(uint256 indexed jobId, address indexed evaluator, bytes32 reason)',
  'event JobExpired(uint256 indexed jobId)',
]);

/**
 * The transport-agnostic ERC-8183 evaluator client the rail drives. A concrete
 * implementation may sit over an in-process Map (tests/CI), a local devnet via
 * viem, or any operator-owned testnet wiring. It exposes exactly the evaluator
 * surface — read job state, release, refund — and nothing that funds or submits.
 *
 * Status strings are the ERC-8183 lifecycle names from ./job-status.mjs
 * (Open | Funded | Submitted | Completed | Rejected | Expired).
 *
 * @typedef {Object} Erc8183Client
 * @property {(jobId: string) => (Promise<Erc8183JobView>|Erc8183JobView)} getJob
 *   Read the job. Resolves to its current status plus the escrow amount/currency.
 *   Should reject/throw Erc8183JobNotFoundError when no such job exists.
 * @property {(jobId: string, args: { reason: string, optParams?: string }) => (Promise<Erc8183TxResult>|Erc8183TxResult)} complete
 *   Evaluator releases the escrow to the provider. Valid ONLY on a Submitted job.
 * @property {(jobId: string, args: { reason: string, optParams?: string }) => (Promise<Erc8183TxResult>|Erc8183TxResult)} reject
 *   Evaluator refunds the client. Valid ONLY on a Submitted job.
 */

/**
 * @typedef {Object} Erc8183JobView
 * @property {string} jobId
 * @property {import('./job-status.mjs').JobStatusValue|string} status
 * @property {number|string|bigint} amount   Escrowed budget (units per `currency`).
 * @property {string} currency               Currency/token symbol or address.
 */

/**
 * @typedef {Object} Erc8183TxResult
 * @property {string} txRef    Opaque reference for the submitted transaction.
 * @property {import('./job-status.mjs').JobStatusValue|string} [status]
 *   Resulting job status, when the client can report it synchronously.
 */

const REQUIRED_CLIENT_METHODS = Object.freeze(['getJob', 'complete', 'reject']);

/**
 * Assert that `client` structurally implements the Erc8183Client interface.
 * Throws Erc8183ClientError (never silently coerces) so a misconfigured seam
 * fails closed at rail construction instead of at settlement time.
 *
 * @param {unknown} client
 * @returns {Erc8183Client}
 */
export function assertErc8183Client(client) {
  if (!client || (typeof client !== 'object' && typeof client !== 'function')) {
    throw new Erc8183ClientError('Erc8183Client must be an object exposing getJob, complete, and reject');
  }
  const missing = REQUIRED_CLIENT_METHODS.filter((name) => typeof (/** @type {any} */ (client)[name]) !== 'function');
  if (missing.length > 0) {
    throw new Erc8183ClientError(`Erc8183Client is missing required method(s): ${missing.join(', ')}`);
  }
  return /** @type {Erc8183Client} */ (client);
}

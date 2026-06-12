// src/rail.mjs
// The ERC-8183 (Agentic Commerce) RailAdapter: DeliveryProof AS the evaluator.
//
// SCOPE / HONESTY: this rail is the ERC-8183 EVALUATOR slot and NOTHING else. It
// NEVER funds, custodies, or submits a job; it does not open or fund escrow. It
// READS an already-funded job (client.getJob) and, for a job in the on-chain
// Submitted state, RELEASES (client.complete) or REFUNDS (client.reject) the
// escrow from a verified DeliveryProof receipt. It holds NO wallet, NO RPC URL,
// and NO keys of its own: every chain effect goes through the injected
// Erc8183Client seam, which the operator wires to a local devnet / testnet.
//
// There is NO canonical/blessed ERC-8183 contract: jobContractAddress + chainId +
// rpcUrl are always operator config carried by the client. This adapter makes NO
// exactly-once / finality / reorg guarantee — terminalization is operator-owned
// and reorg handling is operator policy. TESTNET / LOCAL ONLY — no mainnet, no
// real funds, no autonomous live tx.
//
// MONEY-SAFETY (mirrors deliveryproof/concept/src/rails/durable-rail.mjs and
// examples/reference-manual-capture-rail.mjs): before any release/refund we
// (1) re-check the 7-field receipt<->hold binding, (2) re-check verdict<->decision
// consistency, (3) optionally verify the receipt signature, and (4) reconcile the
// CURRENT on-chain job status via getJob so idempotency comes from real job state,
// never from a lenient fake — a job already Completed makes a repeat capture a
// no-tx no-op, an opposite terminal is a hard conflict.

import { verifyReceipt, sha256hex } from 'deliveryproof';
import { assertErc8183Client } from './client-interface.mjs';
import {
  JobStatus,
  mapJobStatusToHoldState,
  isSettleable,
  isTerminal,
} from './job-status.mjs';
import {
  Erc8183RailError,
  Erc8183NotSettleableError,
  Erc8183JobNotFoundError,
  Erc8183ClientError,
} from './errors.mjs';
import { deliveryReceiptToEvaluatorCall } from './reason.mjs';

/** @typedef {import('deliveryproof').DeliveryContract} DeliveryContract */
/** @typedef {import('deliveryproof').DeliveryReceipt} DeliveryReceipt */
/** @typedef {import('deliveryproof').Hold} Hold */
/** @typedef {import('./client-interface.mjs').Erc8183Client} Erc8183Client */
/** @typedef {import('./client-interface.mjs').Erc8183JobView} Erc8183JobView */

const DEFAULT_RAIL_ID = 'erc8183-base';
const DEFAULT_CHAIN_NAMESPACE = 'local';
const DEFAULT_JOB_CONTRACT = '0xlocal';

/**
 * Default job-id resolver: pull the ERC-8183 job id out of a DeliveryContract.
 * Tries, in order, an explicit contract.jobId, a predicate param jobId, the
 * contract's idempotencyKey, then its id — so a conformance contract (which sets
 * only idempotencyKey + id and NO jobId) still resolves to a stable job key.
 *
 * @param {DeliveryContract & { jobId?: string|number, idempotencyKey?: string, predicate?: { params?: { jobId?: string|number } } }} contract
 * @returns {string|number|undefined}
 */
function defaultJobIdResolver(contract) {
  return (
    contract?.jobId ??
    contract?.predicate?.params?.jobId ??
    contract?.idempotencyKey ??
    contract?.id
  );
}

/**
 * Create the ERC-8183 RailAdapter.
 *
 * @param {Object} opts
 * @param {Erc8183Client} opts.client REQUIRED injected evaluator seam (getJob/complete/reject).
 * @param {string} [opts.id='erc8183-base'] Rail id; also the hold.railId every receipt must bind to.
 * @param {string} [opts.chainNamespace='local'] Operator chain namespace (part of holdId).
 * @param {string} [opts.jobContractAddress='0xlocal'] Operator job-contract address (part of holdId). NOT a blessed/canonical address.
 * @param {(contract: DeliveryContract) => (string|number|undefined)} [opts.jobIdResolver] Resolve a contract to its on-chain job id.
 * @param {string|null} [opts.settlementPublicKey=null] PEM key receipts are verified against when requireSignature is on (or always, when present).
 * @param {boolean} [opts.requireSignature=false] Fail closed: require settlementPublicKey and a valid signature before any release/refund.
 * @param {boolean} [opts.supportsRestart=false] Advertise restart support (the job Map lives in the client, so restart = same client instance).
 * @param {{ _client?: () => Erc8183Client }|null} [opts.previousRail=null] Prior rail instance to inherit the client from across a restart.
 * @param {() => number} [opts.now=Date.now] Clock for deterministic history timestamps.
 * @param {((event: string, data: Object) => void)|null} [opts.audit=null] Optional best-effort audit hook; failures are swallowed.
 * @returns {{ id: string, authorize: Function, capture: Function, refund: Function, status: Function, health: Function, _client: () => Erc8183Client }}
 */
export function createErc8183Rail(opts = {}) {
  const {
    id = DEFAULT_RAIL_ID,
    chainNamespace = DEFAULT_CHAIN_NAMESPACE,
    jobContractAddress = DEFAULT_JOB_CONTRACT,
    jobIdResolver = defaultJobIdResolver,
    settlementPublicKey = null,
    requireSignature = false,
    supportsRestart = false,
    previousRail = null,
    now = Date.now,
    audit = null,
  } = opts;

  // Inherit the prior rail's client across a restart when one is not passed
  // directly; sharing the instance shares its in-process job Map (the spec's
  // restart model). Fall back to the explicit client otherwise.
  const inheritedClient =
    previousRail && typeof previousRail._client === 'function'
      ? previousRail._client()
      : null;
  const rawClient = opts.client ?? inheritedClient;
  if (!rawClient) {
    throw new Erc8183ClientError(
      'createErc8183Rail: a client is required (pass opts.client, or opts.previousRail with a _client())',
    );
  }
  // Fail closed at construction if the seam is malformed (throws Erc8183ClientError).
  const client = assertErc8183Client(rawClient);

  if (typeof id !== 'string' || id.length === 0) {
    throw new Erc8183RailError('createErc8183Rail: id must be a non-empty string');
  }
  // Opt-in fail-closed mode (mirrors createDurableEscrowRail): requireSignature
  // demands a settlement key be present so we never silently skip verification.
  if (requireSignature === true && (settlementPublicKey === null || settlementPublicKey === undefined)) {
    throw new Erc8183RailError(
      'createErc8183Rail: requireSignature is set but no settlementPublicKey was provided',
    );
  }
  if (typeof jobIdResolver !== 'function') {
    throw new Erc8183RailError('createErc8183Rail: jobIdResolver must be a function');
  }

  /**
   * Idempotency ledger keyed "<holdId>:<release|refund>:<receiptHash>". A repeat of
   * the EXACT same terminal call returns the recorded hold with no second tx. The
   * authoritative idempotency check, however, is reconciliation against live job
   * status in getJob — this Map only short-circuits an identical in-process retry.
   * @type {Map<string, { holdId: string, decision: string, receiptHash: string, hold: Hold }>}
   */
  const terminals = new Map();

  /**
   * Authoritative hold binding captured at authorize, keyed by holdId. This is the
   * 7-field source of truth the templates compare a receipt against: contractId +
   * contractHash come from the contract presented at authorize, amount + currency
   * from the funded on-chain job at that moment. Capture/refund compare the receipt
   * to THIS record so a receipt carrying a wrong amount/currency/contract is
   * rejected even though escrow state itself lives on-chain. (The on-chain job
   * carries no contract identity, so this binding cannot be reconstructed from
   * getJob alone — it must be remembered from authorize, exactly as durable-rail
   * stores its hold.)
   * @type {Map<string, { contractId: string, contractHash: string, amount: *, currency: string }>}
   */
  const bindings = new Map();

  /**
   * Build the deterministic holdId for a job. The job-contract address is operator
   * config, never a canonical/blessed value.
   * @param {string} jobId
   * @returns {string}
   */
  function holdIdFor(jobId) {
    return `erc8183:${chainNamespace}:${jobContractAddress}:${jobId}`;
  }

  /**
   * Resolve a contract to its ERC-8183 job id, normalized to a non-empty string.
   * @param {DeliveryContract} contract
   * @returns {string}
   */
  function resolveJobId(contract) {
    const resolved = jobIdResolver(contract);
    if (resolved === undefined || resolved === null || String(resolved).length === 0) {
      throw new Erc8183RailError(
        '[erc8183-rail] could not resolve a jobId from the contract (set contract.jobId, predicate.params.jobId, idempotencyKey, or id)',
      );
    }
    return String(resolved);
  }

  /**
   * Read a job through the client, normalizing a not-found into a typed error.
   * @param {string} jobId
   * @returns {Promise<Erc8183JobView>}
   */
  async function readJob(jobId) {
    let job;
    try {
      job = await client.getJob(jobId);
    } catch (err) {
      // A client that signals "no such job" via a typed error is honored as-is.
      if (err instanceof Erc8183JobNotFoundError) throw err;
      throw new Erc8183ClientError(`[erc8183-rail] getJob(${jobId}) failed`, { cause: err });
    }
    if (!job || typeof job !== 'object') {
      throw new Erc8183JobNotFoundError(`[erc8183-rail] no ERC-8183 job for id ${jobId}`, { jobId });
    }
    return job;
  }

  /**
   * Synthesize a Hold from a contract + the job's current on-chain view. The hold
   * is bound to THIS rail (railId=id) and to the contract (id + canonical hash);
   * amount/currency come from the funded job, NOT the contract, because the escrow
   * the evaluator can move is whatever is actually funded on-chain.
   * @param {DeliveryContract} contract
   * @param {string} jobId
   * @param {Erc8183JobView} job
   * @returns {Hold}
   */
  function holdFromJob(contract, jobId, job) {
    const state = mapJobStatusToHoldState(job.status);
    return {
      holdId: holdIdFor(jobId),
      contractId: contract.id,
      contractHash: sha256hex(contract),
      railId: id,
      amount: job.amount,
      currency: job.currency,
      state,
      history: [{ state, at: now(), jobId, jobStatus: job.status }],
    };
  }

  /**
   * Project the current job into a Hold WITHOUT a contract context (used by
   * status/reconcile, where we only know the holdId/jobId). contractId/contractHash
   * are intentionally null here: status is a state read, not a binding ceremony.
   * @param {string} jobId
   * @param {Erc8183JobView} job
   * @returns {Hold}
   */
  function holdFromJobStateOnly(jobId, job) {
    const state = mapJobStatusToHoldState(job.status);
    return {
      holdId: holdIdFor(jobId),
      contractId: null,
      contractHash: null,
      railId: id,
      amount: job.amount,
      currency: job.currency,
      state,
      history: [{ state, at: now(), jobId, jobStatus: job.status }],
    };
  }

  /**
   * Recover the jobId embedded in a holdId we minted, or accept a Hold/string.
   * holdId shape: erc8183:<ns>:<addr>:<jobId>. The jobId is the remainder after the
   * third ':' so operator addresses/namespaces containing ':' do not corrupt it.
   * @param {string|Hold} holdOrId
   * @returns {string}
   */
  function jobIdFromHold(holdOrId) {
    const holdId =
      typeof holdOrId === 'string'
        ? holdOrId
        : holdOrId && typeof holdOrId === 'object'
          ? holdOrId.holdId
          : undefined;
    if (typeof holdId !== 'string' || holdId.length === 0) {
      throw new Erc8183RailError('[erc8183-rail] missing holdId');
    }
    const prefix = `erc8183:${chainNamespace}:${jobContractAddress}:`;
    if (!holdId.startsWith(prefix)) {
      throw new Erc8183RailError(
        `[erc8183-rail] holdId ${JSON.stringify(holdId)} is not for this rail (${prefix}<jobId>)`,
      );
    }
    const jobId = holdId.slice(prefix.length);
    if (jobId.length === 0) {
      throw new Erc8183RailError(`[erc8183-rail] holdId ${JSON.stringify(holdId)} is missing its jobId`);
    }
    return jobId;
  }

  function emitAudit(event, data) {
    if (typeof audit !== 'function') return;
    try {
      audit(event, data);
    } catch {
      // Best-effort: an audit sink must never break settlement.
    }
  }

  return {
    id,

    /**
     * ATTACH to an already-funded, Submitted ERC-8183 job. This is the evaluator
     * entry point: it reads the job, asserts it is Submitted (else throws
     * Erc8183NotSettleableError), and synthesizes a held Hold whose amount/currency
     * mirror the funded escrow. It NEVER opens, funds, or submits a job.
     * @param {DeliveryContract} contract
     * @returns {Promise<Hold>}
     */
    async authorize(contract) {
      if (!contract || typeof contract !== 'object') {
        throw new Erc8183RailError('[erc8183-rail] authorize requires a contract');
      }
      if (!contract.id || !contract.price || typeof contract.price !== 'object') {
        throw new Erc8183RailError('[erc8183-rail] contract is missing id or price');
      }
      const jobId = resolveJobId(contract);
      const job = await readJob(jobId);
      if (!isSettleable(job.status)) {
        throw new Erc8183NotSettleableError(
          `[erc8183-rail] job ${jobId} is ${job.status}; the evaluator may only attach to a Submitted job`,
          { jobId, status: job.status },
        );
      }
      const hold = holdFromJob(contract, jobId, job);
      // Remember the authoritative 7-field binding so a later capture/refund can
      // reject a receipt whose contract/amount/currency disagree with what was
      // actually authorized against this funded job.
      bindings.set(hold.holdId, {
        contractId: hold.contractId,
        contractHash: hold.contractHash,
        amount: hold.amount,
        currency: hold.currency,
      });
      emitAudit('rail.authorized', {
        railId: id,
        holdId: hold.holdId,
        jobId,
        contractId: contract.id,
        jobStatus: job.status,
      });
      return cloneHold(hold);
    },

    /**
     * RELEASE the escrow to the provider (ERC-8183 complete) from a verified
     * release receipt. Reconciles live job status first: already Completed ->
     * idempotent no-tx; already Rejected -> conflict.
     * @param {string|Hold} holdOrId
     * @param {DeliveryReceipt} receipt
     * @returns {Promise<Hold>}
     */
    async capture(holdOrId, receipt) {
      return terminalize(holdOrId, receipt, 'release', 'captured');
    },

    /**
     * REFUND the client (ERC-8183 reject) from a verified refund receipt.
     * Reconciles live job status first: already Rejected -> idempotent no-tx;
     * already Completed -> conflict.
     * @param {string|Hold} holdOrId
     * @param {DeliveryReceipt} receipt
     * @returns {Promise<Hold>}
     */
    async refund(holdOrId, receipt) {
      return terminalize(holdOrId, receipt, 'refund', 'refunded');
    },

    /**
     * Read the live job and project its status onto a Hold state.
     * @param {string|Hold} holdOrId
     * @returns {Promise<Hold>}
     */
    async status(holdOrId) {
      const jobId = jobIdFromHold(holdOrId);
      const job = await readJob(jobId);
      return cloneHold(holdFromJobStateOnly(jobId, job));
    },

    /**
     * Liveness probe. Best-effort: never throws — a client without a probe still
     * reports ok with the terminal-ledger size.
     * @returns {Promise<Object>}
     */
    async health() {
      let clientOk = true;
      let clientHealth = null;
      if (typeof (/** @type {any} */ (client).health) === 'function') {
        try {
          clientHealth = await (/** @type {any} */ (client).health)();
          clientOk = clientHealth ? clientHealth.ok !== false : true;
        } catch (err) {
          clientOk = false;
          clientHealth = { ok: false, error: err instanceof Error ? err.message : String(err) };
        }
      }
      return {
        ok: clientOk,
        railId: id,
        chainNamespace,
        jobContractAddress,
        supportsRestart,
        requireSignature,
        terminals: terminals.size,
        client: clientHealth,
      };
    },

    /**
     * Expose the injected client so a successor rail can inherit it across a
     * restart (the in-process job Map lives in the client).
     * @returns {Erc8183Client}
     */
    _client() {
      return client;
    },
  };

  /**
   * The shared terminalization path for capture (release/complete) and refund
   * (refund/reject). Order of checks mirrors durable-rail: decision gate ->
   * verdict consistency -> 7-field binding -> signature -> in-process idempotency
   * -> LIVE getJob reconcile -> submit tx -> record.
   *
   * @param {string|Hold} holdOrId
   * @param {DeliveryReceipt} receipt
   * @param {'release'|'refund'} expectedDecision
   * @param {'captured'|'refunded'} targetState
   * @returns {Promise<Hold>}
   */
  async function terminalize(holdOrId, receipt, expectedDecision, targetState) {
    const jobId = jobIdFromHold(holdOrId);
    const holdId = holdIdFor(jobId);

    // (0) Decision gate: a capture takes only a release receipt, refund only refund.
    if (!receipt || typeof receipt !== 'object' || receipt.decision !== expectedDecision) {
      throw new Erc8183RailError(
        `[erc8183-rail] refusing ${targetState}: receipt.decision must be ${expectedDecision}`,
      );
    }
    // (1) Verdict<->decision consistency (release iff verdict.ok===true).
    assertReceiptDecisionConsistent(receipt);
    // (2) 7-field receipt<->hold binding against the AUTHORITATIVE binding captured
    // at authorize (contractId/contractHash from the contract, amount/currency from
    // the funded job). FAIL CLOSED if no binding is cached: capture/refund REQUIRE a
    // prior authorize() on THIS rail instance. We deliberately do NOT reconstruct the
    // binding from the receipt being settled — sourcing contract identity from the
    // same receipt would make the check a tautology and let a forged receipt carrying
    // only the right holdId + live amount/currency release escrow. The on-chain job
    // carries no contract identity, so after a restart the operator must re-authorize
    // (re-present the funding contract) before terminalizing.
    const binding = bindings.get(holdId);
    if (!binding) {
      throw new Erc8183RailError(
        `[erc8183-rail] no authorized binding for hold ${holdId}: call authorize() with the funding contract on this rail instance before ${targetState === 'captured' ? 'capture' : 'refund'} (the binding is remembered in-memory from authorize and is never derived from the receipt; re-authorize after a restart)`,
      );
    }
    assertReceiptMatchesHold(holdId, id, receipt, expectedDecision, binding);
    // (3) Optional fail-closed signature verification against the settlement key.
    assertReceiptSignature(receipt);

    const receiptHash = sha256hex(receipt);
    const operationKey = `${holdId}:${targetState === 'captured' ? 'release' : 'refund'}:${receiptHash}`;

    // (4) In-process idempotency: an identical retry returns the recorded hold.
    const prior = terminals.get(operationKey);
    if (prior) {
      if (prior.holdId !== holdId || prior.receiptHash !== receiptHash || prior.decision !== receipt.decision) {
        throw new Erc8183RailError(`[erc8183-rail] idempotency conflict for terminal key ${operationKey}`);
      }
      return cloneHold(prior.hold);
    }

    // (5) Reconcile against LIVE on-chain job status before submitting anything.
    // This is the real idempotency + safety gate: if the chain already terminalized
    // this job, we never double-submit, and an OPPOSITE terminal is a hard conflict.
    const before = await readJob(jobId);
    if (isTerminal(before.status)) {
      const reconciled = reconcileTerminal(jobId, before, expectedDecision, targetState, receiptHash, receipt);
      return cloneHold(reconciled);
    }
    if (!isSettleable(before.status)) {
      // Open/Funded: the escrow exists but the job is not yet Submitted; the
      // evaluator may not act. (Submitted is the only settleable status.)
      throw new Erc8183NotSettleableError(
        `[erc8183-rail] job ${jobId} is ${before.status}; the evaluator may only ${targetState === 'captured' ? 'complete' : 'reject'} a Submitted job`,
        { jobId, status: before.status },
      );
    }

    // (6) Submit the evaluator action: release -> complete, refund -> reject. The
    // reason word is the receipt digest projected by reason.mjs.
    const { action, reason } = deliveryReceiptToEvaluatorCall(receipt, jobId);
    let tx;
    try {
      tx = action === 'complete'
        ? await client.complete(jobId, { reason })
        : await client.reject(jobId, { reason });
    } catch (err) {
      // A late race: the job terminalized between our read and our write. Re-read
      // and reconcile so a concurrent settlement is idempotent, not a hard error.
      const after = await readJob(jobId).catch(() => null);
      if (after && isTerminal(after.status)) {
        const reconciled = reconcileTerminal(jobId, after, expectedDecision, targetState, receiptHash, receipt);
        return cloneHold(reconciled);
      }
      throw new Erc8183ClientError(`[erc8183-rail] ${action}(${jobId}) failed`, { cause: err });
    }

    // (7) Confirm the resulting state from the client's report or a fresh read, map
    // it to a Hold, and record the terminal for in-process idempotency.
    const settledStatus = await resolveSettledStatus(jobId, tx, targetState);
    const hold = holdFromTerminal(jobId, settledStatus, receipt, receiptHash, tx, targetState);
    terminals.set(operationKey, {
      holdId,
      decision: receipt.decision,
      receiptHash,
      hold: cloneHold(hold),
    });
    emitAudit(`rail.${targetState}`, {
      railId: id,
      holdId,
      jobId,
      decision: receipt.decision,
      action,
      txRef: tx && typeof tx === 'object' ? tx.txRef ?? null : null,
      operationKey,
    });
    return cloneHold(hold);
  }

  /**
   * Reconcile a job that is ALREADY terminal against the attempted operation.
   *   capture on Completed  -> idempotent captured hold, NO tx.
   *   refund  on Rejected/Expired -> idempotent refunded hold, NO tx.
   *   opposite terminal     -> Erc8183RailError conflict (never silently flip money).
   * Records the (no-tx) terminal so a later identical retry short-circuits in step 4.
   *
   * @param {string} jobId
   * @param {Erc8183JobView} job
   * @param {'release'|'refund'} expectedDecision
   * @param {'captured'|'refunded'} targetState
   * @param {string} receiptHash
   * @param {DeliveryReceipt} receipt
   * @returns {Hold}
   */
  function reconcileTerminal(jobId, job, expectedDecision, targetState, receiptHash, receipt) {
    const liveState = mapJobStatusToHoldState(job.status);
    const holdId = holdIdFor(jobId);
    if (liveState !== targetState) {
      throw new Erc8183RailError(
        `[erc8183-rail] conflict: job ${jobId} is on-chain ${job.status} (${liveState}) but a ${expectedDecision} (${targetState}) was requested`,
      );
    }
    const hold = holdFromTerminal(jobId, job.status, receipt, receiptHash, null, targetState);
    const operationKey = `${holdId}:${expectedDecision}:${receiptHash}`;
    if (!terminals.has(operationKey)) {
      terminals.set(operationKey, {
        holdId,
        decision: receipt.decision,
        receiptHash,
        hold: cloneHold(hold),
      });
    }
    emitAudit('rail.reconciled', {
      railId: id,
      holdId,
      jobId,
      decision: receipt.decision,
      jobStatus: job.status,
      noTx: true,
    });
    return hold;
  }

  /**
   * Determine the job status after a write: trust a terminal status the client
   * reported synchronously, otherwise re-read. Falls back to the canonical terminal
   * status for the target state if the client reports nothing readable.
   * @param {string} jobId
   * @param {{ status?: string }} tx
   * @param {'captured'|'refunded'} targetState
   * @returns {Promise<string>}
   */
  async function resolveSettledStatus(jobId, tx, targetState) {
    if (tx && typeof tx === 'object' && typeof tx.status === 'string' && isTerminal(tx.status)) {
      return tx.status;
    }
    const after = await readJob(jobId).catch(() => null);
    if (after && isTerminal(after.status)) return after.status;
    return targetState === 'captured' ? JobStatus.Completed : JobStatus.Rejected;
  }

  /**
   * Build the terminal Hold returned to the caller. contractId/contractHash come
   * from the receipt (its bound terms), state from the realized job status.
   * @param {string} jobId
   * @param {string} jobStatus
   * @param {DeliveryReceipt} receipt
   * @param {string} receiptHash
   * @param {{ txRef?: string }|null} tx
   * @param {'captured'|'refunded'} targetState
   * @returns {Hold}
   */
  function holdFromTerminal(jobId, jobStatus, receipt, receiptHash, tx, targetState) {
    const state = mapJobStatusToHoldState(jobStatus);
    return {
      holdId: holdIdFor(jobId),
      contractId: receipt.contractId ?? null,
      contractHash: receipt.contractHash ?? null,
      railId: id,
      amount: receipt.amount,
      currency: receipt.currency,
      state,
      history: [
        { state: 'held', at: now(), jobId },
        {
          state,
          at: now(),
          jobId,
          jobStatus,
          decision: receipt.decision,
          receiptRef: receiptRefOf(receipt),
          receiptHash,
          txRef: tx && typeof tx === 'object' ? tx.txRef ?? null : null,
          noTx: tx == null,
        },
      ],
    };
  }

  /**
   * Re-enforce the 7-field receipt<->hold binding at the rail (mirror of
   * durable-rail / reference-manual-capture-rail). Every field is compared against
   * the AUTHORITATIVE binding (holdId derived for this job, railId == this rail,
   * contractId/contractHash/amount/currency from the hold captured at authorize).
   * Blocks a receipt minted for a different hold/contract/amount/currency from
   * terminalizing this job — the core money-safety invariant at the rail layer.
   * @param {string} holdId
   * @param {string} railId
   * @param {DeliveryReceipt} receipt
   * @param {'release'|'refund'} expectedDecision
   * @param {{ contractId: string, contractHash: string, amount: *, currency: string }} binding
   */
  function assertReceiptMatchesHold(holdId, railId, receipt, expectedDecision, binding) {
    const mismatches = [];
    if (receipt.decision !== expectedDecision) mismatches.push('decision');
    if (receipt.holdId !== holdId) mismatches.push('holdId');
    if (receipt.contractId !== binding.contractId) mismatches.push('contractId');
    if (receipt.contractHash !== binding.contractHash) mismatches.push('contractHash');
    if (receipt.railId !== railId) mismatches.push('railId');
    if (receipt.amount !== binding.amount) mismatches.push('amount');
    if (receipt.currency !== binding.currency) mismatches.push('currency');
    if (mismatches.length) {
      throw new Erc8183RailError(
        `[erc8183-rail] receipt does not match hold ${holdId}: ${mismatches.join(', ')}`,
      );
    }
  }

  /**
   * Optional fail-closed signature verification. When a settlement key is present
   * (always, if requireSignature forced one at construction), the receipt must
   * verifyReceipt() against it. With no key configured, decision/verdict/binding
   * checks above still stand (back-compat demo path, mirrors durable-rail).
   * @param {DeliveryReceipt} receipt
   */
  function assertReceiptSignature(receipt) {
    if (settlementPublicKey === null || settlementPublicKey === undefined) {
      if (requireSignature === true) {
        // Defense in depth: construction already forbids this combination.
        throw new Erc8183RailError('[erc8183-rail] requireSignature is set but no settlementPublicKey is configured');
      }
      return;
    }
    if (typeof settlementPublicKey !== 'string' || !verifyReceipt(receipt, settlementPublicKey)) {
      throw new Erc8183RailError('[erc8183-rail] receipt signature failed verification');
    }
  }
}

/**
 * Re-enforce verdict<->decision consistency at the rail layer (mirror of
 * durable-rail.assertReceiptDecisionConsistent): release iff verdict.ok===true,
 * refund iff verdict.ok===false. Blocks a forged, internally contradictory receipt
 * even when signature verification is not configured.
 * @param {DeliveryReceipt} receipt
 */
function assertReceiptDecisionConsistent(receipt) {
  const verdict = receipt && receipt.verdict;
  if (!verdict || typeof verdict.ok !== 'boolean') {
    throw new Erc8183RailError('[erc8183-rail] receipt is missing a boolean verdict.ok');
  }
  const expected = verdict.ok ? 'release' : 'refund';
  if (receipt.decision !== expected) {
    throw new Erc8183RailError(
      `[erc8183-rail] receipt decision '${receipt.decision}' contradicts verdict.ok=${verdict.ok} (expected '${expected}')`,
    );
  }
}

/**
 * @param {DeliveryReceipt} receipt
 * @returns {string}
 */
function receiptRefOf(receipt) {
  const sig = receipt && typeof receipt.signature === 'string' ? receipt.signature : '';
  return sig.slice(0, 16);
}

/**
 * @template T
 * @param {T} value
 * @returns {T}
 */
function cloneHold(value) {
  return JSON.parse(JSON.stringify(value));
}

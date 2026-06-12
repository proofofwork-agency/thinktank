// src/clients/viem.mjs
// viem-backed Erc8183Client over an operator-owned testnet/devnet RPC.
//
// SCOPE / HONESTY: this client talks to a REAL ERC-8183 contract over JSON-RPC,
// but ONLY the evaluator surface: it reads a job (getJob) and, for an already
// Submitted job, calls complete (release escrow to provider) or reject (refund
// client). It NEVER funds, custodies, or submits a job, and there is NO canonical
// or blessed ERC-8183 address: rpcUrl + chainId + jobContractAddress + account are
// ALWAYS operator config, never defaulted to anything live. The wallet here is the
// operator's evaluator key; this code performs no autonomous policy of its own.
// TESTNET / LOCAL ONLY — no mainnet, no real funds. The caller's operator policy
// owns address selection, chain selection, finality/reorg handling, and whether a
// write is ever broadcast. viem is an OPTIONAL dependency: it is imported LAZILY
// inside the factory (never at module top level) so importing this module — or the
// package barrel — in plain Node without viem installed does not crash until a
// caller actually constructs a viem client. node --check must pass with no viem.

import { ERC8183_JOB_ABI } from '../client-interface.mjs';
import { JobStatus, isJobStatus } from '../job-status.mjs';
import { Erc8183ClientError, Erc8183JobNotFoundError } from '../errors.mjs';

/**
 * ERC-8183 Job.status is an on-chain `uint8` enum. The contract ABI returns a
 * numeric index; this is the canonical lifecycle order the spec defines:
 *   0 Open -> 1 Funded -> 2 Submitted -> 3 Completed | 4 Rejected | 5 Expired
 * We project that index back onto the JobStatus string names the rest of the
 * adapter (job-status.mjs, the rail, the Hold mapping) speaks. An out-of-range
 * index is a contract/ABI mismatch and fails closed as an Erc8183ClientError
 * rather than being coerced to a settleable state.
 *
 * @type {ReadonlyArray<import('../job-status.mjs').JobStatusValue>}
 */
const JOB_STATUS_BY_INDEX = Object.freeze([
  JobStatus.Open,
  JobStatus.Funded,
  JobStatus.Submitted,
  JobStatus.Completed,
  JobStatus.Rejected,
  JobStatus.Expired,
]);

/**
 * Create a viem-backed {@link import('../client-interface.mjs').Erc8183Client}.
 *
 * Lazily imports viem (and viem/accounts when `account` is a raw private-key
 * string) INSIDE this async factory, so the module imports cleanly in an
 * environment where the optional `viem` dependency is absent. The returned client
 * exposes exactly the evaluator surface — getJob / complete / reject — over the
 * operator-supplied RPC and contract address; it funds nothing and submits no job.
 *
 * @param {Object} opts
 * @param {string} opts.rpcUrl                 JSON-RPC endpoint (operator-owned testnet/devnet).
 * @param {`0x${string}`} opts.jobContractAddress  Deployed ERC-8183 job contract address.
 * @param {number} [opts.chainId]              Numeric chain id. Used to build a chain
 *   definition when `chain` is not supplied; required for write (writeContract) safety.
 * @param {import('viem').Account|`0x${string}`} [opts.account]  Evaluator signer: a viem
 *   Account, or a 0x-prefixed private key (lazily wrapped via viem/accounts). Required to
 *   complete/reject; getJob alone needs no account.
 * @param {import('viem').Chain} [opts.chain]  Explicit viem chain. Overrides chainId-derived chain.
 * @param {string} [opts.chainName="erc8183-operator-chain"]  Display name for a derived chain.
 * @param {{ symbol?: string, decimals?: number, name?: string }} [opts.nativeCurrency]
 *   Native-currency descriptor for a derived chain (display only).
 * @param {import('viem').PublicClient} [opts.publicClient]   Inject a prebuilt public client.
 * @param {import('viem').WalletClient} [opts.walletClient]   Inject a prebuilt wallet client.
 * @param {(status: number|bigint|string) => (import('../job-status.mjs').JobStatusValue|string)} [opts.mapStatus]
 *   Override the uint8 -> JobStatus projection for a non-default contract enum order.
 * @returns {Promise<import('../client-interface.mjs').Erc8183Client & {
 *   readonly publicClient: import('viem').PublicClient,
 *   readonly walletClient: (import('viem').WalletClient|null),
 *   readonly address: `0x${string}`,
 *   readonly abi: ReadonlyArray<object>,
 * }>}
 */
export async function createViemErc8183Client(opts = {}) {
  if (opts === null || typeof opts !== 'object') {
    throw new Erc8183ClientError('createViemErc8183Client: opts must be an object');
  }
  const { rpcUrl, jobContractAddress, chainId, account, chain: chainOpt } = opts;

  if (typeof jobContractAddress !== 'string' || jobContractAddress.length === 0) {
    throw new Erc8183ClientError('createViemErc8183Client: opts.jobContractAddress (deployed ERC-8183 address) is required');
  }
  // No prebuilt clients => we must be able to reach an operator RPC.
  if (!opts.publicClient && (typeof rpcUrl !== 'string' || rpcUrl.length === 0)) {
    throw new Erc8183ClientError('createViemErc8183Client: opts.rpcUrl (operator testnet/devnet endpoint) is required unless a publicClient is supplied');
  }

  // LAZY import: keep `viem` out of the module load path so this file parses and
  // the package barrel imports without the optional dependency installed.
  let viem;
  try {
    viem = await import('viem');
  } catch (cause) {
    throw new Erc8183ClientError(
      "createViemErc8183Client: optional dependency 'viem' is not installed; run `npm i viem` to use the on-chain client (the in-memory client needs no extra deps)",
      { cause },
    );
  }

  const abi = parseJobAbi(viem);
  const address = normalizeAddress(viem, jobContractAddress);
  const chain = resolveChain(viem, { chain: chainOpt, chainId, opts });
  const resolvedAccount = await resolveAccount(viem, account);
  const mapStatus = typeof opts.mapStatus === 'function' ? opts.mapStatus : defaultMapStatus;

  const publicClient = opts.publicClient ?? viem.createPublicClient({
    chain,
    transport: viem.http(rpcUrl),
  });

  // The wallet client is only needed to broadcast complete/reject. getJob works
  // read-only without an account, so we build the wallet client lazily-ish: only
  // when we actually have an account (or an injected walletClient).
  const walletClient = opts.walletClient ?? (resolvedAccount
    ? viem.createWalletClient({ account: resolvedAccount, chain, transport: viem.http(rpcUrl) })
    : null);

  /**
   * Read the job and normalize it to the adapter's Erc8183JobView shape. Maps the
   * on-chain uint8 status to a JobStatus name and stringifies the jobId. A revert
   * or a zero/empty job is surfaced as Erc8183JobNotFoundError; any other RPC/ABI
   * failure is wrapped as Erc8183ClientError so the rail can fail closed.
   *
   * @param {string|number|bigint} jobIdInput
   * @returns {Promise<import('../client-interface.mjs').Erc8183JobView>}
   */
  async function getJob(jobIdInput) {
    const jobId = normalizeJobIdToString(jobIdInput);
    const jobIdArg = toJobIdBigInt(jobIdInput);
    let raw;
    try {
      raw = await publicClient.readContract({
        address,
        abi,
        functionName: 'getJob',
        args: [jobIdArg],
      });
    } catch (cause) {
      if (looksLikeNotFound(cause)) {
        throw new Erc8183JobNotFoundError(`[erc8183-viem] no such job ${jobId}`, { jobId, cause });
      }
      throw new Erc8183ClientError(`[erc8183-viem] getJob(${jobId}) failed: ${describeError(cause)}`, { cause });
    }
    return normalizeJobView(jobId, raw, mapStatus, address);
  }

  /**
   * Evaluator releases escrow to the provider: writeContract complete(jobId,...).
   * Returns the broadcast tx hash as txRef. Valid on-chain ONLY for a Submitted
   * job (the contract enforces this and will revert otherwise); the rail also
   * reconciles via getJob before calling, so a terminal job never reaches here.
   *
   * @param {string|number|bigint} jobIdInput
   * @param {{ reason?: string, optParams?: string }} [args]
   * @returns {Promise<import('../client-interface.mjs').Erc8183TxResult>}
   */
  async function complete(jobIdInput, args = {}) {
    return writeEvaluatorCall('complete', jobIdInput, args);
  }

  /**
   * Evaluator refunds the client: writeContract reject(jobId,...). Returns the
   * broadcast tx hash as txRef. Same Submitted-only contract precondition as
   * complete.
   *
   * @param {string|number|bigint} jobIdInput
   * @param {{ reason?: string, optParams?: string }} [args]
   * @returns {Promise<import('../client-interface.mjs').Erc8183TxResult>}
   */
  async function reject(jobIdInput, args = {}) {
    return writeEvaluatorCall('reject', jobIdInput, args);
  }

  /**
   * Shared complete/reject broadcast path. Requires a wallet client (operator
   * evaluator key). `reason` is the bytes32 attestation word (a DeliveryProof
   * receipt digest, e.g. "0x…"); `optParams` is extra calldata bytes (defaults to
   * "0x"). The chain is the source of truth for the Submitted-only precondition —
   * any revert is wrapped as Erc8183ClientError; this client adds NO autonomous
   * retry/finality policy (operator-owned).
   *
   * @param {'complete'|'reject'} fn
   * @param {string|number|bigint} jobIdInput
   * @param {{ reason?: string, optParams?: string }} args
   * @returns {Promise<import('../client-interface.mjs').Erc8183TxResult>}
   */
  async function writeEvaluatorCall(fn, jobIdInput, args = {}) {
    if (!walletClient) {
      throw new Erc8183ClientError(`[erc8183-viem] ${fn} requires an evaluator wallet: pass opts.account (or opts.walletClient) when constructing the viem client`);
    }
    const jobId = normalizeJobIdToString(jobIdInput);
    const jobIdArg = toJobIdBigInt(jobIdInput);
    const reason = normalizeReason(viem, args ? args.reason : undefined, jobId);
    const optParams = normalizeOptParams(viem, args ? args.optParams : undefined, jobId);
    let txRef;
    try {
      txRef = await walletClient.writeContract({
        address,
        abi,
        functionName: fn,
        args: [jobIdArg, reason, optParams],
        // account/chain are bound on the wallet client; pass them explicitly too
        // so an injected walletClient without a default account still works.
        account: walletClient.account ?? resolvedAccount ?? undefined,
        chain,
      });
    } catch (cause) {
      throw new Erc8183ClientError(`[erc8183-viem] ${fn}(${jobId}) failed: ${describeError(cause)}`, { cause });
    }
    return { txRef: String(txRef) };
  }

  return {
    getJob,
    complete,
    reject,
    // Read-only handles so an operator can inspect/extend wiring (e.g. wait for a
    // receipt under their own finality policy). Frozen view; not part of the
    // Erc8183Client contract the rail depends on.
    get publicClient() {
      return publicClient;
    },
    get walletClient() {
      return walletClient;
    },
    get address() {
      return address;
    },
    get abi() {
      return abi;
    },
  };
}

/**
 * Parse the human-readable ERC8183_JOB_ABI into a viem ABI object array. Wrapped
 * so a malformed ABI surfaces as Erc8183ClientError rather than a raw viem throw.
 *
 * @param {typeof import('viem')} viem
 * @returns {ReadonlyArray<object>}
 */
function parseJobAbi(viem) {
  try {
    return viem.parseAbi(Array.from(ERC8183_JOB_ABI));
  } catch (cause) {
    throw new Erc8183ClientError(`[erc8183-viem] failed to parse ERC8183_JOB_ABI: ${describeError(cause)}`, { cause });
  }
}

/**
 * Validate/checksum the contract address via viem. No default address ever: an
 * absent or malformed address fails closed.
 *
 * @param {typeof import('viem')} viem
 * @param {string} addressInput
 * @returns {`0x${string}`}
 */
function normalizeAddress(viem, addressInput) {
  if (typeof viem.isAddress === 'function' && !viem.isAddress(addressInput)) {
    throw new Erc8183ClientError(`[erc8183-viem] jobContractAddress is not a valid address: ${String(addressInput)}`);
  }
  if (typeof viem.getAddress === 'function') {
    try {
      return viem.getAddress(addressInput);
    } catch (cause) {
      throw new Erc8183ClientError(`[erc8183-viem] jobContractAddress is not a valid address: ${describeError(cause)}`, { cause });
    }
  }
  return /** @type {`0x${string}`} */ (addressInput);
}

/**
 * Resolve a viem chain. Priority: explicit opts.chain, else a chain derived from
 * the numeric chainId (display-only native currency). The rpcUrl is plumbed into
 * the derived chain's rpcUrls AND the transport, so writeContract has a chain id.
 *
 * @param {typeof import('viem')} viem
 * @param {{ chain?: import('viem').Chain, chainId?: number, opts: Object }} args
 * @returns {import('viem').Chain|undefined}
 */
function resolveChain(viem, { chain, chainId, opts }) {
  if (chain && typeof chain === 'object') return chain;
  if (chainId === undefined || chainId === null) {
    // No chain id: a read-only public client can still operate (viem allows a
    // chainless client for reads). Writes will require the chain id; we let viem
    // surface that if a write is attempted without one.
    return undefined;
  }
  const id = Number(chainId);
  if (!Number.isInteger(id) || id <= 0) {
    throw new Erc8183ClientError(`[erc8183-viem] opts.chainId must be a positive integer when provided (got ${String(chainId)})`);
  }
  const nc = opts.nativeCurrency && typeof opts.nativeCurrency === 'object' ? opts.nativeCurrency : {};
  const rpcUrl = typeof opts.rpcUrl === 'string' ? opts.rpcUrl : undefined;
  const rpcUrls = rpcUrl
    ? { default: { http: [rpcUrl] }, public: { http: [rpcUrl] } }
    : { default: { http: [] }, public: { http: [] } };
  const define = typeof viem.defineChain === 'function' ? viem.defineChain : (/** @param {any} c */ (c) => c);
  return define({
    id,
    name: typeof opts.chainName === 'string' && opts.chainName.length > 0 ? opts.chainName : 'erc8183-operator-chain',
    nativeCurrency: {
      name: typeof nc.name === 'string' ? nc.name : 'Ether',
      symbol: typeof nc.symbol === 'string' ? nc.symbol : 'ETH',
      decimals: Number.isInteger(nc.decimals) ? nc.decimals : 18,
    },
    rpcUrls,
  });
}

/**
 * Resolve the evaluator signer. Accepts an existing viem Account object, or a
 * 0x-prefixed private key string (lazily wrapped via viem/accounts). Returns null
 * when no account is supplied (read-only client).
 *
 * @param {typeof import('viem')} viem
 * @param {import('viem').Account|string|undefined} account
 * @returns {Promise<import('viem').Account|null>}
 */
async function resolveAccount(viem, account) {
  if (account === undefined || account === null) return null;
  if (typeof account === 'object') {
    return /** @type {import('viem').Account} */ (account);
  }
  if (typeof account === 'string') {
    if (!/^0x[0-9a-fA-F]{64}$/.test(account)) {
      throw new Erc8183ClientError('[erc8183-viem] opts.account string must be a 0x-prefixed 32-byte private key, or pass a viem Account object');
    }
    let accounts;
    try {
      accounts = await import('viem/accounts');
    } catch (cause) {
      throw new Erc8183ClientError("[erc8183-viem] could not load 'viem/accounts' to wrap the private key; pass a viem Account object instead", { cause });
    }
    try {
      return accounts.privateKeyToAccount(/** @type {`0x${string}`} */ (account));
    } catch (cause) {
      throw new Erc8183ClientError(`[erc8183-viem] failed to derive account from private key: ${describeError(cause)}`, { cause });
    }
  }
  throw new Erc8183ClientError(`[erc8183-viem] opts.account must be a viem Account or a 0x private-key string (got ${typeof account})`);
}

/**
 * Project the contract getJob() tuple onto the adapter's Erc8183JobView. viem
 * returns either a positional array or, for named outputs, an object — we accept
 * both. Amount is returned as a string (bigint-safe) so downstream numeric
 * comparison (the rail binds amount/currency) is not lossy.
 *
 * @param {string} jobId
 * @param {unknown} raw
 * @param {(status: number|bigint|string) => (import('../job-status.mjs').JobStatusValue|string)} mapStatus
 * @param {`0x${string}`} address
 * @returns {import('../client-interface.mjs').Erc8183JobView}
 */
function normalizeJobView(jobId, raw, mapStatus, address) {
  const { statusRaw, amountRaw, currencyRaw } = extractJobFields(raw);
  if (isEmptyJob(statusRaw, amountRaw, currencyRaw)) {
    // An all-zero tuple from a non-reverting contract means "no such job".
    throw new Erc8183JobNotFoundError(`[erc8183-viem] job ${jobId} not found at ${address} (empty job tuple)`, { jobId });
  }
  let status;
  try {
    status = mapStatus(statusRaw);
  } catch (cause) {
    throw new Erc8183ClientError(`[erc8183-viem] job ${jobId} returned unmappable status ${String(statusRaw)}: ${describeError(cause)}`, { cause });
  }
  if (!isJobStatus(status)) {
    throw new Erc8183ClientError(`[erc8183-viem] job ${jobId} mapped to unknown status ${JSON.stringify(status)} (contract enum / ABI mismatch)`);
  }
  return {
    jobId,
    status,
    amount: normalizeAmount(amountRaw),
    currency: normalizeCurrency(currencyRaw),
  };
}

/**
 * Pull status/amount/currency out of viem's getJob result, accepting both the
 * positional-array form and the named-object form. The ABI declares:
 *   (uint8 status, address client, address provider, address evaluator,
 *    uint256 amount, address currency, bytes32 deliverableHash)
 *
 * @param {unknown} raw
 * @returns {{ statusRaw: unknown, amountRaw: unknown, currencyRaw: unknown }}
 */
function extractJobFields(raw) {
  if (Array.isArray(raw)) {
    return { statusRaw: raw[0], amountRaw: raw[4], currencyRaw: raw[5] };
  }
  if (raw && typeof raw === 'object') {
    const o = /** @type {Record<string, unknown>} */ (raw);
    return {
      statusRaw: o.status,
      amountRaw: o.amount,
      currencyRaw: o.currency,
    };
  }
  throw new Erc8183ClientError(`[erc8183-viem] getJob returned an unexpected shape: ${describeError(raw)}`);
}

/**
 * @param {unknown} statusRaw
 * @param {unknown} amountRaw
 * @param {unknown} currencyRaw
 * @returns {boolean}
 */
function isEmptyJob(statusRaw, amountRaw, currencyRaw) {
  const statusZero = statusRaw === undefined || statusRaw === null
    || (typeof statusRaw === 'bigint' ? statusRaw === 0n : Number(statusRaw) === 0);
  const amountZero = amountRaw === undefined || amountRaw === null
    || (typeof amountRaw === 'bigint' ? amountRaw === 0n : Number(amountRaw) === 0);
  const currencyZero = currencyRaw === undefined || currencyRaw === null
    || currencyRaw === '0x0000000000000000000000000000000000000000'
    || currencyRaw === '0x';
  return statusZero && amountZero && currencyZero;
}

/**
 * Default uint8 -> JobStatus projection. Accepts a number, bigint, or numeric
 * string index. An out-of-range index is a contract/ABI mismatch and throws.
 *
 * @param {number|bigint|string} statusRaw
 * @returns {import('../job-status.mjs').JobStatusValue}
 */
function defaultMapStatus(statusRaw) {
  // A contract that already returns the string name (e.g. a viem-decoded enum
  // configured with string members) passes straight through if recognized.
  if (typeof statusRaw === 'string' && isJobStatus(statusRaw)) {
    return /** @type {import('../job-status.mjs').JobStatusValue} */ (statusRaw);
  }
  const idx = typeof statusRaw === 'bigint' ? Number(statusRaw) : Number(statusRaw);
  if (!Number.isInteger(idx) || idx < 0 || idx >= JOB_STATUS_BY_INDEX.length) {
    throw new Erc8183ClientError(`[erc8183-viem] status index ${String(statusRaw)} is out of range 0..${JOB_STATUS_BY_INDEX.length - 1}`);
  }
  return JOB_STATUS_BY_INDEX[idx];
}

/**
 * Normalize the escrow amount to a bigint-safe string. uint256 amounts can exceed
 * Number.MAX_SAFE_INTEGER, so we never coerce to a JS number here.
 *
 * @param {unknown} amountRaw
 * @returns {string}
 */
function normalizeAmount(amountRaw) {
  if (typeof amountRaw === 'bigint') return amountRaw.toString();
  if (typeof amountRaw === 'number') return String(amountRaw);
  if (typeof amountRaw === 'string') return amountRaw;
  return String(amountRaw ?? '');
}

/**
 * Normalize the currency field. The ABI types currency as an address; we return
 * it as a string token/address identifier so the rail's currency binding compares
 * stable values.
 *
 * @param {unknown} currencyRaw
 * @returns {string}
 */
function normalizeCurrency(currencyRaw) {
  if (typeof currencyRaw === 'string') return currencyRaw;
  return String(currencyRaw ?? '');
}

/**
 * Normalize the bytes32 `reason` attestation word. Accepts a 0x-prefixed 32-byte
 * hex string (a DeliveryProof receipt digest is exactly this); defaults to the
 * 32-byte zero word when omitted. A malformed reason fails closed.
 *
 * @param {typeof import('viem')} viem
 * @param {unknown} reason
 * @param {string} jobId
 * @returns {`0x${string}`}
 */
function normalizeReason(viem, reason, jobId) {
  const ZERO32 = '0x0000000000000000000000000000000000000000000000000000000000000000';
  if (reason === undefined || reason === null) return /** @type {`0x${string}`} */ (ZERO32);
  if (typeof reason !== 'string') {
    throw new Erc8183ClientError(`[erc8183-viem] reason for job ${jobId} must be a 0x-prefixed bytes32 hex string (got ${typeof reason})`);
  }
  if (!/^0x[0-9a-fA-F]{64}$/.test(reason)) {
    throw new Erc8183ClientError(`[erc8183-viem] reason for job ${jobId} must be a 0x-prefixed 32-byte (64 hex char) word; got ${reason.length} chars`);
  }
  // Validate via viem when available (size guard); fall back to the regex above.
  if (typeof viem.isHex === 'function' && !viem.isHex(reason)) {
    throw new Erc8183ClientError(`[erc8183-viem] reason for job ${jobId} is not valid hex`);
  }
  return /** @type {`0x${string}`} */ (reason);
}

/**
 * Normalize the `optParams` calldata bytes. Defaults to empty bytes ("0x"). A
 * non-hex value fails closed rather than being silently dropped.
 *
 * @param {typeof import('viem')} viem
 * @param {unknown} optParams
 * @param {string} jobId
 * @returns {`0x${string}`}
 */
function normalizeOptParams(viem, optParams, jobId) {
  if (optParams === undefined || optParams === null) return '0x';
  if (typeof optParams !== 'string') {
    throw new Erc8183ClientError(`[erc8183-viem] optParams for job ${jobId} must be a 0x-prefixed hex string (got ${typeof optParams})`);
  }
  const isHexShape = /^0x([0-9a-fA-F]{2})*$/.test(optParams);
  const viemHexOk = typeof viem.isHex === 'function' ? viem.isHex(optParams) : true;
  if (!isHexShape || !viemHexOk) {
    throw new Erc8183ClientError(`[erc8183-viem] optParams for job ${jobId} must be 0x-prefixed even-length hex bytes`);
  }
  return /** @type {`0x${string}`} */ (optParams);
}

/**
 * Normalize a jobId to its canonical string key (matches the in-memory client and
 * the rail's holdId keying).
 *
 * @param {string|number|bigint} jobIdInput
 * @returns {string}
 */
function normalizeJobIdToString(jobIdInput) {
  if (jobIdInput === null || jobIdInput === undefined) {
    throw new Erc8183ClientError('[erc8183-viem] jobId is required');
  }
  const t = typeof jobIdInput;
  if (t !== 'string' && t !== 'number' && t !== 'bigint') {
    throw new Erc8183ClientError(`[erc8183-viem] jobId must be a string, number, or bigint (got ${t})`);
  }
  const jobId = String(jobIdInput);
  if (jobId.length === 0) {
    throw new Erc8183ClientError('[erc8183-viem] jobId must be a non-empty string');
  }
  return jobId;
}

/**
 * Coerce a jobId to the bigint the uint256 ABI argument requires. The ERC-8183
 * job key is a uint256; a non-integer jobId is an operator error and fails closed.
 *
 * @param {string|number|bigint} jobIdInput
 * @returns {bigint}
 */
function toJobIdBigInt(jobIdInput) {
  try {
    if (typeof jobIdInput === 'bigint') return jobIdInput;
    if (typeof jobIdInput === 'number') {
      if (!Number.isInteger(jobIdInput) || jobIdInput < 0) {
        throw new Error('jobId number must be a non-negative integer');
      }
      return BigInt(jobIdInput);
    }
    const s = String(jobIdInput).trim();
    if (!/^\d+$/.test(s)) {
      throw new Error('jobId string must be a base-10 non-negative integer for the uint256 ABI argument');
    }
    return BigInt(s);
  } catch (cause) {
    throw new Erc8183ClientError(`[erc8183-viem] jobId ${String(jobIdInput)} is not a valid uint256: ${describeError(cause)}`, { cause });
  }
}

/**
 * Decide whether a readContract failure means "no such job" vs a genuine
 * transport/ABI/contract failure. We are STRICT and fail-closed: ONLY a clear
 * "the contract returned no data" signal (viem ContractFunctionZeroDataError, or a
 * 'returned no data' message) reads as an absent job. A plain revert, or any other
 * execution error, stays an Erc8183ClientError — so transient RPC/contract trouble
 * is never mistaken for an absent job (which could let a caller fail open). We do
 * NOT treat a bare 'reverted' or '0x' substring as not-found.
 *
 * @param {unknown} cause
 * @returns {boolean}
 */
function looksLikeNotFound(cause) {
  const name = cause && typeof cause === 'object' && 'name' in cause ? String(/** @type {any} */ (cause).name) : '';
  if (name === 'ContractFunctionZeroDataError') return true;
  const msg = errorMessage(cause).toLowerCase();
  if (msg.includes('returned no data') || msg.includes('zero data')) return true;
  return false;
}

/**
 * Best-effort short description of an arbitrary thrown value for log messages.
 * @param {unknown} err
 * @returns {string}
 */
function describeError(err) {
  const msg = errorMessage(err);
  return msg.length > 0 ? msg : String(err);
}

/**
 * @param {unknown} err
 * @returns {string}
 */
function errorMessage(err) {
  if (err && typeof err === 'object') {
    const e = /** @type {any} */ (err);
    if (typeof e.shortMessage === 'string' && e.shortMessage.length > 0) return e.shortMessage;
    if (typeof e.message === 'string') return e.message;
  }
  if (typeof err === 'string') return err;
  return '';
}

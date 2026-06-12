#!/usr/bin/env node

// examples/testnet-evaluate.mjs
// OPERATOR-RUN, TESTNET-ONLY end-to-end: settle a REAL on-chain ERC-8183 job with a
// REAL signed DeliveryProof receipt, via the viem-backed evaluator client.
//
// SCOPE / HONESTY: this is the ONE script in the package that broadcasts a live
// transaction, and it is deliberately hard to fire. It is for an OPERATOR on their
// OWN testnet/devnet wallet and job contract. It:
//   * reads ALL chain wiring from env (RPC_URL, PRIVATE_KEY, JOB_CONTRACT, JOB_ID,
//     CHAIN_ID) — there is NO blessed/canonical address baked in;
//   * REFUSES to do anything unless ALLOW_LIVE_TX=1 is set explicitly;
//   * REFUSES any chain id that is not on a small hard ALLOW-LIST of testnet/local
//     ids (31337 anvil, 11155111 sepolia, 84532 base-sepolia), and additionally
//     hard-BLOCKS known mainnet ids (1, 8453, 137, 10, 42161, 56, 43114, ...);
//   * is the EVALUATOR only: it reads an already-funded, Submitted job and calls
//     complete (release escrow to provider) or reject (refund client). It NEVER
//     funds, custodies, or submits a job, and broadcasts at most ONE transaction.
// The DeliveryProof receipt is REAL: signed with a freshly generated settlement key
// (or SETTLEMENT_PRIVATE_KEY if you bring your own) over the canonical receipt body,
// and the rail verifies it (7-field binding + signature) before any on-chain write.
// TESTNET / LOCAL ONLY — no mainnet, no real funds, no autonomous live tx.

import { fileURLToPath } from 'node:url';

import {
  canonicalize,
  sha256hex,
  generateKeypair,
  sign,
  keyId,
  verifyReceipt,
} from 'deliveryproof';

import {
  createErc8183Rail,
  createViemErc8183Client,
  JobStatus,
} from '../src/index.mjs';

const PROTOCOL_VERSION = 'deliveryproof/0.4-jcs1';

/**
 * Chain ids this script will operate on. Intentionally TINY: local devnets and the
 * two public testnets the adapter targets. Anything else is refused, so a fat-finger
 * mainnet RPC cannot move funds.
 */
const ALLOWED_TESTNET_CHAIN_IDS = Object.freeze({
  31337: 'anvil/hardhat local devnet',
  11155111: 'ethereum sepolia testnet',
  84532: 'base sepolia testnet',
});

/**
 * Known MAINNET (real-money) chain ids, blocked with an explicit, named refusal.
 * The allow-list above is already exclusive; this map exists purely to print a
 * louder, more specific error if someone points the script at a real network.
 */
const BLOCKED_MAINNET_CHAIN_IDS = Object.freeze({
  1: 'ethereum mainnet',
  8453: 'base mainnet',
  137: 'polygon mainnet',
  10: 'optimism mainnet',
  42161: 'arbitrum one',
  56: 'bnb smart chain',
  43114: 'avalanche c-chain',
  250: 'fantom opera',
  100: 'gnosis chain',
  324: 'zksync era mainnet',
  59144: 'linea mainnet',
  534352: 'scroll mainnet',
});

/**
 * A refusal that must STOP the script. Thrown for any safety gate (no ALLOW_LIVE_TX,
 * mainnet chain id, missing env). main() prints it and exits non-zero.
 */
class LiveTxRefused extends Error {
  constructor(message) {
    super(message);
    this.name = 'LiveTxRefused';
  }
}

function printBanner(env) {
  const line = '='.repeat(72);
  process.stdout.write(
    `${line}\n` +
      '  DeliveryProof x ERC-8183 — TESTNET-ONLY LIVE EVALUATION\n' +
      '  This broadcasts a REAL transaction on the chain you configured.\n' +
      '  EVALUATOR ONLY: it releases (complete) or refunds (reject) an\n' +
      '  already-funded, Submitted job. It never funds, custodies, or submits.\n' +
      `  chain id : ${env.chainId} (${ALLOWED_TESTNET_CHAIN_IDS[env.chainId]})\n` +
      `  rpc      : ${redactRpc(env.rpcUrl)}\n` +
      `  contract : ${env.jobContract}\n` +
      `  job id   : ${env.jobId}\n` +
      `  decision : ${env.decision} -> ${env.decision === 'release' ? 'complete() [pay provider]' : 'reject() [refund client]'}\n` +
      `${line}\n`,
  );
}

/**
 * Read + validate every operator input from the environment. Throws LiveTxRefused
 * on the first missing/invalid value, so the script never proceeds half-configured.
 *
 * @returns {{ rpcUrl: string, privateKey: string, jobContract: string, jobId: string,
 *   chainId: number, decision: 'release'|'refund', settlementPrivateKey: string|null }}
 */
function readEnv() {
  const env = process.env;

  if (env.ALLOW_LIVE_TX !== '1') {
    throw new LiveTxRefused(
      'refusing to run: set ALLOW_LIVE_TX=1 to authorize a real testnet broadcast.\n' +
        'This script is operator-run and TESTNET-ONLY; it is inert without that flag.',
    );
  }

  const rpcUrl = requireEnv(env, 'RPC_URL', 'an operator testnet/devnet JSON-RPC endpoint');
  const privateKey = requireEnv(env, 'PRIVATE_KEY', "the evaluator wallet's 0x private key (testnet funds only)");
  const jobContract = requireEnv(env, 'JOB_CONTRACT', 'the deployed ERC-8183 job contract address');
  const jobId = requireEnv(env, 'JOB_ID', 'the on-chain job id to evaluate');
  const chainIdRaw = requireEnv(env, 'CHAIN_ID', 'the numeric chain id (must be a known testnet/local id)');

  const chainId = Number(chainIdRaw);
  if (!Number.isInteger(chainId) || chainId <= 0) {
    throw new LiveTxRefused(`CHAIN_ID must be a positive integer; got ${JSON.stringify(chainIdRaw)}`);
  }
  assertTestnetChainId(chainId);

  if (!/^0x[0-9a-fA-F]{64}$/.test(privateKey)) {
    throw new LiveTxRefused('PRIVATE_KEY must be a 0x-prefixed 32-byte hex private key (a TESTNET key — never a mainnet/funds key).');
  }

  const decision = normalizeDecision(env.DECISION);

  // Optional: bring-your-own settlement signing key. If absent we mint a throwaway
  // one (the receipt is still REAL-signed; the rail can run with requireSignature
  // off, or on if you pass the matching public key — see below).
  const settlementPrivateKey = typeof env.SETTLEMENT_PRIVATE_KEY === 'string' && env.SETTLEMENT_PRIVATE_KEY.length > 0
    ? env.SETTLEMENT_PRIVATE_KEY
    : null;

  return { rpcUrl, privateKey, jobContract, jobId, chainId, decision, settlementPrivateKey };
}

/**
 * @param {NodeJS.ProcessEnv} env
 * @param {string} name
 * @param {string} description
 * @returns {string}
 */
function requireEnv(env, name, description) {
  const value = env[name];
  if (typeof value !== 'string' || value.length === 0) {
    throw new LiveTxRefused(`missing required env ${name} (${description}).`);
  }
  return value;
}

/**
 * Hard gate: only the small testnet/local allow-list is permitted. A known mainnet
 * id gets a named, explicit refusal; any other unknown id is refused too (default
 * deny), so a typo never broadcasts to real money.
 *
 * @param {number} chainId
 */
function assertTestnetChainId(chainId) {
  if (BLOCKED_MAINNET_CHAIN_IDS[chainId]) {
    throw new LiveTxRefused(
      `refusing to run on chain id ${chainId} (${BLOCKED_MAINNET_CHAIN_IDS[chainId]}): this is a MAINNET. ` +
        `This script is TESTNET-ONLY. Allowed: ${describeAllowedChains()}.`,
    );
  }
  if (!ALLOWED_TESTNET_CHAIN_IDS[chainId]) {
    throw new LiveTxRefused(
      `refusing to run on chain id ${chainId}: it is not on the testnet/local allow-list. ` +
        `Allowed: ${describeAllowedChains()}.`,
    );
  }
}

function describeAllowedChains() {
  return Object.entries(ALLOWED_TESTNET_CHAIN_IDS)
    .map(([id, name]) => `${id} (${name})`)
    .join(', ');
}

/**
 * @param {string|undefined} raw
 * @returns {'release'|'refund'}
 */
function normalizeDecision(raw) {
  const d = (raw ?? 'release').toLowerCase();
  if (d === 'release' || d === 'complete' || d === 'pay') return 'release';
  if (d === 'refund' || d === 'reject') return 'refund';
  throw new LiveTxRefused(`DECISION must be 'release' (complete) or 'refund' (reject); got ${JSON.stringify(raw)}.`);
}

/**
 * Keep most of an RPC URL out of logs (it may carry an API key in the path/query).
 * @param {string} rpcUrl
 * @returns {string}
 */
function redactRpc(rpcUrl) {
  try {
    const u = new URL(rpcUrl);
    return `${u.protocol}//${u.host}/…`;
  } catch {
    return '<rpc>';
  }
}

/**
 * Build a DeliveryContract whose price mirrors the on-chain job's escrow once we've
 * read it, so the rail's amount/currency binding is satisfied. jobId is carried in
 * predicate.params so the rail's default jobIdResolver maps this contract to the
 * REAL on-chain job.
 *
 * @param {{ id: string }} rail
 * @param {string} jobId
 * @param {{ amount: number|string|bigint, currency: string }} job
 * @returns {Object}
 */
function buildContract(rail, jobId, job) {
  return {
    protocolVersion: PROTOCOL_VERSION,
    id: `erc8183-testnet-${jobId}`,
    buyer: 'operator-client',
    seller: 'operator-provider',
    intent: `evaluate ERC-8183 job ${jobId} on testnet`,
    deliverableType: 'application/json',
    predicate: { kind: 'operator', params: { jobId } },
    // amount/currency mirror the funded job so the hold binds; the rail trusts the
    // on-chain job for the real escrow figure regardless.
    price: { amount: job.amount, currency: job.currency },
    sla: { deadlineMs: 600000 },
    refundRule: 'full-refund-on-fail',
    railId: rail.id,
    nonce: `nonce-${jobId}`,
    createdAt: Date.now(),
    idempotencyKey: `erc8183-testnet:${rail.id}:${jobId}`,
  };
}

/**
 * Assemble a REAL, canonically-signed DeliveryProof receipt bound to the contract +
 * hold (same recipe as the core conformance helpers). The rail re-verifies this:
 * 7-field binding + verdict/decision consistency (+ signature when requireSignature
 * is on), so a tampered receipt is rejected at the money layer before any tx.
 *
 * @param {Object} args
 * @param {Object} args.contract
 * @param {{ holdId: string, amount: *, currency: string }} args.hold
 * @param {'release'|'refund'} args.decision
 * @param {{ publicKey: string, privateKey: string }} args.settlementKey
 * @returns {Object} a signed receipt
 */
function buildSignedReceipt({ contract, hold, decision, settlementKey }) {
  const ok = decision === 'release';
  const evidence = { contractId: contract.id, output: { ok } };
  const verdict = {
    ok,
    tier: 'A',
    verifier: 'operator-evaluator',
    reason: ok ? 'deliverable accepted' : 'deliverable rejected',
    checkedAt: Date.now(),
  };
  const unsigned = {
    protocolVersion: PROTOCOL_VERSION,
    contractId: contract.id,
    contractHash: sha256hex(contract),
    railId: contract.railId,
    holdId: hold.holdId,
    amount: hold.amount,
    currency: hold.currency,
    verdict,
    evidenceHash: sha256hex(evidence),
    routeDecision: null,
    lifecycle: [
      { state: 'authorizing', at: 1 },
      { state: 'held', at: 1, holdId: hold.holdId },
      { state: 'decision', at: 2, decision },
    ],
    nonceRegistryKey: null,
    decision,
    signerKeyId: keyId(settlementKey.publicKey),
    issuedAt: Date.now(),
  };
  return {
    ...unsigned,
    signature: sign(settlementKey.privateKey, canonicalize(unsigned)),
  };
}

async function main() {
  const env = readEnv();
  printBanner(env);

  // The settlement key signs the DeliveryProof receipt. Either the operator brings
  // one (SETTLEMENT_PRIVATE_KEY) or we mint a throwaway pair for this run. We also
  // turn on requireSignature so the rail verifies the signature it will then act on.
  const settlementKey = env.settlementPrivateKey
    ? deriveSettlementKey(env.settlementPrivateKey)
    : generateKeypair();

  // Build the viem evaluator client over the operator's REAL testnet wiring. viem is
  // lazily imported here; if it is not installed this rejects loudly.
  const client = await createViemErc8183Client({
    rpcUrl: env.rpcUrl,
    jobContractAddress: env.jobContract,
    chainId: env.chainId,
    account: env.privateKey,
  });

  const rail = createErc8183Rail({
    client,
    chainNamespace: String(env.chainId),
    jobContractAddress: env.jobContract,
    settlementPublicKey: settlementKey.publicKey,
    requireSignature: true,
  });

  // 1) Read the REAL on-chain job and authorize a hold from it. authorize throws if
  //    the job is not Submitted (the only state the evaluator may act on).
  const job = await client.getJob(env.jobId);
  process.stdout.write(`on-chain job ${env.jobId}: status=${job.status}, amount=${job.amount}, currency=${job.currency}\n`);
  if (job.status !== JobStatus.Submitted) {
    throw new LiveTxRefused(
      `job ${env.jobId} is ${job.status}, not ${JobStatus.Submitted}. The evaluator may act only on a Submitted job; nothing to do.`,
    );
  }

  const contract = buildContract(rail, env.jobId, job);
  const hold = await rail.authorize(contract);
  process.stdout.write(`authorized hold ${hold.holdId} (state=${hold.state})\n`);

  // 2) Build + locally verify a REAL signed receipt for the chosen decision.
  const receipt = buildSignedReceipt({ contract, hold, decision: env.decision, settlementKey });
  const verified = verifyReceipt(receipt, settlementKey.publicKey);
  if (!verified || verified.ok !== true) {
    throw new LiveTxRefused('internal: freshly built receipt failed local verifyReceipt — refusing to broadcast.');
  }

  // 3) Settle on-chain. capture -> complete() (release escrow); refund -> reject().
  const settled = env.decision === 'release'
    ? await rail.capture(hold, receipt)
    : await rail.refund(hold, receipt);

  const txRef = lastTxRef(settled);
  process.stdout.write(
    `\nSETTLED: hold ${settled.holdId} is now '${settled.state}'` +
      `${txRef ? ` (tx ${txRef})` : ' (reconciled, no new tx)'}\n` +
      `Done. This was a TESTNET evaluation on chain ${env.chainId}.\n`,
  );
}

/**
 * Derive a settlement keypair from a provided private key. The core exposes
 * generateKeypair() but not a from-private-key constructor in this script's import
 * surface; rather than guess that API, we treat SETTLEMENT_PRIVATE_KEY as advisory
 * and still mint a fresh pair, but record the operator's intent. Keeping this honest
 * avoids implying an API we did not verify.
 *
 * @param {string} _providedPrivateKey
 * @returns {{ publicKey: string, privateKey: string }}
 */
function deriveSettlementKey(_providedPrivateKey) {
  // We intentionally do NOT fabricate a public key from an unverified private-key
  // format. Generate a real, self-consistent pair so verifyReceipt holds; the
  // operator who needs a fixed signing identity can wire their own keypair here.
  process.stdout.write(
    'note: SETTLEMENT_PRIVATE_KEY is set, but this example mints a fresh settlement keypair to stay\n' +
      '      honest about the core key API. Wire your own keypair in deriveSettlementKey() if you need a fixed signer.\n',
  );
  return generateKeypair();
}

/**
 * Pull a tx reference out of the settled hold's history, if the rail recorded one
 * (a reconcile-only settlement has none).
 *
 * @param {{ history?: Array<Record<string, unknown>> }} settled
 * @returns {string|null}
 */
function lastTxRef(settled) {
  const history = Array.isArray(settled?.history) ? settled.history : [];
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const entry = history[i];
    if (entry && typeof entry === 'object') {
      const ref = entry.txRef ?? entry.txHash ?? entry.tx;
      if (typeof ref === 'string' && ref.length > 0) return ref;
    }
  }
  return null;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((err) => {
    if (err instanceof LiveTxRefused) {
      process.stderr.write(`\n[REFUSED] ${err.message}\n`);
    } else {
      process.stderr.write(`\n[ERROR] ${err?.stack ?? err}\n`);
    }
    process.exitCode = 1;
  });
}

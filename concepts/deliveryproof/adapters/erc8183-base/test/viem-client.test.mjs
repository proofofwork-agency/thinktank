// test/viem-client.test.mjs
// The viem-backed Erc8183Client over a MOCKED EIP-1193 transport.
//
// SCOPE / HONESTY: this test NEVER touches a real chain, RPC endpoint, wallet, or
// private key on a public network. It drives createViemErc8183Client over a
// hand-rolled EIP-1193 request stub wired through viem's custom() transport, so it
// proves the wire behavior — getJob decodes the on-chain status, complete/reject
// encode the correct function selector + args, a reverting call surfaces
// Erc8183ClientError, and NO unexpected JSON-RPC method is ever hit — entirely
// offline. viem is an OPTIONAL dependency: when it is ABSENT this whole suite is
// SKIPPED (so the test PASSES in the dependency-free CI lane); it only runs where a
// developer has installed viem. The signing key below is a throwaway anvil/Hardhat
// well-known dev key, used ONLY to let viem assemble (not broadcast) a tx in the
// stub — it guards no funds. TESTNET / LOCAL ONLY — no mainnet, no real funds, no
// autonomous live tx.

import test from 'node:test';
import assert from 'node:assert/strict';

// Probe for the optional `viem` dependency WITHOUT crashing the dependency-free CI
// lane. We use import.meta.resolve (a deterministic, side-effect-free module
// lookup) rather than a top-level dynamic import(): under `node --test` files run
// concurrently and a racy import() of a missing specifier can resolve differently
// mid-graph-load, whereas resolve is cache-stable. If viem is absent we skip the
// ENTIRE suite so this file still PASSES.
let viem = null;
let viemAvailable = false;
try {
  import.meta.resolve('viem');
  viem = await import('viem');
  viemAvailable = true;
} catch {
  viemAvailable = false;
}

// One shared skip flag for every test. `node:test` honors { skip: true } per test;
// when viem is missing every case is reported as skipped (a PASS), so the suite is
// green with or without the optional dependency installed.
const skip = viemAvailable ? false : 'viem not installed (optional dependency); skipping on-chain client wire tests';

// A well-known throwaway dev private key (anvil/Hardhat account #0). It signs
// NOTHING on a real network here — viem only uses it to assemble a transaction
// object inside the request stub, which we intercept before any broadcast. Never a
// funds-bearing key.
const DEV_PRIVATE_KEY = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80';
const JOB_CONTRACT = '0x5FbDB2315678afecb367f032d93F642f64180aa3';
const CHAIN_ID = 31337; // anvil/local devnet

// The ABI-declared getJob output layout, mirrored from client-interface.mjs:
//   (uint8 status, address client, address provider, address evaluator,
//    uint256 amount, address currency, bytes32 deliverableHash)
// We encode a fixture tuple to feed back through the stub so the client's
// normalizeJobView decodes a genuine Submitted status / amount / currency.
const GET_JOB_OUTPUTS = [
  { name: 'status', type: 'uint8' },
  { name: 'client', type: 'address' },
  { name: 'provider', type: 'address' },
  { name: 'evaluator', type: 'address' },
  { name: 'amount', type: 'uint256' },
  { name: 'currency', type: 'address' },
  { name: 'deliverableHash', type: 'bytes32' },
];

const ZERO_ADDR = '0x0000000000000000000000000000000000000000';
const USDC_LIKE = '0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85'; // an address-shaped "currency"
const ZERO32 = '0x0000000000000000000000000000000000000000000000000000000000000000';
const SUBMITTED_STATUS_INDEX = 2; // 0 Open,1 Funded,2 Submitted,3 Completed,4 Rejected,5 Expired

/**
 * Encode a getJob() result tuple the way the contract would, for the stub to
 * return from eth_call. amount/currency feed the rail's amount/currency binding.
 *
 * @param {{ statusIndex?: number, amount?: bigint, currency?: string }} [job]
 * @returns {`0x${string}`}
 */
function encodeJobResult(job = {}) {
  return viem.encodeAbiParameters(GET_JOB_OUTPUTS, [
    job.statusIndex ?? SUBMITTED_STATUS_INDEX,
    ZERO_ADDR,
    ZERO_ADDR,
    ZERO_ADDR,
    job.amount ?? 5n,
    job.currency ?? USDC_LIKE,
    ZERO32,
  ]);
}

/**
 * Decode an eth_call/eth_sendTransaction `data` field against ERC8183_JOB_ABI and
 * return { functionName, args }. Throws if the selector is not one of our three
 * declared functions — that is itself a test signal (wrong selector encoded).
 *
 * @param {ReadonlyArray<object>} abi
 * @param {`0x${string}`} data
 * @returns {{ functionName: string, args: readonly unknown[] }}
 */
function decodeCall(abi, data) {
  return viem.decodeFunctionData({ abi, data });
}

/**
 * Build a viem-compatible EIP-1193 request stub plus a recorder of every method
 * seen, so a test can assert the EXACT set of JSON-RPC methods that were hit (and
 * fail if an unexpected one appears). The stub answers only the methods viem needs
 * to assemble + "broadcast" a contract write or read against a single chain:
 *   eth_chainId, eth_call, eth_getTransactionCount, eth_gasPrice,
 *   eth_estimateGas, eth_maxPriorityFeePerGas, eth_getBlockByNumber,
 *   eth_blockNumber, eth_sendRawTransaction / eth_sendTransaction.
 * The `handlers` map overrides/extends per-test (e.g. force eth_call to revert, or
 * capture the decoded write args). Any method with no handler and no default is a
 * hard error — so an unexpected RPC surfaces loudly.
 *
 * @param {Object} [options]
 * @param {Record<string, (params: any[]) => any>} [options.handlers]
 * @returns {{ transport: import('viem').Transport, methods: string[], calls: Array<{ method: string, params: any[] }> }}
 */
function makeStubTransport({ handlers = {} } = {}) {
  const methods = [];
  const calls = [];

  // Default JSON-RPC answers sufficient for viem to assemble a legacy/EIP-1559 tx
  // and a read. Kept minimal and explicit; a test overrides via `handlers`.
  const defaults = {
    eth_chainId: () => viem.numberToHex(CHAIN_ID),
    eth_blockNumber: () => viem.numberToHex(1n),
    eth_getBlockByNumber: () => ({
      number: viem.numberToHex(1n),
      baseFeePerGas: viem.numberToHex(1_000_000_000n),
      gasLimit: viem.numberToHex(30_000_000n),
      timestamp: viem.numberToHex(1n),
    }),
    eth_getTransactionCount: () => viem.numberToHex(0n),
    eth_gasPrice: () => viem.numberToHex(1_000_000_000n),
    eth_maxPriorityFeePerGas: () => viem.numberToHex(1_000_000_000n),
    eth_estimateGas: () => viem.numberToHex(100_000n),
    eth_call: () => encodeJobResult(),
    eth_sendRawTransaction: () => `0x${'11'.repeat(32)}`,
    eth_sendTransaction: () => `0x${'11'.repeat(32)}`,
  };

  const request = async ({ method, params }) => {
    methods.push(method);
    calls.push({ method, params: params ?? [] });
    const handler = handlers[method] ?? defaults[method];
    if (!handler) {
      // An unexpected JSON-RPC method must never be silently tolerated — the
      // adapter should touch only the small set above.
      throw new Error(`UNEXPECTED_RPC_METHOD:${method}`);
    }
    return handler(params ?? []);
  };

  const transport = viem.custom({ request });
  return { transport, methods, calls };
}

/**
 * Construct a viem client over the stub transport. Injects a publicClient and (for
 * writes) a walletClient built on the SAME stub, so getJob/complete/reject all flow
 * through our recorder. Returns the client plus the stub's method recorder.
 *
 * @param {Object} [options]
 * @param {Record<string, (params: any[]) => any>} [options.handlers]
 * @param {boolean} [options.withWallet=true]
 */
async function makeViemClient({ handlers = {}, withWallet = true } = {}) {
  const { createViemErc8183Client } = await import('../src/clients/viem.mjs');
  const stub = makeStubTransport({ handlers });
  const chain = viem.defineChain({
    id: CHAIN_ID,
    name: 'erc8183-test-local',
    nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
    rpcUrls: { default: { http: ['http://127.0.0.1:8545'] }, public: { http: ['http://127.0.0.1:8545'] } },
  });
  const { privateKeyToAccount } = await import('viem/accounts');
  const account = privateKeyToAccount(DEV_PRIVATE_KEY);

  const publicClient = viem.createPublicClient({ chain, transport: stub.transport });
  const walletClient = withWallet
    ? viem.createWalletClient({ account, chain, transport: stub.transport })
    : undefined;

  const client = await createViemErc8183Client({
    rpcUrl: 'http://127.0.0.1:8545',
    jobContractAddress: JOB_CONTRACT,
    chainId: CHAIN_ID,
    account,
    chain,
    publicClient,
    walletClient,
  });
  return { client, stub, account, abi: client.abi };
}

test('getJob: eth_call decodes the on-chain uint8 status to a JobStatus and binds amount/currency', { skip }, async () => {
  let seenCallData = null;
  const { client, stub, abi } = await makeViemClient({
    handlers: {
      eth_call: (params) => {
        // params[0] = { to, data }. Assert the call targets our contract and
        // selects getJob with the right jobId argument.
        seenCallData = params[0]?.data ?? null;
        const decoded = decodeCall(abi, params[0].data);
        assert.equal(decoded.functionName, 'getJob');
        assert.equal(decoded.args[0], 7n, 'getJob must be called with the uint256 jobId');
        assert.equal(
          String(params[0].to).toLowerCase(),
          JOB_CONTRACT.toLowerCase(),
          'eth_call must target the operator job contract address',
        );
        return encodeJobResult({ statusIndex: SUBMITTED_STATUS_INDEX, amount: 5n, currency: USDC_LIKE });
      },
    },
  });

  const job = await client.getJob('7');
  assert.equal(job.jobId, '7');
  assert.equal(job.status, 'Submitted', 'uint8 index 2 must decode to Submitted');
  assert.equal(job.amount, '5', 'amount must be the bigint-safe string from the tuple');
  assert.equal(job.currency, viem.getAddress(USDC_LIKE), 'currency must be the (checksummed) address token');

  assert.ok(seenCallData, 'eth_call must have carried encoded getJob calldata');
  // The ONLY non-trivial RPC for a read is eth_call (chainId may be probed). No
  // write/broadcast method may appear on a read path.
  assert.ok(stub.methods.includes('eth_call'), 'getJob must issue eth_call');
  for (const forbidden of ['eth_sendRawTransaction', 'eth_sendTransaction']) {
    assert.ok(!stub.methods.includes(forbidden), `getJob must not broadcast (${forbidden})`);
  }
});

test('getJob maps every uint8 status index to the right JobStatus name', { skip }, async () => {
  const expected = ['Open', 'Funded', 'Submitted', 'Completed', 'Rejected', 'Expired'];
  for (let idx = 0; idx < expected.length; idx += 1) {
    const { client } = await makeViemClient({
      handlers: {
        // A terminal/non-zero status with a non-zero amount so the tuple is never
        // mistaken for an empty (not-found) job.
        eth_call: () => encodeJobResult({ statusIndex: idx, amount: 5n, currency: USDC_LIKE }),
      },
    });
    const job = await client.getJob('1');
    assert.equal(job.status, expected[idx], `uint8 ${idx} must map to ${expected[idx]}`);
  }
});

test('getJob: an out-of-range uint8 status index fails closed as Erc8183ClientError', { skip }, async () => {
  const { Erc8183ClientError } = await import('../src/errors.mjs');
  const { client } = await makeViemClient({
    handlers: {
      eth_call: () => encodeJobResult({ statusIndex: 9, amount: 5n, currency: USDC_LIKE }),
    },
  });
  await assert.rejects(
    () => client.getJob('1'),
    (err) => {
      assert.ok(err instanceof Erc8183ClientError, `expected Erc8183ClientError, got ${err}`);
      assert.match(err.message, /out of range|status/i);
      return true;
    },
  );
});

test('getJob: an all-zero job tuple is treated as not-found (Erc8183JobNotFoundError)', { skip }, async () => {
  const { Erc8183JobNotFoundError } = await import('../src/errors.mjs');
  const { client } = await makeViemClient({
    handlers: {
      // status 0, amount 0, currency zero-address => empty job tuple.
      eth_call: () => encodeJobResult({ statusIndex: 0, amount: 0n, currency: ZERO_ADDR }),
    },
  });
  await assert.rejects(
    () => client.getJob('404'),
    (err) => {
      assert.ok(err instanceof Erc8183JobNotFoundError, `expected Erc8183JobNotFoundError, got ${err}`);
      return true;
    },
  );
});

test('complete: encodes the complete() selector + (jobId, reason, optParams) and broadcasts once', { skip }, async () => {
  const reason = `0x${'ab'.repeat(32)}`; // a 32-byte bytes32 reason word
  let decodedWrite = null;
  let writeTo = null;
  const { client, stub, abi } = await makeViemClient({
    handlers: {
      eth_sendRawTransaction: (params) => {
        // viem signs locally then submits raw; recover the calldata by parsing the
        // serialized tx so we assert the exact selector + args reached the wire.
        const tx = viem.parseTransaction(params[0]);
        writeTo = tx.to;
        decodedWrite = decodeCall(abi, tx.data);
        return `0x${'22'.repeat(32)}`;
      },
    },
  });

  const res = await client.complete('42', { reason });
  assert.equal(res.txRef, `0x${'22'.repeat(32)}`, 'txRef must be the broadcast tx hash');

  assert.ok(decodedWrite, 'complete must serialize a contract call onto the wire');
  assert.equal(decodedWrite.functionName, 'complete', 'must encode the complete() selector');
  assert.equal(decodedWrite.args[0], 42n, 'jobId arg (uint256) must be 42');
  assert.equal(String(decodedWrite.args[1]).toLowerCase(), reason.toLowerCase(), 'reason (bytes32) must round-trip');
  assert.equal(decodedWrite.args[2], '0x', 'optParams defaults to empty bytes');
  assert.equal(String(writeTo).toLowerCase(), JOB_CONTRACT.toLowerCase(), 'write must target the operator contract');

  // Exactly one broadcast.
  const broadcasts = stub.methods.filter((m) => m === 'eth_sendRawTransaction' || m === 'eth_sendTransaction');
  assert.equal(broadcasts.length, 1, 'complete must broadcast exactly one transaction');
});

test('reject: encodes the reject() selector + (jobId, reason, optParams)', { skip }, async () => {
  const reason = `0x${'cd'.repeat(32)}`;
  let decodedWrite = null;
  const { client, abi } = await makeViemClient({
    handlers: {
      eth_sendRawTransaction: (params) => {
        const tx = viem.parseTransaction(params[0]);
        decodedWrite = decodeCall(abi, tx.data);
        return `0x${'33'.repeat(32)}`;
      },
    },
  });

  const res = await client.reject('43', { reason, optParams: '0xbeef' });
  assert.equal(res.txRef, `0x${'33'.repeat(32)}`);
  assert.equal(decodedWrite.functionName, 'reject', 'must encode the reject() selector');
  assert.equal(decodedWrite.args[0], 43n);
  assert.equal(String(decodedWrite.args[1]).toLowerCase(), reason.toLowerCase());
  assert.equal(String(decodedWrite.args[2]).toLowerCase(), '0xbeef', 'optParams bytes must round-trip');
});

test('a reverting eth_call surfaces Erc8183ClientError (rail can fail closed), not a raw viem throw', { skip }, async () => {
  const { Erc8183ClientError } = await import('../src/errors.mjs');
  const { client } = await makeViemClient({
    handlers: {
      eth_call: () => {
        // Simulate a non-not-found execution failure (e.g. node/ABI trouble). The
        // client must WRAP this as Erc8183ClientError so the rail never mistakes a
        // transport error for an absent job and fails open.
        const err = new Error('execution reverted: boom');
        err.name = 'CallExecutionError';
        throw err;
      },
    },
  });
  await assert.rejects(
    () => client.getJob('99'),
    (err) => {
      assert.ok(err instanceof Erc8183ClientError, `expected Erc8183ClientError, got ${err?.name}: ${err}`);
      assert.match(err.message, /getJob\(99\)/);
      return true;
    },
  );
});

test('a reverting write surfaces Erc8183ClientError', { skip }, async () => {
  const { Erc8183ClientError } = await import('../src/errors.mjs');
  const { client } = await makeViemClient({
    handlers: {
      eth_estimateGas: () => {
        const err = new Error('execution reverted: not Submitted');
        err.name = 'EstimateGasExecutionError';
        throw err;
      },
    },
  });
  await assert.rejects(
    () => client.complete('7', { reason: `0x${'ab'.repeat(32)}` }),
    (err) => {
      assert.ok(err instanceof Erc8183ClientError, `expected Erc8183ClientError, got ${err?.name}: ${err}`);
      assert.match(err.message, /complete\(7\)/);
      return true;
    },
  );
});

test('NO unexpected JSON-RPC method is hit across getJob then complete', { skip }, async () => {
  // Wire a single client through one stub and run a read then a write, then assert
  // the union of methods seen is a SUBSET of an allow-list. An adapter that started
  // calling, say, eth_getLogs or a wallet_* method would trip this.
  const { client, stub } = await makeViemClient({
    handlers: {
      eth_sendRawTransaction: () => `0x${'44'.repeat(32)}`,
    },
  });

  await client.getJob('5');
  await client.complete('5', { reason: `0x${'ab'.repeat(32)}` });

  const allowed = new Set([
    'eth_chainId',
    'eth_blockNumber',
    'eth_getBlockByNumber',
    'eth_getTransactionCount',
    'eth_gasPrice',
    'eth_maxPriorityFeePerGas',
    'eth_estimateGas',
    'eth_fillTransaction',
    'eth_call',
    'eth_sendRawTransaction',
    'eth_sendTransaction',
  ]);
  // Note: the adapter does not choose RPC methods — viem does. This allow-list
  // tracks the methods viem's read+write flow legitimately issues (it added
  // eth_fillTransaction in the 2.5x line); a stray eth_getLogs / wallet_* / etc.
  // would still trip the assertion below.
  const unexpected = [...new Set(stub.methods)].filter((m) => !allowed.has(m));
  assert.deepEqual(unexpected, [], `unexpected JSON-RPC method(s) hit: ${unexpected.join(', ')}`);
});

test('complete without a wallet client fails closed (read-only client cannot broadcast)', { skip }, async () => {
  const { Erc8183ClientError } = await import('../src/errors.mjs');
  // Build a read-only client: no account, no walletClient. getJob works; writes must
  // refuse loudly rather than silently no-op.
  const { createViemErc8183Client } = await import('../src/clients/viem.mjs');
  const stub = makeStubTransport({});
  const chain = viem.defineChain({
    id: CHAIN_ID,
    name: 'erc8183-test-local',
    nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
    rpcUrls: { default: { http: ['http://127.0.0.1:8545'] }, public: { http: ['http://127.0.0.1:8545'] } },
  });
  const publicClient = viem.createPublicClient({ chain, transport: stub.transport });
  const client = await createViemErc8183Client({
    rpcUrl: 'http://127.0.0.1:8545',
    jobContractAddress: JOB_CONTRACT,
    chainId: CHAIN_ID,
    publicClient,
    // no account, no walletClient => read-only
  });

  assert.equal(client.walletClient, null, 'a no-account client must have no wallet client');
  await assert.rejects(
    () => client.complete('7', { reason: `0x${'ab'.repeat(32)}` }),
    (err) => {
      assert.ok(err instanceof Erc8183ClientError, `expected Erc8183ClientError, got ${err}`);
      assert.match(err.message, /wallet/i);
      return true;
    },
  );
  // And no broadcast was attempted.
  assert.ok(!stub.methods.includes('eth_sendRawTransaction'));
  assert.ok(!stub.methods.includes('eth_sendTransaction'));
});

test('a malformed bytes32 reason fails closed BEFORE any RPC is issued', { skip }, async () => {
  const { Erc8183ClientError } = await import('../src/errors.mjs');
  const { client, stub } = await makeViemClient({});
  await assert.rejects(
    () => client.complete('7', { reason: '0x1234' }), // too short for bytes32
    (err) => {
      assert.ok(err instanceof Erc8183ClientError, `expected Erc8183ClientError, got ${err}`);
      assert.match(err.message, /reason/i);
      return true;
    },
  );
  // Input validation must happen before the wire: no broadcast attempted.
  assert.ok(!stub.methods.includes('eth_sendRawTransaction'));
  assert.ok(!stub.methods.includes('eth_sendTransaction'));
});

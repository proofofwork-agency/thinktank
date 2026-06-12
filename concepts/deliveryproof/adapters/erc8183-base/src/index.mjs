// src/index.mjs
// Public barrel for @deliveryproof/rail-erc8183-base.
//
// SCOPE / HONESTY: this package is the first concrete DeliveryProof RailAdapter
// that targets the ERC-8183 ("Agentic Commerce") evaluator slot. DeliveryProof IS
// the evaluator: it reads an already-funded, Submitted on-chain job and, per its
// signed receipt, calls complete() (release escrow to provider) or reject()
// (refund the client). It NEVER funds, custodies, or submits a job; it offers no
// exactly-once / finality guarantee (the job contract and reorg policy are
// operator-owned). There is NO blessed contract address — address + chainId +
// rpcUrl are operator config. `viem` is an OPTIONAL dependency, imported lazily
// ONLY inside createViemErc8183Client; importing this barrel in plain Node never
// touches it. TESTNET / LOCAL ONLY — no mainnet, no real funds, no autonomous tx.
//
// Usage:
//   import { createErc8183Rail, createInMemoryErc8183Client } from '@deliveryproof/rail-erc8183-base';
//   const client = createInMemoryErc8183Client();
//   const rail = createErc8183Rail({ client });

export { createErc8183Rail } from './rail.mjs';

export { createInMemoryErc8183Client } from './clients/in-memory.mjs';

export {
  JobStatus,
  mapJobStatusToHoldState,
  isSettleable,
  isTerminal,
  isJobStatus,
} from './job-status.mjs';

export { ERC8183_JOB_ABI, assertErc8183Client } from './client-interface.mjs';

export { deliveryReceiptToEvaluatorCall } from './reason.mjs';

export {
  Erc8183RailError,
  Erc8183NotSettleableError,
  Erc8183JobNotFoundError,
  Erc8183ClientError,
} from './errors.mjs';

/**
 * Lazily construct a viem-backed Erc8183Client. `viem` is an OPTIONAL dependency:
 * it is imported only when this function runs, so the barrel above stays usable in
 * a plain Node process (and in CI) without viem installed. Operator config
 * (rpcUrl, account, jobContractAddress, chainId, ...) is forwarded unchanged.
 *
 * @param {Object} opts viem client options; see ./clients/viem.mjs.
 * @returns {Promise<import('./client-interface.mjs').Erc8183Client>}
 */
export async function createViemErc8183Client(opts) {
  const mod = await import('./clients/viem.mjs');
  return mod.createViemErc8183Client(opts);
}

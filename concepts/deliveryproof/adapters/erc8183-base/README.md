# @deliveryproof/rail-erc8183-base

The first real DeliveryProof `RailAdapter`: it drives an on-chain
[ERC-8183](https://eips.ethereum.org/EIPS/eip-8183) ("Agentic Commerce") job to
settlement using **DeliveryProof as the evaluator**.

ERC-8183 standardizes a Job with an escrowed budget and three roles — Client,
Provider, and Evaluator — where ONLY the evaluator may call `complete(jobId)`
(release escrow to the provider) or `reject(jobId)` (refund the client). The spec
deliberately leaves the evaluator's verification *method* undefined. DeliveryProof
fills that slot with an objective, content-checking verdict: a signed
`DeliveryReceipt` whose `decision` maps one-to-one onto `complete`/`reject`, with
the receipt hash carried as the evaluator `reason` attestation.

```text
DeliveryProof receipt.decision === 'release'  ->  complete(jobId, reason)   (pay provider)
DeliveryProof receipt.decision === 'refund'   ->  reject(jobId, reason)     (refund client)
```

## LOUD honesty (read this first)

This adapter is the ERC-8183 **evaluator only**. It is **TESTNET / LOCAL ONLY**.

- **Not custody.** It never funds, escrows, submits, or holds a job. It reads an
  already-funded, already-Submitted job and emits the evaluator decision. The
  ERC-8183 contract — not this adapter, and not DeliveryProof — owns the escrow
  and the money.
- **No mainnet, no real funds, no autonomous live transactions.** The live
  `viem` client is gated behind explicit operator config and an
  `ALLOW_LIVE_TX` opt-in (see [docs/OPERATOR-RUNBOOK.md](./docs/OPERATOR-RUNBOOK.md)).
  Out of the box, the package runs against an in-memory fake.
- **No canonical / blessed contract address.** This package ships no hardcoded
  ERC-8183 contract address, chain id, or RPC URL, and implies none. The
  contract address, chain, RPC endpoint, and signer are entirely operator
  configuration. Anyone claiming a "the" DeliveryProof ERC-8183 address is wrong.
- **The operator owns keys, gas, chain choice, RPC credentials, and finality.**
  This adapter does not manage wallets, gas, nonces, retries, or reorgs, and
  makes **no exactly-once or finality guarantee**. On-chain finality and reorg
  policy belong to the operator and the chain. See
  [ESCALATIONS.md](./ESCALATIONS.md).
- **The predicate is still load-bearing.** DeliveryProof proves delivered bytes
  satisfy a declared predicate; it does not prove external facts are true. A
  perfect proof against the wrong predicate is still wrong.

The narrow scope this package adds over the core `deliveryproof` library — and
only this — is **testnet/local on-chain submission** through an injected client
seam. See [SECURITY.md](./SECURITY.md).

## What the adapter actually does

DeliveryProof's core `settle()` flow expects a `RailAdapter` with
`authorize / capture / refund / status`. This adapter maps each onto an ERC-8183
evaluator action over a job it does **not** own:

| RailAdapter op | ERC-8183 action | Effect |
|----------------|-----------------|--------|
| `authorize(contract)` | **attach** to an existing job (read `getJob`) | Asserts the job is `Submitted`, then synthesizes a `held` Hold. Never funds or submits. |
| `capture(hold, releaseReceipt)` | `complete(jobId, reason)` | Releases escrow to the provider. |
| `refund(hold, refundReceipt)` | `reject(jobId, reason)` | Refunds the client. |
| `status(hold)` | `getJob(jobId)` | Maps the live Job status to a Hold state. |

`authorize` is an **attach**, not a create. The funding, the Open→Funded→Submitted
transitions, and the deposit all happen outside DeliveryProof. The adapter only
joins an already-funded, already-Submitted job and lets DeliveryProof decide its
release or refund. If the job is not `Submitted`, `authorize` throws
`Erc8183NotSettleableError` rather than guess.

The full Hold⇄Job state table, the attach seam, idempotency-via-`getJob`, and the
reorg stance live in [docs/STATE-MAPPING.md](./docs/STATE-MAPPING.md).

## Install

This package is part of the DeliveryProof monorepo and is workspace-linked to the
core `deliveryproof` package in [`../../concept`](../../concept). From the repo
root:

```bash
npm install
```

The core `deliveryproof` package is imported by name:

```js
import { settle, verifyReceipt } from 'deliveryproof';
import { createErc8183Rail, createInMemoryErc8183Client } from '@deliveryproof/rail-erc8183-base';
```

`viem` is an **optional** dependency. The package imports cleanly in plain Node
without it; `viem` is loaded *lazily* only when you actually call
`createViemErc8183Client()`. You do not need a chain, an RPC URL, or `viem`
installed to run the in-memory path or the conformance suite.

## The `Erc8183Client` seam

The adapter never talks to a chain directly. It talks to an injected
`Erc8183Client` — a small interface with exactly three methods:

```js
// getJob(jobId)                      -> { jobId, status, amount, currency }
// complete(jobId, { reason, optParams }) -> { txRef, status }
// reject(jobId,   { reason, optParams }) -> { txRef, status }
```

This is the single boundary between DeliveryProof's verdict logic and any wallet,
RPC, gas, or chain behavior. It lets the same rail code run against a fake in
tests and against a real testnet from the same call sites. Two clients ship:

### In-memory client (default, no chain)

`createInMemoryErc8183Client()` implements the seam over an in-process `Map` of
jobs. On `getJob` for an unknown `jobId` it auto-creates a `Submitted`,
pre-funded job (`amount: 5`, `currency: "USDC"`) so the core conformance suite —
whose fixtures price work at 5 USDC and pass no `jobId` — runs end to end. It
enforces evaluator-only + Submitted-only semantics and **throws on a second
`complete`/`reject` of an already-terminal job**, so the rail's idempotency must
come from reconciling via `getJob`, not from a lenient fake.

```js
import { createErc8183Rail, createInMemoryErc8183Client } from '@deliveryproof/rail-erc8183-base';

const client = createInMemoryErc8183Client();
const rail = createErc8183Rail({ client });
// rail.authorize / capture / refund / status now work with no chain.
```

### viem client (testnet/local on-chain)

`createViemErc8183Client({ rpcUrl, account, jobContractAddress, chainId, ... })`
implements the seam against a real EVM endpoint via `viem`'s
`readContract`/`writeContract`, using the human-readable `ERC8183_JOB_ABI`. It
imports `viem` lazily, so importing this package never requires `viem` to be
installed until you call this factory. Every required parameter — RPC URL,
account/signer, contract address, chain id — is yours to supply; the package
hardcodes none of them.

See [docs/OPERATOR-RUNBOOK.md](./docs/OPERATOR-RUNBOOK.md) for the env vars
(`RPC_URL`, `PRIVATE_KEY`, `JOB_CONTRACT`, `JOB_ID`, `CHAIN_ID`, `ALLOW_LIVE_TX`)
and the human-decision checklist before any live transaction.

## Money-safety (re-enforced at the rail)

The adapter mirrors the core durable rail's money-safety invariants at the
ERC-8183 boundary. The gates below reject a **mis-bound or internally
contradictory** receipt before any on-chain call. Since v0.10 signature
verification is no longer optional: the rail **requires** `settlementPublicKey` at
construction, which closes the **forged-but-fully-consistent** receipt — one with
correct `holdId`/`contractId`/`contractHash`/`amount`/`currency` against a real
authorized binding, which gates 1-2 alone cannot distinguish from a real one. The
gates, in order:

1. **7-field receipt⇄hold binding.** `capture`/`refund` verify `decision`,
   `holdId`, `contractId`, `contractHash`, `railId` (=== `hold.railId`),
   `amount`, and `currency` before any on-chain call.
2. **Verdict-consistency gate.** Release only if `verdict.ok === true`; refund
   only if `verdict.ok === false`. A receipt whose `decision` contradicts its
   `verdict.ok` is rejected before any submission — even with no signature key.
3. **Signature verification (closes the forged-but-consistent hole).** The rail
   requires `settlementPublicKey` at construction and calls
   `verifyReceipt(receipt, settlementPublicKey)` before any submission.
   `requireSignature` is a retained no-op alias. `allowUnsignedReceipts: true`
   skips this gate for local fixtures — never set it on a path that moves real
   value: gates 1-2 reject a mis-bound or contradictory receipt, but a forged
   receipt carrying the correct fields is indistinguishable without gate 3.
4. **Idempotency via `getJob`, not a trusting fake.** Before submitting a tx the
   rail reconciles the live job: if it is already `Completed` and this is a
   capture, it returns the captured Hold with **no** tx; if already `Rejected`
   and this is a refund, it returns the refunded Hold with no tx; the opposite
   terminal state throws a conflict. A terminals `Map` keyed
   `"<holdId>:<release|refund>:<receiptHash>"` short-circuits exact replays.

This re-enforcement is defense in depth: it does not replace the operator's own
authorization, monitoring, and finality controls on the chain side.

## Run the conformance suite

The adapter is certified by the core's exported `runRailConformance()` suite (the
same ten cases every DeliveryProof rail must pass), driven over the in-memory
client:

```bash
node examples/conformance-demo.mjs
```

`status-after-restart` shares one in-memory client instance across the simulated
restart (the job `Map` survives), exercising idempotency-via-`getJob`.

## Module map

| Module | Exports |
|--------|---------|
| `src/index.mjs` | barrel: `createErc8183Rail`, `createInMemoryErc8183Client`, `createViemErc8183Client`, `JobStatus`, `mapJobStatusToHoldState`, `isSettleable`, `isTerminal`, `ERC8183_JOB_ABI`, `assertErc8183Client`, `deliveryReceiptToEvaluatorCall`, error classes |
| `src/rail.mjs` | `createErc8183Rail(opts)` — the `RailAdapter` |
| `src/client-interface.mjs` | `ERC8183_JOB_ABI`, `assertErc8183Client` |
| `src/job-status.mjs` | `JobStatus`, `mapJobStatusToHoldState`, `isSettleable`, `isTerminal` |
| `src/reason.mjs` | `deliveryReceiptToEvaluatorCall` |
| `src/errors.mjs` | `Erc8183RailError`, `Erc8183NotSettleableError`, `Erc8183JobNotFoundError`, `Erc8183ClientError` |
| `src/clients/in-memory.mjs` | `createInMemoryErc8183Client` |
| `src/clients/viem.mjs` | `createViemErc8183Client` (lazy `viem`) |

## Documentation

- [docs/STATE-MAPPING.md](./docs/STATE-MAPPING.md) — Hold⇄Job mapping table, the
  authorize-attach seam, idempotency-via-`getJob`, and the reorg stance.
- [docs/OPERATOR-RUNBOOK.md](./docs/OPERATOR-RUNBOOK.md) — running the testnet
  example, env vars, and the human-decision checklist.
- [SECURITY.md](./SECURITY.md) — how this adapter widens the core security scope
  (and how narrowly).
- [ESCALATIONS.md](./ESCALATIONS.md) — what stays a human/operator decision.
- [CHANGELOG.md](./CHANGELOG.md) — local development slices.
- Core protocol: [`../../concept/README.md`](../../concept/README.md),
  [`../../concept/docs/ADAPTER-RFC.md`](../../concept/docs/ADAPTER-RFC.md).

## License

Apache-2.0 — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).

You may use, modify, redistribute, and build commercial or closed-source products
on this software. In exchange, Apache-2.0 §4(d) requires that you keep the
attribution in [NOTICE](./NOTICE) — the ProofOfWork Agency copyright line — visible
somewhere customary in your product (source header, docs, or a third-party
notices screen). No permission request, no fee, no obligation to open your own
changes. Just keep the credit.

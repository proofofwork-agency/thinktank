# Operator Runbook — ERC-8183 Base Adapter

How to run the ERC-8183 evaluator adapter, locally and against a **testnet**.
This adapter is the ERC-8183 ("Agentic Commerce") evaluator only. It is
**TESTNET / LOCAL ONLY** — no mainnet, no real funds, no custody, no finality
guarantee. Before any live transaction, complete the human-decision checklist at
the end of this document.

## Prerequisites

- Node v22+.
- The monorepo installed from the root (`npm install`), which workspace-links the
  core `deliveryproof` package.
- For live (testnet) runs only: `viem` installed and a funded **testnet**
  evaluator account authorized on the target ERC-8183 contract.

## Path A — local, no chain (default)

Run the rail entirely against the in-memory client. No `viem`, no RPC, no keys, no
transaction:

```bash
# Certify the adapter against the core RailAdapter conformance suite.
node examples/conformance-demo.mjs
```

This drives `authorize / capture / refund / status` over
`createInMemoryErc8183Client()` and exercises the 7-field binding, the
verdict-consistency gate, idempotent terminalization, and idempotency-via-`getJob`
(including a simulated restart that shares the in-memory job `Map`). It submits no
transaction.

This is the path CI and day-to-day development should use.

## Path B — testnet evaluate (live, gated)

`examples/testnet-evaluate.mjs` runs the same rail against a **real testnet**
through the `viem` client. It performs a live `complete`/`reject` submission **only
when** the full configuration is present and `ALLOW_LIVE_TX` is explicitly set.
Absent either, it **refuses and exits non-zero** — it does NOT dry-run on the
in-memory client (use Path A / `conformance-demo.mjs` for the no-chain path).

```bash
export RPC_URL="https://<your-testnet-rpc>"      # operator-supplied testnet RPC
export PRIVATE_KEY="0x<evaluator-testnet-key>"   # operator-owned signer; NEVER mainnet
export JOB_CONTRACT="0x<erc8183-contract>"       # operator-chosen; no canonical address
export JOB_ID="<submitted-job-id>"               # an already-funded, Submitted job
export CHAIN_ID="<testnet-chain-id>"             # e.g. a Base testnet chain id
export ALLOW_LIVE_TX="1"                          # explicit opt-in; omit and the example REFUSES

node examples/testnet-evaluate.mjs
```

### Environment variables

| Variable | Required for live tx | Meaning |
|----------|----------------------|---------|
| `RPC_URL` | yes | Testnet RPC endpoint. Operator-supplied. No default, no canonical endpoint. |
| `PRIVATE_KEY` | yes | Evaluator signer key. Operator-owned. **Testnet only.** Never a mainnet key. |
| `JOB_CONTRACT` | yes | ERC-8183 contract address. Operator-chosen. **There is no blessed/default address.** |
| `JOB_ID` | yes | The job to evaluate. Must already be funded and `Submitted`. |
| `CHAIN_ID` | yes | Target testnet chain id. Operator-chosen. |
| `ALLOW_LIVE_TX` | yes | Explicit opt-in to submit a transaction. Unset/empty ⇒ the example REFUSES and exits non-zero (no dry-run). |

If any required variable is missing, or `ALLOW_LIVE_TX` is not set, the example
**refuses and exits non-zero** — it does not dry-run on the in-memory client (use
Path A / `conformance-demo.mjs` for the no-chain path). This is intentional:
**live submission is opt-in, never the default.**

### What a live run does

1. Builds a `viem` client (`createViemErc8183Client`) from your config (lazy
   `viem` import).
2. `authorize` reads `getJob(JOB_ID)`; if the job is not `Submitted` it throws
   `Erc8183NotSettleableError` and stops — no tx.
3. The DeliveryProof verdict decides direction: a release receipt →
   `complete(jobId, reason)`; a refund receipt → `reject(jobId, reason)`.
4. Before submitting, the rail reconciles via `getJob`: an already-terminal job in
   the matching direction returns idempotently with no tx; the opposite terminal
   throws a conflict.
5. On submission, the example prints the returned `txRef`. A `txRef` is a
   submission reference, **not** a finality proof.

## Operational notes

- **Secrets.** `PRIVATE_KEY` and `RPC_URL` credentials are operator secrets. Do
  not commit them, and prefer a secret manager over shell history. The adapter
  never logs key material; keep it that way in your own wrapping code.
- **Gas.** The evaluator account must hold enough testnet gas. Gas funding, fee
  strategy, and nonce/retry handling are operator-owned; the adapter does not
  manage them.
- **Finality / reorgs.** The adapter does not wait for confirmations or guard
  against reorgs. Choose a confirmation policy appropriate to your testnet and
  treat `txRef` as "submitted," not "final." See
  [STATE-MAPPING.md](./STATE-MAPPING.md#reorg-stance).
- **Idempotency.** Re-running against the same `JOB_ID` after a successful
  terminalization is safe: the reconcile-via-`getJob` path returns idempotently
  with no second tx (or throws on an opposite-direction conflict).

## Human-decision checklist (before any live tx)

Do not set `ALLOW_LIVE_TX` until every box is a deliberate human decision. Each
maps to an item in [../ESCALATIONS.md](../ESCALATIONS.md) and the core
[`../../../concept/docs/ESCALATIONS.md`](../../../concept/docs/ESCALATIONS.md).

- [ ] **Network is testnet.** No mainnet. Confirmed `CHAIN_ID` is a testnet.
- [ ] **Contract chosen.** The target ERC-8183 `JOB_CONTRACT` is reviewed and
      operator-selected (there is no canonical/default address).
- [ ] **Signer policy.** The evaluator `PRIVATE_KEY` is an authorized evaluator on
      that contract, is testnet-only, and its custody/rotation is decided.
- [ ] **RPC policy.** The `RPC_URL` endpoint and any credentials are operator-
      supplied and approved for this environment (including CI, if applicable).
- [ ] **Gas policy.** The evaluator account is funded with testnet gas; fee/nonce/
      retry handling is decided.
- [ ] **Finality policy.** Confirmation depth and reorg-response behavior are
      decided; the team understands the adapter makes no finality guarantee.
- [ ] **Custody understood.** The team understands the adapter takes no custody;
      the ERC-8183 contract holds the escrow.
- [ ] **No real funds.** This is testnet/local only; no real-money settlement is
      being performed.

Once these are settled, a live testnet run is a deliberate, scoped operator action
— which is exactly the boundary this adapter is built to respect.

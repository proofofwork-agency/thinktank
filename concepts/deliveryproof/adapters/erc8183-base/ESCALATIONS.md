# Human Decision Register — ERC-8183 Base Adapter

These items require explicit human/operator approval before they may be used.
They are outside the scope of this adapter, which is the ERC-8183 ("Agentic
Commerce") **evaluator** only, **TESTNET / LOCAL ONLY**.

This register is additive to the core register, which already covers custody, MSB/
MTL/tax/consumer obligations, live on-chain submission, and external operator
review:
[`../../concept/docs/ESCALATIONS.md`](../../concept/docs/ESCALATIONS.md).

The core register states the general rule for live chain work; this file pins the
ERC-8183-specific decisions an operator must own before pointing this adapter at a
real (testnet) chain.

## What Stays A Human / Operator Decision

The adapter ships an in-memory fake by default and never acts live on its own.
Each of the following is an operator/human go/no-go, NOT something this package
decides or defaults:

### Mainnet vs testnet/local

This adapter is testnet/local only. **Any mainnet or real-funds use is out of
scope and requires the core live-chain go/no-go plus a deliberate human
decision.** Nothing here is built or tested for mainnet.

### Keys and signer policy

The operator owns the evaluator signer: key generation, custody (KMS/HSM vs local
file), rotation, revocation, and which address is authorized as the ERC-8183
evaluator on the target contract. This package never generates, stores, or manages
private keys.

### Gas

Gas funding, gas limits, fee strategy, nonce management, transaction simulation,
and retry policy are operator-owned. The adapter does not manage gas or nonces.

### Chain choice

Which chain (testnet) and which ERC-8183 contract implementation are in scope is
an operator decision. **There is no canonical, blessed, or default DeliveryProof
ERC-8183 contract address** — the address and chain id are operator configuration.

### RPC credentials

The RPC endpoint URL and any associated credentials/keys are operator-supplied and
operator-secured. Whether RPC credentials may appear in CI or in a local agent
environment is a separate human decision (see the core register).

### Custody

The adapter takes no custody. The ERC-8183 contract holds the escrow. Whether a
given deployment's funding/escrow/contract arrangement is custodial or
non-custodial — and any resulting MSB/MTL/legal obligations — is a question for the
operator and counsel, per the core register.

### Finality

On-chain finality, reorg handling, and what "settled" means for a given chain are
operator policy. The adapter submits an evaluator decision and reports a `txRef`;
it makes **no exactly-once and no finality guarantee**. How finality, partial
confirmation, reorg reversal, and replay are detected and reported to operators is
operator-owned.

## The `ALLOW_LIVE_TX` Gate

Live (testnet) submission through the `viem` client is gated behind an explicit
operator opt-in (`ALLOW_LIVE_TX`, see
[docs/OPERATOR-RUNBOOK.md](./docs/OPERATOR-RUNBOOK.md)). Absent that opt-in and the
required configuration (`RPC_URL`, `PRIVATE_KEY`, `JOB_CONTRACT`, `JOB_ID`,
`CHAIN_ID`), the live testnet example (`examples/testnet-evaluate.mjs`) **refuses
and exits non-zero** — it does NOT fall back to the in-memory fake; use
`examples/conformance-demo.mjs` for the in-memory no-chain path. Flipping that gate
is itself a human action and presumes all of the decisions above have been made.

## Not In This Register

The pure projection of a `DeliveryReceipt` onto an evaluator `complete`/`reject`
call shape, the Hold⇄Job status mapping, the in-memory reference client, and the
conformance run are in the package. Live transaction submission, wallet control,
RPC credentials, key custody, gas, chain choice, and finality remain in this
register and the core register.

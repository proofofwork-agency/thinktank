# Security Policy

`@deliveryproof/rail-erc8183-base` is a companion `RailAdapter` for the core
`deliveryproof` library. It is the ERC-8183 ("Agentic Commerce") **evaluator**:
given a signed `DeliveryReceipt`, it drives an already-funded, already-Submitted
on-chain job to `complete` (release escrow to the provider) or `reject` (refund
the client). It is **TESTNET / LOCAL ONLY**.

This document describes how this adapter widens the security scope over the core
package — and how narrowly. Read the core policy first:
[`../../concept/SECURITY.md`](../../concept/SECURITY.md).

## The Scope Widening Over Core

The core `deliveryproof` package explicitly excludes "wallet signing, provider/RPC
helpers, contract-call helpers, private-key handling, or on-chain submission."

This adapter adds **exactly one** capability beyond core, and nothing else:

> **testnet / local on-chain submission of an ERC-8183 evaluator decision
> (`complete` / `reject`) through an injected client seam.**

Everything else in the core security boundary still holds here unchanged:

- signed `DeliveryReceipt` integrity and verification (via `verifyReceipt`);
- the settlement invariant that failed verdicts refund rather than capture;
- the verdict-consistency gate (a receipt whose `decision` contradicts its
  `verdict.ok` is rejected before any action);
- the 7-field receipt⇄hold binding before any terminal action;
- idempotent terminalization and conflict rejection.

## What This Adapter Does NOT Add

These remain explicit non-goals, identical to core:

- **No custody.** The adapter never funds, escrows, deposits, submits, or holds a
  job. The ERC-8183 contract owns the escrow and the money. The adapter only
  attaches to a job another party already funded and Submitted.
- **No mainnet and no real funds.** Testnet / local only. No production money
  movement.
- **No autonomous live transactions.** The live `viem` client is gated behind
  explicit operator configuration plus an `ALLOW_LIVE_TX` opt-in.
- **No canonical / blessed contract.** No hardcoded contract address, chain id,
  or RPC URL, and none implied. Address, chain, RPC, and signer are operator
  configuration.
- **No exactly-once or finality guarantee.** The adapter makes no claim about
  on-chain finality, reorg safety, or exactly-once submission. Gas, nonce, retry,
  reorg, and finality policy belong to the operator and the chain.
- **No key custody.** The adapter does not generate, store, rotate, or manage
  private keys. The operator owns the evaluator signer and the RPC credentials.
- No legal, tax, MSB, MTL, KYC, AML, or compliance certification.

## The Client Seam Is The Trust Boundary

All chain interaction is funneled through one injected `Erc8183Client` interface
(`getJob` / `complete` / `reject`). The adapter:

- validates the injected client shape (`assertErc8183Client`) and fails closed if
  it is malformed (`Erc8183ClientError`);
- treats an absent job as an operator/config error (`Erc8183JobNotFoundError`),
  never papering over it;
- refuses to act on a job that is not `Submitted` (`Erc8183NotSettleableError`);
- reconciles real on-chain state via `getJob` before any submission, so a stale
  local view cannot double-submit.

The injected client (especially the `viem` one) is where wallet, RPC credentials,
gas, and submission live. Securing those — key custody, signer authorization, RPC
credential handling, gas limits, simulation, retry, and reorg response — is the
operator's responsibility, not this package's.

## High-Priority Issue Classes

Treat these as high priority, in addition to the core classes:

- any path that submits `complete`/`reject` while `verdict.ok !== true`;
- any path that submits a terminal action without the full 7-field receipt⇄hold
  binding;
- a stale-state path that double-submits because it did not reconcile via
  `getJob`;
- a `viem` (or other live) client that submits a transaction without the operator
  opt-in;
- any hardcoded or implied canonical contract address, chain id, or RPC URL;
- leakage of private keys or RPC credentials into logs, errors, or audit records.

## Reporting Vulnerabilities

Report suspected vulnerabilities privately to the maintainer, as described in the
core policy. Useful reports include the affected commit hash, a minimal
reproduction, expected versus observed behavior, and whether the issue can cause a
false release, a forged-receipt submission, a verifier bypass, a stale-state
double-submit, or credential leakage.

## Operator Responsibilities

Before any live (testnet) transaction, the operator must decide and own: the
target contract and network, the signer custody model, the RPC provider and
credential policy, whether CI may use testnet RPC, and the gas/retry/simulation/
reorg policy. These are human-decision items, enumerated in
[ESCALATIONS.md](./ESCALATIONS.md) and the core
[`../../concept/docs/ESCALATIONS.md`](../../concept/docs/ESCALATIONS.md).

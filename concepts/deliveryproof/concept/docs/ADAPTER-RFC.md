# Adapter RFC: Companion Rails, ERC-8183 First

Status: **proposal only**. This document does not approve live chain calls,
wallet custody, RPC credentials, payment-provider accounts, or production money
movement. Those remain human-decision items in
[ESCALATIONS.md](./ESCALATIONS.md).

## Decision

DeliveryProof should build real rail integrations as **companion packages**, not
inside the core `deliveryproof` package.

The first reference companion should be:

```text
@deliveryproof/rail-erc8183-base
```

The priority order is:

1. `@deliveryproof/rail-erc8183-base` — first reference adapter.
2. `@deliveryproof/rail-x402-escrow` — named x402 escrow/voucher extension, not
   generic base-x402 support.
3. Stripe enterprise adapter.
4. Raw EVM escrow adapter.
5. Raw Solana program adapter.

## Why Companion Packages

The core library is intentionally small: protocol objects, canonicalization,
verifiers, routing, signed receipts, reference rails, conformance suites, and
projection helpers. It does not own live custody, provider credentials, wallet
control, RPC submission, gas policy, compliance, or external-rail finality.

Companion packages preserve that boundary while proving that DeliveryProof can
drive real settlement:

- the core stays dependency-light and rail-neutral;
- each adapter can pin heavy provider, wallet, chain, KMS, database, and audit
  dependencies independently;
- operators can review rail-specific custody, compliance, nonce, gas, reorg, and
  failure behavior separately;
- companion CI can run the core conformance suites against the real adapter.

## Why ERC-8183 First

The first adapter should optimize for semantic fidelity and honesty, not maximum
network reach.

ERC-8183 already defines the shape DeliveryProof needs: a job with escrowed
budget, provider submission, a pluggable evaluator, and evaluator-controlled
`complete(jobId, reason?)` or `reject(jobId, reason?)`. DeliveryProof already
ships the pure projection:

```js
toErc8183EvaluatorResult(receipt, { jobId })
```

The companion adapter therefore adds only the boundary the core intentionally
omits:

- configured Base RPC/provider access;
- evaluator wallet/signing policy;
- contract ABI and address configuration;
- transaction simulation/submission;
- gas, nonce, retry, reorg, and finality handling;
- production audit records for submitted transactions.

That makes ERC-8183 the cleanest reference for "DeliveryProof as the deep
evaluator." `receipt.decision === 'release'` maps to `complete`; `refund` maps to
`reject`; the signed receipt hash can be used as the evaluator reason or
attestation reference. The chain contract, not DeliveryProof, owns final escrow
finality.

## Why x402 Second

x402 has stronger reach and a better HTTP/MCP ecosystem fit, but generic x402 is
not itself a delivery-gated escrow rail. Base x402 is a payment/access protocol:
it verifies payment before serving a resource, and the simple payment flow is not
the same as a post-delivery release/refund hold.

DeliveryProof should therefore not claim generic "x402 support" for a
`RailAdapter`. The honest second adapter is a named integration with an
x402-compatible escrow, voucher, or batch-settlement extension where redemption
or capture can be gated on the DeliveryProof verdict:

```text
@deliveryproof/rail-x402-escrow
```

Its claim should be narrow: it replaces shallow escrow gates such as HTTP 2xx,
JSON shape, or expected hash with DeliveryProof's objective content predicates.
The adapter must qualify its custody/finality story according to the exact
facilitator, escrow contract, chain, and voucher mechanism it targets.

## Why Stripe Third

Stripe is production-relevant for enterprise and fiat workflows, but it is less
natural as the first proof of DeliveryProof's core thesis. Stripe integrations
usually imply merchant-of-record, KYC, dispute, card, bank, platform, and
provider-account concerns. Those are useful later, but they make a first
reference adapter more about payment-processor operations than about the
delivery-gated verifier boundary.

## Why Raw Chains Later

Raw EVM and raw Solana adapters are settlement venues, not agent-commerce
protocols. Building directly against them would require DeliveryProof to design
or select custom escrow semantics, program/contract interfaces, dispute behavior,
and finality policy. That is more work and a weaker standards story than using
ERC-8183 or a named x402 escrow/voucher layer.

Base ranks above raw Ethereum L1 for a first EVM adapter because ERC-8183 is
already live in that ecosystem and lower-cost execution is a better fit for
agentic commerce. Raw Solana can be valuable later, especially under an x402
settlement path, but a DeliveryProof-native Solana program would be a custom
escrow project rather than a minimal reference adapter.

## Companion Adapter Contract

Every companion rail should implement the core `RailAdapter` behavior while
making its external finality model explicit.

Minimum requirements:

- verify DeliveryProof receipts with the configured settlement public key or
  keyring before terminal action;
- reject receipts whose `decision` contradicts `verdict.ok`;
- bind terminal action to the exact hold/job, amount, currency, rail id, contract
  id, and contract hash;
- preserve idempotency for repeated terminal submission of the same receipt;
- reject conflicting terminal attempts;
- expose enough status for audit bundles and dispute review;
- run `runRailConformance()` in companion CI;
- document which external system actually owns finality.

For ERC-8183 specifically, the adapter should also:

- require a configured evaluator signer;
- require a configured ERC-8183 contract address and ABI version;
- verify that the target job is in the expected funded/submitted state before
  terminal submission when the chain API exposes that state;
- map `release` to `complete(jobId, reason)` and `refund` to
  `reject(jobId, reason)`;
- include a receipt commitment in `reason`;
- record transaction hash, chain id, contract address, job id, action, receipt
  hash, and finality status.

## Non-Goals

This RFC does not propose:

- adding wallet, RPC, provider, private-key, or chain-call code to core;
- claiming DeliveryProof becomes trustless or formally fair;
- claiming generic x402 escrow support without naming the exact extension;
- taking custody of funds;
- making legal, tax, KYC, AML, chargeback, or money-transmitter claims;
- deploying contracts or submitting transactions from this repo.

## Implementation Gate

Before implementing `@deliveryproof/rail-erc8183-base`, a human must approve:

- target contract implementation and network;
- signer custody model;
- RPC provider and credential policy;
- whether CI may use testnet RPC;
- gas, retry, simulation, and reorg policy;
- audit and incident-response requirements;
- whether the adapter is testnet-only, demo-only, or production-intended.

Until those decisions are made, this RFC is a design recommendation, not an
implementation task.

## Sources

- DeliveryProof whitepaper, §6 Interop and §8 Limitations:
  [WHITEPAPER.md](./WHITEPAPER.md)
- Production integration companion-package boundary:
  [PRODUCTION-INTEGRATION.md](./PRODUCTION-INTEGRATION.md)
- Human approval gate for live chain work:
  [ESCALATIONS.md](./ESCALATIONS.md)
- ERC-8183, "Agentic Commerce":
  <https://eips.ethereum.org/EIPS/eip-8183>
- x402 batch settlement:
  <https://www.x402.org/writing/x402-batch-settlement>
- x402 documentation:
  <https://docs.x402.org/>

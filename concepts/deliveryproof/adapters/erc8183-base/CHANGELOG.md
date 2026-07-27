# Changelog

All notable local changes to `@deliveryproof/rail-erc8183-base` are summarized
here. The package has not been publicly published; commit hashes identify the
local development slices.

## v0.2.0 — Fail closed by default (local, unpublished)

Tracks `deliveryproof@0.10`. **Breaking.**

- `createErc8183Rail` now REQUIRES `settlementPublicKey` and verifies the receipt
  signature before any `complete`/`reject`. This rail moves real escrow, so an
  unauthenticated receipt here is worse than on the reference rails. Opt out with
  `allowUnsignedReceipts: true` (local fixtures only); `requireSignature` is a
  retained no-op alias.
- Options are read from a null-prototype own-property copy, so a polluted
  `Object.prototype` cannot inject `allowUnsignedReceipts` or an attacker-held
  `settlementPublicKey`.

## v0.1.0 — First reference adapter (local, unpublished)

The first real DeliveryProof `RailAdapter`: DeliveryProof as the **ERC-8183
("Agentic Commerce") evaluator**. **TESTNET / LOCAL ONLY** — no mainnet, no real
funds, no custody, no finality guarantee.

- Added `createErc8183Rail(opts)`, a `RailAdapter` that maps the DeliveryProof
  Hold lifecycle onto an already-funded, already-Submitted ERC-8183 job:
  `authorize` **attaches** to a `Submitted` job (read `getJob`, never funds or
  submits), `capture` → `complete(jobId, reason)`, `refund` →
  `reject(jobId, reason)`, `status` → `getJob` mapped to a Hold state.
- Re-enforced the core money-safety invariants at the ERC-8183 boundary: the
  7-field receipt⇄hold binding, the verdict-consistency gate (release iff
  `verdict.ok === true`, refund iff `verdict.ok === false`), optional
  `settlementPublicKey` / `requireSignature` signature verification, and
  idempotency by reconciling live job state via `getJob` before any submission.
- Added the injected `Erc8183Client` seam (`getJob` / `complete` / `reject`) as
  the single trust boundary for all chain interaction, with `assertErc8183Client`
  shape validation and the human-readable `ERC8183_JOB_ABI`.
- Added a typed error hierarchy (`Erc8183RailError`, `Erc8183NotSettleableError`,
  `Erc8183JobNotFoundError`, `Erc8183ClientError`) so callers can distinguish
  not-settleable, not-found, and bad-client conditions without string-matching.
- Added the total Job-status ⇄ Hold-state mapping (`JobStatus`,
  `mapJobStatusToHoldState`, `isSettleable`, `isTerminal`); `Expired` maps to
  `refunded` (same money outcome as a rejection), and unknown statuses throw
  rather than silently default.
- Added `createInMemoryErc8183Client()`, an in-process reference client that
  auto-creates a `Submitted`, pre-funded `5 USDC` job for unknown ids (so the core
  `runRailConformance()` fixtures pass), enforces evaluator-only + Submitted-only
  semantics, and **throws on a second terminalization** so rail idempotency must
  come from reconcile-via-`getJob`.
- Added `createViemErc8183Client()`, a testnet/local on-chain client over `viem`'s
  `readContract`/`writeContract`. `viem` is an **optional** dependency, lazily
  imported only inside this factory, so the package imports cleanly in plain Node
  without it.
- Certified the adapter against the core's exported `runRailConformance()` suite
  via `examples/conformance-demo.mjs`, including a shared-client restart path.
- Documented the narrow scope widening over core (testnet/local on-chain
  submission only) in [SECURITY.md](./SECURITY.md), the human/operator decisions in
  [ESCALATIONS.md](./ESCALATIONS.md), the Hold⇄Job mapping and reorg stance in
  [docs/STATE-MAPPING.md](./docs/STATE-MAPPING.md), and the testnet run plus
  human-decision checklist in [docs/OPERATOR-RUNBOOK.md](./docs/OPERATOR-RUNBOOK.md).
- Honesty posture: no hardcoded or implied canonical ERC-8183 contract address;
  address, chain id, RPC URL, signer, gas, and finality are operator
  configuration. The adapter is the evaluator, not a custodian, and makes no
  exactly-once or finality guarantee.

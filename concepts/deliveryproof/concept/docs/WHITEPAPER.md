# DeliveryProof: Verified-Delivery-Gated Settlement for AI-Agent Commerce

*A rail-neutral protocol and reference implementation that conditions payment on
**objective proof of delivery**, not merely proof of authorization.*

**Status:** v0.9.1 local hardening build for the OSS library (JCS-correct canonicalization + fail-closed-on-contradiction rails/interop) · Node v22+ · Apache-2.0
**Author:** Danillo Felix.
**Build collaborators:** Claude (Anthropic) & Codex (OpenAI), collaborating via ContextRelay, 2026-05-30.

---

## Abstract

Autonomous agents are beginning to pay one another for digital work, and a layer
of payment-authorization protocols (Coinbase x402, Google AP2, Stripe MPP,
Visa/Mastercard agent rails) now answers the question *"is this agent allowed to
pay?"* well. None of them answers the complementary question that actually protects
the buyer: *"did the counterparty deliver what was promised?"* Shipping escrow
systems that claim "verified delivery" (e.g. PayCrow, Virtuals ACP, x402 escrow
extensions, ERC-8183/ERC-8004) gate release on **shallow** checks — HTTP 2xx, JSON
shape, an opaque LLM "evaluator," or an explicitly *undefined* evaluator slot. We
present **DeliveryProof**, a rail-neutral protocol that gates settlement on a
**deep, objective delivery predicate** and emits a signed, independently verifiable
**DeliveryReceipt**. Conditioning payment on the validity of a delivered artifact is
not itself new — it has on-chain academic precedent (FairSwap, OptiSwap; §7) and a
contemporaneous agent-commerce proposal (TessPay). DeliveryProof's contribution is to
package that idea as a deterministic, rail-neutral *content-predicate* and
signed-receipt layer for agent-commerce rails, concretely three things: (1) **verifier
depth** — a deterministic, recomputable correctness check,
demonstrated on tabular datasets where a schema-valid but corrupt deliverable is
*paid* by a shallow checker and *refunded* by DeliveryProof on the same bytes; (2)
a **verifier router** that selects the cheapest sufficient verifier for a declared
assurance level and **refuses to silently downgrade**, recording its choice in the
signed receipt so a downgrade is tamper-evident; and (3) an **honest, tiered trust
model** that names the irreducible trust points rather than hiding them. We show
DeliveryProof composes *under* existing escrow/validation shells via thin export
adapters (ERC-8004 validation payload, ERC-8183 evaluator decision), positioning it
as the deep evaluator those standards leave undefined. The reference implementation
uses a single audited runtime dependency (`@noble/hashes`) for Ethereum
Keccak-256 helpers, otherwise relies on Node built-ins, and ships with an
executable test suite. DeliveryProof offers **no formal fairness theorem**: its
guarantee is an objective, recomputable verdict and a portable, tamper-evident
receipt, not a cryptographic fair-exchange proof (§2, §7).

> **Why this exists.** "Pay only if the counterparty delivered" is a *fair-exchange*
> problem, and strong fair exchange is provably impossible without a trusted third
> party (Pagnia–Gärtner 1999; §2). DeliveryProof does not try to remove that trusted
> party — it makes it **explicit, objective, tiered, and auditable**: the verifier and
> its signed verdict, the router that selected it, and the settlement rail. (Origin
> note: the project began as the constructive tail of a separate negative result about
> ledgerless digital money; that is history, not the theorem that governs this design.)

---

## 1. Introduction

### 1.1 The problem: "allowed to pay" ≠ "delivered"

Today's agent-payment rails authorize, authenticate, and transfer. They prove
*permission to pay*. They do not — and by design do not — prove that the seller's
deliverable was correct. When a paid API returns `{"temperature": 999}` for a
weather query, or a data vendor ships a table with the right columns but corrupted
values, an authorization-only rail pays anyway. The buyer's recourse is a dispute
*after* the money moved.

### 1.2 Why escrow is not enough

The market has converged on escrow + "release on verified delivery." But the
*verifier* in those systems is shallow or undefined: HTTP-2xx-plus-JSON-schema,
an opaque LLM judge, a pluggable human/vote arbiter, or — in the ERC-8183/8004
standards — an evaluator slot the spec explicitly declines to define. Escrow is now
table stakes; **the verifier is the unsolved part.**

### 1.3 Contributions

These are contributions of *execution and positioning*, not a new primitive — the
predicate-gated fair-exchange category is precedented on-chain (§7). What this
reference implementation provides:

1. **A rail-neutral delivery-verification protocol** — `DeliveryContract` →
   `DeliveryEvidence` → signed `DeliveryReceipt` — with a hard invariant: *no code
   path pays the seller on a negative verdict* (§3, §4).
2. **Verifier depth, not escrow, as the hard part** — deterministic re-execution and
   deep tabular correctness, with a reproducible "money-shot" experiment (§5).
3. **A no-silent-downgrade verifier router** whose routing decision is signed into
   the receipt, making assurance-downgrade tamper-evident (§3.3).
4. **An explicit tiered-trust model** (Tier A objective / B attested / C subjective)
   that surfaces irreducible trust instead of marketing it away (§3.4).
5. **Thin interop adapters** projecting a DeliveryReceipt onto ERC-8004 / ERC-8183
   payload shapes, so DeliveryProof fills the deep-evaluator gap *inside* those
   shells rather than competing with them (§6).

---

## 2. Background: fair exchange requires an explicit trust point

DeliveryProof solves a *fair-exchange* problem: the buyer wants to pay only if the
seller delivered the agreed artifact, the seller wants to be paid if they did, and
neither wants to move first. This is one of the oldest problems in security, and it has
a hard floor: **strong fair exchange between two mutually distrusting parties is
impossible without a trusted third party** (Pagnia and Gärtner, 1999), a result that
sits on early fair-exchange and contract-signing foundations (Even, Goldreich, and
Lempel, 1985). Fairness is not free; some party or mechanism must be trusted to break
the symmetry.

The honest move is therefore not to pretend the trusted third party away, but to make
it **explicit, objective, tiered, and auditable.** DeliveryProof's primary trust point
is the verifier: a deterministic predicate over the delivered bytes whose verdict anyone
can recompute, signed into a receipt, with the routing choice that selected it also
signed so assurance cannot be silently weakened. The rail that captures or refunds is a
second named trust point; the predicate's author is a third (§3.5). DeliveryProof does
not claim trustlessness — it claims to convert *hidden, unbounded* trust into *named,
scoped, checkable* trust, and to gate payment on the one thing that is objectively
decidable for a machine deliverable: **did the delivered artifact satisfy a declared
predicate?**

On-chain constructions realize this same fair-exchange goal with formal guarantees:
FairSwap and OptiSwap use a smart contract as the trusted third party plus a
proof-of-misbehavior dispute game (§7). DeliveryProof is deliberately weaker and
narrower — off-chain, rail-neutral, no dispute game, and **no formal fairness theorem.**
Its trade is portability and an objective, recomputable verdict, not a cryptographic
fairness proof.

*Provenance.* The project began as the constructive tail of a separate negative result
about portable, ledgerless digital money — you cannot have trustless, issuerless, and
remotely-verifiable value at once, because objective global scarcity is itself global
shared state. That inquiry is why the author started *naming* trust instead of trying to
abolish it, but it is an origin story, not the theorem that governs pay-iff-delivered.
The governing result is the fair-exchange impossibility above.

---

## 3. The protocol

### 3.1 Objects

- **DeliveryContract** — what is bought, the **delivery predicate** to satisfy,
  price, SLA, refund rule, target rail, and a nonce; buyer/seller identified by the
  `keyId` of their public keys. Contracts carry a `protocolVersion` and are
  canonicalized with the RFC-8785-style JCS encoder used throughout the protocol.
- **DeliveryEvidence** — the deliverable: `output`, its `outputHash`, the bound
  `nonce`, and optional `logs` / `attestations`.
- **DeliveryReceipt** — the signed outcome: `contractHash`, rail/hold/amount/currency,
  the `verdict`, the optional `routeDecision`, an `evidenceHash`, the `decision`
  (`release` | `refund`), lifecycle/nonce-registry evidence, the settlement signer's
  `keyId`, and an Ed25519 signature anyone can check with `verifyReceipt`.

Full field tables and the settlement state machine are in [SPEC.md](../SPEC.md).

### 3.2 Settlement (`settle`)

Optionally reserve the settlement nonce → authorize a hold on the rail → produce
evidence before the SLA deadline → run the chosen `Verifier` to get a `Verdict` →
derive the decision (`verdict.ok ? 'release' : 'refund'`) → **sign** the
`DeliveryReceipt` → `capture` (release) or `refund` on the rail. If evidence
production or verification throws *after* funds are held, the exception becomes an
`ok:false` verdict and the hold is refunded — a crashed seller/verifier never strands
escrow. If the nonce registry is enabled, the nonce is burned on every attempted
settlement, including refunds; retrying requires a fresh nonce.

**Invariant.** There is **no path** that captures (pays the seller) when
`verdict.ok === false`. The verdict gates settlement; `engine.test.mjs` asserts it.

### 3.3 Verifier router (no silent downgrade)

`routeVerifier(contract, { policy })` selects the **cheapest verifier that still
meets the declared assurance** for the deliverable type. If nothing qualifies it
**throws** rather than quietly using a weaker check; a weaker verifier is chosen only
when `fallbackAllowed: true` is set explicitly, and that fallback is flagged. The
`routeDecision` (selected verifier, candidates, rejections, and a `policyHash`) is
**signed into the receipt**, so downgrading a dataset transaction to a shape check is
tamper-evident.

### 3.4 The tiered-trust model

| Tier | Meaning | Trust required | Examples (this reference build) |
|------|---------|----------------|---------------------|
| **A** | **Objective** — independently recomputable or cryptographically self-evident. | None beyond the predicate (transcript also binds the contract's authorized signer). | `builtin-replay` (resource-bounded replay), `dataset` (deep tabular correctness), `api-response` (paid API/MCP response correctness), `document` (structured Markdown correctness), `hash` (exact bytes), `schema` (shape — *shallow foil*), `transcript` (authorized nonce-bound signature), `compose` (AND/OR/threshold over child verifiers) |
| **B** | **Attested** — correctness rides on an external proof system. | Trust that proof system / hardware / source. | `signed-oracle` (runnable Ed25519 oracle/provenance attestation); *(interfaces only)* TEE attestation, zkTLS transcript, ZK proof |
| **C** | **Subjective** — a model/rubric judges quality. | Trust the judge; advisory only. | *(production)* LLM-as-judge, rubric grader |

Most shipped verifiers are **Tier A**. Four core verifier families are *deep*:
`builtin-replay` re-executes the work in a bounded worker; `dataset` proves objective tabular correctness (row count; required/nullable;
per-field type/domain/range/regex/null-rate; unique keys; optional dataset hash and
byte-tagged Merkle root; a **verifier-seeded** sample hash plus emitted Merkle proofs
for sampled rows; aggregate invariants including `sum`/`min`/`max`/`avg`/`count`/`distinct`); and `api-response` proves a **paid API / MCP tool-call
response** actually answers the request — over a captured `{contractId, nonce,
request, response}` transcript (bound to the contract + nonce so a response from a
different contract cannot be replayed) it checks request binding, status, content
type, body shape, JSON-path field assertions (`equals`/`in`/`min`/`max`/`matches`/
`type`/`fromRequest`), and freshness; `document` proves objective Markdown
structure/checksums (frontmatter, headings, terms, links, tables, code blocks)
with bounded document/line preflight and without grading prose quality. `compose` lets a contract require AND/OR/
threshold combinations of verifiers and signs the child trace into the final receipt.
`schema` is retained as the **shallow foil** so the depth gap is explicit and
testable. Tier B is represented by a real `signed-oracle` verifier, plus explicit
interface descriptors for TEE, zkTLS, and ZK proof systems. Tier C is documented as
an extension point, not built here.

*Honest scope of `builtin-replay`:* it bounds resource consumption of deterministic
built-in replay (CWE-400) with `worker_threads`, wall-clock timeouts, resource
limits, and preflight size/depth checks. It does **not** execute arbitrary seller
JavaScript and is **not** an OS jail for hostile code; Node worker limits primarily
bound the V8 isolate and global process OOM can still abort the process.

*Honest scope of `api-response`:* it proves the response satisfies the declared
predicate over the captured transcript bytes — not that the external-world fact is
true (that the real weather was 21°). Establishing that the bytes genuinely came
from the source is a separate provenance trust point (zkTLS/TLSNotary, Tier B) that
*composes with* this verifier.

### 3.5 Honest framing — what DeliveryProof does *not* do

Four trust points are irreducible and are **named, not hidden**: (1) *predicate
authorship* — a perfect proof against a wrong predicate is still wrong; (2)
*external-truth sources* — provenance proofs say "the source said X," not "X is
true"; (3) *subjective quality* — not objectively verifiable in general; (4)
*settlement-rail policy* — the rail defines what capture/refund actually mean.
DeliveryProof scopes and tiers these; it does not pretend to remove them.

---

## 4. Implementation

Requires **Node v22+**. The package has one audited runtime dependency,
`@noble/hashes`, for Ethereum Keccak-256 helpers; otherwise it uses Node
built-ins. Use `npm ci` to install the exact lockfile. There is no build step.

```bash
node examples/demo-compute.mjs   # happy path, refund, transcript-tamper, compute money-shot
node examples/demo-dataset.mjs   # dataset money-shot: shallow schema PAYS, deep dataset REFUNDS
node examples/demo-api.mjs       # API money-shot: 200+valid-JSON wrong-city PAYS shallow, REFUNDS deep
node examples/demo-document.mjs  # document money-shot: valid Markdown string PAYS shallow, REFUNDS deep
node examples/demo-merkle-partial.mjs # partial Merkle sample: release valid rows, refund swaps/cherry-picks
node examples/demo-interop.mjs   # one signed receipt -> ERC-8004 + ERC-8183 payloads
node examples/demo-keyring.mjs   # receipt verification across settlement-key rotation
node examples/demo-audit-bundle.mjs # inspect receipt-bound contract/evidence/rail hashes
node examples/demo-keccak-interop.mjs # sha256 default vs opt-in keccak256 + ABI projection
node examples/demo-production-seams.mjs # rail + replay-store conformance seams
node --test                      # full test suite
```

```
src/
  protocol/  canonical.mjs (JCS + hashes) · schema.mjs (runtime validation) · crypto.mjs · types.mjs
  protocol/  keccak.mjs (Ethereum Keccak-256 via @noble/hashes)
  protocol/  merkle.mjs (byte-tagged dataset Merkle roots + inclusion proofs)
             merkle-sample.mjs (bounded partial-sample index selection)
             signer.mjs (signer/keyring interface descriptors)
  runtime.mjs · errors.mjs · operability/index.mjs · operability/audit-bundle.mjs
  verifiers/ schema · hash · builtin-replay · transcript · dataset · api-response · document · compose · index
  verifiers/ tier-b/interfaces.mjs · tier-b/signed-oracle.mjs
  router/    policy.mjs  — routeVerifier(): cheapest sufficient verifier, no silent downgrade
  rails/     escrow-mock.mjs · durable-rail.mjs
  engine/    deliveryproof.mjs — settle(), verifyReceipt()
  engine/    nonce-registry.mjs · milestones.mjs
  testing/   rail-conformance.mjs · replay-store-conformance.mjs
  mcp/       paidToolWithDeliveryProof.mjs — paid MCP tool wrapper (+ makeEvidence hook)
  interop/   erc8004.mjs · erc8183.mjs — thin receipt -> standard-payload export
examples/    demo-compute.mjs · demo-dataset.mjs · demo-api.mjs · demo-document.mjs · demo-merkle-partial.mjs · demo-interop.mjs · demo-keyring.mjs · demo-audit-bundle.mjs · demo-keccak-interop.mjs · demo-production-seams.mjs
test/        protocol · verifiers · engine · router · interop · mcp  (node:test)
```

### Library hardening boundary (v0.7-v0.8)

v0.7 is a production-hardening build for the **open-source objective-verification
library**: protocol objects, canonicalization, verifiers, routing, settlement
orchestration, interop helpers, and reference rails. It is not a hosted SaaS,
custody service, payment processor, marketplace, legal/tax product, or guarantee
that a real rail will move money.

The library hardening scorecard is tracked in
[PRODUCTION-READINESS.md](../PRODUCTION-READINESS.md). The API surface is documented
in [docs/API.md](./API.md), stability labels in
[docs/API-STABILITY.md](./API-STABILITY.md), security policy in
[SECURITY.md](../SECURITY.md), threat model in
[docs/THREAT-MODEL.md](./THREAT-MODEL.md), and supply-chain policy in
[docs/SUPPLY-CHAIN.md](./SUPPLY-CHAIN.md). The v0.9 integration notes are in
[docs/PRODUCTION-INTEGRATION.md](./PRODUCTION-INTEGRATION.md), the full vs.
partial Merkle decision table is in
[docs/MERKLE-PARTIAL-VS-FULL.md](./MERKLE-PARTIAL-VS-FULL.md), and human
decision gates are tracked in [docs/ESCALATIONS.md](./ESCALATIONS.md).

A real deployment still needs:

- a production **non-custodial** rail adapter;
- production key management and operator security review;
- an attested Tier-B verifier when the use case depends on external-world
  provenance;
- legal, tax, and compliance review by qualified professionals.

The in-repo `createMockEscrowRail()` is only a reference state machine for tests and
demos. `createDurableEscrowRail()` demonstrates local WAL/idempotency mechanics,
but it is still not production money movement. Both reference rails reject a receipt
whose `decision` contradicts its `verdict.ok` before any terminalization, and since
v0.10 require `settlementPublicKey` at construction so a valid settlement signature is
verified on every capture/refund; a real rail adapter must still enforce its own authorization,
idempotency, custody, and compliance rules. Tier-B interface descriptors are not implemented proof systems;
`signed-oracle` proves only that an allowed attester signed a bound statement.

The adapter and verifier **interfaces** are the stable surface; the implementations
behind them are swappable. Reference choices vs. a production deployment:
`node:crypto` plus operator key management; mock escrow/durable local WAL → real
non-custodial `RailAdapter`s (x402 / Stripe MPP / AP2); runnable signed-oracle +
Tier-B descriptors → real ZK/TEE/zkTLS verifiers; hand-rolled MCP wrapper → real
MCP SDK middleware.

Additional v0.4-v0.7 hardening:

- RFC-8785-style canonicalization, `protocolVersion`, and runtime schema validation
  on wire objects.
- SLA/deadline enforcement, lifecycle trace signing, and nonce replay prevention.
- Durable local rail with idempotency keys and write-ahead recovery. This proves
  exactly-once **local terminalization**, not universal exactly-once money movement.
- Milestone settlement composition: partial delivery/refund is modeled as multiple
  independently settled child contracts plus a signed aggregate, not a fractional
  mutation of a single hold.
- Schedule-bound milestone aggregate verification: the verifier can recompute child
  contracts from the schedule and reject truncation, reordering, or substituted child
  receipts.
- Dataset regex constraints and document parsing are bounded as pragmatic
  verifier-side CWE-400 guardrails. Dataset also supports `avg` and `count`
  aggregate invariants.
- Dataset Merkle commitments use a byte-tagged construction:
  `leaf = SHA256(0x00 || canonicalize(row))`,
  `node = SHA256(0x01 || leftHashBytes || rightHashBytes)`, and
  `empty = SHA256(0x02)`. Leaves are sorted by `canonicalize(row)`, odd nodes
  carry up unchanged, and passing dataset verdicts can emit
  `{ root, leaf, index, leafCount, siblings }` inclusion proofs for
  verifier-seeded sampled rows.
- CSV dataset input supports RFC-4180 quoted fields, embedded commas/newlines, and
  escaped `""` quotes with a single-pass bounded parser that fails closed on
  malformed quoting.
- v0.7 adds prototype-pollution guards, injectable clocks with default `Date.now`
  behavior, bounded JSON-dataset defaults, bounded API-response predicate surfaces,
  a package root API, optional best-effort audit hooks, local rail health/flush/close
  helpers, and library-hardening documentation. Audit hooks are not signed into
  receipts and never affect settlement decisions.

Additional v0.9 integration seams:

- Rail conformance and replay-store conformance suites let companion packages test
  real rail adapters and durable replay stores against the reference behavior.
- `createNonceRegistry({ store })` delegates replay persistence while preserving
  DeliveryProof nonce-key ownership; `createWalReplayStore({ logPath, fsync })`
  remains the local WAL reference store.
- `verifyReceipt` accepts a PEM string as before and now also supports
  `{ keys }` and `{ keyring }` for settlement-authority rotation windows. The
  signing path in `settle()` is unchanged.
- `validateDeliveryProofConfig(config, { profile: 'production' })` adds a
  production preflight: missing nonce registry is a hard error, while no audit
  sink, tmpfs-like WAL paths, and undeclared rail receipt-signature verification
  are warnings.
- `buildAuditBundle()` collates existing receipt, contract, evidence, and optional
  rail-status hashes for dispute inspection. It is not a new proof and does not
  alter settlement.
- `hashAlg: 'keccak256'` interop projection mode emits real Ethereum Keccak-256
  digest words and ABI-shaped argument bytes for ERC-8004/8183 adapters. SHA-256
  remains the default for backward compatibility.

Additional v0.9.1 hardening (a dual independent code review — Claude + Codex — confirmed
the central `settle()` "no capture when `verdict.ok !== true`" invariant holds, and
closed several exported, money-moving surfaces that failed *open* by default):

- Canonicalization now emits RFC 8785 / JCS text directly from the code-unit-sorted key
  list instead of round-tripping through a JS object, which had silently reordered
  integer-like keys (`{"10":1,"2":2}`) and broken cross-implementation
  hash/signature/Merkle reproducibility. The `CANONICALIZATION = 'RFC8785-JCS'` claim is
  now actually true. String-keyed records and arrays are byte-identical to before, so the
  wire profile stays `deliveryproof/0.4-jcs1`, and only objects containing integer-like
  keys change bytes — named-field records like contracts and receipts are unaffected.
- Reference rails (`escrow-mock`, `durable-rail`) re-enforce the money-safety invariant at
  the money layer, not only inside `settle()`: a receipt whose `decision` disagrees with
  `verdict.ok` is rejected before any terminalization, and (since v0.10) a settlement key is required so signature verification
  makes a valid settlement signature mandatory. The consistency gate closes the
  *contradictory*-receipt hole; only signature verification closes the *forged-but-
  consistent unsigned* receipt hole.
- Interop projection (`erc8004`, `erc8183`) refuses to project an internally contradictory
  receipt into a chain-facing `complete` / `release` / `100` result. This is a consistency
  gate, not authentication: a caller posting on-chain should still `verifyReceipt()` against
  the settlement key first.
- The nonce-registry WAL replay validates record fields and rejects a lone or forged `mark`
  (mark-before-reserve or fingerprint mismatch) that could otherwise synthesize replay
  state after restart.
- The standalone `schema` and `api-response` verifiers reject non-finite (`Infinity` /
  `NaN`) numbers at the I-JSON boundary, and contract/receipt amounts must be positive and
  finite.

A `keyId` widening (DER-based, 128-bit) is intentionally deferred: the current `keyId`
is internally consistent, and changing its derivation would change the
`signerKeyId`/`keyId` fields embedded in signed receipts (and therefore their canonical
bytes and signatures) for no security gain today. Mandatory rail/interop signature
verification by default was the other tracked follow-up; **v0.10 ships it**. Rails now
require a settlement key at construction and verify every terminalization, after two
independent review passes each reproduced a working forgery against the previous
opt-in default.

---

## 5. Experiment: the money-shot

**Claim under test.** A deliverable can be *structurally valid yet objectively
wrong*; a shallow verifier pays it, a deep verifier refuses — on identical bytes.

**Compute (`demo-compute.mjs`).** A seller is paid to sort `[5,3,9,1]` and returns
`[9,5,3,1]` — a valid integer array, wrong order. The `schema` verifier (shape only)
→ **RELEASE**; the `builtin-replay` verifier (re-executes the sort, compares) → **REFUND**.

**Dataset (`demo-dataset.mjs`), routed.** A buyer purchases a 1,000-row table. The
seller ships correct columns/types/row-count but a **duplicated key** (and corrupted
revenue). Under a low-assurance policy the **router selects `schema`** → RELEASE
(this is what a shallow rail pays). Under a high-assurance policy the router selects
`dataset`, which reports a structured diff — `unique key [id] duplicate at row 37
(first seen at row 2)` — → **REFUND**. The receipt commits the `routeDecision`, so
the choice of depth is tamper-evident.

**API/MCP response (`demo-api.mjs`), routed.** A paid API returns HTTP 200 and
schema-valid JSON, but answers the wrong city (`London` for an Amsterdam request).
The shallow `schema` verifier → RELEASE; the router-selected `api-response` verifier
checks the bound request/response transcript, returns a structured diff
`city: expected Amsterdam, actual London`, and → **REFUND**.

**Document (`demo-document.mjs`), routed.** A buyer purchases a structured Markdown
delivery report. The seller ships a valid string but omits a required `Checksums`
section. The shallow `schema` verifier → RELEASE; the router-selected `document`
verifier checks frontmatter, headings, terms, links, tables, code-block languages,
and section checksums, then returns a structured diff and → **REFUND**. This is
objective structure only, not semantic grading.

**Partial Merkle sample (`demo-merkle-partial.mjs`), routed.** A buyer commits to
a dataset Merkle root and asks the seller for only the verifier-selected rows plus
Merkle proofs. A valid partial proof → **RELEASE** without giving the verifier the
full dataset. A leaf-swap attempt and a cherry-pick attempt both → **REFUND**.
Honest scope: this proves inclusion plus sampled-row conformance only, not
full-dataset truth.

---

## 6. Interop: the deep evaluator under existing shells

ERC-8004 (validation registry) and ERC-8183 (job + escrow + evaluator) standardize
*where a verdict is anchored* and *the escrow around it*, but treat the evaluator as
"any address that can call complete/reject" — the verification **method is
undefined**. DeliveryProof fills that slot. Thin, pure projection helpers
map one signed receipt onto both shapes:

- `toErc8004ValidationPayload(receipt)` → `{ requestHash, response: ok?100:0,
  responseURI, responseHash, tag, hashAlg }`
- `toErc8183EvaluatorResult(receipt, { jobId })` → `{ action: 'complete'|'reject',
  jobId, reason, hashAlg }`

SHA-256 remains the default projection hash for backward compatibility. Opt-in
`hashAlg: 'keccak256'` mode emits real Ethereum Keccak-256 digest words via
`@noble/hashes`, and `includeAbi: true` attaches ABI-shaped argument bytes. There
are still **no contracts, wallets, provider/RPC URLs, private keys, chain calls,
or on-chain submission helpers** here. We map the semantic shape and encode
arguments; a production adapter still owns the actual contract call boundary.

---

## 7. Related work

x402 revives HTTP 402 as an internet-native payment flow: a client requests a
resource, receives payment requirements, submits a signed payment payload, and the
server returns the resource after payment verification. Coinbase's x402
documentation frames the protocol around paid API/content access and MCP tool calls,
and its extension system now includes signed offers and receipts for verifiable
proof-of-interaction artifacts [1,2,3]. That work is complementary to DeliveryProof:
x402 answers *how a machine pays for access* and how a server signs the interaction;
DeliveryProof answers *whether the artifact delivered after access satisfies an
objective predicate*.

Google's Agent Payments Protocol (AP2) similarly focuses on authorization and
evidence for agent-performed payment transactions: checkout mandates, payment
mandates, receipts, and dispute evidence. AP2 explicitly positions itself as a
security feature within a broader commerce protocol and leaves the catalog,
checkout-update, and commerce API details outside its scope [4]. That makes AP2 a
natural upstream authorization layer for DeliveryProof rather than a substitute for
delivery verification.

Stripe/OpenAI's Agentic Commerce Protocol (ACP), Stripe's agentic-commerce products,
and Stripe/Tampo-style Machine Payments Protocol work define agent checkout and
payment-session surfaces for merchants and agents [5]. Their center of gravity is
commerce/payment orchestration. DeliveryProof deliberately avoids becoming another
payment rail: its useful role is downstream of authorization, at the point where a
receipt must prove why capture or refund was justified.

PayCrow and x402 escrow-style tools are closer because they condition release on a
verification strategy. Public MCP connector metadata for PayCrow exposes strategies
such as JSON Schema or expected hash verification for protected calls [6]. Those are
valuable primitives, but they illustrate the gap this paper targets: a schema-valid
object can still be objectively wrong, and an expected hash only works when the
buyer already knows the correct bytes. DeliveryProof keeps schema/hash as Tier-A
building blocks but adds deep predicates such as deterministic re-execution and
dataset conformance.

ERC-8004 and ERC-8183 are the most direct interop targets. ERC-8004 defines agent
identity, reputation, and validation registry surfaces; its validation registry is
generic and verifier-agnostic, recording validation results rather than prescribing
the method that produced them [7]. ERC-8183 defines an agentic-commerce job with
escrowed budget and an evaluator who may mark the job completed or rejected; the
standard defines the escrow/evaluator state machine, not a universal correctness
predicate [8]. DeliveryProof can therefore sit underneath these shells as the
off-chain evaluator: it produces the signed verdict and route decision that an
ERC-8004 validation or ERC-8183 evaluator action can reference.

TessPay is conceptually close. It proposes verify-then-pay infrastructure for
agentic commerce with escrow, task execution evidence, TLS Notary/TEE-style proofs,
and modular rail adapters [9]. A402 is also close but more channel-centric: it
proposes atomic service channels and TEE-assisted adaptor signatures so service
execution, result delivery, and payment finalization are coupled [10]. DeliveryProof
is narrower. It does not attempt to own delegation, discovery, channel protocols,
escrow contracts, or a validator economy. Its contribution is the small,
rail-neutral receipt and verifier-depth layer: `DeliveryReceipt`, signed
`routeDecision`, and executable Tier-A predicates that can be used by any of the
above systems.

The academic lineage matters because it both motivates and partly pre-empts this work.
Fair exchange of digital goods has a long theory: its impossibility without a trusted
third party (Pagnia–Gärtner 1999 [11]) rests on early contract-signing and fair-exchange
foundations (Even–Goldreich–Lempel 1985 [12]). Constructively, **FairSwap**
(Dziembowski–Eckey–Faust, CCS 2018 [13]) and **OptiSwap** (Eckey–Faust–Schlosser, 2020
[14]) realize *exactly the predicate-gated idea at DeliveryProof's core* — they condition
payment on whether a delivered digital good satisfies a buyer-specified correctness
relation — but do so *on-chain*, with a smart contract as the trusted third party and a
proof-of-misbehavior dispute game, and they carry formal fairness guarantees.
DeliveryProof is weaker and narrower by design: off-chain, rail-neutral, shipping
deterministic content predicates as a small library, signing the route decision and
verdict into a portable receipt, and projecting that receipt onto existing
escrow/validation shells. It has **no formal fairness theorem and no autonomous on-chain
enforcement** — the rail, not the protocol, provides finality. Its claim to attention is
execution and positioning (content-level deterministic predicates, the runnable
same-bytes demos, shipped standards-projection), not a new fairness primitive.

The resulting distinction is simple: DeliveryProof is **not a rail** and **not
escrow**. It is a portable proof record and verifier policy layer for the part these
systems tend to leave shallow, pluggable, or undefined: *what exactly counts as
delivered, and was that predicate satisfied?*

Related-work sources:

[1] x402 documentation, "Overview," Coinbase Developer Platform, 2026.
[2] x402 documentation, "MCP Server with x402," Coinbase Developer Platform, 2026.
[3] x402 documentation, "Signed Offers & Receipts," x402 Extensions, 2026.
[4] Agent Payments Protocol documentation, "Agentic Payment Protocol (v0.2)," 2026.
[5] Stripe documentation, "Agentic commerce," 2026.
[6] PayCrow MCP connector metadata, `safe_pay` / protected-call verification data, 2026.
[7] ERC-8004, "Trustless Agents," Ethereum Improvement Proposals, draft, 2026.
[8] ERC-8183, "Agentic Commerce," Ethereum Improvement Proposals, draft, 2026.
[9] Goenka, Pathak, Asthana, "TessPay: Verify-then-Pay Infrastructure for Trusted Agentic Commerce," arXiv:2602.00213, 2026.
[10] "A402: Bridging Web 3.0 Payments and Web 2.0 Services with Atomic Service Channels," arXiv:2603.01179, 2026.
[11] H. Pagnia and F. C. Gärtner, "On the Impossibility of Fair Exchange without a Trusted Third Party," Technical Report TUD-BS-1999-02, Darmstadt University of Technology, 1999.
[12] S. Even, O. Goldreich, A. Lempel, "A Randomized Protocol for Signing Contracts," Communications of the ACM 28(6):637–647, 1985.
[13] S. Dziembowski, L. Eckey, S. Faust, "FairSwap: How to Fairly Exchange Digital Goods," ACM CCS 2018 (IACR ePrint 2018/740).
[14] L. Eckey, S. Faust, B. Schlosser, "OptiSwap: Fast Optimistic Fair Exchange," 2020 (IACR ePrint 2019/1330).

## 8. Limitations and threat model

DeliveryProof makes trust explicit; it does not remove trust. The main limitations
are therefore part of the protocol's intended threat model, not incidental bugs.

First, predicate authorship is load-bearing. A verifier can only answer whether the
delivered artifact satisfied the predicate in the contract. If the buyer writes a
weak predicate, accepts a malicious template, or omits the property they actually
care about, a perfectly verified deliverable can still be commercially wrong.
`routeDecision` prevents silent downgrade of verifier strength; it does not prove
the chosen predicate captures human intent.

Second, dataset verification is objective but not omniscient. Row count, required
and nullable fields, type/domain/range/regex checks, unique keys, full-scan aggregates,
optional dataset hashes, and verifier-seeded samples are useful correctness
constraints. They are not full semantic truth. Sampling is especially partial: it
can catch tampering probabilistically or as part of a committed audit policy, but it
does not prove every unsampled row is correct unless paired with full-dataset
commitments or full-scan invariants that cover the relevant property. v0.6 Merkle
support, preserved in v0.8, includes full-root mode: the verifier still receives
the full dataset, checks the committed Merkle root for anti-equivocation, and emits
inclusion proofs for sampled rows so downstream consumers can verify those rows
without the full set. v0.8 adds explicit partial Merkle sample mode via
`dataset-merkle-sample`: the verifier receives only `{ index, row, proof }` entries
for deterministic verifier-selected sorted leaf indices, checks each proof against
the committed root, and checks row-level constraints on the supplied rows. Merkle
inclusion proves row membership in the committed set; it does not by itself prove
global row count, uniqueness, aggregate, or full-dataset truth.
Dataset regex constraints are deliberately bounded and conservative to reduce
verifier-side ReDoS risk, but they are not a formal safe-regex system; predicate
authors still own their patterns.

Third, external truth and subjective quality are outside Tier A. A zkTLS proof can
show that a server returned a response; it cannot prove the response is true. A TEE
can attest to a measured program under a hardware trust root; it cannot eliminate
trust in the TEE ecosystem. An LLM judge can be useful for semantic quality, but it
is a trusted judge and should be treated as Tier C, not objective correctness.

Fourth, settlement finality remains rail policy. DeliveryProof signs why the engine
chose `release` or `refund`, and the mock rail enforces the local state machine.
Real rails define their own authorization windows, capture semantics, refund timing,
chargebacks, reversals, compliance blocks, and failure modes. A signed
DeliveryReceipt is evidence for rail action; it is not itself a universal guarantee
of final settlement.

Fifth, the ERC-8004 and ERC-8183 adapters are projection helpers only. The default
path still emits `0x`-prefixed SHA-256 digests with `hashAlg: 'sha256'` for
backward compatibility. Opt-in `hashAlg: 'keccak256'` mode emits Ethereum
Keccak-256 digest words and ABI-shaped argument bytes. The adapters intentionally
contain no contracts, wallets, provider/RPC URLs, private keys, chain calls, or
submission logic.

Sixth, an ERC evaluator can still point at a bad predicate. DeliveryProof can supply
a deep evaluator result for ERC-8004/8183-style shells, but those shells may still
choose weak policies, malicious evaluators, or predicates that do not encode the
buyer’s intent. Interop increases adoption surface; it does not guarantee good
governance.

Seventh, the mock escrow is a reference state machine, not a settlement guarantee.
It exists to test the invariant that `verdict.ok === false` never captures the hold.
The durable rail adds local WAL recovery and idempotent terminalization for the same
mock hold ledger, but it does not claim fsync-level power-loss durability and still
does not model custody, insolvency, external-rail exactly-once semantics, rail
disputes, gas failures, bank/card reversals, or legal enforceability.

Eighth, cryptographic operations are intentionally narrow: Node built-ins for
Ed25519 and SHA-256, plus `@noble/hashes` for Ethereum Keccak-256 because Node's
`sha3-256` is not Ethereum Keccak. A production deployment still needs durable
key storage, key rotation, replay-window policy, and independent security review.

Ninth, resource bounds are not arbitrary-code sandboxing. Canonicalization and
verifier paths have pragmatic depth/size/work caps, but these are guardrails, not
formal denial-of-service proofs. The `builtin-replay` verifier
runs deterministic built-in replay in a worker with size/depth/time limits; it does
not run untrusted seller JavaScript, and Node worker resource limits are not a
complete process or OS isolation boundary. The `document` verifier similarly caps
document size, line length, and line count before parsing; these are parser
resource bounds, not a general Markdown security sandbox.

Tenth, nonce replay protection is attempt-scoped. Reserving a nonce before
authorization prevents replay holds, but it also means a refunded or failed attempt
burns the nonce; retries require a fresh nonce.

Eleventh, milestone settlement is receipt-level composition. Each child milestone is
settled independently and the aggregate verifies child receipts and accounting. It
is not a single rail-native partial-capture primitive, and a production rollup may
want an additional externally signed schedule commitment.

Twelfth, CSV support is now RFC-4180-compatible for quoted fields, embedded
commas/newlines, and escaped quotes, but it remains deliberately bounded. The parser
caps total CSV characters, cell characters, column count, and row count, and fails
closed on malformed quoting rather than silently guessing.

Thirteenth, byte-tagged Merkle commitments remain SHA-256 commitments for
portability, not EVM-native hashing. External consumers must reproduce the exact
construction (`0x00 || canonicalize(row)`, `0x01 || left || right`, `0x02`
empty) or wrap it at a chain boundary. Keccak helpers exist for interop
projections; they do not change core protocol commitments.

Fourteenth, DeliveryProof is not a marketplace, reputation system, identity layer, or
Sybil-resistant economy. It verifies a delivery predicate and records why settlement
was released or refunded. Discovery, reputation, KYA/KYC, validator incentives,
pricing, abuse control, and Sybil resistance belong in surrounding systems.

Fifteenth, DeliveryProof provides no formal fairness theorem. Unlike on-chain optimistic
fair-exchange constructions (FairSwap, OptiSwap), it has no dispute game and no autonomous
on-chain enforcement; fairness reduces to the honest behavior of the named trust points —
verifier, rail, and predicate author — and to the rail's own finality model. The
contribution is an objective, recomputable verdict and a portable receipt, not a
cryptographic guarantee that a dishonest counterparty cannot strand the exchange. At the
money layer the reference rails reject a receipt whose `decision` contradicts its
`verdict.ok`, and since v0.10 settlement-signature verification is mandatory by default;
neither replaces a real rail's authorization, custody, and finality rules.

The threat model is therefore intentionally narrow: for objective digital
deliverables, assuming the buyer chose an adequate predicate and the rail honors the
signed decision, DeliveryProof prevents payment release on a negative verification
result and produces a portable audit record of the decision. Claims beyond that are
out of scope.

## 9. Conclusion

Escrow for agents is solved; **objective delivery verification is not.** DeliveryProof
shows the missing layer is buildable, small, and honest: a signed delivery receipt, a
no-silent-downgrade verifier router, deep objective verifiers, and an explicit tiered
trust model — composable beneath the payment rails and escrow shells already shipping.
It does not abolish trust; it makes trust legible and gates payment on proof. Whether
this becomes an adopted standard depends on one open question we name plainly:
*recurring demand for deep objective correctness.* This repository exists to make the
protocol and its gating invariant concrete, runnable, and falsifiable.

---

## Reproducibility

Every claim in §5–§6 is runnable: `node --test` (full suite) and the
`examples/demo-*.mjs` scripts. No network, one pinned runtime dependency,
deterministic.

## License

Apache-2.0

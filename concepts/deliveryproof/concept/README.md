# DeliveryProof

Verified-delivery-gated settlement for AI-agent commerce.

DeliveryProof is a rail-neutral protocol and Node reference implementation that
holds payment until a machine-checkable delivery predicate passes. It answers the
question payment-authorization rails leave open: not just "is this agent allowed
to pay?", but "did the counterparty deliver the thing the contract asked for?"
It makes trust explicit and checkable; it does not abolish trust.

For the full paper-style treatment, read [docs/WHITEPAPER.md](./docs/WHITEPAPER.md).
For byte-level protocol details, read [SPEC.md](./SPEC.md).

## Is It Live-Tested?

**Yes, locally end to end.** The v0.10 tree runs `310/310` Node tests and eleven
example demos. Those tests and demos execute real canonical hashing, Ed25519
receipt signatures, deep verifiers, replay protection, keyring verification,
Ethereum Keccak helpers, and the money-shot flows where shallow checks release
while deep checks refund on the same bytes.

**No, not as real money or a deployed service.** This repository ships reference
rails only: an in-memory mock rail and a local durable rail. It does not custody
funds, call a payment provider, submit transactions, hold private keys, run an
RPC client, or deploy a service.

## The Problem

Agent payment systems are good at authorization. They can prove that an agent is
allowed to pay, that a payment request is shaped correctly, or that an escrow hold
exists.

That is different from proving delivery.

If a seller returns `{"temperature": 999}` for a weather request, a shallow rail
may see HTTP 200 plus valid JSON and release payment. If a data vendor ships a
table with the right columns but corrupted values, a schema check may pass even
though the buyer did not receive the promised dataset. DeliveryProof puts an
objective delivery predicate in front of settlement so the release/refund decision
is bound to the delivered artifact.

## How One Transaction Works

The exact wire objects are specified in [SPEC.md](./SPEC.md). This README uses
compact examples to show the *shape* of the flow; field names, nesting, and
types are simplified for reading. [SPEC.md](./SPEC.md) is normative and
copy-paste-ready — for example, the real wire field is `protocolVersion:
"deliveryproof/0.4-jcs1"` and prices are numbers under `price`, not strings.

### 1. Write the contract

The buyer and seller agree on what is being bought, which predicate must pass,
which rail will hold funds, and which nonce makes this settlement attempt unique.

```js
const contract = {
  protocolVersion: "deliveryproof/0.4-jcs1",
  contractId: "weather-quote-001",
  buyer: { keyId: "buyer-ed25519" },
  seller: { keyId: "seller-ed25519" },
  amount: "25.00",
  currency: "USD",
  rail: { id: "escrow-mock" },
  nonce: "nonce-001",
  deliverable: {
    type: "api-response",
    request: { city: "AMS", units: "celsius" },
    predicate: {
      status: 200,
      jsonPaths: [{ path: "$.city", equals: "AMS" }]
    }
  }
};
```

The predicate is load-bearing. A perfect proof against the wrong predicate is
still wrong.

### 2. Authorize a hold

The selected rail authorizes a hold before the seller is paid.

```js
const hold = {
  railId: "escrow-mock",
  holdId: "hold-weather-quote-001",
  amount: "25.00",
  currency: "USD",
  state: "held"
};
```

In this repository, the shipped rails are reference rails for local testing and
integration development. A real payment rail belongs in a companion package or a
deployment-specific integration.

### 3. Deliver evidence

The seller produces the deliverable and binds it to the contract nonce.

```js
const evidence = {
  contractId: "weather-quote-001",
  nonce: "nonce-001",
  output: {
    status: 200,
    body: { city: "AMS", temperature: 21 }
  },
  outputHash: "sha256:..."
};
```

Evidence is canonicalized and hashed before it is signed into the receipt.

### 4. Route to the verifier

The router picks the cheapest verifier that still satisfies the requested
assurance level. It refuses to silently downgrade.

```js
const routeDecision = {
  selected: "api-response",
  assurance: "tier-a",
  fallbackUsed: false,
  policyHash: "sha256:..."
};
```

The route decision is part of the signed receipt, so a downgrade is
tamper-evident.

### 5. Produce a verdict

The verifier checks the evidence against the predicate.

```js
const verdict = {
  ok: true,
  verifier: "api-response",
  reason: "response satisfied declared JSON-path assertions"
};
```

If the verifier returns `ok: false`, settlement must refund. The engine test suite
asserts the core invariant: there is no capture path when `verdict.ok === false`.

### 6. Sign the receipt

The settlement outcome is signed as a `DeliveryReceipt`.

```js
const receipt = {
  contractHash: "sha256:...",
  evidenceHash: "sha256:...",
  routeDecision,
  verdict,
  decision: "release",
  rail: { id: "escrow-mock", holdId: "hold-weather-quote-001" },
  signerKeyId: "settlement-ed25519",
  signature: "ed25519:..."
};
```

Consumers verify receipts with `verifyReceipt(receipt, pem)`,
`verifyReceipt(receipt, { keys })`, or `verifyReceipt(receipt, { keyring })`.

### 7. Capture or refund

The decision follows the verdict.

```js
const decision = verdict.ok ? "release" : "refund";
```

`release` captures the hold. `refund` returns it. Same-receipt terminal replay is
idempotent on the reference rails; conflicting terminal attempts are rejected.

The reference rails re-enforce the verdict at the money layer, not only inside
`settle()`: a receipt whose `decision` disagrees with its `verdict.ok` is rejected
before any capture or refund, so a forged "release the hold" receipt carrying a
failing verdict cannot terminalize.

**Since v0.10 the rails also fail closed on authenticity.** Every rail requires a
`settlementPublicKey` at construction and verifies the DeliveryReceipt signature
before any terminalization. Up to v0.9.1 this was opt-in, and a rail built
without a key verified *no* signature at all — so a receipt that was internally
consistent (`verdict.ok: true`, `decision: 'release'`) with the correct binding
fields could capture a hold with no settlement private key involved. Two
independent review passes reproduced that with a working exploit. It is closed.

Demos and fixtures that genuinely need the old behaviour pass
`allowUnsignedReceipts: true`. The name is deliberately blunt, construction is
the only place it can be set, and every terminalization taken on that path emits
a `rail.unsigned.accepted` audit event.

## The Money Shot

DeliveryProof keeps shallow and deep checks side by side so the difference is
reproducible.

On the same delivered bytes:

- A shallow schema verifier can release payment because the artifact has the right
  shape.
- A deep verifier can refund because the artifact violates the promised content.

The dataset, API-response, document, and partial-Merkle demos show this pattern.
That is the core claim of the project: the escrow shell is not the hard part; the
delivery verifier is.

## 60-Second Quickstart

Requires Node v22+.

```bash
npm ci
npm test
node examples/demo-dataset.mjs
node examples/demo-keyring.mjs
node examples/demo-audit-bundle.mjs
node examples/demo-keccak-interop.mjs
node examples/demo-production-seams.mjs
npm run demo
```

Expected shape:

- `npm test` runs the full Node test suite.
- `node examples/demo-dataset.mjs` shows a shallow schema path that releases and a
  deep dataset path that refunds on corrupted data.
- `node examples/demo-keyring.mjs` shows verification-only key rotation.
- `node examples/demo-audit-bundle.mjs` shows receipt-bound dispute inspection.
- `node examples/demo-keccak-interop.mjs` prints SHA-256 and opt-in Keccak
  ERC projection digests side by side.
- `node examples/demo-production-seams.mjs` runs the exported rail and replay
  store conformance suites against reference adapters.
- `npm run demo` runs all eleven examples under `examples/`.

## Architecture

```text
Buyer + seller contract
        |
        v
settle(contract, produceEvidence, options)
        |
        +--> nonce registry reserves the attempt
        |
        +--> rail.authorize() creates a hold
        |
        +--> seller produces DeliveryEvidence
        |
        +--> verifier router selects sufficient verifier
        |
        +--> verifier returns Verdict
        |
        +--> engine signs DeliveryReceipt
        |
        +--> verdict.ok ? rail.capture() : rail.refund()
```

The receipt binds the contract hash, evidence hash, route decision, verdict,
settlement decision, rail status, signer key id, and signature. The audit-bundle
helper collates those bindings for dispute review; it does not create a new proof.

## Trust Model

DeliveryProof is not marketed as trustless. It names the trust points.

| Tier | Meaning | Examples in this repository |
|------|---------|-----------------------------|
| A | Objective and independently recomputable | `hash`, `schema`, `builtin-replay`, `transcript`, `dataset`, `api-response`, `document`, `compose`, Merkle sample verification |
| B | Attested by another proof system or source | `signed-oracle`; interface descriptors for TEE, zkTLS, and ZK proof systems |
| C | Subjective judgment | Documented as an extension point, not shipped as a settlement-critical verifier |

The important boundary is simple: DeliveryProof makes trust explicit and
checkable; it does not abolish it.

## What This Is Not

- Not a deployed service.
- Not a payment processor.
- Not custody software.
- Not a wallet, RPC client, contract caller, or on-chain submission tool.
- Not a replacement for legal review of regulated custody, MSB, MTL, or payment
  operations.
- Not a claim that external facts are true. A verifier can prove that bytes match
  a predicate; provenance and truth-source trust are separate.
- Not a way around predicate authorship. The predicate is load-bearing.

The repository has one pinned runtime dependency, `@noble/hashes@2.2.0`, for
Ethereum Keccak helpers. Otherwise the reference implementation relies on Node
built-ins. The ERC-8004 and ERC-8183 helpers are projection/encoding helpers only:
they do not sign with wallets, connect to providers, submit transactions, or
custody assets.

## v0.9 Integration Seams

v0.9 adds the seams needed for real integrations without adding provider-specific
code to the core package.

- **Rail conformance:** exported conformance cases certify that a rail adapter
  honors release/refund terminality, idempotency, receipt binding, no-network
  reference behavior, and refusal to capture on a verdict-contradicting receipt.
  See `examples/demo-production-seams.mjs`.
- **Fail-closed rail mode:** the reference rails reject internally contradictory
  receipts unconditionally, and (since v0.10) require `settlementPublicKey` at
  construction so every terminalization is signature-checked by default. The
  `requireSignature` flag is retained as a no-op alias. The interop
  projection helpers (`toErc8004ValidationPayload`, `toErc8183EvaluatorResult`)
  likewise refuse to project a contradictory receipt into a chain-facing
  `complete`/`release` result.
- **Replay-store conformance:** the nonce registry can use a supplied replay
  store, and the conformance suite checks reserve/mark/get semantics, restart
  survival, and concurrent double-reserve rejection. See
  `examples/demo-production-seams.mjs`.
- **Keyring verification:** `verifyReceipt` still accepts a PEM string, and also
  supports `{ keys }` and `{ keyring }` for verification-only rotation. See
  `examples/demo-keyring.mjs`.
- **Production profile preflight:** `validateDeliveryProofConfig(config,
  { profile: "production" })` hard-errors on a missing nonce registry and warns
  about operational risks such as no audit sink or non-durable local WAL choices.
- **Audit bundles:** `buildAuditBundle` collates contract, evidence, receipt,
  verdict, decision, and optional rail status hashes for dispute inspection. See
  `examples/demo-audit-bundle.mjs`.
- **Ethereum interop:** Keccak and ABI-shape helpers support ERC-8004/ERC-8183
  projection payloads. `sha256` remains the default hash algorithm; `keccak256` is
  opt-in. See `examples/demo-keccak-interop.mjs`.

For wiring guidance, including how to build companion packages that bring Stripe,
Postgres, KMS, or chain-specific code outside this core package, see
[docs/PRODUCTION-INTEGRATION.md](./docs/PRODUCTION-INTEGRATION.md).

## Where To Read Next

- [Whitepaper](./docs/WHITEPAPER.md) - full concept, impossibility-result
  background, experiment narrative, related work, and limitations.
- [Specification](./SPEC.md) - normative objects, hashes, signatures, and state
  machine.
- [API reference](./docs/API.md) - exported functions and usage.
- [API stability](./docs/API-STABILITY.md) - stability promises and versioning.
- [Production integration](./docs/PRODUCTION-INTEGRATION.md) - rails, replay
  stores, keyrings, audit sinks, and companion-package guidance.
- [Full vs partial Merkle](./docs/MERKLE-PARTIAL-VS-FULL.md) - what partial
  Merkle sampling proves and what it does not.
- [Threat model](./docs/THREAT-MODEL.md) - assumptions and attacker boundaries.
- [Supply chain](./docs/SUPPLY-CHAIN.md) - dependency and release posture.
- [Escalations](./docs/ESCALATIONS.md) - human-decision areas such as custody,
  live chain submission, and external operator review.
- [Security](./SECURITY.md) and
  [production-readiness notes](./PRODUCTION-READINESS.md) - operational caveats.

## License

Apache-2.0 — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).

You may use, modify, redistribute, and build commercial or closed-source products
on this software. In exchange, Apache-2.0 §4(d) requires that you keep the
attribution in [NOTICE](./NOTICE) — the ProofOfWork Agency copyright line — visible
somewhere customary in your product (source header, docs, or a third-party
notices screen). No permission request, no fee, no obligation to open your own
changes. Just keep the credit.

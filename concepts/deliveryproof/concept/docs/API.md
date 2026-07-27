# DeliveryProof API Reference

Import the public surface from the package root:

```js
import {
  settle,
  verifyReceipt,
  assertReceiptMeetsPolicy,
  routeVerifier,
  getVerifier,
  createMockEscrowRail
} from 'deliveryproof';
```

Subpath imports are not part of the stable API. Stability labels are maintained in
`docs/API-STABILITY.md`.

## Core Settlement

### `settle(options)`

Runs the settlement state machine:

1. validates and normalizes the contract;
2. authorizes a rail hold;
3. asks the seller to produce evidence;
4. runs the verifier;
5. signs a `DeliveryReceipt`;
6. captures only on `verdict.ok === true`, otherwise refunds.

`options` includes:

- `contract`;
- `produceEvidence(contract, context)`;
- `verifier`;
- `rail`;
- `settlementKey`;
- optional `routeDecision`;
- optional `nonceRegistry`;
- optional `now`;
- optional `audit`.

`now` defaults to `Date.now`. `audit` is best-effort and cannot affect settlement
or signed receipt bytes. Production callers should provide either a persistent
`nonceRegistry` or a rail adapter with equivalent idempotency/replay protection.
When `routeDecision` is supplied, `settle` requires it to name the same verifier
that is actually injected.

### `verifyReceipt(receipt, trust)`

Verifies the Ed25519 signature over the canonical receipt-without-signature. Returns
`true` or `false`. It also rejects receipts whose signed `decision` contradicts
the signed `verdict.ok` value.

`trust` may be a PEM public key string, `{ keys: string[] }`, or `{ keyring }`.
Keyring mode is verify-only and is intended for settlement-authority rotation
windows.

### `assertReceiptMeetsPolicy(receipt, policy)`

Validates optional production-integration requirements after `verifyReceipt`
succeeds. Direct library users may choose their verifier and rail explicitly,
while stricter integrations can require signed routing evidence, disallow
fallback, pin the expected rail/verifier, or require a nonce-registry key.

Common policy keys:

- `requireRouteDecision: true`;
- `allowFallback: false`;
- `minAssurance`;
- `expectedVerifier`;
- `expectedRailId`;
- `requireNonceRegistry: true`;
- `expectedPolicyHash` (v0.10) — pin the exact router policy that produced the
  decision. Without it, a receipt routed under a permissive policy is
  indistinguishable from one routed under the strict policy you believe was in
  force.

Two v0.10 behaviour changes worth knowing:

- `minAssurance` now **fails** when the receipt carries no `routeDecision`.
  Previously that check was skipped, so the weakest possible receipt satisfied the
  strictest possible policy.
- `settle()` no longer signs a caller-supplied `selectedAssurance`. It re-derives
  the value from the trusted profile table and refuses to sign a mismatch, and it
  will not grant a protocol assurance level to a verifier that is not the built-in
  by object identity. A custom verifier still runs; it cannot inherit an assurance
  number by reusing a built-in's name.

## Replay stores

### `createNonceRegistry(options)` / `createWalReplayStore(options)`

The default WAL store is durable across restarts, but its uniqueness check lives
in an in-process `Map`. Two processes sharing one log will **both** reserve the
same nonce. Single-process deployments only.

### `createSqliteReplayStore({ dbPath })` (v0.10)

Cross-process-atomic replay store. Uniqueness is a SQLite `PRIMARY KEY`, so the
constraint — not application code — decides the winner of a concurrent
reservation, under SQLite's own file lock. Use this whenever more than one
process can settle.

```js
import { createNonceRegistry, createSqliteReplayStore } from 'deliveryproof';

const nonceRegistry = createNonceRegistry({
  store: createSqliteReplayStore({ dbPath: '/var/lib/deliveryproof/replay.db' }),
});
```

Uses `node:sqlite` (built into Node 22+), so the package's single-runtime-dependency
guarantee is unchanged. Pass `':memory:'` for single-process tests — an in-memory
database has nothing to be atomic *across*.

Known limitation, shared with the WAL store: `mark()` authenticates only the
replay key, so any holder of that key can advance or regress a row's state. This
is a property of the `ReplayStore` interface contract both stores implement.

## Verifiers

### `getVerifier(kind)` and `verifiers`

Resolve verifier implementations by predicate kind. Runnable built-ins include:

- `schema`;
- `hash`;
- `builtin-replay`;
- `transcript`;
- `dataset`;
- `api-response`;
- `document`;
- `compose`;
- `signed-oracle`.

Tier-A verifiers are objective and recomputable. `signed-oracle` is Tier B: it
proves an allowed attester signed a bound statement, not that the external-world
fact is true.

## Router

### `routeVerifier(contract, { policy, registry?, profiles? })`

Selects the cheapest verifier that still satisfies `policy.minAssurance`. If no
verifier qualifies, it throws unless `fallbackAllowed: true`. The route decision is
designed to be signed into the receipt so downgrades are visible.

## Protocol Utilities

Stable helpers include:

- `canonicalize`;
- `sha256hex`;
- `sha256utf8`;
- `sha256bytes`;
- `keccak256`;
- `PROTOCOL_VERSION`;
- Ed25519 key/sign/verify helpers;
- schema assertion helpers;
- Merkle helpers.

Merkle helpers use byte-tagged SHA-256:

```text
leaf  = SHA256(0x00 || canonicalize(row))
node  = SHA256(0x01 || leftHashBytes || rightHashBytes)
empty = SHA256(0x02)
```

## Rails

### `createMockEscrowRail(options?)`

Reference in-memory rail for tests and demos only. It is not production money
movement. It rejects a receipt whose `decision` contradicts its `verdict.ok` before
any terminalization. Since v0.10 it **requires** `settlementPublicKey` at
construction and verifies the DeliveryReceipt signature on every
`capture`/`refund`. Construction without a key throws unless the caller passes
`allowUnsignedReceipts: true`, which skips verification and emits a
`rail.unsigned.accepted` audit event on each terminalization. `requireSignature`
is a retained no-op alias.

### Durable local rail helpers

The durable rail demonstrates append-only local WAL recovery, idempotent terminal
operations, `flush`, `close`, and `health`. It is still a reference local hold
ledger, not a production external rail adapter, and it does not claim
fsync-level power-loss durability. Like the mock rail it rejects receipts whose
`decision` contradicts `verdict.ok`, and since v0.10 requires
`settlementPublicKey` at construction so signatures are verified before the
terminal WAL record is written (`allowUnsignedReceipts: true` opts out).

## Operability

Operability helpers provide:

- optional best-effort audit events at engine/router/rail boundaries;
- config validation for required functions and object shapes;
- health/status helpers for local components.

These helpers are library utilities. They do not imply a hosted service.

## MCP Wrapper

### `paidToolWithDeliveryProof(options)`

Wraps a local tool call in the DeliveryProof settlement flow. The wrapper defaults
to an in-memory nonce registry for that wrapper instance, so accidental
same-contract replay fails closed in demos and local integrations. Production
callers should pass a persistent nonce registry or equivalent rail idempotency.

`strictRouting: true` requires a `routeDecision` object or function and rejects
direct unrouted calls. This is recommended for production wedges that want signed
routing evidence; it is not forced on lower-level `settle()` callers.

`makeEvidence` may add verifier-specific proof material, but it cannot replace the
raw tool output unless `allowOutputOverride: true` is set explicitly. That keeps
the default wrapper behavior aligned with the artifact the tool actually returned.

## Interop

ERC-8004 and ERC-8183 helpers project signed receipts into standard-shaped payloads.
They do not perform chain calls, wallet actions, RPC, private-key handling, or
on-chain submission. SHA-256 remains the default projection hash for backward
compatibility; callers may opt into `hashAlg: 'keccak256'` for EVM-native digest
words and ABI-shaped argument encoding.

Public helpers:

- `toErc8004ValidationPayload(receipt, { hashAlg?, includeAbi? })`;
- `encodeErc8004ValidationAbi(payload)`;
- `toErc8183EvaluatorResult(receipt, { jobId?, hashAlg?, includeAbi? })`;
- `encodeErc8183EvaluatorAbi(result)`.

## Minimal Example

```js
import {
  createMockEscrowRail,
  generateKeypair,
  settle,
  verifiers
} from 'deliveryproof';

const settlementKey = generateKeypair();
const rail = createMockEscrowRail();

const result = await settle({
  contract,
  produceEvidence: async () => evidence,
  verifier: verifiers.hash,
  rail,
  settlementKey
});

console.log(result.receipt.decision);
```

Use a real non-custodial rail adapter before moving real money.

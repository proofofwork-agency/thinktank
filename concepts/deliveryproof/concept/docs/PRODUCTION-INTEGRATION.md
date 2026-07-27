# Production Integration Guide

DeliveryProof is an objective-verification library with one pinned runtime
dependency, `@noble/hashes`, for Ethereum Keccak-256 helpers. Production
deployments should wire it into external custody, replay storage, key management,
audit, and compliance systems outside this package.

This guide names the integration seams added for v0.9. The in-repo
implementations remain references for local tests and demos.

## Receipt Verification And Key Rotation

`verifyReceipt(receipt, publicKeyPem)` still verifies a single settlement
authority key. For rotation windows, pass a key list or keyring:

```js
import { createInMemoryKeyring, verifyReceipt } from 'deliveryproof';

const okFromList = verifyReceipt(receipt, {
  keys: [previousSettlementPublicKey, activeSettlementPublicKey],
});

const keyring = createInMemoryKeyring([
  previousSettlementPublicKey,
  activeSettlementPublicKey,
]);
const okFromKeyring = verifyReceipt(receipt, { keyring });
```

The verifier resolves `receipt.signerKeyId` first, then scans configured keys as a
fallback. All verification arms return `false` rather than throwing for malformed
trust inputs, unknown key ids, empty keyrings, or bad signatures.

`createInMemoryKeyring()` is a public-key lookup helper, not KMS or HSM custody.
Production signing policy, revocation, operator authorization, and private-key
custody belong in the deployment or a companion package.


### Replay store: use the atomic one if more than one process can settle

The bundled WAL store keeps its uniqueness check in an in-process `Map`, so two
processes sharing one log will BOTH reserve the same nonce and the same contract
can settle twice. Since v0.10 the package ships an atomic alternative whose
uniqueness is a SQLite `PRIMARY KEY`:

```js
import { createNonceRegistry, createSqliteReplayStore } from 'deliveryproof';

const nonceRegistry = createNonceRegistry({
  store: createSqliteReplayStore({ dbPath: '/var/lib/deliveryproof/replay.db' }),
});
```

It uses `node:sqlite` (Node 22+), so the one-runtime-dependency guarantee holds.
A Postgres/Redis store with an equivalent atomic uniqueness constraint is also
fine — validate any implementation with the exported replay-store conformance
suite, which covers concurrent double-reserve.


## Signature-Verifying Rails

Reference rails can reject forged direct terminalization when constructed with the
settlement public key:

```js
import { createDurableEscrowRail } from 'deliveryproof';

const rail = createDurableEscrowRail({
  logPath: '/var/lib/deliveryproof/rail.jsonl',
  settlementPublicKey: activeSettlementPublicKey, // REQUIRED since v0.10
});
```

Since v0.10 a settlement key is mandatory: construction throws without one, and
every terminalization verifies the receipt signature. `requireSignature` is a
retained no-op alias.

Two gates run at the money layer, and they close different holes. The
*consistency* gate rejects a receipt whose `decision` contradicts its
`verdict.ok` — that stops a forged "release" carrying a failing verdict, and it
has never needed a key. *Signature verification* is what stops a
forged-but-internally-consistent receipt. Before v0.10 the second gate was
opt-in, so a rail built without a key accepted any well-formed release receipt;
that is why the key is now required rather than encouraged.

`allowUnsignedReceipts: true` restores the old behaviour for demos and fixtures.
Do not set it in a deployment: it disables the only check that distinguishes a
real settlement receipt from a well-formed forgery.

The rail still must enforce its own money-movement semantics. A production rail
adapter should verify receipt signatures before terminal settlement, carry
idempotency keys into the external rail, and map capture/refund outcomes to the
rail's real finality model.

## Replay Store And Fsync

`createNonceRegistry()` owns DeliveryProof nonce keys and fingerprints. By
default it wraps the in-process WAL replay store:

```js
import { createNonceRegistry, createWalReplayStore } from 'deliveryproof';

const replayStore = createWalReplayStore({
  logPath: '/var/lib/deliveryproof/replay.jsonl',
  fsync: true,
});

const nonceRegistry = createNonceRegistry({ store: replayStore });
```

The in-repo WAL store is restart-durable when `logPath` is set, and `fsync: true`
forces `appendFileSync` followed by `fsyncSync` for each WAL append. It has no
cross-process lock. A production `DurableReplayStore` should implement the
exported `REPLAY_STORE_INTERFACE` methods and enforce concurrent
double-reserve rejection with an atomic storage primitive, such as a database
unique constraint.

## Audit Sink

Pass `audit` to `settle`, `routeVerifier`, or reference rails to receive
best-effort boundary events:

```js
const audit = {
  emit(event) {
    // Write to your logging, SIEM, warehouse, or dispute system.
  },
  onError(error, event) {
    // Audit failures are observed, not allowed to change settlement.
  },
};
```

Audit events are not signed receipt bytes and audit sink failures do not affect
settlement decisions. Treat them as operational telemetry.

## Production Preflight

Use the production profile before accepting real traffic:

```js
import { validateDeliveryProofConfig } from 'deliveryproof';

const result = validateDeliveryProofConfig({
  rail,
  verifier,
  settlementKey,
  nonceRegistry,
  audit,
  railReceiptSignatureVerification: true,
  replayStoreLogPath: '/var/lib/deliveryproof/replay.jsonl',
}, { profile: 'production' });

if (!result.ok) throw new Error(result.errors.join('; '));
```

The default profile is backward compatible and checks object shapes. The
production profile adds one hard error and several warnings:

- hard error: missing `nonceRegistry`;
- warning: no audit sink configured;
- warning: WAL paths under tmpfs-like locations such as `/tmp`, `/var/folders`,
  or `/dev/shm`;
- warning: a rail is configured without declaring
  `railReceiptSignatureVerification: true`.

## Audit Bundles For Disputes

Use `buildAuditBundle()` to collate the receipt, contract, evidence, and optional
rail status into an inspectable object:

```js
import { buildAuditBundle } from 'deliveryproof';

const bundle = buildAuditBundle({
  receipt,
  contract,
  evidence,
  railStatus: rail.status(receipt.holdId),
});
```

The bundle hashes the supplied artifacts and reports whether existing receipt
bindings still match. It does not create a new proof, contact telemetry, or alter
settlement. Use it as a dispute inspection aid alongside receipt verification and
rail records.

## Companion Package Pattern

Keep heavyweight integrations out of this small core library. Build them in a
companion package that depends on `deliveryproof`:

```json
{
  "name": "@your-org/deliveryproof-stripe-pg-kms",
  "dependencies": {
    "deliveryproof": "<approved-release-version>",
    "pg": "...",
    "stripe": "...",
    "@aws-sdk/client-kms": "..."
  }
}
```

The companion package should:

- implement a real `RailAdapter` for Stripe, x402, AP2, on-chain escrow, or
  another non-custodial rail;
- implement `REPLAY_STORE_INTERFACE` with durable atomic uniqueness;
- implement private-key signing through KMS or HSM, while using DeliveryProof's
  public keyring verification surface for receipts;
- configure a production audit sink;
- run DeliveryProof's exported conformance suites in companion CI.

Example conformance tests:

```js
import {
  runRailConformance,
  runReplayStoreConformance,
} from 'deliveryproof';

test('rail adapter conforms', async () => {
  const result = await runRailConformance({
    createRail: ({ settlementPublicKey }) => createYourRail({
      settlementPublicKey,
    }),
  });
  assert.equal(result.ok, true);
});

test('replay store conforms', async () => {
  const result = await runReplayStoreConformance({
    createStore: () => createYourPostgresReplayStore(),
    supportsRestart: true,
  });
  assert.equal(result.ok, true);
});
```

Run those tests in the companion package CI with real dependency versions pinned
there. This repository should remain the small protocol, verifier, and interface
surface.

For the current adapter strategy and priority order, see
[ADAPTER-RFC.md](./ADAPTER-RFC.md). The short version: build
`@deliveryproof/rail-erc8183-base` first as a companion reference adapter, then a
named x402 escrow/voucher integration second; do not add live wallet/RPC/provider
code to core.

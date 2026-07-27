# DeliveryProof API Stability

DeliveryProof v0.10 exposes one supported package entry point:

```js
import {
  settle,
  verifyReceipt,
  assertReceiptMeetsPolicy,
  routeVerifier,
  datasetVerifier,
} from 'deliveryproof';
```

The package export map intentionally exposes only `.`. Files under `src/` are
implementation modules unless re-exported from `src/index.mjs`.

## Breaking Changes in v0.10

This is a pre-1.0 concept library; v0.10 breaks compatibility deliberately rather
than shipping an unsafe default through a deprecation window.

- **Rail constructors require `settlementPublicKey`.** `createMockEscrowRail`,
  `createDurableEscrowRail`, and `createErc8183Rail` now throw without one. Pass
  `allowUnsignedReceipts: true` to opt out (demos/fixtures only). `requireSignature`
  remains accepted as a no-op alias.
- **`settle()` rejects unverifiable `routeDecision.selectedAssurance`.** The value
  is re-derived from the trusted profile table, and a protocol assurance level is
  granted only to the built-in verifier by object identity.
- **`assertReceiptMeetsPolicy` with `minAssurance` now fails** on a receipt with no
  `routeDecision`, where it previously passed.
- **SLA deadlines are enforced for `createdAt: 0`.** Only negative or non-finite
  `createdAt` disables the deadline.
- **The contract passed to `produceEvidence` is deeply frozen.** A producer that
  mutated it previously succeeded; it now throws and the settlement refunds.
- **`testsuite` is renamed `builtin-replay`.** The old predicate kind and the old
  exported symbols remain as deprecated aliases resolving to the same objects;
  direct imports of `src/verifiers/testsuite*.mjs` (never a supported path) break.

New stable export: `createSqliteReplayStore`.

## Stable Exports

Stable exports are intended for application and adapter authors:

- settlement: `settle`, `verifyReceipt`, `assertReceiptMeetsPolicy`
- milestone helpers: `compileMilestoneContracts`, `settleMilestones`, `verifyMilestoneAggregate`
- verifier routing: `routeVerifier`, `deriveComposeProfile`, `VERIFIER_PROFILES`, `ASSURANCE_NAMES`
- verifier registry and built-ins: `verifiers`, `getVerifier`, and the named verifier objects
- partial dataset sampling: `selectSampleIndices`, `verifyInclusionSample`,
  and `datasetMerkleSampleVerifier`
- protocol utilities: canonical hashing, Ethereum Keccak-256 helper, signing, key ids, schema validators, Merkle helpers
- rail adapters: `createDurableEscrowRail`, `createMockEscrowRail`
- replay stores: `createNonceRegistry`, `createWalReplayStore`, `createSqliteReplayStore`
- interop projections: ERC-8004 and ERC-8183 helpers, including opt-in ABI-shaped argument encoding
- typed public errors: `DeliveryProofError` and subclasses
- operability helpers: audit sink normalization, config validation, local
  healthcheck, and explicit graceful shutdown

Stable means a compatible v0.x patch should not remove or silently change the
function signature. The underlying wire profile remains `deliveryproof/0.4-jcs1`
until SPEC says otherwise.

## Experimental Or Reference Exports

These exports are available from the package root but carry explicit caveats:

- `createMockEscrowRail` and `createDurableEscrowRail` are reference/example rails,
  not production payment rails. Their optional receipt-signature check is a
  defense-in-depth local guard, not a substitute for a real rail adapter.
- `paidToolWithDeliveryProof` is a local MCP wrapper helper, not a hosted service.
- `TIER_B_INTERFACE_DESCRIPTORS` and `getTierBInterface` describe non-runnable
  provenance interfaces unless the descriptor says `implemented: true`.
- `runBuiltinReplay` is exported for deterministic local replay and test
  harnesses; it is not a general-purpose JavaScript sandbox. The old
  `runTestsuiteReplay` name remains as a deprecated alias.
- Audit hooks and healthcheck helpers are local library integration points. They
  do not imply a hosted DeliveryProof service or production payment rail.
- `dataset-merkle-sample` proves inclusion plus sampled-row conformance only.
  It is not a substitute for the full dataset verifier when global row count,
  uniqueness, aggregates, or whole-dataset truth are required.

## Not Public

Direct imports from `src/*` are unsupported by package exports. Consumers that
need a missing symbol should ask for it to be promoted to `src/index.mjs` with
documentation and tests.

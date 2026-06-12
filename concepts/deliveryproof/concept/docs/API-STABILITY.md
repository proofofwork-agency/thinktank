# DeliveryProof API Stability

DeliveryProof v0.9 exposes one supported package entry point:

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
- `runTestsuiteReplay` is exported for deterministic local replay and test
  harnesses; it is not a general-purpose JavaScript sandbox.
- Audit hooks and healthcheck helpers are local library integration points. They
  do not imply a hosted DeliveryProof service or production payment rail.
- `dataset-merkle-sample` proves inclusion plus sampled-row conformance only.
  It is not a substitute for the full dataset verifier when global row count,
  uniqueness, aggregates, or whole-dataset truth are required.

## Not Public

Direct imports from `src/*` are unsupported by package exports. Consumers that
need a missing symbol should ask for it to be promoted to `src/index.mjs` with
documentation and tests.

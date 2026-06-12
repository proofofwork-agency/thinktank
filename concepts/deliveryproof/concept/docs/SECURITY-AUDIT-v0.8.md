# DeliveryProof v0.8 Security Audit Pass

Date: 2026-06-01
Scope: local OSS library at commit line `ef9f484 -> 8383565` plus the follow-up
security-hardening patch. This review did not push, publish, deploy, or touch any
real payment rail.

## Executive Summary

The review found no code path where a failing verifier verdict captures the mock
or durable rail hold. That core invariant remains intact.

The audit did find several hardening gaps that matter before anyone treats the
library as production-grade:

- partial Merkle mode allowed `k=0` for non-empty datasets, which could make an
  empty proof pass;
- rails terminalized receipts by decision without re-checking that the receipt was
  bound to the exact hold, rail, amount, currency, contract id, and contract hash;
- settlement accepted mismatched public/private settlement keys until after a hold
  could be authorized;
- `verifyReceipt` trusted the supplied public key cryptographically but did not
  also require `signerKeyId` to match that public key;
- `routeDecision` could be signed into the receipt while a different injected
  verifier actually ran;
- `contract.railId` could name a different rail than the injected adapter, which
  could authorize a hold and fail later at terminalization;
- nonce-registry keys used delimiter-joined strings instead of a canonical hash;
- JSON dataset verification was bounded by row count but not tightly enough by row
  shape, primitive cell type, non-finite numbers, and oversized spec arrays;
- document verification bounded the delivered Markdown but not all buyer-supplied
  document spec arrays and text fields;
- docs over-described the durable rail unless they explicitly said it is not an
  fsync-level power-loss durability claim.

All items above were fixed or documented in the hardening patch, with regression
tests added.

A final non-breaking hardening batch added defense-in-depth for the trust-boundary
items that should not become breaking API requirements:

- `verifyReceipt` now rejects even correctly signed receipts when the signed
  `decision` contradicts the signed `verdict.ok`;
- `assertReceiptMeetsPolicy` lets production integrations require a signed route
  decision, disallow fallback, pin rail/verifier identity, and require nonce
  registry evidence without forcing those policies on lower-level library users;
- partial Merkle mode mirrors full-dataset row/cell bounds before hashing sampled
  rows or proof leaves;
- canonicalization has default depth, node, string, and object-key caps;
- the MCP wrapper defaults to an in-memory replay registry and offers
  `strictRouting` for production wedges that require signed routing evidence.
- reference rails can optionally verify receipt signatures when configured with
  `settlementPublicKey`, closing the direct-rail forged-receipt footgun for local
  deployments that expose rail methods.

## Black-Hat Lens

Attacks considered:

- Try to get paid with a failing verdict: still blocked by engine decision
  derivation, capture guard, and rail decision checks.
- Replay a release receipt onto another hold: now blocked by receipt/hold binding
  checks in both reference rails.
- Present row A in a Merkle proof but conformance-check row B: blocked by the
  partial Merkle leaf/row binding test.
- Provide no sampled rows in partial mode: now rejected for non-empty datasets.
- Poison replay keys with delimiter collisions: nonce keys are now canonical
  SHA-256 commitments.
- Stranding a hold with a bad settlement key or non-canonical contract extra:
  settlement now self-tests keys and precomputes the contract hash before
  authorization.
- Mismatch the signed router decision and the actual verifier: now rejected before
  authorization.
- Wire a contract to a different rail adapter than its `railId`: now rejected
  before authorization.
- Push unbounded JSON row shapes through dataset hashing/scanning: now rejected
  before dataset hash and row scanning.
- Push huge document predicate arrays through repeated structural scans: now
  rejected by document-spec caps.
- Push oversized partial Merkle row/proof-leaf cells through pre-hash
  canonicalization: now rejected before leaf hashing.
- Sign a receipt where `decision` says release but `verdict.ok` says false: now
  rejected by `verifyReceipt`.
- Call a reference rail directly with a forged unsigned receipt: now rejected when
  the rail is configured with `settlementPublicKey`.

## White-Hat Lens

Properties that held through the audit:

- `decision = verdict.ok ? 'release' : 'refund'` is still the only settlement
  decision source.
- The capture branch still refuses capture unless `verdict.ok === true`.
- Audit events remain best-effort and are not included in signed receipt bytes.
- Partial Merkle mode remains honest: it proves inclusion plus sampled-row
  conformance only, not whole-dataset truth.
- Router non-bypassability for `compose`, `signed-oracle`, and
  `dataset-merkle-sample` remains pinned by tests.
- The dependency policy in that v0.8 slice remained unchanged.

## Grey-Hat / Product Lens

DeliveryProof is still best understood as a library and proof layer, not a
complete payment processor. A real product still needs:

- a production non-custodial rail adapter;
- persistent replay/idempotency storage or equivalent rail idempotency;
- production key management, backup, monitoring, and incident response;
- an attested Tier-B verifier when the claim depends on external-world truth;
- legal/compliance review before handling real commercial disputes.

Competitively, the useful wedge remains narrow but real: rails such as x402,
Stripe-style payment intents, AP2-style mandates, and escrow products can decide
whether payment is authorized or held. DeliveryProof decides whether the delivered
artifact satisfied an objective predicate, then emits a signed receipt that a rail
can use.

## Verification

Local gates after fixes:

- `npm test`: final count recorded in the latest local gate
- `npm run demo`: 6 demos passing
- `npm run check`: full-tree `node --check` passing
- `git diff --check`: passing
- `npm pack --dry-run`: package dry-run passing

## Residual Risk

No audit can make the claim "absolutely no security risks." The honest claim is:
the known code-level issues found in this pass were fixed or documented, and the
current local gates pass. Remaining risk is mostly integration and operations:
production rails, key custody, replay persistence, WAL integrity and filesystem
permissions for the durable local rail, monitoring, external attestations, and
legal/payment compliance.

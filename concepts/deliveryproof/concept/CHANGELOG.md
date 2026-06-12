# Changelog

All notable local changes are summarized here. The project has not been publicly
published; commit hashes identify the local development slices.

## v0.9.1 - Dual-agent review hardening (local, unpublished)

A dual independent code review (Claude + Codex, coordinated via ContextRelay)
confirmed the central `settle()` invariant — no capture when `verdict.ok !== true`
— holds, and closed several exported, money-moving surfaces that failed open by
default. Suite went 251 -> 260, all green.

- Rewrote `protocol/canonical.mjs` to emit RFC 8785 / JCS text directly from the
  code-unit-sorted key list instead of round-tripping through a JS object. The
  round-trip reordered integer-like keys (`"2"` before `"10"`), breaking
  cross-implementation hash/signature/Merkle reproducibility; the
  `CANONICALIZATION = 'RFC8785-JCS'` claim is now actually true. String-keyed
  records and arrays are byte-identical to before, so the wire profile stays
  `deliveryproof/0.4-jcs1`, and only objects containing integer-like keys change
  bytes — named-field records like contracts and receipts are unaffected (the full
  suite, including signed-receipt verification, stays green at 260/260).
- Reference rails (`escrow-mock`, `durable-rail`) now reject a receipt whose
  `decision` contradicts its `verdict.ok` before any terminalization, and added
  opt-in `requireSignature: true` to make settlement-signature verification
  mandatory (and to require a key at construction).
- Interop projection (`erc8004`, `erc8183`) refuses to project an internally
  contradictory receipt into a chain-facing `complete`/`release`/`100` result.
- `engine/nonce-registry.mjs` WAL replay validates record fields and rejects a
  lone or forged `mark` (mark-before-reserve or fingerprint mismatch).
- Standalone `schema` and `api-response` verifiers reject non-finite
  (`Infinity`/`NaN`) numbers; contract and receipt amounts must be positive and
  finite.
- Added `test/hardening.test.mjs` (9 regression tests) and a new rail-conformance
  case `no-capture-on-contradictory-verdict`.
- Updated the whitepaper to ground the design in the fair-exchange impossibility
  result (Pagnia-Gärtner 1999; Even-Goldreich-Lempel 1985), engage FairSwap /
  OptiSwap as on-chain precedent, and frame novelty as execution/positioning.
- Deferred: `keyId` widening (DER-based, 128-bit) and mandatory-by-default
  rail/interop signature verification; `requireSignature` ships the latter as
  opt-in.

## v0.9.0 - Integration seams and Ethereum keccak interop (local, unpublished)

- Added rail conformance coverage for rail adapters, including safety cases for
  receipt/hold binding, terminal decision conflicts, idempotent same-receipt
  recapture, and refund/capture direction.
- Added replay-store seams for `createNonceRegistry({ store })`, exported the
  default `createWalReplayStore({ logPath, fsync })`, and added a replay-store
  conformance suite for companion durable stores.
- Added verify-only keyring support for `verifyReceipt(receipt, { keys })` and
  `verifyReceipt(receipt, { keyring })` while preserving the PEM-string behavior
  and leaving `settle()` signing unchanged.
- Added signer and keyring interface descriptors plus `createInMemoryKeyring()` as
  a small public-key lookup helper.
- Added a production config profile. Missing nonce registry is a hard error;
  missing audit sink, tmpfs-like WAL paths, and undeclared rail receipt-signature
  verification are warnings.
- Added `buildAuditBundle()` for local dispute inspection. It collates existing
  receipt, contract, evidence, and optional rail-status hashes and checks; it does
  not create a new proof, contact telemetry, or alter settlement.
- Added documentation for full dataset verification versus partial Merkle sample
  verification, production integration wiring, companion package boundaries, and
  human-decision escalations.
- Added the first runtime dependency, exactly pinned as `@noble/hashes@2.2.0`,
  for Ethereum Keccak-256 helpers. Added `keccak256()` with tests proving Node's
  `sha3-256` differs from Ethereum Keccak-256.
- Added opt-in `hashAlg: 'keccak256'` mode for ERC-8004 and ERC-8183 projection
  helpers, plus ABI-shaped argument encoding. SHA-256 remains the default for
  backward compatibility.
- Replaced the dependency policy and CI gate with an allowlist that permits only
  `@noble/hashes@2.2.0`, rejects transitive packages, and uses `npm ci` with a
  committed lockfile.

## v0.8.0 - Partial Merkle verifier mode (local, unpublished)

- Added bounded deterministic partial-sample index selection for dataset Merkle
  roots. The seed binds the contract nonce, committed root, row count, sample
  count, and a domain string; work is bounded by the committed sample size, not by
  full dataset size.
- Added the `dataset-merkle-sample` verifier. It checks verifier-selected Merkle
  proofs and row-level column constraints without requiring the full dataset.
- Made partial mode explicit-only in the router so a generic `dataset`
  high-assurance policy cannot silently downgrade to inclusion-only sampling.
- Exported `selectSampleIndices`, `verifyInclusionSample`, and
  `datasetMerkleSampleVerifier` from the package root.
- Added `examples/demo-merkle-partial.mjs`, showing one valid sample releasing
  payment and leaf-swap/cherry-pick attempts refunding.
- Updated README/SPEC to mark partial Merkle sample mode as supported and to keep
  its scope honest: it proves inclusion plus sampled-row conformance only, not
  full-dataset row count, uniqueness, aggregates, dataset hash, or whole-table
  truth.
- Deferred EVM-native keccak256/ABI profiles and real rail adapters at this slice;
  v0.9 later added projection-only Keccak/ABI helpers after explicit human
  approval.

## v0.7.0 - Production-readiness hardening (local, unpublished)

- Added a production-readiness scorecard and explicit scope boundary for the OSS
  objective-verification library.
- Hardened runtime validation with prototype-pollution guards for canonical JSON,
  schema paths, verifier inputs, and WAL record shapes.
- Added narrow production error classes for configuration and validation failures.
- Added injectable clock handling while preserving default `Date.now()` behavior
  and signed receipt bytes for existing callers.
- Added resource-bound regressions for JSON datasets and API-response predicates.
  JSON datasets without `rowCount.max` remain backward compatible through a
  built-in default cap; this is a hardening change, not a breaking contract
  requirement.
- Packaged a root public API barrel with stable versus experimental/reference
  export labels and Node `>=22` metadata.
- Added optional boundary audit hooks and operability helpers. Audit sink failures
  are best-effort and never affect settlement.
- Extended the durable local rail with flush, close, health, and closed-state
  write guards.
- Added production documentation: security policy, contribution guide, API
  reference, threat model, and production-readiness caveats.
- Added read-only CI for Node 22/24, dependency-policy enforcement, full-tree syntax
  checks, whitespace checks, and package dry-run verification.
- Added supply-chain/release-integrity documentation and finalized the v0.7
  production-readiness scorecard.

## v0.6 - Dataset proof depth and parser completion (local, unpublished)

- Added byte-tagged SHA-256 Merkle helpers for dataset row commitments:
  `0x00 || canonicalize(row)` leaves, `0x01 || left || right` nodes, and `0x02`
  empty root.
- Wired dataset `merkleRoot` predicates into the verifier and emitted
  downstream-verifiable inclusion proofs for verifier-seeded sampled rows.
- Added bounded RFC-4180 CSV parsing with quoted fields, embedded commas/newlines,
  escaped quotes, and fail-closed malformed-quote handling.
- Documented that v0.6 Merkle mode is full-root mode only; partial verifier mode is
  deferred.

## v0.5 - Deep correctness core (local, unpublished)

- Bound milestone aggregate verification to the schedule in an explicit strong
  mode, preventing truncation, reordering, and child substitution when callers
  provide `{ schedule }`.
- Added dataset regex constraints, `avg`, and `count` aggregate invariants with
  bounded regex-source and cell-input guardrails.
- Added the objective structured-document verifier with bounded Markdown parsing,
  frontmatter/headings/terms/links/tables/code-block/checksum checks, and no
  semantic grading.
- Added documentation sync and fixed a signed-oracle test tamper flake.

## v0.4 - Protocol hardening and milestone rollup (local, unpublished)

- Added protocol-versioned canonical wire objects and schema validation.
- Added lifecycle trace signing, nonce replay prevention, and durable local rail
  recovery/idempotency.
- Added API-response, compose, Tier-B signed-oracle, MCP wrapper, and ERC-8004 /
  ERC-8183 interop helpers.
- Added milestone settlement composition and signed aggregate verification.

## Earlier proof-of-concept baseline

- Implemented the core DeliveryContract, DeliveryEvidence, DeliveryReceipt,
  settlement engine, mock rail, router, and initial Tier-A verifiers.
- Added runnable money-shot demos showing shallow verifiers release while deep
  objective verifiers refund on the same incorrect deliverable bytes.

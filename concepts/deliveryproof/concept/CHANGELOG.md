# Changelog

All notable local changes are summarized here. The project has not been publicly
published; commit hashes identify the local development slices.

## v0.10 - Fail closed by default (local, unpublished)

**Breaking.** Two independent adversarial passes (Claude + Codex), each with a
working proof-of-concept, showed that the two headline safety claims held inside
`settle()` but were not enforced at the boundaries. Both are now enforced.
Suite went 260 -> 310, all green.

- **Rails require a settlement key.** `createMockEscrowRail`,
  `createDurableEscrowRail`, and `createErc8183Rail` now throw at construction
  without `settlementPublicKey`, and verify the receipt signature on every
  terminalization. Previously a rail built without a key verified *nothing*: a
  receipt with `verdict.ok: true`, `decision: 'release'` and the correct binding
  fields captured a hold with no settlement private key involved. Both review
  passes reproduced this independently.
  - Opt out with `allowUnsignedReceipts: true` (demos/fixtures only). Every
    terminalization on that path emits a `rail.unsigned.accepted` audit event.
  - `requireSignature` is retained as a no-op alias: verification is the default.
  - No deprecation window. This is pre-1.0, and a deprecation window on a
    money-safety default only extends the period where the unsafe default ships.
- **The engine no longer signs assurance claims it cannot verify.** `settle()`
  previously checked only that `routeDecision.selected` matched the verifier's
  name, then signed the caller's own `selectedAssurance` — and
  `assertReceiptMeetsPolicy()` trusted that signed number. An assurance-1
  `schema` verifier therefore satisfied a `minAssurance: 3` policy with a
  hand-written `selectedAssurance: 99`. The engine now re-derives assurance from
  the trusted profile table and refuses to sign a mismatch. Tamper-*evident* was
  never the same as *checked*.
  - The trusted table moved to `src/router/profiles.mjs`, a leaf module, so the
    engine can re-derive without depending on the router. `VERIFIER_PROFILES`,
    `ASSURANCE_NAMES`, and `deriveComposeProfile` are re-exported unchanged.
  - `assertReceiptMeetsPolicy` gains `expectedPolicyHash`, and a receipt with no
    `routeDecision` now *fails* an assurance floor instead of silently passing it.
- **`createSqliteReplayStore`** (new): a replay store whose uniqueness is a
  SQLite `PRIMARY KEY`, so concurrent reservations are rejected across
  processes. The bundled WAL store holds its uniqueness check in an in-process
  Map, so two processes sharing one log both reserve the same nonce — asserted
  deterministically in `test/sqlite-replay-store.test.mjs`. Uses `node:sqlite`
  (Node 22+); the single-runtime-dependency guarantee is unchanged.
- **Post-authorize liveness:** `settle()` now races `produceEvidence` against the
  SLA deadline. Previously the deadline only *aborted a signal*, so a producer
  that ignored its `AbortSignal` left `settle()` pending forever with the buyer's
  funds held. An unresponsive seller is now a failed delivery -> refund.
### Second review round — the fixes were themselves attacked

The v0.10 changes above were then adversarially re-reviewed, which found five
further breaks. Four were in the new code; all are closed, each with a
regression test derived from its proof-of-concept.

- **A producer could rewrite the contract it was handed.** `normalizedContract`
  was a shallow copy, and the *same mutable object* went to `rail.authorize()`,
  then to seller-controlled `produceEvidence()`, then to `verifier.verify()`. A
  seller mutated the predicate mid-flight (`sum([100])` -> `sum([1,2])`),
  returned the weakened answer, and the real verifier passed it — while
  `contractHash` still committed to the original terms. The receipt attested to
  terms nobody verified. Now deep-cloned and recursively frozen before use, so a
  mutation attempt throws and refunds. **This was the most serious defect found
  in either round**, and it predates v0.10.
- **A custom verifier could inherit a built-in's assurance by reusing its name.**
  Profiles are keyed by name, so an object called `dataset` that checked nothing
  got `dataset`'s assurance signed into a receipt. The engine now requires object
  identity with the built-in registry entry before signing a protocol assurance.
  Custom verifiers still run; they cannot wear a number they did not earn.
- **A `routeDecision` getter could show one assurance to validation and another
  to downstream readers**, because validation follows getters and the prototype
  chain while canonicalization signs own data properties only. The decision is
  now normalized to plain own data before validating, and that same object is
  signed — validated bytes are the signed bytes.
- **`createdAt: 0` silently disabled SLA enforcement entirely.** Both deadline
  helpers bailed on `createdAt <= 0`, but epoch 0 is schema-valid, so a
  never-resolving producer held funds forever — the liveness fix above did not
  apply. Now only negative or non-finite `createdAt` disables the deadline.
- **Prototype pollution could disable rail signature verification** — and worse,
  inject an attacker-held `settlementPublicKey` so a rail verified against the
  *wrong* key. All three rails now read options from a null-prototype
  own-property copy.

(Superseded in the third round below: the regression and flip transitions were
closed after all, by making transitions monotonic and extending the conformance
suite rather than leaving the interface as found.)

### Third review round — the round-2 fixes were themselves attacked

Same discipline again: the fixes above were adversarially reviewed, which found
six more issues. Suite 288 -> 310.

- **The verifier identity check compared against mutable state.** Granting
  assurance on `builtInVerifiers[selected] === verifier` is worthless if the
  registry entry can be replaced (`verifiers.dataset = impostor`) or the object
  rewritten (`datasetVerifier.verify = evil`). Worse, `verify` was resolved
  *after* the producer ran, so a seller passed the identity check with the real
  verifier and then rewrote its method from inside its own `produceEvidence`.
  Observed: signed assurance-3 receipt, valid signature, escrow captured. Now the
  registry and every built-in verifier are frozen, and `settle()` binds the
  verify callable before any seller code runs — which protects custom verifiers
  too, rather than relying on anyone remembering to freeze.
- **`VERIFIER_PROFILES` rows were mutable.** A frozen table with mutable rows is
  not a trusted table: `VERIFIER_PROFILES.schema.assurance = 3` would have made
  the engine re-derive and then *sign* assurance 3 for the shallow foil. Table,
  rows, and `kinds` arrays are now frozen.
- **A non-canonicalizable `routeDecision` stranded a held escrow.**
  `structuredClone` preserves values JCS rejects (Map, Date, BigInt, Infinity,
  cycles). Validation passed, the rail authorized a hold, the seller delivered,
  and canonicalization then threw during receipt signing — outside the delivery
  try/catch. Result: funds held with no receipt, no capture, no refund. The
  decision is now proved canonicalizable before anything is authorized.
- **Prototype pollution defeated the downstream policy checks.** A receipt whose
  *signed* `routeDecision` was `{}` — carrying no assurance claim at all — passed
  `minAssurance: 99` and an `expectedPolicyHash` pin, because policy read through
  the prototype chain while canonicalization signs own properties only. All
  policy reads are now own-property.
- **A custom verifier could still sign `selectedAssuranceName`.** The numeric
  claim was guarded; the prose one was not.
- **Compat regression from the rename, caught and fixed:** a legacy route
  selecting `testsuite` was rejected because the aliased object's own name is
  `builtin-replay`. Name equality now falls back to registry identity.

Confirmed solid under attack: the contract deep-freeze (sloppy assignment
no-ops, `Reflect.set` returns false, `defineProperty` and array mutation throw;
exotic inputs fail before authorization), and the getter/prototype divergence fix
on `routeDecision` (getters materialize exactly once; validated own canonical
data is byte-identical to the signed data).

Also in this round: replay-key transitions are now monotonic across BOTH stores
and the WAL replay path — a reservation cannot be born settled, a terminal cannot
regress to `reserved` (which would free a spent nonce), and terminals cannot
flip. Four cases added to the exported replay-store conformance suite. The
residual risk is stated plainly in `replay-transitions.mjs`: `mark()` still
cannot authenticate its caller, so whoever knows a key can drive the first
`reserved -> terminal` transition. Closing that needs a token the interface has
no room for.

- **`testsuite` verifier renamed to `builtin-replay`.** It supports four
  deterministic ops (`sort`, `sum`, `unique`, `reverse`); recomputing those is
  genuinely deep for the predicates they cover, so assurance stays 3 — the defect
  was a name implying generality it never had. `testsuite` remains a deprecated
  alias resolving to the same verifier and profile object.

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

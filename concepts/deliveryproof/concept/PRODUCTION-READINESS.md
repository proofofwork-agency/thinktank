# DeliveryProof Library Hardening Scorecard

Status: v0.7 hardening scorecard with v0.8 and security-audit addenda.

This document defines the bounded OSS-library hardening target for DeliveryProof.
It is not a claim that the project is ready to custody funds, operate a hosted
SaaS, or move real money through any external payment rail.

## Claim Boundary

The v0.7 target was:

> DeliveryProof clears a 90/100 library-hardening score as an open-source
> objective-verification library and protocol reference implementation.

That includes the protocol records, canonicalization and signing, deterministic verifiers, settlement engine, interop projection helpers, and reference rail interfaces.

That does not mean:

- Ready to custody money.
- Ready to operate a hosted SaaS.
- Ready to move real funds through Stripe, x402, AP2, bank rails, or any other external payment rail.
- Ready to replace operator security review, legal review, tax advice, or a third-party cryptographic audit.

Any real-money deployment still needs, at minimum:

- A real non-custodial production rail adapter.
- An attested Tier-B verifier when the use case needs external provenance beyond Tier-A objective checks.
- Operator threat modeling, key-management review, infrastructure hardening, monitoring, and incident response.

The in-repo mock rail is a reference state machine only. It is not a production settlement guarantee.

## Locked Rubric

Each dimension is scored from 0 to 100. The final score is the weighted sum.
DeliveryProof may claim a `>=90/100` library-hardening score only if the weighted
score is at least 90 and the residual-risk section stays honest.

| Dimension | Weight | What Counts |
| --- | ---: | --- |
| Correctness and tests | 18 | Deterministic tests, edge cases, public API behavior, money-safety invariant, receipt verification, verifier regression coverage. |
| Security and threat model | 18 | Input validation, prototype-pollution resistance, ReDoS/resource guardrails, cryptography via `node:crypto`, no fake crypto claims, no secrets in repo. |
| Reliability, resource bounds, and recovery | 14 | No unhandled settlement paths, bounded parsing/replay, idempotency, WAL recovery/fail-closed behavior, deterministic clocks where needed. |
| API and packaging | 12 | Clean public API barrel, package exports, Node engine declaration, semver version, files whitelist, JSDoc types, reproducible install/test path. |
| Supply-chain and release integrity | 8 | Small dependency surface, no generated opaque build step, committed lockfile when dependencies exist, signed-tag guidance before publishing. |
| Observability and auditability | 8 | Optional built-in audit/log sink at engine/router/rail boundaries, structured events for decisions and rail transitions, receipt/audit trace usability. |
| Operability | 7 | Config validation, graceful durable-rail flush/close behavior, health/status helper, runbook clarity without implying hosted SaaS. |
| Docs and runbooks | 10 | README/SPEC accuracy, `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, API reference, threat model, production caveats. |
| CI and quality gates | 5 | GitHub Actions with `node --test`, syntax checks, whitespace checks, no publish step, documented local gates. |

Total: 100.

## Baseline Score

Baseline reference: v0.6 local commit `59f3622` (`Sync v0.6 docs`).

Current local state when this document was added: `0632fca` (`Harden runtime validation and clocks`) is already on top of v0.6. That hardening commit begins closing the P1 items, but the baseline below intentionally scores the v0.6 state that existed before v0.7 production hardening began.

Fresh re-baseline on current HEAD before writing this file:

- `node --test`: 176/176 pass.
- Working tree: clean.
- `package.json`: still minimal (`version: 0.0.1`, no exports, no engines, no files whitelist, no `check` script).
- Missing production docs at baseline: `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/API.md`, `docs/THREAT-MODEL.md`.
- Missing CI at baseline: no `.github/workflows` directory.

Approximate baseline score: 70/100.

| Dimension | Weight | Baseline Score | Weighted Points | Evidence |
| --- | ---: | ---: | ---: | --- |
| Correctness and tests | 18 | 88 | 15.84 | v0.6 had 166 deterministic tests, five demos, signed receipt and verifier coverage, and critical no-capture tests. |
| Security and threat model | 18 | 78 | 14.04 | Strong JCS, signed receipts, bounded CSV/document/testsuite paths, mock/Tier-B caveats; remaining audit work around prototype-pollution keys, WAL shapes, and public-entry validation. |
| Reliability, resource bounds, and recovery | 14 | 76 | 10.64 | Durable rail/idempotency/WAL recovery and nonce registry exist; clock injection and broader resource regression evidence still incomplete at baseline. |
| API and packaging | 12 | 35 | 4.20 | Minimal package metadata, no exports map, no public `src/index.mjs`, no engine declaration, no files whitelist. |
| Supply-chain and release integrity | 8 | 70 | 5.60 | The source-only repo had a small supply-chain surface; no release integrity statement, signed-tag guidance, or CI-backed checks. |
| Observability and auditability | 8 | 45 | 3.60 | Receipts and lifecycle traces are signed/auditable, but no explicit audit sink/logger interface. |
| Operability | 7 | 45 | 3.15 | Durable rail has recovery/compact patterns; no health/status helper, graceful close/flush API, or runbook. |
| Docs and runbooks | 10 | 65 | 6.50 | README/SPEC are unusually detailed and honest, but missing production docs and API reference. |
| CI and quality gates | 5 | 0 | 0.00 | No workflow yet. |

Weighted baseline: 63.57/100 from strict arithmetic. The prior "about 70/100" estimate remains a useful qualitative shorthand, but the final v0.7 claim must use the weighted math above and the updated final score.

## Locked v0.7 Slice Plan

The remaining work is serialized and locally committed slice by slice. Each slice must pass local gates before the next one starts.

Local gates:

- `node --test`
- all five demos exit 0
- `node --check` over `src`, `test`, `examples`, and supporting scripts
- `git diff --check`

### P1a: Security Validation and Prototype-Pollution Audit

Scope:

- Canonical JSON object handling.
- Schema validators and public validation helpers.
- Dataset, document, and API-response verifier input paths.
- WAL `JSON.parse` paths.
- Object merge/copy surfaces.
- Public-entry validation behavior.

Required evidence:

- Tests for `__proto__`, `constructor`, and `prototype` keys where parsed data is later merged or stored.
- Tests for malformed WAL shapes.
- Tests for public-entry validation behavior.
- Behavior remains stable for existing valid callers.

### P1b: Resource and Performance Bounds

Scope:

- Confirm every untrusted parser or loop is capped.
- Add regression tests for oversized CSV, document, dataset, Merkle, testsuite, and API-response inputs.
- Add deterministic perf/resource smoke tests only when non-flaky; otherwise document manual benchmark commands.

### P2: API and Packaging

Scope:

- `package.json` version `0.7.0`.
- `exports`, `engines.node >=22`, `files`, `scripts.test`, `scripts.check`, and `scripts.demo`.
- `src/index.mjs` public API barrel exporting only the hardened stable surface.
- JSDoc public types and API stability documentation.
- Keep the dependency surface explicitly reviewed and bounded.

### P3: Observability and Operability

Scope:

- Optional built-in audit sink at engine/router/rail boundaries.
- Config validation helper.
- Durable rail close/flush/graceful-shutdown behavior.
- Health/status helper that does not imply hosted SaaS.

### P4: Docs

Scope:

- `SECURITY.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `docs/API.md`
- `docs/THREAT-MODEL.md`
- README/SPEC library-hardening section.
- Loud mock-rail and Tier-B caveats.
- SPEC status updated to v0.7 without changing the wire profile unless a later slice explicitly does so.

### P5: CI and Supply-Chain Statement

Scope:

- `.github/workflows/ci.yml`.
- Node 22, and Node 24 if available in Actions.
- `node --test`.
- `node --check` over `src`, `test`, `examples`, and supporting scripts.
- `git diff --check`.
- No publish step.
- Supply-chain note: explicit dependency policy, reproducible source release, signed tags recommended when publishing.

### P6: Final Scorecard and Email

Scope:

- Rerun all local gates.
- Update this document with final weighted score and evidence.
- Include a residual-risk section.
- Claim `>=90/100 library-hardening score` only if weighted math clears the threshold.
- Email `bbnillo@gmail.com` only after final verification succeeds.
- No public push.

## Final v0.7 Score

Final local reference: this P6 scorecard commit, on top of `9e132cc`.

Final local gate before this score:

- `npm test`: 183/183 pass.
- all five demos exit 0.
- `npm run check`: syntax-checks every `.mjs` file under `src`, `test`, `examples`, and supporting scripts.
- `git diff --check`: pass.
- `npm pack --dry-run`: pass; package contents are source, docs, license, and metadata only.
- Dependency check: no runtime, development, peer, or optional dependencies; no lockfile.

Weighted final library-hardening score: **91.16/100**.

This clears the `>=90/100` threshold for the explicit OSS-library scope above. It
does **not** mean "ready to move real money" and does not change the out-of-scope
list below.

| Dimension | Weight | Final Score | Weighted Points | Evidence |
| --- | ---: | ---: | ---: | --- |
| Correctness and tests | 18 | 94 | 16.92 | 183 deterministic `node:test` cases, five runnable demos, critical no-capture-on-failed-verdict tests, receipt tamper tests, router no-downgrade tests, verifier money-shot regressions, package self-reference test. Not 100 because there is no coverage metric or external conformance suite. |
| Security and threat model | 18 | 92 | 16.56 | Prototype-pollution guards, public validation helpers, bounded CSV/document/dataset/API-response/testsuite surfaces, node:crypto only, no fake Tier-B crypto, `SECURITY.md`, and `docs/THREAT-MODEL.md`. Not 100 because there is no third-party audit, formal safe-regex proof, or hostile-code sandbox. |
| Reliability, resource bounds, and recovery | 14 | 91 | 12.74 | Settlement exceptions after authorization become refund verdicts, durable local rail has WAL recovery/idempotent terminal operations/closed-state guards/flush/close/health, injectable clocks remove wall-clock flakes, JSON datasets and Merkle builds are bounded. Not 100 because real external rail failure modes remain adapter-specific. |
| API and packaging | 12 | 90 | 10.80 | `package.json` version `0.7.0`, root export map, Node `>=22`, files whitelist, stable `src/index.mjs` barrel, API stability doc, API reference, and simple npm scripts. Not 100 because there are no generated `.d.ts` files and subpath imports remain intentionally unsupported. |
| Supply-chain and release integrity | 8 | 88 | 7.04 | At the v0.7 checkpoint the package had a minimal source package, no build or generated opaque artifacts, `npm pack --dry-run` gate, read-only CI, and supply-chain policy with signed-tag guidance. v0.9 adds one pinned runtime dependency and a committed lockfile. Not 100 because no public signed tag, npm provenance, SLSA attestation, or third-party audit exists yet. |
| Observability and auditability | 8 | 88 | 7.04 | Optional best-effort audit sink at engine/router/rail boundaries, audit failures cannot affect settlement, audit fields do not enter signed receipt bytes, lifecycle/route decisions remain signed for auditability. Not 100 because there is no hosted telemetry, metrics backend, or tracing integration. |
| Operability | 7 | 88 | 6.16 | Config validation helpers, local healthcheck, durable-rail flush/close/graceful shutdown, API docs and runbook-style security/contribution guidance. Not 100 because production deployment runbooks, monitoring, backups, and incident response are operator work outside the library. |
| Docs and runbooks | 10 | 94 | 9.40 | README/SPEC updated to v0.7, `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/API.md`, `docs/API-STABILITY.md`, `docs/THREAT-MODEL.md`, `docs/SUPPLY-CHAIN.md`, and loud mock-rail/Tier-B/non-custodial caveats. Not 100 because no generated reference site or third-party deployment guide exists. |
| CI and quality gates | 5 | 90 | 4.50 | GitHub Actions matrix for Node 22.x and 24.x, dependency allowlist/lockfile guard, `npm test`, full-tree `npm run check`, `git diff --check`, `npm pack --dry-run`, read-only permissions, no publish step. Not 100 because remote CI execution has not been observed here and there is no coverage/performance dashboard. |

## Final Residual Risks

- The mock rail is not production money movement, escrow-of-record, or a money transmitter.
- The durable rail proves local WAL/idempotency behavior only; real payment rails need production adapters and rail-specific failure handling.
- Operators still need key-management policy, key rotation, monitoring, backups, incident response, and security review.
- Tier-B interface descriptors remain interface-only except the signed-oracle example; use cases needing external-world provenance need a real attested proof system.
- Regex and parser guardrails are pragmatic built-in CWE-400 mitigations, not formal safe-regex or arbitrary-input security proofs.
- The testsuite verifier is bounded deterministic replay, not an OS sandbox for hostile seller code.
- Projection-only Keccak/ABI helpers exist in v0.9; live on-chain adapters remain outside this library.
- Partial-verifier Merkle mode remains deferred; v0.7 preserves full-root mode only.
- Public push, npm publish, signed tags, and package provenance remain gated on explicit human approval.

## v0.8 Addendum

v0.8 adds partial Merkle sample mode on top of the v0.7 production-hardening
baseline. This is a feature addition, not a new custody or hosted-service claim.

Supported in v0.8:

- `dataset-merkle-sample` verifies committed sampled rows without receiving the
  full dataset.
- Sample selection is deterministic, bounded by `k`, and bound to nonce, root,
  row count, and sample count.
- Proof verification binds the supplied row to the committed Merkle leaf before
  row-level conformance checks run.
- Router selection is explicit-only so generic `dataset` high-assurance policies
  keep using the full dataset verifier.

The v0.7 library-hardening score of 91.16/100 remains scoped to the OSS
objective-verification library and reference implementation. v0.8 does not change the out-of-scope
boundary: a real deployment still needs a production non-custodial rail adapter,
operator key/security review, and any required attested Tier-B verifier.

Partial Merkle mode does **not** prove global row count truth, uniqueness,
aggregates, dataset hash, or whole-dataset correctness. Use the full dataset
verifier for those properties.

Still deferred after v0.8:

- Live EVM contract adapters, wallet control, provider/RPC wiring, and on-chain submission.
- Real x402, Stripe MPP, AP2, card, bank, or wallet rail adapters.
- Hosted DeliveryProof Cloud.
- Public push, npm publish, signed tags, and package provenance.

## v0.8 Security-Audit Addendum

The post-v0.8 black/white/grey review found one real fail-open partial-mode bug
and several trust-boundary/resource-hardening gaps. The committed follow-up
patches close the code-level items found in this pass:

- non-empty partial Merkle commitments now reject `k=0`;
- partial Merkle sample rows and proof leaves are bounded before leaf hashing;
- `verifyReceipt` rejects signed receipts whose `decision` contradicts
  `verdict.ok`;
- `assertReceiptMeetsPolicy` gives production integrations an opt-in strict
  policy check for route decisions, fallback, rail/verifier pinning, and nonce
  registry use;
- the MCP wrapper defaults to replay protection for local wrapper instances and
  offers `strictRouting`;
- reference rails can optionally verify receipt signatures when constructed with
  `settlementPublicKey`;
- canonicalization now has depth, node, string, and object-key caps;
- reference rails bind terminal receipts to the exact hold, rail, amount,
  currency, contract id, and contract hash.

The honest claim after this pass is still bounded: known code-level issues found
in the local audit were fixed or documented, local tests pass, and remaining risk
is integration/operations risk around real rails, keys, monitoring, external
attestations, and compliance.

## v0.9.1 Dual-Agent Review Hardening Addendum

A dual independent code review (Claude + Codex) of the v0.9.0 tree confirmed the
central money-safety invariant — `settle()` never captures when `verdict.ok !==
true` — holds, and found that several *exported* money-moving surfaces failed open
by default. The committed follow-up patches close them; the suite went 251 -> 260,
all green.

- Canonicalization emits RFC 8785 / JCS text directly, fixing integer-like-key
  reordering that had silently broken the `RFC8785-JCS` claim for cross-
  implementation hashing. String-keyed records stay byte-identical and the wire
  profile is unchanged.
- Reference rails reject receipts whose `decision` contradicts `verdict.ok` before
  terminalization, and add opt-in `requireSignature` for mandatory settlement-
  signature checks.
- ERC-8004/8183 projection helpers refuse to project a contradictory receipt into
  a chain-facing success.
- The nonce-registry WAL rejects lone or forged `mark` records on replay.
- Standalone verifiers reject non-finite numbers; amounts must be positive and
  finite.

This does not change the out-of-scope boundary or the real-money posture: a
deployment still needs a production non-custodial rail adapter, operator
key/security review, and any required attested Tier-B verifier. Deferred
follow-ups: `keyId` widening and mandatory-by-default rail/interop signature
verification (`requireSignature` ships it as opt-in).

## Explicitly Out Of Scope For v0.7

- Hosted DeliveryProof Cloud.
- Custody or escrow of real funds.
- Real x402, Stripe MPP, AP2, card, bank, or wallet settlement adapters.
- Public publish, npm publish, GitHub push, or PR creation.
- Legal/tax compliance certification.
- Formal third-party security audit.
- Formal safe-regex proof.
- Real TEE, zkTLS, ZK, or on-chain submission implementation.
- Partial-verifier Merkle mode.
- New verifier features beyond hardening existing v0.6 functionality.

## Residual Risks To Revisit At Final Scoring

- The mock rail is not production money movement.
- Node `node:crypto` is acceptable for the reference implementation, but production operators may require KMS/HSM/key rotation policies.
- Tier-B interface descriptors remain interface-only except the signed-oracle example.
- Regex guardrails are pragmatic built-in mitigations, not formal safe-regex proofs.
- A real deployment needs operator logging, monitoring, backup, incident response, and security review outside this library.

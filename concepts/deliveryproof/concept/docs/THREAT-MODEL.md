# Threat Model

DeliveryProof protects a narrow boundary: objective digital-delivery verification
and signed settlement justification. It does not make payment rails trustless and
does not certify that a human intent was well specified.

## Protected Assets

- the settlement invariant: failed verdicts refund, successful verdicts may release;
- signed `DeliveryReceipt` bytes and Ed25519 verification;
- canonical hashes of contracts, evidence, datasets, documents, and receipts;
- route decisions that prevent silent verifier downgrade;
- nonce and lifecycle records that make replay and terminal state auditable;
- local durable-rail WAL records and idempotency keys;
- verifier resource bounds over untrusted inputs.

## Main Adversaries

- a seller trying to get paid for an incorrect deliverable;
- a buyer or integrator who chooses a weak predicate and later expects stronger
  guarantees;
- an attacker replaying evidence, receipts, nonces, or API transcripts;
- an attacker attempting verifier downgrade;
- an attacker sending oversized or pathological inputs to exhaust CPU or memory;
- an attacker injecting prototype-pollution keys into parsed JSON or WAL records;
- a compromised or dishonest Tier-B attester.

## Mitigations

- The engine derives `decision` from `verdict.ok` and guards capture on positive
  verdicts only.
- Receipts are signed over canonical receipt bytes without the signature field.
- `routeDecision` can be signed into receipts, making downgrade policy visible.
- Canonicalization emits RFC 8785 / JCS text directly (integer-like keys included),
  rejects non-I-JSON values, and guards prototype-pollution keys, so independent
  implementations reproduce the same hashes and signatures.
- Reference rails and the ERC-8004/8183 projection helpers re-enforce the verdict at
  the money/interop boundary: a receipt whose `decision` contradicts `verdict.ok` is
  rejected before terminalization or chain-facing projection, and rails accept opt-in
  `requireSignature` for mandatory settlement-signature checks.
- The nonce-registry WAL validates replay records and rejects a lone or forged `mark`
  (mark-before-reserve or fingerprint mismatch).
- Standalone `schema` and `api-response` verifiers reject non-finite numbers; contract
  and receipt amounts must be positive and finite.
- Dataset, document, API-response, testsuite, and Merkle paths have explicit size,
  count, depth, or time bounds.
- Durable local rail operations are WAL-backed and idempotent.
- Audit hooks are best-effort and run outside the signed receipt body.
- Tier labels name residual trust instead of hiding it.

## Out Of Scope

- production custody or real external rail finality;
- legal enforceability, tax treatment, chargebacks, compliance holds, and disputes;
- host compromise, malicious Node runtime, or stolen signing keys;
- arbitrary hostile-code execution sandboxing;
- formal safe-regex proof;
- global semantic truth of datasets, documents, or API responses;
- subjective quality judgments as Tier-A proof;
- wallet signing, provider/RPC helpers, private-key handling, contract-call
  helpers, and on-chain submission;
- partial Merkle verifier mode without the full dataset;
- public package publishing and supply-chain signing.

## Trust Assumptions

The buyer must choose a predicate that captures their intent. External-truth
provenance must be supplied by a trusted Tier-B system such as zkTLS, TEE, ZK, or a
signed oracle. Real deployments must use production key management and a real
non-custodial rail adapter.

## Security Boundary Claim

For objective digital deliverables, assuming the predicate is adequate and the rail
honors the signed decision, DeliveryProof prevents release on a negative verifier
result and produces a portable audit record explaining release or refund.

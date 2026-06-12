# Security Policy

DeliveryProof is an OSS library and protocol reference build with one pinned
runtime dependency: `@noble/hashes` for Ethereum Keccak-256 helpers. Otherwise it
uses Node built-ins. The library-hardening target applies to protocol objects,
canonicalization, verifiers, routing, settlement orchestration, interop helpers,
and reference rails.

It is not a hosted escrow service, a custodian, a payment processor, a legal
settlement guarantee, or a substitute for an operator security review.

## Supported Scope

The supported security boundary is:

- signed `DeliveryReceipt` integrity and verification;
- the settlement invariant that failed verdicts refund rather than capture;
- no-silent-downgrade verifier routing;
- deterministic Tier-A verifiers with bounded parser/resource surfaces;
- local durable-rail write-ahead recovery and idempotency semantics;
- optional boundary audit hooks that never alter settlement behavior.

The following are explicit non-goals for this repository:

- production custody or movement of real funds;
- production x402, Stripe, AP2, card, bank, or chain rail adapters;
- formal third-party audit certification;
- formal safe-regex proof;
- arbitrary hostile-code sandboxing;
- legal, tax, PSD2/EMI/MSB/MTL, or compliance certification;
- wallet signing, provider/RPC helpers, contract-call helpers, private-key
  handling, or on-chain submission.

## Reporting Vulnerabilities

Until the project has a public disclosure process, report suspected
vulnerabilities privately to the maintainer. Do not publish exploit details until a
fix or mitigation window has been agreed.

Useful reports include:

- the affected commit hash;
- a minimal reproduction command or test case;
- expected versus observed behavior;
- whether the issue can cause a false release, forged receipt, verifier bypass,
  downgrade, denial of service, or replay.

## High-Priority Issue Classes

Treat these as high priority:

- any code path that captures while `verdict.ok !== true`;
- signed receipt byte instability or signature bypass;
- canonicalization collisions or prototype-pollution influence over hashes;
- verifier downgrade without explicit policy;
- unbounded parser or loop over attacker-controlled input;
- WAL corruption that replays or reverses terminal rail state;
- audit/logging hooks that affect signed receipt bytes or settlement decisions;
- false Tier-A claims for attested or subjective checks.

## Operator Responsibilities

A real deployment must add a production non-custodial rail adapter, key-management
policy, operator monitoring, backup and recovery procedures, abuse controls, and
legal/compliance review. If a use case depends on external-world provenance, it
must use an attested Tier-B verifier and document the residual trust in that
attestation system.

The in-repo mock rail is only a reference state machine. The durable rail is a
local WAL/idempotency reference, not universal exactly-once money movement; it
uses synchronous file writes but does not claim fsync-level power-loss durability.
Both reference rails can optionally verify receipt signatures when configured
with `settlementPublicKey`, but production rail adapters must still enforce their
own authorization, idempotency, custody, monitoring, and compliance controls.

Supply-chain and release-integrity policy is documented in
`docs/SUPPLY-CHAIN.md`.

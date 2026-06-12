# Contributing

DeliveryProof optimizes for a small, auditable, zero-dependency core. Changes
should preserve that shape unless the maintainer explicitly decides otherwise.

## Local Setup

Requires Node v22 or newer. There is no install step.

```bash
npm test
npm run check
npm run demo
git diff --check
```

Do not add runtime dependencies, devDependencies, build steps, generated bundles,
or network-dependent tests. The repository should remain usable with `git clone`
and plain `node`.

## Change Rules

- Keep settlement non-custodial and rail-neutral.
- Do not present mock rails, reference adapters, or Tier-B interface descriptors
  as production money movement or production cryptographic proof systems.
- Keep verifier failures as structured failing verdicts where possible; public
  validation errors may throw, but settlement must convert verifier/producer
  failures after authorization into refund verdicts.
- Preserve signed receipt byte compatibility unless a protocol-version bump is
  explicitly planned and documented.
- Bound every parser or loop over untrusted input.
- Add deterministic `node:test` coverage for new behavior and for regressions.
- Keep tests offline, seeded where randomness is useful, and non-flaky.
- Use Node built-ins for cryptography and IO unless a human explicitly approves a
  dependency/security decision.

## Review Checklist

Before requesting review, confirm:

- `npm test`, `npm run check`, `npm run demo`, and `git diff --check` pass;
- no path captures on a failed verdict;
- new public API is exported from `src/index.mjs` only if it is intentionally
  stable or clearly labeled experimental/reference;
- docs state any new trust assumptions, bounds, or limitations;
- no public push or package publish is attempted without explicit human approval.

## Scope For v0.7

v0.7 is a production-hardening release for the OSS library. It is not the hosted
SaaS, a custody product, a real rail adapter release, or a new verifier-feature
release. Partial Merkle verifier mode and keccak/ABI profiles remain out of scope.

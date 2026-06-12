# Supply Chain And Release Integrity

DeliveryProof keeps the supply-chain surface deliberately small. v0.9 adds the
first runtime dependency, pinned exactly for Ethereum Keccak-256 support.

## Dependency Policy

- Runtime dependencies: exactly `@noble/hashes@2.2.0`.
- Development dependency bucket: empty.
- Peer and optional dependency buckets: empty.
- Build step: none.
- Generated checked-in artifacts: none.
- Lockfile: committed and required.

The local and CI path is `git clone`, install a supported Node runtime, run
`npm ci`, then run the built-in scripts. Do not add dependencies or generated
build products beyond the explicit allowlist without a separate human security
decision.

## Reproducible Source Package

`package.json` uses a `files` whitelist so `npm pack --dry-run` includes only the
library source, docs, license, and package metadata. The package is source-only:
there is no transpilation, minification, bundle, or postinstall script.

Before any public package publication, compare the dry-run tarball listing against
the intended release contents and record the commit hash.

## CI Gate

The GitHub Actions workflow is non-publishing and read-only. It runs on Node 22
and Node 24, then checks:

- `npm ci` succeeds, proving `package.json` and `package-lock.json` are in sync;
- the dependency allowlist contains exactly `@noble/hashes@2.2.0`, no dev/peer/
  optional dependencies, and no transitive packages;
- `npm test`;
- `npm run check`, which syntax-checks every `.mjs` file under `src`, `test`,
  `examples`, and `scripts`;
- `git diff --check`;
- `npm pack --dry-run`.

There is no publish, deployment, secret use, or external payment-rail action in CI.

## Release Integrity Before Publication

Public release remains gated on explicit human approval. If a public release is
authorized later, the recommended minimum release process is:

1. Confirm the final library-hardening score and residual risks.
2. Re-run the local gate and CI on the exact release commit.
3. Create a signed git tag for the release.
4. Record the commit hash, tag, test summary, and `npm pack --dry-run` listing.
5. Publish only from the tagged commit.

This repository does not yet claim SLSA compliance, npm provenance attestation, a
third-party security audit, or signed npm package provenance.

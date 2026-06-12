// test/honesty.test.mjs
// Enforces the adapter's hard honesty constraints as executable tests.
//
// SCOPE / HONESTY: these are the non-negotiables, pinned so a future change cannot
// quietly violate them. They assert that (1) the public barrel never statically
// imports viem (it is genuinely lazy/optional) and loads in plain Node; (2) the package
// declares NO chain library as a hard dependency (viem lives only under
// optionalDependencies, nothing else chain-related leaks into dependencies); and
// (3) the README and SECURITY docs actually say "testnet" and carry an explicit
// no-canonical/blessed-address caveat. If any of these regress, this file fails.
// TESTNET / LOCAL ONLY — no mainnet, no real funds, no autonomous live tx.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const pkgRoot = join(here, '..');

function readPkgFile(name) {
  return readFileSync(join(pkgRoot, name), 'utf8');
}

// Statically scan src/ for a TOP-LEVEL `import ... from 'viem'` (or `import 'viem'`).
// A dynamic `await import('viem')` is allowed and is NOT matched. Returns offending
// "src/<file>:<line>" strings; empty means viem is only ever lazily imported.
function scanSrcForStaticViemImports() {
  const srcDir = join(pkgRoot, 'src');
  const offenders = [];
  for (const rel of readdirSync(srcDir, { recursive: true })) {
    if (typeof rel !== 'string' || !rel.endsWith('.mjs')) continue;
    const lines = readFileSync(join(srcDir, rel), 'utf8').split('\n');
    lines.forEach((line, i) => {
      if (
        /^\s*import\b[^\n]*\bfrom\s*['"]viem(\/[^'"]*)?['"]/.test(line) ||
        /^\s*import\s*['"]viem(\/[^'"]*)?['"]/.test(line)
      ) {
        offenders.push(`src/${rel}:${i + 1}`);
      }
    });
  }
  return offenders;
}

test('the public barrel never statically imports viem and loads in plain Node', async () => {
  // The real invariant is laziness, not viem's absence from node_modules (installing
  // viem flips that). Prove it STATICALLY: no source file may carry a top-level
  // `import ... from "viem"`; the only allowed viem load is `await import("viem")`
  // inside createViemErc8183Client. This holds whether or not viem is installed.
  const staticViemImports = scanSrcForStaticViemImports();
  assert.deepEqual(
    staticViemImports,
    [],
    `viem must never be statically imported (use await import("viem")); found at: ${staticViemImports.join(', ')}`,
  );

  // The barrel itself must import cleanly — it may only LAZILY import viem inside
  // createViemErc8183Client, never at module top-level.
  const mod = await import('../src/index.mjs');
  assert.equal(typeof mod.createErc8183Rail, 'function');
  assert.equal(typeof mod.createInMemoryErc8183Client, 'function');
  assert.equal(typeof mod.createViemErc8183Client, 'function');
  assert.equal(typeof mod.deliveryReceiptToEvaluatorCall, 'function');
  assert.equal(typeof mod.assertErc8183Client, 'function');
  assert.ok(Array.isArray(mod.ERC8183_JOB_ABI));
  assert.ok(mod.JobStatus && mod.JobStatus.Submitted === 'Submitted');
  for (const name of [
    'Erc8183RailError',
    'Erc8183NotSettleableError',
    'Erc8183JobNotFoundError',
    'Erc8183ClientError',
  ]) {
    assert.equal(typeof mod[name], 'function', `${name} must be exported`);
  }
});

test('createViemErc8183Client defers viem to call time (async factory)', async () => {
  const mod = await import('../src/index.mjs');
  // The factory is async and only touches viem when invoked, so importing the barrel
  // never loads viem. Called with an invalid address (and possibly no viem at all) it
  // must reject at call time, not at import time.
  await assert.rejects(
    () => mod.createViemErc8183Client({ rpcUrl: 'http://127.0.0.1:8545', jobContractAddress: '0xlocal' }),
    'createViemErc8183Client must reject when viem is not installed',
  );
});

test('package.json declares NO chain library as a hard dependency', () => {
  const pkg = JSON.parse(readPkgFile('package.json'));
  const deps = pkg.dependencies ?? {};
  const optional = pkg.optionalDependencies ?? {};

  // The ONLY hard dependency is the workspace core. No chain libs in dependencies.
  const chainLibs = ['viem', 'ethers', 'web3', '@wagmi/core', 'wagmi', 'web3.js'];
  for (const lib of chainLibs) {
    assert.equal(lib in deps, false, `${lib} must NOT be a hard dependency`);
  }
  assert.ok('deliveryproof' in deps, 'core "deliveryproof" must be a dependency');

  // viem must be present, and ONLY as an optional dependency.
  assert.ok('viem' in optional, 'viem must be declared under optionalDependencies');
  assert.equal('viem' in deps, false, 'viem must not also be a hard dependency');

  // Defense in depth: no dependency name should look chain-related.
  for (const name of Object.keys(deps)) {
    assert.ok(
      !/viem|ethers|web3|wagmi/i.test(name),
      `unexpected chain-related hard dependency: ${name}`,
    );
  }
});

test('README contains "testnet" and an explicit no-canonical-address caveat', () => {
  const readme = readPkgFile('README.md');
  assert.match(readme, /testnet/i, 'README must mention testnet');
  assert.match(
    readme,
    /no canonical|no blessed|not? a canonical|no hardcoded.*address|no.*blessed.*contract/i,
    'README must carry a no-canonical/blessed-address caveat',
  );
});

test('SECURITY contains "testnet" and an explicit no-canonical-address caveat', () => {
  const security = readPkgFile('SECURITY.md');
  assert.match(security, /testnet/i, 'SECURITY must mention testnet');
  assert.match(
    security,
    /no canonical|no blessed|not? a canonical|no hardcoded.*address|no.*blessed.*contract/i,
    'SECURITY must carry a no-canonical/blessed-address caveat',
  );
});

test('SECURITY states no mainnet / no real funds', () => {
  const security = readPkgFile('SECURITY.md');
  assert.match(security, /no mainnet/i, 'SECURITY must state no mainnet');
  assert.match(security, /no real funds|real money|no.*funds/i, 'SECURITY must state no real funds');
});

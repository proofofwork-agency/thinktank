#!/usr/bin/env node

// examples/conformance-demo.mjs
// Run the DeliveryProof RailAdapter conformance suite against the ERC-8183 adapter
// and print a PASS/FAIL line per case (exit 1 on any failure).
//
// SCOPE / HONESTY: this demo runs the adapter over the in-memory (FAKE) client only
// — NO chain, NO wallet, NO RPC, NO keys, NO live tx. The in-memory client's job
// Map is the only "chain state" here, and a restart simply reuses the prior rail's
// client instance so its Map survives. It exercises the same 10 cases CI asserts,
// but as a human-runnable, self-contained script (mirrors the core
// reference-manual-capture-rail.mjs demo). TESTNET / LOCAL ONLY — no mainnet, no
// real funds, no autonomous live tx.

import { fileURLToPath } from 'node:url';

import { runRailConformance } from 'deliveryproof';
import { createErc8183Rail, createInMemoryErc8183Client } from '../src/index.mjs';

/**
 * Per-case rail factory: a fresh rail gets a fresh in-memory client; a restart rail
 * inherits the prior rail's client so the in-process job Map (the simulated chain
 * state) survives the restart, which is what status-after-restart needs.
 *
 * @param {{ previousRail?: { _client: () => any } }} [ctx]
 * @returns {ReturnType<typeof createErc8183Rail>}
 */
function createRail({ previousRail } = {}) {
  const client = previousRail ? previousRail._client() : createInMemoryErc8183Client();
  return createErc8183Rail({ client, supportsRestart: true });
}

async function main() {
  const result = await runRailConformance({ createRail, supportsRestart: true });

  for (const entry of result.cases) {
    console.log(`${entry.ok ? 'PASS' : 'FAIL'} ${entry.name}${entry.error ? `: ${entry.error}` : ''}`);
  }
  console.log(
    result.ok
      ? `\nERC-8183 adapter: ${result.cases.length}/${result.cases.length} conformance cases PASSED`
      : `\nERC-8183 adapter: conformance FAILED (${result.cases.filter((c) => !c.ok).length} failing)`,
  );

  if (!result.ok) process.exitCode = 1;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await main();
}

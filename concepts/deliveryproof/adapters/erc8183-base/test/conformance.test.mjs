// test/conformance.test.mjs
// The ERC-8183 RailAdapter against DeliveryProof's own runRailConformance suite.
//
// SCOPE / HONESTY: this drives the adapter through the 10 core conformance cases
// with the in-memory (FAKE) client only — NO chain, NO wallet, NO RPC, NO keys,
// NO live tx. It proves two things: (1) the real adapter passes every case,
// including status-after-restart (which inherits the prior rail's client so the
// in-process job Map survives), and (2) the suite actually BITES — a deliberately
// broken control rail whose client lets a second complete() succeed and ignores
// the Submitted-only rule FAILS conformance. A green suite that cannot fail proves
// nothing; the control rail is the proof the assertions have teeth.
// TESTNET / LOCAL ONLY — no mainnet, no real funds, no autonomous live tx.

import test from 'node:test';
import assert from 'node:assert/strict';

import { runRailConformance, RAIL_CONFORMANCE_CASES } from 'deliveryproof';
import {
  createErc8183Rail,
  createInMemoryErc8183Client,
} from '../src/index.mjs';

import { createBrokenControlRail } from './helpers/broken-control-rail.mjs';

test('erc8183 rail passes the full DeliveryProof conformance suite', async () => {
  // Per-case closure: a fresh rail gets a fresh in-memory client; a restart rail
  // inherits the prior rail's client (its job Map is the simulated chain state).
  const createRail = ({ previousRail } = {}) => {
    const client = previousRail ? previousRail._client() : createInMemoryErc8183Client();
    return createErc8183Rail({ client, supportsRestart: true, allowUnsignedReceipts: true });
  };

  const result = await runRailConformance({ createRail, supportsRestart: true });

  assert.equal(
    result.ok,
    true,
    result.cases
      .map((c) => (c.ok ? `PASS ${c.name}` : `FAIL ${c.name}: ${c.error}`))
      .join('\n'),
  );

  // Every case that ran must be green, and the restart case must have run.
  for (const entry of result.cases) {
    assert.equal(entry.ok, true, `case ${entry.name} should pass: ${entry.error ?? ''}`);
  }
  const ran = new Set(result.cases.map((c) => c.name));
  assert.ok(
    ran.has('status-after-restart'),
    'status-after-restart must run when supportsRestart is advertised',
  );
});

test('every advertised conformance case is exercised', async () => {
  const createRail = ({ previousRail } = {}) => {
    const client = previousRail ? previousRail._client() : createInMemoryErc8183Client();
    return createErc8183Rail({ client, supportsRestart: true, allowUnsignedReceipts: true });
  };
  const result = await runRailConformance({ createRail, supportsRestart: true });
  const ran = new Set(result.cases.map((c) => c.name));
  for (const name of RAIL_CONFORMANCE_CASES) {
    assert.ok(ran.has(name), `conformance case ${name} must be exercised when restart is supported`);
  }
});

test('a signature-enforcing rail still passes conformance with the suite key', async () => {
  // The suite mints receipts signed by ctx.settlementKey and forwards its public
  // key as opts.settlementPublicKey. A fail-closed rail (requireSignature) must
  // still pass: it verifies every receipt against that key before terminalizing.
  const createRail = ({ settlementPublicKey, previousRail } = {}) => {
    const client = previousRail ? previousRail._client() : createInMemoryErc8183Client();
    return createErc8183Rail({
      client,
      supportsRestart: true,
      settlementPublicKey,
      requireSignature: true,
    });
  };
  const result = await runRailConformance({ createRail, supportsRestart: true });
  assert.equal(
    result.ok,
    true,
    result.cases
      .map((c) => (c.ok ? `PASS ${c.name}` : `FAIL ${c.name}: ${c.error}`))
      .join('\n'),
  );
});

test('the conformance suite BITES: a broken control rail FAILS', async () => {
  // Control rail: a lenient fake client that (a) lets a SECOND complete()/reject()
  // succeed instead of throwing, and (b) ignores the Submitted-only rule, plus a
  // rail wrapper that trusts receipt.decision blindly (no 7-field binding, no
  // verdict-consistency, no idempotency reconcile). If conformance can pass THIS,
  // its assertions are theater. It must fail.
  const createRail = ({ previousRail } = {}) => createBrokenControlRail({ previousRail });

  const result = await runRailConformance({ createRail, supportsRestart: true });

  assert.equal(
    result.ok,
    false,
    'conformance MUST fail for a rail that ignores binding/verdict/idempotency rules',
  );
  const failed = result.cases.filter((c) => !c.ok).map((c) => c.name);
  assert.ok(
    failed.length > 0,
    `expected at least one failing case for the broken control rail, got: ${JSON.stringify(result.cases)}`,
  );
});

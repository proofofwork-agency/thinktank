import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

import {
  settle,
  verifyReceipt,
  routeVerifier,
  hashVerifier,
  createDurableEscrowRail,
  createNonceRegistry,
  generateKeypair,
  sha256hex,
  validateDeliveryProofConfig,
  assertDeliveryProofConfig,
  deliveryProofHealthcheck,
  gracefulShutdown,
  DeliveryProofConfigurationError,
} from 'deliveryproof';

function tmpWal(t) {
  const dir = mkdtempSync(join(tmpdir(), 'deliveryproof-operability-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return join(dir, 'rail.jsonl');
}

function fixedRail() {
  let state = 'held';
  const hold = { holdId: 'fixed-hold', contractId: 'c', amount: 1, currency: 'USDC', state, history: [] };
  return {
    id: 'fixed-rail',
    authorize() {
      state = 'held';
      hold.state = state;
      return { ...hold, history: [] };
    },
    capture() {
      state = 'captured';
      hold.state = state;
      return { ...hold, history: [] };
    },
    refund() {
      state = 'refunded';
      hold.state = state;
      return { ...hold, history: [] };
    },
    status() {
      return { ...hold, state, history: [] };
    },
  };
}

function contractFor(output) {
  return {
    id: 'c',
    buyer: 'buyer',
    seller: 'seller',
    intent: 'operability test',
    deliverableType: 'application/json',
    predicate: { kind: 'hash', params: { expectedHash: sha256hex(output) } },
    price: { amount: 1, currency: 'USDC' },
    sla: { deadlineMs: 1_000 },
    refundRule: 'refund',
    railId: 'fixed-rail',
    nonce: 'n',
    createdAt: 1_700_000_000_000,
  };
}

test('operability: engine audit is best-effort and does not enter signed receipt bytes', async () => {
  const output = { ok: true };
  const settlementKey = generateKeypair();
  const now = () => 1_700_000_000_500;

  const baseline = await settle({
    contract: contractFor(output),
    produceEvidence: () => ({ output }),
    verifier: hashVerifier,
    rail: fixedRail(),
    settlementKey,
    now,
  });

  const events = [];
  const errors = [];
  const audited = await settle({
    contract: contractFor(output),
    produceEvidence: () => ({ output }),
    verifier: hashVerifier,
    rail: fixedRail(),
    settlementKey,
    now,
    audit: {
      emit(event) {
        events.push(event.event);
        if (event.event === 'engine.verdict.checked') throw new Error('audit backend down');
      },
      onError(err, event) {
        errors.push(`${event.event}:${err.message}`);
      },
    },
  });

  assert.deepEqual(audited.receipt, baseline.receipt);
  assert.equal(verifyReceipt(audited.receipt, settlementKey.publicKey), true);
  assert.equal(Object.prototype.hasOwnProperty.call(audited.receipt, 'audit'), false);
  assert.equal(audited.hold.state, 'captured');
  assert.ok(events.includes('engine.settle.started'));
  assert.ok(events.includes('engine.settle.completed'));
  assert.deepEqual(errors, ['engine.verdict.checked:audit backend down']);
});

test('operability: router emits boundary audit decisions without changing routing output', () => {
  const events = [];
  const result = routeVerifier(
    { predicate: { kind: 'hash', params: {} } },
    {
      policy: { deliverableType: 'any', minAssurance: 2 },
      now: () => 5,
      audit: (event) => events.push(event),
    },
  );

  assert.equal(result.routeDecision.selected, 'hash');
  assert.deepEqual(events.map((e) => e.event), ['router.route.selected']);
  assert.equal(events[0].selected, 'hash');
  assert.equal(events[0].at, 5);
});

test('operability: durable rail exposes flush, close, health, and graceful shutdown', async (t) => {
  const events = [];
  const rail = createDurableEscrowRail({
    logPath: tmpWal(t),
    now: () => 9,
    audit: (event) => events.push(event.event),
  });

  assert.equal(rail.flush(), true);
  assert.equal(rail.health().closed, false);
  const shutdown = await gracefulShutdown(rail);
  assert.deepEqual(shutdown, { ok: true, closed: 1, errors: [] });
  assert.equal(rail.health().closed, true);
  assert.throws(
    () => rail.authorize({ id: 'closed', price: { amount: 1, currency: 'USDC' } }),
    /rail is closed/,
  );
  assert.deepEqual(events, ['rail.flushed', 'rail.flushed', 'rail.closed']);
});

test('operability: config validation and healthcheck are explicit local-library checks', () => {
  const bad = validateDeliveryProofConfig({
    now: 'soon',
    verifier: {},
    rail: { authorize() {} },
    settlementKey: { publicKey: 'pub' },
    audit: 42,
  });
  assert.equal(bad.ok, false);
  assert.ok(bad.errors.some((e) => e.includes('now must be a function')));
  assert.ok(bad.errors.some((e) => e.includes('audit sink')));
  assert.ok(bad.errors.some((e) => e.includes('verifier')));
  assert.ok(bad.errors.some((e) => e.includes('rail must expose capture')));
  assert.ok(bad.errors.some((e) => e.includes('settlementKey')));
  assert.throws(() => assertDeliveryProofConfig({ verifier: {} }), DeliveryProofConfigurationError);

  const healthy = deliveryProofHealthcheck({
    now: () => 77,
    verifier: hashVerifier,
    rail: fixedRail(),
    settlementKey: { publicKey: 'pub', privateKey: 'priv' },
  });
  assert.equal(healthy.ok, true);
  assert.equal(healthy.status, 'ok');
  assert.equal(healthy.checkedAt, 77);
  assert.equal(healthy.components.rail, 'ok');
});

test('operability: production profile requires replay safety and warns on deployment gaps', () => {
  const base = {
    verifier: hashVerifier,
    rail: fixedRail(),
    settlementKey: { publicKey: 'pub', privateKey: 'priv' },
  };

  const missingReplay = validateDeliveryProofConfig(base, { profile: 'production' });
  assert.equal(missingReplay.ok, false);
  assert.ok(missingReplay.errors.some((e) => e.includes('requires nonceRegistry')));
  assert.ok(missingReplay.warnings.some((e) => e.includes('audit sink')));
  assert.ok(missingReplay.warnings.some((e) => e.includes('rail-no-sig-verify')));

  const production = validateDeliveryProofConfig({
    ...base,
    nonceRegistry: createNonceRegistry(),
    audit: () => {},
    railReceiptSignatureVerification: true,
    nonceRegistryLogPath: '/tmp/deliveryproof-nonce.jsonl',
  }, { profile: 'production' });
  assert.equal(production.ok, true);
  assert.ok(production.warnings.some((e) => e.includes('tmpfs WAL')));

  assert.throws(
    () => assertDeliveryProofConfig(base, { profile: 'production' }),
    DeliveryProofConfigurationError,
  );

  const health = deliveryProofHealthcheck({
    ...base,
    now: () => 88,
  }, { profile: 'production' });
  assert.equal(health.ok, false);
  assert.equal(health.status, 'degraded');
  assert.equal(health.checkedAt, 88);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

import { createNonceRegistry, createWalReplayStore } from '../src/engine/nonce-registry.mjs';
import { runReplayStoreConformance } from '../src/testing/replay-store-conformance.mjs';

function tempLog(t) {
  const dir = mkdtempSync(join(tmpdir(), 'deliveryproof-replay-store-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return join(dir, 'replay.jsonl');
}

test('replay store conformance: WAL store passes including restart', async (t) => {
  const logPath = tempLog(t);
  const result = await runReplayStoreConformance({
    createStore: () => createWalReplayStore({ logPath }),
    supportsRestart: true,
  });
  assert.equal(result.ok, true, describeCases(result));
  assert.equal(result.cases.some((entry) => entry.name === 'survive-restart' && entry.ok), true);
});

test('replay store conformance: broken double-reserve store fails the safety case', async () => {
  const result = await runReplayStoreConformance({
    createStore: () => createBrokenDoubleReserveStore(),
    supportsRestart: false,
  });
  assert.equal(result.ok, false);
  assert.equal(result.cases.find((entry) => entry.name === 'reject-concurrent-double-reserve')?.ok, false);
});

test('createNonceRegistry delegates to a supplied store without changing nonceKey ownership', () => {
  const calls = [];
  const entries = new Map();
  const store = {
    reserve(record) {
      calls.push(['reserve', record.key, record.fingerprint, record.state, record.at]);
      entries.set(record.key, { fingerprint: record.fingerprint, state: record.state, at: record.at });
    },
    mark(key, state, at) {
      calls.push(['mark', key, state, at]);
      const prior = entries.get(key);
      entries.set(key, { fingerprint: prior.fingerprint, state, at });
    },
    get(key) {
      return entries.get(key) ?? null;
    },
  };
  const registry = createNonceRegistry({ store, now: () => 42 });
  const key = registry.reserve({
    contract: {
      protocolVersion: 'deliveryproof/0.4-jcs1',
      id: 'contract-store-delegate',
      buyer: 'buyer',
      seller: 'seller',
      railId: 'rail',
      nonce: 'nonce',
    },
    settlementKeyId: 'settlement-key',
  });
  registry.mark(key, 'captured');

  assert.match(key, /^[0-9a-f]{64}$/);
  assert.equal(calls[0][0], 'reserve');
  assert.equal(calls[0][1], key);
  assert.equal(calls[0][3], 'reserved');
  assert.equal(calls[0][4], 42);
  assert.deepEqual(calls[1], ['mark', key, 'captured', 42]);
  assert.equal(registry.get(key).state, 'captured');
});

test('createWalReplayStore fsync mode persists replay records', (t) => {
  const logPath = tempLog(t);
  const store = createWalReplayStore({ logPath, fsync: true });
  store.reserve({ key: 'fsync-key', fingerprint: 'fsync-fingerprint', state: 'reserved', at: 1 });
  store.mark('fsync-key', 'refunded', 2);

  const recovered = createWalReplayStore({ logPath, fsync: true });
  assert.deepEqual(recovered.get('fsync-key'), {
    fingerprint: 'fsync-fingerprint',
    state: 'refunded',
    at: 2,
  });
});

function describeCases(result) {
  return result.cases
    .map((entry) => entry.ok ? `PASS ${entry.name}` : `FAIL ${entry.name}: ${entry.error}`)
    .join('\n');
}

function createBrokenDoubleReserveStore() {
  const entries = new Map();
  return {
    reserve({ key, fingerprint, state = 'reserved', at = Date.now() }) {
      entries.set(key, { fingerprint, state, at });
      return key;
    },
    mark(key, state, at = Date.now()) {
      const prior = entries.get(key);
      if (!prior) throw new Error(`unknown key ${key}`);
      entries.set(key, { fingerprint: prior.fingerprint, state, at });
    },
    get(key) {
      const entry = entries.get(key);
      return entry ? { ...entry } : null;
    },
  };
}

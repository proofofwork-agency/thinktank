// Regression tests for the v0.9 hardening pass.
//
// Each test corresponds to a finding from the dual code-review pass:
//  1. canonical.mjs   — RFC8785/JCS ordering for integer-like object keys
//  2. rails           — decision/verdict consistency enforced at the money layer
//  3. interop         — no chain-facing projection from a contradictory receipt
//  4. nonce WAL       — replay rejects a lone/forged mark record
//  5. verifiers       — non-finite (Infinity/NaN) numbers rejected
//  6. schema          — money amounts must be positive and finite

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  canonicalize,
  schemaVerifier,
  apiResponseVerifier,
  toErc8004ValidationPayload,
  toErc8183EvaluatorResult,
  createMockEscrowRail,
  createWalReplayStore,
  validateContract,
} from '../src/index.mjs';

test('canonical: integer-like object keys follow RFC8785/JCS code-unit order', () => {
  // Previously these round-tripped through a JS object whose integer keys
  // JSON.stringify re-ordered numerically ("2" before "10"), breaking JCS.
  assert.equal(canonicalize({ '10': 1, '2': 2, a: 3 }), '{"10":1,"2":2,"a":3}');
  assert.equal(canonicalize({ '100': 0, '20': 0, '3': 0, x: 0 }), '{"100":0,"20":0,"3":0,"x":0}');
  assert.equal(canonicalize({ z: { '10': 1, '2': 2 } }), '{"z":{"10":1,"2":2}}');
  assert.equal(canonicalize({ b: 1, '2': 2, A: 3, '10': 4 }), '{"10":4,"2":2,"A":3,"b":1}');
  // string-keyed records and arrays stay byte-identical to plain canonical JSON
  assert.equal(canonicalize({ id: 'x', amount: 1, city: 'AMS' }), '{"amount":1,"city":"AMS","id":"x"}');
  assert.equal(canonicalize([3, 2, 1]), '[3,2,1]');
});

test('schema verifier rejects non-finite (Infinity / NaN) numbers', () => {
  const c = { predicate: { params: { schema: { type: 'number' } } } };
  assert.equal(schemaVerifier.verify(c, { output: Infinity }, { now: () => 1 }).ok, false);
  assert.equal(schemaVerifier.verify(c, { output: -Infinity }, { now: () => 1 }).ok, false);
  assert.equal(schemaVerifier.verify(c, { output: NaN }, { now: () => 1 }).ok, false);
  assert.equal(schemaVerifier.verify(c, { output: 42 }, { now: () => 1 }).ok, true);
});

test('api-response verifier rejects non-finite numbers in typed fields', () => {
  const c = { id: 'c', nonce: 'n', predicate: { params: { fields: [{ path: '$.x', type: 'number' }] } } };
  const evidence = (x) => ({
    output: { contractId: 'c', nonce: 'n', request: { method: 'GET', url: 'u' }, response: { status: 200, body: { x } } },
  });
  assert.equal(apiResponseVerifier.verify(c, evidence(Infinity), { now: () => 1 }).ok, false);
  assert.equal(apiResponseVerifier.verify(c, evidence(5), { now: () => 1 }).ok, true);
});

test('interop projections reject internally contradictory receipts', () => {
  const contradictory = { decision: 'release', verdict: { ok: false }, contractId: 'job', contractHash: 'h' };
  assert.throws(() => toErc8183EvaluatorResult(contradictory));
  assert.throws(() => toErc8004ValidationPayload(contradictory));
  // consistent receipts still project
  assert.equal(toErc8183EvaluatorResult({ decision: 'release', verdict: { ok: true }, contractId: 'job' }).action, 'complete');
  assert.equal(toErc8004ValidationPayload({ decision: 'refund', verdict: { ok: false }, contractHash: 'h' }).response, 0);
});

test('mock rail refuses a forged release receipt whose verdict.ok is false', () => {
  const rail = createMockEscrowRail({ logger: false, allowUnsignedReceipts: true });
  const hold = rail.authorize({ id: 'c1', price: { amount: 5, currency: 'USD' } });
  const forged = {
    decision: 'release', verdict: { ok: false }, holdId: hold.holdId, contractId: 'c1',
    contractHash: hold.contractHash, railId: 'escrow-mock', amount: 5, currency: 'USD', signature: 'AAAA',
  };
  assert.throws(() => rail.capture(hold, forged));
  assert.equal(rail.status(hold.holdId).state, 'held');
});

test('mock rail still captures a consistent release receipt', () => {
  const rail = createMockEscrowRail({ logger: false, allowUnsignedReceipts: true });
  const hold = rail.authorize({ id: 'c2', price: { amount: 7, currency: 'USD' } });
  const ok = {
    decision: 'release', verdict: { ok: true }, holdId: hold.holdId, contractId: 'c2',
    contractHash: hold.contractHash, railId: 'escrow-mock', amount: 7, currency: 'USD', signature: 'AAAA',
  };
  assert.equal(rail.capture(hold, ok).state, 'captured');
});

test('mock rail without a settlement key or explicit opt-out throws at construction', () => {
  assert.throws(() => createMockEscrowRail({ logger: false }));
});

test('nonce WAL replay rejects a lone mark record with no prior reservation', () => {
  const dir = mkdtempSync(join(tmpdir(), 'dp-hardening-'));
  const logPath = join(dir, 'wal.log');
  writeFileSync(logPath, `${JSON.stringify({ type: 'mark', key: 'k', fingerprint: 'f', state: 'captured', at: 1 })}\n`);
  assert.throws(() => createWalReplayStore({ logPath }));
});

test('contract amount must be a positive finite number', () => {
  const mk = (amount) => ({
    protocolVersion: 'x', id: 'i', buyer: 'b', seller: 's', intent: 'x', deliverableType: 'application/json',
    refundRule: 'r', railId: 'rail', nonce: 'n', predicate: { kind: 'k', params: {} },
    price: { amount, currency: 'USD' }, sla: { deadlineMs: 1 }, createdAt: 1,
  });
  const amountErr = (amount) => validateContract(mk(amount)).errors.some((e) => e.includes('price.amount'));
  assert.equal(amountErr(-1), true);
  assert.equal(amountErr(0), true);
  assert.equal(amountErr(Infinity), true);
  assert.equal(amountErr(5), false);
});

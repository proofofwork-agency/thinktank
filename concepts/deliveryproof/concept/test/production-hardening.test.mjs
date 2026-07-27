import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { performance } from 'node:perf_hooks';

import { canonicalize, sha256hex, sha256utf8 } from '../src/protocol/canonical.mjs';
import { DeliveryProofValidationError } from '../src/protocol/errors.mjs';
import { generateKeypair } from '../src/protocol/crypto.mjs';
import { settle } from '../src/engine/deliveryproof.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { createDurableEscrowRail } from '../src/rails/durable-rail.mjs';
import { createNonceRegistry } from '../src/engine/nonce-registry.mjs';
import { hashVerifier } from '../src/verifiers/hash.mjs';
import { datasetVerifier } from '../src/verifiers/dataset.mjs';
import { documentVerifier } from '../src/verifiers/document.mjs';
import { apiResponseVerifier } from '../src/verifiers/api-response.mjs';
import { schemaVerifier } from '../src/verifiers/schema.mjs';

function tmpFile(t, prefix) {
  const dir = mkdtempSync(join(tmpdir(), prefix));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return join(dir, 'wal.jsonl');
}

function lcg(seed) {
  let state = seed >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 2 ** 32;
  };
}

function csvCell(value) {
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

test('production hardening: public API errors use DeliveryProofError taxonomy', async () => {
  const settlementKey = generateKeypair();
  await assert.rejects(
    () => settle({
      contract: null,
      produceEvidence: () => ({ output: null }),
      verifier: hashVerifier,
      rail: createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
      settlementKey,
    }),
    DeliveryProofValidationError,
  );
});

test('production hardening: injectable clocks make receipts, rails, and verifiers deterministic', async () => {
  const now = () => 1_700_000_000_000;
  const output = { ok: true };
  const settlementKey = generateKeypair();
  const result = await settle({
    contract: {
      id: 'clock-contract',
      buyer: 'buyer',
      seller: 'seller',
      intent: 'clock determinism',
      deliverableType: 'application/json',
      predicate: { kind: 'hash', params: { expectedHash: sha256hex(output) } },
      price: { amount: 1, currency: 'USDC' },
      sla: { deadlineMs: 60_000 },
      refundRule: 'refund',
      railId: 'escrow-mock',
      nonce: 'clock-nonce',
      createdAt: now(),
    },
    produceEvidence: () => ({ output }),
    verifier: hashVerifier,
    rail: createMockEscrowRail({ now, settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
    now,
  });

  assert.equal(result.verdict.checkedAt, now());
  assert.equal(result.receipt.issuedAt, now());
  assert.equal(result.hold.history.every((entry) => entry.at === now()), true);
});

test('production hardening: canonicalize preserves dangerous JSON keys without prototype pollution', () => {
  const payload = JSON.parse('{"__proto__":{"polluted":true},"constructor":{"prototype":{"polluted":true}},"safe":1}');
  const before = Object.prototype.polluted;
  assert.equal(canonicalize(payload), '{"__proto__":{"polluted":true},"constructor":{"prototype":{"polluted":true}},"safe":1}');
  assert.equal(Object.prototype.polluted, before);
});

test('production hardening: WAL replay rejects prototype-pollution records fail-closed', (t) => {
  const railWal = tmpFile(t, 'deliveryproof-rail-pollution-');
  writeFileSync(
    railWal,
    '{"type":"authorize","idempotencyKey":"x","fingerprint":"f","hold":{"holdId":"h","contractId":"c","amount":1,"currency":"USDC","state":"held","history":[],"__proto__":{"polluted":true}}}\n',
    'utf8',
  );
  assert.throws(
    () => createDurableEscrowRail({ logPath: railWal, allowUnsignedReceipts: true }),
    /unsafe WAL line/,
  );
  assert.equal(Object.prototype.polluted, undefined);

  const nonceWal = tmpFile(t, 'deliveryproof-nonce-pollution-');
  writeFileSync(
    nonceWal,
    '{"type":"reserve","key":"k","fingerprint":"f","state":"reserved","at":1,"constructor":{"prototype":{"polluted":true}}}\n',
    'utf8',
  );
  assert.throws(() => createNonceRegistry({ logPath: nonceWal }), /unsafe WAL line/);
  assert.equal(Object.prototype.polluted, undefined);
});

test('production hardening: dataset JSON rows reject prototype-pollution keys before scanning', () => {
  const row = JSON.parse('{"id":1,"name":"Ada","__proto__":{"polluted":true}}');
  const verdict = datasetVerifier.verify(
    {
      predicate: {
        kind: 'dataset',
        params: {
          format: 'json',
          columns: [
            { name: 'id', type: 'number' },
            { name: 'name', type: 'string' },
          ],
          rowCount: { min: 1, max: 1 },
        },
      },
    },
    { output: [row] },
    { now: () => 7 },
  );
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /prototype-pollution key/);
  assert.equal(Object.prototype.polluted, undefined);
});

test('production hardening: dataset JSON row scanning has a backward-compatible default row cap', () => {
  const row = { id: 1, name: 'Ada' };
  const verdict = datasetVerifier.verify(
    {
      predicate: {
        kind: 'dataset',
        params: {
          format: 'json',
          columns: [
            { name: 'id', type: 'number' },
            { name: 'name', type: 'string' },
          ],
          rowCount: { min: 1 },
        },
      },
    },
    { output: [row] },
    { now: () => 8 },
  );
  assert.equal(verdict.ok, true);

  const tooManyRows = Array.from({ length: 100_001 }, (_, id) => ({ id, name: `name-${id}` }));
  const oversized = datasetVerifier.verify(
    {
      predicate: {
        kind: 'dataset',
        params: {
          format: 'json',
          columns: [
            { name: 'id', type: 'number' },
            { name: 'name', type: 'string' },
          ],
          rowCount: { min: 0 },
        },
      },
    },
    { output: tooManyRows },
    { now: () => 8 },
  );
  assert.equal(oversized.ok, false);
  assert.match(oversized.reason, /JSON data row count exceeds max 100000/);
});

test('production hardening: dataset JSON cells and specs are bounded before hashing', () => {
  const baseContract = {
    predicate: {
      kind: 'dataset',
      params: {
        format: 'json',
        columns: [
          { name: 'id', type: 'number' },
          { name: 'name', type: 'string' },
        ],
        rowCount: { min: 1, max: 1 },
      },
    },
  };

  const nested = datasetVerifier.verify(
    baseContract,
    { output: [{ id: 1, name: { nested: true } }] },
    { now: () => 9 },
  );
  assert.equal(nested.ok, false);
  assert.match(nested.reason, /must be a primitive or null/);

  const nonFiniteBound = datasetVerifier.verify(
    {
      predicate: {
        kind: 'dataset',
        params: {
          format: 'json',
          columns: [{ name: 'id', type: 'number' }],
          rowCount: { min: 0, max: Infinity },
        },
      },
    },
    { output: [] },
    { now: () => 9 },
  );
  assert.equal(nonFiniteBound.ok, false);
  assert.match(nonFiniteBound.reason, /rowCount.max must be a non-negative integer/);

  const hugeDomain = datasetVerifier.verify(
    {
      predicate: {
        kind: 'dataset',
        params: {
          format: 'json',
          columns: [{ name: 'id', type: 'number', domain: Array.from({ length: 10_001 }, (_, i) => i) }],
          rowCount: { min: 1, max: 1 },
        },
      },
    },
    { output: [{ id: 1 }] },
    { now: () => 9 },
  );
  assert.equal(hugeDomain.ok, false);
  assert.match(hugeDomain.reason, /domain exceeds 10000 values/);
});

test('production hardening: api-response regex constraints are bounded before matching', () => {
  const contract = {
    id: 'api-hardening',
    nonce: 'api-nonce',
    createdAt: 0,
    predicate: {
      kind: 'api-response',
      params: {
        fields: [{ path: 'message', matches: '(a+)+$' }],
      },
    },
  };
  const evidence = {
    output: {
      contractId: 'api-hardening',
      nonce: 'api-nonce',
      request: { method: 'GET', url: 'https://example.test' },
      response: { status: 200, body: { message: 'aaaaaaaaaaaaaaaa!' } },
    },
  };
  const verdict = apiResponseVerifier.verify(contract, evidence, { now: () => 11 });
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /outside the supported safe subset/);
});

test('production hardening: api-response bodySchema traversal and paths are bounded', () => {
  const baseEvidence = {
    output: {
      contractId: 'api-bounds',
      nonce: 'api-bounds-nonce',
      request: { method: 'GET', url: 'https://example.test' },
      response: { status: 200, body: [] },
    },
  };
  const arrayVerdict = apiResponseVerifier.verify(
    {
      id: 'api-bounds',
      nonce: 'api-bounds-nonce',
      predicate: {
        kind: 'api-response',
        params: { bodySchema: { type: 'array', items: { type: 'number' } } },
      },
    },
    {
      output: {
        ...baseEvidence.output,
        response: { status: 200, body: Array.from({ length: 10_001 }, (_, i) => i) },
      },
    },
    { now: () => 12 },
  );
  assert.equal(arrayVerdict.ok, false);
  assert.match(arrayVerdict.reason, /exceeding max 10000/);

  const pathVerdict = apiResponseVerifier.verify(
    {
      id: 'api-bounds',
      nonce: 'api-bounds-nonce',
      predicate: {
        kind: 'api-response',
        params: { fields: [{ path: 'x'.repeat(257), equals: 1 }] },
      },
    },
    baseEvidence,
    { now: () => 12 },
  );
  assert.equal(pathVerdict.ok, false);
  assert.match(pathVerdict.reason, /path exceeds 256 characters/);
});

test('production hardening: api-response bodySchema width and allowed sets are bounded', () => {
  const baseEvidence = {
    output: {
      contractId: 'api-width',
      nonce: 'api-width-nonce',
      request: { method: 'GET', url: 'https://example.test' },
      response: { status: 200, body: { code: 'ok' } },
    },
  };
  const requiredVerdict = apiResponseVerifier.verify(
    {
      id: 'api-width',
      nonce: 'api-width-nonce',
      predicate: {
        kind: 'api-response',
        params: {
          bodySchema: {
            type: 'object',
            required: Array.from({ length: 257 }, (_, i) => `k${i}`),
          },
        },
      },
    },
    baseEvidence,
    { now: () => 12 },
  );
  assert.equal(requiredVerdict.ok, false);
  assert.match(requiredVerdict.reason, /required.*exceeds/);

  const inVerdict = apiResponseVerifier.verify(
    {
      id: 'api-width',
      nonce: 'api-width-nonce',
      predicate: {
        kind: 'api-response',
        params: { fields: [{ path: 'code', in: Array.from({ length: 1_001 }, (_, i) => `v${i}`) }] },
      },
    },
    baseEvidence,
    { now: () => 12 },
  );
  assert.equal(inVerdict.ok, false);
  assert.match(inVerdict.reason, /allowed set exceeds/);
});

test('production hardening: schema verifier traversal is bounded', () => {
  const deepSchema = { type: 'object', properties: {} };
  let cursor = deepSchema;
  const deepValue = {};
  let valueCursor = deepValue;
  for (let i = 0; i < 130; i++) {
    cursor.properties.child = { type: 'object', properties: {} };
    cursor = cursor.properties.child;
    valueCursor.child = {};
    valueCursor = valueCursor.child;
  }
  const deep = schemaVerifier.verify(
    { predicate: { kind: 'schema', params: { schema: deepSchema } } },
    { output: deepValue },
    { now: () => 12 },
  );
  assert.equal(deep.ok, false);
  assert.match(deep.reason, /max depth/);

  const tooManyRequired = schemaVerifier.verify(
    {
      predicate: {
        kind: 'schema',
        params: {
          schema: { type: 'object', required: Array.from({ length: 10_001 }, (_, i) => `k${i}`) },
        },
      },
    },
    { output: {} },
    { now: () => 12 },
  );
  assert.equal(tooManyRequired.ok, false);
  assert.match(tooManyRequired.reason, /required.*exceeds/);
});

test('production hardening: seeded CSV property test accepts RFC-4180 quoted cells', () => {
  const rand = lcg(0xC0FFEE);
  const rows = [];
  for (let i = 0; i < 40; i++) {
    const name = `name-${i},${Math.floor(rand() * 100)}`;
    const note = i % 3 === 0 ? `line ${i}\nquoted "${i}"` : `plain ${i}`;
    rows.push({ id: i, name, note });
  }
  const csv = [
    'id,name,note',
    ...rows.map((row) => [row.id, row.name, row.note].map(csvCell).join(',')),
  ].join('\n');
  const verdict = datasetVerifier.verify(
    {
      nonce: 'csv-property',
      predicate: {
        kind: 'dataset',
        params: {
          format: 'csv',
          columns: [
            { name: 'id', type: 'number' },
            { name: 'name', type: 'string' },
            { name: 'note', type: 'string' },
          ],
          rowCount: { min: rows.length, max: rows.length },
          datasetHash: sha256hex(rows),
        },
      },
    },
    { output: csv },
    { now: () => 13 },
  );
  assert.equal(verdict.ok, true);
});

test('production hardening: seeded markdown property test keeps objective checks deterministic', () => {
  const rand = lcg(0xD0C);
  const terms = [];
  for (let i = 0; i < 12; i++) terms.push(`term-${Math.floor(rand() * 1000)}`);
  const doc = `# Report\n\n## Evidence\n\n${terms.join(' ')}\n`;
  const verdict = documentVerifier.verify(
    {
      predicate: {
        kind: 'document',
        params: {
          format: 'markdown',
          headings: [{ text: 'Report', level: 1 }, { text: 'Evidence', level: 2 }],
          requiredTerms: terms.map((term) => ({ text: term, minCount: 1 })),
          checksums: [{ target: 'document', sha256: sha256utf8(doc) }],
        },
      },
    },
    { output: doc },
    { now: () => 17 },
  );
  assert.equal(verdict.ok, true);
});

test('production hardening: document verifier bounds contract spec arrays', () => {
  const manyTerms = documentVerifier.verify(
    {
      predicate: {
        kind: 'document',
        params: {
          requiredTerms: Array.from({ length: 257 }, (_, i) => `term-${i}`),
        },
      },
    },
    { output: '# Report\n\nterm-1' },
    { now: () => 16 },
  );
  assert.equal(manyTerms.ok, false);
  assert.match(manyTerms.reason, /requiredTerms has 257 item\(s\), exceeding max 256/);

  const hugeHeading = documentVerifier.verify(
    {
      predicate: {
        kind: 'document',
        params: {
          headings: [{ text: 'x'.repeat(1_025) }],
        },
      },
    },
    { output: '# Report' },
    { now: () => 16 },
  );
  assert.equal(hugeHeading.ok, false);
  assert.match(hugeHeading.reason, /heading text exceeds 1024 characters/);
});

test('production hardening: seeded canonicalize property test is order-independent', () => {
  const rand = lcg(0xA11CE);
  for (let i = 0; i < 100; i++) {
    const value = {
      z: Math.floor(rand() * 1000),
      a: `v-${Math.floor(rand() * 1000)}`,
      nested: { y: i % 2 === 0, b: [i, Math.floor(rand() * 100)] },
    };
    const reordered = {
      nested: { b: value.nested.b, y: value.nested.y },
      a: value.a,
      z: value.z,
    };
    assert.equal(canonicalize(value), canonicalize(reordered));
  }
});

test('production hardening: resource smoke rejects oversized document preflight quickly', () => {
  const oversizedLine = `# ${'x'.repeat(16_385)}`;
  const started = performance.now();
  const verdict = documentVerifier.verify(
    { predicate: { kind: 'document', params: { format: 'markdown', headings: [{ text: 'x', level: 1 }] } } },
    { output: oversizedLine },
    { now: () => 19 },
  );
  const elapsed = performance.now() - started;
  assert.equal(verdict.ok, false);
  assert.equal(verdict.diff.reason, 'line too long');
  assert.ok(elapsed < 500, `oversized document preflight took ${elapsed}ms`);
});

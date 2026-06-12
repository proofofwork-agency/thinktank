import test from 'node:test';
import assert from 'node:assert/strict';

import { merkleRoot } from '../src/protocol/merkle.mjs';
import { selectSampleIndices } from '../src/protocol/merkle-sample.mjs';

const rows = [
  { id: 3, region: 'eu', revenue: 30 },
  { id: 1, region: 'us', revenue: 10 },
  { id: 5, region: 'apac', revenue: 50 },
  { id: 2, region: 'eu', revenue: 20 },
  { id: 4, region: 'us', revenue: 40 },
  { id: 6, region: 'apac', revenue: 60 },
];

test('merkle sample selection: deterministic and sorted', () => {
  const root = merkleRoot(rows);
  const selected = selectSampleIndices('n-1', root, rows.length, 4);

  assert.deepEqual(selected, [...selected].sort((a, b) => a - b));
  assert.deepEqual(selected, selectSampleIndices('n-1', root, rows.length, 4));
});

test('merkle sample selection: k is capped to rowCount and zero cases are empty', () => {
  const root = merkleRoot(rows);

  assert.deepEqual(selectSampleIndices('n-1', root, 0, 8), []);
  assert.deepEqual(selectSampleIndices('n-1', root, 2, 10), [0, 1]);
  assert.equal(selectSampleIndices('n-1', root, rows.length, 0).length, 0);
});

test('merkle sample selection: indices are unique and in range', () => {
  const root = merkleRoot(rows);
  const selected = selectSampleIndices('n-1', root, rows.length, rows.length);

  assert.equal(selected.length, rows.length);
  assert.equal(new Set(selected).size, selected.length);
  assert.deepEqual(selected, [0, 1, 2, 3, 4, 5]);
});

test('merkle sample selection: changed input changes selection', () => {
  const root = merkleRoot(rows);
  const changedRoot = merkleRoot([...rows, { id: 7, region: 'eu', revenue: 70 }]);
  const base = selectSampleIndices('n-1', root, rows.length, 3);

  assert.notDeepEqual(base, selectSampleIndices('n-2', root, rows.length, 3));
  assert.notDeepEqual(base, selectSampleIndices('n-1', changedRoot, rows.length, 3));
  assert.notDeepEqual(base, selectSampleIndices('n-1', root, rows.length + 1, 3));
  assert.notDeepEqual(base, selectSampleIndices('n-1', root, rows.length, 4).slice(0, 3));
});

test('merkle sample selection: work is bounded by k, not rowCount', () => {
  const root = merkleRoot(rows);
  const start = process.hrtime.bigint();
  const selected = selectSampleIndices('large-rowcount', root, 10_000_000, 8);
  const elapsedMs = Number(process.hrtime.bigint() - start) / 1_000_000;

  assert.equal(selected.length, 8);
  assert.equal(new Set(selected).size, 8);
  assert.deepEqual(selected, [...selected].sort((a, b) => a - b));
  assert.ok(selected.every((index) => Number.isInteger(index) && index >= 0 && index < 10_000_000));
  assert.ok(elapsedMs < 250, `selection should not scale with rowCount; elapsed ${elapsedMs}ms`);
});

test('merkle sample selection: rejects invalid bounds', () => {
  const root = merkleRoot(rows);

  assert.throws(() => selectSampleIndices('', root, rows.length, 1), /nonce/);
  assert.throws(() => selectSampleIndices('n', 'not-hex', rows.length, 1), /root/);
  assert.throws(() => selectSampleIndices('n', root, -1, 1), /rowCount/);
  assert.throws(() => selectSampleIndices('n', root, rows.length, -1), /k/);
  assert.throws(() => selectSampleIndices('n', root, rows.length, 10_001), /k/);
});

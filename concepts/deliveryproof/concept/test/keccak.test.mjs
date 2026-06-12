import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

import { keccak256 } from '../src/protocol/keccak.mjs';

test('keccak256 matches Ethereum known vectors', () => {
  assert.equal(
    keccak256(''),
    'c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470',
  );
  assert.equal(
    keccak256('abc'),
    '4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45',
  );
  assert.equal(
    keccak256(new Uint8Array([0, 1, 2, 3])),
    'd98f2e8134922f73748703c8e7084d42f13d2fa1439936ef5a3abcf5646fe83f',
  );
});

test('node sha3-256 is not Ethereum keccak256', () => {
  const nodeSha3Empty = createHash('sha3-256').update('', 'utf8').digest('hex');
  assert.equal(
    nodeSha3Empty,
    'a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a',
  );
  assert.notEqual(nodeSha3Empty, keccak256(''));
});

test('keccak256 rejects unsupported input types', () => {
  assert.throws(() => keccak256({}), /string or Uint8Array/);
});

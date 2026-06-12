import test from 'node:test';
import assert from 'node:assert/strict';

import {
  CANONICALIZATION,
  PROTOCOL_VERSION,
  canonicalize,
  sha256bytes,
  sha256hex,
  sha256utf8,
} from '../src/protocol/canonical.mjs';
import { generateKeypair, sign, verify, keyId } from '../src/protocol/crypto.mjs';

test('canonicalize is independent of object key insertion order', () => {
  const a = { b: 1, a: 2, c: { y: 9, x: 8 } };
  const b = { c: { x: 8, y: 9 }, a: 2, b: 1 };
  assert.equal(canonicalize(a), canonicalize(b));
  // Keys are emitted in sorted order.
  assert.equal(canonicalize(a), '{"a":2,"b":1,"c":{"x":8,"y":9}}');
});

test('canonicalize preserves array order (arrays are not sorted)', () => {
  assert.equal(canonicalize([3, 1, 2]), '[3,1,2]');
  assert.notEqual(canonicalize([1, 2, 3]), canonicalize([3, 2, 1]));
  // Nested object keys inside arrays are still sorted, element order kept.
  assert.equal(
    canonicalize([{ b: 1, a: 2 }, { d: 4, c: 3 }]),
    '[{"a":2,"b":1},{"c":3,"d":4}]',
  );
});

test('canonicalize handles primitives and null', () => {
  assert.equal(canonicalize(42), '42');
  assert.equal(canonicalize('hi'), '"hi"');
  assert.equal(canonicalize(true), 'true');
  assert.equal(canonicalize(null), 'null');
});

test('sha256hex is stable and order-independent for objects', () => {
  const h1 = sha256hex({ a: 1, b: 2 });
  const h2 = sha256hex({ b: 2, a: 1 });
  assert.equal(h1, h2);
  // Stable across repeated calls.
  assert.equal(sha256hex({ a: 1, b: 2 }), h1);
  // Lowercase 64-char hex.
  assert.match(h1, /^[0-9a-f]{64}$/);
});

test('sha256hex differs when content differs', () => {
  assert.notEqual(sha256hex({ a: 1 }), sha256hex({ a: 2 }));
});

test('protocol constants identify the wire version and canonicalization profile', () => {
  assert.match(PROTOCOL_VERSION, /^deliveryproof\//);
  assert.equal(CANONICALIZATION, 'RFC8785-JCS');
});

test('sha256utf8 matches a known vector for the empty string', () => {
  // Raw SHA-256 of "" — guards the raw-byte hashing wiring against regressions.
  assert.equal(
    sha256utf8(''),
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  );
});

test('sha256hex hashes canonical JSON, while sha256utf8/sha256bytes hash raw domains', () => {
  const str = 'deliveryproof';
  const bytes = new TextEncoder().encode(str);
  assert.equal(sha256utf8(str), sha256bytes(bytes));
  assert.notEqual(sha256hex(str), sha256utf8(str)); // protocol JSON string includes quotes
  assert.match(sha256bytes(bytes), /^[0-9a-f]{64}$/);
});

test('canonicalize rejects ambiguous non-I-JSON values', () => {
  assert.throws(() => canonicalize({ a: undefined }), /undefined/);
  assert.throws(() => canonicalize([, 1]), /sparse/);
  assert.throws(() => canonicalize({ n: Number.NaN }), /non-finite/);
  assert.throws(() => canonicalize(new Date()), /non-plain/);
  assert.throws(() => canonicalize({ s: '\ud800' }), /lone high surrogate/);
});

test('canonicalize enforces bounded depth, nodes, strings, and key count', () => {
  assert.throws(() => canonicalize([[[1]]], { maxDepth: 2 }), /depth exceeds 2/);
  assert.throws(() => canonicalize([1, 2, 3], { maxNodes: 3 }), /node count exceeds 3/);
  assert.throws(() => canonicalize('abcd', { maxStringChars: 3 }), /string length exceeds 3/);
  assert.throws(() => canonicalize({ a: 1, b: 2 }, { maxObjectKeys: 1 }), /object key count exceeds 1/);
  assert.equal(canonicalize({ a: ['ok'] }, { maxDepth: 4, maxNodes: 4, maxStringChars: 2, maxObjectKeys: 1 }), '{"a":["ok"]}');
});

test('sign/verify round-trip succeeds', () => {
  const { publicKey, privateKey } = generateKeypair();
  const msg = 'verified delivery gates settlement';
  const sig = sign(privateKey, msg);
  assert.equal(typeof sig, 'string');
  assert.equal(verify(publicKey, msg, sig), true);
});

test('verify fails on a tampered message', () => {
  const { publicKey, privateKey } = generateKeypair();
  const msg = 'release on delivery';
  const sig = sign(privateKey, msg);
  assert.equal(verify(publicKey, msg + ' (mutated)', sig), false);
});

test('verify fails on a tampered signature', () => {
  const { publicKey, privateKey } = generateKeypair();
  const msg = 'release on delivery';
  const sig = sign(privateKey, msg);
  // Flip the first base64 char to a different valid base64 char.
  const flipped = (sig[0] === 'A' ? 'B' : 'A') + sig.slice(1);
  assert.equal(verify(publicKey, msg, flipped), false);
});

test('verify fails under a different (wrong) public key', () => {
  const signer = generateKeypair();
  const other = generateKeypair();
  const msg = 'release on delivery';
  const sig = sign(signer.privateKey, msg);
  assert.equal(verify(other.publicKey, msg, sig), false);
});

test('keyId is stable, 16 hex chars, and tied to the public key', () => {
  const { publicKey } = generateKeypair();
  const id = keyId(publicKey);
  assert.match(id, /^[0-9a-f]{16}$/);
  // Stable for the same key.
  assert.equal(keyId(publicKey), id);
  // Matches the documented derivation: first 16 hex of raw sha256(pem).
  assert.equal(id, sha256utf8(publicKey).slice(0, 16));
});

test('keyId differs across distinct keypairs', () => {
  const a = generateKeypair();
  const b = generateKeypair();
  assert.notEqual(keyId(a.publicKey), keyId(b.publicKey));
});

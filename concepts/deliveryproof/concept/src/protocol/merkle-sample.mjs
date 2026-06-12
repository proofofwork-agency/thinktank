// merkle-sample.mjs — deterministic partial-Merkle sample index selection.
//
// Indices are sorted-leaf indices: they refer to the same sorted leaf order used
// by buildMerkleTree(). This helper deliberately does not verify proofs; M1b wires
// proof verification and row conformance on top of this bounded selection core.

import { sha256utf8 } from './canonical.mjs';

const HASH_HEX_RE = /^[0-9a-f]{64}$/;
const SAMPLE_INDEX_DOMAIN = 'deliveryproof.dataset.merkle.sample.v1';
const MAX_SAMPLE_K = 10_000;

/**
 * Deterministically select sorted-leaf indices for partial Merkle verification.
 *
 * The seed binds nonce, committed root, rowCount, k, and a domain string. Selection
 * uses bounded rejection sampling and returns sorted unique indices without ever
 * materializing the rowCount-sized index space.
 *
 * @param {string} nonce
 * @param {string} root committed Merkle root
 * @param {number} rowCount committed sorted leaf count
 * @param {number} k committed sample count; capped to rowCount
 * @returns {number[]}
 */
export function selectSampleIndices(nonce, root, rowCount, k) {
  assertNonce(nonce);
  assertRoot(root);
  assertRowCount(rowCount);
  assertK(k);

  const sampleSize = Math.min(k, rowCount);
  if (sampleSize === 0) return [];

  const seed = sampleSeed(nonce, root, rowCount, k);
  const selected = new Set();
  let counter = 0;
  const maxAttempts = Math.max(1000, sampleSize * 100);
  while (selected.size < sampleSize) {
    if (counter >= maxAttempts) {
      throw new Error('could not derive enough unique Merkle sample indices within the bounded attempt limit');
    }
    const digest = sha256utf8(`${seed}:${counter}`);
    const index = Number(BigInt(`0x${digest}`) % BigInt(rowCount));
    selected.add(index);
    counter++;
  }

  return [...selected].sort((a, b) => a - b);
}

/**
 * @param {string} nonce
 * @param {string} root
 * @param {number} rowCount
 * @param {number} k
 * @returns {string}
 */
function sampleSeed(nonce, root, rowCount, k) {
  return sha256utf8(`${SAMPLE_INDEX_DOMAIN}|${nonce}|${root}|${rowCount}|${k}`);
}

function assertNonce(nonce) {
  if (typeof nonce !== 'string' || nonce.length === 0) throw new Error('nonce must be a non-empty string');
}

function assertRoot(root) {
  if (typeof root !== 'string' || !HASH_HEX_RE.test(root)) {
    throw new Error('root must be a lowercase 64-character hex SHA-256 digest');
  }
}

function assertRowCount(rowCount) {
  if (!Number.isSafeInteger(rowCount) || rowCount < 0) throw new Error('rowCount must be a non-negative safe integer');
}

function assertK(k) {
  if (!Number.isSafeInteger(k) || k < 0 || k > MAX_SAMPLE_K) {
    throw new Error(`k must be a non-negative safe integer <= ${MAX_SAMPLE_K}`);
  }
}

// merkle.mjs — deterministic SHA-256 Merkle commitments for dataset rows.
//
// Leaves are sorted by canonicalize(row), so the root is independent of input
// presentation order. Duplicate rows remain distinct leaves at distinct sorted
// indices; proofs therefore include both index and leafCount. Odd nodes are
// carried up unchanged rather than duplicated, avoiding duplicate-node
// malleability for odd-sized trees.
//
// Domain separation:
//   leaf = SHA256(0x00 || canonicalize(row))
//   node = SHA256(0x01 || leftHashBytes || rightHashBytes)
//   empty = SHA256(0x02)

import { canonicalize, sha256bytes } from './canonical.mjs';

const LEAF_PREFIX = 0x00;
const NODE_PREFIX = 0x01;
const EMPTY_PREFIX = 0x02;
const HASH_HEX_RE = /^[0-9a-f]{64}$/;
const encoder = new TextEncoder();

/**
 * @param {*} leaf
 * @returns {string}
 */
export function merkleLeafHash(leaf) {
  return taggedHash(LEAF_PREFIX, encoder.encode(canonicalize(leaf)));
}

/**
 * @param {string} left
 * @param {string} right
 * @returns {string}
 */
export function merkleNodeHash(left, right) {
  return taggedHash(NODE_PREFIX, hexToBytes(left), hexToBytes(right));
}

/**
 * @returns {string}
 */
export function emptyMerkleRoot() {
  return taggedHash(EMPTY_PREFIX);
}

/**
 * Sort leaves by canonical JSON. Duplicate canonical rows are tie-broken by
 * original position so they remain separate, deterministic leaves.
 *
 * @param {Array<*>} leaves
 * @returns {Array<{value:*, canonical:string, originalIndex:number, index:number, hash:string}>}
 */
export function sortedMerkleLeaves(leaves) {
  assertArray(leaves, 'leaves');
  return leaves
    .map((value, originalIndex) => ({
      value,
      canonical: canonicalize(value),
      originalIndex,
      index: -1,
      hash: '',
    }))
    .sort((a, b) => (a.canonical < b.canonical ? -1 : a.canonical > b.canonical ? 1 : a.originalIndex - b.originalIndex))
    .map((entry, index) => ({ ...entry, index, hash: merkleLeafHash(entry.value) }));
}

/**
 * @param {Array<*>} leaves
 * @returns {string}
 */
export function merkleRoot(leaves) {
  return buildMerkleTree(leaves).root;
}

/**
 * @param {Array<*>} leaves
 * @returns {{root:string, leafCount:number, leaves:Array<{value:*, canonical:string, originalIndex:number, index:number, hash:string}>, levels:string[][]}}
 */
export function buildMerkleTree(leaves) {
  const sorted = sortedMerkleLeaves(leaves);
  if (sorted.length === 0) {
    return { root: emptyMerkleRoot(), leafCount: 0, leaves: [], levels: [] };
  }

  const levels = [sorted.map((entry) => entry.hash)];
  while (levels[levels.length - 1].length > 1) {
    const prior = levels[levels.length - 1];
    const next = [];
    for (let i = 0; i < prior.length; i += 2) {
      if (i + 1 >= prior.length) {
        next.push(prior[i]);
      } else {
        next.push(merkleNodeHash(prior[i], prior[i + 1]));
      }
    }
    levels.push(next);
  }

  return { root: levels[levels.length - 1][0], leafCount: sorted.length, leaves: sorted, levels };
}

/**
 * Build a proof for a sorted leaf index. The caller supplies the sorted index,
 * not the original presentation index; use sortedMerkleLeaves() to map when
 * needed.
 *
 * @param {Array<*>} leaves
 * @param {number} index sorted leaf index
 * @returns {{root:string, leaf:*, index:number, leafCount:number, siblings:Array<{side:'left'|'right', hash:string}>}}
 */
export function buildMerkleProof(leaves, index) {
  const tree = buildMerkleTree(leaves);
  assertIndex(index, tree.leafCount);
  const leaf = tree.leaves[index].value;
  const siblings = [];
  let idx = index;

  for (let level = 0; level < tree.levels.length - 1; level++) {
    const nodes = tree.levels[level];
    if (idx % 2 === 0) {
      if (idx + 1 < nodes.length) siblings.push({ side: 'right', hash: nodes[idx + 1] });
    } else {
      siblings.push({ side: 'left', hash: nodes[idx - 1] });
    }
    idx = Math.floor(idx / 2);
  }

  return { root: tree.root, leaf, index, leafCount: tree.leafCount, siblings };
}

/**
 * Verify a Merkle inclusion proof. `leafCount` is required so odd carry-up
 * levels and out-of-range indices are unambiguous.
 *
 * @param {Object} proof
 * @param {string} proof.root
 * @param {*} proof.leaf
 * @param {number} proof.index sorted leaf index
 * @param {number} proof.leafCount total sorted leaves in the committed tree
 * @param {Array<{side:'left'|'right', hash:string}>} proof.siblings
 * @returns {boolean}
 */
export function verifyMerkleProof(proof) {
  try {
    if (!proof || typeof proof !== 'object') return false;
    assertHash(proof.root, 'proof.root');
    assertIndex(proof.index, proof.leafCount);
    if (!Array.isArray(proof.siblings)) return false;

    let current = merkleLeafHash(proof.leaf);
    let idx = proof.index;
    let width = proof.leafCount;
    let siblingIndex = 0;

    while (width > 1) {
      if (idx % 2 === 0 && idx + 1 >= width) {
        idx = Math.floor(idx / 2);
        width = Math.ceil(width / 2);
        continue;
      }

      if (siblingIndex >= proof.siblings.length) return false;
      const sibling = proof.siblings[siblingIndex++];
      assertSibling(sibling);
      const expectedSide = idx % 2 === 0 ? 'right' : 'left';
      if (sibling.side !== expectedSide) return false;
      current = sibling.side === 'right'
        ? merkleNodeHash(current, sibling.hash)
        : merkleNodeHash(sibling.hash, current);
      idx = Math.floor(idx / 2);
      width = Math.ceil(width / 2);
    }

    return siblingIndex === proof.siblings.length && current === proof.root;
  } catch {
    return false;
  }
}

/**
 * @param {number} tag
 * @param {...Uint8Array} parts
 * @returns {string}
 */
function taggedHash(tag, ...parts) {
  const total = 1 + parts.reduce((sum, part) => sum + part.length, 0);
  const bytes = new Uint8Array(total);
  bytes[0] = tag;
  let offset = 1;
  for (const part of parts) {
    bytes.set(part, offset);
    offset += part.length;
  }
  return sha256bytes(bytes);
}

/**
 * @param {string} value
 * @param {string} [name]
 */
function assertHash(value, name = 'hash') {
  if (typeof value !== 'string' || !HASH_HEX_RE.test(value)) {
    throw new Error(`${name} must be a lowercase 64-character hex SHA-256 digest`);
  }
}

/**
 * @param {string} hex
 * @returns {Uint8Array}
 */
function hexToBytes(hex) {
  assertHash(hex);
  return Uint8Array.from(Buffer.from(hex, 'hex'));
}

/**
 * @param {*} value
 * @param {string} name
 */
function assertArray(value, name) {
  if (!Array.isArray(value)) throw new Error(`${name} must be an array`);
}

/**
 * @param {number} index
 * @param {number} leafCount
 */
function assertIndex(index, leafCount) {
  if (!Number.isInteger(leafCount) || leafCount < 1) throw new Error('leafCount must be a positive integer');
  if (!Number.isInteger(index) || index < 0 || index >= leafCount) throw new Error('index out of range');
}

/**
 * @param {*} sibling
 */
function assertSibling(sibling) {
  if (!sibling || typeof sibling !== 'object') throw new Error('sibling must be an object');
  if (sibling.side !== 'left' && sibling.side !== 'right') throw new Error('sibling.side must be left or right');
  assertHash(sibling.hash, 'sibling.hash');
}

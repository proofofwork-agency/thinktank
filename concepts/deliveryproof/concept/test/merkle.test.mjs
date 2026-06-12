import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildMerkleProof,
  buildMerkleTree,
  emptyMerkleRoot,
  merkleLeafHash,
  merkleNodeHash,
  merkleRoot,
  sortedMerkleLeaves,
  verifyMerkleProof,
} from '../src/protocol/merkle.mjs';

const rows = [
  { id: 3, city: 'Zurich' },
  { id: 1, city: 'Amsterdam' },
  { id: 2, city: 'Berlin' },
];

test('merkle: root is presentation-independent and leaves are sorted by canonical row bytes', () => {
  const reordered = [rows[1], rows[2], rows[0]];
  assert.equal(merkleRoot(rows), merkleRoot(reordered));

  const leaves = sortedMerkleLeaves(rows);
  assert.deepEqual(leaves.map((leaf) => leaf.value.id), [1, 2, 3]);
  assert.deepEqual(leaves.map((leaf) => leaf.originalIndex), [1, 2, 0]);
  assert.match(merkleRoot(rows), /^[0-9a-f]{64}$/);
});

test('merkle: empty, single, odd, and duplicate leaf sets are deterministic', () => {
  assert.match(emptyMerkleRoot(), /^[0-9a-f]{64}$/);
  assert.equal(merkleRoot([]), emptyMerkleRoot());

  const single = [{ id: 1 }];
  assert.equal(merkleRoot(single), merkleLeafHash(single[0]));
  assert.equal(verifyMerkleProof(buildMerkleProof(single, 0)), true);

  const odd = merkleRoot([{ id: 1 }, { id: 2 }, { id: 3 }]);
  const oddAgain = merkleRoot([{ id: 3 }, { id: 1 }, { id: 2 }]);
  assert.equal(odd, oddAgain);

  const duplicates = [{ id: 1 }, { id: 1 }, { id: 2 }];
  const firstDuplicate = buildMerkleProof(duplicates, 0);
  const secondDuplicate = buildMerkleProof(duplicates, 1);
  assert.equal(firstDuplicate.leaf.id, 1);
  assert.equal(secondDuplicate.leaf.id, 1);
  assert.notDeepEqual(firstDuplicate.siblings, secondDuplicate.siblings);
  assert.equal(verifyMerkleProof(firstDuplicate), true);
  assert.equal(verifyMerkleProof(secondDuplicate), true);
});

test('merkle: odd node carry-up avoids duplicate-last ambiguity', () => {
  const three = merkleRoot([{ id: 1 }, { id: 2 }, { id: 3 }]);
  const duplicatedLast = merkleRoot([{ id: 1 }, { id: 2 }, { id: 3 }, { id: 3 }]);
  assert.notEqual(three, duplicatedLast);
});

test('merkle: proof verification rejects out-of-range index and tampered siblings', () => {
  const proof = buildMerkleProof(rows, 1);
  assert.equal(verifyMerkleProof(proof), true);

  assert.equal(verifyMerkleProof({ ...proof, index: proof.leafCount }), false);
  assert.equal(verifyMerkleProof({ ...proof, leafCount: 0 }), false);
  assert.equal(verifyMerkleProof({ ...proof, siblings: [{ ...proof.siblings[0], side: proof.siblings[0].side === 'left' ? 'right' : 'left' }] }), false);
  assert.equal(verifyMerkleProof({ ...proof, siblings: [{ ...proof.siblings[0], hash: '0'.repeat(64) }] }), false);
  assert.equal(verifyMerkleProof({ ...proof, siblings: [...proof.siblings, { side: 'left', hash: proof.siblings[0].hash }] }), false);
});

test('merkle: proof verification rejects a forged leaf made from an internal node', () => {
  const left = merkleLeafHash({ id: 1 });
  const right = merkleLeafHash({ id: 2 });
  const internal = merkleNodeHash(left, right);
  const forgedLeaf = `${left}${right}`;

  assert.notEqual(merkleLeafHash(forgedLeaf), internal);
  assert.equal(
    verifyMerkleProof({
      root: internal,
      leaf: forgedLeaf,
      index: 0,
      leafCount: 1,
      siblings: [],
    }),
    false,
  );
});

test('merkle: proofs for all odd-count leaves verify and remain index-specific', () => {
  const tree = buildMerkleTree(rows);
  for (const leaf of tree.leaves) {
    const proof = buildMerkleProof(rows, leaf.index);
    assert.equal(proof.root, tree.root);
    assert.equal(proof.leafCount, tree.leafCount);
    assert.deepEqual(proof.leaf, leaf.value);
    assert.equal(verifyMerkleProof(proof), true);

    const wrongIndex = (proof.index + 1) % proof.leafCount;
    assert.equal(verifyMerkleProof({ ...proof, index: wrongIndex }), false);
  }
});

test('merkle: helper fails closed on malformed proof shapes', () => {
  assert.throws(() => buildMerkleProof([], 0), /leafCount must be a positive integer|index out of range/);
  assert.equal(verifyMerkleProof(null), false);
  assert.equal(verifyMerkleProof({ root: 'not-hex', leaf: {}, index: 0, leafCount: 1, siblings: [] }), false);
  assert.equal(verifyMerkleProof({ root: merkleRoot([{ id: 1 }]), leaf: { id: 1 }, index: 0, leafCount: 1, siblings: [{ side: 'up', hash: '0'.repeat(64) }] }), false);
});

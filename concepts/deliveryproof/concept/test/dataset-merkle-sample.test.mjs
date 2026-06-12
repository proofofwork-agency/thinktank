import test from 'node:test';
import assert from 'node:assert/strict';

import { buildMerkleProof, emptyMerkleRoot, merkleRoot } from '../src/protocol/merkle.mjs';
import { selectSampleIndices } from '../src/protocol/merkle-sample.mjs';
import { datasetMerkleSampleVerifier, verifyInclusionSample } from '../src/verifiers/dataset-merkle-sample.mjs';

const rows = [
  { id: 3, region: 'eu', revenue: 30, active: true },
  { id: 1, region: 'us', revenue: 10, active: true },
  { id: 5, region: 'apac', revenue: 50, active: false },
  { id: 2, region: 'eu', revenue: 20, active: true },
  { id: 4, region: 'us', revenue: 40, active: false },
  { id: 6, region: 'apac', revenue: 60, active: true },
];

function contract(overrides = {}) {
  return {
    id: 'partial-dataset-contract',
    nonce: overrides.nonce ?? 'partial-dataset-nonce',
    predicate: {
      kind: 'dataset-merkle-sample',
      params: {
        merkleRoot: overrides.root ?? merkleRoot(rows),
        rowCount: overrides.rowCount ?? rows.length,
        k: overrides.k ?? 3,
        columns: overrides.columns ?? [
          { name: 'id', type: 'number', required: true, range: { min: 1 } },
          { name: 'region', type: 'string', required: true, domain: ['us', 'eu', 'apac'], regex: '^(us|eu|apac)$' },
          { name: 'revenue', type: 'number', required: true, range: { min: 0, max: 100 } },
          { name: 'active', type: 'boolean', required: true },
        ],
        ...overrides.params,
      },
    },
  };
}

function evidenceFor(c = contract(), sourceRows = rows) {
  const { merkleRoot: root, rowCount, k } = c.predicate.params;
  const indices = selectSampleIndices(c.nonce, root, rowCount, k);
  return {
    merkleSamples: indices.map((index) => {
      const proof = buildMerkleProof(sourceRows, index);
      return { index, row: proof.leaf, proof };
    }),
  };
}

test('dataset-merkle-sample: valid sample proves inclusion plus sampled-row conformance only', () => {
  const c = contract();
  const verdict = verifyInclusionSample(c, evidenceFor(c), { now: () => 123 });

  assert.equal(verdict.ok, true);
  assert.equal(verdict.checkedAt, 123);
  assert.equal(verdict.verifier, 'dataset-merkle-sample');
  assert.match(verdict.reason, /inclusion \+ sampled-row conformance only, NOT full-dataset truth/);
  assert.equal(verdict.merkleSample.root, c.predicate.params.merkleRoot);
  assert.equal(verdict.merkleSample.rowCount, rows.length);
  assert.equal(verdict.merkleSample.samples.length, c.predicate.params.k);
  assert.equal(datasetMerkleSampleVerifier.name, 'dataset-merkle-sample');
});

test('dataset-merkle-sample: sample array order is irrelevant but selected index set is exact', () => {
  const c = contract();
  const e = evidenceFor(c);

  assert.equal(verifyInclusionSample(c, { merkleSamples: [...e.merkleSamples].reverse() }).ok, true);
});

test('dataset-merkle-sample: leaf/row mismatch rejected when proof is for row A but sample row is row B', () => {
  const c = contract();
  const e = evidenceFor(c);
  e.merkleSamples[0] = {
    ...e.merkleSamples[0],
    row: { ...e.merkleSamples[0].row, revenue: e.merkleSamples[0].row.revenue + 1 },
  };

  const verdict = verifyInclusionSample(c, e);
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /proof leaf must match/);
  assert.equal(verdict.diff.reason, 'leaf-row binding mismatch');
});

test('dataset-merkle-sample: cherry-pick wrong, extra, missing, and duplicate indices are rejected', () => {
  const c = contract({ k: 2 });
  const e = evidenceFor(c);
  const selected = new Set(e.merkleSamples.map((s) => s.index));
  const unselected = [...Array(rows.length).keys()].find((index) => !selected.has(index));
  const extraProof = buildMerkleProof(rows, unselected);

  const wrong = {
    merkleSamples: [
      { index: unselected, row: extraProof.leaf, proof: extraProof },
      e.merkleSamples[1],
    ],
  };
  assert.match(verifyInclusionSample(c, wrong).reason, /missing verifier-selected|extra Merkle sample/);

  const extra = { merkleSamples: [...e.merkleSamples, { index: unselected, row: extraProof.leaf, proof: extraProof }] };
  assert.match(verifyInclusionSample(c, extra).reason, /cover exactly/);

  const missing = { merkleSamples: e.merkleSamples.slice(1) };
  assert.match(verifyInclusionSample(c, missing).reason, /cover exactly/);

  const duplicate = { merkleSamples: [e.merkleSamples[0], e.merkleSamples[0]] };
  assert.match(verifyInclusionSample(c, duplicate).reason, /duplicate/);
});

test('dataset-merkle-sample: wrong leafCount from smaller tree is rejected', () => {
  const c = contract({ k: 1 });
  const e = evidenceFor(c);
  e.merkleSamples[0] = {
    ...e.merkleSamples[0],
    proof: { ...e.merkleSamples[0].proof, leafCount: rows.length - 1 },
  };

  const verdict = verifyInclusionSample(c, e);
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /leafCount/);
});

test('dataset-merkle-sample: k must prove at least one row for non-empty datasets and never throw', () => {
  const zero = verifyInclusionSample(contract({ k: 0 }), { merkleSamples: [] });
  assert.equal(zero.ok, false);
  assert.match(zero.reason, /at least 1/);

  const tooLarge = verifyInclusionSample(contract({ k: 10_001 }), { merkleSamples: [] });
  assert.equal(tooLarge.ok, false);
  assert.match(tooLarge.reason, /10000/);
});

test('dataset-merkle-sample: proof leaf rejects prototype-pollution keys before hashing', () => {
  const c = contract({ k: 1 });
  const e = evidenceFor(c);
  e.merkleSamples[0] = {
    ...e.merkleSamples[0],
    proof: {
      ...e.merkleSamples[0].proof,
      leaf: JSON.parse('{"id":1,"__proto__":{"polluted":true}}'),
    },
  };

  const verdict = verifyInclusionSample(c, e);
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /prototype-pollution/i);
});

test('dataset-merkle-sample: oversized sampled rows and proof leaves are rejected before hashing', () => {
  const c = contract({ k: 1 });
  const e = evidenceFor(c);
  const oversized = 'x'.repeat(65_537);

  const oversizedSample = {
    merkleSamples: [{
      ...e.merkleSamples[0],
      row: { ...e.merkleSamples[0].row, oversized },
    }],
  };
  const sampleVerdict = verifyInclusionSample(c, oversizedSample);
  assert.equal(sampleVerdict.ok, false);
  assert.match(sampleVerdict.reason, /exceeds max 65536/);

  const oversizedProofLeaf = {
    merkleSamples: [{
      ...e.merkleSamples[0],
      proof: { ...e.merkleSamples[0].proof, leaf: { ...e.merkleSamples[0].proof.leaf, oversized } },
    }],
  };
  const proofVerdict = verifyInclusionSample(c, oversizedProofLeaf);
  assert.equal(proofVerdict.ok, false);
  assert.match(proofVerdict.reason, /exceeds max 65536/);
});

test('dataset-merkle-sample: out-of-range index is rejected', () => {
  const c = contract({ k: 1 });
  const e = evidenceFor(c);
  e.merkleSamples[0] = {
    ...e.merkleSamples[0],
    index: rows.length,
    proof: { ...e.merkleSamples[0].proof, index: rows.length },
  };

  const verdict = verifyInclusionSample(c, e);
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /out of committed rowCount range|cover exactly/);
});

test('dataset-merkle-sample: tampered sibling is rejected', () => {
  const c = contract({ k: 1 });
  const e = evidenceFor(c);
  e.merkleSamples[0] = {
    ...e.merkleSamples[0],
    proof: {
      ...e.merkleSamples[0].proof,
      siblings: e.merkleSamples[0].proof.siblings.map((sibling, i) => (i === 0 ? { ...sibling, hash: '0'.repeat(64) } : sibling)),
    },
  };

  const verdict = verifyInclusionSample(c, e);
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /Merkle inclusion proof failed/);
});

test('dataset-merkle-sample: per-row column conformance is enforced', () => {
  const badRows = [{ id: 1, region: 'moon', revenue: 10, active: true }];
  const c = contract({ root: merkleRoot(badRows), rowCount: badRows.length, k: 1 });
  const e = evidenceFor(c, badRows);

  const verdict = verifyInclusionSample(c, e);
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /outside the allowed domain/);
});

test('dataset-merkle-sample: row-level optional nullable and regex constraints work', () => {
  const localRows = [
    { id: 1, code: 'us-001', note: null },
    { id: 2, code: 'eu-002' },
  ];
  const c = contract({
    root: merkleRoot(localRows),
    rowCount: localRows.length,
    k: 2,
    columns: [
      { name: 'id', type: 'number', required: true },
      { name: 'code', type: 'string', required: true, regex: '^(us|eu)-\\d{3}$' },
      { name: 'note', type: 'string', required: false, nullable: true },
    ],
  });

  assert.equal(verifyInclusionSample(c, evidenceFor(c, localRows)).ok, true);
});

test('dataset-merkle-sample: global-only constraints are rejected fail-closed', () => {
  for (const params of [
    { uniqueKeys: [['id']] },
    { aggregates: [{ column: 'revenue', op: 'sum', expected: 210 }] },
    { datasetHash: '0'.repeat(64) },
    { sample: { k: 1, sampleDigest: 'x' } },
    { sampleDigest: 'x' },
    { format: 'json' },
  ]) {
    const verdict = verifyInclusionSample(contract({ params }), evidenceFor(contract()));
    assert.equal(verdict.ok, false);
    assert.match(verdict.reason, /does not prove global constraint/);
  }
});

test('dataset-merkle-sample: oversized column and domain specs are rejected', () => {
  const c = contract({
    columns: [
      { name: 'region', type: 'string', required: true, domain: Array.from({ length: 10_001 }, (_, i) => `v${i}`) },
    ],
  });
  const verdict = verifyInclusionSample(c, evidenceFor(contract()));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /domain length exceeds/);
});

test('dataset-merkle-sample: empty committed dataset requires empty root and no samples', () => {
  const c = contract({ root: emptyMerkleRoot(), rowCount: 0, k: 3 });
  assert.equal(verifyInclusionSample(c, { merkleSamples: [] }).ok, true);

  const failed = verifyInclusionSample(contract({ root: merkleRoot([{ id: 1 }]), rowCount: 0, k: 3 }), { merkleSamples: [] });
  assert.equal(failed.ok, false);
  assert.match(failed.reason, /empty Merkle root/);
});

import test from 'node:test';
import assert from 'node:assert/strict';

import { canonicalize, sha256hex, sha256utf8 } from '../src/protocol/canonical.mjs';
import { generateKeypair, sign, keyId } from '../src/protocol/crypto.mjs';
import { merkleRoot, verifyMerkleProof } from '../src/protocol/merkle.mjs';
import { verifiers, getVerifier } from '../src/verifiers/index.mjs';
import { schemaVerifier } from '../src/verifiers/schema.mjs';
import { hashVerifier } from '../src/verifiers/hash.mjs';
import { testsuiteVerifier } from '../src/verifiers/testsuite.mjs';
import { transcriptVerifier } from '../src/verifiers/transcript.mjs';
import { datasetVerifier } from '../src/verifiers/dataset.mjs';
import { datasetMerkleSampleVerifier } from '../src/verifiers/dataset-merkle-sample.mjs';
import { documentVerifier } from '../src/verifiers/document.mjs';
import { composeVerifier } from '../src/verifiers/compose.mjs';

/** Build minimal evidence for an output, computing the bound outputHash. */
function evidenceFor(output, extra = {}) {
  return {
    contractId: 'c1',
    nonce: 'n1',
    output,
    outputHash: sha256hex(output),
    producedAt: 0,
    ...extra,
  };
}

/** Assert the common Verdict shape and tier on any verifier result. */
function assertVerdictShape(verdict, expectedVerifier) {
  assert.equal(typeof verdict.ok, 'boolean');
  assert.equal(verdict.tier, 'A');
  assert.equal(verdict.verifier, expectedVerifier);
  assert.equal(typeof verdict.reason, 'string');
  assert.ok(verdict.reason.length > 0, 'reason must be non-empty');
  assert.equal(typeof verdict.checkedAt, 'number');
}

test('registry: getVerifier returns each built-in and throws on unknown', () => {
  assert.equal(getVerifier('schema'), schemaVerifier);
  assert.equal(getVerifier('hash'), hashVerifier);
  assert.equal(getVerifier('testsuite'), testsuiteVerifier);
  assert.equal(getVerifier('transcript'), transcriptVerifier);
  assert.equal(getVerifier('dataset'), datasetVerifier);
  assert.equal(getVerifier('dataset-merkle-sample'), datasetMerkleSampleVerifier);
  assert.equal(getVerifier('document'), documentVerifier);
  assert.equal(getVerifier('compose'), composeVerifier);
  assert.equal(verifiers.schema, schemaVerifier);
  assert.equal(verifiers.dataset, datasetVerifier);
  assert.equal(verifiers['dataset-merkle-sample'], datasetMerkleSampleVerifier);
  assert.equal(verifiers.document, documentVerifier);
  assert.equal(verifiers.compose, composeVerifier);
  assert.throws(() => getVerifier('nope'), /unknown verifier/);
});

// --- schema verifier ---------------------------------------------------------

test('schema verifier: pass on matching shape', () => {
  const contract = {
    predicate: {
      kind: 'schema',
      params: {
        schema: {
          type: 'object',
          required: ['name', 'age'],
          properties: { name: { type: 'string' }, age: { type: 'number' } },
        },
      },
    },
  };
  const verdict = schemaVerifier.verify(contract, evidenceFor({ name: 'Ada', age: 36 }));
  assertVerdictShape(verdict, 'schema');
  assert.equal(verdict.ok, true);
});

test('schema verifier: pass on nested array-of-objects shape', () => {
  const contract = {
    predicate: {
      kind: 'schema',
      params: {
        schema: {
          type: 'array',
          items: { type: 'object', properties: { id: { type: 'number' } } },
        },
      },
    },
  };
  const verdict = schemaVerifier.verify(contract, evidenceFor([{ id: 1 }, { id: 2 }]));
  assert.equal(verdict.ok, true);
});

test('schema verifier: fail on missing required property', () => {
  const contract = {
    predicate: {
      kind: 'schema',
      params: {
        schema: { type: 'object', required: ['email'], properties: { email: { type: 'string' } } },
      },
    },
  };
  const verdict = schemaVerifier.verify(contract, evidenceFor({ name: 'no email here' }));
  assertVerdictShape(verdict, 'schema');
  assert.equal(verdict.ok, false);
});

test('schema verifier: fail on wrong primitive type', () => {
  const contract = {
    predicate: { kind: 'schema', params: { schema: { type: 'object', properties: { age: { type: 'number' } } } } },
  };
  const verdict = schemaVerifier.verify(contract, evidenceFor({ age: 'not-a-number' }));
  assert.equal(verdict.ok, false);
});

test('schema verifier: fail when no schema provided', () => {
  const verdict = schemaVerifier.verify({ predicate: { kind: 'schema', params: {} } }, evidenceFor({}));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /schema is required/);
});

// --- hash verifier -----------------------------------------------------------

test('hash verifier: pass when output hash matches expected', () => {
  const output = { result: [1, 2, 3], meta: { ok: true } };
  const contract = { predicate: { kind: 'hash', params: { expectedHash: sha256hex(output) } } };
  const verdict = hashVerifier.verify(contract, evidenceFor(output));
  assertVerdictShape(verdict, 'hash');
  assert.equal(verdict.ok, true);
});

test('hash verifier: hash is canonical (key-order independent)', () => {
  // expectedHash committed from one key order; output delivered in another.
  const committed = sha256hex({ a: 1, b: 2 });
  const contract = { predicate: { kind: 'hash', params: { expectedHash: committed } } };
  const verdict = hashVerifier.verify(contract, evidenceFor({ b: 2, a: 1 }));
  assert.equal(verdict.ok, true);
});

test('hash verifier: fail on mismatched output', () => {
  const contract = { predicate: { kind: 'hash', params: { expectedHash: sha256hex({ a: 1 }) } } };
  const verdict = hashVerifier.verify(contract, evidenceFor({ a: 999 }));
  assertVerdictShape(verdict, 'hash');
  assert.equal(verdict.ok, false);
});

test('hash verifier: fail when no expectedHash provided', () => {
  const verdict = hashVerifier.verify({ predicate: { kind: 'hash', params: {} } }, evidenceFor({}));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /expectedHash/);
});

// --- testsuite verifier (objective replay) -----------------------------------

test('testsuite verifier: pass on correct sort', async () => {
  const contract = { predicate: { kind: 'testsuite', params: { op: 'sort', input: [5, 3, 9, 1] } } };
  const verdict = await testsuiteVerifier.verify(contract, evidenceFor([1, 3, 5, 9]));
  assertVerdictShape(verdict, 'testsuite');
  assert.equal(verdict.ok, true);
});

test('testsuite verifier: pass on sum, unique, reverse', async () => {
  const sum = await testsuiteVerifier.verify(
    { predicate: { kind: 'testsuite', params: { op: 'sum', input: [1, 2, 3, 4] } } },
    evidenceFor(10),
  );
  assert.equal(sum.ok, true);

  const unique = await testsuiteVerifier.verify(
    { predicate: { kind: 'testsuite', params: { op: 'unique', input: [1, 1, 2, 2, 3] } } },
    evidenceFor([1, 2, 3]),
  );
  assert.equal(unique.ok, true);

  const reverse = await testsuiteVerifier.verify(
    { predicate: { kind: 'testsuite', params: { op: 'reverse', input: [1, 2, 3] } } },
    evidenceFor([3, 2, 1]),
  );
  assert.equal(reverse.ok, true);
});

test('testsuite verifier: fail on wrong (cheating) sort output', async () => {
  const contract = { predicate: { kind: 'testsuite', params: { op: 'sort', input: [5, 3, 9, 1] } } };
  const verdict = await testsuiteVerifier.verify(contract, evidenceFor([9, 5, 3, 1]));
  assertVerdictShape(verdict, 'testsuite');
  assert.equal(verdict.ok, false);
});

test('testsuite verifier: fail on unsupported op', async () => {
  const contract = { predicate: { kind: 'testsuite', params: { op: 'factorize', input: [12] } } };
  const verdict = await testsuiteVerifier.verify(contract, evidenceFor([2, 2, 3]));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /could not compute reference/);
});

// --- transcript verifier (nonce-bound signed attestation) --------------------

/** Build evidence carrying a valid nonce-bound signed attestation. */
function transcriptEvidence({ contractId, nonce, output, signWith, signMessage }) {
  const outputHash = sha256hex(output);
  const message = signMessage ?? canonicalize({ contractId, nonce, outputHash });
  const signature = sign(signWith.privateKey, message);
  return {
    contractId,
    nonce,
    output,
    outputHash,
    producedAt: 0,
    attestations: [
      { signerKeyId: keyId(signWith.publicKey), publicKey: signWith.publicKey, signature, nonce },
    ],
  };
}

test('transcript verifier: pass on valid nonce-bound signature', () => {
  const seller = generateKeypair();
  const contract = { id: 'c1', nonce: 'n1', seller: keyId(seller.publicKey), predicate: { kind: 'transcript', params: {} } };
  const evidence = transcriptEvidence({
    contractId: 'c1',
    nonce: 'n1',
    output: { answer: 42 },
    signWith: seller,
  });
  const verdict = transcriptVerifier.verify(contract, evidence);
  assertVerdictShape(verdict, 'transcript');
  assert.equal(verdict.ok, true);
});

test('transcript verifier: fail when signature is tampered (byte flipped)', () => {
  const seller = generateKeypair();
  const contract = { id: 'c1', nonce: 'n1', seller: keyId(seller.publicKey), predicate: { kind: 'transcript', params: {} } };
  const evidence = transcriptEvidence({
    contractId: 'c1',
    nonce: 'n1',
    output: { answer: 42 },
    signWith: seller,
  });
  const sig = evidence.attestations[0].signature;
  evidence.attestations[0].signature = (sig[0] === 'A' ? 'B' : 'A') + sig.slice(1);
  const verdict = transcriptVerifier.verify(contract, evidence);
  assert.equal(verdict.ok, false);
});

test('transcript verifier: fail on nonce mismatch (replay protection)', () => {
  const seller = generateKeypair();
  // Seller signs for the wrong nonce.
  const evidence = transcriptEvidence({
    contractId: 'c1',
    nonce: 'WRONG',
    output: { answer: 42 },
    signWith: seller,
  });
  const contract = { id: 'c1', nonce: 'n1', seller: keyId(seller.publicKey), predicate: { kind: 'transcript', params: {} } };
  const verdict = transcriptVerifier.verify(contract, evidence);
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /nonce/);
});

test('transcript verifier: fail when the output is swapped after signing (output binding)', () => {
  // The verifier recomputes outputHash from evidence.output and checks the
  // signature over canonical({contractId, nonce, outputHash}). So swapping the
  // delivered output after the seller signed breaks the binding: the signature
  // no longer verifies for the new output's hash.
  const seller = generateKeypair();
  const evidence = transcriptEvidence({
    contractId: 'c1',
    nonce: 'n1',
    output: { answer: 42 },
    signWith: seller,
  });
  // Swap the delivered output (and its self-reported hash) post-signature.
  evidence.output = { answer: 0 };
  evidence.outputHash = sha256hex(evidence.output);
  const contract = { id: 'c1', nonce: 'n1', seller: keyId(seller.publicKey), predicate: { kind: 'transcript', params: {} } };
  const verdict = transcriptVerifier.verify(contract, evidence);
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /signature does not verify/);
});

test('transcript verifier: fail when signer is not the contracted seller', () => {
  const seller = generateKeypair();
  const stranger = generateKeypair();
  const contract = { id: 'c1', nonce: 'n1', seller: keyId(seller.publicKey), predicate: { kind: 'transcript', params: {} } };
  const evidence = transcriptEvidence({
    contractId: 'c1',
    nonce: 'n1',
    output: { answer: 42 },
    signWith: stranger,
  });
  const verdict = transcriptVerifier.verify(contract, evidence);
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /not authorized/);
});

test('transcript verifier: pass when signer is explicitly allowed', () => {
  const seller = generateKeypair();
  const attester = generateKeypair();
  const contract = {
    id: 'c1',
    nonce: 'n1',
    seller: keyId(seller.publicKey),
    predicate: { kind: 'transcript', params: { allowedSignerKeyIds: [keyId(attester.publicKey)] } },
  };
  const evidence = transcriptEvidence({
    contractId: 'c1',
    nonce: 'n1',
    output: { answer: 42 },
    signWith: attester,
  });
  const verdict = transcriptVerifier.verify(contract, evidence);
  assert.equal(verdict.ok, true);
});

test('transcript verifier: fail when attestation is missing', () => {
  const seller = generateKeypair();
  const contract = { id: 'c1', nonce: 'n1', seller: keyId(seller.publicKey), predicate: { kind: 'transcript', params: {} } };
  const verdict = transcriptVerifier.verify(contract, evidenceFor({ answer: 42 }));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /attestations\[0\] is required/);
});

// --- dataset verifier (DEEP tabular correctness) -----------------------------
//
// These tests mirror the existing verifier tests: they reuse evidenceFor and
// assertVerdictShape, and drive each ordered check (i)-(v) to both pass and fail.

/** Build a deterministic N-row table of {id, region, revenue, churned}. */
function buildRows(n) {
  const regions = ['us', 'eu', 'apac'];
  const rows = [];
  for (let i = 0; i < n; i++) {
    rows.push({
      id: i + 1,
      region: regions[i % regions.length],
      revenue: (i % 10) + 1, // 1..10, fully determined
      churned: i % 2 === 0,
    });
  }
  return rows;
}

/** The column spec the buyer commits for buildRows() tables. */
function datasetColumns() {
  return [
    { name: 'id', type: 'number', required: true, nullable: false, range: { min: 1 } },
    { name: 'region', type: 'string', required: true, nullable: false, domain: ['us', 'eu', 'apac'] },
    { name: 'revenue', type: 'number', required: true, nullable: false, range: { min: 0, max: 1000 }, maxNullRate: 0 },
    { name: 'churned', type: 'boolean', required: true, nullable: false },
  ];
}

/** Dataset commitment used to derive the verifier-side sample seed. */
function datasetHashFor(rows) {
  return sha256hex(rows);
}

/** Recompute the verifier-derived sample seed for a set of rows. */
function sampleSeedFor(nonce, rows) {
  return sha256utf8(`${nonce}|${datasetHashFor(rows)}`);
}

/** Recompute the committed sample digest for a set of rows (matches the verifier). */
function sampleDigestFor(rows, nonce, k) {
  const seed = sampleSeedFor(nonce, rows);
  const keyed = rows.map((row, i) => ({ i, key: sha256utf8(`${seed}:${i}`) }));
  keyed.sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : a.i - b.i));
  const selected = keyed.slice(0, Math.min(k, keyed.length)).map((e) => rows[e.i]);
  return sha256hex(selected);
}

/** Sum a numeric column over rows. */
function sumColumn(rows, column) {
  return rows.reduce((acc, r) => acc + r[column], 0);
}

/** Average a numeric column over rows. */
function avgColumn(rows, column) {
  return sumColumn(rows, column) / rows.length;
}

/** A full, correct dataset contract for an N-row table (with sample + aggregate). */
function datasetContract(n, { nonce = 'nonce-dataset-test', k = 5 } = {}) {
  const rows = buildRows(n);
  return {
    id: 'dataset-contract',
    nonce,
    predicate: {
      kind: 'dataset',
      params: {
        format: 'json',
        columns: datasetColumns(),
        rowCount: { min: n, max: n },
        uniqueKeys: [['id']],
        sample: { k, sampleDigest: sampleDigestFor(rows, nonce, k) },
        aggregates: [
          { column: 'revenue', op: 'sum', expected: sumColumn(rows, 'revenue') },
          { column: 'region', op: 'distinct', expected: 3 },
        ],
      },
    },
  };
}

test('dataset verifier: pass on a fully-correct dataset (all checks i-vi)', () => {
  const n = 30;
  const contract = datasetContract(n);
  const verdict = datasetVerifier.verify(contract, evidenceFor(buildRows(n)));
  assertVerdictShape(verdict, 'dataset');
  assert.equal(verdict.ok, true);
  assert.match(verdict.reason, /30 rows/);
});

test('dataset verifier: pass on a quote-free CSV deliverable', () => {
  // Same logical table, delivered as CSV. format:'csv' so cells are coerced.
  const n = 6;
  const rows = buildRows(n);
  const header = 'id,region,revenue,churned';
  const body = rows.map((r) => `${r.id},${r.region},${r.revenue},${r.churned}`).join('\n');
  const csv = header + '\n' + body;
  const seed = 'csv-seed';
  const k = 3;
  const contract = {
    nonce: 'nonce-csv',
    predicate: {
      kind: 'dataset',
      params: {
        format: 'csv',
        columns: datasetColumns(),
        rowCount: { min: n, max: n },
        // The committed digest is computed over the PARSED (coerced) rows.
        sample: { k, sampleDigest: sampleDigestFor(rows, 'nonce-csv', k) },
        aggregates: [{ column: 'revenue', op: 'sum', expected: sumColumn(rows, 'revenue') }],
      },
    },
  };
  const verdict = datasetVerifier.verify(contract, evidenceFor(csv));
  assert.equal(verdict.ok, true);
});

test('dataset verifier: fail (i) on a missing declared column', () => {
  const n = 5;
  const rows = buildRows(n).map(({ id, region, revenue }) => ({ id, region, revenue })); // drop "churned"
  const contract = datasetContract(n);
  const verdict = datasetVerifier.verify(contract, evidenceFor(rows));
  assertVerdictShape(verdict, 'dataset');
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /missing required column "churned"/);
  assert.deepEqual(verdict.diff, {
    field: 'churned',
    expected: 'present',
    actual: 'missing',
    row: 0,
    reason: 'required column missing',
  });
});

test('dataset verifier: fail (ii) on rowCount outside [min,max]', () => {
  const contract = datasetContract(10); // commits rowCount {min:10,max:10}
  const verdict = datasetVerifier.verify(contract, evidenceFor(buildRows(9))); // one short
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /rowCount 9 is below the agreed minimum 10/);
});

test('dataset verifier: fail (iii) on wrong field type', () => {
  const n = 5;
  const rows = buildRows(n);
  rows[2].revenue = 'not-a-number';
  const contract = datasetContract(n);
  const verdict = datasetVerifier.verify(contract, evidenceFor(rows));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /column "revenue" row 2: expected number/);
});

test('dataset verifier: fail (iii) on out-of-domain value', () => {
  const n = 5;
  const rows = buildRows(n);
  rows[1].region = 'antarctica'; // outside ['us','eu','apac']
  const contract = datasetContract(n);
  const verdict = datasetVerifier.verify(contract, evidenceFor(rows));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /outside the allowed domain/);
});

test('dataset verifier: fail (iii) on out-of-range numeric value', () => {
  const n = 5;
  const rows = buildRows(n);
  rows[0].revenue = 99999; // above range.max 1000
  const contract = datasetContract(n);
  const verdict = datasetVerifier.verify(contract, evidenceFor(rows));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /above range\.max 1000/);
});

test('dataset verifier: fail (iii) on null-rate over the agreed maximum', () => {
  const n = 4;
  const rows = buildRows(n);
  rows[0].revenue = null; // 1/4 = 0.25 > maxNullRate 0
  const contract = datasetContract(n);
  contract.predicate.params.columns = datasetColumns().map((col) =>
    col.name === 'revenue' ? { ...col, nullable: true, maxNullRate: 0 } : col,
  );
  const verdict = datasetVerifier.verify(contract, evidenceFor(rows));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /null-rate .* exceeds maxNullRate 0/);
});

test('dataset verifier: fail (iii) on null when nullable is not true', () => {
  const n = 4;
  const rows = buildRows(n);
  rows[0].revenue = null;
  const contract = datasetContract(n);
  const verdict = datasetVerifier.verify(contract, evidenceFor(rows));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /nullable must be true/);
  assert.equal(verdict.diff.field, 'revenue');
  assert.equal(verdict.diff.row, 0);
});

test('dataset verifier: regex field constraints pass and fail deterministically', () => {
  const rows = [
    { id: 1, email: 'ada@example.com' },
    { id: 2, email: 'grace@example.com' },
  ];
  const contract = {
    predicate: {
      kind: 'dataset',
      params: {
        format: 'json',
        columns: [
          { name: 'id', type: 'number', required: true, nullable: false },
          {
            name: 'email',
            type: 'string',
            required: true,
            nullable: false,
            regex: '^[^@]+@example\\.com$',
          },
        ],
        rowCount: { min: 2, max: 2 },
      },
    },
  };

  assert.equal(datasetVerifier.verify(contract, evidenceFor(rows)).ok, true);

  const tampered = [{ ...rows[0] }, { ...rows[1], email: 'grace@evil.test' }];
  const verdict = datasetVerifier.verify(contract, evidenceFor(tampered));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /does not match regex/);
  assert.deepEqual(verdict.diff, {
    field: 'email',
    expected: '/^[^@]+@example\\.com$/',
    actual: 'grace@evil.test',
    row: 1,
    reason: 'regex mismatch',
  });
});

test('dataset verifier: regex constraints are only valid on string columns', () => {
  const verdict = datasetVerifier.verify(
    {
      predicate: {
        kind: 'dataset',
        params: {
          columns: [{ name: 'id', type: 'number', regex: '^\\d+$' }],
          rowCount: { min: 1, max: 1 },
        },
      },
    },
    evidenceFor([{ id: 1 }]),
  );
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /regex requires string/);
});

test('dataset verifier: regex constraints are bounded to a conservative subset', () => {
  const nested = datasetVerifier.verify(
    {
      predicate: {
        kind: 'dataset',
        params: {
          columns: [{ name: 'code', type: 'string', regex: '(a+)+$' }],
          rowCount: { min: 1, max: 1 },
        },
      },
    },
    evidenceFor([{ code: 'aaaa' }]),
  );
  assert.equal(nested.ok, false);
  assert.match(nested.reason, /safe subset/);
  assert.match(nested.diff.reason, /nested quantified groups/);

  const longInput = datasetVerifier.verify(
    {
      predicate: {
        kind: 'dataset',
        params: {
          columns: [{ name: 'code', type: 'string', regex: '^a+$' }],
          rowCount: { min: 1, max: 1 },
        },
      },
    },
    evidenceFor([{ code: 'a'.repeat(513) }]),
  );
  assert.equal(longInput.ok, false);
  assert.match(longInput.reason, /regex input exceeds/);
  assert.equal(longInput.diff.reason, 'regex input too long');
});

test('dataset verifier: invalid regex sources fail before row scanning', () => {
  const verdict = datasetVerifier.verify(
    {
      predicate: {
        kind: 'dataset',
        params: {
          columns: [{ name: 'email', type: 'string', regex: '[' }],
          rowCount: { min: 1, max: 1 },
        },
      },
    },
    evidenceFor([{ email: 'ada@example.com' }]),
  );
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /regex is invalid/);
});

test('dataset verifier: fail (iv) on duplicate unique key', () => {
  const n = 5;
  const rows = buildRows(n);
  rows[3].id = rows[1].id;
  const contract = datasetContract(n);
  const verdict = datasetVerifier.verify(contract, evidenceFor(rows));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /unique key .* duplicate/);
  assert.equal(verdict.diff.field, 'id');
  assert.equal(verdict.diff.reason, 'duplicate key first seen at row 1');
});

test('dataset verifier: fail (v) on sample-digest mismatch (silent row tampering)', () => {
  const n = 30;
  const contract = datasetContract(n);
  // Deliver tampered rows: same shape/types/domain/range, but EVERY revenue is
  // shifted by a constant. Shifting every row guarantees every verifier-selected
  // sample row changes, so the committed sampleDigest must mismatch regardless of
  // which indices the seed picks (this is exactly silent content tampering on a
  // table that still looks well-formed). We recompute the aggregate's expected so
  // ONLY the digest check fails; the verifier checks the digest (iv) before
  // aggregates (v), so the reason must be the digest mismatch.
  const tampered = buildRows(n).map((r) => ({ ...r, revenue: r.revenue + 1 }));
  contract.predicate.params.aggregates = [
    { column: 'revenue', op: 'sum', expected: sumColumn(tampered, 'revenue') },
  ];
  const verdict = datasetVerifier.verify(contract, evidenceFor(tampered));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /sample digest mismatch/);
  assert.equal(verdict.diff.field, 'sample.sampleDigest');
});

test('dataset verifier: fail (vi) on a violated aggregate invariant', () => {
  const n = 20;
  const contract = datasetContract(n);
  // Override the committed sum so it is wrong, leaving the deliverable honest.
  // (Sample is over the honest rows, so it still matches; only the aggregate fails.)
  contract.predicate.params.aggregates = [
    { column: 'revenue', op: 'sum', expected: sumColumn(buildRows(n), 'revenue') + 1 },
  ];
  const verdict = datasetVerifier.verify(contract, evidenceFor(buildRows(n)));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /aggregate sum\(revenue\)/);
  assert.deepEqual(verdict.diff, {
    field: 'revenue',
    expected: sumColumn(buildRows(n), 'revenue') + 1,
    actual: sumColumn(buildRows(n), 'revenue'),
    row: null,
    reason: 'aggregate sum mismatch',
  });
});

test('dataset verifier: aggregate tolerance allows a bounded deviation', () => {
  const n = 10;
  const rows = buildRows(n);
  const trueSum = sumColumn(rows, 'revenue');
  const contract = {
    predicate: {
      kind: 'dataset',
      params: {
        columns: datasetColumns(),
        rowCount: { min: n, max: n },
        aggregates: [{ column: 'revenue', op: 'sum', expected: trueSum + 2, tolerance: 3 }],
      },
    },
  };
  const verdict = datasetVerifier.verify(contract, evidenceFor(rows));
  assert.equal(verdict.ok, true);
});

test('dataset verifier: avg and count aggregate invariants pass', () => {
  const n = 10;
  const rows = buildRows(n);
  const contract = {
    predicate: {
      kind: 'dataset',
      params: {
        columns: datasetColumns(),
        rowCount: { min: n, max: n },
        aggregates: [
          { column: 'revenue', op: 'avg', expected: avgColumn(rows, 'revenue') },
          { column: 'region', op: 'count', expected: n },
        ],
      },
    },
  };
  const verdict = datasetVerifier.verify(contract, evidenceFor(rows));
  assert.equal(verdict.ok, true);
});

test('dataset verifier: avg and count aggregate mismatches return structured diffs', () => {
  const n = 10;
  const rows = buildRows(n);
  const avgContract = {
    predicate: {
      kind: 'dataset',
      params: {
        columns: datasetColumns(),
        rowCount: { min: n, max: n },
        aggregates: [{ column: 'revenue', op: 'avg', expected: avgColumn(rows, 'revenue') + 1 }],
      },
    },
  };
  const avgVerdict = datasetVerifier.verify(avgContract, evidenceFor(rows));
  assert.equal(avgVerdict.ok, false);
  assert.match(avgVerdict.reason, /aggregate avg\(revenue\)/);
  assert.deepEqual(avgVerdict.diff, {
    field: 'revenue',
    expected: avgColumn(rows, 'revenue') + 1,
    actual: avgColumn(rows, 'revenue'),
    row: null,
    reason: 'aggregate avg mismatch',
  });

  const countContract = {
    predicate: {
      kind: 'dataset',
      params: {
        columns: datasetColumns(),
        rowCount: { min: n, max: n },
        aggregates: [{ column: 'region', op: 'count', expected: n - 1 }],
      },
    },
  };
  const countVerdict = datasetVerifier.verify(countContract, evidenceFor(rows));
  assert.equal(countVerdict.ok, false);
  assert.match(countVerdict.reason, /aggregate count\(region\)/);
  assert.equal(countVerdict.diff.field, 'region');
  assert.equal(countVerdict.diff.actual, n);
  assert.equal(countVerdict.diff.reason, 'aggregate count mismatch');
});

test('dataset verifier: RFC-4180 CSV quoted fields parse commas, newlines, and escaped quotes', () => {
  const csv = 'id,note,score\n1,"hello, world",10\n2,"line one\nline ""two""",11';
  const contract = {
    predicate: {
      kind: 'dataset',
      params: {
        format: 'csv',
        columns: [
          { name: 'id', type: 'number' },
          { name: 'note', type: 'string', regex: '^(hello, world|line one\\nline "two")$' },
          { name: 'score', type: 'number' },
        ],
        rowCount: { min: 2, max: 2 },
        aggregates: [{ column: 'score', op: 'sum', expected: 21 }],
      },
    },
  };
  const verdict = datasetVerifier.verify(contract, evidenceFor(csv));
  assert.equal(verdict.ok, true);
});

test('dataset verifier: malformed RFC-4180 CSV quoting fails closed', () => {
  const contract = {
    predicate: {
      kind: 'dataset',
      params: {
        format: 'csv',
        columns: [{ name: 'id', type: 'number' }, { name: 'note', type: 'string' }],
        rowCount: { min: 1, max: 10 },
      },
    },
  };

  const unterminated = datasetVerifier.verify(contract, evidenceFor('id,note\n1,"hello'));
  assert.equal(unterminated.ok, false);
  assert.match(unterminated.reason, /unterminated quoted field/);

  const quoteInsideUnquoted = datasetVerifier.verify(contract, evidenceFor('id,note\n1,he"llo'));
  assert.equal(quoteInsideUnquoted.ok, false);
  assert.match(quoteInsideUnquoted.reason, /quote inside an unquoted field/);

  const textAfterClosingQuote = datasetVerifier.verify(contract, evidenceFor('id,note\n1,"hello"x'));
  assert.equal(textAfterClosingQuote.ok, false);
  assert.match(textAfterClosingQuote.reason, /non-comma text after a closing quote/);
});

test('dataset verifier: CSV parser is bounded before row checks complete', () => {
  const contract = {
    predicate: {
      kind: 'dataset',
      params: {
        format: 'csv',
        columns: [{ name: 'id', type: 'number' }, { name: 'note', type: 'string' }],
        rowCount: { min: 1, max: 1 },
      },
    },
  };

  const tooManyRows = datasetVerifier.verify(contract, evidenceFor('id,note\n1,ok\n2,extra'));
  assert.equal(tooManyRows.ok, false);
  assert.match(tooManyRows.reason, /CSV data row count exceeds max 1/);

  const tooLargeCell = datasetVerifier.verify(
    { ...contract, predicate: { ...contract.predicate, params: { ...contract.predicate.params, rowCount: { min: 1, max: 2 } } } },
    evidenceFor(`id,note\n1,${'a'.repeat(65_537)}`),
  );
  assert.equal(tooLargeCell.ok, false);
  assert.match(tooLargeCell.reason, /CSV cell exceeds 65536 characters/);
});

test('dataset verifier: determinism — same nonce+datasetHash yields identical sampleDigest', () => {
  const n = 50;
  const rows = buildRows(n);
  const nonce = 'determinism-nonce';
  const k = 8;
  const params = {
    columns: datasetColumns(),
    rowCount: { min: n, max: n },
    sample: { k, sampleDigest: sampleDigestFor(rows, nonce, k) },
  };
  const contract = { nonce, predicate: { kind: 'dataset', params } };
  const v1 = datasetVerifier.verify(contract, evidenceFor(rows));
  const v2 = datasetVerifier.verify(contract, evidenceFor(rows));
  assert.equal(v1.ok, true);
  assert.equal(v2.ok, true);
  // The committed digest is stable across independent recomputations.
  assert.equal(sampleDigestFor(rows, nonce, k), sampleDigestFor(rows, nonce, k));
  assert.notEqual(sampleDigestFor(rows, nonce, k), sampleDigestFor(rows, 'other-nonce', k));
});

test('dataset verifier: optional datasetHash commitments and evidence hashes are checked', () => {
  const rows = buildRows(6);
  const contract = datasetContract(6);
  contract.predicate.params.datasetHash = datasetHashFor(rows);
  assert.equal(datasetVerifier.verify(contract, evidenceFor(rows, { datasetHash: datasetHashFor(rows) })).ok, true);

  const wrongEvidenceHash = datasetVerifier.verify(contract, evidenceFor(rows, { datasetHash: sha256hex('wrong') }));
  assert.equal(wrongEvidenceHash.ok, false);
  assert.match(wrongEvidenceHash.reason, /evidence\.datasetHash mismatch/);

  const wrongCommittedHash = datasetVerifier.verify(
    { ...contract, predicate: { ...contract.predicate, params: { ...contract.predicate.params, datasetHash: sha256hex('wrong') } } },
    evidenceFor(rows),
  );
  assert.equal(wrongCommittedHash.ok, false);
  assert.match(wrongCommittedHash.reason, /datasetHash mismatch/);
});

test('dataset verifier: committed merkleRoot matches the full sorted row set', () => {
  const rows = buildRows(12);
  const contract = datasetContract(12, { k: 4 });
  contract.predicate.params.merkleRoot = merkleRoot(rows);

  const verdict = datasetVerifier.verify(contract, evidenceFor(rows));
  assert.equal(verdict.ok, true);
  assert.match(verdict.reason, /merkle root matched/);

  const tampered = buildRows(12);
  tampered[3] = { ...tampered[3], revenue: tampered[3].revenue + 1 };
  const tamperedContract = datasetContract(12, { k: 4 });
  tamperedContract.predicate.params.merkleRoot = merkleRoot(rows);
  tamperedContract.predicate.params.sample.sampleDigest = sampleDigestFor(tampered, tamperedContract.nonce, 4);
  tamperedContract.predicate.params.aggregates = [
    { column: 'revenue', op: 'sum', expected: sumColumn(tampered, 'revenue') },
    { column: 'region', op: 'distinct', expected: 3 },
  ];

  const failed = datasetVerifier.verify(tamperedContract, evidenceFor(tampered));
  assert.equal(failed.ok, false);
  assert.match(failed.reason, /merkleRoot mismatch/);
  assert.equal(failed.diff.field, 'merkleRoot');
});

test('dataset verifier: emits verifiable Merkle proofs for seeded sample rows', () => {
  const rows = buildRows(20);
  const k = 5;
  const contract = datasetContract(20, { k });
  contract.predicate.params.merkleRoot = merkleRoot(rows);

  const verdict = datasetVerifier.verify(contract, evidenceFor(rows));
  assert.equal(verdict.ok, true);
  assert.equal(verdict.merkle.root, contract.predicate.params.merkleRoot);
  assert.equal(verdict.merkle.leafCount, rows.length);
  assert.equal(verdict.merkle.proofs.length, k);

  for (const proof of verdict.merkle.proofs) {
    assert.equal(proof.root, verdict.merkle.root);
    assert.equal(proof.leafCount, verdict.merkle.leafCount);
    assert.equal(verifyMerkleProof(proof), true);
    assert.equal(verifyMerkleProof({ ...proof, leaf: { ...proof.leaf, revenue: proof.leaf.revenue + 1 } }), false);
  }
});

test('dataset verifier: merkleRoot requires the existing rowCount.max build bound', () => {
  const rows = buildRows(2);
  const verdict = datasetVerifier.verify(
    {
      nonce: 'merkle-bound',
      predicate: {
        kind: 'dataset',
        params: {
          columns: datasetColumns(),
          rowCount: { min: 2 },
          merkleRoot: merkleRoot(rows),
        },
      },
    },
    evidenceFor(rows),
  );
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /rowCount\.max/);
});

test('dataset verifier: fail when spec is missing required fields', () => {
  const noColumns = datasetVerifier.verify(
    { predicate: { kind: 'dataset', params: { rowCount: { min: 0, max: 1 } } } },
    evidenceFor([]),
  );
  assert.equal(noColumns.ok, false);
  assert.match(noColumns.reason, /non-empty columns array/);

  const noRowCount = datasetVerifier.verify(
    { predicate: { kind: 'dataset', params: { columns: datasetColumns() } } },
    evidenceFor(buildRows(1)),
  );
  assert.equal(noRowCount.ok, false);
  assert.match(noRowCount.reason, /rowCount/);
});

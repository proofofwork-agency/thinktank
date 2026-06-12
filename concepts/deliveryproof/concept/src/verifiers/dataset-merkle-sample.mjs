// src/verifiers/dataset-merkle-sample.mjs
// Tier A partial verifier: Merkle inclusion + sampled-row conformance only.
//
// This verifier intentionally does NOT prove full dataset truth. It checks that
// verifier-selected sorted leaf indices are included in a committed Merkle root and
// that the supplied rows satisfy row-level column constraints. Global properties
// such as uniqueness, aggregates, datasetHash, or full rowCount truth require the
// full dataset verifier.

import { merkleLeafHash, verifyMerkleProof, emptyMerkleRoot } from '../protocol/merkle.mjs';
import { selectSampleIndices } from '../protocol/merkle-sample.mjs';
import { assertNoPrototypePollutionKeys, checkedAt as checkedAtFrom } from '../protocol/runtime.mjs';

/** @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('../protocol/types.mjs').DeliveryEvidence} DeliveryEvidence */
/** @typedef {import('../protocol/types.mjs').Verdict} Verdict */

const NAME = 'dataset-merkle-sample';
const TIER = 'A';
const HASH_HEX_RE = /^[0-9a-f]{64}$/;
const MAX_REGEX_SOURCE_CHARS = 128;
const MAX_REGEX_CELL_CHARS = 512;
const MAX_SAMPLE_K = 10_000;
const MAX_PARTIAL_COLUMNS = 10_000;
const MAX_PARTIAL_DOMAIN_VALUES = 10_000;
const MAX_PARTIAL_ROW_FIELDS = 10_000;
const MAX_PARTIAL_CELL_CHARS = 65_536;
const FORBIDDEN_GLOBAL_KEYS = ['uniqueKeys', 'aggregates', 'datasetHash', 'sample', 'sampleDigest', 'format'];

/**
 * Verify partial Merkle samples outside the full dataset verifier.
 *
 * @param {DeliveryContract} contract
 * @param {DeliveryEvidence} evidence
 * @param {{now?:()=>number}} [opts]
 * @returns {Verdict}
 */
export function verifyInclusionSample(contract, evidence, opts = {}) {
  const checkedAt = checkedAtFrom(opts);
  const params = contract?.predicate?.params;
  if (!params || typeof params !== 'object') {
    return fail('contract.predicate.params is required for dataset-merkle-sample', checkedAt);
  }
  const invalidGlobal = FORBIDDEN_GLOBAL_KEYS.find((key) => params[key] !== undefined);
  if (invalidGlobal !== undefined) {
    return fail(
      `dataset-merkle-sample does not prove global constraint "${invalidGlobal}"`,
      checkedAt,
      diff({ field: invalidGlobal, expected: 'absent in partial mode', actual: params[invalidGlobal], reason: 'global constraint not proven' }),
    );
  }

  const { merkleRoot, rowCount, k, columns } = params;
  if (typeof contract?.nonce !== 'string' || contract.nonce.length === 0) {
    return fail('contract.nonce is required for partial Merkle sample selection', checkedAt);
  }
  if (typeof merkleRoot !== 'string' || !HASH_HEX_RE.test(merkleRoot)) {
    return fail('merkleRoot must be a lowercase 64-character hex SHA-256 digest', checkedAt, diff({
      field: 'merkleRoot',
      expected: 'lowercase 64-character hex SHA-256 digest',
      actual: merkleRoot,
      reason: 'invalid merkle root',
    }));
  }
  if (!Number.isSafeInteger(rowCount) || rowCount < 0) {
    return fail('rowCount must be a non-negative safe integer for partial Merkle mode', checkedAt, diff({
      field: 'rowCount',
      expected: 'non-negative safe integer',
      actual: rowCount,
      reason: 'invalid rowCount',
    }));
  }
  if (!Number.isSafeInteger(k) || k < 0 || k > MAX_SAMPLE_K) {
    return fail(`k must be a non-negative safe integer <= ${MAX_SAMPLE_K} for partial Merkle mode`, checkedAt, diff({
      field: 'k',
      expected: `non-negative safe integer <= ${MAX_SAMPLE_K}`,
      actual: k,
      reason: 'invalid k',
    }));
  }
  if (rowCount > 0 && k === 0) {
    return fail('k must be at least 1 when rowCount is greater than 0', checkedAt, diff({
      field: 'k',
      expected: 'integer >= 1 for non-empty committed datasets',
      actual: k,
      reason: 'empty sample would prove no rows',
    }));
  }
  if (!Array.isArray(columns) || columns.length === 0) {
    return fail('dataset-merkle-sample requires a non-empty columns array', checkedAt);
  }
  if (columns.length > MAX_PARTIAL_COLUMNS) {
    return fail(`dataset-merkle-sample columns length exceeds max ${MAX_PARTIAL_COLUMNS}`, checkedAt, diff({
      field: 'columns.length',
      expected: `<= ${MAX_PARTIAL_COLUMNS}`,
      actual: columns.length,
      reason: 'too many columns',
    }));
  }

  const regexByColumn = new Map();
  for (const col of columns) {
    const err = validateColumn(col);
    if (err !== null) return fail(err.reason, checkedAt, err.diff);
    if (col.regex !== undefined) {
      try {
        regexByColumn.set(col.name, new RegExp(col.regex));
      } catch (err) {
        return fail(`column "${col.name}" regex is invalid: ${err.message}`, checkedAt, diff({
          field: col.name,
          expected: 'valid regex source',
          actual: col.regex,
          reason: 'invalid regex constraint',
        }));
      }
    }
  }

  let expectedIndices;
  try {
    expectedIndices = selectSampleIndices(contract.nonce, merkleRoot, rowCount, k);
  } catch (err) {
    return fail(`could not derive verifier-selected Merkle sample indices: ${err.message}`, checkedAt, diff({
      field: 'k',
      expected: `valid sample policy with k <= ${MAX_SAMPLE_K}`,
      actual: k,
      reason: 'sample selection failed',
    }));
  }
  if (rowCount === 0 && merkleRoot !== emptyMerkleRoot()) {
    return fail('empty partial Merkle sample requires the empty Merkle root', checkedAt, diff({
      field: 'merkleRoot',
      expected: emptyMerkleRoot(),
      actual: merkleRoot,
      reason: 'empty root mismatch',
    }));
  }

  const samples = evidence?.merkleSamples;
  if (!Array.isArray(samples)) {
    return fail('evidence.merkleSamples must be an array', checkedAt);
  }
  if (samples.length !== expectedIndices.length) {
    return fail('evidence.merkleSamples must cover exactly the verifier-selected indices', checkedAt, diff({
      field: 'evidence.merkleSamples.length',
      expected: expectedIndices.length,
      actual: samples.length,
      reason: 'wrong sample count',
    }));
  }

  const byIndex = new Map();
  for (const sample of samples) {
    if (!sample || typeof sample !== 'object') return fail('each merkle sample must be an object', checkedAt);
    if (!Number.isInteger(sample.index) || sample.index < 0 || sample.index >= rowCount) {
      return fail('sample index out of committed rowCount range', checkedAt, diff({
        field: 'sample.index',
        expected: `[0, ${rowCount})`,
        actual: sample.index,
        reason: 'out of range',
      }));
    }
    if (byIndex.has(sample.index)) {
      return fail('duplicate Merkle sample index', checkedAt, diff({
        field: 'sample.index',
        expected: 'unique verifier-selected index',
        actual: sample.index,
        reason: 'duplicate',
      }));
    }
    byIndex.set(sample.index, sample);
  }

  for (const index of expectedIndices) {
    if (!byIndex.has(index)) {
      return fail('missing verifier-selected Merkle sample index', checkedAt, diff({
        field: 'sample.index',
        expected: index,
        actual: [...byIndex.keys()].sort((a, b) => a - b),
        reason: 'missing selected index',
      }));
    }
  }
  for (const index of byIndex.keys()) {
    if (!expectedIndices.includes(index)) {
      return fail('extra Merkle sample index not selected by verifier seed', checkedAt, diff({
        field: 'sample.index',
        expected: expectedIndices,
        actual: index,
        reason: 'extra unselected index',
      }));
    }
  }

  const verified = [];
  for (const index of expectedIndices) {
    const sample = byIndex.get(index);
    const proof = sample.proof;
    if (!proof || typeof proof !== 'object') return fail('sample proof must be an object', checkedAt);
    if (proof.root !== merkleRoot) {
      return fail('proof root does not match committed Merkle root', checkedAt, diff({
        field: 'proof.root',
        expected: merkleRoot,
        actual: proof.root,
        reason: 'root mismatch',
      }));
    }
    if (proof.leafCount !== rowCount) {
      return fail('proof leafCount does not match committed rowCount', checkedAt, diff({
        field: 'proof.leafCount',
        expected: rowCount,
        actual: proof.leafCount,
        reason: 'leafCount mismatch',
      }));
    }
    if (proof.index !== index || sample.index !== index) {
      return fail('proof index does not match verifier-selected sample index', checkedAt, diff({
        field: 'proof.index',
        expected: index,
        actual: proof.index,
        reason: 'index mismatch',
      }));
    }
    if (sample.row === null || typeof sample.row !== 'object' || Array.isArray(sample.row)) {
      return fail('sample row must be an object', checkedAt, diff({
        field: 'sample.row',
        expected: 'object',
        actual: describe(sample.row),
        reason: 'invalid row',
      }));
    }
    try {
      assertNoPrototypePollutionKeys(sample.row, `sample row ${index}`);
      assertSampleRowBounds(sample.row, `sample row ${index}`);
    } catch (err) {
      return fail(err.message, checkedAt, diff({
        field: 'sample.row',
        expected: 'bounded primitive row object',
        actual: sample.row,
        reason: 'unsafe row',
      }));
    }

    if (proof.leaf !== null && typeof proof.leaf === 'object') {
      try {
        assertNoPrototypePollutionKeys(proof.leaf, `proof leaf ${index}`);
        assertSampleRowBounds(proof.leaf, `proof leaf ${index}`);
      } catch (err) {
        return fail(err.message, checkedAt, diff({
          field: 'proof.leaf',
          expected: 'bounded primitive row object',
          actual: proof.leaf,
          reason: 'unsafe proof leaf',
        }));
      }
    }

    const proofLeafHash = merkleLeafHash(proof.leaf);
    const rowLeafHash = merkleLeafHash(sample.row);
    if (proofLeafHash !== rowLeafHash) {
      return fail('proof leaf must match the supplied sample row', checkedAt, diff({
        field: 'sample.row',
        expected: proofLeafHash,
        actual: rowLeafHash,
        row: index,
        reason: 'leaf-row binding mismatch',
      }));
    }
    if (!verifyMerkleProof(proof)) {
      return fail('Merkle inclusion proof failed', checkedAt, diff({
        field: 'proof',
        expected: 'valid inclusion proof',
        actual: proof,
        row: index,
        reason: 'invalid proof',
      }));
    }

    const rowErr = checkRowConformance(sample.row, columns, regexByColumn, index);
    if (rowErr !== null) return fail(rowErr.reason, checkedAt, rowErr.diff);
    verified.push({ index, row: sample.row, leafHash: rowLeafHash });
  }

  return pass(
    'partial Merkle sample verified: inclusion + sampled-row conformance only, NOT full-dataset truth',
    checkedAt,
    { root: merkleRoot, rowCount, k, indices: expectedIndices, samples: verified },
  );
}

export const datasetMerkleSampleVerifier = {
  name: NAME,
  tier: TIER,
  verify: verifyInclusionSample,
};

function fail(reason, checkedAt, d = null) {
  const verdict = { ok: false, tier: TIER, verifier: NAME, reason, checkedAt };
  if (d !== null) verdict.diff = d;
  return verdict;
}

function pass(reason, checkedAt, merkleSample) {
  return { ok: true, tier: TIER, verifier: NAME, reason, checkedAt, merkleSample };
}

function validateColumn(col) {
  if (!col || typeof col.name !== 'string' || typeof col.type !== 'string') {
    return {
      reason: 'each column needs a string name and a string type',
      diff: diff({ field: 'columns', expected: 'column {name,type}', actual: col, reason: 'invalid column' }),
    };
  }
  if (col.name.length > MAX_PARTIAL_CELL_CHARS) {
    return {
      reason: `column name exceeds ${MAX_PARTIAL_CELL_CHARS} characters`,
      diff: diff({ field: 'columns.name', expected: `<= ${MAX_PARTIAL_CELL_CHARS} chars`, actual: col.name.length, reason: 'column name too long' }),
    };
  }
  if (col.type !== 'string' && col.type !== 'number' && col.type !== 'boolean') {
    return {
      reason: `column "${col.name}" has unsupported type "${col.type}"`,
      diff: diff({ field: col.name, expected: 'string|number|boolean', actual: col.type, reason: 'unsupported type' }),
    };
  }
  if (col.maxNullRate !== undefined) {
    return {
      reason: `dataset-merkle-sample does not prove maxNullRate for column "${col.name}"`,
      diff: diff({ field: col.name, expected: 'no maxNullRate in partial mode', actual: col.maxNullRate, reason: 'global null-rate not proven' }),
    };
  }
  if (Array.isArray(col.domain)) {
    if (col.domain.length > MAX_PARTIAL_DOMAIN_VALUES) {
      return {
        reason: `column "${col.name}" domain length exceeds ${MAX_PARTIAL_DOMAIN_VALUES}`,
        diff: diff({ field: col.name, expected: `domain length <= ${MAX_PARTIAL_DOMAIN_VALUES}`, actual: col.domain.length, reason: 'domain too large' }),
      };
    }
    for (const value of col.domain) {
      const err = primitiveCellError(value, `column "${col.name}" domain value`);
      if (err !== null) {
        return {
          reason: err,
          diff: diff({ field: col.name, expected: 'bounded primitive domain values', actual: describe(value), reason: 'invalid domain value' }),
        };
      }
    }
  }
  if (col.range !== undefined) {
    if (col.range === null || typeof col.range !== 'object' || Array.isArray(col.range)) {
      return {
        reason: `column "${col.name}" range must be an object`,
        diff: diff({ field: col.name, expected: 'range object', actual: describe(col.range), reason: 'invalid range' }),
      };
    }
    for (const key of ['min', 'max']) {
      if (col.range[key] !== undefined && (typeof col.range[key] !== 'number' || !Number.isFinite(col.range[key]))) {
        return {
          reason: `column "${col.name}" range.${key} must be a finite number`,
          diff: diff({ field: col.name, expected: 'finite number', actual: col.range[key], reason: 'invalid range bound' }),
        };
      }
    }
  }
  if (col.regex !== undefined) {
    if (col.type !== 'string') {
      return {
        reason: `column "${col.name}" declares regex but is type "${col.type}" (regex requires string)`,
        diff: diff({ field: col.name, expected: 'string column', actual: col.type, reason: 'regex requires string column' }),
      };
    }
    if (typeof col.regex !== 'string' || col.regex.length === 0) {
      return {
        reason: `column "${col.name}" regex must be a non-empty RegExp source string`,
        diff: diff({ field: col.name, expected: 'non-empty regex source', actual: col.regex, reason: 'invalid regex constraint' }),
      };
    }
    const safetyError = regexSafetyError(col.regex);
    if (safetyError !== null) {
      return {
        reason: `column "${col.name}" regex is outside the supported safe subset: ${safetyError}`,
        diff: diff({ field: col.name, expected: 'bounded safe regex subset', actual: col.regex, reason: safetyError }),
      };
    }
  }
  return null;
}

function assertSampleRowBounds(row, label) {
  const keys = Object.keys(row);
  if (keys.length > MAX_PARTIAL_ROW_FIELDS) {
    throw new Error(`${label}: row field count exceeds max ${MAX_PARTIAL_ROW_FIELDS}`);
  }
  for (const key of keys) {
    if (key.length > MAX_PARTIAL_CELL_CHARS) {
      throw new Error(`${label}: row field name exceeds max ${MAX_PARTIAL_CELL_CHARS} characters`);
    }
    const err = primitiveCellError(row[key], `${label}.${key}`);
    if (err !== null) throw new Error(err);
  }
}

function primitiveCellError(value, label) {
  if (value === null || typeof value === 'boolean') return null;
  if (typeof value === 'string') {
    return value.length <= MAX_PARTIAL_CELL_CHARS
      ? null
      : `${label}: string cell exceeds max ${MAX_PARTIAL_CELL_CHARS} characters`;
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? null : `${label}: numeric cell must be finite`;
  }
  return `${label}: partial Merkle rows support only primitive cells`;
}

function checkRowConformance(row, columns, regexByColumn, index) {
  for (const col of columns) {
    const hasColumn = Object.prototype.hasOwnProperty.call(row, col.name);
    const value = row[col.name];
    if (!hasColumn && col.required !== false) {
      return {
        reason: `sample row ${index} is missing required column "${col.name}"`,
        diff: diff({ field: col.name, expected: 'present', actual: 'missing', row: index, reason: 'required column missing' }),
      };
    }
    if (value === null || value === undefined) {
      if (!hasColumn && col.required === false) continue;
      if (col.nullable !== true) {
        return {
          reason: `column "${col.name}" sample row ${index}: ${describe(value)} is not allowed (nullable must be true)`,
          diff: diff({ field: col.name, expected: 'non-null value', actual: describe(value), row: index, reason: 'null not allowed' }),
        };
      }
      continue;
    }
    if (!typeOk(value, col.type)) {
      return {
        reason: `column "${col.name}" sample row ${index}: expected ${col.type}, got ${describe(value)}`,
        diff: diff({ field: col.name, expected: col.type, actual: describe(value), row: index, reason: 'wrong type' }),
      };
    }
    if (Array.isArray(col.domain) && !col.domain.includes(value)) {
      return {
        reason: `column "${col.name}" sample row ${index}: value ${JSON.stringify(value)} is outside the allowed domain`,
        diff: diff({ field: col.name, expected: col.domain, actual: value, row: index, reason: 'outside domain' }),
      };
    }
    if (col.range && typeof value === 'number') {
      if (typeof col.range.min === 'number' && value < col.range.min) {
        return {
          reason: `column "${col.name}" sample row ${index}: ${value} is below range.min ${col.range.min}`,
          diff: diff({ field: col.name, expected: `>= ${col.range.min}`, actual: value, row: index, reason: 'below range.min' }),
        };
      }
      if (typeof col.range.max === 'number' && value > col.range.max) {
        return {
          reason: `column "${col.name}" sample row ${index}: ${value} is above range.max ${col.range.max}`,
          diff: diff({ field: col.name, expected: `<= ${col.range.max}`, actual: value, row: index, reason: 'above range.max' }),
        };
      }
    }
    const regex = regexByColumn.get(col.name) ?? null;
    if (regex && value.length > MAX_REGEX_CELL_CHARS) {
      return {
        reason: `column "${col.name}" sample row ${index}: regex input exceeds ${MAX_REGEX_CELL_CHARS} characters`,
        diff: diff({ field: col.name, expected: `<= ${MAX_REGEX_CELL_CHARS} chars before regex match`, actual: value.length, row: index, reason: 'regex input too long' }),
      };
    }
    if (regex && !regex.test(value)) {
      return {
        reason: `column "${col.name}" sample row ${index}: value ${JSON.stringify(value)} does not match regex /${col.regex}/`,
        diff: diff({ field: col.name, expected: `/${col.regex}/`, actual: value, row: index, reason: 'regex mismatch' }),
      };
    }
  }
  return null;
}

function regexSafetyError(source) {
  if (source.length > MAX_REGEX_SOURCE_CHARS) {
    return `regex source exceeds ${MAX_REGEX_SOURCE_CHARS} characters`;
  }
  if (/\\[1-9]/.test(source)) {
    return 'backreferences are not supported in dataset regex constraints';
  }
  if (/\(\?[=!<]/.test(source)) {
    return 'lookahead/lookbehind assertions are not supported in dataset regex constraints';
  }
  if (/\((?:[^()\\]|\\.)*[+*{](?:[^()\\]|\\.)*\)\s*[+*{]/.test(source)) {
    return 'nested quantified groups are not supported in dataset regex constraints';
  }
  if (/\((?:[^()\\]|\\.)*\|(?:[^()\\]|\\.)*\)\s*[+*{]/.test(source)) {
    return 'quantified alternation groups are not supported in dataset regex constraints';
  }
  return null;
}

function typeOk(value, type) {
  switch (type) {
    case 'string':
      return typeof value === 'string';
    case 'number':
      return typeof value === 'number' && !Number.isNaN(value);
    case 'boolean':
      return typeof value === 'boolean';
    default:
      return false;
  }
}

function describe(value) {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (Array.isArray(value)) return 'array';
  if (typeof value === 'number' && Number.isNaN(value)) return 'NaN';
  return typeof value;
}

function diff({ field, expected, actual, row = null, reason }) {
  return { field, expected, actual, row, reason };
}

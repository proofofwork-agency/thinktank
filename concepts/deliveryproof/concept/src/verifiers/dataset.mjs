// src/verifiers/dataset.mjs
// Tier A verifier: DEEP, OBJECTIVE tabular/dataset correctness.
//
// This is the verifier that closes a gap no shipped settlement rail closes: it
// gates payment on whether a delivered DATASET is actually CORRECT, not merely
// well-shaped. A competitor's shallow check (HTTP 2xx + JSON-schema shape — what
// the schema verifier in this repo models) accepts any table with the right
// columns and primitive types. This verifier additionally proves, with no third
// party and no external truth source (Tier A), that the table's CONTENT matches
// what the contract committed to.
//
// It checks IN ORDER and returns a failing Verdict on the FIRST broken check:
//   (i)   declared required columns are present and every row is parseable;
//   (ii)  rowCount is within {min,max} and the computed datasetHash matches any
//         committed/evidence hash;
//   (iii) per-field required/nullable + type + domain + range + regex + max null-rate;
//   (iv)  declared uniqueKeys are globally unique;
//   (v)   a deterministic verifier-seeded k-row sampleDigest equals a value the
//         contract committed (seed = sha256utf8(contract.nonce + "|" + datasetHash));
//   (vi)  1..N aggregate invariants (sum|distinct|min|max|avg|count on a column)
//         each equal their committed expected value, within an optional tolerance.
//
// WHY THIS IS OBJECTIVE (Tier A): every check is a pure function of (contract,
// evidence). The sampleDigest reuses the protocol's canonicalize()+sha256hex so
// buyer and verifier always agree on the bytes; nothing here trusts the seller,
// a network, an oracle, or an LLM. The contract author still owns whether the
// spec captures intent (an irreducible trust point documented in types.mjs).
//
// DELIVERABLE FORMATS:
//   - array-of-objects (the primary path) is used directly;
//   - a CSV string is parsed by a bounded, single-pass RFC-4180 parser
//     supporting quoted fields, embedded commas/newlines, and escaped "" quotes.
//
// Dataset verifier reuses local protocol hashing/canonicalization helpers.

import { canonicalize, sha256hex, sha256utf8 } from '../protocol/canonical.mjs';
import { buildMerkleTree } from '../protocol/merkle.mjs';
import { assertNoPrototypePollutionKeys, checkedAt as checkedAtFrom, safeRecord } from '../protocol/runtime.mjs';

/** @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('../protocol/types.mjs').DeliveryEvidence} DeliveryEvidence */
/** @typedef {import('../protocol/types.mjs').Verdict} Verdict */

const NAME = 'dataset';
const TIER = 'A';
const MAX_REGEX_SOURCE_CHARS = 128;
const MAX_REGEX_CELL_CHARS = 512;
const MAX_CSV_CHARS = 1_000_000;
const MAX_CSV_CELL_CHARS = 65_536;
const MAX_CSV_COLUMNS = 10_000;
const MAX_CSV_ROWS = 100_000;
const MAX_JSON_ROWS = 100_000;
const MAX_JSON_CELL_CHARS = 65_536;
const MAX_DATASET_SPEC_ITEMS = 10_000;
const HASH_HEX_RE = /^[0-9a-f]{64}$/;

/**
 * Build a failing Verdict with a precise reason.
 * @param {string} reason
 * @param {number} checkedAt
 * @param {Object|null} [diff]
 * @returns {Verdict}
 */
function fail(reason, checkedAt, diff = null) {
  const verdict = { ok: false, tier: TIER, verifier: NAME, reason, checkedAt };
  if (diff !== null) verdict.diff = diff;
  return verdict;
}

/**
 * Build a passing Verdict.
 * @param {string} reason
 * @param {number} checkedAt
 * @param {Object|null} [extra]
 * @returns {Verdict}
 */
function pass(reason, checkedAt, extra = null) {
  const verdict = { ok: true, tier: TIER, verifier: NAME, reason, checkedAt };
  if (extra?.merkle !== undefined) verdict.merkle = extra.merkle;
  return verdict;
}

/**
 * Short human-readable description of a value's runtime type for error messages.
 * @param {*} value
 * @returns {string}
 */
function describe(value) {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (Array.isArray(value)) return 'array';
  if (typeof value === 'number' && Number.isNaN(value)) return 'NaN';
  return typeof value;
}

/**
 * Build the structured first-failure diff carried on failing dataset verdicts.
 * @param {Object} params
 * @param {string} params.field
 * @param {*} params.expected
 * @param {*} params.actual
 * @param {number|null} [params.row]
 * @param {string} params.reason
 * @returns {{field:string,expected:*,actual:*,row:number|null,reason:string}}
 */
function diff({ field, expected, actual, row = null, reason }) {
  return { field, expected, actual, row, reason };
}

/**
 * Parse a CSV string into an array-of-objects with a bounded RFC-4180 state
 * machine. The first non-empty record is the header. Unquoted cells are trimmed
 * for backward compatibility with the prior quote-free parser; quoted cells are
 * kept exactly as authored except for RFC-4180 "" unescaping. Cell values are
 * converted to number / boolean / null using the same rules as JSON-array
 * deliverables so the two input paths verify identically.
 *
 * The parser is intentionally single-pass and regex-free. It fails closed on
 * malformed quoting (unterminated quoted field, quote inside unquoted field,
 * non-comma text after a closing quote) and applies document/cell/column/row
 * caps before or during parsing to bound verifier resource use.
 *
 * @param {string} text
 * @param {{rowLimit?:number}} [opts]
 * @returns {Array<Object>}
 */
function parseCsv(text, opts = {}) {
  if (text.length > MAX_CSV_CHARS) {
    throw new Error(`CSV exceeds ${MAX_CSV_CHARS} characters`);
  }

  const records = parseCsvRecords(text, opts.rowLimit);
  if (records.length === 0) {
    throw new Error('CSV is empty (no header row)');
  }
  const header = records[0].map((h) => h.trim());
  if (header.some((h) => h.length === 0)) {
    throw new Error('CSV header has an empty column name');
  }
  if (header.length > MAX_CSV_COLUMNS) {
    throw new Error(`CSV header declares ${header.length} columns, exceeding max ${MAX_CSV_COLUMNS}`);
  }
  const rows = [];
  for (let i = 1; i < records.length; i++) {
    const cells = records[i];
    if (cells.length !== header.length) {
      throw new Error(
        `CSV row ${i} has ${cells.length} fields but header declares ${header.length}`,
      );
    }
    const row = safeRecord();
    for (let c = 0; c < header.length; c++) {
      row[header[c]] = coerceCsvCell(cells[c].trim());
    }
    rows.push(row);
  }
  return rows;
}

/**
 * @param {string} text
 * @param {number|undefined} rowLimit parsed data-row cap from rowCount.max
 * @returns {string[][]}
 */
function parseCsvRecords(text, rowLimit) {
  const records = [];
  let record = [];
  let cell = '';
  let inQuotes = false;
  let quotedCell = false;
  let afterClosingQuote = false;
  let atCellStart = true;

  const maxDataRows = Number.isInteger(rowLimit) && rowLimit >= 0
    ? Math.min(rowLimit, MAX_CSV_ROWS)
    : MAX_CSV_ROWS;

  const pushCell = () => {
    record.push(quotedCell ? cell : cell.trim());
    if (record.length > MAX_CSV_COLUMNS) {
      throw new Error(`CSV record has more than ${MAX_CSV_COLUMNS} columns`);
    }
    cell = '';
    quotedCell = false;
    afterClosingQuote = false;
    atCellStart = true;
  };

  const pushRecord = () => {
    pushCell();
    if (record.length === 1 && record[0].length === 0) {
      record = [];
      return;
    }
    records.push(record);
    if (records.length > maxDataRows + 1) {
      throw new Error(`CSV data row count exceeds max ${maxDataRows}`);
    }
    record = [];
  };

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];

    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          appendCsvChar('"');
          i++;
        } else {
          inQuotes = false;
          afterClosingQuote = true;
        }
      } else {
        appendCsvChar(ch);
      }
      continue;
    }

    if (afterClosingQuote) {
      if (ch === ',') {
        pushCell();
      } else if (ch === '\r' || ch === '\n') {
        if (ch === '\r' && text[i + 1] === '\n') i++;
        pushRecord();
      } else {
        throw new Error('CSV has non-comma text after a closing quote');
      }
      continue;
    }

    if (ch === '"') {
      if (atCellStart) {
        inQuotes = true;
        quotedCell = true;
        atCellStart = false;
      } else {
        throw new Error('CSV has a quote inside an unquoted field');
      }
    } else if (ch === ',') {
      pushCell();
    } else if (ch === '\r' || ch === '\n') {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      pushRecord();
    } else {
      appendCsvChar(ch);
      atCellStart = false;
    }
  }

  if (inQuotes) throw new Error('CSV has an unterminated quoted field');
  if (afterClosingQuote || cell.length > 0 || record.length > 0) pushRecord();

  return records;

  function appendCsvChar(ch) {
    cell += ch;
    if (cell.length > MAX_CSV_CELL_CHARS) {
      throw new Error(`CSV cell exceeds ${MAX_CSV_CELL_CHARS} characters`);
    }
  }
}

/**
 * Convert a raw CSV cell string into a JS primitive so CSV and JSON-array
 * deliverables verify identically:
 *   "" -> null ; "true"/"false" -> boolean ; a finite numeric string -> number ;
 *   otherwise the string is kept as-is.
 * @param {string} cell
 * @returns {*}
 */
function coerceCsvCell(cell) {
  if (cell === '') return null;
  if (cell === 'true') return true;
  if (cell === 'false') return false;
  // Numeric: only when the whole trimmed cell is a finite JS number. We avoid
  // Number('') (=> 0) by the empty check above, and reject NaN/Infinity inputs.
  const n = Number(cell);
  if (!Number.isNaN(n) && Number.isFinite(n) && /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(cell)) {
    return n;
  }
  return cell;
}

/**
 * Stable dataset commitment over parsed rows.
 * @param {Array<Object>} rows
 * @returns {string}
 */
function datasetHashFor(rows) {
  return sha256hex(rows);
}

/**
 * The sample seed is verifier-derived from immutable contract/evidence facts,
 * never supplied by the seller or caller. This prevents seller-chosen "lucky"
 * samples.
 * @param {string} nonce
 * @param {string} datasetHash
 * @returns {string}
 */
function sampleSeedFor(nonce, datasetHash) {
  return sha256utf8(`${nonce}|${datasetHash}`);
}

/**
 * Normalize evidence.output into an array-of-row-objects, or throw with a
 * precise reason the verifier turns into a failing Verdict.
 * @param {*} output
 * @param {string|undefined} declaredFormat 'json' | 'csv' | undefined (infer)
 * @returns {Array<Object>}
 */
function toRows(output, declaredFormat, rowLimit) {
  const format = declaredFormat ?? (typeof output === 'string' ? 'csv' : 'json');
  if (format === 'csv') {
    if (typeof output !== 'string') {
      throw new Error(`format 'csv' requires a string output, got ${describe(output)}`);
    }
    return parseCsv(output, { rowLimit });
  }
  if (format === 'json') {
    if (!Array.isArray(output)) {
      throw new Error(`format 'json' requires an array-of-objects output, got ${describe(output)}`);
    }
    const maxRows = Number.isInteger(rowLimit) && rowLimit >= 0
      ? Math.min(rowLimit, MAX_JSON_ROWS)
      : MAX_JSON_ROWS;
    if (output.length > maxRows) {
      throw new Error(`JSON data row count exceeds max ${maxRows}`);
    }
    for (let i = 0; i < output.length; i++) {
      const row = output[i];
      if (row === null || typeof row !== 'object' || Array.isArray(row)) {
        throw new Error(`row ${i} is not an object (got ${describe(row)})`);
      }
      assertNoPrototypePollutionKeys(row, `row ${i}`);
      assertJsonRowBounds(row, i);
    }
    return output;
  }
  throw new Error(`unsupported dataset format "${format}" (expected 'json' or 'csv')`);
}

/**
 * Check a single cell value against a column's type. Returns true on match.
 * null/undefined are NOT type errors here — null-rate is handled separately so a
 * column can legitimately allow some nulls.
 * @param {*} value
 * @param {string} type 'string' | 'number' | 'boolean'
 * @returns {boolean}
 */
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

/**
 * Deterministically select k row indices from `n` rows using the contract seed.
 * Each index i is keyed by sha256utf8(seed + ':' + i); indices are sorted ascending
 * by that hex key (ties broken by index) and the first k are taken. The selected
 * rows are returned IN SELECTION ORDER (i.e. sorted by key), so the digest is a
 * stable function of (seed, rows) and independent of any later re-presentation.
 *
 * @param {Array<Object>} rows
 * @param {string} seed
 * @param {number} k
 * @returns {Array<Object>} the selected rows, in selection order
 */
function selectSeededRows(rows, seed, k) {
  return selectSeededRowEntries(rows, seed, k).map((entry) => entry.row);
}

/**
 * Deterministically select k row entries from `n` rows using the contract seed.
 * The original row index is retained so Merkle proofs can map the selected row
 * to its sorted leaf index without trusting presentation order.
 *
 * @param {Array<Object>} rows
 * @param {string} seed
 * @param {number} k
 * @returns {Array<{row:Object, originalIndex:number}>}
 */
function selectSeededRowEntries(rows, seed, k) {
  const keyed = rows.map((row, i) => ({ i, key: sha256utf8(`${seed}:${i}`) }));
  keyed.sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : a.i - b.i));
  const take = Math.min(k, keyed.length);
  const selected = [];
  for (let s = 0; s < take; s++) {
    selected.push({ row: rows[keyed[s].i], originalIndex: keyed[s].i });
  }
  return selected;
}

/**
 * Build an inclusion proof from an already-built tree, avoiding O(k*n)
 * recomputation when emitting proofs for verifier-seeded samples.
 *
 * @param {{root:string,leafCount:number,leaves:Array<{value:*,index:number}>,levels:string[][]}} tree
 * @param {number} index sorted leaf index
 * @returns {{root:string,leaf:*,index:number,leafCount:number,siblings:Array<{side:'left'|'right',hash:string}>}}
 */
function merkleProofFromTree(tree, index) {
  if (!Number.isInteger(index) || index < 0 || index >= tree.leafCount) {
    throw new Error('merkle proof index out of range');
  }
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
  return {
    root: tree.root,
    leaf: tree.leaves[index].value,
    index,
    leafCount: tree.leafCount,
    siblings,
  };
}

/**
 * Normalize unique key declarations. Supports both:
 *   uniqueKeys: ['id']                    // one single-column key
 *   uniqueKeys: [['tenantId', 'email']]   // one composite key
 *   uniqueKeys: [['id'], ['tenantId','email']]
 * @param {*} uniqueKeys
 * @returns {string[][]}
 */
function normalizeUniqueKeys(uniqueKeys) {
  if (uniqueKeys === undefined) return [];
  if (!Array.isArray(uniqueKeys)) {
    throw new Error('uniqueKeys must be an array of column names or column-name arrays');
  }
  if (uniqueKeys.length > MAX_DATASET_SPEC_ITEMS) {
    throw new Error(`uniqueKeys declares more than ${MAX_DATASET_SPEC_ITEMS} entries`);
  }
  if (uniqueKeys.length === 0) return [];
  if (uniqueKeys.every((k) => typeof k === 'string')) return [uniqueKeys];
  const normalized = [];
  for (const key of uniqueKeys) {
    if (typeof key === 'string') {
      normalized.push([key]);
      continue;
    }
    if (!Array.isArray(key) || key.length === 0 || !key.every((k) => typeof k === 'string')) {
      throw new Error('each uniqueKeys entry must be a string or a non-empty string[]');
    }
    if (key.length > MAX_DATASET_SPEC_ITEMS) {
      throw new Error(`uniqueKeys entry declares more than ${MAX_DATASET_SPEC_ITEMS} columns`);
    }
    normalized.push(key);
  }
  return normalized;
}

/**
 * @param {Object} row
 * @param {number} index
 */
function assertJsonRowBounds(row, index) {
  const keys = Object.keys(row);
  if (keys.length > MAX_CSV_COLUMNS) {
    throw new Error(`row ${index} declares ${keys.length} fields, exceeding max ${MAX_CSV_COLUMNS}`);
  }
  for (const key of keys) {
    if (key.length > MAX_CSV_CELL_CHARS) {
      throw new Error(`row ${index} field name exceeds ${MAX_CSV_CELL_CHARS} characters`);
    }
    const value = row[key];
    if (typeof value === 'string' && value.length > MAX_JSON_CELL_CHARS) {
      throw new Error(`row ${index} field "${key}" string exceeds ${MAX_JSON_CELL_CHARS} characters`);
    }
    if (typeof value === 'number' && !Number.isFinite(value)) {
      throw new Error(`row ${index} field "${key}" must be a finite number`);
    }
    if (value !== null && typeof value === 'object') {
      throw new Error(`row ${index} field "${key}" must be a primitive or null`);
    }
  }
}

/**
 * Stable key material for uniqueness checks.
 * @param {Object} row
 * @param {string[]} columns
 * @returns {string}
 */
function uniqueKeyValue(row, columns) {
  return columns.map((name) => `${name}=${canonicalize(row[name])}`).join('\u0000');
}

/**
 * DeliveryProof intentionally supports a conservative RegExp subset for dataset
 * cells. JavaScript RegExp is backtracking-based, so unbounded buyer-authored
 * patterns can become a verifier-side DoS surface. These checks are not a formal
 * safe-regex proof; they are a built-in guardrail that rejects common dangerous
 * constructs and caps both pattern and input size.
 *
 * @param {string} source
 * @returns {string|null} null when accepted, otherwise the rejection reason
 */
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

/**
 * Compute an aggregate over a column. Throws on a non-numeric cell where the op
 * requires numbers (the verifier turns the throw into a precise failing Verdict).
 * @param {Array<Object>} rows
 * @param {string} column
 * @param {string} op 'sum' | 'distinct' | 'min' | 'max' | 'avg' | 'count'
 * @returns {number}
 */
function aggregate(rows, column, op) {
  switch (op) {
    case 'count': {
      let count = 0;
      for (const row of rows) {
        const v = row[column];
        if (v !== null && v !== undefined) count++;
      }
      return count;
    }
    case 'distinct': {
      const seen = new Set();
      for (const row of rows) {
        const v = row[column];
        // Distinct counts non-null values; null/undefined are treated as "no value".
        if (v === null || v === undefined) continue;
        seen.add(`${typeof v}:${String(v)}`);
      }
      return seen.size;
    }
    case 'sum':
    case 'min':
    case 'max':
    case 'avg': {
      let acc = op === 'sum' ? 0 : undefined;
      let count = 0;
      let saw = false;
      for (const row of rows) {
        const v = row[column];
        if (v === null || v === undefined) continue;
        if (typeof v !== 'number' || Number.isNaN(v)) {
          throw new Error(`aggregate "${op}" on column "${column}" hit a non-number (${describe(v)})`);
        }
        saw = true;
        count++;
        if (op === 'sum') acc += v;
        else if (op === 'min') acc = acc === undefined ? v : Math.min(acc, v);
        else if (op === 'max') acc = acc === undefined ? v : Math.max(acc, v);
        else acc = acc === undefined ? v : acc + v;
      }
      if ((op === 'min' || op === 'max' || op === 'avg') && !saw) {
        throw new Error(`aggregate "${op}" on column "${column}" has no numeric values`);
      }
      if (op === 'avg') return acc / count;
      return acc;
    }
    default:
      throw new Error(`unsupported aggregate op "${op}" (expected sum|distinct|min|max|avg|count)`);
  }
}

/**
 * @type {import('../protocol/types.mjs').Verifier}
 */
export const datasetVerifier = {
  name: NAME,
  tier: TIER,
  /**
   * @param {DeliveryContract} contract
   * @param {DeliveryEvidence} evidence
   * @returns {Verdict}
   */
  verify(contract, evidence, opts = {}) {
    const checkedAt = checkedAtFrom(opts);
    const params = contract?.predicate?.params;
    if (!params || typeof params !== 'object') {
      return fail('contract.predicate.params is required for the dataset verifier', checkedAt);
    }
    const { format, columns, rowCount, sample, aggregates, uniqueKeys, merkleRoot: committedMerkleRoot } = params;

    if (!Array.isArray(columns) || columns.length === 0) {
      return fail('dataset spec requires a non-empty columns array', checkedAt);
    }
    if (columns.length > MAX_CSV_COLUMNS) {
      return fail(`dataset spec declares ${columns.length} columns, exceeding max ${MAX_CSV_COLUMNS}`, checkedAt);
    }
    const regexByColumn = new Map();
    for (const col of columns) {
      if (!col || typeof col.name !== 'string' || typeof col.type !== 'string') {
        return fail('each column needs a string name and a string type', checkedAt);
      }
      if (col.name.length > MAX_CSV_CELL_CHARS) {
        return fail(`column name exceeds ${MAX_CSV_CELL_CHARS} characters`, checkedAt);
      }
      if (col.type !== 'string' && col.type !== 'number' && col.type !== 'boolean') {
        return fail(`column "${col.name}" has unsupported type "${col.type}"`, checkedAt);
      }
      if (Array.isArray(col.domain) && col.domain.length > MAX_DATASET_SPEC_ITEMS) {
        return fail(`column "${col.name}" domain exceeds ${MAX_DATASET_SPEC_ITEMS} values`, checkedAt);
      }
      if (col.range !== undefined) {
        if (typeof col.range !== 'object' || col.range === null || Array.isArray(col.range)) {
          return fail(`column "${col.name}" range must be an object`, checkedAt);
        }
        if (col.range.min !== undefined && (typeof col.range.min !== 'number' || !Number.isFinite(col.range.min))) {
          return fail(`column "${col.name}" range.min must be a finite number`, checkedAt);
        }
        if (col.range.max !== undefined && (typeof col.range.max !== 'number' || !Number.isFinite(col.range.max))) {
          return fail(`column "${col.name}" range.max must be a finite number`, checkedAt);
        }
      }
      if (col.maxNullRate !== undefined &&
          (typeof col.maxNullRate !== 'number' || !Number.isFinite(col.maxNullRate) || col.maxNullRate < 0 || col.maxNullRate > 1)) {
        return fail(`column "${col.name}" maxNullRate must be a finite number between 0 and 1`, checkedAt);
      }
      if (col.regex !== undefined) {
        if (col.type !== 'string') {
          return fail(
            `column "${col.name}" declares regex but is type "${col.type}" (regex requires string)`,
            checkedAt,
            diff({ field: col.name, expected: 'string column', actual: col.type, reason: 'regex requires string column' }),
          );
        }
        if (typeof col.regex !== 'string' || col.regex.length === 0) {
          return fail(
            `column "${col.name}" regex must be a non-empty RegExp source string`,
            checkedAt,
            diff({ field: col.name, expected: 'non-empty regex source', actual: col.regex, reason: 'invalid regex constraint' }),
          );
        }
        const safetyError = regexSafetyError(col.regex);
        if (safetyError !== null) {
          return fail(
            `column "${col.name}" regex is outside the supported safe subset: ${safetyError}`,
            checkedAt,
            diff({ field: col.name, expected: 'bounded safe regex subset', actual: col.regex, reason: safetyError }),
          );
        }
        try {
          regexByColumn.set(col.name, new RegExp(col.regex));
        } catch (err) {
          return fail(
            `column "${col.name}" regex is invalid: ${err.message}`,
            checkedAt,
            diff({ field: col.name, expected: 'valid regex source', actual: col.regex, reason: 'invalid regex constraint' }),
          );
        }
      }
    }

    let normalizedUniqueKeys;
    try {
      normalizedUniqueKeys = normalizeUniqueKeys(uniqueKeys);
    } catch (err) {
      return fail(err.message, checkedAt, diff({
        field: 'uniqueKeys',
        expected: 'string[] or string[][]',
        actual: uniqueKeys,
        reason: err.message,
      }));
    }

    if (!rowCount || typeof rowCount !== 'object' || Array.isArray(rowCount)) {
      return fail('dataset spec requires rowCount {min,max}', checkedAt);
    }
    const { min, max } = rowCount;
    if (min !== undefined && (!Number.isInteger(min) || min < 0)) {
      return fail(
        'rowCount.min must be a non-negative integer when present',
        checkedAt,
        diff({ field: 'rowCount.min', expected: 'non-negative integer', actual: min, reason: 'invalid rowCount bound' }),
      );
    }
    if (max !== undefined && (!Number.isInteger(max) || max < 0)) {
      return fail(
        'rowCount.max must be a non-negative integer when present',
        checkedAt,
        diff({ field: 'rowCount.max', expected: 'non-negative integer', actual: max, reason: 'invalid rowCount bound' }),
      );
    }
    if (min !== undefined && max !== undefined && min > max) {
      return fail(
        'rowCount.min cannot exceed rowCount.max',
        checkedAt,
        diff({ field: 'rowCount', expected: 'min <= max', actual: rowCount, reason: 'invalid rowCount bound' }),
      );
    }

    // Parse the deliverable into rows (this also enforces "every row parseable").
    let rows;
    try {
      rows = toRows(evidence?.output, format, rowCount?.max);
    } catch (err) {
      return fail(`could not parse dataset: ${err.message}`, checkedAt);
    }
    const actualDatasetHash = datasetHashFor(rows);

    // (i) Declared required columns present in EVERY row.
    for (let r = 0; r < rows.length; r++) {
      const row = rows[r];
      for (const col of columns) {
        const hasColumn = Object.prototype.hasOwnProperty.call(row, col.name);
        if (!hasColumn && col.required !== false) {
          return fail(
            `row ${r} is missing required column "${col.name}"`,
            checkedAt,
            diff({ field: col.name, expected: 'present', actual: 'missing', row: r, reason: 'required column missing' }),
          );
        }
      }
    }

    // (ii) rowCount within {min,max}.
    if (typeof min === 'number' && rows.length < min) {
      return fail(
        `rowCount ${rows.length} is below the agreed minimum ${min}`,
        checkedAt,
        diff({ field: 'rowCount', expected: `>= ${min}`, actual: rows.length, reason: 'below minimum' }),
      );
    }
    if (typeof max === 'number' && rows.length > max) {
      return fail(
        `rowCount ${rows.length} exceeds the agreed maximum ${max}`,
        checkedAt,
        diff({ field: 'rowCount', expected: `<= ${max}`, actual: rows.length, reason: 'above maximum' }),
      );
    }
    if (typeof params.datasetHash === 'string' && params.datasetHash !== actualDatasetHash) {
      return fail(
        `datasetHash mismatch: committed ${params.datasetHash.slice(0, 16)}… but delivered table hashes to ${actualDatasetHash.slice(0, 16)}…`,
        checkedAt,
        diff({
          field: 'datasetHash',
          expected: params.datasetHash,
          actual: actualDatasetHash,
          reason: 'committed dataset hash mismatch',
        }),
      );
    }
    if (typeof evidence?.datasetHash === 'string' && evidence.datasetHash !== actualDatasetHash) {
      return fail(
        `evidence.datasetHash mismatch: evidence says ${evidence.datasetHash.slice(0, 16)}… but delivered table hashes to ${actualDatasetHash.slice(0, 16)}…`,
        checkedAt,
        diff({
          field: 'evidence.datasetHash',
          expected: actualDatasetHash,
          actual: evidence.datasetHash,
          reason: 'evidence hash does not match delivered rows',
        }),
      );
    }

    let merkleTree = null;
    if (committedMerkleRoot !== undefined) {
      if (typeof committedMerkleRoot !== 'string' || !HASH_HEX_RE.test(committedMerkleRoot)) {
        return fail(
          'merkleRoot must be a lowercase 64-character hex SHA-256 digest',
          checkedAt,
          diff({ field: 'merkleRoot', expected: 'lowercase 64-character hex SHA-256 digest', actual: committedMerkleRoot, reason: 'invalid merkle root' }),
        );
      }
      if (!Number.isInteger(max) || max < 0) {
        return fail(
          'merkleRoot verification requires rowCount.max as a non-negative integer bound',
          checkedAt,
          diff({ field: 'rowCount.max', expected: 'non-negative integer bound for merkle build', actual: max, reason: 'missing merkle build bound' }),
        );
      }
      merkleTree = buildMerkleTree(rows);
      if (merkleTree.root !== committedMerkleRoot) {
        return fail(
          `merkleRoot mismatch: committed ${committedMerkleRoot.slice(0, 16)}… but delivered rows build root ${merkleTree.root.slice(0, 16)}…`,
          checkedAt,
          diff({ field: 'merkleRoot', expected: committedMerkleRoot, actual: merkleTree.root, reason: 'committed merkle root mismatch' }),
        );
      }
    }

    // (iii) per-field required/nullable + type + domain + range + regex + max null-rate.
    for (const col of columns) {
      let nulls = 0;
      const domainSet = Array.isArray(col.domain) ? new Set(col.domain) : null;
      const regex = regexByColumn.get(col.name) ?? null;
      for (let r = 0; r < rows.length; r++) {
        const hasColumn = Object.prototype.hasOwnProperty.call(rows[r], col.name);
        const value = rows[r][col.name];
        if (value === null || value === undefined) {
          nulls++;
          if (!hasColumn && col.required === false) continue;
          if (col.nullable !== true) {
            return fail(
              `column "${col.name}" row ${r}: ${describe(value)} is not allowed (nullable must be true)`,
              checkedAt,
              diff({ field: col.name, expected: 'non-null value', actual: describe(value), row: r, reason: 'null not allowed' }),
            );
          }
          continue;
        }
        if (!typeOk(value, col.type)) {
          return fail(
            `column "${col.name}" row ${r}: expected ${col.type}, got ${describe(value)}`,
            checkedAt,
            diff({ field: col.name, expected: col.type, actual: describe(value), row: r, reason: 'wrong type' }),
          );
        }
        if (domainSet && !domainSet.has(value)) {
          return fail(
            `column "${col.name}" row ${r}: value ${JSON.stringify(value)} is outside the allowed domain`,
            checkedAt,
            diff({ field: col.name, expected: col.domain, actual: value, row: r, reason: 'outside domain' }),
          );
        }
        if (col.range && typeof value === 'number') {
          if (typeof col.range.min === 'number' && value < col.range.min) {
            return fail(
              `column "${col.name}" row ${r}: ${value} is below range.min ${col.range.min}`,
              checkedAt,
              diff({ field: col.name, expected: `>= ${col.range.min}`, actual: value, row: r, reason: 'below range.min' }),
            );
          }
          if (typeof col.range.max === 'number' && value > col.range.max) {
            return fail(
              `column "${col.name}" row ${r}: ${value} is above range.max ${col.range.max}`,
              checkedAt,
              diff({ field: col.name, expected: `<= ${col.range.max}`, actual: value, row: r, reason: 'above range.max' }),
            );
          }
        }
        if (regex && value.length > MAX_REGEX_CELL_CHARS) {
          return fail(
            `column "${col.name}" row ${r}: regex input exceeds ${MAX_REGEX_CELL_CHARS} characters`,
            checkedAt,
            diff({ field: col.name, expected: `<= ${MAX_REGEX_CELL_CHARS} chars before regex match`, actual: value.length, row: r, reason: 'regex input too long' }),
          );
        }
        if (regex && !regex.test(value)) {
          return fail(
            `column "${col.name}" row ${r}: value ${JSON.stringify(value)} does not match regex /${col.regex}/`,
            checkedAt,
            diff({ field: col.name, expected: `/${col.regex}/`, actual: value, row: r, reason: 'regex mismatch' }),
          );
        }
      }
      if (typeof col.maxNullRate === 'number' && rows.length > 0) {
        const rate = nulls / rows.length;
        if (rate > col.maxNullRate) {
          return fail(
            `column "${col.name}" null-rate ${rate.toFixed(4)} exceeds maxNullRate ${col.maxNullRate}`,
            checkedAt,
            diff({ field: col.name, expected: `null-rate <= ${col.maxNullRate}`, actual: rate, reason: 'maxNullRate exceeded' }),
          );
        }
      }
    }

    // (iv) unique key constraints.
    for (const keyColumns of normalizedUniqueKeys) {
      const seen = new Map();
      for (let r = 0; r < rows.length; r++) {
        const row = rows[r];
        for (const column of keyColumns) {
          if (!Object.prototype.hasOwnProperty.call(row, column) || row[column] === null || row[column] === undefined) {
            return fail(
              `unique key [${keyColumns.join(', ')}] row ${r}: column "${column}" is missing/null`,
              checkedAt,
              diff({ field: keyColumns.join('+'), expected: 'non-null unique key', actual: null, row: r, reason: 'unique key missing/null' }),
            );
          }
        }
        const key = uniqueKeyValue(row, keyColumns);
        if (seen.has(key)) {
          return fail(
            `unique key [${keyColumns.join(', ')}] duplicate at row ${r} (first seen at row ${seen.get(key)})`,
            checkedAt,
            diff({
              field: keyColumns.join('+'),
              expected: 'unique',
              actual: key,
              row: r,
              reason: `duplicate key first seen at row ${seen.get(key)}`,
            }),
          );
        }
        seen.set(key, r);
      }
    }

    // (v) deterministic verifier-seeded sample digest.
    let merkleProofBundle = null;
    if (sample !== undefined) {
      if (!sample || typeof sample.k !== 'number' || !Number.isInteger(sample.k) || sample.k < 0 ||
          typeof sample.sampleDigest !== 'string') {
        return fail(
          'sample must be { k:non-negative integer, sampleDigest:string }',
          checkedAt,
          diff({ field: 'sample', expected: '{ k:non-negative integer, sampleDigest:string }', actual: sample, reason: 'invalid sample spec' }),
        );
      }
      if (typeof contract?.nonce !== 'string' || contract.nonce.length === 0) {
        return fail(
          'contract.nonce is required to derive the dataset sample seed',
          checkedAt,
          diff({ field: 'contract.nonce', expected: 'non-empty string', actual: contract?.nonce, reason: 'missing sample seed input' }),
        );
      }
      const seed = sampleSeedFor(contract.nonce, actualDatasetHash);
      const selectedEntries = selectSeededRowEntries(rows, seed, sample.k);
      const selected = selectedEntries.map((entry) => entry.row);
      const digest = sha256hex(selected);
      if (digest !== sample.sampleDigest) {
        return fail(
          `sample digest mismatch: committed ${sample.sampleDigest.slice(0, 16)}… but verifier-seeded ${sample.k} rows hash to ${digest.slice(0, 16)}… (rows tampered)`,
          checkedAt,
          diff({ field: 'sample.sampleDigest', expected: sample.sampleDigest, actual: digest, reason: 'sample digest mismatch' }),
        );
      }
      if (merkleTree !== null) {
        const sortedIndexByOriginal = new Map();
        for (const leaf of merkleTree.leaves) sortedIndexByOriginal.set(leaf.originalIndex, leaf.index);
        merkleProofBundle = {
          root: merkleTree.root,
          leafCount: merkleTree.leafCount,
          proofs: selectedEntries.map((entry) => merkleProofFromTree(merkleTree, sortedIndexByOriginal.get(entry.originalIndex))),
        };
      }
    }

    // (vi) aggregate invariants.
    if (aggregates !== undefined) {
      if (!Array.isArray(aggregates)) {
        return fail('aggregates must be an array of { column, op, expected, tolerance? }', checkedAt);
      }
      if (aggregates.length > MAX_DATASET_SPEC_ITEMS) {
        return fail(`aggregates declares more than ${MAX_DATASET_SPEC_ITEMS} entries`, checkedAt);
      }
      for (const agg of aggregates) {
        if (!agg || typeof agg.column !== 'string' || typeof agg.op !== 'string') {
          return fail('each aggregate needs a string column and a string op', checkedAt);
        }
        if (typeof agg.expected !== 'number') {
          return fail(`aggregate ${agg.op}(${agg.column}) needs a numeric "expected"`, checkedAt);
        }
        if (!Number.isFinite(agg.expected)) {
          return fail(`aggregate ${agg.op}(${agg.column}) expected value must be finite`, checkedAt);
        }
        let actual;
        try {
          actual = aggregate(rows, agg.column, agg.op);
        } catch (err) {
          return fail(`could not compute aggregate: ${err.message}`, checkedAt, diff({
            field: agg.column,
            expected: `aggregate ${agg.op}`,
            actual: 'not computable',
            reason: err.message,
          }));
        }
        if (agg.tolerance !== undefined && (typeof agg.tolerance !== 'number' || !Number.isFinite(agg.tolerance) || agg.tolerance < 0)) {
          return fail(`aggregate ${agg.op}(${agg.column}) tolerance must be a non-negative finite number`, checkedAt);
        }
        const tolerance = typeof agg.tolerance === 'number' ? agg.tolerance : 0;
        if (Math.abs(actual - agg.expected) > tolerance) {
          return fail(
            `aggregate ${agg.op}(${agg.column}) = ${actual} but contract committed ${agg.expected}` +
              (tolerance > 0 ? ` (±${tolerance})` : ''),
            checkedAt,
            diff({
              field: agg.column,
              expected: agg.expected,
              actual,
              reason: `aggregate ${agg.op} mismatch`,
            }),
          );
        }
      }
    }

    return pass(
      `dataset passed all checks: ${rows.length} rows, ${columns.length} typed columns` +
        (normalizedUniqueKeys.length > 0 ? `, ${normalizedUniqueKeys.length} unique key constraint(s) held` : '') +
        (sample !== undefined ? ', verifier-seeded sample digest matched' : '') +
        (merkleTree !== null ? ', merkle root matched' : '') +
        (Array.isArray(aggregates) && aggregates.length > 0
          ? `, ${aggregates.length} aggregate invariant(s) held`
          : ''),
      checkedAt,
      merkleProofBundle !== null ? { merkle: merkleProofBundle } : null,
    );
  },
};

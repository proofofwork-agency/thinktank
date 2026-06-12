// canonical.mjs — RFC 8785-style deterministic JSON + hashing primitives.
//
// DeliveryProof signs and hashes JSON protocol records. That only works if every
// party rejects ambiguous values and computes the same bytes for the same logical
// object. This module follows the JSON Canonicalization Scheme (JCS, RFC 8785)
// shape: I-JSON values only, no whitespace, recursively sorted object keys, and
// ECMAScript JSON primitive serialization.
//
// Uses node:crypto for SHA-256 hashing.

import { createHash } from 'node:crypto';

export const PROTOCOL_VERSION = 'deliveryproof/0.4-jcs1';
export const CANONICALIZATION = 'RFC8785-JCS';
export const MAX_CANONICAL_DEPTH = 256;
export const MAX_CANONICAL_NODES = 1_000_000;
export const MAX_CANONICAL_STRING_CHARS = 1_000_000;
export const MAX_CANONICAL_OBJECT_KEYS = 100_000;

/**
 * Produce canonical JSON for an I-JSON value.
 *
 * Rules:
 *  - Object keys are sorted by UTF-16 code unit order at every depth.
 *  - Arrays keep their order and must not have holes.
 *  - Numbers must be finite.
 *  - JS-only values (`undefined`, functions, symbols, bigint), non-plain
 *    objects, accessors, `toJSON`, and lone surrogate strings are rejected.
 *
 * @param {*} value
 * @param {{maxDepth?:number,maxNodes?:number,maxStringChars?:number,maxObjectKeys?:number}} [opts]
 * @returns {string}
 */
export function canonicalize(value, opts = {}) {
  const state = canonicalState(opts);
  return serializeJcs(value, '$', state, 0);
}

/**
 * Lowercase hex SHA-256 over canonical JSON. This is the protocol commitment
 * hash for JSON values.
 *
 * @param {*} value
 * @returns {string}
 */
export function sha256jcs(value) {
  return sha256utf8(canonicalize(value));
}

/**
 * Lowercase hex SHA-256 over a UTF-8 string.
 *
 * @param {string} text
 * @returns {string}
 */
export function sha256utf8(text) {
  if (typeof text !== 'string') throw new TypeError('sha256utf8: text must be a string');
  return sha256bytes(Buffer.from(text, 'utf8'));
}

/**
 * Lowercase hex SHA-256 over raw bytes.
 *
 * @param {Uint8Array} bytes
 * @returns {string}
 */
export function sha256bytes(bytes) {
  if (!(bytes instanceof Uint8Array)) throw new TypeError('sha256bytes: bytes must be a Uint8Array');
  return createHash('sha256').update(bytes).digest('hex');
}

/**
 * Backward-compatible protocol hash entry point. Strings are now JSON strings
 * for protocol commitments; use sha256utf8() for raw text domains.
 *
 * @param {*} input
 * @returns {string}
 */
export function sha256hex(input) {
  return sha256jcs(input);
}

function canonicalState(opts) {
  return {
    nodes: 0,
    maxDepth: positiveInteger(opts.maxDepth, MAX_CANONICAL_DEPTH, 'maxDepth'),
    maxNodes: positiveInteger(opts.maxNodes, MAX_CANONICAL_NODES, 'maxNodes'),
    maxStringChars: positiveInteger(opts.maxStringChars, MAX_CANONICAL_STRING_CHARS, 'maxStringChars'),
    maxObjectKeys: positiveInteger(opts.maxObjectKeys, MAX_CANONICAL_OBJECT_KEYS, 'maxObjectKeys'),
  };
}

function positiveInteger(value, fallback, name) {
  if (value === undefined) return fallback;
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new TypeError(`canonicalize: ${name} must be a positive safe integer`);
  }
  return value;
}

function tickNode(state, path, depth) {
  state.nodes += 1;
  if (state.nodes > state.maxNodes) {
    throw new TypeError(`${path}: canonical JSON node count exceeds ${state.maxNodes}`);
  }
  if (depth > state.maxDepth) {
    throw new TypeError(`${path}: canonical JSON depth exceeds ${state.maxDepth}`);
  }
}

// Emit canonical JSON TEXT directly, building each object body from keys sorted
// by UTF-16 code unit.
//
// We deliberately do NOT normalize into a JS object and hand it to
// JSON.stringify: ECMAScript enumerates integer-index property names ("2"
// before "10") in ascending numeric order regardless of insertion order, which
// silently reorders array-index-like keys and breaks RFC 8785 / JCS ordering
// (e.g. {"10":1,"2":2} must serialize with "10" first). Constructing the string
// from the sorted key list is the only way to stay JCS-compliant for every
// valid object. For primitives, arrays, and string-keyed objects this produces
// byte-identical output to the previous JSON.stringify path.
function serializeJcs(value, path, state, depth) {
  tickNode(state, path, depth);
  const t = typeof value;
  if (value === null) return 'null';
  if (t === 'boolean') return value ? 'true' : 'false';
  if (t === 'string') {
    assertValidString(value, path, state);
    return JSON.stringify(value);
  }
  if (t === 'number') {
    if (!Number.isFinite(value)) throw new TypeError(`${path}: non-finite numbers are not valid protocol JSON`);
    return JSON.stringify(value);
  }
  if (t === 'undefined' || t === 'function' || t === 'symbol' || t === 'bigint') {
    throw new TypeError(`${path}: ${t} is not valid protocol JSON`);
  }
  if (Array.isArray(value)) {
    let body = '';
    for (let i = 0; i < value.length; i++) {
      if (!Object.prototype.hasOwnProperty.call(value, i)) {
        throw new TypeError(`${path}[${i}]: sparse arrays are not valid protocol JSON`);
      }
      if (i > 0) body += ',';
      body += serializeJcs(value[i], `${path}[${i}]`, state, depth + 1);
    }
    return `[${body}]`;
  }
  if (!isPlainObject(value)) {
    throw new TypeError(`${path}: non-plain objects are not valid protocol JSON`);
  }
  if (typeof value.toJSON === 'function') {
    throw new TypeError(`${path}: toJSON hooks are not allowed in protocol JSON`);
  }
  const symbols = Object.getOwnPropertySymbols(value);
  if (symbols.length > 0) throw new TypeError(`${path}: symbol keys are not valid protocol JSON`);

  const keys = Object.keys(value).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  if (keys.length > state.maxObjectKeys) {
    throw new TypeError(`${path}: object key count exceeds ${state.maxObjectKeys}`);
  }
  let body = '';
  let first = true;
  for (const key of keys) {
    assertValidString(key, `${path}.{key}`, state);
    const desc = Object.getOwnPropertyDescriptor(value, key);
    if (!desc || desc.get || desc.set) throw new TypeError(`${path}.${key}: accessors are not valid protocol JSON`);
    if (!first) body += ',';
    first = false;
    body += `${JSON.stringify(key)}:${serializeJcs(desc.value, `${path}.${key}`, state, depth + 1)}`;
  }
  return `{${body}}`;
}

function isPlainObject(value) {
  if (value === null || typeof value !== 'object') return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function assertValidString(value, path, state) {
  if (value.length > state.maxStringChars) {
    throw new TypeError(`${path}: string length exceeds ${state.maxStringChars}`);
  }
  for (let i = 0; i < value.length; i++) {
    const c = value.charCodeAt(i);
    if (c >= 0xd800 && c <= 0xdbff) {
      const next = value.charCodeAt(i + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) {
        throw new TypeError(`${path}: lone high surrogate is not valid I-JSON`);
      }
      i++;
    } else if (c >= 0xdc00 && c <= 0xdfff) {
      throw new TypeError(`${path}: lone low surrogate is not valid I-JSON`);
    }
  }
}

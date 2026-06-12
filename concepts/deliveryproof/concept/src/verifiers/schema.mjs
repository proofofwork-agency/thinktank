// src/verifiers/schema.mjs
// Tier A verifier: validates evidence.output against a simple recursive shape schema.
//
// The schema (contract.predicate.params.schema) is a minimal JSON-Schema-like shape:
//   { type: 'object'|'array'|'number'|'string'|'boolean',
//     properties?: { [key]: schema },   // for type 'object'
//     items?: schema,                    // for type 'array'
//     required?: string[] }              // for type 'object'
//
// This is objective (Tier A): no third-party trust, no external truth source.
// It only checks that the delivered output structurally matches the agreed shape.

/** @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('../protocol/types.mjs').DeliveryEvidence} DeliveryEvidence */
/** @typedef {import('../protocol/types.mjs').Verdict} Verdict */
import { checkedAt } from '../protocol/runtime.mjs';

const NAME = 'schema';
const TIER = 'A';
const MAX_SCHEMA_DEPTH = 128;
const MAX_SCHEMA_NODES = 100_000;
const MAX_SCHEMA_ARRAY_ITEMS = 100_000;
const MAX_SCHEMA_PROPERTIES = 10_000;
const MAX_SCHEMA_REQUIRED = 10_000;

/**
 * Recursively check a value against a simple shape schema.
 * Returns null on success, or a human-readable reason string on the first mismatch.
 *
 * @param {*} value
 * @param {*} schema
 * @param {string} path - JSON-pointer-ish path for error messages
 * @returns {string|null}
 */
function checkShape(value, schema, path, state = { nodes: 0 }, depth = 0) {
  state.nodes += 1;
  if (state.nodes > MAX_SCHEMA_NODES) {
    return `schema traversal exceeds max node count ${MAX_SCHEMA_NODES}`;
  }
  if (depth > MAX_SCHEMA_DEPTH) {
    return `schema traversal exceeds max depth ${MAX_SCHEMA_DEPTH}`;
  }
  if (schema === null || typeof schema !== 'object') {
    return `schema at ${path} is not a valid shape object`;
  }
  const expectedType = schema.type;
  if (typeof expectedType !== 'string') {
    return `schema at ${path} is missing a string "type"`;
  }

  switch (expectedType) {
    case 'object': {
      if (value === null || typeof value !== 'object' || Array.isArray(value)) {
        return `expected object at ${path}, got ${describe(value)}`;
      }
      const required = Array.isArray(schema.required) ? schema.required : [];
      if (required.length > MAX_SCHEMA_REQUIRED) {
        return `schema.required at ${path} exceeds max length ${MAX_SCHEMA_REQUIRED}`;
      }
      for (const key of required) {
        if (!Object.prototype.hasOwnProperty.call(value, key)) {
          return `missing required property "${key}" at ${path}`;
        }
      }
      const properties = (schema.properties && typeof schema.properties === 'object')
        ? schema.properties
        : {};
      const propertyKeys = Object.keys(properties);
      if (propertyKeys.length > MAX_SCHEMA_PROPERTIES) {
        return `schema.properties at ${path} exceeds max key count ${MAX_SCHEMA_PROPERTIES}`;
      }
      for (const key of propertyKeys) {
        // Only validate properties that are present; absence is governed by `required`.
        if (Object.prototype.hasOwnProperty.call(value, key)) {
          const childPath = path === '$' ? `$.${key}` : `${path}.${key}`;
          const err = checkShape(value[key], properties[key], childPath, state, depth + 1);
          if (err) return err;
        }
      }
      return null;
    }
    case 'array': {
      if (!Array.isArray(value)) {
        return `expected array at ${path}, got ${describe(value)}`;
      }
      if (value.length > MAX_SCHEMA_ARRAY_ITEMS) {
        return `array at ${path} exceeds max length ${MAX_SCHEMA_ARRAY_ITEMS}`;
      }
      if (schema.items !== undefined) {
        for (let i = 0; i < value.length; i++) {
          const err = checkShape(value[i], schema.items, `${path}[${i}]`, state, depth + 1);
          if (err) return err;
        }
      }
      return null;
    }
    case 'number': {
      // I-JSON numbers must be finite: reject NaN AND ±Infinity. The engine path
      // also blocks these via canonicalize(), but this verifier is exported and
      // used standalone, so it must enforce the protocol number boundary itself.
      if (typeof value !== 'number' || !Number.isFinite(value)) {
        return `expected number at ${path}, got ${describe(value)}`;
      }
      return null;
    }
    case 'string': {
      if (typeof value !== 'string') {
        return `expected string at ${path}, got ${describe(value)}`;
      }
      return null;
    }
    case 'boolean': {
      if (typeof value !== 'boolean') {
        return `expected boolean at ${path}, got ${describe(value)}`;
      }
      return null;
    }
    default:
      return `unsupported schema type "${expectedType}" at ${path}`;
  }
}

/**
 * Short human-readable description of a value's runtime type for error messages.
 * @param {*} value
 * @returns {string}
 */
function describe(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'array';
  if (Number.isNaN(value)) return 'NaN';
  return typeof value;
}

/**
 * @type {import('../protocol/types.mjs').Verifier}
 */
export const schemaVerifier = {
  name: NAME,
  tier: TIER,
  /**
   * @param {DeliveryContract} contract
   * @param {DeliveryEvidence} evidence
   * @returns {Verdict}
   */
  verify(contract, evidence, opts = {}) {
    const at = checkedAt(opts);
    const schema = contract?.predicate?.params?.schema;
    if (schema === undefined) {
      return {
        ok: false,
        tier: TIER,
        verifier: NAME,
        reason: 'contract.predicate.params.schema is required for the schema verifier',
        checkedAt: at,
      };
    }
    const err = checkShape(evidence?.output, schema, '$');
    if (err) {
      return {
        ok: false,
        tier: TIER,
        verifier: NAME,
        reason: `output does not match schema: ${err}`,
        checkedAt: at,
      };
    }
    return {
      ok: true,
      tier: TIER,
      verifier: NAME,
      reason: `output structurally matches the agreed ${schema.type} schema`,
      checkedAt: at,
    };
  },
};

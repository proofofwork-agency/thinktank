// src/verifiers/api-response.mjs
// Tier A verifier: DEEP correctness of a paid API / MCP tool-call RESPONSE.
//
// This is the verifier for the surface where agent commerce actually happens:
// paid HTTP APIs and MCP tool calls (x402, MCP payment wrappers, PayCrow, etc.).
// Those rails verify that payment happened and, at best, that the response was
// HTTP 2xx with a valid JSON shape. A response can be 200 + schema-valid and still
// be objectively WRONG — wrong entity, stale, or violating a numeric bound the
// buyer paid for. This verifier checks the delivered request/response transcript
// against an explicit, deterministic predicate and refuses settlement when it
// does not hold.
//
// IMPORTANT SCOPE (Tier A, honest): this proves the RESPONSE SATISFIES THE
// DECLARED PREDICATE over the captured transcript bytes — e.g. "the response for
// the city we asked about returns that same city, a fresh timestamp, and a price
// within the agreed max." It does NOT prove the external-world fact is true (that
// the real weather was 21°). External truth is a separate, non-Tier-A trust point
// (see README §3.5); provenance proofs like zkTLS would address "did this source
// really return these bytes," which composes with — but is distinct from — this.
//
// The verifier operates on a CAPTURED transcript carried in evidence.output; it
// makes NO live network calls; it is deterministic over captured transcript bytes.
//
// evidence.output shape (the captured request/response transcript):
//   {
//     contractId,                              // MUST equal contract.id   (binding, mandatory)
//     nonce,                                   // MUST equal contract.nonce (replay guard, mandatory)
//     request:  { method, url, query?, bodyHash? },   // mandatory
//     response: { status, headers?, body },    // body = parsed JSON (or any value)
//     producedAt?: number                      // ms epoch when produced (freshness)
//   }
// The contractId+nonce binding is mandatory and non-bypassable: a response captured
// for a different contract cannot be replayed into this settlement.
//
// contract.predicate.params (all checks optional; each runs only if present):
//   {
//     request?:  { method?, url?, bodyHash? },        // expected request binding
//     status?:   number | { min?, max? },             // expected status / range
//     contentType?: string,                           // exact content-type header match
//     requiredHeaders?: string[],                     // header names that must be present
//     bodySchema?: <shape>,                           // reuse schema-style shape over response.body
//     fields?: [ { path, equals?|in?|min?|max?|matches?|type?|fromRequest? } ],
//                                                     // JSON-path assertions on response.body
//     freshnessMs?: number,                           // producedAt must be within this of contract time
//     // (no eval, ever — only the declarative predicates above)
//   }
//
// Reuses local protocol hashing/canonicalization helpers.

import { canonicalize, sha256hex } from '../protocol/canonical.mjs';
import { checkedAt } from '../protocol/runtime.mjs';

/** @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('../protocol/types.mjs').DeliveryEvidence} DeliveryEvidence */
/** @typedef {import('../protocol/types.mjs').Verdict} Verdict */

const NAME = 'api-response';
const TIER = 'A';
const MAX_FIELD_REGEX_SOURCE_CHARS = 128;
const MAX_FIELD_REGEX_INPUT_CHARS = 512;
const MAX_FIELD_ASSERTIONS = 256;
const MAX_REQUIRED_HEADERS = 128;
const MAX_RESPONSE_HEADERS = 512;
const MAX_JSON_PATH_CHARS = 256;
const MAX_BODY_SCHEMA_DEPTH = 64;
const MAX_BODY_SCHEMA_NODES = 2_048;
const MAX_BODY_SCHEMA_ARRAY_ITEMS = 10_000;
const MAX_BODY_SCHEMA_PROPERTIES = 256;
const MAX_BODY_SCHEMA_REQUIRED = 256;
const MAX_FIELD_IN_OPTIONS = 1_000;

function fail(reason, at, diff) {
  const v = { ok: false, tier: TIER, verifier: NAME, reason, checkedAt: at };
  if (diff) v.diff = diff;
  return v;
}
function pass(reason, at) {
  return { ok: true, tier: TIER, verifier: NAME, reason, checkedAt: at };
}

function describe(value) {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (Array.isArray(value)) return 'array';
  if (typeof value === 'number' && Number.isNaN(value)) return 'NaN';
  return typeof value;
}

/**
 * Resolve a restricted JSON path against a value. Supports dot keys and [index]:
 *   "$.quote.price", "items[0].id", "city". Leading "$." or "$" is optional.
 * Returns { found: boolean, value }.
 * @param {*} root
 * @param {string} path
 */
function resolvePath(root, path) {
  if (typeof path !== 'string' || path.length === 0) return { found: false };
  let p = path.startsWith('$.') ? path.slice(2) : path.startsWith('$') ? path.slice(1) : path;
  // Split into tokens: keys and [index] segments.
  const tokens = [];
  const re = /[^.[\]]+|\[\d+\]/g;
  let m;
  while ((m = re.exec(p)) !== null) {
    const t = m[0];
    if (t.startsWith('[')) tokens.push(Number(t.slice(1, -1)));
    else tokens.push(t);
  }
  let cur = root;
  for (const tok of tokens) {
    if (cur === null || cur === undefined) return { found: false };
    if (typeof tok === 'number') {
      if (!Array.isArray(cur) || tok < 0 || tok >= cur.length) return { found: false };
      cur = cur[tok];
    } else {
      if (typeof cur !== 'object' || Array.isArray(cur) || !Object.prototype.hasOwnProperty.call(cur, tok)) {
        return { found: false };
      }
      cur = cur[tok];
    }
  }
  return { found: true, value: cur };
}

function typeOk(value, type) {
  switch (type) {
    case 'string': return typeof value === 'string';
    // I-JSON numbers must be finite: reject NaN AND ±Infinity (non-canonical).
    case 'number': return typeof value === 'number' && Number.isFinite(value);
    case 'boolean': return typeof value === 'boolean';
    case 'object': return value !== null && typeof value === 'object' && !Array.isArray(value);
    case 'array': return Array.isArray(value);
    default: return false;
  }
}

function regexSafetyError(source) {
  if (source.length > MAX_FIELD_REGEX_SOURCE_CHARS) {
    return `regex source exceeds ${MAX_FIELD_REGEX_SOURCE_CHARS} characters`;
  }
  if (/\\[1-9]/.test(source)) return 'backreferences are not supported in api-response regex constraints';
  if (/\(\?[=!<]/.test(source)) return 'lookahead/lookbehind assertions are not supported in api-response regex constraints';
  if (/\((?:[^()\\]|\\.)*[+*{](?:[^()\\]|\\.)*\)\s*[+*{]/.test(source)) {
    return 'nested quantified groups are not supported in api-response regex constraints';
  }
  if (/\((?:[^()\\]|\\.)*\|(?:[^()\\]|\\.)*\)\s*[+*{]/.test(source)) {
    return 'quantified alternation groups are not supported in api-response regex constraints';
  }
  return null;
}

// Minimal recursive shape check reused for an optional response bodySchema.
// (Same spirit as the schema verifier, kept local so this module is standalone.)
function checkShape(value, schema, path, state = { nodes: 0 }, depth = 0) {
  if (depth > MAX_BODY_SCHEMA_DEPTH) return `bodySchema at ${path} exceeds max depth ${MAX_BODY_SCHEMA_DEPTH}`;
  state.nodes++;
  if (state.nodes > MAX_BODY_SCHEMA_NODES) return `bodySchema traversal exceeds max nodes ${MAX_BODY_SCHEMA_NODES}`;
  if (schema === null || typeof schema !== 'object') return `schema at ${path} is not a shape object`;
  const t = schema.type;
  if (typeof t !== 'string') return `schema at ${path} missing string "type"`;
  if (!typeOk(value, t)) return `expected ${t} at ${path}, got ${describe(value)}`;
  if (t === 'object') {
    const required = Array.isArray(schema.required) ? schema.required : [];
    if (required.length > MAX_BODY_SCHEMA_REQUIRED) {
      return `bodySchema.required at ${path} exceeds max length ${MAX_BODY_SCHEMA_REQUIRED}`;
    }
    for (const key of required) {
      if (!Object.prototype.hasOwnProperty.call(value, key)) return `missing required "${key}" at ${path}`;
    }
    const props = schema.properties && typeof schema.properties === 'object' ? schema.properties : {};
    const propKeys = Object.keys(props);
    if (propKeys.length > MAX_BODY_SCHEMA_PROPERTIES) {
      return `bodySchema.properties at ${path} exceeds max key count ${MAX_BODY_SCHEMA_PROPERTIES}`;
    }
    for (const key of propKeys) {
      if (Object.prototype.hasOwnProperty.call(value, key)) {
        const err = checkShape(value[key], props[key], path === '$' ? `$.${key}` : `${path}.${key}`, state, depth + 1);
        if (err) return err;
      }
    }
  } else if (t === 'array' && schema.items !== undefined) {
    if (value.length > MAX_BODY_SCHEMA_ARRAY_ITEMS) {
      return `array at ${path} has ${value.length} item(s), exceeding max ${MAX_BODY_SCHEMA_ARRAY_ITEMS}`;
    }
    for (let i = 0; i < value.length; i++) {
      const err = checkShape(value[i], schema.items, `${path}[${i}]`, state, depth + 1);
      if (err) return err;
    }
  }
  return null;
}

/**
 * @type {import('../protocol/types.mjs').Verifier}
 */
export const apiResponseVerifier = {
  name: NAME,
  tier: TIER,
  /**
   * @param {DeliveryContract} contract
   * @param {DeliveryEvidence} evidence
   * @returns {Verdict}
   */
  verify(contract, evidence, opts = {}) {
    const at = checkedAt(opts);
    const params = contract?.predicate?.params;
    if (!params || typeof params !== 'object') {
      return fail('contract.predicate.params is required for the api-response verifier', at);
    }
    const tx = evidence?.output;
    if (!tx || typeof tx !== 'object' || Array.isArray(tx)) {
      return fail('evidence.output must be a {contractId,nonce,request,response} transcript object', at);
    }

    // (0) Contract binding — the transcript MUST be bound to THIS contract + nonce,
    // so a valid response captured for a different (e.g. cheaper) contract cannot be
    // replayed into this settlement. This binding is mandatory and non-bypassable.
    if (tx.contractId !== contract?.id) {
      return fail('transcript.contractId does not match contract.id', at,
        { field: 'contractId', expected: contract?.id, actual: tx.contractId, reason: 'contract binding mismatch' });
    }
    if (tx.nonce !== contract?.nonce) {
      return fail('transcript.nonce does not match contract.nonce', at,
        { field: 'nonce', expected: contract?.nonce, actual: tx.nonce, reason: 'nonce binding mismatch (replay)' });
    }

    const req = tx.request;
    const res = tx.response;
    // request is mandatory: api-response correctness is meaningless without the
    // request it answers (it is the basis of request-binding + fromRequest checks).
    if (!req || typeof req !== 'object' || Array.isArray(req)) {
      return fail('transcript is missing a request object', at);
    }
    if (!res || typeof res !== 'object') {
      return fail('transcript is missing a response object', at);
    }

    // (1) Request binding — the response must answer the request the contract meant.
    if (params.request && typeof params.request === 'object') {
      for (const f of ['method', 'url', 'bodyHash']) {
        if (params.request[f] !== undefined) {
          const exp = f === 'method' ? String(params.request[f]).toUpperCase() : params.request[f];
          const act = f === 'method' && typeof req[f] === 'string' ? req[f].toUpperCase() : req[f];
          if (act !== exp) {
            return fail(`request.${f} mismatch`, at,
              { field: `request.${f}`, expected: exp, actual: act, reason: 'request binding mismatch' });
          }
        }
      }
    }

    // (2) Status / status range.
    if (params.status !== undefined) {
      const s = res.status;
      if (typeof params.status === 'number') {
        if (s !== params.status) {
          return fail(`status ${s} != expected ${params.status}`, at,
            { field: 'response.status', expected: params.status, actual: s, reason: 'status mismatch' });
        }
      } else {
        const { min, max } = params.status;
        if ((typeof min === 'number' && s < min) || (typeof max === 'number' && s > max)) {
          return fail(`status ${s} outside [${min ?? '-∞'},${max ?? '∞'}]`, at,
            { field: 'response.status', expected: `[${min ?? ''},${max ?? ''}]`, actual: s, reason: 'status out of range' });
        }
      }
    }

    // (3) Content-type + required headers (header lookup is case-insensitive).
    const headers = res.headers && typeof res.headers === 'object' ? res.headers : {};
    const headerKeys = Object.keys(headers);
    if (headerKeys.length > MAX_RESPONSE_HEADERS) {
      return fail(`response has ${headerKeys.length} header(s), exceeding max ${MAX_RESPONSE_HEADERS}`, at,
        { field: 'response.headers', expected: `<= ${MAX_RESPONSE_HEADERS}`, actual: headerKeys.length, reason: 'too many headers' });
    }
    const headerGet = (name) => {
      const lc = String(name).toLowerCase();
      for (const k of headerKeys) if (k.toLowerCase() === lc) return headers[k];
      return undefined;
    };
    if (params.contentType !== undefined) {
      const ct = headerGet('content-type');
      if (ct !== params.contentType) {
        return fail(`content-type ${describe(ct)} != ${params.contentType}`, at,
          { field: 'response.headers.content-type', expected: params.contentType, actual: ct, reason: 'content-type mismatch' });
      }
    }
    if (Array.isArray(params.requiredHeaders)) {
      if (params.requiredHeaders.length > MAX_REQUIRED_HEADERS) {
        return fail(`requiredHeaders has ${params.requiredHeaders.length} item(s), exceeding max ${MAX_REQUIRED_HEADERS}`, at);
      }
      for (const h of params.requiredHeaders) {
        if (headerGet(h) === undefined) {
          return fail(`required header "${h}" missing`, at,
            { field: `response.headers.${h}`, expected: 'present', actual: 'absent', reason: 'missing required header' });
        }
      }
    }

    // (4) Optional response body shape (structural floor).
    if (params.bodySchema !== undefined) {
      const err = checkShape(res.body, params.bodySchema, '$');
      if (err) {
        return fail(`response body does not match bodySchema: ${err}`, at,
          { field: '$', expected: 'bodySchema', actual: err, reason: 'body shape mismatch' });
      }
    }

    // (5) Field assertions over the response body — the DEEP part.
    if (params.fields !== undefined) {
      if (!Array.isArray(params.fields)) {
        return fail('predicate.params.fields must be an array of field assertions', at);
      }
      if (params.fields.length > MAX_FIELD_ASSERTIONS) {
        return fail(`predicate.params.fields has ${params.fields.length} assertion(s), exceeding max ${MAX_FIELD_ASSERTIONS}`, at);
      }
      for (const f of params.fields) {
        if (!f || typeof f.path !== 'string') {
          return fail('each field assertion needs a string path', at);
        }
        if (f.path.length > MAX_JSON_PATH_CHARS) {
          return fail(`field assertion path exceeds ${MAX_JSON_PATH_CHARS} characters`, at,
            { field: 'fields.path', expected: `<= ${MAX_JSON_PATH_CHARS} chars`, actual: f.path.length, reason: 'path too long' });
        }
        const { found, value } = resolvePath(res.body, f.path);
        if (!found) {
          return fail(`response body path "${f.path}" not found`, at,
            { field: f.path, expected: 'present', actual: 'missing', reason: 'path not found' });
        }
        // fromRequest: the value must equal a value pulled from the request (binding).
        if (f.fromRequest !== undefined) {
          if (typeof f.fromRequest !== 'string') {
            return fail('field assertion fromRequest must be a string path', at);
          }
          if (f.fromRequest.length > MAX_JSON_PATH_CHARS) {
            return fail(`fromRequest path exceeds ${MAX_JSON_PATH_CHARS} characters`, at,
              { field: 'fields.fromRequest', expected: `<= ${MAX_JSON_PATH_CHARS} chars`, actual: f.fromRequest.length, reason: 'path too long' });
          }
          const rq = resolvePath(req, f.fromRequest);
          if (!rq.found) {
            return fail(`request path "${f.fromRequest}" (for fromRequest) not found`, at,
              { field: f.fromRequest, expected: 'present', actual: 'missing', reason: 'request path not found' });
          }
          if (canonicalize(value) !== canonicalize(rq.value)) {
            return fail(`response "${f.path}" does not match request "${f.fromRequest}"`, at,
              { field: f.path, expected: rq.value, actual: value, reason: 'response/request value mismatch' });
          }
        }
        if (f.type !== undefined && !typeOk(value, f.type)) {
          return fail(`"${f.path}" expected type ${f.type}, got ${describe(value)}`, at,
            { field: f.path, expected: f.type, actual: describe(value), reason: 'type mismatch' });
        }
        if (f.equals !== undefined && canonicalize(value) !== canonicalize(f.equals)) {
          return fail(`"${f.path}" != expected`, at,
            { field: f.path, expected: f.equals, actual: value, reason: 'equals mismatch' });
        }
        if (Array.isArray(f.in)) {
          if (f.in.length > MAX_FIELD_IN_OPTIONS) {
            return fail(`"${f.path}" allowed set exceeds max ${MAX_FIELD_IN_OPTIONS} option(s)`, at,
              { field: f.path, expected: `<= ${MAX_FIELD_IN_OPTIONS} options`, actual: f.in.length, reason: 'allowed set too large' });
          }
          if (!f.in.some((opt) => canonicalize(opt) === canonicalize(value))) {
            return fail(`"${f.path}" not in allowed set`, at,
              { field: f.path, expected: f.in, actual: value, reason: 'value not in allowed set' });
          }
        }
        if (typeof f.min === 'number') {
          if (typeof value !== 'number' || value < f.min) {
            return fail(`"${f.path}" below min ${f.min}`, at,
              { field: f.path, expected: `>= ${f.min}`, actual: value, reason: 'below min' });
          }
        }
        if (typeof f.max === 'number') {
          if (typeof value !== 'number' || value > f.max) {
            return fail(`"${f.path}" above max ${f.max}`, at,
              { field: f.path, expected: `<= ${f.max}`, actual: value, reason: 'above max' });
          }
        }
        if (typeof f.matches === 'string') {
          let rx;
          const safetyError = regexSafetyError(f.matches);
          if (safetyError !== null) {
            return fail(`field "${f.path}" regex is outside the supported safe subset: ${safetyError}`, at);
          }
          try { rx = new RegExp(f.matches); } catch { return fail(`field "${f.path}" has an invalid regex`, at); }
          if (typeof value === 'string' && value.length > MAX_FIELD_REGEX_INPUT_CHARS) {
            return fail(`"${f.path}" regex input exceeds ${MAX_FIELD_REGEX_INPUT_CHARS} characters`, at,
              { field: f.path, expected: `<= ${MAX_FIELD_REGEX_INPUT_CHARS} chars before regex match`, actual: value.length, reason: 'regex input too long' });
          }
          if (typeof value !== 'string' || !rx.test(value)) {
            return fail(`"${f.path}" does not match /${f.matches}/`, at,
              { field: f.path, expected: `/${f.matches}/`, actual: value, reason: 'regex mismatch' });
          }
        }
      }
    }

    // (6) Freshness — the response must be recent relative to the contract.
    if (typeof params.freshnessMs === 'number') {
      const produced = typeof evidence.producedAt === 'number' ? evidence.producedAt
        : typeof tx.producedAt === 'number' ? tx.producedAt : undefined;
      const reference = typeof contract.createdAt === 'number' ? contract.createdAt : at;
      if (produced === undefined) {
        return fail('freshness required but transcript has no producedAt', at,
          { field: 'producedAt', expected: 'present', actual: 'absent', reason: 'no timestamp' });
      }
      if (Math.abs(reference - produced) > params.freshnessMs) {
        return fail(`response is stale: |${reference} - ${produced}| > ${params.freshnessMs}ms`, at,
          { field: 'producedAt', expected: `within ${params.freshnessMs}ms`, actual: produced, reason: 'stale response' });
      }
    }

    return pass(
      `api-response satisfied the contract predicate over the captured transcript` +
        (params.fields ? ` (${params.fields.length} field assertion(s))` : ''),
      at,
    );
  },
};

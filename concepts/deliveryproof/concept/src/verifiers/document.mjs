// src/verifiers/document.mjs
// Tier A verifier: objective structured-document correctness for Markdown.
//
// This verifier checks bytes and structure only: frontmatter fields, headings,
// required terms, links, table headers, fenced code-block languages, and raw
// SHA-256 checksums over the whole document or named sections. It does NOT grade
// prose quality, truth, completeness, style, or semantic usefulness.

import { canonicalize, sha256utf8 } from '../protocol/canonical.mjs';
import { checkedAt as checkedAtFrom, safeRecord } from '../protocol/runtime.mjs';

/** @typedef {import('../protocol/types.mjs').DeliveryContract} DeliveryContract */
/** @typedef {import('../protocol/types.mjs').DeliveryEvidence} DeliveryEvidence */
/** @typedef {import('../protocol/types.mjs').Verdict} Verdict */

const NAME = 'document';
const TIER = 'A';
const MAX_DOCUMENT_CHARS = 1_000_000;
const MAX_LINE_CHARS = 16_384;
const MAX_LINES = 50_000;
const MAX_DOCUMENT_SPEC_ITEMS = 256;
const MAX_DOCUMENT_SPEC_TEXT_CHARS = 1_024;

/**
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
 * @param {string} reason
 * @param {number} checkedAt
 * @returns {Verdict}
 */
function pass(reason, checkedAt) {
  return { ok: true, tier: TIER, verifier: NAME, reason, checkedAt };
}

/**
 * @param {Object} params
 * @param {string} params.field
 * @param {*} params.expected
 * @param {*} params.actual
 * @param {string} params.reason
 * @param {number|null} [params.row]
 * @returns {{field:string,expected:*,actual:*,row:number|null,reason:string}}
 */
function diff({ field, expected, actual, reason, row = null }) {
  return { field, expected, actual, row, reason };
}

/**
 * @param {string} text
 * @returns {string}
 */
function normalizeMarkdown(text) {
  return text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

/**
 * Bound parser resource use before hashing or structural checks. This is a
 * pragmatic CWE-400 guardrail, not a security sandbox for arbitrary Markdown.
 *
 * @param {string} text
 * @returns {{ok:true}|{ok:false, reason:string, diff:Object}}
 */
function preflightMarkdown(text) {
  if (text.length > MAX_DOCUMENT_CHARS) {
    return {
      ok: false,
      reason: `document is ${text.length} character(s), exceeds maximum ${MAX_DOCUMENT_CHARS}`,
      diff: diff({ field: 'document.length', expected: `<=${MAX_DOCUMENT_CHARS}`, actual: text.length, reason: 'document too large' }),
    };
  }

  let line = 1;
  let lineLength = 0;
  for (let i = 0; i < text.length; i++) {
    if (text.charCodeAt(i) === 10) {
      if (lineLength > MAX_LINE_CHARS) {
        return {
          ok: false,
          reason: `line ${line} is ${lineLength} character(s), exceeds maximum ${MAX_LINE_CHARS}`,
          diff: diff({ field: 'document.lineLength', expected: `<=${MAX_LINE_CHARS}`, actual: lineLength, row: line, reason: 'line too long' }),
        };
      }
      line++;
      if (line > MAX_LINES) {
        return {
          ok: false,
          reason: `document has more than ${MAX_LINES} line(s)`,
          diff: diff({ field: 'document.lines', expected: `<=${MAX_LINES}`, actual: line, reason: 'too many lines' }),
        };
      }
      lineLength = 0;
    } else {
      lineLength++;
    }
  }

  if (lineLength > MAX_LINE_CHARS) {
    return {
      ok: false,
      reason: `line ${line} is ${lineLength} character(s), exceeds maximum ${MAX_LINE_CHARS}`,
      diff: diff({ field: 'document.lineLength', expected: `<=${MAX_LINE_CHARS}`, actual: lineLength, row: line, reason: 'line too long' }),
    };
  }

  return { ok: true };
}

/**
 * Parse a tiny YAML-like frontmatter block:
 *   ---
 *   key: value
 *   ---
 * Values are strings, numbers, booleans, or comma-delimited arrays in [a,b].
 *
 * @param {string[]} lines
 * @returns {{ frontmatter: Object, bodyStart: number, error: string|null }}
 */
function parseFrontmatter(lines) {
  if (lines[0] !== '---') return { frontmatter: {}, bodyStart: 0, error: null };
  let close = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i] === '---') {
      close = i;
      break;
    }
  }
  if (close === -1) return { frontmatter: {}, bodyStart: 0, error: 'frontmatter block is not closed' };
  const frontmatter = safeRecord();
  for (let i = 1; i < close; i++) {
    const line = lines[i].trim();
    if (line.length === 0) continue;
    const idx = line.indexOf(':');
    if (idx <= 0) return { frontmatter: {}, bodyStart: 0, error: `frontmatter line ${i + 1} is not key: value` };
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    if (key.length === 0) return { frontmatter: {}, bodyStart: 0, error: `frontmatter line ${i + 1} has an empty key` };
    frontmatter[key] = parseScalar(value);
  }
  return { frontmatter, bodyStart: close + 1, error: null };
}

/**
 * @param {string} value
 * @returns {*}
 */
function parseScalar(value) {
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    return value.slice(1, -1);
  }
  if (value === 'true') return true;
  if (value === 'false') return false;
  const n = Number(value);
  if (value.length > 0 && Number.isFinite(n) && /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(value)) return n;
  if (value.startsWith('[') && value.endsWith(']')) {
    const inner = value.slice(1, -1).trim();
    if (inner.length === 0) return [];
    return inner.split(',').map((x) => parseScalar(x.trim()));
  }
  return value;
}

/**
 * @param {string} text normalized markdown
 * @returns {{frontmatter:Object, headings:Object[], links:Object[], tables:Object[], codeBlocks:Object[], error:string|null}}
 */
function parseMarkdown(text) {
  const lines = text.split('\n');
  const fm = parseFrontmatter(lines);
  if (fm.error) return { frontmatter: {}, headings: [], links: [], tables: [], codeBlocks: [], error: fm.error };

  const headings = [];
  const links = [];
  const tables = [];
  const codeBlocks = [];
  let inFence = false;
  let fence = null;

  for (let i = fm.bodyStart; i < lines.length; i++) {
    const line = lines[i];
    const fenceMatch = line.match(/^```([A-Za-z0-9_-]*)\s*$/);
    if (fenceMatch) {
      if (!inFence) {
        inFence = true;
        fence = { language: fenceMatch[1] || '', startLine: i + 1, content: [] };
      } else {
        codeBlocks.push({ ...fence, endLine: i + 1, content: fence.content.join('\n') });
        inFence = false;
        fence = null;
      }
      continue;
    }
    if (inFence) {
      fence.content.push(line);
      continue;
    }

    const heading = line.match(/^(#{1,6})[ \t]+(.+?)\s*#*\s*$/);
    if (heading) {
      headings.push({ level: heading[1].length, text: heading[2].trim(), line: i + 1 });
    }

    for (const match of line.matchAll(/\[([^\]\n]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g)) {
      links.push({ text: match[1], href: match[2], line: i + 1 });
    }

    if (line.includes('|') && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      tables.push({ headers: splitTableRow(line), line: i + 1 });
    }
  }
  if (inFence) return { frontmatter: {}, headings: [], links: [], tables: [], codeBlocks: [], error: 'unclosed fenced code block' };

  for (let h = 0; h < headings.length; h++) {
    const current = headings[h];
    let endLine = lines.length + 1;
    for (let n = h + 1; n < headings.length; n++) {
      if (headings[n].level <= current.level) {
        endLine = headings[n].line;
        break;
      }
    }
    current.content = lines.slice(current.line, endLine - 1).join('\n').trim();
  }

  return { frontmatter: fm.frontmatter, headings, links, tables, codeBlocks, error: null };
}

/**
 * @param {string} line
 * @returns {boolean}
 */
function isTableSeparator(line) {
  const cells = splitTableRow(line);
  return cells.length >= 2 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

/**
 * @param {string} line
 * @returns {string[]}
 */
function splitTableRow(line) {
  const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '');
  return trimmed.split('|').map((cell) => cell.trim());
}

/**
 * @param {string} href
 * @returns {string}
 */
function linkScheme(href) {
  if (href.startsWith('#')) return 'anchor';
  const match = href.match(/^([A-Za-z][A-Za-z0-9+.-]*):/);
  return match ? match[1].toLowerCase() : 'relative';
}

/**
 * @param {*} actual
 * @param {*} spec
 * @param {string} field
 * @returns {string|null}
 */
function checkScalarSpec(actual, spec, field) {
  if (!spec || typeof spec !== 'object') return null;
  if (typeof spec.type === 'string' && typeof actual !== spec.type) {
    return `${field} expected ${spec.type}, got ${describe(actual)}`;
  }
  if (Object.prototype.hasOwnProperty.call(spec, 'equals') && canonicalize(actual) !== canonicalize(spec.equals)) {
    return `${field} != expected`;
  }
  if (Array.isArray(spec.in) && !spec.in.some((v) => canonicalize(v) === canonicalize(actual))) {
    return `${field} not in allowed set`;
  }
  return null;
}

/**
 * @param {Array<*>} spec
 * @param {string} label
 * @returns {string|null}
 */
function specArrayError(spec, label) {
  if (spec.length > MAX_DOCUMENT_SPEC_ITEMS) {
    return `${label} has ${spec.length} item(s), exceeding max ${MAX_DOCUMENT_SPEC_ITEMS}`;
  }
  return null;
}

/**
 * @param {string} value
 * @param {string} label
 * @returns {string|null}
 */
function specTextError(value, label) {
  if (value.length > MAX_DOCUMENT_SPEC_TEXT_CHARS) {
    return `${label} exceeds ${MAX_DOCUMENT_SPEC_TEXT_CHARS} characters`;
  }
  return null;
}

/**
 * @param {*} value
 * @returns {string}
 */
function describe(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'array';
  return typeof value;
}

/**
 * @param {string} haystack
 * @param {string} needle
 * @param {boolean} caseSensitive
 * @returns {number}
 */
function countOccurrences(haystack, needle, caseSensitive) {
  if (needle.length === 0) return 0;
  const h = caseSensitive ? haystack : haystack.toLowerCase();
  const n = caseSensitive ? needle : needle.toLowerCase();
  let count = 0;
  let offset = 0;
  while (true) {
    const idx = h.indexOf(n, offset);
    if (idx === -1) return count;
    count++;
    offset = idx + n.length;
  }
}

/**
 * @param {Object[]} headings
 * @param {string} text
 * @param {number|undefined} level
 * @param {boolean} caseSensitive
 * @returns {Object[]}
 */
function matchingHeadings(headings, text, level, caseSensitive) {
  return headings.filter((h) => {
    const textOk = caseSensitive ? h.text === text : h.text.toLowerCase() === text.toLowerCase();
    const levelOk = level === undefined || h.level === level;
    return textOk && levelOk;
  });
}

/**
 * @type {import('../protocol/types.mjs').Verifier}
 */
export const documentVerifier = {
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
      return fail('contract.predicate.params is required for the document verifier', checkedAt);
    }
    if (params.format !== undefined && params.format !== 'markdown') {
      return fail(`unsupported document format "${params.format}" (expected markdown)`, checkedAt);
    }
    if (typeof evidence?.output !== 'string') {
      return fail(
        `document verifier requires evidence.output to be a Markdown string, got ${describe(evidence?.output)}`,
        checkedAt,
      );
    }

    const text = normalizeMarkdown(evidence.output);
    const preflight = preflightMarkdown(text);
    if (!preflight.ok) return fail(preflight.reason, checkedAt, preflight.diff);

    const documentHash = sha256utf8(text);
    if (typeof params.documentHash === 'string' && params.documentHash !== documentHash) {
      return fail(
        `documentHash mismatch: committed ${params.documentHash.slice(0, 16)}... but delivered document hashes to ${documentHash.slice(0, 16)}...`,
        checkedAt,
        diff({ field: 'documentHash', expected: params.documentHash, actual: documentHash, reason: 'document hash mismatch' }),
      );
    }
    if (typeof evidence.documentHash === 'string' && evidence.documentHash !== documentHash) {
      return fail(
        `evidence.documentHash mismatch: evidence says ${evidence.documentHash.slice(0, 16)}... but delivered document hashes to ${documentHash.slice(0, 16)}...`,
        checkedAt,
        diff({ field: 'evidence.documentHash', expected: documentHash, actual: evidence.documentHash, reason: 'evidence hash mismatch' }),
      );
    }

    const parsed = parseMarkdown(text);
    if (parsed.error) return fail(`could not parse markdown document: ${parsed.error}`, checkedAt);

    const frontmatterVerdict = checkFrontmatter(params.frontmatter, parsed.frontmatter, checkedAt);
    if (frontmatterVerdict) return frontmatterVerdict;

    const headingVerdict = checkHeadings(params.headings, parsed.headings, checkedAt);
    if (headingVerdict) return headingVerdict;

    const termVerdict = checkRequiredTerms(params.requiredTerms, text, checkedAt);
    if (termVerdict) return termVerdict;

    const linkVerdict = checkLinks(params.links, parsed.links, checkedAt);
    if (linkVerdict) return linkVerdict;

    const tableVerdict = checkTables(params.tables, parsed.tables, checkedAt);
    if (tableVerdict) return tableVerdict;

    const codeVerdict = checkCodeBlocks(params.codeBlocks, parsed.codeBlocks, checkedAt);
    if (codeVerdict) return codeVerdict;

    const checksumVerdict = checkChecksums(params.checksums, text, parsed.headings, checkedAt);
    if (checksumVerdict) return checksumVerdict;

    return pass(
      `document passed all objective checks: ${parsed.headings.length} heading(s), ${parsed.links.length} link(s), ${parsed.tables.length} table(s), ${parsed.codeBlocks.length} code block(s)`,
      checkedAt,
    );
  },
};

/**
 * @param {*} spec
 * @param {Object} frontmatter
 * @param {number} checkedAt
 * @returns {Verdict|null}
 */
function checkFrontmatter(spec, frontmatter, checkedAt) {
  if (spec === undefined) return null;
  if (!spec || typeof spec !== 'object') return fail('frontmatter spec must be an object', checkedAt);
  const required = Array.isArray(spec.required) ? spec.required : [];
  for (const key of required) {
    if (!Object.prototype.hasOwnProperty.call(frontmatter, key)) {
      return fail(
        `frontmatter is missing required key "${key}"`,
        checkedAt,
        diff({ field: `frontmatter.${key}`, expected: 'present', actual: 'missing', reason: 'required frontmatter missing' }),
      );
    }
  }
  const fields = spec.fields && typeof spec.fields === 'object' ? spec.fields : {};
  for (const [key, fieldSpec] of Object.entries(fields)) {
    if (!Object.prototype.hasOwnProperty.call(frontmatter, key)) continue;
    const err = checkScalarSpec(frontmatter[key], fieldSpec, `frontmatter.${key}`);
    if (err) {
      return fail(err, checkedAt, diff({ field: `frontmatter.${key}`, expected: fieldSpec, actual: frontmatter[key], reason: err }));
    }
  }
  return null;
}

/**
 * @param {*} spec
 * @param {Object[]} headings
 * @param {number} checkedAt
 * @returns {Verdict|null}
 */
function checkHeadings(spec, headings, checkedAt) {
  if (spec === undefined) return null;
  if (!Array.isArray(spec)) return fail('headings must be an array', checkedAt);
  const arrayError = specArrayError(spec, 'headings');
  if (arrayError) return fail(arrayError, checkedAt);
  for (const h of spec) {
    if (!h || typeof h.text !== 'string') return fail('each heading spec needs text', checkedAt);
    const textError = specTextError(h.text, 'heading text');
    if (textError) return fail(textError, checkedAt);
    const caseSensitive = h.caseSensitive !== false;
    const matches = matchingHeadings(headings, h.text, h.level, caseSensitive);
    const minCount = Number.isInteger(h.minCount) ? h.minCount : 1;
    const maxCount = Number.isInteger(h.maxCount) ? h.maxCount : Infinity;
    if (matches.length < minCount) {
      return fail(
        `required heading "${h.text}" appears ${matches.length} time(s), expected at least ${minCount}`,
        checkedAt,
        diff({ field: 'headings', expected: { text: h.text, level: h.level, minCount }, actual: matches.length, reason: 'required heading missing' }),
      );
    }
    if (matches.length > maxCount) {
      return fail(
        `heading "${h.text}" appears ${matches.length} time(s), expected at most ${maxCount}`,
        checkedAt,
        diff({ field: 'headings', expected: { text: h.text, level: h.level, maxCount }, actual: matches.length, reason: 'heading appears too often' }),
      );
    }
  }
  return null;
}

/**
 * @param {*} spec
 * @param {string} text
 * @param {number} checkedAt
 * @returns {Verdict|null}
 */
function checkRequiredTerms(spec, text, checkedAt) {
  if (spec === undefined) return null;
  if (!Array.isArray(spec)) return fail('requiredTerms must be an array', checkedAt);
  const arrayError = specArrayError(spec, 'requiredTerms');
  if (arrayError) return fail(arrayError, checkedAt);
  for (const entry of spec) {
    const term = typeof entry === 'string' ? { text: entry } : entry;
    if (!term || typeof term.text !== 'string') return fail('each requiredTerms entry needs text', checkedAt);
    const textError = specTextError(term.text, 'required term text');
    if (textError) return fail(textError, checkedAt);
    const caseSensitive = term.caseSensitive === true;
    const minCount = Number.isInteger(term.minCount) ? term.minCount : 1;
    const actual = countOccurrences(text, term.text, caseSensitive);
    if (actual < minCount) {
      return fail(
        `required term "${term.text}" appears ${actual} time(s), expected at least ${minCount}`,
        checkedAt,
        diff({ field: 'requiredTerms', expected: { text: term.text, minCount }, actual, reason: 'required term missing' }),
      );
    }
  }
  return null;
}

/**
 * @param {*} spec
 * @param {Object[]} links
 * @param {number} checkedAt
 * @returns {Verdict|null}
 */
function checkLinks(spec, links, checkedAt) {
  if (spec === undefined) return null;
  if (!spec || typeof spec !== 'object') return fail('links spec must be an object', checkedAt);
  if (Array.isArray(spec.allowedSchemes)) {
    const schemeError = specArrayError(spec.allowedSchemes, 'links.allowedSchemes');
    if (schemeError) return fail(schemeError, checkedAt);
    const allowed = new Set(spec.allowedSchemes.map((x) => String(x).toLowerCase()));
    for (const link of links) {
      const scheme = linkScheme(link.href);
      if (!allowed.has(scheme)) {
        return fail(
          `link "${link.href}" uses disallowed scheme "${scheme}"`,
          checkedAt,
          diff({ field: 'links', expected: [...allowed], actual: link.href, row: link.line, reason: 'disallowed link scheme' }),
        );
      }
    }
  }
  if (Array.isArray(spec.required)) {
    const requiredError = specArrayError(spec.required, 'links.required');
    if (requiredError) return fail(requiredError, checkedAt);
    const hrefs = new Set(links.map((link) => link.href));
    for (const href of spec.required) {
      if (typeof href !== 'string') return fail('each required link must be a string', checkedAt);
      const hrefError = specTextError(href, 'required link');
      if (hrefError) return fail(hrefError, checkedAt);
      if (!hrefs.has(href)) {
        return fail(
          `required link "${href}" is missing`,
          checkedAt,
          diff({ field: 'links', expected: href, actual: [...hrefs], reason: 'required link missing' }),
        );
      }
    }
  }
  return null;
}

/**
 * @param {*} spec
 * @param {Object[]} tables
 * @param {number} checkedAt
 * @returns {Verdict|null}
 */
function checkTables(spec, tables, checkedAt) {
  if (spec === undefined) return null;
  if (!Array.isArray(spec)) return fail('tables must be an array', checkedAt);
  const arrayError = specArrayError(spec, 'tables');
  if (arrayError) return fail(arrayError, checkedAt);
  for (const t of spec) {
    if (!t || !Array.isArray(t.headers) || t.headers.length === 0) {
      return fail('each table spec needs a non-empty headers array', checkedAt);
    }
    const headersError = specArrayError(t.headers, 'table headers');
    if (headersError) return fail(headersError, checkedAt);
    for (const header of t.headers) {
      if (typeof header !== 'string') return fail('each table header must be a string', checkedAt);
      const headerError = specTextError(header, 'table header');
      if (headerError) return fail(headerError, checkedAt);
    }
    const mode = t.mode ?? 'exact';
    const found = tables.some((table) => {
      if (mode === 'contains') return t.headers.every((header) => table.headers.includes(header));
      return canonicalize(table.headers) === canonicalize(t.headers);
    });
    if (!found) {
      return fail(
        `required table headers [${t.headers.join(', ')}] not found`,
        checkedAt,
        diff({ field: 'tables', expected: t.headers, actual: tables.map((table) => table.headers), reason: 'required table missing' }),
      );
    }
  }
  return null;
}

/**
 * @param {*} spec
 * @param {Object[]} codeBlocks
 * @param {number} checkedAt
 * @returns {Verdict|null}
 */
function checkCodeBlocks(spec, codeBlocks, checkedAt) {
  if (spec === undefined) return null;
  if (!Array.isArray(spec)) return fail('codeBlocks must be an array', checkedAt);
  const arrayError = specArrayError(spec, 'codeBlocks');
  if (arrayError) return fail(arrayError, checkedAt);
  for (const c of spec) {
    if (!c || typeof c !== 'object') return fail('each codeBlocks entry must be an object', checkedAt);
    const language = typeof c.language === 'string' ? c.language : null;
    if (language !== null) {
      const languageError = specTextError(language, 'code block language');
      if (languageError) return fail(languageError, checkedAt);
    }
    const count = codeBlocks.filter((block) => language === null || block.language === language).length;
    const minCount = Number.isInteger(c.minCount) ? c.minCount : 1;
    const maxCount = Number.isInteger(c.maxCount) ? c.maxCount : Infinity;
    if (count < minCount || count > maxCount) {
      return fail(
        `code block count for ${language ?? 'any language'} is ${count}, expected ${minCount}..${Number.isFinite(maxCount) ? maxCount : '∞'}`,
        checkedAt,
        diff({ field: 'codeBlocks', expected: { language, minCount, maxCount }, actual: count, reason: 'code block count mismatch' }),
      );
    }
  }
  return null;
}

/**
 * @param {*} spec
 * @param {string} text
 * @param {Object[]} headings
 * @param {number} checkedAt
 * @returns {Verdict|null}
 */
function checkChecksums(spec, text, headings, checkedAt) {
  if (spec === undefined) return null;
  if (!Array.isArray(spec)) return fail('checksums must be an array', checkedAt);
  const arrayError = specArrayError(spec, 'checksums');
  if (arrayError) return fail(arrayError, checkedAt);
  for (const c of spec) {
    if (!c || typeof c.sha256 !== 'string') return fail('each checksum needs sha256', checkedAt);
    const target = c.target ?? 'document';
    let actual;
    let label;
    if (target === 'document') {
      actual = sha256utf8(text);
      label = 'document';
    } else if (target === 'section') {
      if (typeof c.heading !== 'string') return fail('section checksum needs heading', checkedAt);
      const headingError = specTextError(c.heading, 'checksum heading');
      if (headingError) return fail(headingError, checkedAt);
      const matches = matchingHeadings(headings, c.heading, c.level, c.caseSensitive !== false);
      if (matches.length === 0) {
        return fail(
          `checksum section "${c.heading}" is missing`,
          checkedAt,
          diff({ field: 'checksums', expected: { target: 'section', heading: c.heading, level: c.level }, actual: 'missing', reason: 'checksum section missing' }),
        );
      }
      actual = sha256utf8(matches[0].content);
      label = `section:${c.heading}`;
    } else {
      return fail(`unsupported checksum target "${target}"`, checkedAt);
    }
    if (actual !== c.sha256) {
      return fail(
        `checksum mismatch for ${label}: committed ${c.sha256.slice(0, 16)}... but computed ${actual.slice(0, 16)}...`,
        checkedAt,
        diff({ field: 'checksums', expected: c.sha256, actual, reason: 'checksum mismatch' }),
      );
    }
  }
  return null;
}

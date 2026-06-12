// test/document.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';

import { sha256utf8 } from '../src/protocol/canonical.mjs';
import { documentVerifier } from '../src/verifiers/document.mjs';
import { getVerifier, verifiers } from '../src/verifiers/index.mjs';
import { routeVerifier } from '../src/router/policy.mjs';

const goodDoc = `---
title: Delivery Report
version: 1
status: final
---

# Delivery Report

## Scope

The delivered API response satisfies the deterministic predicate.

## Evidence

| field | value |
| --- | --- |
| city | Amsterdam |

[Receipt](https://example.com/receipt)

\`\`\`json
{"city":"Amsterdam","price":3}
\`\`\`

## Checksums

The evidence checksum is bound below.
`;

function sectionText(markdown, heading) {
  const lines = markdown.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  let start = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() === `## ${heading}`) {
      start = i + 1;
      break;
    }
  }
  assert.notEqual(start, -1, `section ${heading} should exist in fixture`);
  let end = lines.length;
  for (let i = start; i < lines.length; i++) {
    if (/^#{1,2}\s+/.test(lines[i])) {
      end = i;
      break;
    }
  }
  return lines.slice(start, end).join('\n').trim();
}

function contract(extraParams = {}) {
  return {
    id: 'doc-contract',
    nonce: 'doc-nonce',
    deliverableType: 'document',
    predicate: {
      kind: 'document',
      params: {
        format: 'markdown',
        frontmatter: {
          required: ['title', 'version', 'status'],
          fields: {
            status: { type: 'string', equals: 'final' },
            version: { type: 'number', equals: 1 },
          },
        },
        headings: [
          { text: 'Delivery Report', level: 1 },
          { text: 'Scope', level: 2 },
          { text: 'Evidence', level: 2 },
          { text: 'Checksums', level: 2 },
        ],
        requiredTerms: [{ text: 'deterministic predicate', minCount: 1 }],
        links: { allowedSchemes: ['https'], required: ['https://example.com/receipt'] },
        tables: [{ headers: ['field', 'value'] }],
        codeBlocks: [{ language: 'json', minCount: 1 }],
        checksums: [{ target: 'section', heading: 'Evidence', level: 2, sha256: sha256utf8(sectionText(goodDoc, 'Evidence')) }],
        ...extraParams,
      },
    },
  };
}

function evidence(output, extra = {}) {
  return { output, ...extra };
}

test('document: registered in registry and router profile', () => {
  assert.equal(getVerifier('document'), documentVerifier);
  assert.equal(verifiers.document, documentVerifier);
  const { verifier, routeDecision } = routeVerifier(contract(), {
    policy: { deliverableType: 'document', minAssurance: 3 },
  });
  assert.equal(verifier, documentVerifier);
  assert.equal(routeDecision.selected, 'document');
  assert.equal(routeDecision.selectedAssurance, 3);
});

test('document: passes a correct structured Markdown document', () => {
  const verdict = documentVerifier.verify(contract(), evidence(goodDoc));
  assert.equal(verdict.ok, true);
  assert.equal(verdict.tier, 'A');
  assert.equal(verdict.verifier, 'document');
});

test('document: MONEY-SHOT — schema-valid string missing required section refunds', () => {
  const badDoc = goodDoc.replace('\n## Checksums\n\nThe evidence checksum is bound below.\n', '\n');
  const shallow = getVerifier('schema').verify(
    { predicate: { kind: 'schema', params: { schema: { type: 'string' } } } },
    { output: badDoc },
  );
  assert.equal(shallow.ok, true, 'shallow schema accepts any string document');

  const verdict = documentVerifier.verify(contract(), evidence(badDoc));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /required heading "Checksums"/);
  assert.equal(verdict.diff.reason, 'required heading missing');
});

test('document: section checksum catches shape-valid content tampering', () => {
  const tampered = goodDoc.replace('| city | Amsterdam |', '| city | London |');
  const verdict = documentVerifier.verify(contract(), evidence(tampered));
  assert.equal(verdict.ok, false);
  assert.match(verdict.reason, /checksum mismatch/);
  assert.equal(verdict.diff.reason, 'checksum mismatch');
});

test('document: frontmatter, required terms, links, tables, and code blocks fail with structured diffs', () => {
  const noFrontmatter = goodDoc.replace('status: final', 'status: draft');
  const frontmatterVerdict = documentVerifier.verify(contract(), evidence(noFrontmatter));
  assert.equal(frontmatterVerdict.ok, false);
  assert.equal(frontmatterVerdict.diff.field, 'frontmatter.status');

  const noTerm = goodDoc.replace('deterministic predicate', 'general requirement');
  const termVerdict = documentVerifier.verify(contract(), evidence(noTerm));
  assert.equal(termVerdict.ok, false);
  assert.equal(termVerdict.diff.field, 'requiredTerms');

  const badLink = goodDoc.replace('https://example.com/receipt', 'javascript:alert(1)');
  const linkVerdict = documentVerifier.verify(contract(), evidence(badLink));
  assert.equal(linkVerdict.ok, false);
  assert.equal(linkVerdict.diff.reason, 'disallowed link scheme');

  const noTable = goodDoc.replace('| field | value |\n| --- | --- |\n| city | Amsterdam |\n', '');
  const tableVerdict = documentVerifier.verify(contract(), evidence(noTable));
  assert.equal(tableVerdict.ok, false);
  assert.equal(tableVerdict.diff.field, 'tables');

  const noCodeLang = goodDoc.replace('```json', '```');
  const codeVerdict = documentVerifier.verify(contract(), evidence(noCodeLang));
  assert.equal(codeVerdict.ok, false);
  assert.equal(codeVerdict.diff.field, 'codeBlocks');
});

test('document: optional documentHash and evidence documentHash are checked', () => {
  const hash = sha256utf8(goodDoc);
  assert.equal(documentVerifier.verify(contract({ documentHash: hash }), evidence(goodDoc, { documentHash: hash })).ok, true);

  const badContractHash = documentVerifier.verify(contract({ documentHash: sha256utf8('wrong') }), evidence(goodDoc));
  assert.equal(badContractHash.ok, false);
  assert.equal(badContractHash.diff.field, 'documentHash');

  const badEvidenceHash = documentVerifier.verify(contract(), evidence(goodDoc, { documentHash: sha256utf8('wrong') }));
  assert.equal(badEvidenceHash.ok, false);
  assert.equal(badEvidenceHash.diff.field, 'evidence.documentHash');
});

test('document: malformed markdown structures fail closed', () => {
  const frontmatter = documentVerifier.verify(contract(), evidence('---\ntitle: Missing close\n# Body'));
  assert.equal(frontmatter.ok, false);
  assert.match(frontmatter.reason, /frontmatter block is not closed/);

  const fence = documentVerifier.verify(contract(), evidence('# Title\n```js\nconsole.log(1)'));
  assert.equal(fence.ok, false);
  assert.match(fence.reason, /unclosed fenced code block/);
});

test('document: preflight bounds document and line size before parsing', () => {
  const tooLongLine = `# ${'x'.repeat(16_385)}`;
  const lineVerdict = documentVerifier.verify(contract(), evidence(tooLongLine));
  assert.equal(lineVerdict.ok, false);
  assert.equal(lineVerdict.diff.reason, 'line too long');

  const tooLargeDocument = `${'# Title\n'}${'x'.repeat(1_000_001)}`;
  const sizeVerdict = documentVerifier.verify(contract(), evidence(tooLargeDocument));
  assert.equal(sizeVerdict.ok, false);
  assert.equal(sizeVerdict.diff.reason, 'document too large');
});

test('router: does NOT silently downgrade document to schema at minAssurance 3', () => {
  assert.throws(
    () => routeVerifier(contract(), { policy: { deliverableType: 'document', minAssurance: 3, maxCost: 1 } }),
    /no verifier meets required assurance/,
  );
});

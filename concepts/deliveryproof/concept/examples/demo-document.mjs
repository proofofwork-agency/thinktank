// examples/demo-document.mjs
//
// THE DOCUMENT money-shot: a seller ships a Markdown report that is a valid
// string, but is missing an agreed section/checksum. A shallow schema check pays;
// the deep document verifier refunds on the same bytes.

import { generateKeypair, keyId } from '../src/protocol/crypto.mjs';
import { sha256utf8 } from '../src/protocol/canonical.mjs';
import { settle, verifyReceipt } from '../src/engine/deliveryproof.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { getVerifier } from '../src/verifiers/index.mjs';
import { routeVerifier } from '../src/router/policy.mjs';

const HEAVY = '═'.repeat(74);
const LINE = '─'.repeat(74);
const kv = (k, v) => console.log('  ' + String(k).padEnd(23) + ': ' + v);

const buyer = generateKeypair();
const seller = generateKeypair();
const settlementKey = generateKeypair();

const goodDocument = `---
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
  const start = lines.findIndex((line) => line.trim() === `## ${heading}`) + 1;
  if (start <= 0) throw new Error(`fixture missing ${heading}`);
  let end = lines.length;
  for (let i = start; i < lines.length; i++) {
    if (/^#{1,2}\s+/.test(lines[i])) {
      end = i;
      break;
    }
  }
  return lines.slice(start, end).join('\n').trim();
}

const badDocument = goodDocument.replace('\n## Checksums\n\nThe evidence checksum is bound below.\n', '\n');

function contract() {
  return {
    id: 'dc_document_demo',
    buyer: keyId(buyer.publicKey),
    seller: keyId(seller.publicKey),
    intent: 'deliver a structured Markdown delivery report with evidence and checksum sections',
    deliverableType: 'document',
    predicate: {
      kind: 'document',
      params: {
        format: 'markdown',
        frontmatter: { required: ['title', 'version', 'status'], fields: { status: { equals: 'final' } } },
        headings: [
          { text: 'Delivery Report', level: 1 },
          { text: 'Evidence', level: 2 },
          { text: 'Checksums', level: 2 },
        ],
        requiredTerms: [{ text: 'deterministic predicate', minCount: 1 }],
        links: { allowedSchemes: ['https'], required: ['https://example.com/receipt'] },
        tables: [{ headers: ['field', 'value'] }],
        codeBlocks: [{ language: 'json', minCount: 1 }],
        checksums: [{ target: 'section', heading: 'Evidence', level: 2, sha256: sha256utf8(sectionText(goodDocument, 'Evidence')) }],
      },
    },
    price: { amount: 8, currency: 'USDC' },
    sla: { deadlineMs: 60_000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'nonce-document-demo',
    createdAt: Date.now(),
  };
}

console.log('\n' + HEAVY);
console.log('  DeliveryProof — DOCUMENT money-shot: shallow PAYS, deep REFUNDS');
console.log(HEAVY);
console.log(`
  A buyer pays 8 USDC for a structured Markdown delivery report. The seller
  ships a valid string with the right rough shape, but omits the required
  Checksums section. Watch shallow schema pay, then document verification refund.
`);
kv('buyer', keyId(buyer.publicKey));
kv('seller(cheat)', keyId(seller.publicKey));

{
  const rail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
  const shallowContract = {
    ...contract(),
    predicate: { kind: 'schema', params: { schema: { type: 'string' } } },
  };
  console.log('\n' + LINE);
  console.log('  SHALLOW verifier: schema only ("is it a string?")');
  console.log(LINE);
  const r = await settle({
    contract: shallowContract,
    produceEvidence: () => ({ output: badDocument }),
    verifier: getVerifier('schema'),
    rail,
    settlementKey,
  });
  kv('predicate met?', r.verdict.ok ? 'YES' : 'NO');
  kv('decision', r.receipt.decision.toUpperCase());
  kv('seller paid?', r.hold.state === 'captured' ? 'YES' : 'NO');
  if (r.hold.state !== 'captured') throw new Error('MONEY-SHOT BROKEN: shallow path should release');
}

{
  const rail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
  const c = contract();
  const { verifier, routeDecision } = routeVerifier(c, {
    policy: { deliverableType: 'document', minAssurance: 3 },
  });
  console.log('\n' + LINE);
  console.log('  DEEP verifier: document structure + checksum predicate');
  console.log(LINE);
  kv('router selected', routeDecision.selected + '  (tier ' + routeDecision.selectedAssurance + ')');
  const r = await settle({
    contract: c,
    produceEvidence: () => ({ output: badDocument, documentHash: sha256utf8(badDocument) }),
    verifier,
    rail,
    settlementKey,
    routeDecision,
  });
  kv('predicate met?', r.verdict.ok ? 'YES' : 'NO');
  kv('reason', r.verdict.reason);
  if (r.verdict.diff) kv('structured diff', JSON.stringify(r.verdict.diff));
  kv('decision', r.receipt.decision.toUpperCase());
  kv('seller paid?', r.hold.state === 'captured' ? 'YES' : 'NO');
  kv('receipt valid?', verifyReceipt(r.receipt, settlementKey.publicKey) ? 'YES' : 'NO');
  if (r.hold.state === 'captured') throw new Error('MONEY-SHOT BROKEN: deep path should refund');
}

console.log('\n' + HEAVY);
console.log('  Takeaway: a document can be a valid string yet miss objective contract terms.');
console.log('  DeliveryProof checks declared structure/checksums; it does not grade prose.');
console.log(HEAVY + '\n');

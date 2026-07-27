// examples/demo-api.mjs
//
// THE API money-shot: a paid API call returns HTTP 200 + schema-valid JSON, but
// the answer is objectively WRONG for what was requested. A shallow shape check
// (what x402/PayCrow-style rails do) RELEASES and pays the seller; the router,
// at high assurance, selects the deep `api-response` verifier, which catches the
// wrong entity and REFUNDS — on the same bytes.
//
//   Run: node examples/demo-api.mjs
//
// The "API call" is a captured request/response transcript; no
// live network. This proves the release/refund DECISION for the paid-API / MCP
// tool-call surface where agent commerce actually happens.

import { generateKeypair, keyId } from '../src/protocol/crypto.mjs';
import { settle, verifyReceipt } from '../src/engine/deliveryproof.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { getVerifier } from '../src/verifiers/index.mjs';
import { routeVerifier } from '../src/router/policy.mjs';

const HEAVY = '═'.repeat(74);
const LINE = '─'.repeat(74);
const j = (v) => JSON.stringify(v);
const kv = (k, v) => console.log('  ' + String(k).padEnd(22) + ': ' + v);

const buyer = generateKeypair();
const seller = generateKeypair();
const settlementKey = generateKeypair();

// The buyer paid 4 USDC for a fresh Amsterdam weather reading priced <= 5.
function contract() {
  return {
    id: 'dc_api_demo',
    buyer: keyId(buyer.publicKey),
    seller: keyId(seller.publicKey),
    intent: 'paid weather API: Amsterdam, fresh, price <= 5',
    deliverableType: 'api-response',
    predicate: {
      kind: 'api-response',
      params: {
        request: { method: 'GET', url: 'https://api.example.com/weather?city=Amsterdam' },
        status: { min: 200, max: 299 },
        contentType: 'application/json',
        fields: [
          { path: 'city', equals: 'Amsterdam' },
          { path: 'temperature', type: 'number', min: -90, max: 60 },
          { path: 'price', max: 5 },
        ],
        freshnessMs: 60_000,
      },
    },
    price: { amount: 4, currency: 'USDC' },
    sla: { deadlineMs: 60_000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'nonce-api-demo',
    createdAt: Date.now(),
  };
}

// The seller delivers HTTP 200 + valid JSON — but it's the WRONG city (London),
// stale would also fail; here we use wrong-entity, the classic schema-valid-but-wrong.
const C = contract();
const deliveredTranscript = {
  contractId: C.id,   // bound to this contract (mandatory)
  nonce: C.nonce,     // replay guard (mandatory)
  request: { method: 'GET', url: 'https://api.example.com/weather?city=Amsterdam' },
  response: {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    body: { city: 'London', temperature: 21, price: 3 }, // valid shape, WRONG city
  },
  producedAt: C.createdAt,
};

console.log('\n' + HEAVY);
console.log('  DeliveryProof — API money-shot: shallow PAYS, deep REFUNDS');
console.log(HEAVY);
console.log(`
  A buyer pays 4 USDC for a weather API call for Amsterdam. The seller returns
  HTTP 200 + valid JSON — correct shape, but the WRONG city (London). Watch a
  shallow shape-check pay it, then watch the router select the deep api-response
  verifier and refund on the SAME bytes.
`);
kv('buyer', keyId(buyer.publicKey));
kv('seller(cheat)', keyId(seller.publicKey));

// --- Shallow path: schema verifier (shape only) -> RELEASE -------------------
{
  const rail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
  const shapeContract = {
    ...contract(),
    predicate: { kind: 'schema', params: { schema: { type: 'object',
      properties: { city: { type: 'string' }, temperature: { type: 'number' }, price: { type: 'number' } },
      required: ['city', 'temperature', 'price'] } } },
  };
  console.log('\n' + LINE);
  console.log('  SHALLOW verifier: JSON-schema shape only ("right fields + types?")');
  console.log(LINE);
  kv('verifier', 'schema  (what x402/PayCrow-style checks do)');
  const r = await settle({
    contract: shapeContract,
    produceEvidence: () => ({ output: deliveredTranscript.response.body }),
    verifier: getVerifier('schema'),
    rail, settlementKey,
  });
  kv('predicate met?', r.verdict.ok ? 'YES' : 'NO');
  kv('decision', r.receipt.decision.toUpperCase());
  kv('seller paid?', r.hold.state === 'captured' ? 'YES' : 'NO');
  console.log('  >> A shallow shape-check PAYS for the wrong city. This is the status quo.');
}

// --- Deep path: router selects api-response -> REFUND ------------------------
{
  const rail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
  const c = contract();
  const { verifier, routeDecision } = routeVerifier(c, {
    policy: { deliverableType: 'api-response', minAssurance: 3 },
  });
  console.log('\n' + LINE);
  console.log('  DEEP verifier: router selects api-response (request binding + field correctness + freshness)');
  console.log(LINE);
  kv('router selected', routeDecision.selected + '  (tier ' + routeDecision.selectedAssurance + ')');
  const r = await settle({
    contract: c,
    produceEvidence: () => ({ output: deliveredTranscript }),
    verifier, rail, settlementKey, routeDecision,
  });
  kv('predicate met?', r.verdict.ok ? 'YES' : 'NO');
  kv('reason', r.verdict.reason);
  if (r.verdict.diff) kv('structured diff', j(r.verdict.diff));
  kv('decision', r.receipt.decision.toUpperCase());
  kv('seller paid?', r.hold.state === 'captured' ? 'YES' : 'NO');
  kv('receipt valid?', verifyReceipt(r.receipt, settlementKey.publicKey) ? 'YES' : 'NO');
  console.log('  >> The deep api-response check REFUNDS. Same 200 + valid JSON, money saved.');

  if (r.hold.state === 'captured') throw new Error('MONEY-SHOT BROKEN: deep path should refund');
}

console.log('\n' + HEAVY);
console.log('  Takeaway: paid API/MCP rails verify "200 + valid JSON"; DeliveryProof');
console.log('  verifies the response actually answers the request (right entity, in-range,');
console.log('  fresh). Honest scope: this proves the response satisfies the predicate over');
console.log('  the captured transcript — not that the external-world fact is true.');
console.log(HEAVY + '\n');

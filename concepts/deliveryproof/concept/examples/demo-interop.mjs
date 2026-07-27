// examples/demo-interop.mjs
//
// Shows DeliveryProof as the DEEP EVALUATOR that the emerging agent-commerce
// standards leave undefined. The SAME signed DeliveryReceipt is projected onto
// BOTH an ERC-8004 ValidationRegistry payload and an ERC-8183 evaluator decision
// — once for a correct deliverable (release), once for a corrupt one (refund).
//
//   Run: node examples/demo-interop.mjs
//
// Thin, no chain logic: this is a payload-shape projection that
// demonstrates DeliveryProof can plug INTO those escrow/validation shells instead
// of competing with them.

import { generateKeypair, keyId } from '../src/protocol/crypto.mjs';
import { settle } from '../src/engine/deliveryproof.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { getVerifier } from '../src/verifiers/index.mjs';
import { toErc8004ValidationPayload, toErc8183EvaluatorResult } from '../src/interop/index.mjs';

const HEAVY = '═'.repeat(74);
const LINE = '─'.repeat(74);
const j = (v) => JSON.stringify(v);

function contract(seller) {
  return {
    id: 'dc_interop_demo',
    buyer: keyId(generateKeypair().publicKey),
    seller: keyId(seller.publicKey),
    intent: 'sort array ascending',
    deliverableType: 'compute',
    predicate: { kind: 'builtin-replay', params: { op: 'sort', input: [5, 3, 9, 1] } },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 30000 },
    refundRule: 'full-refund-on-fail',
    railId: 'escrow-mock',
    nonce: 'nonce-interop-demo',
    createdAt: Date.now(), // real timestamp: an epoch-0 contract is long past its SLA deadline
  };
}

const settlementKey = generateKeypair();
const seller = generateKeypair();

async function run(label, output) {
  const result = await settle({
    contract: contract(seller),
    produceEvidence: () => ({ output }),
    verifier: getVerifier('builtin-replay'),
    rail: createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey }),
    settlementKey,
  });
  console.log('\n' + LINE);
  console.log('  ' + label + '  (delivered ' + j(output) + ')');
  console.log(LINE);
  console.log('  DeliveryProof verdict : ok=' + result.verdict.ok + ' -> decision=' + result.receipt.decision.toUpperCase());
  console.log('  ERC-8004 validation   : ' + j(toErc8004ValidationPayload(result.receipt, { responseURI: 'ipfs://deliveryproof/receipt' })));
  console.log('  ERC-8183 evaluator    : ' + j(toErc8183EvaluatorResult(result.receipt, { jobId: 'job-42' })));
}

console.log('\n' + HEAVY);
console.log('  DeliveryProof — interop: one deep verdict, two standard shells');
console.log(HEAVY);
console.log(`
  ERC-8004 and ERC-8183 standardize WHERE a verdict is anchored and the escrow
  around it, but leave the VERIFIER/EVALUATOR method undefined. DeliveryProof
  supplies the deep objective verdict; the same signed receipt projects onto both.
`);

await run('CORRECT delivery', [1, 3, 5, 9]);
await run('CORRUPT delivery', [9, 5, 3, 1]);

console.log('\n' + HEAVY);
console.log('  Takeaway: DeliveryProof is the deep evaluator those shells leave open.');
console.log('  release -> ERC-8004 response=100 / ERC-8183 complete;');
console.log('  refund  -> ERC-8004 response=0   / ERC-8183 reject.');
console.log('  (Thin shape projection; sha256 by default, opt-in keccak256/ABI args; no chain submission.)');
console.log(HEAVY + '\n');

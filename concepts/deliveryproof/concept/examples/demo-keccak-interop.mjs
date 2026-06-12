// examples/demo-keccak-interop.mjs
//
// Shows the v0.9 Ethereum interop seam. SHA-256 remains the default projection
// hash for backward compatibility; Ethereum Keccak-256 and ABI-shaped argument
// bytes are opt-in. This is projection only: no wallet, provider, RPC URL,
// private key, contract call, chain submission, or custody code.
//
//   Run: node examples/demo-keccak-interop.mjs

import {
  createMockEscrowRail,
  generateKeypair,
  keyId,
  settle,
  testsuiteVerifier,
  toErc8004ValidationPayload,
  toErc8183EvaluatorResult,
} from '../src/index.mjs';

const HEAVY = '='.repeat(74);
const LINE = '-'.repeat(74);

function kv(label, value) {
  console.log('  ' + String(label).padEnd(24) + ': ' + value);
}

function short(value) {
  return value.length > 42 ? `${value.slice(0, 42)}...` : value;
}

const settlementKey = generateKeypair();
const seller = generateKeypair();
const buyer = generateKeypair();

const contract = {
  id: 'dc_keccak_interop_demo',
  buyer: keyId(buyer.publicKey),
  seller: keyId(seller.publicKey),
  intent: 'sort array ascending',
  deliverableType: 'application/json',
  predicate: { kind: 'testsuite', params: { op: 'sort', input: [5, 3, 9, 1] } },
  price: { amount: 5, currency: 'USDC' },
  sla: { deadlineMs: 60000 },
  refundRule: 'full-refund-on-fail',
  railId: 'escrow-mock',
  nonce: 'nonce-keccak-interop-demo',
  createdAt: 0,
};

console.log('\n' + HEAVY);
console.log('  DeliveryProof v0.9.1 — sha256 default, keccak opt-in');
console.log(HEAVY);
console.log(`
  The same signed receipt can be projected for ERC-8004 / ERC-8183 using the
  default SHA-256 hashes or opt-in Ethereum Keccak-256 hashes plus ABI-shaped
  args. These helpers prepare payload shapes only; they do not submit on-chain.
`);

const result = await settle({
  contract,
  produceEvidence: () => ({ output: [1, 3, 5, 9] }),
  verifier: testsuiteVerifier,
  rail: createMockEscrowRail(),
  settlementKey,
});

const erc8004Sha = toErc8004ValidationPayload(result.receipt);
const erc8004Keccak = toErc8004ValidationPayload(result.receipt, {
  hashAlg: 'keccak256',
  includeAbi: true,
  responseURI: 'ipfs://deliveryproof/receipt-demo',
});
const erc8183Sha = toErc8183EvaluatorResult(result.receipt, { jobId: 'job-keccak-demo' });
const erc8183Keccak = toErc8183EvaluatorResult(result.receipt, {
  jobId: 'job-keccak-demo',
  hashAlg: 'keccak256',
  includeAbi: true,
});

console.log(LINE);
console.log('  ERC-8004 ValidationRegistry payload');
console.log(LINE);
kv('default hashAlg', erc8004Sha.hashAlg);
kv('default requestHash', short(erc8004Sha.requestHash));
kv('default responseHash', short(erc8004Sha.responseHash));
kv('keccak hashAlg', erc8004Keccak.hashAlg);
kv('keccak requestHash', short(erc8004Keccak.requestHash));
kv('keccak responseHash', short(erc8004Keccak.responseHash));
kv('digests differ?', erc8004Sha.responseHash !== erc8004Keccak.responseHash);
kv('ABI signature', erc8004Keccak.abi.signature);
kv('encoded args prefix', short(erc8004Keccak.abi.encodedArgs));

console.log('\n' + LINE);
console.log('  ERC-8183 evaluator projection');
console.log(LINE);
kv('default reason', short(erc8183Sha.reason));
kv('keccak reason', short(erc8183Keccak.reason));
kv('digests differ?', erc8183Sha.reason !== erc8183Keccak.reason);
kv('ABI signature', erc8183Keccak.abi.signature);
kv('encoded args prefix', short(erc8183Keccak.abi.encodedArgs));

console.log('\n' + HEAVY);
console.log('  Takeaway: sha256 remains default; keccak256/ABI is explicit opt-in.');
console.log('  Projection only: no chain submission, provider, wallet, or custody.');
console.log(HEAVY + '\n');

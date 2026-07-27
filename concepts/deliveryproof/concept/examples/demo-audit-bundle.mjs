// examples/demo-audit-bundle.mjs
//
// Shows the v0.9 audit bundle seam. The bundle is a local inspection aid: it
// collates the hashes already bound into a signed DeliveryReceipt plus optional
// rail status. It is not telemetry, a new proof, or a settlement-path change.
//
//   Run: node examples/demo-audit-bundle.mjs

import {
  buildAuditBundle,
  createMockEscrowRail,
  generateKeypair,
  keyId,
  settle,
  sha256hex,
  builtinReplayVerifier,
} from '../src/index.mjs';

const HEAVY = '='.repeat(74);
const LINE = '-'.repeat(74);

function kv(label, value) {
  console.log('  ' + String(label).padEnd(30) + ': ' + value);
}

const settlementKey = generateKeypair();
const seller = generateKeypair();
const buyer = generateKeypair();

const contract = {
  id: 'dc_audit_bundle_demo',
  buyer: keyId(buyer.publicKey),
  seller: keyId(seller.publicKey),
  intent: 'sort array ascending',
  deliverableType: 'application/json',
  predicate: { kind: 'builtin-replay', params: { op: 'sort', input: [5, 3, 9, 1] } },
  price: { amount: 5, currency: 'USDC' },
  sla: { deadlineMs: 60000 },
  refundRule: 'full-refund-on-fail',
  railId: 'escrow-mock',
  nonce: 'nonce-audit-bundle-demo',
  createdAt: Date.now(), // real timestamp: an epoch-0 contract is long past its SLA deadline
};

console.log('\n' + HEAVY);
console.log('  DeliveryProof v0.9.1 — audit bundle inspection');
console.log(HEAVY);
console.log(`
  This demo settles once on the reference mock rail, then builds an audit bundle
  from the existing contract, evidence, signed receipt, and rail status. The
  bundle lets an operator re-check bindings; it does not create a new proof,
  contact a telemetry backend, or move money.
`);

const rail = createMockEscrowRail({ settlementPublicKey: settlementKey.publicKey });
const result = await settle({
  contract,
  produceEvidence: () => ({ output: [1, 3, 5, 9] }),
  verifier: builtinReplayVerifier,
  rail,
  settlementKey,
});
const railStatus = await rail.status(result.hold.holdId);
const bundle = buildAuditBundle({
  receipt: result.receipt,
  contract: result.contract,
  evidence: result.evidence,
  railStatus,
});

console.log(LINE);
console.log('  Bound artifacts');
console.log(LINE);
kv('decision', result.receipt.decision.toUpperCase());
kv('rail state', railStatus.state);
kv('contract hash', bundle.contract.hash);
kv('receipt contractHash', bundle.receipt.contractHash);
kv('evidence hash', bundle.evidence.hash);
kv('receipt evidenceHash', bundle.receipt.evidenceHash);
kv('rail status hash', bundle.railStatus.hash);
kv('bundle canonical hash', bundle.canonicalHash);

console.log('\n' + LINE);
console.log('  Binding checks');
console.log(LINE);
for (const [name, ok] of Object.entries(bundle.checks)) {
  kv(name, ok);
}

const tamperedContract = {
  ...result.contract,
  price: { amount: 999, currency: 'USDC' },
};
const tampered = buildAuditBundle({
  receipt: result.receipt,
  contract: tamperedContract,
  evidence: result.evidence,
  railStatus,
});

console.log('\n' + LINE);
console.log('  Tamper check');
console.log(LINE);
kv('tampered contract hash', sha256hex(tamperedContract));
kv('matches receipt?', tampered.checks.contractHashMatchesReceipt);
kv('surface', 'contractHashMatchesReceipt=false');

console.log('\n' + HEAVY);
console.log('  Takeaway: buildAuditBundle() collates inspectable receipt bindings.');
console.log('  It is an inspection aid, not a new proof, rail, or telemetry system.');
console.log(HEAVY + '\n');

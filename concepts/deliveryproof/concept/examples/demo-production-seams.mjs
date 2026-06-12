// examples/demo-production-seams.mjs
//
// Shows the v0.9 adapter conformance seams plus the v0.9.1 fail-closed money-layer
// guarantees. These are local reference checks for
// implementers: a companion package can bring Stripe/Postgres/KMS/chain-specific
// code and run the exported conformance suites in its own CI.
//
// This demo uses only in-repo reference adapters. It does not move real money,
// call a provider, submit transactions, or prove cross-process database locking.
//
//   Run: node examples/demo-production-seams.mjs

import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import {
  canonicalize,
  createDurableEscrowRail,
  createMockEscrowRail,
  createWalReplayStore,
  generateKeypair,
  keyId,
  PROTOCOL_VERSION,
  runRailConformance,
  runReplayStoreConformance,
  sha256hex,
  sign,
  toErc8004ValidationPayload,
  toErc8183EvaluatorResult,
  verifyReceipt,
} from '../src/index.mjs';

const HEAVY = '='.repeat(74);
const LINE = '-'.repeat(74);

function printCases(title, result) {
  console.log('\n' + LINE);
  console.log('  ' + title + ' -> ' + (result.ok ? 'PASS' : 'FAIL'));
  console.log(LINE);
  for (const entry of result.cases) {
    console.log('  ' + (entry.ok ? 'PASS ' : 'FAIL ') + entry.name + (entry.error ? ` :: ${entry.error}` : ''));
  }
}

console.log('\n' + HEAVY);
console.log('  DeliveryProof v0.9.1 — production adapter seams');
console.log(HEAVY);
console.log(`
  The core package stays rail-neutral. Production integrations should live in
  companion packages and prove their adapters against the exported conformance
  suites. Here we run those suites against the in-repo reference adapters.
`);

const railResult = await runRailConformance({
  createRail: ({ settlementPublicKey }) => createMockEscrowRail({ logger: false, settlementPublicKey }),
});
printCases('mock rail conformance', railResult);

const dir = mkdtempSync(join(tmpdir(), 'deliveryproof-demo-replay-store-'));
try {
  const railLogPath = join(dir, 'durable-rail.jsonl');
  const durableRailResult = await runRailConformance({
    createRail: ({ settlementPublicKey }) => createDurableEscrowRail({ logPath: railLogPath, settlementPublicKey }),
    supportsRestart: true,
  });
  printCases('durable rail conformance', durableRailResult);

  const logPath = join(dir, 'replay.jsonl');
  const replayResult = await runReplayStoreConformance({
    createStore: () => createWalReplayStore({ logPath }),
    supportsRestart: true,
  });
  printCases('WAL replay-store conformance', replayResult);
} finally {
  rmSync(dir, { recursive: true, force: true });
}

console.log('\n' + HEAVY);
console.log('  Takeaway: adapters can be certified without adding provider code here.');
console.log('  The WAL store is in-process; production stores should enforce atomic');
console.log('  double-reserve rejection with their own durable uniqueness mechanism.');
console.log(HEAVY + '\n');

// ---------------------------------------------------------------------------
// v0.9.1 — fail-closed money layer (the dual-agent review hardening).
//
// The conformance suite above already exercises the rail's refusal to pay on a
// verdict-contradicting receipt. Here we show the three v0.9.1 guarantees
// explicitly, by forging settlement attempts and watching them fail:
//   1. the consistency gate  — rails reject a decision<->verdict.ok contradiction;
//   2. requireSignature      — opt-in mandatory settlement-signature verification;
//   3. interop refusal       — no contradictory receipt becomes a chain-facing win.
//
// Nothing moves money. Each forged attempt MUST be rejected; if any is accepted
// the demo throws and exits non-zero, so this doubles as a live regression check.
// ---------------------------------------------------------------------------

// Hand-build a signed receipt bound to a hold (mirrors what settle() emits). The
// signingKey lets us forge "signed by an attacker" receipts; verdictOk lets us
// forge a release receipt that carries a failing verdict.
function buildReceipt({ contract, hold, decision, verdictOk, signingKey, signerKeyId }) {
  const evidence = { contractId: contract.id, output: { ok: verdictOk } };
  const unsigned = {
    protocolVersion: PROTOCOL_VERSION,
    contractId: contract.id,
    contractHash: sha256hex(contract),
    railId: hold.railId,
    holdId: hold.holdId,
    amount: hold.amount,
    currency: hold.currency,
    verdict: { ok: verdictOk, tier: 'A', verifier: 'demo', reason: verdictOk ? 'passed' : 'failed', checkedAt: 2 },
    evidenceHash: sha256hex(evidence),
    routeDecision: null,
    lifecycle: [{ state: 'decision', at: 2, decision }],
    nonceRegistryKey: null,
    decision,
    signerKeyId,
    issuedAt: 3,
  };
  return { ...unsigned, signature: sign(signingKey.privateKey, canonicalize(unsigned)) };
}

function demoContract(rail, label) {
  return {
    protocolVersion: PROTOCOL_VERSION,
    id: `dc_${label}`,
    buyer: 'buyer_demo',
    seller: 'seller_demo',
    intent: `fail-closed demo ${label}`,
    deliverableType: 'application/json',
    predicate: { kind: 'testsuite', params: { op: 'identity' } },
    price: { amount: 5, currency: 'USDC' },
    sla: { deadlineMs: 60000 },
    refundRule: 'full-refund-on-fail',
    railId: rail.id,
    nonce: `nonce_${label}`,
    createdAt: 1,
  };
}

// Run fn(); REQUIRE it to throw. Returns the rejection message for printing.
async function expectReject(label, fn) {
  try {
    await fn();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.startsWith('DEMO INVARIANT BROKEN')) throw err;
    return msg;
  }
  throw new Error(`DEMO INVARIANT BROKEN: ${label} should have been rejected but was accepted`);
}

console.log('\n' + HEAVY);
console.log('  DeliveryProof v0.9.1 — fail-closed money layer');
console.log(HEAVY);

const settlementKey = generateKeypair();
const attackerKey = generateKeypair();
const settlementKeyId = keyId(settlementKey.publicKey);

// 1) Consistency gate on a keyless reference rail.
{
  console.log('\n' + LINE);
  console.log('  1) consistency gate: a "release" receipt that carries verdict.ok=false');
  console.log(LINE);
  const rail = createMockEscrowRail({ logger: false });
  const contract = demoContract(rail, 'consistency');
  const hold = await rail.authorize(contract);

  const forged = buildReceipt({ contract, hold, decision: 'release', verdictOk: false, signingKey: settlementKey, signerKeyId: settlementKeyId });
  const why = await expectReject('forged release+verdict.ok=false', () => rail.capture(hold, forged));
  console.log('  forged "pay me" receipt (decision=release, verdict.ok=false) -> REJECTED');
  console.log('    ' + why);
  console.log('  hold after attack: ' + (await rail.status(hold.holdId)).state.toUpperCase() + ' (funds not released)');

  const honest = buildReceipt({ contract, hold, decision: 'release', verdictOk: true, signingKey: settlementKey, signerKeyId: settlementKeyId });
  console.log('  honest release receipt (verdict.ok=true)  -> ' + (await rail.capture(hold, honest)).state.toUpperCase());
}

// 2) requireSignature: opt-in mandatory settlement-signature verification.
{
  console.log('\n' + LINE);
  console.log('  2) requireSignature: a forged-but-internally-consistent receipt');
  console.log(LINE);

  // Fail-closed construction: requireSignature without a key is refused outright.
  const ctorWhy = await expectReject('requireSignature without key', async () =>
    createMockEscrowRail({ logger: false, requireSignature: true }));
  console.log('  createMockEscrowRail({ requireSignature:true }) with no key -> REFUSED at construction');
  console.log('    ' + ctorWhy);

  const rail = createMockEscrowRail({ logger: false, settlementPublicKey: settlementKey.publicKey, requireSignature: true });
  const contract = demoContract(rail, 'requiresig');
  const hold = await rail.authorize(contract);

  // Internally consistent (release + verdict.ok=true) but signed by an attacker:
  // the consistency gate alone would pass it; only the signature check stops it.
  const forged = buildReceipt({ contract, hold, decision: 'release', verdictOk: true, signingKey: attackerKey, signerKeyId: settlementKeyId });
  console.log('  forged receipt is internally consistent; valid settlement signature? ' + (verifyReceipt(forged, settlementKey.publicKey) ? 'YES' : 'NO'));
  const why = await expectReject('attacker-signed receipt', () => rail.capture(hold, forged));
  console.log('  attacker-signed release receipt -> REJECTED');
  console.log('    ' + why);
  console.log('  hold after attack: ' + (await rail.status(hold.holdId)).state.toUpperCase());

  const honest = buildReceipt({ contract, hold, decision: 'release', verdictOk: true, signingKey: settlementKey, signerKeyId: settlementKeyId });
  console.log('  genuine settlement-signed receipt -> ' + (await rail.capture(hold, honest)).state.toUpperCase());
}

// 3) Interop refuses to project a contradictory receipt as a chain-facing success.
{
  console.log('\n' + LINE);
  console.log('  3) interop: a contradictory receipt cannot become an on-chain success');
  console.log(LINE);
  const rail = createMockEscrowRail({ logger: false });
  const contract = demoContract(rail, 'interop');
  const hold = await rail.authorize(contract);

  const contradictory = buildReceipt({ contract, hold, decision: 'release', verdictOk: false, signingKey: settlementKey, signerKeyId: settlementKeyId });
  const why8004 = await expectReject('erc8004 contradiction', async () => toErc8004ValidationPayload(contradictory));
  const why8183 = await expectReject('erc8183 contradiction', async () => toErc8183EvaluatorResult(contradictory, { jobId: 'job-1' }));
  console.log('  toErc8004ValidationPayload(contradictory) -> REFUSED');
  console.log('    ' + why8004);
  console.log('  toErc8183EvaluatorResult(contradictory)   -> REFUSED');
  console.log('    ' + why8183);

  const honest = buildReceipt({ contract, hold, decision: 'release', verdictOk: true, signingKey: settlementKey, signerKeyId: settlementKeyId });
  const erc8004 = toErc8004ValidationPayload(honest);
  const erc8183 = toErc8183EvaluatorResult(honest, { jobId: 'job-1' });
  console.log('  honest release receipt -> ERC-8004 response=' + erc8004.response + ', ERC-8183 action=' + erc8183.action);

  console.log('\n' + HEAVY);
  console.log('  Takeaway: the money-safety invariant is re-enforced at the money/interop');
  console.log('  layer, not just inside settle(). The consistency gate blocks contradictory');
  console.log('  receipts everywhere; requireSignature additionally blocks forged-but-');
  console.log('  consistent unsigned receipts. A real adapter still owns custody and finality.');
  console.log(HEAVY + '\n');
}

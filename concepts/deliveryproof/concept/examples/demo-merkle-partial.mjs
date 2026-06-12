// examples/demo-merkle-partial.mjs
//
// DeliveryProof — PARTIAL MERKLE money shot (Node v22+).
//
//   Run: node examples/demo-merkle-partial.mjs
//
// THE POINT:
//   A seller does NOT send the full dataset to the verifier. Instead it sends
//   only the verifier-selected rows plus Merkle proofs. DeliveryProof verifies
//   that each sampled row is included in the committed dataset root and satisfies
//   row-level constraints, then releases or refunds.
//
// Honest scope:
//   This proves inclusion + sampled-row conformance only. It does NOT prove
//   global row count truth, uniqueness, aggregates, or whole-dataset correctness.
//   Use the full dataset verifier for those properties.

import { buildMerkleProof, merkleRoot } from '../src/protocol/merkle.mjs';
import { selectSampleIndices } from '../src/protocol/merkle-sample.mjs';
import { generateKeypair, keyId } from '../src/protocol/crypto.mjs';
import { createMockEscrowRail } from '../src/rails/escrow-mock.mjs';
import { settle, verifyReceipt } from '../src/engine/deliveryproof.mjs';
import { routeVerifier } from '../src/router/policy.mjs';

const LINE = '─'.repeat(74);
const HEAVY = '═'.repeat(74);

function banner(title) {
  console.log('\n' + HEAVY);
  console.log('  ' + title);
  console.log(HEAVY);
}

function section(title) {
  console.log('\n' + LINE);
  console.log('  ' + title);
  console.log(LINE);
}

function kv(label, value) {
  console.log('  ' + String(label).padEnd(25) + ': ' + value);
}

function yn(value) {
  return value ? 'YES' : 'NO';
}

const ROW_COUNT = 64;
const SAMPLE_K = 5;
const CONTRACT_NONCE = 'nonce-merkle-partial-demo';

function buildRows() {
  const regions = ['us', 'eu', 'apac', 'latam'];
  const rows = [];
  for (let i = 0; i < ROW_COUNT; i++) {
    rows.push({
      id: i + 1,
      region: regions[i % regions.length],
      revenue: 100 + (i % 20),
      active: i % 3 !== 0,
    });
  }
  return rows;
}

function contractFor({ buyer, seller, settlementKey, root }) {
  return {
    id: 'dc_merkle_partial_demo',
    buyer: keyId(buyer.publicKey),
    seller: keyId(seller.publicKey),
    intent: 'prove selected customer rows belong to the committed dataset',
    deliverableType: 'dataset-merkle-sample',
    predicate: {
      kind: 'dataset-merkle-sample',
      params: {
        merkleRoot: root,
        rowCount: ROW_COUNT,
        k: SAMPLE_K,
        columns: [
          { name: 'id', type: 'number', required: true, range: { min: 1 } },
          { name: 'region', type: 'string', required: true, domain: ['us', 'eu', 'apac', 'latam'], regex: '^(us|eu|apac|latam)$' },
          { name: 'revenue', type: 'number', required: true, range: { min: 0, max: 200 } },
          { name: 'active', type: 'boolean', required: true },
        ],
      },
    },
    price: { amount: 25, currency: 'USDC' },
    sla: { deadlineMs: 30_000 },
    refundRule: 'refund if sampled rows are not included or do not satisfy row-level constraints',
    railId: 'escrow-mock',
    nonce: CONTRACT_NONCE,
    createdAt: 1_800_000_000_000,
    settlementKeyId: keyId(settlementKey.publicKey),
  };
}

function evidenceFor(contract, rows) {
  const { merkleRoot: root, rowCount, k } = contract.predicate.params;
  const selected = selectSampleIndices(contract.nonce, root, rowCount, k);
  return {
    output: { mode: 'partial-merkle-sample', selected },
    merkleSamples: selected.map((index) => {
      const proof = buildMerkleProof(rows, index);
      return { index, row: proof.leaf, proof };
    }),
  };
}

async function runSettlement({ title, contract, route, settlementKey, evidence }) {
  section(title);
  const rail = createMockEscrowRail();
  const result = await settle({
    contract,
    produceEvidence: () => evidence,
    verifier: route.verifier,
    routeDecision: route.routeDecision,
    rail,
    settlementKey,
    now: () => 1_800_000_001_000,
  });

  kv('router selected', route.routeDecision.selected);
  kv('predicate met?', yn(result.verdict.ok));
  kv('reason', result.verdict.reason);
  kv('decision', result.receipt.decision.toUpperCase());
  kv('seller paid?', yn(result.hold.state === 'captured'));
  kv('receipt valid?', yn(verifyReceipt(result.receipt, settlementKey.publicKey)));
  return result;
}

banner('DeliveryProof — PARTIAL MERKLE money shot: prove rows without the full dataset');

console.log(`
  A buyer pays 25 USDC for sampled proof about a committed customer dataset.
  The verifier does NOT receive all ${ROW_COUNT} rows. It receives only ${SAMPLE_K}
  verifier-selected sorted-leaf indices, the corresponding rows, and Merkle proofs.

  Success path: every supplied row is included in the committed root and satisfies
  row-level rules, so payment releases.

  Attack paths: the seller tries to swap a row or cherry-pick an unselected row.
  DeliveryProof refunds because the proof no longer matches the verifier-selected
  contract-bound sample.
`);

const rows = buildRows();
const root = merkleRoot(rows);
const buyer = generateKeypair();
const seller = generateKeypair();
const settlementKey = generateKeypair();
const contract = contractFor({ buyer, seller, settlementKey, root });
const route = routeVerifier(contract, { policy: { deliverableType: 'dataset-merkle-sample', minAssurance: 3 } });
const goodEvidence = evidenceFor(contract, rows);

kv('buyer keyId', keyId(buyer.publicKey));
kv('seller keyId', keyId(seller.publicKey));
kv('settlement auth', keyId(settlementKey.publicKey));
kv('committed root', root.slice(0, 24) + '…');
kv('selected sorted indices', goodEvidence.merkleSamples.map((sample) => sample.index).join(', '));

const release = await runSettlement({
  title: 'SUCCESS — supplied rows are included and conform',
  contract,
  route,
  settlementKey,
  evidence: goodEvidence,
});

const swapped = {
  ...goodEvidence,
  merkleSamples: goodEvidence.merkleSamples.map((sample, index) =>
    index === 0
      ? { ...sample, row: { ...sample.row, revenue: sample.row.revenue + 999 } }
      : sample,
  ),
};
const leafSwap = await runSettlement({
  title: 'ATTACK 1 — proof is for row A, seller asks us to check row B',
  contract,
  route,
  settlementKey,
  evidence: swapped,
});

const selected = new Set(goodEvidence.merkleSamples.map((sample) => sample.index));
const unselected = [...Array(ROW_COUNT).keys()].find((index) => !selected.has(index));
const cherryProof = buildMerkleProof(rows, unselected);
const cherryPicked = {
  ...goodEvidence,
  merkleSamples: [
    { index: unselected, row: cherryProof.leaf, proof: cherryProof },
    ...goodEvidence.merkleSamples.slice(1),
  ],
};
const cherryPick = await runSettlement({
  title: 'ATTACK 2 — seller cherry-picks an unselected but valid row',
  contract,
  route,
  settlementKey,
  evidence: cherryPicked,
});

banner('RESULT');
kv('valid partial proof', `${release.receipt.decision.toUpperCase()} (seller paid: ${yn(release.hold.state === 'captured')})`);
kv('leaf-swap attempt', `${leafSwap.receipt.decision.toUpperCase()} (seller paid: ${yn(leafSwap.hold.state === 'captured')})`);
kv('cherry-pick attempt', `${cherryPick.receipt.decision.toUpperCase()} (seller paid: ${yn(cherryPick.hold.state === 'captured')})`);

console.log(`
  Takeaway: partial Merkle mode lets a buyer verify selected rows against a
  committed dataset root WITHOUT giving the verifier the full dataset. The sample
  indices are derived from nonce + root + rowCount + k, so the seller cannot pick
  easier rows after the fact.

  Honest scope: this proves inclusion + sampled-row conformance only. It does
  not prove global rowCount truth, uniqueness, aggregates, or full-dataset truth.
`);

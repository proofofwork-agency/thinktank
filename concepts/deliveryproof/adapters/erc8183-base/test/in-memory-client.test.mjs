// test/in-memory-client.test.mjs
// The in-memory (FAKE) Erc8183Client state machine, in isolation.
//
// SCOPE / HONESTY: this tests the test seam itself — NO rail, NO chain, NO RPC, NO
// keys, NO live tx. The whole point of this client is to model ERC-8183 evaluator
// semantics STRICTLY: getJob auto-provisions a funded Submitted job; complete/reject
// act ONLY on Submitted and THROW on a second terminal transition. That strictness
// is what forces the rail's idempotency to come from reconcile-via-getJob rather
// than a lenient fake. If these guards regress, the conformance suite would pass for
// the wrong reasons, so they are pinned here directly.
// TESTNET / LOCAL ONLY — no mainnet, no real funds, no autonomous live tx.

import test from 'node:test';
import assert from 'node:assert/strict';

import { createInMemoryErc8183Client } from '../src/clients/in-memory.mjs';
import { JobStatus } from '../src/job-status.mjs';
import { Erc8183NotSettleableError, Erc8183RailError } from '../src/errors.mjs';

test('getJob auto-provisions an unknown job as a funded Submitted job (5/USDC)', () => {
  const client = createInMemoryErc8183Client();
  const job = client.getJob('job-1');
  assert.equal(job.status, JobStatus.Submitted);
  assert.equal(job.amount, 5);
  assert.equal(job.currency, 'USDC');
  assert.equal(job.jobId, 'job-1');
});

test('getJob normalizes number and string jobIds to the same job', () => {
  const client = createInMemoryErc8183Client();
  const created = client.getJob(5);
  client.complete(5, { reason: '0xabc' });
  // String "5" must address the SAME job a numeric 5 created, else a restart
  // lookup (which stringifies) would miss the terminal state.
  const viaString = client.getJob('5');
  assert.equal(created.jobId, '5');
  assert.equal(viaString.status, JobStatus.Completed);
});

test('complete moves Submitted -> Completed and returns a synthetic mem: txRef', () => {
  const client = createInMemoryErc8183Client();
  client.getJob('c1');
  const res = client.complete('c1', { reason: '0xdeadbeef' });
  assert.equal(res.status, JobStatus.Completed);
  assert.match(res.txRef, /^mem:complete:c1:/);
  assert.equal(client.getJob('c1').status, JobStatus.Completed);
});

test('reject moves Submitted -> Rejected and returns a synthetic mem: txRef', () => {
  const client = createInMemoryErc8183Client();
  client.getJob('r1');
  const res = client.reject('r1', { reason: '0xfeed' });
  assert.equal(res.status, JobStatus.Rejected);
  assert.match(res.txRef, /^mem:reject:r1:/);
  assert.equal(client.getJob('r1').status, JobStatus.Rejected);
});

test('a SECOND complete on an already-Completed job THROWS (no lenient re-pay)', () => {
  const client = createInMemoryErc8183Client();
  client.getJob('c2');
  client.complete('c2', { reason: '0x1' });
  assert.throws(
    () => client.complete('c2', { reason: '0x1' }),
    (err) => {
      assert.ok(err instanceof Erc8183NotSettleableError, `expected Erc8183NotSettleableError, got ${err}`);
      assert.equal(err.status, JobStatus.Completed);
      return true;
    },
  );
});

test('reject after complete THROWS — the fake never flips a terminal job', () => {
  const client = createInMemoryErc8183Client();
  client.getJob('c3');
  client.complete('c3');
  assert.throws(() => client.reject('c3'), Erc8183NotSettleableError);
  // Status is unchanged: still Completed.
  assert.equal(client.getJob('c3').status, JobStatus.Completed);
});

test('complete/reject refuse a non-Submitted (Open/Funded/Expired) job', () => {
  const client = createInMemoryErc8183Client();
  client.seedJob('open', { status: JobStatus.Open });
  client.seedJob('funded', { status: JobStatus.Funded });
  client.seedJob('expired', { status: JobStatus.Expired });
  assert.throws(() => client.complete('open'), Erc8183NotSettleableError);
  assert.throws(() => client.reject('funded'), Erc8183NotSettleableError);
  assert.throws(() => client.complete('expired'), Erc8183NotSettleableError);
});

test('complete/reject on an UNKNOWN job THROW (evaluator must read a funded job first)', () => {
  const client = createInMemoryErc8183Client();
  // No getJob call, so no auto-provisioned job exists; a state-changing call must
  // not silently create one.
  assert.throws(() => client.complete('ghost'), Erc8183NotSettleableError);
  assert.throws(() => client.reject('ghost'), Erc8183NotSettleableError);
});

test('autoCreate:false makes getJob throw on an unknown job', () => {
  const client = createInMemoryErc8183Client({ autoCreate: false });
  assert.throws(() => client.getJob('missing'), Erc8183RailError);
});

test('a shared jobs Map survives a simulated restart (two clients, one chain state)', () => {
  const jobs = new Map();
  const before = createInMemoryErc8183Client({ jobs });
  before.getJob('shared');
  before.complete('shared', { reason: '0x2' });

  // "Restart": a brand-new client constructed over the SAME Map sees the terminal.
  const after = createInMemoryErc8183Client({ jobs });
  assert.equal(after.getJob('shared').status, JobStatus.Completed);
  // And it still refuses to re-settle the terminal job.
  assert.throws(() => after.complete('shared'), Erc8183NotSettleableError);
});

test('_jobs() exposes the same backing Map instance passed in', () => {
  const jobs = new Map();
  const client = createInMemoryErc8183Client({ jobs });
  assert.equal(client._jobs(), jobs);
  assert.equal(client.jobs, jobs);
});

test('getJob returns a VIEW clone — mutating it does not corrupt the store', () => {
  const client = createInMemoryErc8183Client();
  const view = client.getJob('v1');
  view.status = JobStatus.Completed;
  view.amount = 999;
  const fresh = client.getJob('v1');
  assert.equal(fresh.status, JobStatus.Submitted, 'store status must be untouched by mutating a view');
  assert.equal(fresh.amount, 5, 'store amount must be untouched by mutating a view');
});

test('seedJob can stage any lifecycle status and defaults to a funded Submitted job', () => {
  const client = createInMemoryErc8183Client();
  const seeded = client.seedJob('s1');
  assert.equal(seeded.status, JobStatus.Submitted);
  assert.equal(seeded.amount, 5);
  assert.equal(seeded.currency, 'USDC');

  const completed = client.seedJob('s2', { status: JobStatus.Completed, amount: 42, currency: 'DAI' });
  assert.equal(completed.status, JobStatus.Completed);
  assert.equal(completed.amount, 42);
  assert.equal(completed.currency, 'DAI');
  // A seeded Completed job is terminal: complete must throw.
  assert.throws(() => client.complete('s2'), Erc8183NotSettleableError);
});

test('normalizeJobId rejects null/undefined and non-stringable shapes', () => {
  const client = createInMemoryErc8183Client();
  assert.throws(() => client.getJob(null), Erc8183RailError);
  assert.throws(() => client.getJob(undefined), Erc8183RailError);
  assert.throws(() => client.getJob({}), Erc8183RailError);
  assert.throws(() => client.getJob(''), Erc8183RailError);
});

test('listJobs snapshots every job as a view (no live references)', () => {
  const client = createInMemoryErc8183Client();
  client.getJob('l1');
  client.seedJob('l2', { status: JobStatus.Rejected });
  const all = client.listJobs();
  const byId = Object.fromEntries(all.map((j) => [j.jobId, j.status]));
  assert.equal(byId.l1, JobStatus.Submitted);
  assert.equal(byId.l2, JobStatus.Rejected);
  // Mutating a snapshot entry does not affect the store.
  all[0].status = JobStatus.Expired;
  assert.equal(client.getJob('l1').status, JobStatus.Submitted);
});

import test from 'node:test';
import assert from 'node:assert/strict';

import { sha256hex } from '../src/protocol/canonical.mjs';
import { runBuiltinReplay } from '../src/verifiers/builtin-replay-runner.mjs';
import { builtinReplayVerifier } from '../src/verifiers/builtin-replay.mjs';

function evidenceFor(output) {
  return {
    contractId: 'c1',
    nonce: 'n1',
    output,
    outputHash: sha256hex(output),
    producedAt: 0,
  };
}

test('builtin-replay worker: verifier still passes correct replay', async () => {
  const verdict = await builtinReplayVerifier.verify(
    { predicate: { kind: 'builtin-replay', params: { op: 'reverse', input: [1, 2, 3] } } },
    evidenceFor([3, 2, 1]),
  );
  assert.equal(verdict.ok, true);
  assert.match(verdict.reason, /bounded worker/);
});

test('builtin-replay worker: rejects oversized tasks before worker execution', async () => {
  const result = await runBuiltinReplay(
    { op: 'reverse', input: ['x'.repeat(100)], actual: ['x'.repeat(100)] },
    { maxInputBytes: 64 },
  );
  assert.equal(result.ok, false);
  assert.match(result.reason, /too large/);
});

test('builtin-replay worker: rejects deeply nested tasks before worker execution', async () => {
  const result = await runBuiltinReplay(
    { op: 'reverse', input: [[[[[1]]]]], actual: [[[[[1]]]]] },
    { maxDepth: 4 },
  );
  assert.equal(result.ok, false);
  assert.match(result.reason, /too deep/);
});

test('builtin-replay worker: terminates worker on timeout', async () => {
  const result = await runBuiltinReplay(
    { op: 'reverse', input: [1], actual: [1] },
    { timeoutMs: 25, workerURL: new URL('../test-fixtures/hang-worker.mjs', import.meta.url) },
  );
  assert.equal(result.ok, false);
  assert.match(result.reason, /timed out/);
});

test('builtin-replay worker: reports worker crash as a failed verdict input', async () => {
  const result = await runBuiltinReplay(
    { op: 'reverse', input: [1], actual: [1] },
    { timeoutMs: 250, workerURL: new URL('../test-fixtures/crash-worker.mjs', import.meta.url) },
  );
  assert.equal(result.ok, false);
  assert.match(result.reason, /worker error|exited/);
});

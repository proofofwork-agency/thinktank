export const REPLAY_STORE_CONFORMANCE_CASES = Object.freeze([
  'reserve-once',
  'reject-replay-same-fingerprint',
  'reject-replay-conflicting-fingerprint',
  'mark-advances-state',
  'get-unknown-returns-null',
  'survive-restart',
  'reject-concurrent-double-reserve',
  'reject-reserve-into-terminal-state',
  'reject-terminal-regression',
  'reject-terminal-flip',
  'idempotent-same-terminal-mark',
]);

/**
 * Run the replay-store conformance suite against any store implementation.
 *
 * The bundled WAL store is in-process and has no cross-process lock. This suite
 * proves the interface contract for a single process; production Postgres/Redis
 * stores should satisfy reject-concurrent-double-reserve with atomic uniqueness.
 *
 * @param {Object} opts
 * @param {(ctx: Object) => (Object|Promise<Object>)} opts.createStore
 * @param {boolean} [opts.supportsRestart]
 * @returns {Promise<{ok:boolean,cases:{name:string,ok:boolean,error?:string}[]}>}
 */
export async function runReplayStoreConformance({ createStore, supportsRestart = false } = {}) {
  if (typeof createStore !== 'function') {
    throw new TypeError('runReplayStoreConformance: createStore must be a function');
  }
  const ctx = { createStore };
  const runners = new Map([
    ['reserve-once', reserveOnce],
    ['reject-replay-same-fingerprint', rejectReplaySameFingerprint],
    ['reject-replay-conflicting-fingerprint', rejectReplayConflictingFingerprint],
    ['mark-advances-state', markAdvancesState],
    ['get-unknown-returns-null', getUnknownReturnsNull],
    ['survive-restart', surviveRestart],
    ['reject-concurrent-double-reserve', rejectConcurrentDoubleReserve],
    ['reject-reserve-into-terminal-state', rejectReserveIntoTerminalState],
    ['reject-terminal-regression', rejectTerminalRegression],
    ['reject-terminal-flip', rejectTerminalFlip],
    ['idempotent-same-terminal-mark', idempotentSameTerminalMark],
  ]);

  const cases = [];
  for (const name of REPLAY_STORE_CONFORMANCE_CASES) {
    if (name === 'survive-restart' && !supportsRestart) continue;
    try {
      await runners.get(name)(ctx);
      cases.push({ name, ok: true });
    } catch (err) {
      cases.push({ name, ok: false, error: err instanceof Error ? err.message : String(err) });
    }
  }
  return { ok: cases.every((entry) => entry.ok), cases };
}

/**
 * Register one node:test test that fails with the conformance case table.
 *
 * @param {Function} test node:test test function
 * @param {import('node:assert/strict')} assert node:assert/strict module
 * @param {Object} opts runReplayStoreConformance options plus optional name
 * @returns {*}
 */
export function registerReplayStoreConformance(test, assert, opts = {}) {
  const name = opts.name ?? 'replay store conformance';
  return test(name, async () => {
    const result = await runReplayStoreConformance(opts);
    assert.equal(result.ok, true, formatConformanceFailures(result));
  });
}

function formatConformanceFailures(result) {
  return result.cases
    .map((entry) => entry.ok ? `PASS ${entry.name}` : `FAIL ${entry.name}: ${entry.error}`)
    .join('\n');
}

async function reserveOnce(ctx) {
  const store = await makeStore(ctx, 'reserve-once');
  await reserve(store, record('reserve-once'));
  const entry = await store.get('key-reserve-once');
  assertEntry(entry, 'fingerprint-reserve-once', 'reserved', 'reserve must write a reserved entry');
}

async function rejectReplaySameFingerprint(ctx) {
  const store = await makeStore(ctx, 'reject-replay-same-fingerprint');
  const first = record('reject-replay-same-fingerprint');
  await reserve(store, first);
  await assertRejects(
    () => reserve(store, first),
    'reserve must reject replay of the same key and fingerprint',
  );
}

async function rejectReplayConflictingFingerprint(ctx) {
  const store = await makeStore(ctx, 'reject-replay-conflicting-fingerprint');
  const first = record('reject-replay-conflicting-fingerprint');
  await reserve(store, first);
  await assertRejects(
    () => reserve(store, { ...first, fingerprint: 'fingerprint-conflict' }),
    'reserve must reject replay of the same key with a different fingerprint',
  );
}

async function markAdvancesState(ctx) {
  const store = await makeStore(ctx, 'mark-advances-state');
  const first = record('mark-advances-state');
  await reserve(store, first);
  await store.mark(first.key, 'captured', 2);
  const entry = await store.get(first.key);
  assertEntry(entry, first.fingerprint, 'captured', 'mark must advance state');
}

async function getUnknownReturnsNull(ctx) {
  const store = await makeStore(ctx, 'get-unknown-returns-null');
  const entry = await store.get('missing-key');
  if (entry !== null) {
    throw new Error(`get of an unknown key must return null, got ${JSON.stringify(entry)}`);
  }
}

async function surviveRestart(ctx) {
  const first = await makeStore(ctx, 'survive-restart', { phase: 'initial' });
  const firstRecord = record('survive-restart');
  await reserve(first, firstRecord);
  await first.mark(firstRecord.key, 'refunded', 2);

  const restarted = await makeStore(ctx, 'survive-restart', { phase: 'restart', previousStore: first });
  const entry = await restarted.get(firstRecord.key);
  assertEntry(entry, firstRecord.fingerprint, 'refunded', 'restart must recover marked state');
}

async function rejectConcurrentDoubleReserve(ctx) {
  const store = await makeStore(ctx, 'reject-concurrent-double-reserve');
  const first = record('reject-concurrent-double-reserve');
  const attempts = await Promise.allSettled([
    Promise.resolve().then(() => reserve(store, first)),
    Promise.resolve().then(() => reserve(store, first)),
  ]);
  const fulfilled = attempts.filter((entry) => entry.status === 'fulfilled').length;
  const rejected = attempts.filter((entry) => entry.status === 'rejected').length;
  if (fulfilled !== 1 || rejected !== 1) {
    throw new Error(`concurrent double reserve must produce exactly one success and one rejection, got ${fulfilled} success/${rejected} rejection`);
  }
}

// The replay-key state machine. `mark()` authenticates only the key, so any
// caller who knows it can drive a transition. Monotonic transitions remove the
// ones an attacker wants: a store must not let a reservation be born settled, a
// terminal be regressed (which would free a spent nonce), or one terminal flip
// to the other. Added after adversarial review demonstrated all three.

async function rejectReserveIntoTerminalState(ctx) {
  const store = await makeStore(ctx, 'reject-reserve-into-terminal-state');
  const first = record('reject-reserve-into-terminal-state');
  await assertRejects(
    () => reserve(store, { ...first, state: 'captured' }),
    'reserve must refuse to create a reservation already in a terminal state',
  );
}

async function rejectTerminalRegression(ctx) {
  const store = await makeStore(ctx, 'reject-terminal-regression');
  const first = record('reject-terminal-regression');
  await reserve(store, first);
  await store.mark(first.key, 'captured', 2);
  await assertRejects(
    () => store.mark(first.key, 'reserved', 3),
    'mark must refuse to regress a terminal state back to reserved',
  );
  assertEntry(await store.get(first.key), first.fingerprint, 'captured', 'state must survive a rejected regression');
}

async function rejectTerminalFlip(ctx) {
  const store = await makeStore(ctx, 'reject-terminal-flip');
  const first = record('reject-terminal-flip');
  await reserve(store, first);
  await store.mark(first.key, 'captured', 2);
  await assertRejects(
    () => store.mark(first.key, 'refunded', 3),
    'mark must refuse to flip one terminal state to the other',
  );
}

async function idempotentSameTerminalMark(ctx) {
  const store = await makeStore(ctx, 'idempotent-same-terminal-mark');
  const first = record('idempotent-same-terminal-mark');
  await reserve(store, first);
  await store.mark(first.key, 'refunded', 2);
  // Retry safety: a settlement re-marking its OWN terminal must not throw.
  await store.mark(first.key, 'refunded', 3);
  assertEntry(await store.get(first.key), first.fingerprint, 'refunded', 'same-terminal re-mark must be idempotent');
}

async function makeStore(ctx, caseName, extra = {}) {
  const store = await ctx.createStore({ caseName, ...extra });
  assertStore(store);
  return store;
}

function assertStore(store) {
  if (!store || typeof store !== 'object') throw new Error('createStore must return a store object');
  for (const method of ['reserve', 'mark', 'get']) {
    if (typeof store[method] !== 'function') throw new Error(`store.${method} must be a function`);
  }
}

function record(label) {
  return {
    key: `key-${label}`,
    fingerprint: `fingerprint-${label}`,
    state: 'reserved',
    at: 1,
  };
}

async function reserve(store, entry) {
  return store.reserve(entry);
}

async function assertRejects(fn, message) {
  try {
    await fn();
  } catch {
    return;
  }
  throw new Error(message);
}

function assertEntry(entry, fingerprint, state, message) {
  if (!entry || typeof entry !== 'object') {
    throw new Error(`${message}: missing entry`);
  }
  if (entry.fingerprint !== fingerprint) {
    throw new Error(`${message}: expected fingerprint ${fingerprint}, got ${JSON.stringify(entry.fingerprint)}`);
  }
  if (entry.state !== state) {
    throw new Error(`${message}: expected state ${state}, got ${JSON.stringify(entry.state)}`);
  }
}

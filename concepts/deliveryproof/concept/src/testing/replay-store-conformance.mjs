export const REPLAY_STORE_CONFORMANCE_CASES = Object.freeze([
  'reserve-once',
  'reject-replay-same-fingerprint',
  'reject-replay-conflicting-fingerprint',
  'mark-advances-state',
  'get-unknown-returns-null',
  'survive-restart',
  'reject-concurrent-double-reserve',
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

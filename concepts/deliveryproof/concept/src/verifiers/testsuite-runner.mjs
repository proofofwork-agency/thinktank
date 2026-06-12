import { Worker } from 'node:worker_threads';
import { fileURLToPath } from 'node:url';

const DEFAULT_TIMEOUT_MS = 1000;
const DEFAULT_MAX_INPUT_BYTES = 512 * 1024;
const DEFAULT_MAX_DEPTH = 64;
const DEFAULT_RESOURCE_LIMITS = {
  maxOldGenerationSizeMb: 32,
  maxYoungGenerationSizeMb: 16,
  stackSizeMb: 4,
};

const WORKER_URL = new URL('./testsuite-worker.mjs', import.meta.url);

/**
 * Run objective replay in a worker thread with bounded wall-clock time and V8
 * resource limits. This does not make arbitrary JavaScript safe; the worker only
 * executes DeliveryProof's built-in deterministic replay operations.
 *
 * @param {{ op: string, input: *, actual: * }} task
 * @param {Object} [options]
 * @param {number} [options.timeoutMs]
 * @param {number} [options.maxInputBytes]
 * @param {number} [options.maxDepth]
 * @param {Object} [options.resourceLimits]
 * @param {URL} [options.workerURL] Test hook for timeout/crash fixtures.
 * @returns {Promise<{ ok: true, expected: *, matched: boolean } | { ok: false, reason: string }>}
 */
export async function runTestsuiteReplay(task, options = {}) {
  const timeoutMs = boundedPositiveInteger(options.timeoutMs, DEFAULT_TIMEOUT_MS, DEFAULT_TIMEOUT_MS, 'timeoutMs');
  const maxInputBytes = boundedPositiveInteger(options.maxInputBytes, DEFAULT_MAX_INPUT_BYTES, DEFAULT_MAX_INPUT_BYTES, 'maxInputBytes');
  const maxDepth = boundedPositiveInteger(options.maxDepth, DEFAULT_MAX_DEPTH, DEFAULT_MAX_DEPTH, 'maxDepth');
  const size = jsonSizeBytes(task);
  if (size > maxInputBytes) {
    return { ok: false, reason: `testsuite input too large (${size} bytes > ${maxInputBytes} bytes)` };
  }
  const depth = jsonDepth(task);
  if (depth > maxDepth) {
    return { ok: false, reason: `testsuite input too deep (${depth} > ${maxDepth})` };
  }

  return runWorkerTask(options.workerURL ?? WORKER_URL, task, {
    timeoutMs,
    resourceLimits: { ...DEFAULT_RESOURCE_LIMITS, ...(options.resourceLimits ?? {}) },
  });
}

/**
 * @param {URL} workerURL
 * @param {*} workerData
 * @param {{ timeoutMs: number, resourceLimits: Object }} options
 */
export function runWorkerTask(workerURL, workerData, options) {
  return new Promise((resolve) => {
    let settled = false;
    const worker = new Worker(workerURL, {
      workerData,
      resourceLimits: options.resourceLimits,
    });

    const done = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    };

    const timer = setTimeout(() => {
      worker.terminate().catch(() => {});
      done({ ok: false, reason: `testsuite worker timed out after ${options.timeoutMs}ms` });
    }, options.timeoutMs);

    worker.once('message', (message) => {
      done(message && typeof message === 'object' ? message : { ok: false, reason: 'testsuite worker returned a non-object result' });
    });
    worker.once('error', (err) => {
      done({ ok: false, reason: `testsuite worker error: ${err.message}` });
    });
    worker.once('exit', (code) => {
      if (code !== 0) {
        done({ ok: false, reason: `testsuite worker exited with code ${code}` });
      }
    });
  });
}

/**
 * @param {unknown} value
 * @param {number} fallback
 * @param {number} maximum
 * @param {string} label
 */
function boundedPositiveInteger(value, fallback, maximum, label) {
  if (value === undefined) return fallback;
  if (!Number.isInteger(value) || value <= 0) {
    throw new TypeError(`${label} must be a positive integer`);
  }
  return Math.min(value, maximum);
}

/**
 * @param {*} value
 */
function jsonSizeBytes(value) {
  return Buffer.byteLength(JSON.stringify(value), 'utf8');
}

/**
 * @param {*} value
 * @returns {number}
 */
function jsonDepth(value) {
  if (value === null || typeof value !== 'object') return 0;
  if (Array.isArray(value)) {
    return 1 + Math.max(0, ...value.map(jsonDepth));
  }
  return 1 + Math.max(0, ...Object.values(value).map(jsonDepth));
}

export function defaultTestsuiteWorkerPath() {
  return fileURLToPath(WORKER_URL);
}

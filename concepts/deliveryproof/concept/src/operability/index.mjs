// Observability and operability helpers.
//
// These helpers are intentionally library-local. They do not imply a hosted
// DeliveryProof service, process supervisor, metrics backend, or payment rail.

import { DeliveryProofConfigurationError } from '../protocol/errors.mjs';
import { clockFrom } from '../protocol/runtime.mjs';

/**
 * @typedef {{ event:string, at:number, [key:string]: unknown }} AuditEvent
 * @typedef {{ emit: (event: AuditEvent) => unknown, onError?: (error: Error, event: AuditEvent) => unknown }} AuditSink
 */

/**
 * Normalize an optional audit sink. A sink may be a function or an object with
 * emit(event). Undefined/null means no-op.
 *
 * @param {undefined|null|((event: AuditEvent) => unknown)|AuditSink} audit
 * @returns {null|AuditSink}
 */
export function normalizeAuditSink(audit) {
  if (audit === undefined || audit === null) return null;
  if (typeof audit === 'function') return { emit: audit };
  if (audit && typeof audit === 'object' && typeof audit.emit === 'function') return audit;
  throw new DeliveryProofConfigurationError('audit sink must be a function or an object with emit(event)');
}

/**
 * Emit a best-effort audit event. Audit sink failures must not affect settlement
 * decisions or receipt bytes; if an onError hook exists, it receives failures.
 *
 * @param {null|AuditSink} audit
 * @param {string} event
 * @param {Object} [fields]
 * @param {{ now?: () => number }} [opts]
 */
export function emitAudit(audit, event, fields = {}, opts = {}) {
  if (audit === null) return;
  const readNow = clockFrom(opts);
  const record = { event, at: readNow(), ...fields };
  try {
    const result = audit.emit(record);
    if (result && typeof result.then === 'function') {
      result.catch((err) => handleAuditError(audit, err, record));
    }
  } catch (err) {
    handleAuditError(audit, err, record);
  }
}

/**
 * @param {null|AuditSink} audit
 * @param {*} err
 * @param {AuditEvent} record
 */
function handleAuditError(audit, err, record) {
  if (audit && typeof audit.onError === 'function') {
    try {
      audit.onError(err instanceof Error ? err : new Error(String(err)), record);
    } catch {
      // Observability must remain best-effort.
    }
  }
}

/**
 * @param {*} logger
 * @param {*} fallback
 */
export function normalizeLogger(logger, fallback = console) {
  if (logger === undefined) return fallback;
  if (logger === null || logger === false) return null;
  if (typeof logger === 'function') return { log: logger };
  if (logger && typeof logger === 'object') return logger;
  throw new DeliveryProofConfigurationError('logger must be a function, object, null, or false');
}

/**
 * @param {*} logger
 * @param {'debug'|'info'|'warn'|'error'|'log'} level
 * @param {string} message
 * @param {Object} [fields]
 */
export function logBoundary(logger, level, message, fields = {}) {
  if (!logger) return;
  const fn = typeof logger[level] === 'function' ? logger[level] : logger.log;
  if (typeof fn !== 'function') return;
  if (fields && Object.keys(fields).length > 0) fn.call(logger, message, fields);
  else fn.call(logger, message);
}

/**
 * Validate common DeliveryProof runtime configuration without constructing a
 * hosted service. This is a helper for library users wiring an engine/rail.
 *
 * @param {Object} [config]
 * @param {{ profile?: 'default'|'production' }} [opts]
 * @returns {{ ok:boolean, errors:string[], warnings:string[] }}
 */
export function validateDeliveryProofConfig(config = {}, opts = {}) {
  const errors = [];
  const warnings = [];
  const profile = opts.profile ?? 'default';
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    return { ok: false, errors: ['config must be an object'], warnings };
  }
  if (!['default', 'production'].includes(profile)) {
    errors.push('profile must be default or production');
  }

  if (config.now !== undefined && typeof config.now !== 'function') errors.push('now must be a function when provided');
  if (config.audit !== undefined) {
    try {
      normalizeAuditSink(config.audit);
    } catch (err) {
      errors.push(err.message);
    }
  }
  if (config.logger !== undefined) {
    try {
      normalizeLogger(config.logger);
    } catch (err) {
      errors.push(err.message);
    }
  }
  if (config.verifier !== undefined && (!config.verifier || typeof config.verifier.verify !== 'function')) {
    errors.push('verifier must expose verify(contract, evidence, opts)');
  }
  if (config.rail !== undefined) {
    const rail = config.rail;
    for (const method of ['authorize', 'capture', 'refund']) {
      if (!rail || typeof rail[method] !== 'function') errors.push(`rail must expose ${method}()`);
    }
    if (rail && typeof rail.status !== 'function') warnings.push('rail.status() is recommended for post-settlement state reads');
  }
  if (config.settlementKey !== undefined) {
    if (!config.settlementKey || typeof config.settlementKey.publicKey !== 'string' || typeof config.settlementKey.privateKey !== 'string') {
      errors.push('settlementKey must include publicKey and privateKey PEM strings');
    }
  }
  if (profile === 'production') {
    validateProductionProfile(config, errors, warnings);
  }

  return { ok: errors.length === 0, errors, warnings };
}

/**
 * @param {Object} [config]
 * @param {{ profile?: 'default'|'production' }} [opts]
 * @returns {{ ok:true, errors:string[], warnings:string[] }}
 */
export function assertDeliveryProofConfig(config = {}, opts = {}) {
  const result = validateDeliveryProofConfig(config, opts);
  if (!result.ok) throw new DeliveryProofConfigurationError(`invalid DeliveryProof config: ${result.errors.join('; ')}`);
  return result;
}

/**
 * Report local library wiring health. This does not perform network checks or
 * imply that a hosted SaaS/payment deployment exists.
 *
 * @param {Object} [config]
 * @param {{ profile?: 'default'|'production' }} [opts]
 * @returns {{ ok:boolean, status:'ok'|'degraded', checkedAt:number, components:Object, errors:string[], warnings:string[] }}
 */
export function deliveryProofHealthcheck(config = {}, opts = {}) {
  const readNow = clockFrom({ now: config?.now });
  const validation = validateDeliveryProofConfig(config, opts);
  const components = {
    verifier: config?.verifier === undefined ? 'not-configured' : validation.errors.some((e) => e.startsWith('verifier ')) ? 'invalid' : 'ok',
    rail: config?.rail === undefined ? 'not-configured' : validation.errors.some((e) => e.startsWith('rail ')) ? 'invalid' : 'ok',
    settlementKey: config?.settlementKey === undefined ? 'not-configured' : validation.errors.some((e) => e.startsWith('settlementKey ')) ? 'invalid' : 'ok',
    audit: config?.audit === undefined ? 'not-configured' : validation.errors.some((e) => e.includes('audit sink')) ? 'invalid' : 'ok',
  };
  return {
    ok: validation.ok,
    status: validation.ok ? 'ok' : 'degraded',
    checkedAt: readNow(),
    components,
    errors: validation.errors,
    warnings: validation.warnings,
  };
}

function validateProductionProfile(config, errors, warnings) {
  if (config.nonceRegistry === undefined) {
    errors.push('production profile requires nonceRegistry');
  }
  if (config.audit === undefined || config.audit === null) {
    warnings.push('production profile: no audit sink configured');
  }
  if (usesTmpfsWal(config)) {
    warnings.push('production profile: tmpfs WAL paths are not durable storage');
  }
  if (config.rail !== undefined && config.railReceiptSignatureVerification !== true) {
    warnings.push('production profile: rail-no-sig-verify is not declared safe');
  }
}

function usesTmpfsWal(config) {
  for (const value of [
    config.logPath,
    config.walPath,
    config.nonceRegistryLogPath,
    config.replayStoreLogPath,
    config.nonceRegistry?.logPath,
    config.replayStore?.logPath,
  ]) {
    if (typeof value === 'string' && /^(\/tmp\/|\/var\/folders\/|\/dev\/shm\/)/.test(value)) return true;
  }
  return false;
}

/**
 * Best-effort flush+close for local resources such as the durable rail. This is
 * intentionally explicit; it does not install process signal handlers.
 *
 * @param {Array<*>|*} resources
 * @returns {Promise<{ ok:boolean, closed:number, errors:string[] }>}
 */
export async function gracefulShutdown(resources) {
  const items = Array.isArray(resources) ? resources : [resources];
  const errors = [];
  let closed = 0;
  for (const resource of items) {
    if (!resource) continue;
    try {
      if (typeof resource.flush === 'function') await resource.flush();
      if (typeof resource.close === 'function') {
        await resource.close();
        closed++;
      }
    } catch (err) {
      errors.push(err instanceof Error ? err.message : String(err));
    }
  }
  return { ok: errors.length === 0, closed, errors };
}

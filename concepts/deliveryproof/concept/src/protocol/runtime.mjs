// Small runtime helpers shared by the production-hardening path.

import { DeliveryProofConfigurationError, DeliveryProofValidationError } from './errors.mjs';

const PROTOTYPE_POLLUTION_KEYS = new Set(['__proto__', 'constructor', 'prototype']);

/**
 * @param {{ now?: () => number }|undefined} [opts]
 * @returns {() => number}
 */
export function clockFrom(opts = undefined) {
  const now = opts?.now ?? Date.now;
  if (typeof now !== 'function') {
    throw new DeliveryProofConfigurationError('now must be a function returning epoch milliseconds');
  }
  return now;
}

/**
 * @param {{ now?: () => number }|undefined} [opts]
 * @returns {number}
 */
export function checkedAt(opts = undefined) {
  return clockFrom(opts)();
}

/**
 * @returns {Record<string, unknown>}
 */
export function safeRecord() {
  return Object.create(null);
}

/**
 * Reject object shapes that are dangerous to merge into ordinary JavaScript
 * objects. JSON.parse itself does not mutate Object.prototype, but WAL records
 * and parsed deliverables are later copied into state; fail closed before that.
 *
 * @param {*} value
 * @param {string} [path]
 */
export function assertNoPrototypePollutionKeys(value, path = '$') {
  if (value === null || typeof value !== 'object') return;
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) {
      assertNoPrototypePollutionKeys(value[i], `${path}[${i}]`);
    }
    return;
  }
  for (const key of Object.keys(value)) {
    if (PROTOTYPE_POLLUTION_KEYS.has(key)) {
      throw new DeliveryProofValidationError(`${path}.${key}: prototype-pollution key is not allowed`);
    }
    assertNoPrototypePollutionKeys(value[key], `${path}.${key}`);
  }
}

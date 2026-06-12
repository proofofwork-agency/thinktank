import { keccak_256 } from '@noble/hashes/sha3.js';
import { bytesToHex, utf8ToBytes } from '@noble/hashes/utils.js';

/**
 * Lowercase hex Ethereum Keccak-256 over UTF-8 text or raw bytes.
 *
 * Node's built-in `sha3-256` implements the finalized FIPS SHA-3 padding, not
 * Ethereum Keccak padding. Keep this helper narrow so the dependency boundary is
 * easy to audit.
 *
 * @param {string|Uint8Array} input
 * @returns {string}
 */
export function keccak256(input) {
  const bytes = typeof input === 'string' ? utf8ToBytes(input) : input;
  if (!(bytes instanceof Uint8Array)) {
    throw new TypeError('keccak256: input must be a string or Uint8Array');
  }
  return bytesToHex(keccak_256(bytes));
}

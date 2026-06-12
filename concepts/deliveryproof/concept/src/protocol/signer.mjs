import { keyId } from './crypto.mjs';

export const SIGNER_INTERFACE = Object.freeze({
  name: 'deliveryproof-signer',
  trustRoot: 'caller-supplied signing authority such as an in-memory key, KMS, or HSM adapter',
  proves: 'a settlement authority can produce signatures over canonical DeliveryProof receipts',
  doesNotProve: 'key custody safety, operator authorization, or production KMS/HSM policy correctness',
  requiredMethods: Object.freeze(['sign(message)', 'keyId()']),
  implemented: false,
});

export const KEYRING_INTERFACE = Object.freeze({
  name: 'deliveryproof-keyring',
  trustRoot: 'caller-supplied public-key set for settlement authority rotation',
  proves: 'a receipt signature verifies under one of the configured settlement authority public keys',
  doesNotProve: 'that the key was authorized by business policy, not revoked, or managed safely',
  requiredMethods: Object.freeze(['keys', 'get(keyId)']),
  implemented: false,
});

/**
 * Create a tiny in-memory public-key keyring for receipt verification.
 *
 * This is not a KMS/HSM implementation. It is a small descriptor and
 * lookup helper for public PEM strings used by verifyReceipt().
 *
 * @param {string[]} pems SPKI public-key PEM strings.
 * @returns {{ keys: readonly string[], get: (id: string) => readonly string[] }}
 */
export function createInMemoryKeyring(pems = []) {
  if (!Array.isArray(pems)) {
    throw new TypeError('createInMemoryKeyring: pems must be an array');
  }
  const keys = Object.freeze([...pems].filter((pem) => typeof pem === 'string'));
  const byId = new Map();
  for (const pem of keys) {
    const id = keyId(pem);
    const bucket = byId.get(id) ?? [];
    bucket.push(pem);
    byId.set(id, bucket);
  }
  for (const [id, bucket] of byId.entries()) {
    byId.set(id, Object.freeze([...bucket]));
  }
  return Object.freeze({
    keys,
    get(id) {
      return byId.get(id) ?? Object.freeze([]);
    },
  });
}

// crypto.mjs — Ed25519 signing primitives over node:crypto.
//
// Used to (a) sign DeliveryReceipts with a settlement authority key and
// (b) sign nonce-bound delivery transcripts (Tier-A transcript verifier).
//
// PoC note: keys are PEM strings here for portability with Node's crypto APIs.
// A production build would swap this module for @noble/ed25519 + a real KMS/HSM
// without changing callers, since the surface (generate/sign/verify/keyId) is
// intentionally minimal.

import {
  generateKeyPairSync,
  sign as cryptoSign,
  verify as cryptoVerify,
  createHash,
} from 'node:crypto';

/**
 * Generate a fresh Ed25519 keypair.
 *
 * @returns {{ publicKey: string, privateKey: string }} PEM-encoded keys
 *   (publicKey = SPKI PEM, privateKey = PKCS#8 PEM).
 */
export function generateKeypair() {
  const { publicKey, privateKey } = generateKeyPairSync('ed25519');
  return {
    publicKey: publicKey.export({ type: 'spki', format: 'pem' }),
    privateKey: privateKey.export({ type: 'pkcs8', format: 'pem' }),
  };
}

/**
 * Sign a UTF-8 message with an Ed25519 private key.
 *
 * Ed25519 is a one-shot signature scheme, so the algorithm argument to
 * node:crypto's sign() must be null. node:crypto accepts the PEM string
 * directly as the key.
 *
 * @param {string} privateKeyPem PKCS#8 PEM private key
 * @param {string} message       UTF-8 message to sign
 * @returns {string} base64-encoded signature
 */
export function sign(privateKeyPem, message) {
  const sig = cryptoSign(null, Buffer.from(message, 'utf8'), privateKeyPem);
  return sig.toString('base64');
}

/**
 * Verify an Ed25519 signature over a UTF-8 message.
 *
 * Returns false (never throws) on malformed signatures or keys, so callers can
 * treat verification as a pure boolean gate.
 *
 * @param {string} publicKeyPem SPKI PEM public key
 * @param {string} message      UTF-8 message that was signed
 * @param {string} signatureB64 base64-encoded signature
 * @returns {boolean} true iff the signature is valid for (publicKey, message)
 */
export function verify(publicKeyPem, message, signatureB64) {
  try {
    return cryptoVerify(
      null,
      Buffer.from(message, 'utf8'),
      publicKeyPem,
      Buffer.from(signatureB64, 'base64'),
    );
  } catch {
    return false;
  }
}

/**
 * Short, stable identifier for a public key: the first 16 hex chars of
 * sha256(publicKeyPem). Stable for a given PEM string, collision-resistant
 * enough for human-readable references in contracts/receipts.
 *
 * @param {string} publicKeyPem SPKI PEM public key
 * @returns {string} 16-character lowercase hex key id
 */
export function keyId(publicKeyPem) {
  return createHash('sha256')
    .update(publicKeyPem, 'utf8')
    .digest('hex')
    .slice(0, 16);
}

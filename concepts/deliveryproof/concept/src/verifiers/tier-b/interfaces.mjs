// Tier-B provenance interface descriptors.
//
// These are NOT cryptographic implementations. They describe the evidence shape
// a real TEE / zkTLS / ZK verifier adapter must bind into DeliveryProof. The
// runnable Tier-B example in this directory is `signed-oracle.mjs`, which uses
// real Ed25519 signatures but still only proves "an attester said X".

export const TIER_B_INTERFACE_DESCRIPTORS = Object.freeze({
  tee: Object.freeze({
    name: 'tee-attestation',
    trustRoot: 'platform quote verifier / endorsement chain',
    proves: 'an approved enclave measurement produced or attested to the outputHash for this contract nonce',
    doesNotProve: 'that enclave code is bug-free, that the platform root is honest, or that external-world facts are true',
    requiredBindings: Object.freeze(['contractId', 'nonce', 'outputHash', 'measurement', 'quote']),
    implemented: false,
  }),
  zktls: Object.freeze({
    name: 'zktls-source-proof',
    trustRoot: 'TLS transcript proof system and named HTTPS origin',
    proves: 'a named HTTPS origin returned bytes/fields that hash to outputHash',
    doesNotProve: 'that the origin is truthful, complete, or authorized to define business truth',
    requiredBindings: Object.freeze(['contractId', 'nonce', 'outputHash', 'origin', 'transcriptProof']),
    implemented: false,
  }),
  zk: Object.freeze({
    name: 'zk-computation-proof',
    trustRoot: 'verification key and circuit semantics',
    proves: 'a committed computation satisfied the circuit constraints for public inputs including outputHash',
    doesNotProve: 'that the circuit encodes the buyer intent correctly',
    requiredBindings: Object.freeze(['contractId', 'nonce', 'outputHash', 'verificationKeyId', 'proof']),
    implemented: false,
  }),
});

/**
 * @param {'tee'|'zktls'|'zk'} name
 */
export function getTierBInterface(name) {
  const descriptor = TIER_B_INTERFACE_DESCRIPTORS[name];
  if (!descriptor) {
    throw new Error(`unknown Tier-B interface "${name}"`);
  }
  return descriptor;
}

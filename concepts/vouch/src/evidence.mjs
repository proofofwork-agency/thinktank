// Evidence adapters: how a settlement outcome is *proved*, never voted on.
//
// This is the line between vouch and every "decentralised insurance" protocol
// that resolves claims by token-holder governance. An adapter is a pure
// function from evidence to {outcome, reason}. It must be deterministic and
// re-runnable by anyone holding the same bytes, so a disputed settlement is
// resolved by re-execution rather than by whoever controls the most votes.
//
// vouch core stays dependency-free: the DeliveryProof module is *injected*
// rather than imported, so this package runs offline and DeliveryProof stays
// an optional composition rather than a hard coupling.

export const OUTCOME = Object.freeze({
  DELIVERED: 'delivered',
  FAILED: 'failed',
});

/**
 * Wrap a raw predicate into a checked adapter.
 *
 * The wrapper enforces the adapter contract itself: an adapter that throws, or
 * returns something outside the outcome enum, is treated as FAILED-unproven and
 * rejected rather than silently defaulting to a payout in either direction.
 */
export function createAdapter(kind, decide) {
  if (typeof kind !== 'string' || kind.length === 0) {
    throw new TypeError('createAdapter: kind must be a non-empty string');
  }
  if (typeof decide !== 'function') {
    throw new TypeError('createAdapter: decide must be a function');
  }

  return Object.freeze({
    kind,
    decide(commitment, evidence) {
      const result = decide(commitment, evidence);
      if (!result || typeof result !== 'object') {
        throw new TypeError(`adapter ${kind}: decide must return an object`);
      }
      if (result.outcome !== OUTCOME.DELIVERED && result.outcome !== OUTCOME.FAILED) {
        throw new TypeError(
          `adapter ${kind}: outcome must be '${OUTCOME.DELIVERED}' or '${OUTCOME.FAILED}', got ${String(result.outcome)}`,
        );
      }
      if (typeof result.reason !== 'string' || result.reason.length === 0) {
        throw new TypeError(`adapter ${kind}: reason must be a non-empty string`);
      }
      return Object.freeze({ outcome: result.outcome, reason: result.reason });
    },
  });
}

/**
 * Adapter over a DeliveryProof signed receipt.
 *
 * DeliveryProof's normative gating invariant is that no hold is ever captured
 * while `verdict.ok === false`; a failing verdict can only lead to a refund.
 * That is precisely the property vouch needs, and it is why the failure
 * trigger is not forgeable by a beneficiary who simply wants to collect: the
 * verdict comes from a deterministic verifier over the delivered artifact, and
 * anyone can re-run it on the same bytes.
 *
 * @param {object} deliveryproof - the DeliveryProof module (or any object
 *   exposing a compatible `verifyReceipt`), injected by the caller.
 */
export function createDeliveryProofAdapter(deliveryproof) {
  if (!deliveryproof || typeof deliveryproof.verifyReceipt !== 'function') {
    throw new TypeError(
      'createDeliveryProofAdapter: expected a module exposing verifyReceipt(receipt, key)',
    );
  }

  return createAdapter('deliveryproof', (commitment, evidence) => {
    const { receipt, settlementPublicKey } = evidence ?? {};
    if (!receipt || typeof receipt !== 'object') {
      throw new TypeError('deliveryproof adapter: evidence.receipt is required');
    }

    // An unsigned or wrongly-signed receipt is not evidence of anything.
    const verified = deliveryproof.verifyReceipt(receipt, settlementPublicKey);
    const signatureOk = typeof verified === 'boolean' ? verified : verified?.ok === true;
    if (!signatureOk) {
      throw new Error('deliveryproof adapter: receipt signature did not verify');
    }

    // Bind the receipt to *this* commitment. Without this a beneficiary could
    // present a genuine failure receipt from some unrelated job.
    const expected = commitment.verifier?.contractHash;
    if (expected !== undefined) {
      const actual = receipt.contractHash ?? receipt.contract?.hash;
      if (actual !== expected) {
        throw new Error(
          `deliveryproof adapter: receipt contractHash ${String(actual)} does not match commitment ${String(expected)}`,
        );
      }
    }

    if (receipt.decision === 'release') {
      return { outcome: OUTCOME.DELIVERED, reason: `deliveryproof:release:${receipt.verdict?.reason ?? 'ok'}` };
    }
    if (receipt.decision === 'refund') {
      return { outcome: OUTCOME.FAILED, reason: `deliveryproof:refund:${receipt.verdict?.reason ?? 'failed'}` };
    }
    throw new TypeError(`deliveryproof adapter: unknown decision ${String(receipt.decision)}`);
  });
}

/**
 * A self-contained adapter for offline simulation and tests: the evidence is a
 * boolean `delivered` flag plus a reason. Useful for exercising the market and
 * the economics without standing up a full DeliveryProof settlement.
 */
export const attestationAdapter = createAdapter('attestation', (_commitment, evidence) => {
  if (!evidence || typeof evidence.delivered !== 'boolean') {
    throw new TypeError('attestation adapter: evidence.delivered must be a boolean');
  }
  return {
    outcome: evidence.delivered ? OUTCOME.DELIVERED : OUTCOME.FAILED,
    reason: evidence.reason ?? (evidence.delivered ? 'attested-delivered' : 'attested-failed'),
  };
});

/** Registry so a commitment's `verifier.kind` selects its adapter by name. */
export function createAdapterRegistry(adapters = []) {
  const byKind = new Map();
  for (const adapter of adapters) byKind.set(adapter.kind, adapter);

  return Object.freeze({
    register(adapter) {
      byKind.set(adapter.kind, adapter);
      return this;
    },
    resolve(kind) {
      const adapter = byKind.get(kind);
      if (!adapter) throw new Error(`no evidence adapter registered for kind '${kind}'`);
      return adapter;
    },
    kinds() {
      return [...byKind.keys()];
    },
  });
}

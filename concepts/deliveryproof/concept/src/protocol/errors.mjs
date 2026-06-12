// Shared runtime error taxonomy for public DeliveryProof APIs.
//
// Verifiers should usually return a failing Verdict for buyer/seller data
// mismatches. These errors are for invalid API/configuration/runtime state around
// the protocol library itself.

export class DeliveryProofError extends Error {
  /**
   * @param {string} message
   * @param {{ code?: string, cause?: unknown }} [opts]
   */
  constructor(message, opts = {}) {
    super(message, opts.cause === undefined ? undefined : { cause: opts.cause });
    this.name = new.target.name;
    this.code = opts.code ?? 'DELIVERYPROOF_ERROR';
  }
}

export class DeliveryProofValidationError extends DeliveryProofError {
  /**
   * @param {string} message
   * @param {{ cause?: unknown }} [opts]
   */
  constructor(message, opts = {}) {
    super(message, { code: 'DELIVERYPROOF_VALIDATION', ...opts });
  }
}

export class DeliveryProofConfigurationError extends DeliveryProofError {
  /**
   * @param {string} message
   * @param {{ cause?: unknown }} [opts]
   */
  constructor(message, opts = {}) {
    super(message, { code: 'DELIVERYPROOF_CONFIGURATION', ...opts });
  }
}

export class DeliveryProofRailError extends DeliveryProofError {
  /**
   * @param {string} message
   * @param {{ cause?: unknown }} [opts]
   */
  constructor(message, opts = {}) {
    super(message, { code: 'DELIVERYPROOF_RAIL', ...opts });
  }
}

// Money is always an integer count of minor units (think: micro-dollars).
//
// Floats are banned throughout the settlement path. An indemnity cap that
// rounds the wrong way is the difference between "collusion is unprofitable"
// and "collusion nets a fraction of a unit per job, forever".

/** Assert a value is a non-negative integer amount of minor units. */
export function assertAmount(value, label) {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new TypeError(
      `${label} must be a non-negative safe integer of minor units, received ${String(value)}`,
    );
  }
  return value;
}

/** Assert a strictly positive integer amount. */
export function assertPositiveAmount(value, label) {
  assertAmount(value, label);
  if (value === 0) throw new TypeError(`${label} must be greater than zero`);
  return value;
}

/** Addition that refuses to silently leave the safe-integer range. */
export function addAmount(a, b) {
  const sum = a + b;
  if (!Number.isSafeInteger(sum)) throw new RangeError('amount overflow');
  return sum;
}

/** Subtraction that refuses to go negative. */
export function subAmount(a, b) {
  const diff = a - b;
  if (diff < 0) throw new RangeError('amount underflow');
  return diff;
}

/**
 * Multiply an amount by a rational numerator/denominator, rounding UP.
 *
 * Premiums round up (against the underwriter's favour, toward the buyer) so
 * that a rounding residue can never be farmed by writing many tiny policies.
 */
export function mulDivCeil(amount, numerator, denominator) {
  assertAmount(amount, 'amount');
  if (!Number.isSafeInteger(numerator) || numerator < 0) {
    throw new TypeError('numerator must be a non-negative safe integer');
  }
  if (!Number.isSafeInteger(denominator) || denominator <= 0) {
    throw new TypeError('denominator must be a positive safe integer');
  }
  // The intermediate product overflows a double long before either operand
  // does — 5,000 USDC in micro-units times a basis-point factor is already
  // past MAX_SAFE_INTEGER. BigInt keeps the multiply-divide exact; the public
  // surface stays Number.
  return fromBigInt(ceilDiv(BigInt(amount) * BigInt(numerator), BigInt(denominator)));
}

/** Exact ceiling division on non-negative BigInts. */
function ceilDiv(numerator, denominator) {
  return (numerator + denominator - 1n) / denominator;
}

function fromBigInt(value) {
  if (value > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new RangeError('amount overflow: result exceeds MAX_SAFE_INTEGER');
  }
  return Number(value);
}

/** Convert a probability in [0,1] to an integer premium, rounding up. */
export function priceFromProbability(exposure, probability, loadBasisPoints = 0) {
  assertAmount(exposure, 'exposure');
  if (typeof probability !== 'number' || !Number.isFinite(probability) || probability < 0 || probability > 1) {
    throw new TypeError(`probability must be within [0,1], received ${String(probability)}`);
  }
  if (!Number.isSafeInteger(loadBasisPoints) || loadBasisPoints < 0) {
    throw new TypeError('loadBasisPoints must be a non-negative safe integer');
  }
  // Work in basis points of probability to stay in integer arithmetic, and do
  // the widening multiply in BigInt so a realistic exposure cannot overflow.
  const probBps = Math.ceil(probability * 10_000);
  const loaded = BigInt(probBps) * BigInt(10_000 + loadBasisPoints);
  return fromBigInt(ceilDiv(BigInt(exposure) * loaded, 100_000_000n));
}

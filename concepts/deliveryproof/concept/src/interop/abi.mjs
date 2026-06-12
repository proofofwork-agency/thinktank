const HEX_RE = /^[0-9a-fA-F]*$/;
const textEncoder = new TextEncoder();

/**
 * Minimal Ethereum ABI argument encoding for the projection shapes this package
 * emits. It intentionally does not produce calldata selectors or perform calls.
 *
 * Supported types: bytes32, uint8, string.
 *
 * @param {string[]} types
 * @param {*[]} values
 * @returns {string} 0x-prefixed ABI-encoded arguments.
 */
export function encodeAbiParameters(types, values) {
  if (!Array.isArray(types) || !Array.isArray(values) || types.length !== values.length) {
    throw new TypeError('encodeAbiParameters: types and values must be same-length arrays');
  }
  const head = [];
  const tail = [];
  let dynamicOffset = 32 * types.length;
  for (let i = 0; i < types.length; i++) {
    const type = types[i];
    const value = values[i];
    if (type === 'string') {
      const encoded = encodeString(value);
      head.push(encodeUint(dynamicOffset));
      tail.push(encoded);
      dynamicOffset += encoded.length / 2;
    } else {
      head.push(encodeStatic(type, value));
    }
  }
  return `0x${head.join('')}${tail.join('')}`;
}

function encodeStatic(type, value) {
  if (type === 'bytes32') return encodeBytes32(value);
  if (type === 'uint8') return encodeUint8(value);
  throw new TypeError(`encodeAbiParameters: unsupported type ${JSON.stringify(type)}`);
}

function encodeBytes32(value) {
  if (typeof value !== 'string') throw new TypeError('bytes32 ABI value must be a hex string');
  const hex = strip0x(value);
  if (hex.length !== 64 || !HEX_RE.test(hex)) {
    throw new TypeError('bytes32 ABI value must be 32 bytes');
  }
  return hex.toLowerCase();
}

function encodeUint8(value) {
  if (!Number.isSafeInteger(value) || value < 0 || value > 255) {
    throw new TypeError('uint8 ABI value must be an integer in [0,255]');
  }
  return encodeUint(value);
}

function encodeUint(value) {
  const bigint = BigInt(value);
  return bigint.toString(16).padStart(64, '0');
}

function encodeString(value) {
  if (typeof value !== 'string') throw new TypeError('string ABI value must be a string');
  const bytes = textEncoder.encode(value);
  return `${encodeUint(bytes.length)}${padRight(bytesToHex(bytes))}`;
}

function padRight(hex) {
  const remainder = hex.length % 64;
  return remainder === 0 ? hex : hex.padEnd(hex.length + 64 - remainder, '0');
}

function bytesToHex(bytes) {
  let hex = '';
  for (const byte of bytes) hex += byte.toString(16).padStart(2, '0');
  return hex;
}

function strip0x(hex) {
  return hex.startsWith('0x') || hex.startsWith('0X') ? hex.slice(2) : hex;
}

// schema.mjs — runtime validation for DeliveryProof wire records.
//
// This is intentionally small: it validates the core protocol envelope without
// pretending to be a complete JSON Schema implementation. Verifier-specific
// predicate params remain verifier-owned extension data.

import { PROTOCOL_VERSION, canonicalize } from './canonical.mjs';

export function validationOk() {
  return { ok: true, errors: [] };
}

export function validationError(errors) {
  return { ok: false, errors: Array.isArray(errors) ? errors : [String(errors)] };
}

export function validateContract(contract) {
  const e = [];
  if (!isObj(contract)) return validationError('contract must be an object');
  reqString(contract, 'protocolVersion', e);
  if (contract.protocolVersion !== PROTOCOL_VERSION) e.push(`protocolVersion must be ${PROTOCOL_VERSION}`);
  for (const f of ['id', 'buyer', 'seller', 'intent', 'deliverableType', 'refundRule', 'railId', 'nonce']) reqString(contract, f, e);
  if (!isObj(contract.predicate)) e.push('predicate must be an object');
  else {
    reqString(contract.predicate, 'kind', e, 'predicate.kind');
    if (!isObj(contract.predicate.params)) e.push('predicate.params must be an object');
  }
  if (!isObj(contract.price)) e.push('price must be an object');
  else {
    if (typeof contract.price.amount !== 'number' || !Number.isFinite(contract.price.amount) || contract.price.amount <= 0) e.push('price.amount must be a positive finite number');
    reqString(contract.price, 'currency', e, 'price.currency');
  }
  if (!isObj(contract.sla)) e.push('sla must be an object');
  else if (typeof contract.sla.deadlineMs !== 'number' || !Number.isFinite(contract.sla.deadlineMs)) e.push('sla.deadlineMs must be a finite number');
  if (typeof contract.createdAt !== 'number' || !Number.isFinite(contract.createdAt)) e.push('createdAt must be a finite number');
  return e.length ? validationError(e) : validationOk();
}

export function validateEvidence(evidence) {
  const e = [];
  if (!isObj(evidence)) return validationError('evidence must be an object');
  reqString(evidence, 'protocolVersion', e);
  if (evidence.protocolVersion !== PROTOCOL_VERSION) e.push(`protocolVersion must be ${PROTOCOL_VERSION}`);
  reqString(evidence, 'contractId', e);
  reqString(evidence, 'nonce', e);
  reqString(evidence, 'outputHash', e);
  if (!Object.prototype.hasOwnProperty.call(evidence, 'output')) e.push('output is required');
  if (evidence.logs !== undefined && !Array.isArray(evidence.logs)) e.push('logs must be an array when present');
  if (evidence.attestations !== undefined && !Array.isArray(evidence.attestations)) e.push('attestations must be an array when present');
  if (typeof evidence.producedAt !== 'number' || !Number.isFinite(evidence.producedAt)) e.push('producedAt must be a finite number');
  try { canonicalize(evidence); } catch (err) { e.push(`evidence is not canonical JSON: ${err.message}`); }
  return e.length ? validationError(e) : validationOk();
}

export function validateVerdict(verdict) {
  const e = [];
  if (!isObj(verdict)) return validationError('verdict must be an object');
  if (typeof verdict.ok !== 'boolean') e.push('verdict.ok must be boolean');
  if (!['A', 'B', 'C'].includes(verdict.tier)) e.push('verdict.tier must be A, B, or C');
  reqString(verdict, 'verifier', e, 'verdict.verifier');
  reqString(verdict, 'reason', e, 'verdict.reason');
  if (typeof verdict.checkedAt !== 'number' || !Number.isFinite(verdict.checkedAt)) e.push('verdict.checkedAt must be a finite number');
  try { canonicalize(verdict); } catch (err) { e.push(`verdict is not canonical JSON: ${err.message}`); }
  return e.length ? validationError(e) : validationOk();
}

export function validateReceipt(receipt, { requireSignature = true } = {}) {
  const e = [];
  if (!isObj(receipt)) return validationError('receipt must be an object');
  reqString(receipt, 'protocolVersion', e);
  if (receipt.protocolVersion !== PROTOCOL_VERSION) e.push(`protocolVersion must be ${PROTOCOL_VERSION}`);
  for (const f of ['contractId', 'contractHash', 'railId', 'holdId', 'currency', 'evidenceHash', 'decision', 'signerKeyId']) reqString(receipt, f, e);
  if (typeof receipt.amount !== 'number' || !Number.isFinite(receipt.amount) || receipt.amount <= 0) e.push('amount must be a positive finite number');
  if (!['release', 'refund'].includes(receipt.decision)) e.push('decision must be release or refund');
  const vv = validateVerdict(receipt.verdict);
  if (!vv.ok) e.push(...vv.errors.map((x) => `verdict.${x}`));
  if (!('routeDecision' in receipt)) e.push('routeDecision must be present (object or null)');
  if (!Array.isArray(receipt.lifecycle)) e.push('lifecycle must be present as an array');
  if (!('nonceRegistryKey' in receipt)) e.push('nonceRegistryKey must be present (string or null)');
  else if (receipt.nonceRegistryKey !== null && typeof receipt.nonceRegistryKey !== 'string') e.push('nonceRegistryKey must be string or null');
  if (typeof receipt.issuedAt !== 'number' || !Number.isFinite(receipt.issuedAt)) e.push('issuedAt must be a finite number');
  if (requireSignature) reqString(receipt, 'signature', e);
  try { canonicalize(receipt); } catch (err) { e.push(`receipt is not canonical JSON: ${err.message}`); }
  return e.length ? validationError(e) : validationOk();
}

export function assertContract(contract) {
  assertValid(validateContract(contract), 'DeliveryContract');
}

export function assertEvidence(evidence) {
  assertValid(validateEvidence(evidence), 'DeliveryEvidence');
}

export function assertVerdict(verdict) {
  assertValid(validateVerdict(verdict), 'Verdict');
}

export function assertReceipt(receipt, opts) {
  assertValid(validateReceipt(receipt, opts), 'DeliveryReceipt');
}

function assertValid(result, label) {
  if (!result.ok) throw new TypeError(`${label} validation failed: ${result.errors.join('; ')}`);
}

function isObj(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function reqString(obj, field, errors, label = field) {
  if (typeof obj[field] !== 'string' || obj[field].length === 0) errors.push(`${label} must be a non-empty string`);
}

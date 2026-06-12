// src/interop/index.mjs
// Interop export adapters: project a DeliveryProof DeliveryReceipt onto the
// payload SHAPES of emerging agent-commerce standards whose evaluator/validator
// method is deliberately undefined. DeliveryProof supplies the deep, objective
// verdict those slots leave open. Thin, pure projection helpers — no chain logic.
export { toErc8004ValidationPayload, encodeErc8004ValidationAbi } from './erc8004.mjs';
export { toErc8183EvaluatorResult, encodeErc8183EvaluatorAbi } from './erc8183.mjs';

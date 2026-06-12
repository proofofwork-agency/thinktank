# Adapters

Companion rail adapters that map DeliveryProof settlement onto a real settlement
venue. Each adapter is its own workspace package, pins its own heavy dependencies
(chain clients, KMS, databases), and depends on the core `deliveryproof` package
(in [`../concept`](../concept)) through the workspace.

Every adapter must pass the core's exported `runRailConformance()` suite and keep
the core's money-safety invariants (verdict-consistency gate, 7-field receipt
binding, idempotent terminalization). It must also state plainly which external
system owns final settlement — the adapter is the DeliveryProof evaluator, not a
custodian.

Priority order and rationale: [`../concept/docs/ADAPTER-RFC.md`](../concept/docs/ADAPTER-RFC.md).

| Adapter | Status |
|---------|--------|
| [`erc8183-base/`](./erc8183-base) — `@deliveryproof/rail-erc8183-base` | first reference adapter (testnet/local only) |

Live/mainnet operation (keys, gas, chain choice, custody, finality) is an
operator/human responsibility — see
[`../concept/docs/ESCALATIONS.md`](../concept/docs/ESCALATIONS.md).

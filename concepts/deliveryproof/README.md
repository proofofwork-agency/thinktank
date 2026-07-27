# DeliveryProof (monorepo)

Verified-delivery-gated settlement for AI-agent commerce — the reference library
plus the real rail adapters that drive it on actual settlement venues.

This repository is an npm-workspaces monorepo:

| Path | Package | What it is |
|------|---------|------------|
| [`concept/`](./concept) | `deliveryproof` | The core reference library: protocol objects, JCS canonicalization, deep verifiers, the no-silent-downgrade router, signed `DeliveryReceipt`s, reference rails, conformance suites, and ERC-8004/8183 projection helpers. Dependency-light (one pinned runtime dep), rail-neutral, non-custodial, **not** a deployed service. |
| [`adapters/`](./adapters) | `@deliveryproof/rail-*` | Companion rail adapters that map DeliveryProof settlement onto a real venue. Each pins its own heavy dependencies (chain clients, KMS, DB) so the core stays small. |
| [`example/`](./example) | `deliveryproof-demo` | Standalone React/Vite demo app that explains the delivery-verification flow. It is intentionally outside the npm workspaces so demo UI dependencies do not become production library dependencies. |

The split is deliberate: `concept/` proves the *idea* is buildable, small, and honest;
the adapters prove it can drive *real* settlement without pulling chain/wallet/RPC code
into the core. The strategy and priority order are in
[`concept/docs/ADAPTER-RFC.md`](./concept/docs/ADAPTER-RFC.md).

## Layout

```text
deliveryproof/                 (monorepo root — npm workspaces)
├── concept/                   the deliveryproof reference library (start here)
│   ├── src/ test/ examples/ docs/
│   └── README.md SPEC.md WHITEPAPER (docs/) ...
├── adapters/
│   └── erc8183-base/          @deliveryproof/rail-erc8183-base (first reference adapter)
└── example/                   standalone React/Vite demo app
```

## Quickstart

Requires Node v22+.

```bash
npm install              # installs all workspaces and links them
npm test                 # runs every workspace's tests
npm run verify:deps      # asserts the core (concept/) still ships exactly one runtime dep
```

To work on a single package, `cd` into it (`cd concept` or
`cd adapters/erc8183-base`) and use its own `npm test` / `npm run check`.

To run the demo app:

```bash
cd example
npm install
npm run dev
```

## What this is and is not

The core is a reference implementation, not a deployed money-moving product: it does
not custody funds, hold private keys, submit transactions, or call a payment provider.
Adapters add the real settlement boundary, but live/mainnet operation (keys, gas, chain
choice, custody, finality) remains an operator/human responsibility — see
[`concept/docs/ESCALATIONS.md`](./concept/docs/ESCALATIONS.md).

## License

Apache-2.0 — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).

You may use, modify, redistribute, and build commercial or closed-source products
on this software. In exchange, Apache-2.0 §4(d) requires that you keep the
attribution in [NOTICE](./NOTICE) — the ProofOfWork Agency copyright line — visible
somewhere customary in your product (source header, docs, or a third-party
notices screen). No permission request, no fee, no obligation to open your own
changes. Just keep the credit.

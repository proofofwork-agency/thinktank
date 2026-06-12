# DeliveryProof Demo App

Small React demo that explains DeliveryProof as a rail-neutral delivery-verification layer.

It intentionally lives outside the `deliveryproof` npm workspaces so the production
library keeps its dependency-light, zero-demo-install invariant.

## Run

```bash
npm install
npm run dev
```

Open the local URL printed by Vite.

## What It Shows

- Buyer payment is held by a rail such as Stripe or x402.
- Seller submits work.
- DeliveryProof checks objective delivery rules.
- A signed verdict tells the rail to release or refund.
- Info bulbs explain rails, proofs, Merkle inclusion, signed receipts, and scope limits.

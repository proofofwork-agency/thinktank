# COG Denomination Extension 0.1

Status: Reference extension

Payment rails continue to carry their native settlement asset (for example,
USDC). This extension changes the obligation's denomination, not the wallet,
chain, facilitator, or payment protocol.

The `denomination` object MUST contain `unit`, `basket`, `spec_sha256`,
`quantity`, and a `resolved` object. `resolved` MUST contain `usd_per_cog`,
`rule`, `publisher`, `fix_window_end`, and `invoice_sha256`.

For x402 the object is placed at `accepts[].extra.denomination`. For AP2 it is
placed at `mandate.denomination`. Implementations MUST preserve all unrelated
rail fields.

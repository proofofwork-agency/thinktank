# COG-Denominated Pricing Rider

Template v0.1 — not legal advice

Between **$provider** (“Provider”) and **$client** (“Client”).

## 1. Definitions

“COG-1 Fix” means an eligible published price in USD of the COG-1 Reference
Workload. “Settlement Fix” means the arithmetic median selected under
COG-SETTLE-1 for the seven UTC calendar days ending on and including the end of
the service period. It is not selected from the invoice date.

## 2. Price

For each $period, Client shall pay:

1. a fixed component of USD $fixed_usd_per_period; and
2. an indexed component of $cogs_per_period cogs, resolved to USD at the
   Settlement Fix.

Indicative total at the displayed fix of USD $fix_usd per cog:
USD $estimated_total_usd.

## 3. Term and symmetry

The term is $term. The cog quantity does not change during the term. The USD
value moves with the Settlement Fix in both directions.

## 4. Unavailability and versioning

The parties adopt COG-SETTLE-1’s labeled unavailability ladder. An external
anchor is provisional, requires acknowledgement, and is subject to true-up.
Basket retirement uses the contract’s chain-linking rule.

## 5. Audit

Either party may recompute an invoice from the signed archive and compare the
canonical invoice identifier. The payer need not possess signing key material.

Fix source shown when this template was produced: $fix_source.
Qualification: $qualification. Receipt count: $receipts.
$basis_warning

# COG-1 Unit Specification

Status: Draft 1

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.

## 1. Unit

One cog is the obligation-denomination unit for one COG-1 Reference Workload:
1,000,000 blended tokens, consisting of 800,000 input tokens and 200,000 output
tokens, delivered at the frozen COG-1 qualifying capability tier.

The unit is not a token, currency, security, or payment rail. A contract states
its quantity in cogs and resolves that quantity into a settlement currency.

## 2. Fix evidence tiers

Evidence tiers, strongest first, are `receipted-depth`, `venue-quote`,
`venue-quote-live`, `external-anchor`, and `bundled-snapshot`.

A COG-1 Settlement Fix MUST satisfy the obligation's `min_tier`.
`external-anchor` and `bundled-snapshot` MUST NOT be represented as a normal
Settlement Fix.

## 3. Blend

For separate prices `P_in` and `P_out`, the COG-1 price is:

`0.8 * P_in + 0.2 * P_out`

An upstream price using a different input/output mix MUST disclose the mismatch.
If the component prices are unavailable, normalization MUST set `exact:false`
and publish an uncertainty interval.

## 4. Versioning

Basket changes create a new specification version. A standing obligation MUST
name the specification URI and SHA-256 digest it uses. Retirement SHOULD use a
chain link computed over at least 180 days of parallel publication.

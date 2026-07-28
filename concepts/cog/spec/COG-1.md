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

Evidence tiers, strongest first, are `receipted-depth`, `receipted-lite`,
`venue-quote`, `venue-quote-live`, `external-anchor`, and `bundled-snapshot`.

`receipted-lite` proves that an execution occurred but does not satisfy the
`K`/`N` depth eligibility floor. It MUST NOT be represented as
`receipted-depth`.

A COG-1 Settlement Fix MUST satisfy the obligation's `min_tier`.
`external-anchor` and `bundled-snapshot` MUST NOT be represented as a normal
Settlement Fix.

## 3. Blend

For separate prices `P_in` and `P_out`, the COG-1 price is:

`0.8 * P_in + 0.2 * P_out`

An upstream price using a different input/output mix MUST disclose the mismatch.
If the component prices are unavailable, normalization MUST set `exact:false`
and publish an uncertainty interval.

## 4. Fix rule and depth eligibility

A `receipted-depth` COG-1 price fix MUST be the median executable price across
qualifying sized purchases. A publication window is eligible only after at
least `K=5` independent purchases of at least `N=10,000,000` blended tokens
each. After a purchase clears that eligibility floor, it contributes one price
observation regardless of its token count.

Publishers MUST NOT describe this rule as volume-weighted or market-volume
weighted. The purchase sizes are selected by the protocol rather than observed
from market activity. The eligibility floor, not weighting, is the mechanism
that prevents a loss-leader sip from setting the fix: the protection is
admission, not weighting.

## 5. Versioning

Basket changes create a new specification version. A standing obligation MUST
name the specification URI and SHA-256 digest it uses. Retirement SHOULD use a
chain link computed over at least 180 days of parallel publication.

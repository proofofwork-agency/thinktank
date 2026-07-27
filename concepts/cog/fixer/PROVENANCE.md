# Price provenance: what the published fix actually measures

A price index is only as good as its answer to "whose price, bought where, on what terms."
This file records those answers for COG-1, including the ones that are unflattering.

## The venue fee, stated precisely

The fixer's quote mode and its receipt buys both run through OpenRouter. OpenRouter charges a
**5.5% fee on credit purchases** (minimum $0.80).

It is tempting — and wrong — to say "prices sourced through OpenRouter are 5.5% too high."
The precise statement:

- OpenRouter's **posted per-token rates** are provider rates denominated in OpenRouter credits,
  roughly 1:1 with USD. The posted rate is therefore approximately venue-neutral.
- The 5.5% is a **credit-purchase fee**: acquiring 1 credit costs about $1.055. So the
  **effective USD cost of transacting through this venue** is posted × 1.055.
- A receipt's billed cost is charged in credits, so a receipted cost is a **venue price**, not
  an underlying provider price.

### The design decision, and why

**COG-1 measures the underlying provider price, not the price of buying cognition through one
venue.** So the series stays at posted rates, and `venue_credit_fee_pct` is published as
disclosure alongside it rather than baked into the number.

The alternative — restating the series venue-adjusted — was considered and rejected. It would
move the last official point from $0.2517 to $0.2386, which changes every headline figure in
the repository ($44,591, $103,214, $195,409, $136,786), the README, WHITEPAPER §1 and §4, the
demo chart, and two tests. That is a large, cascading change in exchange for measuring
something the unit does not claim to measure.

**Disclose, don't restate.** If a future version of COG-1 decides the venue price is the right
measurement, that is a basket version change (COG-2) with an overlap window and a linking
factor — not a silent restatement of history. See WHITEPAPER.md §5.

### What this means for a contract

A buyer settling a cog-denominated invoice is not buying through our venue and does not pay our
venue's fee. The fix is a reference rate for the underlying cognition. A party who *does*
transact through a venue pays that venue's costs, exactly as a party buying oil pays freight
that Brent does not include.

## Where each kind of number comes from

| Kind | Source | Venue-neutral? | Settleable? |
|---|---|---|---|
| Pre-2025 series points | Provider launch/list announcements | yes | no — historical backtest only |
| 2026 series points | OpenRouter live feed, dated | posted rate: yes; effective cost: no | no — labeled `live-quote` |
| Quote-mode fix | OpenRouter posted prices | posted rate: yes | provisional, disclosed |
| Receipted fix | Actual buys, observed billed cost | **no** — venue price | yes |
| External anchor | Epoch AI, CC BY 4.0 | their methodology, their blend | **never** |

The asymmetry in the last two rows is deliberate. A receipted number is settleable *because*
it was transacted, even though transacting means paying a venue. An anchor number is not
settleable *however* well-sourced, because nobody bought anything.

## Known impurities, listed rather than hidden

1. **The DeepSeek V4 Flash point is a promotional venue rate.** $0.0983/$0.1966 is roughly 30%
   below DeepSeek's own published $0.14/$0.28. It is marked `provisional` and excluded from the
   official fix. A promotional reseller rate setting the index is precisely the loss-leader
   failure mode WHITEPAPER §6 describes, so it must survive a full window at depth before it
   can set a fix.

2. **The DeepSeek-V3 December-2024 point carries a post-promotional tariff.** $0.27/$1.10 became
   the standard rate around 2025-02-08; the launch rate was roughly $0.14/$0.28. The point is
   dated Dec-2024 but priced Feb-2025, which *understates* deflation across that window. Left
   as-is because it is the conservative direction, and labeled in `data.json`.

3. **Open-weight model prices are reseller-dependent.** For Llama and Qwen, "the market price"
   shifts as small providers enter and exit, independent of the model owner doing anything.
   A model ID is not a price; an endpoint is.

4. **Posted prices are not pinned to a backend.** One OpenRouter model ID can route to several
   backends at different quantizations and prices. Until endpoint pinning ships, a quote-mode
   fix is a floor across backends, not the price of any specific served artifact. Expect the
   published fix to *rise* when pinning lands — the un-pinned number was cheaper because it was
   measuring something nobody can actually buy on demand.

5. **`upstream_inference_cost` requires BYOK.** Without it, a receipt observes the venue price
   and not the provider's underlying cost. Receipts publish
   `underlying_cost_observable: false` rather than implying otherwise.

## The rule this file exists to enforce

Every number the fixer publishes carries the basis it earned, and no more. A posted price is
not called receipted. A venue price is not called a provider price. A promotional rate is not
called a market rate. An anchor is never called a settlement.

When those distinctions are inconvenient, they are the ones that matter.

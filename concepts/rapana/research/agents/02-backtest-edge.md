# 02 — Backtest Edge-Fidelity Audit

**Scope:** `rapana/backtest/` (engine, validation, metrics, carry, funding_spike, cross_sectional) + `rapana/fleet/replay.py`, `rapana/fleet/data_provider.py`, cross-referenced with `DEEP_DIVE_REVIEW.md`.
**Question:** Would the backtest engine *reveal* a non-standard edge if one existed — and what would mask it?

---

## TL;DR — which edges are UN-TESTABLE today

The core `BacktestEngine` is **spot, long-only, taker-only, close-price, single-symbol, bar-driven, infinite-liquidity**. Four non-standard edge families are **structurally un-representable** in it today:

1. **Maker / passive liquidity edges** — every fill pays taker fee + 5bps slip; no maker rebate, no queue, no non-fill (`engine.py:31,100`).
2. **Funding / perp carry in the unified engine** — `BacktestEngine` never accrues funding and cannot go short (`engine.py:173` bearish = flatten). Carry exists only as a *separate* simulator with basis_drag=0 and no leverage/liquidation (`carry.py:52`).
3. **Event-time entries / survival** (listings, delistings, liquidations, funding-settlement triggers) — fixed `for i in range(1,len+1)` bar loop, close-only; no event hook, no per-bar universe membership (`engine.py:81`).
4. **Short / long-short / market-neutral via real legs** — `_target_value` clamps to `[0, max_weight]`; `Signal.direction` has no short-with-size (`engine.py:170`, `signals.py:29`).

Plus two **representable-but-mispriced** edges that would be *hidden* not absent: order-book/depth strategies (no L2 data, no impact) and basis/perp-spot arb (basis is a fixed bps, not measured).

---

## (a) Backtest Fidelity Table

| Dimension | Current model | Location | Verdict |
|---|---|---|---|
| **Fill price** | Bar-`i` close, symmetric slip ±0.05% | `engine.py:86,99` | Infinite-liquidity assumption; no intrabar (OHLC) path, no auction. |
| **Fill type** | Taker only (every delta filled immediately) | `engine.py:100` | No maker/limit, no queue, no non-fill. |
| **Fee model** | Flat 0.1% taker (`BacktestConfig.fee_pct`); 2bp/leg in carry & funding_spike | `engine.py:31`, `carry.py:50`, `funding_spike.py:62` | No maker rebate (MEXC maker = 0%), no tier/VIP schedule, no funding cost. |
| **Slippage** | Fixed symmetric 5bps (engine), 2bps (carry/spike) | `engine.py:32,99`, `carry.py:51`, `funding_spike.py:63` | Size-/vol-/spread-independent; no market impact, no bid-ask model. |
| **Partial fills** | None — entire `delta` fills if `≥ min_notional` | `engine.py:97` | All-or-nothing; cannot model liquidity-constrained entries. |
| **Point-in-time (engine)** | Correct: strategy sees `df.iloc[:i]`, fills at close of `i`, 1-bar lag | `engine.py:81-90` | Honest. |
| **Point-in-time (replay)** | Correct post-fix: reveals `[0, cursor)` only | `replay.py:38-44` | Honest (DEEP_DIVE fixed lookahead at `DEEP_DIVE_REVIEW.md:35`). |
| **Point-in-time (live/paper)** | **Repaint bug** — `StoreDataProvider.get_history` may include the forming bar | `data_provider.py:38-42` | Deferred (`DEEP_DIVE_REVIEW.md:70-72`); highest-priority latent bias. |
| **Walk-forward** | Contiguous, non-overlapping OOS folds with `warmup` lookback per fold | `validation.py:66-83` | Honest; per-fold engine restart mirrors live cold-start. |
| **Holdout** | Locked final-fraction split, evaluated once | `validation.py:153-164` | Honest; walk-forward never sees holdout. |
| **Multiple-testing** | Deflated Sharpe Ratio (Bailey/LdP) over pooled per-bar OOS Sharpe | `validation.py:122-135`, `metrics.py:131-146` | Strong; PSR/EMSR/DSR all implemented. |
| **Benchmark** | Directional: HODL (price-only, no fees). Carry/spike: CASH (0). Cross-sectional: equal-weight HODL of universe. | `validation.py:138-150,239`, `carry.py:115`, `funding_spike.py:129`, `cross_sectional.py:285-309` | HODL-only for long strategies; no factor/beta-adjusted benchmark. |
| **Universe membership** | `store.symbols(timeframe)` — only coins still stored | `cross_sectional.py:69`, `store.py:131-138` | Survivorship-biased (delisted coins gone). |
| **Direction** | Long-only spot; bearish → flatten | `engine.py:167-174` | Cannot represent shorts or true market-neutral in the engine. |
| **Funding accrual** | Absent in `BacktestEngine`; modeled in standalone carry/spike sims | `engine.py` (none), `carry.py:159`, `funding_spike.py:183` | Two parallel cost models, neither unified with the equity curve. |
| **Basis** | Fixed `basis_drag_bps` (default 0), not a measured perp-spot basis | `carry.py:52,146` | Unpriced by default; structurally a guess. |
| **Leverage / liquidation** | None (~1x unlevered everywhere) | `carry.py:21-23` | Deferred to "risk-rails phase". |
| **Listings/delistings** | Not modeled; no schema for it | `store.py:13-43` (no table) | Listing-day and pre-delist edges cannot be tested. |
| **Order book / depth** | Not stored; `fetch_order_book` exists in client but unused in backtest | `client.py:136-138` | Spread/depth/impact edges un-representable. |
| **Event-time / barriers** | None — bar-close loop only | `engine.py:81` | No event triggers, no survival barriers. |
| **Vol-targeting** | Long-only vol scale, capped by `max_weight` | `engine.py:36-37,143-155` | Cannot add exposure via shorts. |
| **Equity mark** | Mark-to-close each bar (`cash + position*price`) | `engine.py:96,129` | No intrabar MTM, no funding in equity. |

---

## (b) Biases that would MASK a genuine non-standard edge

These are the silent failures — a real edge exists, the backtest returns "no edge".

1. **Taker-only fee overstates cost on maker strategies.** `engine.py:31,100` charges 0.1% on every fill. MEXC spot maker fee is 0%. A passive liquidity strategy that earns the spread and pays 0% maker would be charged ~10–50× its true cost, turning a winning maker edge into a wash. *Mask: any maker/limit edge.*

2. **No funding accrual in the core engine.** A long perp position in a negative-funding regime (or a short in positive funding) earns carry that the engine never books. *Mask: structural carry on directional perp positions.*

3. **Long-only clamp hides short/reversion/market-neutral edges.** `engine.py:170` clamps weight to `[0, max_weight]`; `engine.py:173` returns 0 on bearish (flatten). Any alpha that lives on the short side, or in long-short netting, scores as exactly zero. *Mask: short factor, mean-reversion short, stat-arb.*

4. **HODL-only benchmark for directional strategies.** `validation.py:239` gates on `oos_return > hodl`. An edge that produces HODL-like returns with half the variance, or that wins by being *flat* (avoiding drawdowns), fails this gate despite being genuinely valuable. No low-vol or risk-adjusted benchmark. *Mask: defensive/timing/market-neutral-vs-HODL edges.*

5. **Survivorship bias in the cross-sectional universe.** `cross_sectional.py:69` ranks `store.symbols(timeframe)` — delisted coins (often the losers) are absent, inflating both the strategy return and the equal-weight HODL benchmark in correlated ways. *Mask: reversion/value on weak names; listing/delist edges entirely.*

6. **Symmetric fixed slippage with no impact.** `engine.py:32,99` charges the same 5bps on a $10 and a $10k order in an illiquid alt. Small-cap edges that depend on tight spreads get overcharged; large-order edges that depend on depth get *under*charged. *Mask: microcap/illiquid strategies; depth-aware sizing.*

7. **All-or-nothing fills (`engine.py:97`).** A strategy whose edge requires scaling into the book over multiple bars (TWAP/VWAP) or that is sized by available liquidity sees its size forced to the full delta or zero. *Mask: scaling/laddered entries.*

8. **Basis drag defaults to zero (`carry.py:52`).** A delta-neutral book pays real basis noise; with `basis_drag_bps=0` the carry edge looks *better* than live, which can *flip a fail to a pass* — the opposite masking direction, but it can also mask a *genuine* edge by making carry look like "free money" so the real, basis-eaten version never gets the modeling investment. *Bidirectional mask.*

9. **No event/barrier survival.** Funding-settlement, liquidation-cascade, listing-day, and deprecation events are invisible. An edge that triggers on these events (the most plausible "non-standard" crypto edges) cannot fire. *Mask: event-driven alpha.*

10. **Fixed bar-close timing.** `engine.py:81,86` decides and fills at the same close. Strategies needing to act *at the open* or *at funding settlement* (a specific intrabar timestamp) cannot express that timing. *Mask: funding-tick / open-auction edges.*

11. **Live data repaint (deferred).** `data_provider.py:38-42` can feed the forming bar to indicators. If a "live paper" run looks better than replay, this lookahead is why — it would mask the *gap* between backtest and live, hiding that an edge is non-existent. *Mask: backtest-vs-live gap.*

12. **`min_notional=10` silent skip (`engine.py:34,97`).** Signals below $10 notional vanish without a trace; for a microcap strategy this can silently drop most of the trades. *Mask: microcap edge.*

13. **Two parallel cost models.** Carry/spike (2bp) vs engine (10bp) vs `PaperExecutor` (10bp, `execution.py:50`). A strategy tested in one harness and deployed via the other is mispriced before it starts. *Mask: cross-harness consistency.*

---

## (c) Non-standard edges the CURRENT engine CANNOT represent

| Edge | Why it's un-representable | Blocking code |
|---|---|---|
| **Maker / passive liquidity provision** (post limit, earn MEXC 0% maker, queue, partial/non-fill) | No `fill_mode`; every order is taker at the close with fee+slip. No queue, no non-fill probability, no rebate. | `engine.py:31,99-100`; `BacktestConfig` has no maker field |
| **Funding-rate harvesting (directional perp)** | Engine is spot-only and never accrues funding; perp OHLCV is not joined into the equity loop. | `engine.py:167-174` (no funding term); store has funding table but engine doesn't read it |
| **Short / long-short / market-neutral via real legs** | `_target_value` clamps to `[0, max_weight]`; `Signal.direction ∈ {bullish,bearish,neutral}` has no short-with-size; bearish = flatten. | `engine.py:170,173`; `signals.py:29` |
| **Delta-neutral carry in the unified engine** | Exists only as a standalone simulator (`carry.py`), not via coordinated spot+perp legs in `BacktestEngine`; basis is a fixed bps, not measured; no leverage/liquidation. | `carry.py:21-23,52` (deferred); engine has no perp leg |
| **Event-time entries** (funding settlement, liquidation cascade, listing day, deprecation) | Fixed `for i in range(1,len+1)` bar loop at close; no event hook, no intrabar timestamp trigger. | `engine.py:81,86,90` |
| **Listings / delistings survival** | Universe = `store.symbols()` survivors; no `listing_ts`/`delist_ts` schema, no per-bar universe filter. | `cross_sectional.py:69`; `store.py:13-43` (no listings table) |
| **Order-book / depth-aware strategies** (spread capture, impact-limited sizing, L2 microstructure) | No L2 data stored; `fetch_order_book` is live-only and unused in backtest; infinite liquidity at close. | `client.py:136-138` (unused); `store.py` has no book table; `engine.py:99` |
| **Basis / perp-spot arbitrage** | No synchronized perp+spot price pair in the engine; `basis_drag_bps` is a flat guess, not a measured basis series. | `carry.py:52,146`; engine has no perp price feed |
| **Funding-spike fade with directional leg coordination** | `funding_spike.py` models a *single perp leg* synthetically; cannot coordinate a spot hedge or use real partial books. | `funding_spike.py:159-188` (single-leg, no hedge) |
| **Vol-targeted short / risk-parity** | Vol scale multiplies a long-only weight (`engine.py:170`); can't scale a short. | `engine.py:148-155,170` |

---

## (d) Minimal engine changes to test 3–4 non-standard strategy types fairly

Guiding principle: the *honest machinery that already exists* (walk-forward OOS, DSR, holdout, PIT firewall in `validation.py` + `replay.py`) is the hard part and is correct. The gaps are in **fill semantics + instrument support + universe/event data**. Make the smallest change that reuses the existing validation harness.

### Change 1 — Maker / passive-fill support (unlocks maker edges)
**Data:** none new for a first cut (optional: trade prints later for a queue model).
**Engine edits:**
- Add `fill_mode: Literal["taker","maker"]`, `maker_fee_pct=Decimal("0")`, `maker_fill_prob: float`, `maker_price_improvement_bps: float` to `BacktestConfig` (`engine.py:28-37`).
- In the fill block (`engine.py:97-103`), branch on `fill_mode`: maker applies `maker_fee_pct`, *reverse* slippage (price improvement), and a Bernoulli non-fill gate (`random.random() < maker_fill_prob`) — seeded for reproducibility. Unfilled `delta` carries to next bar (new `pending_delta` state).
- Log fill/no-fill so DSR's `n_obs` still reflects real decisions.
**Why minimal:** one config branch + one carry-over state; the validation grid in `validation.py:216` and `cross_sectional.py:367` reuses unchanged.

### Change 2 — Perp mode + funding accrual + short side (unlocks carry, funding-harvest, long-short)
**Data:** already present — `store.funding` table (`store.py:29-37`) and `MexcFuturesClient.fetch_funding_rate_history` (`client.py:195-256`). Need perp OHLCV ingest (spot perp symbol map exists: `to_perp_symbol`, `client.py:158`).
**Engine edits:**
- Add `perp: bool`, `allow_short: bool`, `funding_col: str = "funding_rate"` to `BacktestConfig`.
- Extend `Signal.direction` to accept `"short"` with a magnitude (`signals.py:29` validator + `engine.py:_target_value`): in perp mode, target weight ∈ `[-max_weight, +max_weight]` (`engine.py:167-174`).
- In the bar loop, after the fill, accrue `position * funding_rate[i]` to cash (`engine.py:129`, gated by `cfg.perp` and presence of a funding column joined to the candle frame).
- Replace the flat `basis_drag_bps` with a *measured* perp−spot basis series (join perp close and spot close per ts) so `carry.py:146`'s drag becomes empirical.
**Why minimal:** the validation/DSR harness doesn't change; `carry.py` and `funding_spike.py` collapse INTO the engine (delete two duplicate simulators, one equity curve).

### Change 3 — Event-time entry hook + listings/delistings (unlocks event + survival edges)
**Data:** new `listings`/`delistings` tables (`store.py:13-43`): `(symbol, listing_ts, delist_ts)`. Source: MEXC market history / CCXT `load_markets` snapshots over time (or a one-time backfill). Optional: `events` table for funding-settlement timestamps (derivable from existing funding rows).
**Engine edits:**
- Per-bar universe membership in `cross_sectional.py` (`cross_sectional.py:69,127-144`): filter symbols to `listing_ts <= ref_ts < delist_ts`. This **kills survivorship bias** — the single most impactful change.
- Add an optional `strategy.on_event(event, history) -> Signal | None` hook called *before* the bar loop in `engine.py:81`, where `event` is the funding settlement / listing / delist crossing that bar's timestamp. Strategy can force a same-bar entry keyed to the event ts rather than the close.
**Why minimal:** universe filter is a 3-line change with huge bias removal; the event hook is additive and strategies that ignore it behave exactly as today.

### Change 4 — Fill-grade + impact model (unlocks depth-aware + scales fairly)
**Data:** snapshot L2 books (or just top-of-book spread + 1 level depth) at bar close into a `books` table (`store.py` schema add). One snapshot per symbol per bar keeps volume modest.
**Engine edits:**
- Add `FillGrade` to `BacktestConfig`: `slippage_pct` becomes a function `slippage(notional, bar_volume, book)` (default: current flat 5bps; with book: linear impact `λ * notional / book_depth`).
- Replace the all-or-nothing gate (`engine.py:97`) with a partial-fill cap at available book depth; residual carries to next bar (shares state with Change 1's `pending_delta`).
**Why minimal:** the slippage function is a strategy-injected callable; without L2 data it degrades to today's behavior, so it's backward-compatible.

### What to do FIRST (bias-removal before feature work)
The changes above add capability, but two **deferred/existing biases should be fixed before any non-standard edge is trusted**, because they actively corrupt the comparison:

1. **Fix the live `StoreDataProvider` repaint** (`data_provider.py:38-42`, deferred at `DEEP_DIVE_REVIEW.md:70-72`) — drop the last (forming) bar for indicators. Without this, a "live paper" run is not comparable to replay, so any edge that looks live-only is a lookahead artifact.
2. **Add delisted symbols to the store + universe filter (Change 3's filter).** Survivorship is the single bias most likely to manufacture a *fake* edge and to *mask* a real one simultaneously — it must go before any cross-sectional non-standard strategy is graded.

---

## Net read

The backtest layer's *statistics* (walk-forward + DSR + holdout + PIT firewall) are honest and strong. Its *instrument/fill model* is narrow: it can fairly test **long-only spot TA/timing strategies that pay taker fees**. Anything whose edge lives in **maker economics, funding, the short side, event timing, listings/delistings, or order-book microstructure** is either un-representable or systematically mispriced today — so a "no edge" verdict for those families is not informative. The four changes above reuse the existing validation harness and mostly reduce to: (1) a `fill_mode` branch, (2) perp/short/funding in the engine, (3) a per-bar universe filter + event hook, (4) an injectable slippage/partial-fill function.

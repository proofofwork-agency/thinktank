# 06 — Universe / Selection Edge Audit

**Agent:** 6/60 — Universe-edge research
**Scope:** `rapana/universe/` (Scout + ranker + PIT validation) and `rapana/config.py`
**Thesis:** Pair *selection* compounds more durably than entry/exit timing. A momentum-following selector feeding a mean-reverting strategy is anti-edge; matching the selector to the strategy's structural advantage is where durable crypto alpha lives.

---

## (a) Current Scout Selection Logic

The selector is a 4-stage pipeline. Live network touch is isolated in `Scout`; the actual ranking decision is in the pure, IO-free `rank_universe` so the *same* function ranks live and backtest folds.

### Stage 1 — Discovery (hard eligibility filter)
`rapana/universe/scout.py:56-69` (`Scout.discover_candidates`)
- Quote currency MUST be `USDT` (`scout.py:61`).
- Market MUST be `active` AND `spot` (`scout.py:62-64`).
- Base asset must NOT be a stablecoin (whitelist `_STABLE_BASES`, `scout.py:26-29` — USDT/USDC/DAI/FDUSD/etc.).
- Base asset must NOT be a leveraged ETF token (regex `\d+[LS]$` matches `BTC3L`/`ETH5S` but spares `JUP`, `scout.py:23,32-33`).
- Output sorted ascending — deterministic.

### Stage 2 — Liquidity prefilter (top-K truncation)
`rapana/universe/scout.py:71-91` (`Scout.prefilter_by_ticker`)
- Single bulk `fetch_tickers()` call, screen by **24h quote volume** (`scout.py:86-89`).
- Keep top `candidate_k` (default **50**, `scout.py:53`, `config.py:78`).
- This is itself a (coarse, biased) selection: 24h volume over-samples flavor-of-the-week meme pumps.

### Stage 3 — History fetch
`rapana/universe/scout.py:93-105` — fetches `history_bars` OHLCV per survivor. Default = `momentum_lookback + 5` = **35 bars** (`scout.py:54`). Very short — the Scout looks back ~30 hours on a 1h timeframe.

### Stage 4 — Rank (the actual decision)
`rapana/universe/ranker.py:81-107` (`rank_universe`), parameters in `UniverseParams` (`ranker.py:20-26`):

| Feature | Formula | Source |
|---|---|---|
| Liquidity | `median(close * volume).tail(lookback) * bars_per_day` | `ranker.py:46-55` |
| Momentum | `close[-1] / close[-1-lookback] - 1` | `ranker.py:73` |
| Volatility | `rolling_std(pct_change(close), lookback).iloc[-1]` | `ranker.py:74`, `indicators.py:63-66` |
| **Score** | **`momentum / max(volatility, vol_floor)`** | `ranker.py:77` |

Filters applied (`ranker.py:94-104`):
- Drop if fewer than `momentum_lookback + 1` bars (implicit minimum-age screen, **31 bars**).
- Drop if `dollar_volume < min_quote_volume_usd` (default **$2M/day median**, `ranker.py:23`). Median-not-mean is deliberate: a single wash-trade spike can't smuggle a thin coin through (`ranker.py:49-50`).
- Drop if score is NaN.

Sort: `(-score, symbol)` — deterministic tie-break (`ranker.py:106`). Take `top_n` (default **5**, `ranker.py:22`).

### Rebalance cadence
In `auto` mode the fleet re-runs `Scout.select_symbols()` every `rebalance_bars` cycles (default **24** = daily on 1h, `config.py:77`, `fleet/orchestrator.py:153-180`). Currently-held positions are unioned with new picks so a dropped symbol keeps being managed by the risk gate (`orchestrator.py:173-174`) — good, no silent orphaning.

### What the selector optimizes for, in one sentence
**Risk-adjusted trailing-30-bar return, on USDT-spot coins that passed a 24h-volume top-50 cut.** That is a *short-horizon, trend-following, liquidity-screened* selector. There is no funding, basis, age, listing, unlock, or volatility-regime signal.

---

## (b) Bias Check — momentum-following, listing-lookahead, survivorship

### Is it momentum-following? — **YES, strongly.**
The score is literally `momentum / volatility` (`ranker.py:77`). The prefilter on 24h quote volume is *also* trend-correlated (pumped coins print volume). The Scout is doubly trend-exposed: it picks names that **already went up**, in proportion to how much they went up.

### Does it buy what already pumped? — **Yes, by construction.**
A coin that doubled in the last 30h will, all else equal, dominate the score. This is the classic " retrospective winner" screen. Whether *post-selection* drift is positive (momentum continues) or negative (mean-reversion) depends entirely on the strategy layer — and the strategy layer here includes `MeanReversion` (`strategies/meanrev.py:10-11`), which is **directly counter-indicated** by this selector (you're pre-filtering to the exact population — extended names — where RSI reversion fails most often). Feeding a mean-reverting strategy a momentum-selected universe is anti-edge.

### Point-in-time validation — **honest, verified.**
- The anti-lookahead firewall is real: `select_universe_pit` slices `df[df["ts"] < test_start_ts]` *before* ranking (`universe/validation.py:60-69`). `rank_universe` cannot see the fold it's trading.
- Test `test_pit_cannot_see_the_future_spike` (`tests/test_universe_validation.py:57-63`) proves it: CCC's late moonshot wins on full-data ranking but is invisible to PIT selection at bar 15.
- The funding-rate ingester also drops not-yet-settled intervals (`mexc/client.py:213-215, 238-239`), so the carry track is PIT-clean too.

### Survivorship bias — **EXPLICIT, UNRESOLVED.**
The repo is honest about this and ships it as a caveat, not a fix (`universe/validation.py:9-13, 37-41`):
> "candidates are symbols listed on MEXC TODAY; coins delisted before now are absent, so realized OOS returns are an optimistic upper bound. Point-in-time selection removes look-ahead in ranking — it cannot resurrect delisted names."

The candidate set in `_cmd_validate_universe` (`cli.py:563-572`) is `store.symbols(timeframe)` — every coin ever ingested (typically because it was alive at ingest time). Coins delisted before the ingest window started are **invisible**. The PIT ranker correctly avoids looking *inside* a fold's future, but the *population it ranks over* is pre-censored to survivors.

**Quantification of the leak:** any coin that got delisted for cause (rug, hack, regulatory, insolvency) is absent — and those are precisely the coins where a momentum-following selector would have been most catastrophically wrong (they often pumped first). The realized OOS Sharpe is therefore an *upper bound* on live selector performance; the true number is worse.

### Listing-lookahead bias — **PARTIALLY guarded, mostly incidental.**
- The `len(df) < momentum_lookback + 1` floor (`ranker.py:94`) incidentally excludes coins younger than 31 bars, so a brand-new listing cannot win on a single green hourly candle.
- BUT there is **no first-bar-age metadata** in the store (`data/store.py` has no listing-date column; `meta` table is generic key/value, `store.py:39-42`). Once a coin crosses 31 bars it enters the candidate set with no special handling, even though freshly-listed small-caps have radically different drift/volatility profiles than seasoned coins.
- The 35-bar default history (`scout.py:54`) is so short that a 31-bar-old coin effectively enters ranked on its ENTIRE post-listing life — i.e., the selector is blind to "this is a brand-new listing" as a special state.

### Lookahead in `cross_sectional.py`
The cross-sectional ranker (`backtest/cross_sectional.py:8-9`) ranks bar `i`'s holdings from data ending at `i-1` — PIT-clean. It already supports `funding_rank` as a signal (`cross_sectional.py:34`) — so the *infrastructure* to rank by funding exists, but the **live Scout does not use it**. The cross-sectional backtest harness is where non-momentum selection edges should be prototyped.

---

## (c) Non-standard Selection Edges (ranked by edge-per-effort)

Each entry: the **signal**, the **expected post-selection drift**, and the **integration cost** in this repo.

### 1. **Carry-selection: rank by trailing mean funding rate** (HIGHEST edge-per-effort)
- **Signal:** `mean(funding_rate)` over the last N settlements per symbol. Long-spot + short-perp of the top-K highest-payers. The repo ALREADY ingests this (`data/ingest.py:FundingIngester`, `cli.py:94-127`), ALREADY stores it (`data/store.py:29-37, 151-172`), and ALREADY has a cross-sectional ranker slot for it (`backtest/cross_sectional.py:34`). The **only** missing piece is wiring `funding_rank` into `Scout` / `UniverseParams`.
- **Expected drift:** Structural income, NOT a price bet. Longs pay shorts when `funding > 0` (which is most of the time on retail-heavy MEXC perps). ~0.01–0.05% per 8h is common on high-beta alts. Compounded, this is **direction-independent** — works in bull and bear regimes. The carry backtest (`backtest/carry.py:1-28`) already proves the framing.
- **Why durable:** Funding is a structural feature of the perp/spot basis created by leverage demand, not a price-prediction game. It's the most defensible edge in crypto and the repo is 90% of the way to selecting on it.
- **Integration:** New `UniverseParams` field `signal: Literal["momentum","funding"]`; in `rank_universe`, when `signal=="funding"`, replace the score with `-mean(funding)` (negative because we want high-payers). Reuses `load_store_funding` (`cross_sectional.py:81-99`). Estimated 40 lines.

### 2. **Post-listing drift: bucket by `first_bar_age`** (HIGH edge, medium effort)
- **Signal:** Add `first_bar_ts` to the candles schema (or compute from `MIN(ts)` per symbol). Bucket: `<7d` (wash/irrational), `7–30d` (negative drift as speculator exit + unlock pressure), `30–90d` (stabilizing), `>90d` (seasoned).
- **Expected drift:** Empirically (Bianchi et al., "Cryptocurrencies as an Asset Class?") MEXC/small-exchange listings show **negative** drift in the 7–60d window as airdrop recipients exit and initial unlock cliffs hit. A *short-bias* selector (or simple exclusion of `<30d` names) avoids a known drawdown source the current Scout walks into blindly.
- **Why durable:** It's a structural feature of token distribution, not a statistical pattern. The current Scout *systematically* over-weights fresh listings because their 30h momentum and 24h volume are inflated by listing-day activity — exactly the wrong bucket.
- **Integration:** One new column + index in `_SCHEMA` (`data/store.py:19-24`), one `first_bar_age` filter in `UniverseParams`. ~60 lines plus a migration.

### 3. **Pre-delisting avoidance / post-announcement bounce harvesting** (HIGH edge, HIGH effort)
- **Signal:** Consume MEXC delisting announcements (REST or scraped). Two sub-edges:
  - **Avoidance:** Drop any symbol within N days of a delisting announcement — they routinely dump 20–60% as leveraged longs are force-liquidated. Currently the Scout would *preferentially select* these because the pre-announcement pump inflates both momentum and volume.
  - **Harvesting:** Post-announcement, spot often decouples from perp (perp goes to premium as shorts pile in, then craters as longs exit). A long-spot/short-perp basis trade around the delisting event has documented positive expectancy.
- **Expected drift:** Strongly **negative** pre-event (avoidance saves a -30% to -60% drawdown); mean-reverting post-event on the perp/spot basis.
- **Why durable:** Forced liquidations are mechanical, not behavioral — they happen regardless of opinion. They are also time-bounded, so the edge doesn't crowd.
- **Integration:** Requires a new event-ingest path (no announcement endpoint in `mexc/client.py` today). Needs a `delisting_watch` table and a Scout exclusion filter. ~200 lines + an external data source. Higher effort, but **catastrophe-prevention** value alone justifies it — one avoided delisting pays for the integration.

### 4. **Volatility-regime bucketing** (MEDIUM edge, LOW effort)
- **Signal:** The Scout computes `volatility` already (`ranker.py:74`) but only uses it as a *normalizer*. Instead, **bucket** by realized vol: low-vol bucket → route to `MeanReversion` strategy; high-vol bucket → route to `Breakout`/`TrendFollowing`.
- **Expected drift:** Mean-reversion works in calm regimes and fails in trending regimes (and vice versa). Splitting the universe by vol regime lets each strategy trade only the population where it has edge, instead of both strategies firing on every name. Expected: roughly +0.2–0.4 Sharpe on each strategy from in-regime filtering alone.
- **Why durable:** Regime specialization is the canonical "free" win in systematic trading — and it directly resolves the Scout/strategy mismatch identified in §(b) (momentum selector fighting mean-reversion strategy).
- **Integration:** `FleetConfig` already has a per-symbol loop (`orchestrator.py:139-140`). Add a strategy-router keyed on the Scout's already-computed vol. ~30 lines.

### 5. **Low-float / unlock-approaching tokens (short bias)** (MEDIUM edge, HIGH effort — external data)
- **Signal:** `scheduled_unlock_notional / circulating_supply`, sourced from TokenUnlocks / CryptoRank / Messari. Short-bias (or simple avoidance) in the 30d window around a large unlock.
- **Expected drift:** **Negative**, mechanically — supply hits the market. Documented in academic literature (Liu & Tsyvinski 2021 "Risks and Returns of Cryptocurrency").
- **Why durable:** Driven by token vesting schedules, which are public and deterministic.
- **Integration:** Requires external data feed (no tokenomics source in repo). Highest external effort, lowest marginal benefit on a fleet this size.

### 6. **USDC-pair inclusion + USDT/USDC basis** (LOW-MEDIUM edge, LOW effort)
- **Signal:** The `quote == "USDT"` hard-filter (`scout.py:61`) discards the entire USDC order book. Two edges: (a) USDC books are often thinner but *less wash-traded*, giving cleaner signals; (b) the USDT↔USDC price spread of the same coin flags venue-specific flow and is itself an arb signal.
- **Expected drift:** Modest. Most coins are USDT-dominant on MEXC. But the marginal candidates that pass a USDC liquidity floor are *different* coins than the USDT-screen survivors — diversifies the selection.
- **Integration:** Relax `_STABLE_BASES`/quote filter, add a `quote_currency` param to `UniverseParams`. ~20 lines.

---

## (d) Integration Notes — how selection compounds with the strategy layer

**The single most important fact:** the Scout's score and the strategy layer's edge are *coupled risk factors*, not independent. A great selector for one strategy is a catastrophic selector for another.

1. **Momentum selector × Momentum strategy = concentration, not edge.**
   The current `Breakout`/`TrendFollowing` strategies (`strategies/breakout.py:11`, `strategies/trend.py:10`) are trend signals. The Scout (`ranker.py:77`) also picks by trend. Stacking them means the fleet's P&L is a *leveraged* bet on the trend factor — when momentum regime-flips, both layers fail simultaneously. The validation `PASS` verdict (`cli.py:602-603`) is meaningless here because it tests the *combined* arm; it can't tell you that selection contributed 80% of the risk.

2. **Momentum selector × MeanReversion strategy = anti-edge.**
   `strategies/meanrev.py:11` is RSI reversion. Pre-filtering to "things that already pumped" is precisely how you find the names where RSI reversion gets run over. This pairing should be expected to *underperform* an equal-weight HODL of the same names.

3. **The validation harness is selector-pluggable — use it.**
   `_run_arm` (`universe/validation.py:98-146`) takes a `picker: Callable[[int], list[str]]`. Today only two pickers are exercised: PIT-Scout and fixed-majors (`validation.py:202-210`). Adding a `funding-rank` picker, a `post-listing-excluded` picker, and a `vol-bucketed` picker is a few-line change and the harness will produce apples-to-apples Deflated-Sharpe comparisons (`deflated_best`, `validation.py:213`). **This is the cheapest research surface in the repo and it's under-used.**

4. **Selection edge > timing edge, empirically.**
   Crypto's cross-sectional dispersion is enormous — the gap between the best- and worst-performing liquid coin in any given week is often 50%+. A selector that systematically avoids the bottom quartile (delistings, unlocks, post-listing crash) captures more edge than any entry-timing rule on a fixed universe. The repo's energy is currently split: directional timing (failed C2 — see `RESEARCH-SYNTHESIS.md`), carry (passed C2), and universe (this audit). The carry result is the tell: when the team let *selection* (carry-eligible names) drive the strategy, edge appeared; when they tried *timing* on majors, it didn't.

5. **Recommended prioritization for the next sprint:**
   1. Wire `funding_rank` into `Scout` (edge #1) — uses infrastructure that already exists and is PIT-validated.
   2. Add `first_bar_age` exclusion (edge #2) — closes the listing-lookahead gap noted in §(b).
   3. Add a vol-regime strategy router (edge #4) — resolves the selector/strategy mismatch today.
   4. Prototype all three through the existing `_run_arm` harness before touching live capital — the comparison is one CLI flag away.

---

## Cited files
- `rapana/universe/scout.py:23,26-29,32-33,53,54,56-69,71-91,93-105,107-114`
- `rapana/universe/ranker.py:20-26,46-55,58-78,81-107,110-112`
- `rapana/universe/validation.py:9-13,37-41,60-69,98-146,179-224`
- `rapana/config.py:70-78,96-101`
- `rapana/fleet/orchestrator.py:36,54-55,81,153-180`
- `rapana/strategies/breakout.py:11,13`, `trend.py:10`, `meanrev.py:10-11`
- `rapana/backtest/cross_sectional.py:8-9,34,56-99`
- `rapana/backtest/carry.py:1-28`
- `rapana/mexc/client.py:62-69,195-256`
- `rapana/data/store.py:20-42,131-138,151-172`
- `rapana/data/ingest.py:130-179`
- `rapana/cli.py:64-127,130-143,549-607`
- `tests/test_universe_validation.py:50-63,97-113`
- `rapana/indicators.py:63-66`

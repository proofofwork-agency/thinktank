# 07 — Profit, benchmark, and the honest profit bar

**Agent:** 7/60 · **Scope:** `rapana/fleet/performance.py`, `rapana/fleet/replay.py`, `rapana/fleet/autopilot.py`, `rapana/backtest/metrics.py` (+ the validators that actually compute "profit": `rapana/backtest/validation.py`, `cross_sectional.py`, `carry.py`, `funding_spike.py`, `rapana/fleet/execution.py`, `portfolio.py`).
**Goal:** Define what "profit" means in this codebase, identify the benchmarks each gate measures against, surface the gaps that can manufacture fake profit, and propose an honest profit bar for a non-standard strategy.

All citations are `file:line`. The reviewer's bias: *beating a bad benchmark is fake profit; a strategy is only "profitable" if it clears a benchmark it would be unreasonable to lose to, net of every cost the live book will actually pay.*

---

## (a) Metric inventory

There are **two disjoint metric systems** in this repo. The fleet/promotion path uses one; the backtest research path uses another. They never share code and never agree on what "profit" means.

### A1. Fleet / paper / promotion metrics — `rapana/fleet/performance.py`

`PerformanceTracker` is what `autopilot.py` reads to decide whether to deploy more capital. It computes exactly **four** quantities, all from the equity curve of the in-memory `PaperPortfolio`:

| Metric | File:line | Definition | Notes |
|---|---|---|---|
| `total_return` | `performance.py:34-38` | `final_equity / initial_equity - 1` | Gross of nothing — see (b). |
| `max_drawdown` | `performance.py:40-50` | historical worst peak-to-trough on the equity series | "Historical worst", never decreases — `performance.py:55-59`. |
| `current_drawdown` | `performance.py:52-70` | peak-to-LAST-equity (clears on new high) | Used for reactive demote/halt; comment at `performance.py:53-60`. |
| `win_rate` | `performance.py:72-76` | `#positive_deltas / #nonzero_deltas` over per-cycle realized-PnL **deltas** | **Per-cycle, not per-trade** — see Gap G3. |

`PerformanceTracker.record` (`performance.py:21-28`) is called once per cycle from `runner.run_replay` (`runner.py:75-80`) and `runner.run_scheduled` (`runner.py:113-115`). The "delta" is `realized_total - last_realized` where `realized_total` is the whole portfolio's running realized PnL from `PaperPortfolio.realized_pnl` (`portfolio.py:20, 45`). So one delta can blend many fills across many symbols in one cycle.

`summary()` (`performance.py:78-90`) returns: `cycles, initial_equity, final_equity, total_return_pct, max_drawdown_pct, realized_pnl, win_rate_pct, trade_events`.

### A2. Autopilot's ad-hoc "Sharpe" — `rapana/fleet/autopilot.py`

`Autopilot._sharpe` (`autopilot.py:136-154`) is a **fourth metric bolted onto A1** at promotion time. It is **not annualized** — `autopilot.py:153`: *"Per-cycle Sharpe; thresholds are relative, not annualised."* It is the mean/std of per-cycle equity returns with a std floor to suppress explosive Sharpes on near-flat curves (`autopilot.py:148-152`). It is NOT a Sortino, NOT a benchmark-relative information ratio, NOT net of any benchmark.

### A3. Backtest / research metrics — `rapana/backtest/metrics.py`

`PerformanceMetrics` (`metrics.py:12-31`) is the rigorous system. It is used by every walk-forward validator but **never by the fleet/promotion path**.

| Metric | File:line | Definition |
|---|---|---|
| `total_return` | `metrics.py:47` | `final_equity / initial_equity - 1` |
| `annualized_return` | `metrics.py:49` | CAGR over `len(equity)/bars_per_year` |
| `sharpe` | `metrics.py:51-52` | `mean/std * sqrt(bars_per_year)`, population std (ddof=0) |
| `sortino` | `metrics.py:54-62` | downside-only denominator; falls back to Sharpe when no losing bars to avoid NaN/invalid-JSON (`metrics.py:58-62`) |
| `volatility` | `metrics.py:64` | annualized std |
| `max_drawdown` | `metrics.py:66-69` | cummax-based |
| `win_rate` | `metrics.py:71-78` | over **decided round-trips only** (buy legs with `pnl=0` excluded — `metrics.py:75-77`) |
| `profit_factor` | `metrics.py:73, 79` | `gross_profit / gross_loss` (+inf guard) |
| `num_trades`, `final_equity` | `metrics.py:81-91` | counts |

### A4. Selection-bias statistics — `rapana/backtest/metrics.py`

These are the crown jewels of the repo and the only honest-profit machinery:

| Function | File:line | What it answers |
|---|---|---|
| `probabilistic_sharpe_ratio` | `metrics.py:100-113` | P(true Sharpe > benchmark | noisy estimate, n_obs, skew, kurt) |
| `expected_max_sharpe` | `metrics.py:116-128` | Expected MAX Sharpe across `n_trials` strategies under the null of zero skill — the bar a backtest must clear just to be credible |
| `deflated_sharpe_ratio` (DSR) | `metrics.py:131-146` | P(best of `n_trials` has TRUE Sharpe > 0), correcting for selection bias + sample length + non-normality. The codebase convention (e.g. `metrics.py:142-143`, `validation.py:62`, `carry.py:113`) is **DSR > 0.95 = credible**. |

These statistics are computed **only inside the walk-forward validators** (`validation.py:122-135`, `cross_sectional.py:122-135`, `carry.py:277-291`, `funding_spike.py:318-332`, `universe/validation.py:213`). They are **not** wired into the autopilot. The autopilot's `Sharpe >= 1.0` gate (`autopilot.py:86, 25`) is **a different, naive Sharpe with no multiple-testing correction and no benchmark.**

---

## (b) Benchmark analysis — what each gate measures "profit" against

This is the part that determines whether "profit" is real. Five different gates, four different benchmarks:

| Gate / validator | File:line | "Profit" measured as | Benchmark | Net of fees? | Net of slippage? | Net of funding? |
|---|---|---|---|---|---|---|
| **Autopilot promote** (paper→live capital) | `autopilot.py:83-89` | `total_return` + per-cycle `Sharpe>=1.0` + `max_dd<=10%` over `>=100` cycles | **NONE** (absolute only) | Yes (taker 10bp + 5bp slip/side via `PaperExecutor`, `execution.py:48-54`) | Yes | **No** — spot portfolio, no funding accrual (`portfolio.py:9-53`) |
| Directional single-symbol walk-forward | `validation.py:138-150, 239` | OOS compounded return + DSR | **HODL of that same symbol**, price-only, no fees (`validation.py:138-150`) | Yes (`BacktestConfig` 10bp + 5bp; `engine.py:31-33, 97-100`) | Yes | N/A (spot) |
| Cross-sectional rotation | `cross_sectional.py:285-309, 407-408` | OOS compounded net return + DSR | **Equal-weight HODL of the full universe**, price-only, no fees | Yes (taker 2bp on turnover; `cross_sectional.py:263`) | No (only fee, no slippage on rebalance) | N/A |
| Funding-rate carry (C2) | `carry.py:144-163, 294-325` | OOS compounded **net carry** | **CASH** (`cash_return`, default `0.0`; `carry.py:115, 301`) | Yes (2bp fee + 2bp slip **per leg**, both legs; `carry.py:50-52, 144-146`) | Yes | **Yes** — `gross += f` (`carry.py:159`); reported separately from costs |
| Funding-spike fade (event study) | `funding_spike.py:159-188, 335-370` | OOS compounded **net** (price+fund−cost) | **CASH** (`cash_return`, default `0.0`; `funding_spike.py:129, 342`) | Yes (2bp fee + 2bp slip per side; `funding_spike.py:62-64, 173`) | Yes | **Yes** — `funding_pnl = -s*funding[i]` (`funding_spike.py:183`); split out from price PnL |
| Scout universe selection | `universe/validation.py:213-224` | OOS compounded return + DSR | **HODL basket of fixed majors** (`universe/validation.py:188, 214`) | Yes (engine defaults) | Yes | N/A |

### What "profit" actually means here (key reading)

1. **For the autopilot (the only gate that moves real money): "profit" is NOT benchmarked at all.** `autopilot.py:83-89` promotes when `cycles >= 100 AND max_dd <= 10% AND _sharpe() >= 1.0`. A strategy that simply went long BTC during a bull market would trivially clear this — Sharpe of slow-long equity curves in up-trends is large, drawdowns are small, and 100 cycles is a few days at `paper_interval`. **Beating this gate is not evidence of an edge.** The benchmark is implicit and it is "zero" — i.e. *absolute positive return*.

2. **For the research validators, "profit" = OOS net return beats an explicit benchmark AND DSR > 0.95.** The `passed` flag is consistently defined as `dsr > 0.95 AND best.oos_return > benchmark` (`validation.py:239`, `cross_sectional.py:408`, `carry.py:325`, `funding_spike.py:370`, `universe/validation.py:216`). This is the only honest definition of profit in the codebase.

3. **Fees & slippage: yes, modeled.** Backtest default is `fee_pct=0.001` (10 bp taker) + `slippage_pct=0.0005` (5 bp) per side (`engine.py:31-33`); `PaperExecutor` mirrors this exactly (`execution.py:48-54`). The carry/spike/cross-sectional validators use the **more realistic** 2 bp/side model (`carry.py:50-52`, `funding_spike.py:62-64`, CLI default `--fee 0.0002`, `cli.py:1056, 1074`). All legs in the carry book are charged (entry and exit, spot + perp; `carry.py:144-146`).

4. **Funding: only modeled where it is the PnL source** (carry, funding-spike). The fleet's spot paper portfolio and the directional backtest **never credit or debit funding** — which is correct for spot but means *a paper-replay run can never validate a carry strategy end-to-end*. The performance the autopilot sees is necessarily spot-only.

5. **Benchmarks are mostly price-only with no fees.** `hodl_oos_return` (`validation.py:138-150`) and `equal_weight_hodl_oos_return` (`cross_sectional.py:285-309`) compound `close/first_close` with no fees. This **understates** HODL's real-world cost slightly (a real buy-and-hold pays one entry fee), so the bar is mildly *favorable to HODL* and therefore **conservative for a strategy claiming to beat it**. Good direction.

---

## (c) Gaps — what can manufacture fake profit (or fake loss)

### G1. **Maker rebate (MEXC 0% maker) is never credited.** — *conservative, but distorts strategy choice*
Every cost model in the repo is taker-only: `engine.py:31` `fee_pct=0.001` "0.1% taker"; `carry.py:50` "taker fee per leg"; `funding_spike.py:62` "taker fee per side"; `cross_sectional.py:263` `fee = turnover * fee_pct`; `execution.py:48-54` taker-only. MEXC's 0% spot maker tier (documented in `RESEARCH-SYNTHESIS.md:46` as the venue's structural advantage) is **never modeled**. Effect: a maker-oriented strategy is *under*-credited in backtest, which is conservative — but it also means the system has **no incentive to prefer maker execution**, which the synthesis explicitly recommends. The "honest profit" is biased *downward*, but so is the strategy design signal.

### G2. **The autopilot promotes on absolute Sharpe with no benchmark.** — *the dangerous gap*
`autopilot.py:83-89` + `config.py:50` (`autopilot_promote_sharpe: float = 1.0`) gates real capital on `Sharpe >= 1.0` with **no HODL / BTC / equal-weight comparison**. The `_sharpe` is per-cycle, not annualized (`autopilot.py:153`), and there is no Deflated-Sharpe / multiple-testing correction. Combined with G3 (per-cycle win-rate) and the fact that `PerformanceTracker` never sees a benchmark, the promotion gate can be cleared by **any long-only book in a rising market**, exactly the failure mode `RESEARCH-SYNTHESIS.md:40` warns about ("roughly market-like returns minus unavoidable drag"). **The autopilot has no way to distinguish skill from beta.** This is the single biggest "fake profit" risk in the repo.

### G3. **`PerformanceTracker.win_rate` is per-cycle, not per-trade.** — *confirmed by DEEP_DIVE*
`performance.py:21-28, 72-76` computes `win_rate` over per-cycle realized-PnL deltas. `DEEP_DIVE_REVIEW.md:78-79` flagged this verbatim: *"`performance.win_rate` nets multiple trades per cycle and drops break-even closes, distorting the metric used to gate live promotion. Needs per-trade realized-PnL plumbing."* `metrics.py:75-77` was fixed for the backtest path (excludes `pnl=0` buy legs); `performance.py` was **not** fixed. It still over-counts "events" when no trades closed, under-counts when many trades closed in one cycle, and silently drops break-even closes.

### G4. **No "do nothing" / flat-cash baseline tracked by the fleet.**
The carry/funding-spike validators correctly use `cash_return` (`carry.py:115`, `funding_spike.py:129`) — but the **default is `0.0`** (`carry.py:301`, `funding_spike.py:342`), so "beating cash" defaults to "beating zero". That's fine for a stablecoin world but it's not a real risk-free rate. More importantly: **the autopilot never compares against a do-nothing baseline**, so it cannot tell that "I made 2% in a market that made 12%" is actually a *loss of skill*. A flat T-bill / USDC-yield baseline (~4-5% annualized as of mid-2026) should be the floor for any non-directional strategy; zero is a giveaway.

### G5. **Live data repaint in the scheduled paper path.** — *inflates paper profit*
`DEEP_DIVE_REVIEW.md:69-72` flagged: the live/scheduled paper path (`StoreDataProvider.get_history`) can include the current forming bar — the same lookahead class that was fixed for `ReplayProvider` (`replay.py:34-44`, also `DEEP_DIVE_REVIEW.md:35`). Until fixed, `run_scheduled` paper P&L is systematically optimistic. The autopilot could promote off repaint-inflated numbers. *(Highest-priority deferred item per DEEP_DIVE.)*

### G6. **Circuit breaker is realized-only, anchored to construction-time equity.** — *open risk not in profit*
`DEEP_DIVE_REVIEW.md:74-76`: only realized PnL, anchored at construction time, never re-baselined per day. A large **open** drawdown can exceed `max_daily_loss_pct` without tripping. Doesn't fabricate profit, but lets an unrealized loss sit while `PerformanceTracker.total_return` (which is equity-based) shows the truth — so the *equity* metric is honest even as the *breaker* under-protects.

### G7. **Cross-sectional validator omits slippage on rebalance.**
`cross_sectional.py:263` charges `fee = turnover * fee_pct` but no slippage. For small-cap rotation with realistic spreads, this is a few bp too generous. Directional engine does charge slippage (`engine.py:99`). Inconsistent and slightly optimistic for the cross-sectional track.

### G8. **DSR `sharpe_variance` is the cross-sectional variance of the small pre-committed grid — not all the strategies you mentally considered.**
`validation.py:128-129`, `carry.py:284-286`, `funding_spike.py:325-327` set `sharpe_variance = var(oos_sharpe_bar across records)` and `n_trials = len(records)`. This correctly deflates *within* a single grid run, but the human/researcher typically tries multiple grids, timeframes, and universes over time. The DSR is honest about *intra-grid* selection but cannot see *inter-grid* selection. The pre-committed small grids (`carry.py:67-72`, `funding_spike.py:79-84`) are a deliberate mitigation; the unbounded meta-search is not corrected for.

### G9. **No Sortino / Calmar / profit-factor in the fleet path.**
`PerformanceMetrics` (`metrics.py:12-31`) has all of these; `PerformanceTracker` has none. So the autopilot has no downside-aware metric. A few fat-tail losers can sit under a flatter mean and still pass `_sharpe >= 1.0`.

---

## (d) The honest profit bar (and why)

The right bar depends on **strategy class**, because "beating the market" is the wrong question for a market-neutral book. The repo already half-recognizes this: directional is benchmarked vs HODL, carry vs cash. The honest bar generalizes that principle and tightens the sample/correction requirements.

### D1. The four-part gate every "profit" claim must clear

A strategy is honestly profitable in this codebase iff **all four** hold:

1. **Out-of-sample only.** Pooled OOS returns across `>= 6` non-overlapping folds (`validation.py:66-83`), never the in-sample window.
2. **Net of all costs the live book will actually pay.** Fees AND slippage AND (where relevant) funding AND basis drag — `carry.py:144-146` is the gold standard; the directional `BacktestConfig` is acceptable for spot. **Maker rebate (G1) must be set to 0 unless maker execution is actually implemented** — crediting 0% maker while sending taker orders is itself fake profit.
3. **Beats the honest benchmark for its class** (Table below).
4. **DSR > 0.95** for the best of `n_trials`, where `n_trials` counts **everything tried in this research campaign**, not just the current grid (acknowledging G8).

| Strategy class | Honest benchmark | Why |
|---|---|---|
| Directional single-symbol (spot) | **HODL of that symbol** net of one entry fee (`validation.py:138` extended) | "Did timing beat just holding it?" — the only question that matters. |
| Cross-sectional rotation | **Equal-weight HODL of the full tradable universe**, net of one entry fee (`cross_sectional.py:285`) | De-hypothecates "stock-picking skill" from "the universe went up". |
| Market-neutral carry | **Cash / risk-free** (~4-5% annualized USDC T-bill yield, NOT 0; `carry.py:115` should default to a real rate) | Delta-neutral book has ~zero beta, so HODL is the wrong wall. |
| Event / overlay (funding-spike) | **Cash** (default 0 OK here — the overlay is *flat* by design) | Overlay earns nothing when inactive; cash is the apples-to-apples bar. |
| Live paper fleet (autopilot) | **NEEDS ADDING**: equal-weight basket of the deployed symbols, computed on the same bars (`autopilot.py` has none today) | Without this the autopilot cannot distinguish beta from alpha — see G2. |

### D2. Sample-size reasoning (the part most people skip)

The DSR is what makes the bar honest about sample size. Concretely:

- **Per-bar Sharpe, not annualized.** `metrics.py:131-146` and `validation.py:97-119` correctly feed `probabilistic_sharpe_ratio` a **per-observation** Sharpe and `n_obs` = pooled OOS bars. Annualized Sharpe is for display only (`validation.py:39`, `oos_sharpe_annual`).
- **Minimum `n_obs` for credibility:** the DSR's `sqrt(n_obs - 1)` term means a per-bar Sharpe of 0.03 needs on the order of **1,000+ OOS bars** to clear `P > 0.95` against a zero benchmark, more if returns are skewed/fat-tailed (`metrics.py:108-113` shows the skew/kurt penalty). At 1h bars that's ~42 days of pure OOS exposure; at 8h funding intervals that's ~year of OOS data. **A "100-cycle" autopilot sample is two orders of magnitude too small** to support a credible edge claim, even before noticing it has no benchmark (G2).
- **Multiple-testing deflation:** `expected_max_sharpe` (`metrics.py:116-128`) is the wall. With `sharpe_variance ~ 4e-4` (a typical grid) and `n_trials = 50`, the bar a strategy must clear is roughly `E[max] ≈ 0.025` per-bar — modest in isolation, fatal to a 3-strategy micro-grid that didn't pre-commit. The grids in `carry.py:67-72` (4 policies) and `funding_spike.py:79-84` (4 policies) are correctly small and pre-committed; **the directional and cross-sectional grids are larger and the search across symbols/timeframes compounds the trial count off-book (G8)**. The honest fix is to log every grid run into a campaign ledger and feed the cumulative count to `n_trials`.
- **Skew/kurt correction is real for these strategies.** Carry and funding-spike PnL is *approximately* the funding distribution, which is heavily right-skewed (long-tailed positive spikes). `metrics.py:109` penalizes via `skew * sharpe` — for the same Sharpe, positive skew yields a *lower* PSR, which is correct (the average is driven by rare good intervals). Any "honest profit" claim must report `skew` and `kurtosis` alongside DSR (`carry.py:107`, `funding_spike.py:107` already store them).

### D3. Concrete numerical bar (the answer to "how much profit is honest?")

Given the repo's own machinery, an honestly-profitable Rapana strategy should demonstrate, **on the locked holdout** (`holdout_split`, `validation.py:153-164`) — never the walk-forward window:

| Track | Honest profit bar |
|---|---|
| Directional spot | OOS net total return **> HODL of the same symbol(s) net of one entry fee** by a margin that survives DSR > 0.95 with `n_obs >= 1000` pooled OOS bars AND `worst_fold_return > 0` (`validation.py:45` exposes this — a strategy that nets positive only on average while one fold blows up is not honest profit). |
| Cross-sectional | OOS net total return **> equal-weight HODL of the full universe** with the same DSR/sample constraints. |
| Carry | OOS net carry **> ~4-5% annualized cash yield** (replace `cash_return=0` default) net of fees+slippage+basis drag, DSR > 0.95 over **>= 1 year of OOS funding intervals** (`n_obs >= 1095` at 8h). |
| Funding-spike | OOS net **> 0 (cash)** with DSR > 0.95 over **>= 1 year of OOS intervals**, AND `gross_price > 0` (not just `gross_funding`) — `funding_spike.py:109-110` separates these so that a "win" that is *only disguised carry* is visible and rejected. |
| Fleet autopilot promotion (the live-money gate) | **Currently has no honest bar.** Add: pooled paper-equity Sharpe minus basket-HODL Sharpe (information ratio) **> 0** with PSR > 0.95 AND `total_return > basket_HODL_return` over `>= 1000` cycles (not 100; `config.py:51` is 100× too lax), with the G5 repaint fix applied first. |

### D4. The single sentence

**An edge is honest iff, on data the strategy never saw, net of every cost the live book will pay, it beats the right benchmark for its class (HODL for directional, equal-weight HODL for rotation, cash for market-neutral/event) by a margin whose Deflated Sharpe Ratio — deflated by the true trial count and penalized for non-normality — exceeds 0.95 over at least ~1,000 out-of-sample observations.** Today the autopilot meets none of the italicized conditions, which is the most important finding of this report: the only gate that moves real money is the one with no honest profit bar at all.

---

## Pointers to fix (for the implementer)

- G2 (autopilot benchmark): add `basket_hodl_series` to `PerformanceTracker` and compute an information ratio in `autopilot._sharpe`; gate promote on `IR > threshold` AND `PSR > 0.95` instead of absolute Sharpe. Wire `deflated_sharpe_ratio` (`metrics.py:131`) in.
- G3 (win-rate): replace `PerformanceTracker.win_rate` with a per-fill realized-PnL list fed from `Fill` (`execution.py:15-29`), mirroring `metrics.py:71-78`.
- G4 (cash floor): default `cash_return` to a real USDC T-bill yield in `validate_carry_grid` (`carry.py:294-302`) and `validate_funding_spike_grid` (`funding_spike.py:335-343`).
- G1 (maker): only credit 0% maker if/when a `MakerExecutor` exists; until then keep taker-only — it is the conservative bias.
- G5 (repaint): drop the last unclosed bar in `StoreDataProvider.get_history` (per DEEP_DIVE).
- G8 (campaign ledger): persist `(grid_signature, best.oos_sharpe_bar)` per run and feed cumulative count as `n_trials`.

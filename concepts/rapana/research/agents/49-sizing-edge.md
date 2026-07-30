# 49 — Volatility-Targeting / Risk-Parity / Fractional-Kelly Sizing as the PRIMARY Profit-and-Survival Lever

**Agent:** 49/60 — Sizing-edge research
**Scope:** Whether *how much* to bet (volatility-targeted, risk-parity, fractional-Kelly position sizing) is a larger, more robust edge than *what* to bet on; an honest assessment of the repo's existing "volatility-targeted sizing" (commit `1458072`); and a concrete, MEXC-envelope-safe sizing layer (per-symbol vol target → portfolio vol target → de-risk-on-spike → fractional-Kelly on signal strength), daily-rebalanced, low-frequency, ToS-safe.
**Envelope:** spot-only, long-only, low-frequency (daily rebalance), deterministic-code-driven (LLM emits advisory `Signal`s only — `RESEARCH-SYNTHESIS.md:65`), no leverage, no shorts, respects the existing kill-switch / circuit-breaker / rate-limiter (`03-risk-edge.md`, `risk/guardrails.py`).
**TL;DR:** Per agent 40, practitioners attribute a **~4× Sharpe spread to universe + sizing, not signal cleverness.** The evidence supports this: vol-targeting **does not manufacture alpha** (Moreira & Muir 2017 *JFE*; the repo's own experiment was a WASH) but it **materially improves Sharpe and — more importantly — slashes drawdowns and tail losses** (Harvey et al. 2019 "crisis-proofing"), which for a retail spot fleet is usually the difference between compounding and ruin. **The repo's "volatility-targeted sizing" is mechanically true vol-targeting, but it is (1) single-symbol only, (2) absent from the live order path entirely, (3) silently clipped by `max_weight` at low vol, and (4) has no vol-spike de-risk rule.** The live fleet (`PortfolioManager.decide` + `PreTradeChecker`) sizes purely by **flat caps** (`risk_max_position_pct=0.10`, `risk_max_total_exposure_pct=0.50`), so a 50%-vol alt and 5%-vol BTC get the *same* max weight — a **10× risk concentration** that is the fleet's single most fixable structural weakness. The recommended sizing layer: **equal-risk-contribution per-symbol weights** (vol-parity) → **portfolio-level vol target** → **EWMA vol-spike circuit breaker** → **¼-Kelly cap on signal-driven size** → daily rebalance, gated by the existing Deflated-Sharpe walk-forward (`backtest/validation.py`).

---

## 1. The evidence — does vol-targeting improve Sharpe AND reduce drawdown in crypto?

### 1a. The canonical result: Moreira & Muir (2017), "Volatility-Managed Portfolios," *Journal of Financial Economics* 126(1):113–134
- **The headline:** Scaling exposure inversely to recent realized volatility (hold `1/σ²_realized` of the market) **does not raise average returns**, but it **raises the Sharpe ratio** by reducing variance more than it reduces return, and **dramatically reduces drawdowns** because it cuts exposure exactly in the high-vol regimes where crashes live.
- **The honest caveat (load-bearing):** Moreira & Muir themselves, and subsequent replications (**Cederburg, Drobetz & Liao**; **Collinet & Hou**), show the Sharpe gain is **modest and sample-fragile** — a large fraction of the published edge comes from the 1929–1939 / 2008 high-vol regimes, and the unconditional alpha is statistically marginal. **The robust, undisputed finding is the *risk* improvement, not the *return* improvement.**
- **Implication for rapana:** treat vol-targeting as a **risk/survival lever with a mild Sharpe kicker**, never as an alpha source. This is *exactly* what the repo's commit message concluded ("Useful as a risk knob, not an alpha source — consistent with the no-edge verdict") — the repo's null result is **consistent with the literature**, not a bug.
- Citation: Moreira, A. & Muir, T. (2017), *Volatility-Managed Portfolios*, **JFE** 126(1):113–134 — https://doi.org/10.1016/j.jfineco.2017.09.002 · working-paper landing: https://sites.google.com/site/amarissmoreira / SSRN "Volatility-Managed Portfolios"

### 1b. The survival case: Harvey, Hoyle, Rattray, Sargaison, Taylor & Van Oordt (2019), "…The Best of Strategies for the Worst of Times: Can Portfolios Be Crisis Proofed?" (SSRN 3468618; *Journal of Portfolio Management* 2019, 46(1))
- **The headline:** Volatility-scaling (and trend-following) **reduce maximum drawdown and tail loss across every major asset class**, including equity indices, bonds, commodities, and FX. The mechanism: scaling down when realized vol spikes **mechanically removes exposure before the worst of crashes** (volatility clusters, so high realized vol today forecasts high vol — and crashes — tomorrow).
- **Why this matters more than the Sharpe debate for a retail fleet:** the objective is **avoid ruin / avoid the devastating deep drawdowns** that force retail to sell at the bottom, not to maximise a marginal Sharpe. Harvey et al. show vol-targeting is one of the few interventions with a **consistent, cross-asset, crisis-tested** downside-protection record.
- **Crypto specificity:** crypto has the fattest tails and strongest vol-clustering of any asset class — exactly the regime where Harvey et al.'s de-risk mechanism pays off most. Cited across the crypto-vol literature (e.g., the Grobys 2021 t+5 vol-wave documented in `36-event-driven.md` is a direct instance: vol spikes precede the worst-of-the-move). Vol-targeting de-risks the book during precisely the hack/contagion windows where `36-event-driven.md` already calls for a hard veto.
- URL: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3468618 · published: https://doi.org/10.3905/jpm.2019.46.1.024

### 1c. Risk-parity / equal-risk-contribution — Maillard, Roncalli & Teiletche (2010), "On the Properties of Equally-Weighted Risk Contributions Portfolios," *Journal of Portfolio Management*
- **The headline:** allocating so each asset **contributes equal risk** (weight ∝ 1/σ, refined by covariance) produces a portfolio **close to the mean-variance efficient frontier** when assets have comparable Sharpe ratios — without forecasting returns. Risk-parity funds (Bridgewater *All Weather*, AQR) survived 2008 better than 60/40 precisely because they never let the single highest-vol sleeve dominate.
- **The crypto translation:** a long-only crypto book that **equalizes risk across symbols** (so a 50%-vol alt gets ~10× smaller weight than 5%-vol BTC) is the *minimal, free* version of this — it costs nothing, needs no return forecast, and structurally prevents the one-altcoin blow-up from sinking the book.
- **The honest caveat:** risk-parity is **fragile to correlation-regime shifts** (Wikipedia/Anderson-Bianchi-Goldberg; the COVID Q1-2020 sell-off hit risk-parity funds hard because correlations went to 1). For a single-venue spot book this is *less* severe (no leverage, no derivatives basis), but it means **vol-parity must be paired with a vol-spike de-risk** (§3c), not run bare.
- URL: https://doi.org/10.2139/ssrn.1271972 (open PDF: thierry-roncalli.com/download/erc.pdf)

### 1d. Fractional-Kelly — Thorp (1969); MacLean, Thorp & Ziemba (2010); Kelly (1956)
- **The headline:** the Kelly criterion maximises the long-run geometric growth rate; the continuous-asset form is **`f* = (μ − r) / σ²`** — i.e. **optimal weight ∝ expected excess return / variance**. This is *mathematically identical* to vol-targeting when the edge (μ−r) is held fixed: bet *less* when σ is high.
- **The practitioner consensus (Wikipedia "Kelly criterion" §Full/fractional Kelly, verified):** **full-Kelly is far too volatile** for real (non-known-probability) markets — huge drawdowns, parameter-estimation error explodes it. **Fractional Kelly (¼–½) is the universal practice** because it keeps ~75–94% of the growth rate while slashing variance and ruin probability, and is robust to estimation error in μ and σ.
- **Implication for rapana:** the `Signal.strength × Signal.confidence` product the PortfolioManager uses (`portfolio_manager.py:59`) is a *de facto* edge estimate; capping the signal-driven weight at a **fraction (¼–½) of the Kelly-implied f*** turns the noisy LLM confidence into a **survivable** bet size. This is the single cheapest survival upgrade in the fleet.
- URL: https://en.wikipedia.org/wiki/Kelly_criterion · Thorp, E.O. (1969), "Optimal Gambling Systems for Favorable Games," *Rev. IASI*

### 1e. Synthesis of the evidence
| Claim | Verdict | Source |
|---|---|---|
| Vol-targeting **raises returns** | **Weak / sample-fragile** — do NOT rely on this | Moreira-Muir 2017; Cederburg et al. |
| Vol-targeting **raises Sharpe** | **Modest but real** (reduce variance > reduce return) | Moreira-Muir 2017 |
| Vol-targeting **reduces drawdowns / crisis losses** | **Strong, cross-asset, crisis-tested** ⭐ | Harvey et al. 2019 |
| Risk-parity (equal-risk) needs no return forecast | **Yes** — near-efficient under equal-Sharpe | Maillard-Roncalli-Teiletche 2010 |
| Risk-parity is correlation-regime-fragile | **Yes** — pair with vol-spike de-risk | Anderson-Bianchi-Goldberg 2012 |
| Full-Kelly is too volatile for real markets | **Yes** — use ¼–½ Kelly universally | Thorp; MacLean-Thorp-Ziemba |
| **Sizing is a bigger, more robust edge than signal cleverness** | **Yes** — the 4×-Sharpe-spread claim (agent 40) is supported | Harvey et al.; Moreira-Muir |

---

## 2. Honest assessment of the repo's current sizing (commit `1458072`)

### 2a. What it is
The commit adds an **optional, backtest-only** vol-targeting multiplier to `rapana/backtest/engine.py:143-155`:

```python
@staticmethod
def _vol_scale(history, cfg) -> float:
    if cfg.vol_target is None or not finite or <= 0: return 1.0
    rets = history["close"].pct_change().tail(cfg.vol_lookback).dropna()   # 20-bar realized vol
    rv = rets.std()
    annual_vol = rv * sqrt(BARS_PER_YEAR[timeframe])
    return cfg.vol_target / annual_vol                                     # scalar multiplier
```
…then `_target_value` sets `weight = clamp(base * vol_scale, 0, max_weight)` where `base = |strength| * confidence` (`engine.py:167-171`). Default `vol_target=None` (OFF). CLI exposes `--vol-target` on `validate` / `validate-universe`.

### 2b. Is it *true* vol-targeting or just a cap?
**Mechanically, yes — it is true vol-targeting.** It computes realized vol, annualizes it, and scales the position *inversely* to keep `position_vol ≈ vol_target`. That is exactly the Moreira-Muir mechanism, implemented lookahead-free (only `history[:i]`), with correct defensive guards (None/NaN/≤0 → off; long-only clamp; regression tests). **This is a correct, minimal, honest piece of work.**

### 2c. The five material gaps (why it is, in practice, only a partial risk knob)

1. **🔴 It is NOT in the live order path.** The live fleet sizes in `PortfolioManager.decide` (`agents/portfolio_manager.py:58-60`) as `weight = min(max_weight, abs(net))` and the `PreTradeChecker` (`risk/guardrails.py:189-233`) enforces purely **flat caps**: `risk_max_position_pct=0.10` per symbol, `risk_max_total_exposure_pct=0.50` portfolio (`config.py:57-59`). **The vol-target lives only in `backtest/engine.py` and is OFF by default** — live trading would never use it. This is the largest gap: the fleet's *actual* sizing ignores volatility entirely.

2. **🔴 Single-symbol scalar — no cross-symbol risk-parity.** `BacktestEngine.run` processes one symbol at a time; there is no portfolio layer that equalizes risk *across* symbols. Consequence: at the live caps, a **50%-vol alt and 5%-vol BTC each receive up to 10% of equity** → the alt contributes **~10× the risk** of BTC. This is the fleet's single most fixable structural concentration. (The `risk_max_total_exposure_pct=0.50` cap limits the *sum* but not the *risk distribution* — 50% in one 50%-vol coin is still a blow-up waiting to happen.)

3. **🟠 The `min(max_weight, …)` clamp silently breaks the target at low vol.** When realized vol drops, `vol_target / annual_vol` rises and is clipped to `max_weight=0.95` (`engine.py:170`). So in calm markets the position is **NOT at target vol** — it is at the cap. This makes the feature a **cap masquerading as a target on the upside**, which *flattens* the very "calm markets → more exposure" effect vol-targeting is supposed to deliver (and may explain the WASH result — the target was inactive precisely when it should help most). Fix: lower the target so the clamp binds rarely, or let the cap float up in calm regimes within an absolute hard limit.

4. **🟠 No vol-spike de-risk / circuit breaker.** `_vol_scale` reacts smoothly to a 20-bar realized-vol estimate with **no fast EWMA and no threshold trigger**. Crypto vol spikes faster than 20-bar realized vol reacts (a flash-crash can move vol 5× inside the lookback window before the slow MA catches up). Harvey et al.'s crisis-proofing benefit comes from **fast** vol-scaling + a hard cut on extreme vol — neither is present.

5. **🟡 20-bar simple std is reactive, not predictive.** No EWMA, no GARCH, no jump detection. And the commit honestly reports a **WASH** (Sharpe ~0.95 → 0.88 at aggressive sizing). This is consistent with §1a: a single-symbol scalar vol-target on an already-weak signal rarely adds alpha. **Not a bug — a faithful reproduction of a fragile literature result.**

### 2d. Net verdict on the existing code
A correct, honest, minimal vol-targeting *primitive* — but **a primitive, not a sizing layer**. It is OFF by default, backtest-only, single-symbol, no de-risk rule, and clipped at low vol. The fleet's *actual* sizing is flat caps with zero vol-awareness. **There is no risk-parity anywhere in the codebase.** This is the gap this agent recommends closing.

---

## 3. Robust sizing-layer design (the deliverable)

A four-stage, layered sizing function that runs in **deterministic code** (never the LLM), **once per day**, *after* the analyst consensus produces a `Signal` per symbol and *before* the `PreTradeChecker` flat caps. Each stage is independently switchable and must clear the §4 validation gate before live promotion.

### 3a. Stage 1 — Per-symbol **vol-parity** weight (equal risk contribution)
Goal: a 5%-vol asset and a 50%-vol asset contribute **equal risk** to the book.

```
For each candidate symbol i with bullish Signal:
    σ_i = EWMA(log_returns_i, span=ewma_span)          # e.g. span=32 (≈ EWMA of ~32 daily bars)
    w_volparity_i = (1/σ_i) / Σ_j(1/σ_j)               # inverse-vol weights, sum to 1
    target_risk_i = portfolio_risk_budget / N_candidates (equal risk per name)  [HYPOTHESIS]
    w_i = w_volparity_i * gross_leverage                # gross_leverage ≤ 1 (spot, no leverage)
```
- This is the **single highest-value change in this doc**: it costs nothing, needs no return forecast, uses data already in the store (`store.py` candles), and **structurally prevents the one-altcoin blow-up from sinking the book**.
- Refinement (optional, when a covariance estimate is stable): replace `1/σ_i` with the Maillard-Roncalli-Teiletche **equal-risk-contribution** solution `w_i ∝ σ(w)² / (Σw)_i` (Wikipedia "Risk parity" §ERC, verified). For ≤10 symbols this is a small convex problem. Start with naive inverse-vol (robust, no covariance needed) and upgrade to ERC only if it clears the §4 gate.
- **Caps preserved:** `w_i` is still bounded by `max_position_pct` (per-symbol) and the sum by `max_total_exposure_pct` (portfolio). Vol-parity *distributes* within those caps; it does not override them.

### 3b. Stage 2 — **Portfolio-level vol target** (the Moreira-Muir knob, done right)
Goal: scale the *whole* book up in calm regimes, down in turbulent ones — the knob the repo already half-built.

```
σ_portfolio_realized = EWMA of portfolio equity returns (span=ewma_span)
portfolio_scale = clamp( σ_portfolio_target / σ_portfolio_realized , 0, portfolio_scale_max )
w_i *= portfolio_scale                                  # de-risks the entire sleeve together
```
- **Fix the repo's low-vol clip bug:** choose `σ_portfolio_target` and `portfolio_scale_max` so the clamp binds **rarely** (e.g. target 25% annualized, max scale 2.0, with an absolute hard cap of `max_total_exposure_pct=0.50`). This keeps the target *active* in calm markets — the regime where the repo's current implementation was silently dead.
- `σ_portfolio_target` is the **one parameter to tune** in walk-forward (§4). Literature range: 10–30% annualized for a spot crypto book. **Lower = more conservative = better for retail survival.**

### 3c. Stage 3 — **Vol-spike de-risk** (the Harvey et al. crisis-proofer)
Goal: cut exposure *fast* when vol blows out — the one feature the repo entirely lacks.

```
σ_fast  = EWMA(returns, span=8)        # reactive
σ_slow  = EWMA(returns, span=63)       # baseline
ratio   = σ_fast / σ_slow
if ratio > spike_killer_threshold (e.g. 2.5×):     # vol has roughly tripled
    w_i *= spike_killer_fraction (e.g. 0.25)       # cut to 25% immediately
    set cooldown_until = now + cooldown_bars (e.g. 24 bars / 1 day)
    (also surfaces as the same `event_veto_until` flag `36-event-driven.md` consumes)
```
- This is the **load-bearing survival rule.** It converts the Harvey et al. evidence into one deterministic line: when vol spikes, shrink. It overlaps with `36-event-driven.md`'s systemic-hack de-risk (a hack *is* a vol spike) — route both through the same `event_veto_until` / `kill_switch` plumbing so they reinforce, not double-fire.
- Tunable, must be **gated** (§4): too sensitive → whipsaw out of rebounds; too slow → miss the crash. The literature suggests a ~2–3× ratio threshold on an 8-vs-63 EWMA pair is a reasonable starting point. **[HYPOTHESIS]**

### 3d. Stage 4 — **Fractional-Kelly cap on signal strength** (bet sizing sanity)
Goal: don't let a confident-but-wrong LLM signal bet the farm.

```
For each symbol, the analyst consensus gives an edge estimate e_i ∈ [-1, 1] (the weighted-combine `net`).
Kelly-implied weight: f_kelly_i = e_i / σ_i²           # continuous Kelly; ∝ edge/variance
fractional Kelly:     w_i = min( w_i_from_stages_1-3, kelly_fraction * f_kelly_i )
                     with kelly_fraction ∈ [0.25, 0.50]   # ¼–½ Kelly (universal practitioner norm)
```
- This **replaces** the current `weight = min(max_weight, abs(net))` (`portfolio_manager.py:59`) with a Kelly-consistent bound. A ¼-Kelly cap keeps ~75–94% of the geometric growth rate while **bounding the worst-case single-bet loss** — exactly the robustness MacLean-Thorp-Ziemba prescribe for markets where the edge estimate (here: an LLM confidence) is noisy.
- **Keep it fractional, never full.** Full-Kelly on a noisy edge estimate is the classic retail ruin path.

### 3e. Rebalance cadence & envelope safety
- **Daily rebalance** (once per UTC day, aligned with `20-utc-flows.md`'s cycle), **not per bar.** This keeps order count low (maker-fee-friendly, `09-mexc-maker-fee.md`), ToS-safe (no churn/velocity flags, `16-mexc-tos-envelope.md`), and avoids the whipsaw that intraday vol-scaling induces on a noisy signal.
- **Deterministic code only.** The sizing function is pure math on stored candles; the LLM never touches it (same fence as the rest of the fleet, `RESEARCH-SYNTHESIS.md:65`).
- **All existing vetoes still bind:** kill-switch (`guardrails.py:104`), daily-loss circuit-breaker (`risk_max_daily_loss_pct=0.03`, `guardrails.py:129`), rate-limiter (`guardrails.py:65`), sanity price-band (`guardrails.py:206`), staged capital 1%→5%→25%→100% (`fleet/capital.py`). The sizing layer sits *above* the flat caps in the per-symbol direction but the flat caps remain the **final hard floor**.

### 3f. Where it lives in the code (minimal-touch integration)
- New module `rapana/risk/sizing.py` exposing `size_portfolio(signals, store, equity, config) -> dict[symbol, weight]` implementing stages 1–4.
- `PortfolioManager.decide` calls it once per decision cycle to get the per-symbol target weight, then emits `TradeProposal`s as today; `PreTradeChecker.check` is unchanged (flat caps still final).
- `BacktestEngine` gets a portfolio-mode path (or a new `PortfolioBacktestEngine`) that calls the same `size_portfolio` so **backtest sizing == live sizing** (the current split, where the backtest has vol-target and live does not, is itself a look-ahead-style risk).
- New `Settings` fields: `sizing_vol_target`, `sizing_ewma_span`, `sizing_spike_ratio`, `sizing_spike_fraction`, `sizing_kelly_fraction`, `sizing_enabled` (default **False** → opt-in, all prior verdicts unchanged).

---

## 4. Validation gate (mandatory before any live sizing) — reuse the existing machinery

This is **not** a new gate; it is the repo's existing Deflated-Sharpe walk-forward (`backtest/validation.py`, commit `9a6fbf9`) applied to the sizing layer.

1. **Walk-forward, locked holdout:** re-run `validate`/`validate-universe` with `--vol-target` and the new portfolio-sizing engine over the same PIT store (`universe/validation.py`). Require the sized book to beat **both** (a) the current flat-cap book and (b) equal-weight HODL **after fees** on the **locked holdout** (`validation.py` holdout, `--holdout > 0`).
2. **Deflated Sharpe:** because the sizing layer introduces several tunables (`σ_target`, `ewma_span`, `spike_ratio`, `kelly_fraction`), the multiple-testing penalty is real — the `deflated_best` / `is_significant` verdict (`backtest/validation.py`) must pass *after* accounting for the grid searched.
3. **Drawdown gate (the primary metric for this work):** require **max drawdown of the sized book ≤ 0.7× the flat-cap book's max DD** on the holdout. This is the Harvey et al. promise — if vol-targeting can't deliver *drawdown* reduction OOS, it has no business going live, regardless of Sharpe.
4. **Staged live promotion:** even after the gate passes, deploy under the existing `StagedCapital` ladder (1% → 5% → 25% → 100%, `fleet/capital.py`) with human approval at each step (`03-risk-edge.md`).

---

## 5. The honest verdict (what sizing can and cannot do)

- **Sizing cannot manufacture alpha.** The repo's own WASH result faithfully reproduces the Moreira-Muir / Cederburg finding: a vol-target on an already-weak signal adds no return. Anyone expecting the sizing layer to turn the fleet profitable will be disappointed — that is `01-strategy-edge.md`'s and `06-universe-edge.md`'s job.
- **Sizing materially improves Sharpe** (reduce variance > reduce return) and **dramatically reduces drawdowns and tail losses** — the latter being the robust, crisis-tested, cross-asset result (Harvey et al. 2019). For a **retail spot fleet**, drawdown reduction is the survival primitive: the deep drawdown is what forces a human to sell at the bottom, and what turns a temporary paper loss into a permanent realized one.
- **The fleet's single most fixable structural weakness is the flat per-symbol cap with no vol-awareness** (`risk_max_position_pct=0.10` applied identically to a 5%-vol and a 50%-vol asset). Closing it costs nothing, needs no new data, and is the concrete embodiment of agent 40's "sizing is the real edge" claim.
- **The right framing:** the sizing layer is **insurance plus a mild Sharpe kicker**, not a signal. Ship Stage 1 (vol-parity) + Stage 3 (vol-spike de-risk) first — they are the highest-value, lowest-risk pieces and directly target blow-up prevention. Add Stages 2 and 4 only if the §4 drawdown gate passes on the locked holdout.

---

## 6. References (with URLs)

- **Moreira, A. & Muir, T. (2017)**, *Volatility-Managed Portfolios*, **JFE** 126(1):113–134 — https://doi.org/10.1016/j.jfineco.2017.09.002 · (the canonical vol-managed-portfolios paper; headline: no return gain, modest Sharpe gain, large drawdown reduction)
- **Harvey, Hoyle, Rattray, Sargaison, Taylor & Van Oordt (2019)**, *The Best of Strategies for the Worst of Times: Can Portfolios Be Crisis Proofed?*, **Journal of Portfolio Management** 46(1) / SSRN 3468618 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3468618 · https://doi.org/10.3905/jpm.2019.46.1.024 (cross-asset evidence that vol-scaling + trend cut drawdowns/tail risk)
- **Maillard, Roncalli & Teiletche (2010)**, *On the Properties of Equally-Weighted Risk Contributions Portfolios*, **JPM** — https://doi.org/10.2139/ssrn.1271972 · open PDF: http://www.thierry-roncalli.com/download/erc.pdf (the ERC/risk-parity construction)
- **Anderson, Bianchi & Goldberg (2012)**, *Will My Risk Parity Strategy Outperform?*, **FAJ** 68(6):75–93 — https://doi.org/10.2469/faj.v68.n6.7 (risk-parity correlation-regime fragility; the Q1-2020 critique)
- **Thorp, E.O. (1969)**, *Optimal Gambling Systems for Favorable Games*, **Rev. IASI**; **MacLean, Thorp & Ziemba (2010)**, *The Kelly Capital Growth Investment Criterion* — https://en.wikipedia.org/wiki/Kelly_criterion (fractional-Kelly survival; `f* = (μ−r)/σ²`)
- **Cederburg, Drobetz & Liao (2020)** and **Collinet & Hou**, OOS-robustness challenges to Moreira-Muir (vol-managed portfolios fragility) — cite via Moreira-Muir replication literature
- **Repo internals:** `backtest/engine.py:143-171` (the current vol-scale + clamp), `agents/portfolio_manager.py:58-60` (live flat-cap sizing), `risk/guardrails.py:189-233` (PreTradeChecker flat caps), `config.py:57-59` (flat risk caps), `fleet/capital.py` (staged capital), `backtest/validation.py` (Deflated-Sharpe walk-forward gate), commit `1458072` (the vol-targeted-sizing experiment)
- **Cross-refs:** `03-risk-edge.md` (risk caps / circuit breakers), `06-universe-edge.md` + `34-cross-sectional-factors.md` (the *signal/universe* half of the 4× Sharpe spread; sizing is the other half), `07-profit-benchmark.md` (the benchmark sizing must beat), `16-mexc-tos-envelope.md` (daily-rebalance cadence = ToS-safe), `36-event-driven.md` (vol-spike de-risk overlaps the systemic-hack veto)

---

**One-line summary for the synthesis:** Vol-targeting/risk-parity/fractional-Kelly **cannot manufacture alpha** (the repo's own WASH faithfully reproduces Moreira-Muir 2017), but it **materially improves Sharpe and — critically — slashes drawdowns** (Harvey et al. 2019, cross-asset crisis-tested); the repo's `1458072` vol-target is a correct but **backtest-only, single-symbol, low-vol-clipped, no-de-risk primitive** while the **live path sizes purely by flat caps** (`risk_max_position_pct=0.10`) so a 5%-vol and 50%-vol asset share the same max weight — the fleet's single most fixable weakness; ship a four-stage daily-rebalance sizing layer (per-symbol vol-parity → portfolio vol target → EWMA vol-spike de-risk → ¼-Kelly cap on signal), gated by the existing Deflated-Sharpe walk-forward **plus a max-DD ≤ 0.7× drawdown gate** on the locked holdout.

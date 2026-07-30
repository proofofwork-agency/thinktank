# 54 — Volatility-regime signals: RV/IV, variance risk premium, vol term structure, vol-of-vol as a regime / risk overlay

**Agent:** 54/60 — Vol-regime research
**Scope:** Whether **option-implied volatility** (Deribit DVOL, ATM IV), the **crypto variance risk premium** (IV − RV), the **vol term structure** (near vs far IV), and **vol-of-vol** (the volatility of implied vol) carry regime / risk-off information that Rapana can use as an **exposure scalar + defensive trigger** on MEXC spot. The fleet never trades options — Deribit is read **read-only/public**, exactly as `research/agents/23-expiry-maxpain.md` already prescribes for the expiry overlay.
**Envelope:** spot-only, long-only, low-frequency (**daily** evaluation per the brief, but information-rate-honest — see §e), no arbitrage, no options leg, no hedging. This is a **regime/risk overlay**, not a directional alpha. Same ToS discipline as `research/agents/16-mexc-tos-envelope.md`.
**TL;DR:** The crypto **variance risk premium is real, large, and regime-varying** — Bitcoin's VRP is **bigger than the S&P 500's** (Almeida et al. 2024), and it is **structurally positive (IV > RV) on average** (Alexander–Imeraj 2020; Carr–Wu 2009 generalized to BTC). The actionable signals are **(a)** a **spike / inversion** of the term structure = the market is pricing an imminent vol shock → **defensive / risk-off trigger** (highest confidence); **(b)** a **compressed VRP + contango + low vol-of-vol** = the calm regime where carry/momentum edges work best → **risk-on conviction modifier** (second-highest); **(c)** IV as a **predictor of subsequent realized vol** (Hoang–Baur 2020) → use it as a **position-size scalar**, not a return call. The honest caveat: vol-regime signals are **noisy** and crypto IV is **term-structure-thin** (only since ~2017 for DVOL). Use it as a **conviction modifier + hard risk-off trigger**, never a primary driver. All inputs are **free** (Deribit public API, CoinGlass, Laevitas).

---

## (a) The crypto variance risk premium — does IV exceed RV, and what does its compression/expansion signal?

### (a.1) The mechanic and the stylized fact
The **variance risk premium (VRP)** is the gap between **option-implied variance** (the market's *expectation* of future vol, extracted from option prices) and **subsequently realized variance**. It is the **insurance premium** option buyers pay to sellers for bearing variance risk: on average, the variance-swap strike (≈ IV²) **exceeds** realized variance (RV²), so the *seller* of variance profits and the *buyer* loses on most trades (Wikipedia, "Variance risk premium"; Carr & Wu 2009, *Review of Financial Studies* 22(3):1311 — the foundational cross-asset result). In equity indices this is a **structural, persistent** anomaly: CAPM/Fama-French cannot explain it, which is why variance is treated as an asset class in its own right.

**This generalizes to crypto and is, if anything, stronger.** Three directly-on-point sources:

1. **Alexander C. & Imeraj A. (2020), "The bitcoin VIX and its variance risk premium,"** *Journal of Alternative Investments* 23(2) — introduces the **BVIX** (a VIX-methodology Bitcoin implied-vol index from Deribit options) and documents a **positive, time-varying Bitcoin VRP**. This is the canonical "BTC has a variance risk premium" paper. SSRN 3383734.
2. **Almeida, Grith, Miftachov & Wang (2024), "Risk Premia in the Bitcoin Market,"** arXiv:2410.15195 (https://arxiv.org/abs/2410.15195) — the load-bearing recent result. Headline: **"Bitcoin is much more volatile and has a higher variance risk premium than the S&P 500."** Crucially, they decompose the VRP across **two distinct volatility regimes** via a clustering algorithm on option-implied densities:
   - **Low-volatility regime:** a **relatively high** share of the Bitcoin Premium comes from *positive* returns, and the **BVRP is high** (IV far above RV — investors pay up for variance insurance when the market feels calm-but-uncertain).
   - **High-volatility regime:** the premium from positive vs negative returns **balances out**, and the **BVRP is lower** (IV has already caught up to RV; the insurance is no longer cheap).
   - This is the single most important finding for an overlay: **the VRP is not a constant — it is a regime indicator.** Its *level* tells you which regime you are in.
3. **Borri N., Massacci D., Rubin M. et al. (2022), "Crypto risk premia,"** SSRN 4154627 — confirms IV-implied risk premia are **priced and carry predictability** in crypto cross-sectionally (cited 44×), separate from market/size/momentum factors.

### (a.2) What compression vs expansion signals — the actionable read
Translating the regime result into a signal:

| VRP state | What it means | Overlay action |
|---|---|---|
| **VRP compressed** (IV − RV → 0, or **negative**) | Option market no longer charging a premium for variance; sellers unwilling; **IV has caught up to or overshot realized** | **Defensive.** The "insurance is mispriced" regime — historically associated with **imminent or in-progress vol shocks**. Tighten size; this is the **risk-off trigger** (§d). |
| **VRP normal/rich** (IV − RV at typical positive spread) | The standard state; insurance fairly priced | **Neutral / mild risk-on.** Let other signals drive direction; vol-regime contributes only a size scalar. |
| **VRP very rich** (IV − RV unusually wide, in a calm tape) | The Almeida low-vol regime: investors paying up despite quiet spot | **Risk-on conviction modifier.** This is the regime where carry/momentum edges (the Scout, `research/agents/06-universe-edge.md`; funding fade, `research/agents/12-mexc-funding.md`) historically work best — **tilt size up, do not flip direction.** |

**Caveat (be explicit):** a *negative* VRP (RV > IV) in crypto is **rare and violent** — it marks crises (Mar-2020 COVID, May-2022 Terra, Nov-2022 FTX). It is an excellent **hindsight risk-off marker** but a **noisy real-time one**: by the time VRP goes negative, spot has usually already moved. Use it as a **fast de-risk confirmation**, not a predictor. Section (e) returns to this honestly.

---

## (b) Does an implied-vol spike predict subsequent realized moves — or mean-reversion?

### (b.1) IV as a predictor of *realized vol* (not returns) — yes, this holds
**Hoang L.T. & Baur D.G. (2020), "Forecasting bitcoin volatility: Evidence from the options market,"** *Journal of Futures Markets* 40(3) — the most directly on-point test (https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.22144, cited 39×). Uses Deribit BTC option trades to construct implied volatility and tests whether it forecasts subsequent BTC volatility.

- **Finding: IV contains information about future realized vol** beyond what historical/RV models deliver — i.e. the option market is a genuine, additive forecaster of *volatility* (not of *direction*).
- This is the cleanest single justification for using IV as a **position-size / risk scalar**: when IV is high, **scale down** (the forward move distribution is wider); when IV is low, the size budget can be fuller.
- It does **not** say IV predicts the *sign* of returns — a common retail misread. IV-high → "expect a big move of unknown sign," not "expect a down move."

### (b.2) IV spike → mean reversion vs continuation (the honest split)
Crypto-implied vol is **GARCH-like mean-reverting**: DVOL spikes (to 100%+ in crises, vs a ~50–70% long-run average) tend to **revert**, while spot direction during the spike is **roughly a coin flip** (Hoang–Baur 2020; corroborated by the symmetric positive/negative-return split in Almeida et al.'s high-vol regime). The implication for a long-only spot fleet:

- **Do not** trade "fade the IV spike" as a directional spot bet — that is a *short-vol* trade and we cannot short vol on MEXC spot anyway.
- **Do** use the IV spike as a **"stand down / cut size" trigger** — this is the robust, evidence-backed use. A DVOL spike is a reliable signal that the *next* 1–3 days will be noisier and more whipsaw-prone; the right response is **smaller size and wider patience**, not a directional bet. This mirrors the expiry-week veto logic in `research/agents/23-expiry-maxpain.md` (the Blasco 2022 "witching week" result), generalized from a calendar event to a vol-regime state.

### (b.3) Vol-regime as risk-on / risk-off — the cross-asset analog
In equities, **VIX-regime** is the textbook risk-on/off overlay: VIX < 20 → risk-on (size up, tilt offensive); VIX > 30 → risk-off (de-risk, defensive). The crypto analog is **DVOL-regime**, with **shifted thresholds** (crypto IV is structurally ~3–5× equity IV):

| DVOL (BTC, 30d) | Regime label | Overlay lean |
|---|---|---|
| **< 45%** | **Compressed / calm** | Risk-on conviction modifier — tilt size up within `risk_max_position_pct` (`config.py:57`) |
| **45–75%** | **Normal** | Neutral — let other signals decide; vol-regime is a no-op on direction |
| **75–100%** | **Elevated** | Mild defensive — trim new-entry size to ~50% of target |
| **> 100%** (or 2σ above 90d mean) | **Vol-shock** | **Risk-off trigger** — block new directional entries; tighten existing stops |

These thresholds are **priors, not fitted values** — they must be calibrated against the 2017–2026 DVOL history Deribit publishes for free (§c). Mark them `[HYPOTHESIS → backtest]` until a walk-backtest clears the `deflated_best` / `dsr > 0.95` gate (`backtest/validation.py:122,249`; same gate the funding fade clears at `backtest/funding_spike.py:370`).

---

## (c) Free data — the full vol-regime stack, no key, no KYB

Every input the overlay needs is **public and free**, mirroring the funding-rate pipeline (`research/agents/12-mexc-funding.md`) and the expiry overlay (`research/agents/23-expiry-maxpain.md`). No Deribit account, no paid volatility data vendor required.

### (c.1) Deribit public API (read-only, `Public`-tagged — no auth)
Verified against `docs.deribit.com` (fetched 2026-06-23):

| Endpoint | Returns | Vol-regime use |
|---|---|---|
| `public/get_volatility_index_data?currency=BTC&resolution=1D` | **DVOL** OHLC candles (timestamp, open, high, low, close) — the BTC/ETH 30d implied-vol index, VIX-methodology (https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data) | **Primary IV input** — daily DVOL close is the 30d IV proxy; history for thresholds + vol-of-vol |
| `public/get_book_summary_by_currency?currency=BTC&kind=option` | per-instrument `mark_iv`, `underlying_price`, `mid_price`, `open_interest`, `instrument_name` (encodes expiry + strike, e.g. `BTC-28MAR26-100000-C`) (https://docs.deribit.com/api-reference/market-data/public-get_book_summary_by_currency) | **Term structure + ATM IV**: group by expiry → fit the IV term-structure curve; nearest/farthest liquid expiry → contango vs inversion; per-strike IV → smile/skew (optional, vol-of-vol proxy) |
| `public/get_expirations?currency=BTC&kind=option` | expiry timestamps | Term-structure tenor anchors (7d / 30d / 60d / 90d / quarterly) |
| `public/get_index_price?index_name=btc_usd` | Deribit BTC index | RV computation anchor (cross-check against MEXC spot) |

**Local computations (all deterministic, free, point-in-time auditable):**

```
# DVOL (IV, 30d) — fetched directly, no computation
iv_30d = dvol_close

# Realized vol (RV, 30d) — from spot closes (CoinGecko or MEXC)
log_returns = diff(log(spot_closes[-31:]))
rv_30d = stdev(log_returns) * sqrt(365)          # crypto = 365, not 252

# Variance risk premium (in vol points)
vrp = iv_30d - rv_30d                              # +ve = normal; compression → risk-off

# Term-structure slope — from book_summary mark_iv grouped by expiry
iv_near = atm_iv(expiry ≈ 7d out)
iv_far  = atm_iv(expiry ≈ 60–90d out)
ts_slope = iv_near - iv_far                         # +ve = INVERTED (risk-off); -ve = contango (risk-on)

# Vol-of-vol — the realized vol of implied vol (regime stability proxy)
vol_of_vol = stdev(dvol_closes[-30:]) / mean(dvol_closes[-30:])
```

### (c.2) Aggregators (free, no key) — for cross-checking the local compute
- **CoinGlass** — free Deribit DVOL, ATM IV term structure, option OI, max-pain per expiry. https://www.coinglass.com/ (search "DVOL" / "Bitcoin IV"). Useful as a sanity check on the local DVOL fetch and term-structure fit; **do not** make it the only source — the local point-in-time compute is what the audit trail needs.
- **Laevitas** — Deribit options analytics, DVOL history, vol surface, term structure, skew. https://laevitas.ch/ (free tier).
- **datamish / Tardis** — secondary DVOL / IV history cross-checks.

### (c.3) RV computation — reuse what the fleet already fetches
Realized vol needs only **daily spot closes**, which the fleet already pulls for the Scout (`rapana/universe/scout.py`) and the market-premium feed (`rapana/feeds/market_premium.py:12-17` maps the same CoinGecko free endpoint). No new data dependency for the RV leg — the only *new* fetch is DVOL + option book summary from Deribit, both free public endpoints.

### (c.4) What is NOT needed (and what we explicitly do not touch)
- **No Deribit trading key** — read-only public market data suffices for every metric in this note.
- **No options leg, no variance swap, no short-vol trade** — the overlay only *reads* IV and emits a size/regime *Signal* consumed by the Portfolio/Risk Managers. The only execution leg is a single slow maker MEXC spot order, ToS-clean by construction (same single-leg discipline as `research/agents/18-mexc-premium.md`).

---

## (d) Design — `VolRegimeAnalyst`

### (d.1) The composite regime label (three inputs, one state)
The overlay fuses three vol-regime inputs into a single state, evaluated **daily** (per the brief) but **smoothed** to avoid daily churn:

| Input | Source (free) | What it measures | Lookback |
|---|---|---|---|
| **Variance risk premium** (IV − RV) | DVOL (`get_volatility_index_data`) − computed RV | Insurance premium the option market charges | daily, 30d RV |
| **Term-structure slope** (near − far IV) | `get_book_summary_by_currency` ATM IV by expiry | Near-term fear vs long-term calm | spot slopes, daily |
| **Vol-of-vol** + DVOL level | DVOL 30d history | Regime stability + absolute vol state | 30d rolling |

The three are **deliberately redundant** — they all measure aspects of the same vol regime. A robust overlay should **agree across inputs** before it flips to the defensive state (single-input flips are noise; see §e).

### (d.2) Regime states → exposure scalar + de-risk flag
The composite maps to a **discrete regime** with a corresponding **exposure scalar** (applied to the Portfolio Manager's target weights) and a **hard de-risk flag** (consumed by the Risk Manager veto path, same as `research/agents/43-llm-risk-veto.md` and the `de_risk` flag in `research/agents/57-cross-asset-regime.md`):

| Regime | Trigger (composite, daily) | Exposure scalar | De-risk flag |
|---|---|---|---|
| **VOL-SHOCK (defensive)** | DVOL > 100% **OR** (term structure **inverted** AND VRP **compressed** < 25th pctile of 1yr) **OR** vol-of-vol > 2σ above 90d mean | **0.50** (halve target size) | **ON** — block new directional entries; tighten stops |
| **ELEVATED** | DVOL 75–100% **OR** (inverted TS **xor** compressed VRP) | **0.75** | off |
| **NORMAL** | DVOL 45–75%; TS contango or flat; VRP in 25–75th pctile | **1.00** | off |
| **COMPRESSED / RISK-ON** | DVOL < 45% **AND** TS contango **AND** VRP rich (> 75th pctile) **AND** vol-of-vol < 1σ below 90d mean | **1.25** (cap at fleet max exposure) | off |

**Key design choices:**
- **The de-risk flag is the primary value.** The exposure scalar is a mild, daily reweighting; the **hard risk-off trigger** (vol-shock: inverted TS + compressed VRP, or DVOL > 100%) is where the overlay actually protects capital. This mirrors the repo's existing risk-veto philosophy (`research/agents/43-llm-risk-veto.md`, RiskManager role in `PLAN.md`).
- **No regime goes below 0.50 or above 1.25 unfiltered** — this is a long-only spot fleet; the overlay is a *scalar*, never an all-in/all-out switch. The absolute floor/ceiling stays with the Risk Manager (`rapana/agents/risk_manager.py`) and `risk_max_position_pct` (`config.py:57`).
- **Composite agreement:** the vol-shock trigger requires *either* an extreme DVOL (> 100%) *or* two-of-three structural inputs agreeing (inverted TS **and** compressed VRP). A single noisy input cannot flip the regime alone.
- **[HYPOTHESIS → backtest]:** the DVOL thresholds (45/75/100), the VRP percentile bands (25/75), and the scalar magnitudes (0.50/0.75/1.00/1.25) are **priors**, not fitted values. They must be calibrated against 2017–2026 DVOL history and pass the `deflated_best` / `dsr > 0.95` gate (`backtest/validation.py:122,249`), the same gate the funding fade clears (`backtest/funding_spike.py:370`). **Ship the de-risk flag first; add the scalar second.**

### (d.3) Why daily (with smoothing), not intraday
1. **Information rate:** DVOL is a 30d expectation; daily changes beyond a few vol-points are noise. Evaluate daily, but only **act** on the regime when it has been stable for ≥ 2 consecutive days (avoid whipsaw).
2. **Envelope:** MEXC spot-only, low-freq (`research/agents/16-mexc-tos-envelope.md`); daily regime evaluation + multi-day hysteresis stays inside the maker-fee / anti-bot policy envelope.
3. **Cost:** a daily-regime scalar is **low-turnover** by construction — the regime changes ~10–20 times a year, not daily, with hysteresis.

---

## (e) Honest gating — what this overlay is and is not

### What it IS
- A **regime classifier** grounded in a documented structural anomaly (positive, regime-varying crypto VRP — Almeida et al. 2024; Alexander–Imeraj 2020).
- A **predictor of realized vol** (Hoang–Baur 2020) → use as a **size scalar**, the highest-confidence use.
- A **de-risk trigger** (inverted TS + compressed VRP, or DVOL spike) — the second-highest-confidence use.
- A **risk-on conviction modifier** (compressed DVOL + contango + rich VRP) — the speculative use; requires backtest.
- **Free** — every input is available without a paid API or a Deribit account.

### What it is NOT (be explicit, do not overclaim)
1. **Not a directional / return-alpha.** IV predicts the *magnitude* of subsequent moves, not their *sign* (Hoang–Baur 2020). Trading "DVOL high → short" or "DVOL low → long" is a short-vol / long-vol trade that **cannot be replicated on MEXC spot** and would not survive costs anyway. The overlay only sizes and de-risks; it never sets direction.
2. **Not a precise vol-shock timer.** By the time VRP goes negative or TS inverts hard, spot has often already moved. The overlay is a **fast confirmation + regime label**, not a crystal ball. Expect the defensive trigger to fire *during* the first leg of a shock, not before.
3. **Not independent of the cross-asset regime overlay.** Vol-shock regimes almost always coincide with the `risk_off` / `converged` state from `research/agents/57-cross-asset-regime.md` (alt↔BTC ρ > 0.8). The two are **redundant by design** — when both agree, conviction in de-risking is high; when they disagree, treat the vol signal as the faster of the two.
4. **Term-structure-thin history.** DVOL has published history only since ~late 2017 / early 2018; pre-2017 crypto IV must be reconstructed (Alexander–Imeraj 2020 do this). Treat any backtested threshold magnitude as a **directional** estimate spanning ~2 cycles, not a precise number.
5. **Vol-of-vol is the noisiest input.** Rolling stdev of DVOL is unstable at 30d; prefer a 60–90d window and require a 2σ breach before letting it contribute to the vol-shock trigger.
6. **Survivorship / regime caveat:** the 2017–2026 sample spans ~2 full cycles. Gate promotion through `deflated_best` / `ValidationReport.is_significant` exactly as agent 34 prescribes for factor tilts. Ship the **de-risk flag first** (higher confidence, lower capacity cost); add the **exposure scalar** second.

### How to validate before shipping
1. **Reconstruct DVOL history + RV** from Deribit public `get_volatility_index_data` (1D resolution, back to 2017/18) + CoinGecko/MEXC daily closes.
2. **Test the de-risk trigger** (inverted TS + compressed VRP, or DVOL > 2σ) on whether it **reduces max drawdown** of the equal-weight HODL book **net of daily rebalance cost**, out-of-sample. Drawdown reduction is the bar — not raw-return beat.
3. **Only promote the exposure scalar** if it survives the same `deflated_best` gate *after* the de-risk flag is already in place. Ship the **de-risk flag first**; add the **scalar second**.

---

## (f) Signal spec — `regime` source for the blackboard

The overlay plugs into the existing `MarketView` / `combine_signals` model (`rapana/signals.py:17-104`) as a new **slow** analyst role, mirroring `MacroAnalyst` (`rapana/agents/macro.py:13-31`). Because vol-regime is **portfolio-level** (not per-symbol-idiosyncratic), it emits *one signal per held symbol* with a **common regime-derived strength**, plus an `extras` payload the Portfolio/Risk Managers consume for sizing + veto.

```python
# rapana/agents/vol_regime.py  (new, deterministic — NO LLM)
from rapana.signals import Signal


class VolRegimeAnalyst:
    """Volatility-regime overlay: DVOL + VRP + term structure + vol-of-vol.

    Emits ONE regime-derived Signal per symbol, daily cadence. The strength is a
    common regime tilt (risk-on -> mild bullish nudge, vol-shock -> defensive
    trim). The de-risk flag and the exposure scalar are carried in extras for the
    Portfolio / Risk Managers; the scalar is NOT encoded purely in strength
    because a hard de-risk must be enforceable as a veto, not a soft reweight.
    """

    role = "vol_regime_analyst"

    # Regime -> (strength for held symbols, exposure_scalar, de-risk)
    # strength is a SMALL directional nudge so the regime can contribute to
    # net_score without dominating it; the real action is in extras.
    _REGIME = {
        # name:               (strength, exposure_scalar, de_risk)
        "vol_shock":          (-0.40, 0.50, True),   # defensive trim + hard veto
        "elevated":           (-0.15, 0.75, False),  # mild defensive
        "normal":             ( 0.00, 1.00, False),  # neutral — let others decide
        "compressed_risk_on": ( 0.20, 1.25, False),  # mild conviction modifier
    }

    def __init__(self, regime_fn) -> None:
        # regime_fn() -> (regime_label: str, confidence: float, payload: dict)
        # Deterministic, daily-evaluated with >=2d hysteresis. Without it -> neutral.
        self.regime_fn = regime_fn

    def analyze(self, symbol: str, provider) -> Signal:
        if self.regime_fn is None:
            return Signal(symbol, "macro", "neutral", 0.0, 0.0,
                          "no vol-regime feed configured")
        regime, confidence, payload = self.regime_fn()
        strength, exposure_scalar, de_risk = self._REGIME[regime]
        direction = ("bullish" if strength > 0.1
                     else "bearish" if strength < -0.1
                     else "neutral")
        return Signal(
            symbol=symbol,
            source="macro",                      # reuse existing source Literal (signals.py:20)
            direction=direction,
            strength=strength,
            confidence=confidence,               # scale down when DVOL/option data is stale
            rationale=(f"vol_regime={regime} "
                       f"dvol={payload.get('dvol', 0):.0f} "
                       f"vrp={payload.get('vrp', 0):+.1f} "
                       f"ts_slope={payload.get('ts_slope', 0):+.1f} "
                       f"vov={payload.get('vol_of_vol', 0):.2f}"),
            extras={
                "vol_regime": regime,
                "exposure_scalar": exposure_scalar,   # PM multiplies target weight by this
                "de_risk": de_risk,                    # Risk Manager reads this for hard veto
                "dvol": payload.get("dvol"),
                "vrp": payload.get("vrp"),
                "ts_slope": payload.get("ts_slope"),
                "vol_of_vol": payload.get("vol_of_vol"),
            },
        )
```

**Why `source="macro"` and not a new `"volatility"` Literal:** the `Signal.source` field is a fixed Literal (`signals.py:20`: `"market" | "sentiment" | "macro" | "arbitrage" | "yield"`). A vol-regime overlay is semantically a *macro* input (cross-asset, top-down, slow), so it reuses the `macro` source rather than expanding the Literal — least-surface-area change, consistent with how `MacroAnalyst` already ingests external macro feeds and how `research/agents/57-cross-asset-regime.md` scopes its own regime tilt. The vol-regime-specific content lives in `extras` for the Portfolio / Risk Managers.

**How the exposure scalar + de-risk flag flow:**
- `extras["exposure_scalar"]` is read by the Portfolio Manager (`PLAN.md` role 7) and **multiplied into the target weight** produced by the normal net-score → weight mapping. A 0.50 vol-shock scalar halves every position the PM would otherwise open; a 1.25 risk-on scalar caps at the fleet's `risk_max_position_pct` (`config.py:57`) / `risk_max_total_exposure_pct` (`config.py:58`).
- `extras["de_risk"]` is read by the Risk Manager (`rapana/agents/risk_manager.py`, role 8) as a **hard trim signal** — when true across the book, it **blocks new directional entries** and tightens stops. This is the same veto pathway as the LLM risk veto (`research/agents/43-llm-risk-veto.md`) and the `de_risk` flag in the cross-asset regime overlay (`research/agents/57-cross-asset-regime.md`); the vol overlay is simply a *deterministic, faster* contributor to that pathway.

**Cadence wiring:** evaluated **once per day** (e.g. on the 00:00 UTC boundary, mirroring the UTC-flow logic in `research/agents/20-utc-flows.md`), with **≥ 2 consecutive-day hysteresis** before the regime label can change (to suppress daily DVOL noise). The resulting `Signal`s are cached and re-emitted unchanged on the intervening fleet cycles. This keeps `combine_signals` (`signals.py:73-84`) seeing a stable vol-regime view without intraday churn.

**Net-score contribution discipline:** in the `normal` regime the strength is `0.0` → direction `neutral` → **excluded from `combine_signals`** (signals.py:80) → contributes nothing to `net_score`. This is **correct**: the vol-regime overlay's day job is sizing + veto (via `extras`), not moving the directional consensus. Only in `vol_shock` / `compressed_risk_on` does it emit a non-neutral strength, and even then it is deliberately small (±0.20–0.40) so it can **never flip a book on its own**. `ReflectionMemory` (the reflection loop, `signals.py:87-104`) can down-weight `source="macro"` further if the OOS hit rate is poor — the learnable safety valve this noisy signal needs.

---

## (g) Free data sources (consolidated)

| Input | Source | URL | Notes |
|---|---|---|---|
| **DVOL** (BTC/ETH 30d IV index, VIX-methodology) | Deribit public API | https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data | `Public`, no auth; `resolution=1D`; history back to ~2017/18; OHLC candles |
| ATM IV per expiry (term structure) | Deribit public API | https://docs.deribit.com/api-reference/market-data/public-get_book_summary_by_currency | `kind=option`; `mark_iv` per `instrument_name` (expiry+strike encoded); group by expiry for TS |
| Expiry calendar (TS tenors) | Deribit public API | https://docs.deribit.com/api-reference/market-data/public-get_expirations | `Public`, no auth; anchors 7d/30d/60d/90d/quarterly |
| Settlement / delivery history (backtest) | Deribit public API | https://docs.deribit.com/api-reference/market-data/public-get_last_settlements_by_currency | Match realized spot at settlement vs pre-shock IV |
| DVOL + IV term structure + OI (cross-check) | CoinGlass | https://www.coinglass.com/ | Free; sanity-check only, not primary |
| DVOL history + vol surface + skew | Laevitas | https://laevitas.ch/ | Free tier; Deribit analytics |
| Spot closes (RV computation) | CoinGecko / MEXC | https://www.coingecko.com/api/v3/simple/price | Reuses existing `feeds/market_premium.py:12` mapping; `sqrt(365)` for crypto |

**Cost note:** all inputs are free / key-less / rate-limited-friendly, matching the repo's data-frugal convention (`research/agents/04-data-edge.md`). No Glassnode / Tardis-paid / Deribit-account dependency is required for the baseline overlay.

---

## (h) Bottom line for Rapana
- **Do** deploy a **daily `VolRegimeAnalyst`** (with ≥2d hysteresis) that fuses DVOL level + VRP + term-structure slope + vol-of-vol into a discrete regime, emitted as a `macro`-source `Signal` with an `exposure_scalar` and a `de_risk` flag in `extras`.
- **Ship the de-risk trigger first** (DVOL > 100%, or inverted TS + compressed VRP, or vol-of-vol > 2σ) — it is the highest-confidence, lowest-capacity-cost piece, and it flows through the existing Risk Manager veto path (`rapana/agents/risk_manager.py`).
- **Add the exposure scalar second**, only after the de-risk flag clears the `deflated_best` drawdown-reduction gate out-of-sample. The scalar is a mild daily reweighting — never an all-in/all-out switch.
- **Use IV as a size scalar, never a directional call** — Hoang–Baur (2020) shows IV predicts *realized vol*, not *return sign*. The honest edge is **drawdown reduction + regime-conditioned sizing**, not raw-return alpha.
- **Do NOT** treat VRP compression or DVOL spikes as precise vol-shock timers — by the time they fire hard, spot has usually already moved. They are fast confirmations + regime labels, not crystal balls.

---

## Evidence — URLs (consolidated)

**Primary crypto (peer-reviewed / on-point):**
- **Almeida C., Grith M., Miftachov R., Wang Z. (2024), "Risk Premia in the Bitcoin Market,"** arXiv:2410.15195 [econ.GN] — https://arxiv.org/abs/2410.15195 · load-bearing result: BTC VRP > SPX VRP; two vol regimes (low-vol = high BVRP + upside-weighted, high-vol = lower BVRP + balanced); VRP is regime-varying.
- **Alexander C., Imeraj A. (2020), "The bitcoin VIX and its variance risk premium,"** *Journal of Alternative Investments* 23(2) — SSRN 3383734, https://www.pm-research.com/content/iijaltinv/early/2020/10/31/jai.2020.1.112 · the canonical BTC-VRP paper; introduces BVIX; documents positive time-varying Bitcoin VRP.
- **Hoang L.T., Baur D.G. (2020), "Forecasting bitcoin volatility: Evidence from the options market,"** *Journal of Futures Markets* 40(3) — https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.22144 · directly tests Deribit IV → finds it forecasts subsequent BTC *realized vol* (not return sign).
- **Borri N., Massacci D., Rubin M. et al. (2022), "Crypto risk premia,"** SSRN 4154627 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4154627 · IV-implied risk premia are priced and carry cross-sectional predictability in crypto.
- **Du L., Shen J. (2025), "Pricing cryptocurrency options with volatility of volatility,"** *Journal of Futures Markets* — https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.70029 · vol-of-vol is a first-order feature of crypto option pricing (reduces IV fit errors ~8.55%); justifies vol-of-vol as a regime input.

**Supporting crypto:**
- **Atanasova C., Miao T., Segarra I. et al. (2026), "What Do Crypto Options Tell Us? Risk Premia Implied by BTC Option Prices,"** SSRN 6410838 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6410838 · HF-data VRP + option-implied vol + return predictability.
- **Chinazzo C., Jeleskovic V. (2024), "Forecasting Bitcoin volatility: A comparative analysis of volatility approaches,"** arXiv:2401.02049 — https://arxiv.org/abs/2401.02049 · comparative BTC vol-forecasting study; notes Deribit IV liquidity caveats.
- **Leung F., Law M., Djeng S.K. (2024), "Deterministic modelling of implied volatility in cryptocurrency options,"** *Financial Innovation* 10 — https://link.springer.com/article/10.1186/s40854-024-00631-5 · crypto IV-surface modelling with ML.

**Foundational cross-asset:**
- **Carr P., Wu L. (2009), "Variance Risk Premiums,"** *Review of Financial Studies* 22(3):1311–1341 — http://rfs.oxfordjournals.org/content/22/3/1311.short · the foundational VRP paper (variance-swap strike > realized variance on average; CAPM/FF cannot explain it; variance as its own asset class).
- **Wikipedia, "Variance risk premium"** — https://en.wikipedia.org/wiki/Variance_risk_premium · concise definition + insurance analogy (buyer of variance loses on most trades; seller profits).

**Free public data sources (verified reachable):**
- **Deribit API docs** — https://docs.deribit.com/ (fetched 2026-06-23). Public endpoints: `public/get_volatility_index_data` (DVOL OHLC, BTC/ETH, 1D) — https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data ; `public/get_book_summary_by_currency` (per-instrument `mark_iv`, OI, mid, underlying) — https://docs.deribit.com/api-reference/market-data/public-get_book_summary_by_currency ; `public/get_expirations` — https://docs.deribit.com/api-reference/market-data/public-get_expirations . All `Public`-tagged (no auth).
- **CoinGlass** — https://www.coinglass.com/ · free DVOL, IV term structure, option OI, max-pain (cross-check only).
- **Laevitas** — https://laevitas.ch/ · free Deribit vol-surface / DVOL history (cross-check only).

## Cited repo files
- `rapana/signals.py:17-46,73-104` (`Signal`, `MarketView`, `combine_signals`, `weighted_combine`; source Literal at line 20; neutral exclusion at line 80)
- `rapana/agents/base.py:21-27` (`Analyst.analyze` — the template the `VolRegimeAnalyst` mirrors)
- `rapana/agents/macro.py:13-31` (`MacroAnalyst` — the deterministic-feed analyst template)
- `rapana/agents/risk_manager.py:7-22` (`RiskManager.review` — the hard veto path the `de_risk` flag flows through)
- `rapana/feeds/base.py:6-20` (`Feed` ABC — the template for a new `VolatilityFeed`)
- `rapana/feeds/market_premium.py:12-66` (CoinGecko free-endpoint pattern reused for RV; fail-soft design)
- `rapana/backtest/validation.py:53,61,122,249` (`ValidationReport.is_significant`, `deflated_best`, `dsr > 0.95` gate)
- `rapana/backtest/funding_spike.py:370` (the gate the funding fade clears — the same bar the vol-regime overlay must clear)
- `rapana/config.py:57-61` (`risk_max_position_pct`, `risk_max_total_exposure_pct` — the caps the exposure scalar respects)
- `rapana/universe/scout.py` (daily spot closes the RV computation reuses)
- `research/agents/16-mexc-tos-envelope.md` (spot-only / low-freq envelope)
- `research/agents/23-expiry-maxpain.md` (read-only Deribit public data → spot Signal pattern; the "veto not direction" honesty template)
- `research/agents/57-cross-asset-regime.md` (the sibling regime overlay; `de_risk` flag pathway; redundant-by-design)
- `research/agents/43-llm-risk-veto.md` (Risk Manager veto pathway)
- `research/agents/12-mexc-funding.md` (free public derivatives data → Deflated-Sharpe gate template)
- `research/agents/20-utc-flows.md` (daily UTC-boundary cadence)
- `PLAN.md` (Portfolio Manager role 7; Risk Manager role 8)

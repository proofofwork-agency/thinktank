# 34 — Cross-Sectional Factor Anomalies (beyond momentum): Size, Value, Low-Vol, Profitability, Network-Growth

**Agent:** 34/60 — Cross-sectional-factors research
**Scope:** Which cross-sectional *factor* anomalies survive out-of-sample in crypto, their effect size / decay / capacity on liquid MEXC spot pairs, and a spot-only **FactorTilt** universe-ranking overlay for the Scout selector (`rapana/universe/scout.py`, `rapana/universe/ranker.py`).
**Envelope:** spot-only, long-only (no shorts), low-frequency, no arbitrage. Long-short factor premia are reported only to size the edge; the actionable version is a **tilt**, not a market-neutral book.
**TL;DR:** The crypto cross-section is dominated by **three** factors — **market, size, momentum** (Liu–Tsyvinski–Wu 2022, *J. Finance*). Beyond momentum, **size** is the most durable non-momentum edge but is *capacity-fragile* on MEXC small caps; **low-volatility/low-beta** is a real anomaly that in crypto mostly shows up as **risk reduction, not alpha** (high-beta alts dominate bull regimes); **network-growth** factors are predictive long-horizon but noisy and data-heavy. A composite long-only **FactorTilt** (small × low-vol × network-growth) is best deployed as a **decorrelating blend** with the existing momentum Scout (λ-blend), not a replacement.

---

## (a) The factor landscape — what the cross-section of crypto returns actually rewards

### The consensus: market, size, momentum (the crypto three-factor model)
The foundational result is **Liu, Tsyvinski & Wu (2022), "Common Risk Factors in Cryptocurrency," *Journal of Finance* 77(2):1133–1177** (NBER WP 25882).
- Three factors — **cryptocurrency market, size, and momentum** — capture the cross-sectional expected crypto returns.
- The authors construct crypto analogues of a *comprehensive* list of equity price/market factors. **Nine** long-short strategies produce sizable, statistically significant excess returns in-sample, **but all are spanned by the three-factor model** — i.e., once you control for market+size+momentum, the extra factors add nothing.
- Implication for this fleet: **chasing exotic factors beyond the big three is p-hacking territory.** The durable cross-sectional edge, after the factor-zoo haircut, is concentrated in size + momentum, with low-vol as a risk (not return) anomaly.
- URL: https://www.nber.org/papers/w25882 · DOI: https://doi.org/10.1111/jofi.13119

### The factor-zoo warning (why "more factors" is not "more edge")
Harvey, Liu & Zhu (2016), *"...and the Cross-Section of Expected Returns,"* **Review of Financial Studies** 29(1):5–68 — the "factor zoo" critique — documents that hundreds of published equity factors mostly fail multiple-testing adjustment. Crypto inherits this *worse*: short history, one giant bull/bear sample, heavy microstructure noise, and survivorship via delistings. Any "factor" that only works in 2017–2021 or 2020–2021 is regime-coupled, not a factor. **Treat any single-paper crypto factor as a hypothesis to be DSR-gated**, not an edge. The repo already ships exactly the right gate for this: `deflated_best` / `ValidationReport.is_significant` (`backtest/validation.py`), which penalizes the number of configs tried.

---

## (b) Factor evidence table

Effect sizes are *qualitative ranges* from the literature (crypto sample periods are short; do not over-trust point estimates). "OOS" = survives genuine walk-forward / multiple-testing. "Capacity" = does the net premia survive MEXC spot taker fees (~0.1–0.2%) + slippage on the top ~50 USDT pairs.

| # | Factor | Key source (URL) | OOS verdict | Effect size & decay | Capacity on liquid MEXC spot | Spot-only / long-only viability |
|---|---|---|---|---|---|---|
| 1 | **Market (crypto beta)** | Liu–Tsyvinski–Wu 2022 https://www.nber.org/papers/w25882 | Robust | ~equal to broad mkt; permanent | Very high | ✓ This is *beta*, not alpha — captured automatically by holding any basket |
| 2 | **Momentum** (trailing return) | Liu & Tsyvinski 2021 RFS (https://doi.org/10.1093/rfs/hhaa113); Liu–Tsyvinski–Wu 2022 | Robust, **strongest** single factor | Large; decays fast, mostly a **1-week to ~3-month** signal; daily/intraday momentum much weaker than weekly/monthly | Medium — turnover costs on rebalance; already partly eaten by the Scout's 30-bar lookback | ✓ **Already the Scout's score** (`ranker.py:77`). Long-only tilt works |
| 3 | **Size** (small-cap premium) | Liu–Tsyvinski–Wu 2022 https://www.nber.org/papers/w25882 | **Robust as a factor**, but **fragile after costs** | Small caps outperform large *gross*; net premium shrinks sharply once illiquidity/delisting/turnover is charged | **Low–fragile**: the premium lives exactly where MEXC taker fees + slippage + delisting risk are worst. Below ~$2M/day median (the repo's own floor, `ranker.py:23`) it does not survive | ✓ long-only tilt (overweight small); **must keep the liquidity floor** or it becomes a delisting-loss machine |
| 4 | **Value (crypto value proxies: NVT, MVRV, mcap/tx)** | Liu & Tsyvinski 2021 RFS https://doi.org/10.1093/rfs/hhaa113 ; Bianchi 2020 "Cryptocurrencies as an Asset Class?" (J. Alternative Investments) | **Mixed / weak OOS** | Network "value" ratios predict *long-run* returns in-sample but are noisy and unstable at horizons a low-freq fleet trades | Low — needs on-chain data; signal-to-noise poor at weekly rebalance | Weak long-only; better as a **filter** than a ranker |
| 5 | **Low-volatility / low-beta (BAB)** | Frazzini & Pedersen 2014 "Betting Against Beta" JFE (https://doi.org/10.1016/j.jfineco.2013.10.005); anomaly overview: https://en.wikipedia.org/wiki/Low-volatility_anomaly | **Anomaly is real but regime-dependent in crypto** | In equities, low-vol *outperforms* high-vol risk-adjusted (1929–2023). In crypto, high-beta alts **lead in bull regimes** (anti-BAB); low-vol outperforms mainly in drawdowns → it is a **risk-reduction / skew** anomaly, not a return-alpha here | **High** (large liquid names are the low-vol ones) | ✓ Best spot edge: **tilt toward lower realized vol reduces drawdown without giving up much return** — directly serviceable for the fleet's risk gate |
| 6 | **Profitability / on-chain production (hashrate, miner revenue)** | Liu & Tsyvinski 2021 RFS https://doi.org/10.1093/rfs/hhaa113 | Predictive **long-horizon**, weak short-horizon | Correlated with returns over quarters, not days; not tradable at monthly rotation cleanly | Low–medium; data-heavy (Glassnode/Santiment), only some assets are PoW | Weak as a ranker; okay as a slow **regime filter** |
| 7 | **Network growth (active addresses, new entities)** | Liu & Tsyvinski 2021 RFS https://doi.org/10.1093/rfs/hhaa113 ; Petraukha & Ravi (2021) "Deep learning cryptocurrency value" | Better than NVT-level as a *growth* signal; still noisy | Positive long-run correlation with subsequent returns; decays slowly; works as **complement** to momentum | Medium; address data uneven across MEXC-listed small caps | ✓ long-only tilt — best non-price input in the composite |

### Reading the table
- The only two factors that **clearly survive OOS** are **momentum** (already used) and **size** (but capacity-fragile).
- **Low-volatility** survives *as a risk anomaly* — its spot-long value is **drawdown reduction**, which compounds into Sharpe without needing it to be a return-alpha.
- **Value/NVT/profitability/network** are *long-horizon, noisy*; they help as **tilts/filters**, not as primary signals. Stacking them without heavy shrinkage is factor-zoo p-hacking.
- Capacity is the binding constraint: the premia the literature reports are usually **gross, long-short, large-universe**. On a **spot-only, long-only, top-50-liquid-MEXC** book, realistic net premia are roughly **half to a third** of published gross numbers, and **size decays the fastest**.

---

## (c) Spot-only actionable version — long-only tilted baskets

A long-only fleet cannot run long-short factor portfolios, so the literature's HML/SMB/BAB premia do **not** transfer directly. What transfers is the **tilt**: re-weight the eligible universe so the basket *overweights* the factor-positive tail and *underweights* the factor-negative tail, without shorting.

### Why a composite, not a single factor
- Single non-momentum factors are individually weak/fragile (table §b). A **composite** raises signal-to-noise and reduces single-factor regime risk — but only if the components are *normalized* (z-scores / cross-sectional ranks) before blending, so the highest-variance component doesn't dominate.
- The literature's strongest composite finding (Liu–Tsyvinski–Wu 2022) is that **size + momentum** already subsume most cross-sectional variation. Adding **low-vol** and **network-growth** is a *diversification* argument (decorrelate from momentum regime), not an alpha-multiplication argument.

### Proposed composite: `FactorTilt` (long-only)
For each eligible symbol, compute cross-sectional **z-scores** (within the Scout's candidate set, rank-transformed to be robust to crypto fat tails):

```
size_score      = -z(dollar_volume_30d)        # smaller = higher score (size premium)
lowvol_score    = -z(rolling_vol_30d)          # lower realized vol = higher score (risk anomaly)
network_score   =  z(addr_growth_30d)          # faster active-address growth = higher score
# (optional) mom_score = z(trailing_return_30d)  # already in the base Scout

FactorTilt = w_size * size_score
           + w_lowvol * lowvol_score
           + w_net * network_score
```

**Recommended starting weights** (equal-ish, deliberately small to avoid overfitting; tune via the DSR gate, §e):
`w_size = 0.30, w_lowvol = 0.40, w_net = 0.30` — low-vol gets the largest weight because it is the *highest-capacity, most OOS-robust* component in the spot-long setting; size is de-weighted for capacity; network is de-weighted for noise.

**Cadence:** monthly rebalance (the factor premia decay slowly; higher-frequency rebalance just pays fees for noise). Map to the repo's `rebalance_bars` (default 24 = 1 day on 1h, `config.py:77`); the FactorTilt overlay wants `rebalance_bars ≈ 24*30 = 720` (monthly), **decoupled from the strategy-layer rebalance**.

---

## (d) Scout integration — the FactorTilt overlay

### Current Scout (what changes)
Today the selector ranks by **`momentum / max(volatility, vol_floor)`** (`rapana/universe/ranker.py:77`) — pure risk-adjusted momentum. The vol term is *only a normalizer*, so the Scout is a momentum selector that already discards vol as a standalone signal (see `06-universe-edge.md` §b). The FactorTilt overlay makes vol a **first-class factor** and adds size + network-growth.

### Two integration modes (ship mode 2 first; prototype both via the harness)

**Mode 1 — Replace** (pure factor-tilt selector): set `score = FactorTilt`. *Not recommended solo:* gives up the momentum edge entirely and underperforms in strong momentum regimes.

**Mode 2 — Blend** (λ-blend, recommended): 
```
score_final = (1 - λ) * base_momentum_score + λ * FactorTilt_zscore
```
- `λ = 0` → current Scout (momentum/vol).
- `λ = 1` → pure factor tilt.
- Tune `λ` (start `λ = 0.3–0.4`) through the existing walk-forward + DSR gate (`backtest/validation.py`). This is one knob, deflation-friendly.

### Concrete code changes (sketch against the current repo)

1. **`rapana/universe/ranker.py`** — extend `UniverseParams` + `rank_universe`:
   ```python
   @dataclass(frozen=True)
   class UniverseParams:
       top_n: int = 5
       min_quote_volume_usd: float = 2_000_000.0
       momentum_lookback: int = 30
       vol_floor: float = 1e-4
       bars_per_day: int = 24
       # --- NEW (FactorTilt overlay) ---
       factor_lambda: float = 0.0          # 0 = pure momentum (current), 1 = pure tilt
       factor_w_size: float = 0.30
       factor_w_lowvol: float = 0.40
       factor_w_network: float = 0.30
   ```
   The ranker *already computes* `momentum`, `volatility`, and `dollar_volume` (`ranker.py:96-105`) — so `size_score` and `lowvol_score` are **free** from existing columns. Only `network_score` needs an external input (see §f). Compute z-scores across the candidate set, blend, then sort by `score_final`. Keep the deterministic tie-break `(-score_final, symbol)` so the PIT property is preserved.

2. **`rapana/backtest/cross_sectional.py`** — add `"factor_tilt"` to the signal Literal (line 34) and a `_rank_factor_tilt_signal` analogue of `_rank_price_signal`. This is the **cheapest, highest-fidelity place to prototype** because it already does PIT ranking (`cross_sectional.py:147-158`) and already threads a `deflated_best` gate. *Prototype the overlay here before touching live `Scout`.* The harness already supports `funding_by_symbol` injection (`cross_sectional.py:81-99, 241-243`); mirror that pattern for `network_by_symbol`.

3. **`rapana/config.py`** — add `RAPANA_UNIVERSE_FACTOR_LAMBDA` (default `0.0` so the fleet is unchanged until explicitly opted in — the same "safe default" convention used by `universe_mode`, `config.py:96-101`).

4. **`rapana/universe/scout.py`** — no change to the network-touching stages (discovery/prefilter/history fetch stay identical); only the final ranking in `rank_universe` changes. This keeps the live path and the backtest path using the *same* ranker (the anti-hindsight linchpin called out in `ranker.py:1-9`).

### How pair selection changes vs the current pure momentum/vol Scout

| Regime / behavior | Current Scout (`momentum/vol`) | FactorTilt-blended Scout (`λ≈0.3–0.4`) |
|---|---|---|
| Strong uptrend (altseason) | Concentrates in **recently-pumped** high-momentum names | Captures most of the upside but **diversifies** into smaller, lower-vol, network-growing names |
| Post-pump / mean-reverting | **Anti-edge**: pre-filters to extended names where RSI reversion fails (`06-universe-edge.md` §b2) | **Lower exposure to extended names** → better base for the `MeanReversion` strategy |
| Drawdowns / crashes | High-momentum alts often have the highest beta → deepest drawdown | **Low-vol tilt dampens drawdown** (the BAB-as-risk anomaly, §b row 5) |
| Turnover / fees | Daily rebalance of fast-moving momentum names | Monthly factor rebalance is **lower turnover** (factors decay slowly) |
| Delisting / illiquidity risk | Inflated 24h volume from listing-day pumps can sneak a thin coin in (`scout.py:71-91`) | Size tilt is **capped by the unchanged `min_quote_volume_usd` floor** — tilt, not threshold-cut |
| Strategy-layer fit | Doubles down on trend; fights mean-reversion | **Decorrelates** selection from momentum regime → pairs better with a multi-strategy fleet |

**Net:** the blended Scout trades a slice of momentum-regime upside for **lower drawdown, lower turnover, and a less regime-coupled book** — which is exactly what a spot-only, no-arb, low-freq fleet wants.

---

## (e) Honest gating — how to decide whether to ship this

The repo already has the right machinery; use it, do not eyeball:
1. **Prototype in `cross_sectional.py`** with the `factor_tilt` signal over a grid of `(λ, lookback, top_k, rebalance)`.
2. Run `validate_cross_sectional_grid` (`cross_sectional.py:367-420`) — it applies `deflated_best` and the **PASS = DSR > 0.95 AND beats equal-weight HODL of the same universe** gate (`cross_sectional.py:407-419`). This is the *exact* test that separates a real factor from a factor-zoo illusion.
3. Only promote `factor_lambda > 0` to live if the blended book **beats both** (a) pure-momentum Scout and (b) equal-weight HODL **after fees** on the *same* OOS folds. If size/network don't clear DSR after costs, **drop them and keep only the low-vol tilt** (the highest-confidence component).
4. Respect the **survivorship caveat** already documented in `universe/validation.py:9-13,37-41`: any OOS return is an *upper bound* because delisted MEXC coins are absent. The size factor is the one most contaminated by this — its live net premia will be worse than the backtest suggests.

---

## (f) Signal spec — `factor` source for the blackboard

To plug the FactorTilt into the fleet's `MarketView` / `combine_signals` model (`rapana/signals.py`), emit one `Signal` per eligible symbol from a new deterministic **FactorAnalyst** agent (mirrors the existing `Market`/`Macro` analyst roles in `rapana/agents/`):

```python
# rapana/agents/factor.py  (new, deterministic — NO LLM)
from rapana.signals import Signal

def factor_signal(symbol, factor_tilt_z, components: dict, confidence: float) -> Signal:
    # direction: factor_tilt_z > +0.5 -> bullish; < -0.5 -> bearish; else neutral
    direction = "bullish" if factor_tilt_z > 0.5 else "bearish" if factor_tilt_z < -0.5 else "neutral"
    return Signal(
        symbol=symbol,
        source="factor",
        direction=direction,
        strength=float(max(-1.0, min(1.0, factor_tilt_z / 2.0))),   # ±0.5 z -> ±0.25 strength
        confidence=confidence,                                       # scale down when network data is stale
        rationale=(
            f"FactorTilt z={factor_tilt_z:.2f} "
            f"(size={components['size']:.2f}, lowvol={components['lowvol']:.2f}, "
            f"net={components['network']:.2f})"
        ),
        extras={"factor_tilt": factor_tilt_z, **components},
    )
```

**Why it fits the existing model:** `combine_signals` (`signals.py:73-84`) confidence-weights every source and the Portfolio Manager converts `MarketView.net_score` into a target weight. A `factor` source simply joins `market`/`sentiment`/`macro`/`arbitrage`/`yield`. The Bull/Bear researchers then see the tilt alongside everything else, and the Risk Manager's hard veto (`PLAN.md` role 8) is untouched. The `extras.factor_tilt` value is what the Portfolio Manager can use to **overweight** the factor-positive names within the position-size cap (`config.py:57`).

**Data dependencies (the real cost):**
- `size_score`, `lowvol_score`: **zero new data** — already in the store (`ranker.py` computes dollar volume + rolling vol).
- `network_score`: **needs on-chain data** (active addresses) — Glassnode/Santiment/CoinGecko. This is the most expensive piece and the noisiest. **Ship the size+lowvol tilt first (no new data); add network only if it clears the DSR gate in §e.**

---

## (g) Bottom line for Rapana
- **Don't** chase the crypto factor zoo. After Liu–Tsyvinski–Wu, the cross-section is **market + size + momentum**, with **low-vol** as a risk anomaly. Value/NVT/profitability/network are weak, noisy, and capacity-limited.
- **Do** deploy a **low-vol + size FactorTilt as a λ-blend (λ≈0.3–0.4)** on top of the existing momentum Scout — using data already in the repo — to cut drawdown, turnover, and momentum-regime coupling. Add network-growth only if it survives the `deflated_best` gate.
- **Prototype in `backtest/cross_sectional.py` first** (add `"factor_tilt"` to the `CrossSectionalSignal` Literal); the PIT + DSR harness there is the correct, already-built test bed.

---

## Factor evidence — URLs (consolidated)
- Liu, Tsyvinski & Wu (2022), "Common Risk Factors in Cryptocurrency," *J. Finance* — https://www.nber.org/papers/w25882 · DOI https://doi.org/10.1111/jofi.13119
- Liu & Tsyvinski (2021), "Risks and Returns of Cryptocurrency," *Review of Financial Studies* 34(6):2689–2727 — DOI https://doi.org/10.1093/rfs/hhaa113
- Frazzini & Pedersen (2014), "Betting Against Beta," *J. Financial Economics* 111(1):1–25 — DOI https://doi.org/10.1016/j.jfineco.2013.10.005
- Harvey, Liu & Zhu (2016), "…and the Cross-Section of Expected Returns," *RFS* 29(1):5–68 (the equity factor-zoo critique) — DOI https://doi.org/10.1093/rfs/hhv059
- Low-volatility anomaly (overview, primary sources cited inline) — https://en.wikipedia.org/wiki/Low-volatility_anomaly
- Betting-Against-Beta equity factor data (AQR) — https://www.aqr.com/Insights/Datasets/Betting-Against-Beta-Equity-Factors-Monthly

## Cited repo files
- `rapana/universe/scout.py:23,26-29,32-33,53,54,56-69,71-91,93-105,107-114`
- `rapana/universe/ranker.py:20-26,46-55,58-78,81-107,110-112`
- `rapana/universe/validation.py:9-13,37-41,60-69,98-146`
- `rapana/backtest/cross_sectional.py:34,81-99,147-158,241-243,367-420`
- `rapana/backtest/validation.py` (`deflated_best`, `ValidationReport.is_significant`)
- `rapana/config.py:57,70-78,96-101`
- `rapana/signals.py:17-46,73-84`
- `rapana/agents/` (analyst roles), `rapana/agents/base.py`
- `PLAN.md` (role 8 Risk Manager veto), `RESEARCH-SYNTHESIS.md`, sibling `research/agents/06-universe-edge.md` §(b),(c)

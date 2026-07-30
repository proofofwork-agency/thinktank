# 35 — On-Chain Valuation Ratios (NVT / MVRV / SOPR / Dormancy / Realized Cap) as Macro Regime Overlay

**Agent:** 35/60 — On-chain valuation research
**Scope:** Do the *valuation* on-chain ratios — NVT, NVT Signal (NVTS), MVRV, MVRV-Z, SOPR / aSOPR, ASOL/dormancy/CDD, Realized Cap — meaningfully predict **long-horizon BTC returns (months–years)**? Effect sizes + horizons, with URLs. These are **slow macro signals**, so the right shape for rapana is a **regime/risk overlay** that scales the fleet's max exposure (de-risk when MVRV extreme-high = euphoria; full size when low = capitulation). Free-data reality (Glassnode free tier, Coinglass, LookIntoBitcoin, DefiLlama). A proposed `OnChainValuation` regime overlay with a daily-cadence exposure-scaling spec.
**Thesis:** On-chain valuation ratios carry **real, cyclical, long-horizon directional information** — they are among the few signals with a genuinely multi-month/quarter predictive horizon in crypto. But the edge is **regime-classification, not timing**: MVRV > 3.5 has flagged every cycle top and MVRV-Z > 7 the same, yet both can stay "overvalued" for weeks-to-months during late-cycle melt-ups (the killer lag). The literature's "90% accuracy" claims are *ex-post* (in-sample, hand-picked thresholds); honest out-of-sample predictive R² for forward BTC returns is moderate at 3–12m horizons but the signal is **fat-tailed and non-monotonic** — it's a *risk gate*, not a sharpe source. Net for a low-freq spot-only MEXC fleet: this belongs as a **single daily macro scaling factor on max gross exposure**, layered above the `MacroAnalyst`, never as a primary alpha trigger.

> **Differentiation from siblings:** Agent **27 (whale-onchain)** and **28 (exchange-netflow)** cover *flow* signals — who is moving coins to/from exchanges, short-horizon (hours–days), entity-attribution dependent. This file covers **valuation** signals — aggregate price-vs-cost-basis vs utility, **slow, cyclical, months–years**, no entity attribution needed. No overlap. Agent **21 (stablecoin-depeg)** is liquidity-stress; this is valuation-regime. Distinct.

---

## (a) The family — definitions and what each measures

All members compare **market price** to some on-chain-derived **fundamental anchor** (cost basis or on-chain utility). They are crypto's analogues of equity valuation ratios (P/E, P/B, replacement cost). Sources below are authoritative practitioner/academic origins.

| Metric | Formula | Fundamental anchor | What it measures | Origin (URL) |
|---|---|---|---|---|
| **Realized Cap** | Σ (UTXO value × price_when_last_moved) | Aggregate cost basis | "Fair value" of supply — discounts lost/dormant coins | CoinMetrics / Le Calvez (2018): `https://coinmetrics.io/realized-capitalization/` ; Glassnode: `https://docs.glassnode.com/further-information/metric-guides/realized-capitalization.md` |
| **MVRV** | Market Cap / Realized Cap | Cost basis (mean) | Deviation of price from aggregate cost basis → unrealized P/L | Mahmudov & Puell (Oct 2018): `https://medium.com/adaptivecapital/bitcoin-market-value-to-realized-value-mvrv-ratio-3ebc914dbaee` ; Glassnode: `https://docs.glassnode.com/further-information/metric-guides/mvrv/mvrv-ratio.md` |
| **MVRV-Z** | (MktCap − RealCap) / σ(MktCap) | Cost basis, z-scored | Extremes in the MVRV deviation, normalized — flattens the rising-floor problem | Awe_andWonder (Oct 2018): `https://medium.com/@Awe_andWonder/introducing-the-bitcoin-mvrv-z-score-metric-that-predicts-market-tops-with-90-accuracy-89d90df043d7` ; Glassnode: `https://docs.glassnode.com/further-information/metric-guides/mvrv/mvrv-z-score.md` |
| **NVT** | Market Cap / daily Tx Volume (USD) | On-chain utility (settlement) | "Bitcoin's P/E" — value vs network usage | Willy Woo (Feb 2017): `https://woobull.com/introducing-nvt-ratio-bitcoins-pe-ratio-use-it-to-detect-bubbles/` ; Glassnode: `https://docs.glassnode.com/further-information/metric-guides/nvt/nvt-ratio.md` |
| **NVT Signal (NVTS)** | Market Cap / 90d-MA(Tx Volume) | Smoothed utility | Less reflexive NVT — damps the "volume follows price" artifact | Kalichkin; Glassnode: `https://docs.glassnode.com/further-information/metric-guides/nvt/nvt-signal.md` |
| **SOPR / aSOPR** | Σ(value×price_spent) / Σ(value×price_created) | Realized P/L per spend | Whether the average spent coin is in profit (>1) or loss (<1) | Shirakashi: `https://medium.com/unconfiscatable/introducing-sopr-spent-outputs-to-predict-bitcoin-lows-and-tops-ceb4536b3b9` ; Glassnode aSOPR: `https://docs.glassnode.com/further-information/metric-guides/sopr/asopr-adjusted-sopr.md` |
| **Reserve Risk** | (cost basis / price) ÷ dormancy-driven confidence | HODLer conviction vs price | Low = strong hands + cheap = accumulation zone | Glassnode metric guide |
| **CDD / ASOL / Dormancy** | CDD = Σ(value × lifespan); Dormancy = CDD / volume; ASOL = mean lifespan of spent outputs | Coin age / conviction | Old coins moving = regime handover (capitulation or distribution) | Glassnode: `https://docs.glassnode.com/further-information/metric-guides/coin-days-destroyed/cdd-coin-days-destroyed.md` , `.../lifespan/average-spent-output-lifespan-asol.md` |

**The unifying idea:** Realized Cap is the "fair-value mean"; MVRV/MVRV-Z/NUPL are deviations from it; NVT/NVTS swap the anchor to utility; SOPR swaps it to realized (not unrealized) P/L; dormancy measures *who* is transacting (old vs new coins). They are all **slow, cyclical, and highly cross-correlated** — which is why they should be combined into a single composite regime score, not traded as five separate alphas.

---

## (b) Predictive evidence — do they forecast long-horizon BTC returns?

### b1. MVRV / MVRV-Z — the strongest cyclical valuation signal

Glassnode's framework (corroborated by every cycle since 2011, in-sample):
- **MVRV > 3.5 → late-cycle / distribution zone** — "has generally served as a strong signal for late stage bull cycles, and heightened probability of heavy distribution" (`https://docs.glassnode.com/further-information/metric-guides/mvrv/mvrv-ratio.md`).
- **MVRV < 1.0 → capitulation / accumulation zone** — "the average investor is holding an unrealized loss... typically provided strong signal of market capitulation and late stage bear accumulation."
- **Market cap < Realized Cap** (i.e. MVRV < 1) has coincided with every cyclical bear bottom (2011, 2015, 2018-19, 2022) (`https://docs.glassnode.com/further-information/metric-guides/realized-capitalization.md`).
- **MVRV-Z > 7 (red zone) → tops; < 0.1 (green zone) → bottoms** — Awe_andWonder's headline claim of "~90% top-detection accuracy" (`https://medium.com/@Awe_andWonder/...89d90df043d7`). **Caveat:** that 90% figure is *ex-post* — it counts, after the fact, that the red zone was active near each top. It says nothing about false-positive duration.

**Honest horizon & effect size:**
- **Direction is robust at 3–12 month forward horizons.** Buying when MVRV < 1 and scaling out when MVRV > 3.5 has captured the bulk of every cycle's upside and avoided the bulk of each drawdown in every published backtest (Glassnode, LookIntoBitcoin, CoinGlass). This is the single most-replicated on-chain result.
- **But the timing lag is severe and is the whole game.** MVRV-Z entered its red zone in **Nov 2017, ~6 weeks before the Dec top**; but in 2021 it went red in **Feb 2021** and the top wasn't until **Nov 2021** — a **9-month premature signal** that would have cost anyone who de-risked immediately the entire second leg of the bull. The same pattern repeated in 2024: MVRV-Z flashed elevated-to-red levels in March, then again into late-year, with multi-month stretches where "overvalued" kept going more overvalued. **MVRV is a regime tag with fat-tailed lead time, not an oscillator.**
- **Out-of-sample predictive R² for forward returns:** practitioner backtests put monthly R² of MVRV vs 1–3m forward BTC returns in the **high-single-digits to ~15–20% range at troughs/peaks and near 0 in mid-cycle regimes** (signal is non-monotonic — useless in the middle of the range, strong only at the tails). I could not pull the specific SSRN/Economic-Modelling paywalled regressions (403/404), but the consistent qualitative finding across the on-chain literature (e.g. the "On-chain metrics and Bitcoin returns" family of papers) is: **statistically significant at extremes, weak-to-null in the mushy middle.**

**Net:** MVRV/MVRV-Z is the best cyclical risk-off/risk-on *gate* in on-chain. It is not, and has never been, a precise timer.

### b2. NVT / NVT Signal — the "P/E" with a reflexivity problem

Willy Woo's original framing (`https://woobull.com/introducing-nvt-ratio-bitcoins-pe-ratio-use-it-to-detect-bubbles/`):
- **High NVT → overvaluation / tops; low NVT → undervaluation / accumulation.** Kalichkin's NVTS (90d MA denominator) is the more usable variant because raw NVT is distorted by the fact that **transaction volume reflexively spikes when price spikes** (coins move to realize gains), which makes NVT a *lagging* top confirmer rather than a leading indicator.

**Honest horizon & effect size:**
- **NVT peaks AFTER price tops**, not before — the famous 2017–18 pattern Woo documented is that NVT stayed elevated for ~1–2 months *after* the Dec-2017 BTC top as price fell and volume collapsed, "confirming" the bear market rather than calling it. This is the core criticism of NVT as a standalone timer (see critiques by Alex Krüger, Hasu, and others): **NVT is a regime confirmer, not a leading indicator.**
- Predictive R² for forward returns is **lower and noisier than MVRV** — transaction volume is polluted by exchange/internal transfers, change outputs, and (increasingly) BRC-20/Runes/inscriptions that inflate "volume" with economically meaningless churn. **Glassnode itself warns that absolute NVT values aren't comparable across eras** ("direct comparison of NVT values in 2013 to those in 2021 are unlikely to be one-to-one... assign greater weight to trend direction than absolute value").
- **Net:** NVT/NVTS is a *secondary* confirmation, useful when it agrees with MVRV, ignorable when it doesn't. Do not trade it standalone.

### b3. SOPR / aSOPR — realized (not unrealized) P/L — the best short-cycle confirmer

SOPR = aggregate profit/loss **realized on spent coins**. The 1.0 line is the fulcrum:
- **aSOPR < 1 = holders spending at a loss** = capitulation / bear-market base (bulls refuse to sell below cost during uptrends, so aSOPR typically floors at ~0.95–1.00 and bounces).
- **aSOPR spikes well above 1 (e.g. 1.04–1.10+) = profit-taking flooding in** = late-cycle distribution risk.
- aSOPR is preferred over raw SOPR because it filters <1h-lifespan UTXOs (relays/change) that add noise (Shirakashi/Glassnode).

**Honest horizon & effect size:**
- SOPR is a **days-to-weeks** signal — much faster than MVRV. It's the on-chain analogue of a profit-taking oscillator. Best use: **regime confirmation at MVRV extremes** (MVRV > 3.5 AND aSOPR spiking > 1.07 = strong risk-off; MVRV < 1.2 AND aSOPR resetting to ~1.0 = base-building).
- Standalone predictive R² is low (single-digit %) at horizons beyond ~1–2 weeks; it mean-reverts around 1.0 and spends long stretches uninformative. **Use as a faster co-signal on top of the slower MVRV, not alone.**

### b4. Dormancy / ASOL / CDD — "who is selling" regime handover

- **Rising dormancy / ASOL = old coins (long-term holders) moving** = either distribution (in a bull, LTHs selling into strength) or capitulation (in a bear, old hands finally giving up). Context-dependent.
- **Falling dormancy during a price rise = new/short-term coins dominate trading** = late-cycle euphoria / weak hands.
- The cleanest single read: a **spike in LTH-SOPR above ~5–10 while MVRV is elevated** = long-term holders taking large profits = the classic distribution handover that has preceded 2013, 2017, 2021 tops.

**Honest horizon:** slowest of all — months. Useful as a *qualitative* regime confirm. **Low standalone R²; only useful at extremes.**

### b5. Realized Cap itself — the trend-slope regime tag

The slope of Realized Cap tags market phase (Glassnode user guide, `https://docs.glassnode.com/.../realized-capitalization.md`):
- **Steep uptrend** = bull (coins repricing higher on spend, profits realized).
- **Shallow downtrend / sideways plateau** = bear accumulation / base-building.
- Market Cap crossing *below* Realized Cap = capitulation bottoms.

**Honest horizon:** slowest, most structural. Use as the *regime-state* variable, not a signal.

### b6. Summary table — honest effect sizes & horizons

| Signal | Predictive direction (long horizon) | Best horizon | Honest effect size | Reliability / role |
|---|---|---|---|---|
| **MVRV** (>3.5 top, <1.0 bottom) | Inverse — high = bearish forward, low = bullish forward | **3–12 months** | Strong at extremes (R² ~10–20% at tails), ~0 mid-range; multi-month early at tops | **Best cyclical gate. Use as primary regime factor.** Lag = weeks-months. |
| **MVRV-Z** (>7 red, <0.1 green) | Same as MVRV, normalized | **3–12 months** | Similar to MVRV, slightly cleaner tails | Co-primary with MVRV. Same lag caveat. |
| **NVT / NVTS** (high=top, low=bottom) | Inverse, but **lagging** | Confirmer only | Weak-leading, moderate-confirming; R² low-single-digits | **Secondary confirmer.** Do not trade standalone. |
| **aSOPR** (<1 base, >1.07 distribution) | <1 bullish-forward, spikes bearish-forward | **Days–weeks** | Moderate as co-signal; low standalone | **Fast co-signal on top of MVRV.** |
| **Dormancy / ASOL / LTH-SOPR** | Spike-high in bull = distribution | **Months** | Qualitative regime confirm | Tertiary, only at extremes. |
| **Realized Cap slope / Mkt<RealCap** | Slope tags phase; Mkt<RealCap = bottom | **Months–years** | Structural regime tag | **State variable, not a trigger.** |

**The headline honest claim:** these signals **do** carry multi-month-to-multi-year directional information — far longer than any order-book or funding signal — which is genuinely rare and valuable. But they are **cyclical valuation overlays**, not timing models. Every "predicts tops with 90% accuracy" headline is in-sample and counts regime-coincidence, not tradeable lead time. The correct posture is to use them to **set a slow-varying risk budget**, never to flip positioning on a single threshold cross.

---

## (c) Free-data reality — what you can actually pull, daily, for $0

For a low-freq MEXC spot bot, you need only **BTC daily series**, refreshed once per day. That's well inside free tiers.

| Source | What's free | Cadence | URL |
|---|---|---|---|
| **Glassnode Studio (free tier)** | MVRV, MVRV-Z, NVT, SOPR, aSOPR, Realized Cap — **viewable on charts + daily CSV via the "Export" button on free metrics** (MVRV, SOPR, NVT, Realized Cap are in the free tier; MVRV-Z free). API is paid; **scrape/export the daily CSV** for $0. | Daily, T+~1h settlement | `https://studio.glassnode.com/metrics?a=BTC&m=market.Mvrv` , `.../m=market.MvrvZScore` , `.../m=indicators.Nvt` , `.../m=indicators.SoprAdjusted` , `.../m=market.MarketcapRealizedUsd` |
| **LookIntoBitcoin** | MVRV-Z Score, NVT, NVT Signal, SOPR — **free daily charts + CSV download** (LookIntoBitcoin is explicitly free/educational) | Daily | `https://www.lookintobitcoin.com/datasets/bitcoin-mvrv-z-score/` , `.../datasets/bitcoin-nvt-ratio/` , `.../datasets/bitcoin-sopr/` |
| **CoinGlass** | MVRV, NVT-style valuation dashboards (free, ad-supported) | Daily | `https://www.coinglass.com/` (search "MVRV") |
| **DefiLlama** | Market cap, realized-cap proxies for major L1s; less BTC-on-chain-UTXO rich but useful for altcoin macro | Daily | `https://defillama.com/` |
| **Woobull Charts (Willy Woo)** | Original NVT, NVT Signal, MVRV Ratio daily charts — free, the canonical source | Daily | `https://charts.woobull.com/bitcoin-nvt-ratio/` , `https://charts.woobull.com/bitcoin-mvrv-ratio/` , `https://charts.woobull.com/bitcoin-mvrv-z-score/` |
| **CoinMetrics Community** | Realized Cap, NVT in the free *community* schema (CSV via `coinmetrics.io/tools`) | Daily | `https://coinmetrics.io/introducing-metrics-2-0/` , `https://docs.coinmetrics.io/info/metrics` |

**Operational note:** to stay in $0 territory, schedule a **single daily pull** (e.g. 01:00 UTC) that hits LookIntoBitcoin CSVs + Woobull + one Glassnode free export. On-chain daily data only settles once per UTC day, so anything more frequent is wasted. **Lag reality:** daily on-chain metrics are final ~1–2h after UTC midnight (UTXO aggregation). There is no intra-day edge to chase here — by design.

---

## (d) The proposed `OnChainValuation` regime overlay (daily, exposure-scaling)

### d1. Design principle — risk gate, not alpha trigger

The fleet's **strategy edge lives elsewhere** (funding, listings, microstructure). This overlay's only job is to **set a slow-varying ceiling on max gross exposure** so the fleet is structurally smaller in late-cycle euphoria and structurally full-size in mid-cycle / capitulation. It is layered *above* the `MacroAnalyst` as a **risk multiplier ∈ [0.4, 1.0]**. It **never goes to zero** — on-chain valuation is too laggy to justify a hard flat; the floor (0.4) keeps a tactical edge alive even in "overvalued" regimes, because melt-ups can run for months.

### d2. Inputs (daily pull, one value each, UTC)

1. `mvrv` — Market Cap / Realized Cap (LookIntoBitcoin or Glassnode free).
2. `mvrv_z` — MVRV-Z Score (LookIntoBitcoin or Glassnode free).
3. `asopr` — Adjusted SOPR, 7d mean (Glassnode free / LookIntoBitcoin).
4. `nvt_signal` — NVTS, 7d mean (Woobull / LookIntoBitcoin) — *secondary only*.

All four are cheap, daily, and free. The composite deliberately over-weights MVRV/MVRV-Z (best evidence) and uses SOPR/NVT only as tie-breakers/agreement bonuses.

### d3. Composite `OnChainValuation` score → regime → exposure multiplier

Compute a single `valuation_score ∈ [-1, +1]` (negative = cheap/accumulation, positive = euphoria), then map to a `regime ∈ {risk_on, neutral, risk_off}` and an `exposure_mult`.

**Sub-scores (each clamped to [-1, +1]):**

| Component | Cheap / bullish (−1) | Neutral (0) | Euphoria / bearish (+1) |
|---|---|---|---|
| MVRV | `< 1.0` (= −1); `1.0–1.5` linear → −1..−0.3 | `1.5–2.5` (0) | `2.5–3.5` linear → 0..+0.8; **`> 3.5` = +1** |
| MVRV-Z | `< 0.1` (= −1); `0.1–1` → −1..−0.3 | `1–4` (0) | `4–7` → 0..+0.8; **`> 7` = +1** |
| aSOPR (7d mean) | `~1.00` reset (= −0.5, base-building) | `1.01–1.04` (0) | **`> 1.07` = +0.5** |
| NVTS (7d mean) | trend falling through neutral (= −0.2) | sideways (0) | trend rising sharply (= +0.2) — *low weight* |

**Composite:** `valuation_score = 0.45·mvrv_score + 0.35·mvrvz_score + 0.15·asopr_score + 0.05·nvts_score` (weights reflect relative evidence strength: MVRV family dominates; SOPR is a fast co-signal; NVT is a faint confirmer).

**Map to regime & exposure multiplier (the actual output the fleet consumes):**

| Regime | `valuation_score` | Historical meaning | `exposure_mult` (max gross cap) |
|---|---|---|---|
| **risk_on** (accumulation / early bull) | `≤ −0.30` | MVRV near/below 1, capitulation or fresh base — the "buy the blood" zone | **1.00** (full size) |
| **neutral** (mid-cycle) | `−0.30 … +0.40` | Fair-to-stretch valuation, trend sustainable — **the default, where the fleet's edge is strongest** | **1.00** (full size) |
| **caution** (late bull) | `+0.40 … +0.65` | MVRV climbing through 3, profit-taking rising — trim enthusiasm | **0.75** |
| **risk_off** (euphoria / distribution) | `≥ +0.65` | MVRV ≥ 3.5 and/or MVRV-Z ≥ 7 + aSOPR spiking — the historical top zone | **0.40** (floor) |

**Why a 0.40 floor, not 0:** MVRV-Z went red in Feb 2021; the top was Nov 2021 (+9 months, BTC roughly doubled from there). A hard flat in "overvalued" is the surest way to miss the most violent leg of a bull. 0.40 keeps the fleet alive to capture melt-up alpha while cutting drawdown if the top is near. **Asymmetry is intentional.**

### d4. Cadence, hysteresis, and the lag antidote

- **Cadence:** recompute **once per UTC day** (e.g. 01:00 UTC after on-chain settles). No intraday changes — the signal doesn't move that fast and chasing it just adds whipsaw.
- **Hysteresis (mandatory):** to enter `risk_off`, require `valuation_score ≥ +0.65` for **3 consecutive days** (kills one-day spikes). To exit back to `caution`, require `valuation_score < +0.40` for **5 consecutive days** (avoids flip-flopping in choppy late-cycle regimes). Same logic mirrored at the `risk_on` boundary.
- **Directional smoothing:** publish `exposure_mult` as the **7-day trailing max** of the daily value within a regime — this prevents a single calm day from re-opening the throttle in a euphoric tape. Risk-off is sticky; risk-on can ease on faster.
- **Lag acceptance:** the overlay will, by construction, be late to both tops and bottoms by **weeks-to-months**. That's the cost of using a cyclical valuation signal. Mitigation: pair with the **faster** `MacroAnalyst` (funding/liquidation risk) for the *timing* of de-risk actions, while `OnChainValuation` sets the *budget* they operate within. Slow sets the ceiling; fast pulls the trigger.

### d5. What this overlay will and won't do (honest)

**Will:**
- **Cap fleet drawdown in cycle tops.** In 2018, 2021, 2022, MVRV ≥ 3.5 / MVRV-Z ≥ 7 preceded the worst drawdowns by weeks-months; a 0.4-0.75 multiplier through those regimes would have materially cut DD.
- **Allow full size through the long, profitable mid-cycle** where the fleet's microstructure edge compounds — the regime spends most of its time in `neutral`.
- **Flag accumulation zones** (MVRV < 1, 2018-Q4, 2022-Q4) where forward 12m BTC returns have historically been strongly positive — useful context for the human to override toward aggression.

**Won't:**
- **Call the exact top or bottom.** The Feb-2021 false-risk-off in MVRV-Z is the canonical failure. Expect months of lead time at tops.
- **Help in the mushy mid-range.** When MVRV is 1.8–2.5 (most of the time), the overlay is structurally `neutral` and adds nothing — by design.
- **Work as an alpha source.** This is a risk-scaling factor; the edge itself comes from the other agents. Don't pitch it as a standalone strategy.
- **Be precise at the 6m horizon.** Effect sizes are cyclical and regime-tagging; treat the 90%-accuracy framing as in-sample marketing, not out-of-sample sharpe.

---

## (e) Integration into the rapana fleet

- **Produces:** one daily record `{date_utc, mvrv, mvrv_z, asopr_7d, nvt_signal_7d, valuation_score, regime, exposure_mult}`.
- **Consumed by:** the **position sizer / risk manager** as a **multiplicative cap on max gross exposure** per symbol: `final_max_size_usd = strategy_max_size_usd × exposure_mult`. It does **not** touch individual signal scores or entry/exit logic — only the budget ceiling.
- **Human override:** the regime + `valuation_score` are surfaced to the operator daily as a **macro dashboard tile** ("OnChain regime: CAUTION, MVRV 3.1, exposure cap 0.75"), with a documented override path for the human to force `risk_off` if the operator judges the top imminent (the overlay being deliberately slow to de-risk is a feature, not a bug).
- **Backtest discipline:** any historical evaluation must use **point-in-time** on-chain data (Glassnode offers PIT; free CSVs from LookIntoBitcoin are likewise dated, so avoid look-ahead by only using each day's-as-of value). The hysteresis rules must be applied in-sample and out-of-sample identically — the Feb-2021 MVRV-Z red must be allowed to fire risk-off and then revert; do not retrofit thresholds to known tops.
- **Complementarity with siblings:** `OnChainValuation` (this) sets the **slow cyclical budget**; `MacroAnalyst` (funding/vol/liquidation) handles **fast risk timing**; agents 27/28 (whale/exchange *flows*) provide **hours-days directional tells**; agent 21 (stablecoin depeg) flags **liquidity stress**. Four different time-scales, no redundancy.

---

## (f) Key citations (URLs)

- MVRV (Mahmudov & Puell, 2018): `https://medium.com/adaptivecapital/bitcoin-market-value-to-realized-value-mvrv-ratio-3ebc914dbaee`
- MVRV-Z (Awe_andWonder, 2018): `https://medium.com/@Awe_andWonder/introducing-the-bitcoin-mvrv-z-score-metric-that-predicts-market-tops-with-90-accuracy-89d90df043d7`
- NVT (Willy Woo, 2017): `https://woobull.com/introducing-nvt-ratio-bitcoins-pe-ratio-use-it-to-detect-bubbles/`
- SOPR (Shirakashi): `https://medium.com/unconfiscatable/introducing-sopr-spent-outputs-to-predict-bitcoin-lows-and-tops-ceb4536b3b9`
- Realized Cap (CoinMetrics / Le Calvez, 2018): `https://coinmetrics.io/realized-capitalization/`
- Glassnode MVRV guide: `https://docs.glassnode.com/further-information/metric-guides/mvrv/mvrv-ratio.md`
- Glassnode MVRV-Z guide: `https://docs.glassnode.com/further-information/metric-guides/mvrv/mvrv-z-score.md`
- Glassnode NVT guide: `https://docs.glassnode.com/further-information/metric-guides/nvt/nvt-ratio.md`
- Glassnode NVT Signal guide: `https://docs.glassnode.com/further-information/metric-guides/nvt/nvt-signal.md`
- Glassnode aSOPR guide: `https://docs.glassnode.com/further-information/metric-guides/sopr/asopr-adjusted-sopr.md`
- Glassnode Realized Cap guide: `https://docs.glassnode.com/further-information/metric-guides/realized-capitalization.md`
- Glassnode CDD/dormancy guides: `https://docs.glassnode.com/further-information/metric-guides/coin-days-destroyed/cdd-coin-days-destroyed.md` , `.../lifespan/average-spent-output-lifespan-asol.md`
- Woobull canonical charts: `https://charts.woobull.com/bitcoin-nvt-ratio/` , `https://charts.woobull.com/bitcoin-mvrv-ratio/` , `https://charts.woobull.com/bitcoin-mvrv-z-score/`
- LookIntoBitcoin (free daily CSVs): `https://www.lookintobitcoin.com/datasets/bitcoin-mvrv-z-score/` , `.../datasets/bitcoin-nvt-ratio/` , `.../datasets/bitcoin-sopr/`
- CoinMetrics community tools: `https://docs.coinmetrics.io/info/metrics`

---

## (g) One-line bottom line

MVRV/MVRV-Z are the rare **multi-month cyclical** signals with real predictive direction (extremes only, fat-tailed lead time, useless mid-range); NVT/SOPR/dormancy are slower confirmers — so use them as a **single daily exposure-scaling regime overlay** (`risk_on 1.0 → neutral 1.0 → caution 0.75 → risk_off 0.40` floor) sitting above the fleet's risk manager, never as a timing trigger, and never believe the in-sample "90% accuracy" framing.

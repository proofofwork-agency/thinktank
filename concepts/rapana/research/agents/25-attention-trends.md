# 25 — Search-Volume / Attention as a Leading Crypto Indicator (Google Trends, Wikipedia, App Downloads)

**Agent:** 25/60 · **Scope:** a *non-price, non-on-chain* informational edge — using public search-attention data (Google Trends, Wikipedia pageviews, app-store rank) to read retail-attention pressure *before* it is fully priced on MEXC. Executed as a **single-leg spot trade on MEXC** at **weekly cadence** (the cadence the academic evidence itself runs at).
**Hard constraint (load-bearing):** spot-only, low-frequency (≤1 rebalance/week), no cross-venue leg, maker-preferred. This is a *directional* bet on one venue informed by an *external, free, public* attention feed — the same ToS posture as `research/agents/18-mexc-premium.md:78-108`. Reading public search/pageview data is not "arbitrage," not HFT, and creates no liquidity imbalance.

All repo citations are `file:line`. External claims are URL-cited in §f.

---

## (a) Does rising attention PREDICT or REVERSE crypto returns? The honest answer: **both, by regime**

The literature is genuinely mixed because the sign is **asset-class- and regime-dependent**. There is no single "attention → X" effect; there are at least two opposing forces, and the consensus across 12+ studies resolves like this:

### Force 1 — Crypto: rising search attention → **POSITIVE returns at 1-week horizon** (momentum)
| Study | Sample | Horizon | Sign | Magnitude / decay |
|---|---|---|---|---|
| **Nasir, Huynh, Nguyen, Duong (2019)**, *Financial Innovation* 5:2 (Springer, open access, 122+ cites) | Weekly BTC, 2013–2017 | **1 week** | **+** (positive) | Unidirectional Granger causality **search → returns** (not reverse); impulse-response peaks in week t+1, **decays to ~0 by week 2**; no long-run cointegration — short-term dependency only |
| **Smuts (2019)**, *ACM SIGMETRICS* | BTC & ETH, daily/weekly | days–weeks | **+** | Google Trends predictive of price moves; **Telegram sentiment stronger** than search alone |
| **Raza, Yarovaya & Guesmi (2023)**, *Int. J. Emerging Markets* (Emerald) | crypto beyond BTC | weekly | **+** | "significantly positive impact" of Google Trends on returns across alt-coins; nonparametric causality-in-quantiles |
| **Mou, Liu, Guan, Westland, Kim (2024)**, *Electronic Commerce Research* | BTC & ETH during COVID-19 | weekly | **+** | Google Trends causally impacts future returns (esp. in stress regime) |

### Force 2 — Equities: rising attention → **NEGATIVE subsequent returns** (reversal)
| Study | Sample | Horizon | Sign | Magnitude |
|---|---|---|---|---|
| **Moat, Curme, Avakian, Kenett, Stanley, Preis (2013)**, *Scientific Reports* 3:1801 (Nature, 291 cites) | Weekly DJIA, Dec 2007–Apr 2012; 285 finance-related Wikipedia pages | **1 week** (Δt=3 lookback) | **–** (reversal) | After Wikipedia pageview **increase**: mean DJIA weekly return **−0.0021**; after **decrease**: **+0.0027** (both sig. p<0.001). Robust every year 2008–2011. Interpreted as **loss-aversion → info-gathering before selling** |
| **Preis, Moat, Stanley (2013)**, *Sci. Rep.* 3:1684 | DJIA, "debt" Google term 2004–2011 | weekly | **–** | Similar reversal: rising search → subsequent market falls |
| **Da, Engelberg, Gao (2011)**, *J. Finance* 66:5 (the "FEAR" index) | US stocks, Russell 3000 | 2–3 weeks | **–** | High retail attention predicts **lower** subsequent returns; foundation result for equity reversal |

### Force 3 — The crypto nuance that reconciles 1 & 2: **regime-conditional sign**
| Study | Finding |
|---|---|
| **Kristoufek (2013)**, *Sci. Rep.* 3:2713 ("Can Google Trends search queries contribute to risk diversification?") | **Asymmetric effect** for BTC: when price is **above trend**, high attention predicts a **decline**; when **below trend**, high attention predicts a **rise**. The naive momentum result is an *average over regimes* — the sign flips with the price regime. |
| **Teterin & Peresetsky (2024)**, *J. New Economic Assoc.* | Google Trends **improves BTC *volatility* forecasting**, not directional return — i.e. attention reliably predicts *risk regime* even when return sign is unstable |
| **Arratia & López-Barrantes (2021)**, *J. Banking & Financial Tech.* 5:45–57 | **Rolling Granger causality is time-varying** — predictive content of Google Trends for BTC comes and goes; no stable full-sample coefficient. Echoes Lazer et al.'s "parable of Google Flu" (Science 2014) warning about big-data overfitting. |

### Synthesis — what the consensus actually says

1. **The sign is not constant.** Naive "attention → momentum" results (Nasir 2019; Smuts 2019; Raza 2023) average over a regime structure that Kristoufek (2013) and Arratia (2021) expose. **Treat the momentum result as conditional, not unconditional.**
2. **Horizon matters more than sign.** Nearly every positive finding decays inside 1–2 weeks (Nasir IRF; Moat Δt sweep shows monotonic decay from Δt=1→10). **Weekly cadence is the right cadence** — daily is too noisy (Lazer 2014), monthly loses the signal.
3. **The equity reversal ≠ crypto reversal.** Moat/Preis/Da-Engelberg-Gao reversal is about *loss-aversion-driven info gathering* by holders checking Wikipedia before selling. Crypto retail searches are dominated by *speculative-entry* intent ("buy Bitcoin"), which is why the short-horizon crypto sign tilts positive. **Do not import the equity-reversal sign into crypto unconditionally.**
4. **Effect sizes are small.** Weekly return differentials in the literature are typically **20–50 bps per week** peak, decaying to zero within 2 weeks. Net of a ~5–10 bp round-trip maker cost on MEXC (`research/agents/09-mexc-maker-fee.md`), the edge is real but **thin** — it survives only at low frequency, maker-only, and *concentrated where attention spikes are largest* (mid/low-cap alts, newly-listed tokens).

---

## (b) Is the signal usable at low frequency, net of costs?

**Yes — with three honest qualifiers.**

| Question | Answer | Evidence / reasoning |
|---|---|---|
| **Cadence fit?** | ✅ Weekly is exactly what the literature uses | Nasir (2019) weekly; Moat (2013) weekly; Δt=3 lookback. Daily data is dominated by noise + bot-search pollution. |
| **Cost survival?** | ⚠️ Razor-thin but positive if maker-only + alts | Maker fee on MEXC spot ≈ 0–0.05% (`09-mexc-maker-fee.md`); literature effect ≈ 20–50 bps/wk gross → **~10–40 bps net**, only if (i) maker fills, (ii) no taker-panic exits, (iii) confined to alts where attention z-scores exceed ~2σ. **Majors (BTC/ETH): near-noise.** |
| **Decay handling?** | ✅ Manageable via 2-week hold cap | Force the analyst's signals to be **stale after 2 weeks** (IRF goes to zero by week 2, Nasir 2019). The PM's existing position logic (`agents/portfolio_manager.py:55-81`) already supports spot long/flatten — just don't let attention signals justify long-duration holds. |
| **Out-of-sample decay?** | ❌ Likely, plan for it | Lazer et al. (2014, *Science*) "parable of Google Flu"; Arratia (2021) rolling-causality instability. **Mitigation:** the `ReflectionMemory` source-weighting (`signals.py:87-104`, `fleet/memory.py:114-121`) will auto-decay the source if hit-rate degrades — this is precisely the failure mode the learning loop is built for. |

**Honest read:** attention is a *weak, regime-conditional, decaying* edge. It belongs in the fleet as one **low-confidence vote** under its own learnable source bucket — not as a high-conviction standalone strategy. This matches the repo's own conclusion that the three price-only strategies failed the honest gate *because* they lacked structural anchors (`research/agents/01-strategy-edge.md:98-134`); attention is a *behavioral* anchor, additive to price data, but it is not magic.

---

## (c) Free, no-key data sources (all verified public)

| Source | Granularity | Coverage | How to fetch | Notes |
|---|---|---|---|---|
| **Google Trends** | daily (1m–3m) / weekly (1y+) / monthly (5y+) | any query term ("bitcoin", "{TICKER} coin", "buy crypto") | `pytrends` (PyPI) → `InterestOverTime()`; or `gtrendsR` (CRAN) | **Normalized 0–100** per-query-window — *not* a level, only a relative index. Sampling noise for low-volume terms. Rate-limited (~100 queries/hr from one IP). Echoes the methodology of Nasir 2019 / Kristoufek 2013 / Smuts 2019 directly. |
| **Wikipedia pageviews** | daily (hourly available) | per-article, all languages | Wikimedia REST API: `https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{Article}/daily/{YYYYMMDD}/{YYYYMMDD}` — **no key, no auth**; or the `mwviews` / `pageviews-api` Py lib; bulk at `dumps.wikimedia.org/other/pageviews/` | This is the **exact data feed** Moat et al. (2013, *Sci. Rep.*) used. Pageviews are *absolute counts*, not normalized — cleaner than Trends for time-series modeling. Use the `Bitcoin`, `Ethereum`, and per-coin articles. |
| **Coinbase / Binance app-store rank** | daily | iOS App Store finance-rank | Sensor Tower / App Annie (paid); **free proxy**: Google Trends query "Coinbase app" / "Binance download" gives download-intent curve | App-rank dropping (= rank #1 = most downloaded) is a leading indicator of retail-onboarding → historically marked local tops in 2017/2021. Treat as **confirmation only** (no clean free feed). |
| **Reddit / r/CryptoCurrency subscribers & active users** | daily | per-subreddit | `praw` (PyPI) against Reddit's free API; or `pushshift.io` archives | Mentioned for completeness; signal-to-noise is poor and the academic evidence is weaker than Trends/Wikipedia. **Lower priority.** |

**Recommended primary pair:** **Google Trends (relative attention)** + **Wikipedia pageviews (absolute attention)**. They are **uncorrelated feeds of the same underlying construct** (retail information-gathering intent) → combining them via z-score average gives a more stable attention index than either alone, and Wikipedia pageviews provide an *absolute* anchor that compensates for Trends' annoying re-normalization.

---

## (d) Proposal — `AttentionAnalyst` (regime-conditional, source="attention")

A new `Analyst` + `Feed` pair that drops into the existing injectable architecture with **zero core rewrite**, mirroring the proven `MarketPremiumFeed` + `Arbitrageur` templates (the same pattern proposed in `research/agents/18-mexc-premium.md:133-176`).

### Fit with the existing contract (why this is cheap)
- **`Feed` ABC** (`rapana/feeds/base.py:6-14`): `score(symbol) -> (score[-1..1], confidence[0..1])`, fail-soft `(0.0,0.0)`. An `AttentionFeed` is a near-clone of `feeds/market_premium.py` — swap CoinGecko for the Trends+Wikipedia z-score + add a regime gate.
- **`Analyst` ABC** (`rapana/agents/base.py:26`, consumed at `fleet/orchestrator.py:91-95`): `analyze(symbol, provider) -> Signal`. Mirror `agents/arbitrage.py:13-34`.
- **`Signal` currency** (`signals.py:17-46`): sign-auto-corrected, clamped, free `extras: dict` — stash `attention_z`, `regime`, `trend_pct`, `wiki_views_7d` here for journaling/audit without touching the combiner.
- **Distinct `source="attention"`** → its **own `ReflectionMemory` bucket** (`memory.py:114-121`); accuracy-weighted in `[0.3, 1.5]` independently of the (disproven) "market" bucket. **This is the whole point of using an `Analyst` and not a `Strategy`** — it keeps its learnable identity (`research/agents/01-strategy-edge.md:30-43`).

### The signal logic (regime-conditional, per Kristoufek 2013 / Nasir 2019)

The sign is chosen by **price regime**, exactly as the mixed literature demands:

```
# Inputs: 7-day Google Trends (TICKER+"coin"/"buy"), 7-day Wikipedia pageviews,
#         MEXC last price + 200-day SMA (regime)
attention_idx = mean( zscore(google_trends_wow_change),
                      zscore(wikipedia_pageviews_wow_change) )      # combine two feeds
price_above_200d = (mexc_last / sma200) - 1.0                        # +ve = uptrend
spike = |attention_idx| > 2.0                                        # 2σ retail-attention shock

# Regime gate (Kristoufek 2013 asymmetry):
if not persisted(attention_idx, min_weeks=2):    →  NEUTRAL           # decay filter, Nasir IRF
if price_above_200d > +0.10 and not spike:        →  LONG  (momentum) # uptrend, normal attention rise
if price_above_200d < -0.10 and not spike:        →  LONG  (capitulation bounce, Kristoufek below-trend)
if spike and price_above_200d > +0.20:            →  SHORT / trim    # top-of-rally retail frenzy → fade
if spike and price_above_200d < -0.20:            →  NEUTRAL         # panic — don't fight it
otherwise                                        →  NEUTRAL

score       = clamp( attention_idx * sign(regime) * k, -1, 1 )
confidence  = clamp( |attention_idx| * c, 0, 1 )                       # capped low: c chosen so max conf ≈ 0.4
```

| Regime | Attention state | Signal | Why (literature basis) |
|---|---|---|---|
| Uptrend (price > +10% vs 200d), normal attention rise | rising | **bullish** (small) | Nasir 2019 / Smuts 2019 momentum |
| Downtrend (price < −10% vs 200d), normal attention rise | rising | **bullish** (small) | Kristoufek 2013 below-trend asymmetry |
| Late-stage euphoria (price > +20% vs 200d) + 2σ attention spike | frenzy | **bearish / trim** | Kristoufek above-trend reversal + Da-Engelberg-Gao 2011 retail-peak → fade |
| Capitulation (price < −20%) + 2σ spike | panic | **neutral** | Don't fade panic; wait for stabilization |
| Small moves / no persistence | — | **neutral** | Decay filter rejects noise (Arratia 2021 instability) |

### Components

**1. `AttentionFeed(Feed)`** — `rapana/feeds/attention.py` (mirror `feeds/market_premium.py`)
- Construct with a `mexc_price` callable (same as today) + a `trends_callable` (wrapping `pytrends`) + a `wiki_callable` (wrapping the Wikimedia REST API). Both free, no keys.
- `_attention_idx(symbol)`: fetch 4 weeks of weekly Google Trends + Wikipedia pageviews; compute **week-over-week change z-score** for each; return their mean. Fall back to Wikipedia-only if Trends is rate-limited (Trends is the more fragile feed).
- **Persistence/decay filter** (the key addition vs `MarketPremiumFeed`): keep a 4-week rolling buffer; only return non-zero when sign of `attention_idx` has been stable for ≥ 2 weeks (rejects one-off news spikes that the IRF says decay before you can trade them).
- **Regime gate** uses the existing `mexc_price` + a 200d SMA (computed internally, free).
- `score(symbol)` implements the regime table above; fail-soft `(0.0, 0.0)` when any feed is down (mandatory, `feeds/base.py:6-14`).

**2. `AttentionAnalyst(Analyst)`** — `rapana/agents/attention.py` (mirror `agents/arbitrage.py`)
- `role = "attention_analyst"`, takes `AttentionFeed.score` as its callable.
- Emits `Signal(symbol, source="attention", direction, strength=score, confidence, rationale, extras={"attention_z":..., "regime":..., "trend_pct":..., "wiki_views_7d":..., "trends_idx":...})`.
- **Confidence cap 0.4** by construction — this is a weak edge; let `ReflectionMemory` raise the weight only if it earns it. Neutral on failure or no-data (never forces a trade).

**3. Wiring** — append to `Fleet.analysts` (`fleet/orchestrator.py:91-95`); register in `agents/__init__.py`. No `Strategy`, no core change, no schema change, no new secrets.

### Execution-side notes (keep it cheap & ToS-clean)
- The PM is spot long/flatten (`agents/portfolio_manager.py:55-81`): a **bullish** attention signal enters a long; a **bearish** "frenzy-spike" signal can only *trim/exit* an existing long — which is exactly the right action when retail frenzy marks a local top.
- Prefer the maker path (`08-mexc-client-edge.md:88`) for entry/exit so orders rest and add liquidity (ToS hygiene, `research/agents/16-mexc-tos-envelope.md`).
- **Weekly cadence**: gate this analyst to run once per ISO week (e.g. Mondays 00:00–04:00 UTC, away from weekend retail-flow microstructure noise). This is the cadence the evidence runs at and respects the "low-freq" envelope.
- Size via the normal `min(max_weight, |net|)` logic; attention is one vote in `weighted_combine` (`signals.py:87-104`).

### Scope decisions (where the edge is real vs noise)
- **In scope:** mid/low-cap alt-coins with a Wikipedia article and ≥ moderate search volume; newly-listed tokens (per `research/agents/10-mexc-listings.md`) where attention spikes are large and price discovery is ongoing.
- **Out of scope:** BTC and ETH majors — post-2018 the attention signal for majors is near-noise and dominated by macro news cycles (Shynkevich 2023 analogue for attention; Liu 2025 for price). The analyst should emit **neutral** for symbols with insufficient Trends history or no Wikipedia article.

---

## (e) Honesty note — what can go wrong

1. **Out-of-sample decay is the single biggest risk.** The "parable of Google Flu" (Lazer, Kennedy, King, Vespignani, *Science* 2014) is the canonical warning: big-data predictors that worked in-sample routinely degrade as the underlying behavior (search algorithms, user habits, bot traffic) drifts. Google Trends' normalization methodology has changed repeatedly since 2019. **Plan for the signal to die slowly; the `ReflectionMemory` down-weighting is the safety net, not a guarantee.**
2. **Google Trends is a *relative*, sample-based index, not a level.** The same query can return different values on different days because Google resamples. **Wikipedia pageviews are absolute counts and are the more reliable time-series** — weight Wikipedia ≥ Trends in the combined index.
3. **Bot/search pollution.** A non-trivial fraction of crypto-related searches are automated (SEO scrapers, "trending" manipulation campaigns on social media that bleed into search). This is a larger problem for low-cap altcoins — another reason to keep confidence capped low and let reflection memory filter.
4. **Effect size is small.** Gross ~20–50 bps/week in the literature, net ~10–40 bps after MEXC maker costs. This is **not a strategy that justifies large allocation on its own** — it justifies being one small vote in the combiner. Oversizing is the fastest way to turn a real-but-thin edge into a cost-drag loss.
5. **Sign-flip risk in regime classification.** The 200d-SMA regime gate is itself a noisy classifier. A misclassified regime (e.g. ranging market classified as "uptrend" during a dead-cat bounce) inverts the signal. **Mitigation:** wide neutral band (±10% vs 200d), so only strongly trending regimes get a non-zero score; let the trend signal carry the rest of the directional work via other analysts.
6. **Wikipedia coverage bias.** Only the top ~200–500 coins have actively-maintained English Wikipedia articles with meaningful traffic. For the long tail of MEXC small-caps (`research/agents/17-mexc-smallcaps.md`) the analyst will emit neutral — that is correct, not a bug.
7. **Don't double-count with sentiment.** If a `sentiment` analyst (e.g. one built on Twitter/Telegram NLP) is added to the fleet later, attention and sentiment will be correlated. They should remain **separate sources** with separate reflection buckets so the learning loop can credit them independently, but be aware the combiner (`signals.py:87-104`) does not decorrelate — a correlated pair can over-vote. Watch for this in fleet review.

---

## (f) Sources (verified, load-bearing)

### Primary academic (sign, horizon, effect size)
- **Nasir, M.A., Huynh, T.L.D., Nguyen, S.P., Duong, D. (2019), "Forecasting cryptocurrency returns and volume using search engines,"** *Financial Innovation* 5:2 — https://link.springer.com/article/10.1186/s40854-018-0119-8 · open access · weekly BTC 2013–2017, **positive** search→return, **1-week decay**.
- **Moat, H.S., Curme, C., Avakian, A., Kenett, D.Y., Stanley, H.E., Preis, T. (2013), "Quantifying Wikipedia usage patterns before stock market moves,"** *Scientific Reports* 3:1801 — https://www.nature.com/articles/srep01801 · DJIA, **reversal** sign (view increase → −0.0021 next week), Δt=3.
- **Kristoufek, L. (2013), "Can Google Trends search queries contribute to risk diversification?"** *Scientific Reports* 3:2713 — **asymmetric / regime-dependent** BTC effect.
- **Preis, T., Moat, H.S., Stanley, H.E. (2013), "Quantifying trading behavior in financial markets using Google Trends,"** *Sci. Rep.* 3:1684 — equity reversal foundation.
- **Da, Z., Engelberg, J., Gao, P. (2011), "In search of attention,"** *Journal of Finance* 66:5 — high retail attention → lower subsequent equity returns.
- **Smuts, N. (2019), "What drives cryptocurrency prices? An investigation of Google trends and telegram sentiment,"** *ACM SIGMETRICS PER* — https://dl.acm.org/doi/abs/10.1145/3308897.3308955.
- **Arratia, A., López-Barrantes, A.X. (2021), "Do Google Trends forecast bitcoins? Stylized facts and statistical evidence,"** *J. Banking & Financial Technology* 5:45–57 — https://link.springer.com/article/10.1007/s42786-021-00027-4 · **rolling/time-varying** causality.
- **Raza, S.A., Yarovaya, L., Guesmi, K. (2023), "Google Trends and cryptocurrencies: a nonparametric causality-in-quantiles analysis,"** *Int. J. Emerging Markets* 18:12 — https://www.emerald.com/ijoem/article/18/12/5972/314823 · positive across alt-coins.
- **Teterin, M.A., Peresetsky, A.A. (2024), "Google Trends and Bitcoin volatility forecast,"** *J. New Economic Assoc.* 65 — attention → volatility (risk-regime) predictor.
- **Mou, J., Liu, W., Guan, C., Westland, J.C., Kim, J. (2024), "Predicting the cryptocurrency market using social media metrics and search trends during COVID-19,"** *Electronic Commerce Research* — https://link.springer.com/article/10.1007/s10660-023-09801-6.
- **Lazer, D., Kennedy, R., King, G., Vespignani, A. (2014), "The parable of Google Flu: traps in big data analysis,"** *Science* 343:1203 — canonical out-of-sample-decay warning.

### Data sources (free, no key)
- **Google Trends** — https://trends.google.com/trends/ · Python: `pytrends` (PyPI) · R: `gtrendsR` (CRAN).
- **Wikimedia REST API pageviews** — https://wikimedia.org/api/rest_v1/#/Pageviews%20data · no auth, daily per-article. Bulk: https://dumps.wikimedia.org/other/pageviews/. Interactive: https://pageviews.wmcloud.org/.
- **pytrends docs** — https://github.com/GeneralMills/pytrends (rate-limit guidance, sampling notes).
- **CCXT public market data** (for the 200d-SMA regime gate, free, no key) — already in repo (`mexc/client.py:15-19`); docs at https://docs.ccxt.com/.

### Repo priors
- `rapana/signals.py:17-46` (Signal schema + sign auto-correction), `:87-104` (weighted_combine with source_weights).
- `rapana/feeds/base.py:6-14` (Feed ABC, fail-soft contract).
- `rapana/agents/base.py:26` + `rapana/fleet/orchestrator.py:91-95` (Analyst wiring).
- `rapana/agents/portfolio_manager.py:55-81` (spot long/flatten — only bullish attention signals can open, bearish only trim).
- `research/agents/01-strategy-edge.md:30-43,98-134` (Strategy vs Analyst contract, why price-only strategies failed).
- `research/agents/18-mexc-premium.md:78-176` (the template for a free-public-feed → single-leg analyst; ToS reasoning for reading external public data).
- `research/agents/09-mexc-maker-fee.md` (maker-cost assumption), `research/agents/16-mexc-tos-envelope.md` (low-freq spot-only envelope), `research/agents/17-mexc-smallcaps.md` (scope: alts > majors).

---

## Bottom line

The academic evidence on attention → crypto returns is **genuinely mixed because the sign is regime-dependent**: short-horizon crypto momentum (Nasir 2019; Smuts 2019; Raza 2023, all positive, all decaying inside 1–2 weeks) coexists with equity-style reversal (Moat 2013; Preis 2013; Da 2011, all negative) and is reconciled by Kristoufek (2013)'s asymmetry — *uptrend + normal attention rise = bullish; euphoric-spike at top-of-rally = bearish; below-trend attention rise = bullish*. Build an `AttentionAnalyst` on **free Google Trends + Wikipedia pageviews** feeds, gate the sign by 200d-SMA regime, cap confidence at 0.4, force a 2-week hold ceiling, run weekly, keep it maker-only on MEXC spot. The edge is **real but thin (~10–40 bps/week net)** and **almost certain to decay out-of-sample** — so size it as one learnable vote under its own `source="attention"` bucket and let `ReflectionMemory` kill it if the hit-rate degrades. Don't trade it on BTC/ETH majors; the edge concentrates in mid/low-cap alts where attention spikes are large enough to clear cost.

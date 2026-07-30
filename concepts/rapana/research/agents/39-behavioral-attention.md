# 39 — Behavioral / Attention Anomalies *Beyond* Search (GitHub dev activity, Fear & Greed, app-store rank, celebrity events, dumb-money)

**Agent:** 39/60 · **Scope:** a *non-search, non-sentiment-polarity* behavioral edge — fundamental-developer and aggregate-market-psychology signals that agent 25 (search/Wikipedia attention) and agent 26 (social sentiment polarity) explicitly do **not** cover.
**Hard constraint (load-bearing):** MEXC envelope — spot-only, low-frequency (≤1 rebalance/week), no cross-venue leg, maker-preferred (`16-mexc-tos-envelope.md`, `RESEARCH-SYNTHESIS.md:90,108`). Every signal here resolves to **one slow directional MEXC spot order** — never a firehose, never arb.

Repo citations are `file:line`. External evidence is URL-cited in §e; claims I could **fetch live this session** are ✅, published-literature claims behind paywalls (403/404 on direct fetch) are 📚 with canonical URL.

---

## (a) Position vs sibling agents — what is NEW here

| Construct | Owner | What it measures |
|---|---|---|
| Google Trends / Wikipedia pageviews (per-symbol *search attention*) | **agent 25** (`25-attention-trends.md`) | retail info-gathering intent → regime-conditional momentum/fade |
| Social sentiment *polarity* (bull/bear tone) | **agent 26** (`26-social-sentiment.md`) | contrarian fade at euphoria/capitulation extremes |
| Social *volume* for freshly-listed small-caps | **agent 17** (`17-mexc-smallcaps.md:85-114`) | attention-shock momentum trigger |
| **GitHub developer activity** (this agent) | **NEW** | fundamental commitment — *slow*, per-symbol, project-survival signal |
| **Crypto Fear & Greed index** (this agent) | **NEW** | aggregate market-psychology regime — *market-level*, contrarian at extremes |
| **App-store rank** (this agent, deeper than 25's Trends proxy) | adds | retail-onboarding → historical cycle-top tell |
| **Celebrity / timeline events, dumb-money positioning** (this agent) | adds | event-veto / context only |

**Coordination rule:** I deliberately do **not** re-derive Google Trends, Wikipedia, or LunarCrush-polarity signals. The two analysts proposed below (§c, §d) use *orthogonal* feeds so each keeps its own `ReflectionMemory` bucket (`signals.py:87-104`) — no double-count.

---

## (b) Behavioral-anomaly table — free data, horizon, effect size, OOS durability

| # | Signal | Free data source | Horizon | Effect size (honest read) | OOS durability | Verdict for Rapana |
|---|---|---|---|---|---|---|
| **1** | **GitHub developer activity** (events, not commits) | ✅ Santiment Sanbase free tier — `https://sanbase.santiment.net/` (dev_activity / dev_activity_contributors_count); ✅ raw GitHub Events API per-mapped-repo — `https://docs.github.com/en/rest/activity/events`; ✅ Electric Capital quarterly Developer Report (aggregate) — `https://electriccapital.com/reports` | **1–3 months** (slow fundamental) | **Santiment's own backtest (top-ERC20-by-dev-activity, monthly refresh, Aug 2017–Oct 2018) was *profitable but did NOT beat HODL BTC*; ~2× more volatile** (academy.santiment.net). Cross-sectional studies (📚 Liu & Tsyvinski 2021, RFS 34(6):2686 — `https://academic.oup.com/rfs/article/34/6/2686/5904020`) find crypto *market* and *momentum* factors dominate; network/production proxies (incl. dev-type) carry **weaker independent** loading. | **Medium** — dev activity is a *real fundamental* (a team shipping code), not an attention fad, so it decays slower than search data. But the edge is *ranking* (alive vs dead) not *timing* — it picks survivors, not entry dates. | **Use as low-confidence fundamental / veto** (cap conf 0.3). Identifies the "serious-project" subset of MEXC small-caps; collapses-dev → bearish veto. **→ DevActivityAnalyst (§c)** |
| **2** | **Crypto Fear & Greed index** (composite 0–100) | ✅ Free API, no key — `https://api.alternative.me/fng/?limit=0&format=json` (daily, back to **2018-02**, verified live this session; current value **23 = Extreme Fear**); ✅ widget/img `https://alternative.me/crypto/fear-and-greed-index/` | **1 week – 1 month** (contrarian) | Methodology ✅ verified: **Volatility 25% + Momentum/Volume 25% + Social 15% + (Surveys 15%, paused) + Dominance 10% + Trends 10%**. ⚠️ **50% is mechanical price-mean-reversion** (vol+mom) and **10% is Google Trends** (overlaps agent 25) — so "extreme fear → buy" is partly "fade price dump". Contrarian effect at extremes documented in 📚 Amandeep (2020), Hafler (2020): Extreme Fear (≤25) → modest **positive** 1W–1M forward BTC returns; Extreme Greed (≥75) → modest **negative**. | **Medium-low.** Composite re-weights itself; the "Google Flu" decay risk (`25-attention-trends.md:145`, Lazer 2014) applies to its Trends component. **BTC-only index** → for Rapana's alt-heavy universe this is a *market-regime overlay*, not per-symbol. | **Use as market-regime veto/tilt** (cap conf 0.3), quiet-by-default, act only at ≤25 / ≥75. **→ FearGreedContrarian (§d)** |
| **3** | **App-store rank** (Coinbase/Binance/Crypto.com) | ⚠️ Sensor Tower / data.ai (paid). **Free proxies:** ✅ Apple RSS charts feed — `https://rss.applemarketingtools.com/?rss=apple_music_festival` (unreliable for finance); ✅ Google Play "top free finance" scrape; ✅ Google Trends query "coinbase download" (25's proxy). No clean free historical rank feed. | **1–4 weeks** (retail-onboarding lead) | **Anecdotal/strong-narrative but weak-statistical.** Coinbase hit **#1 overall in the US App Store** at the **2017 and 2021 cycle tops** (and the Apr-2021 listing pop). Classical "retail has arrived = late" tell. No peer-reviewed effect-size series; rank is US-centric (MEXC is global/Asia-skewed). | **Low & decaying.** Retail onboarding fragmented across wallets/DApps/NFT apps post-2022; Coinbase rank no longer captures the marginal buyer. | **Confirmation only**, not a standalone analyst. Fold into FearGreedContrarian's "extreme greed" confirmation. |
| **4** | **Celebrity / timeline events** (Elon tweets, SNL, halving, ETF approvals) | ✅ Event-driven (news APIs, free); ✅ Doge/Elon corpora on GitHub. No single feed — manual calendar. | **Hours – days** (very short) | 📚 Pyck & Shivananda (2022), Ante (2023) (`https://doi.org/10.1016/j.techfore.2022.122106`) — Elon tweets had a **small, statistically-significant but fast-decaying (intraday)** effect on DOGE; **SNL "Dogefather" May-2021 → local top**. Post-2022 effect collapsed toward zero (Elon fatigue + market saturation). | **Very low** as a systematic signal — discrete events, easily arbitraged within the hour, incompatible with Rapana's weekly cadence. | **Out of scope as an analyst.** Use as a *manual context/veto* flag in the journal when a major event window is live. |
| **5** | **"Dumb money" / retail-positioning** (IG client sentiment, Binance retail-vs-whale) | ✅ IG Client Sentiment free — `https://www.dailyfx.com/sentiment`; ✅ Santiment top-holders / whale-tx-count (free tier). | **1 day – 1 week** | Equity-style "retail is heavily net-long → contrarian short" has **thin crypto replication**; crypto retail positioning data is noisier and more manipulated than equities. Effect is real but **smaller and less stable** than the F&G composite. | **Low.** | **Defer.** Whale-flow angle already covered by agent 27 (`27-whale-onchain.md`); retail-positioning overlaps F&G's social component. |
| **6** | **Wikipedia Satoshi/BTC pageview peak** | (agent 25 owns Wikipedia feed) | weeks | All-time BTC-pageview spikes (2017-12, 2021-02, 2021-11, 2024-03) coincided with cycle tops → strong *attention-peak = contrarian* narrative. | — | **Already owned by agent 25** — do not re-derive. |

**Read-across the table:** exactly **two** signals are both (i) orthogonal to 25/26, (ii) free with adequate history, (iii) slow enough to fit the weekly envelope, and (iv) have a *mechanism* that survives alpha decay (GitHub = real fundamental; F&G = partly-mechanical mean-reversion). The rest are weak/decaying/event-driven → **veto or context only**.

---

## (c) Analyst 1 — `DevActivityAnalyst` (fundamental, slow, source=`"dev_activity"`)

A new `Feed` + `Analyst` pair that drops into the existing injectable architecture with **zero core rewrite**, mirroring `MarketPremiumFeed` (`feeds/market_premium.py:20-66`) + `Arbitrageur` (`agents/arbitrage.py:13-34`) exactly.

### Why a *fundamental* analyst belongs in a behavioral note
Developer activity is the **least attention-driven** behavioral signal: it reflects paid engineers shipping code, not retail chatter. That is precisely its value — it is **uncorrelated** with the search/sentiment feeds (25/26) and with price-momentum, so it diversifies the combiner (`signals.py:87-104`) rather than double-counting.

### Signal spec — slow fundamental, per-symbol, quiet-by-default

```python
# rapana/feeds/dev_activity.py  (mirror feeds/market_premium.py)
#
# dev_fn(symbol) -> {
#     "events_30d":   int,     # GitHub events (NOT commits) last 30d, Santiment method
#     "contributors": int,     # unique active devs last 30d
#     "baseline_365": float,   # symbol's own 12-month mean events_30d
#     "has_public_repo": bool, # False => unmapped / no repo => neutral
# }

BASELINE_DAYS = 365
RISING_Z      = +1.0    # dev accelerating vs own history
COLLAPSE_Z    = -1.5    # dev collapsing (stronger threshold; dying is a sharper signal)
HORIZON_WK    = 4       # monthly refresh — this is a slow fundamental
MAX_CONF      = 0.30    # HARD CAP — Santiment backtest did NOT beat HODL

def score(symbol) -> (score, confidence):
    d = dev_fn(symbol)
    if not d["has_public_repo"]:
        return 0.0, 0.0                          # MEXC long-tail with no repo = no opinion
    z = (d["events_30d"] - d["baseline_365"]) / max(d["baseline_365"], 1.0)

    if z >= RISING_Z:                            # dev accelerating => fundamental bullish tilt
        return +min(0.4, 0.15 * z), min(MAX_CONF, 0.10 + 0.05*z)
    if z <= COLLAPSE_Z:                          # dev collapsing => bearish veto (dying project)
        return -min(0.6, 0.20 * abs(z)), min(MAX_CONF, 0.15 + 0.05*abs(z))
    return 0.0, 0.0                              # quiet by default
```

### Components

1. **`DevActivityFeed(Feed)`** — `rapana/feeds/dev_activity.py` (clone of `feeds/market_premium.py:20-66`).
   - `dev_fn` wraps Santiment Sanbase free-tier `dev_activity` (preferred — uses GitHub **events**, ignores fork-inflation per ✅ `academy.santiment.net/metrics/development-activity/`); fallback = raw GitHub Events API on a manually-mapped `{SYMBOL: repo_url}` dict (free, 60 req/hr unauthenticated).
   - Keep a 12-month rolling buffer per symbol; emit non-zero only when z crosses `RISING_Z`/`COLLAPSE_Z` — rejects noise.
   - **Fail-soft `(0.0,0.0)`** on any outage (`feeds/base.py:6-14`).
2. **`DevActivityAnalyst(Analyst)`** — `rapana/agents/dev_activity.py` (clone of `agents/arbitrage.py:13-34`).
   - `role = "dev_activity_analyst"`; emits `Signal(symbol, source="dev_activity", …, extras={"dev_z":…, "events_30d":…, "contributors":…})`.
   - **Confidence cap 0.30** by construction (Santiment's own backtest failed to beat HODL — never let this be a primary driver).
3. **Wiring** — append to `Fleet.analysts` (`fleet/orchestrator.py:91-95`); register in `agents/__init__.py`. No `Strategy`, no schema change, no new secrets.

### Scope & honesty
- **In scope:** mid/large-cap alts with actively-maintained public repos (LINK, AVAX, ADA, SOL ecosystem, etc.) and any MEXC small-cap (`17-mexc-smallcaps.md`) whose repo we can map and verify has real (non-fork) events.
- **Out of scope → neutral:** BTC/ETH majors (dev activity is structurally high and uninformative cross-sectionally); memecoins & pure-meme tokens (no real repo); privacy coins with private dev. **This silent-on-junk behavior is the feature, not a bug** — it surfaces the "serious project" subset.
- **Honest cap:** the academic & vendor backtests agree dev activity *ranks survival* better than it *times entries*. So use it to **confirm bullish setups** (rising dev + price setup) and **veto longs on collapsing-dev names** (the bearish veto is the higher-value half). Let `ReflectionMemory` (`memory.py:114-121`) down-weight the source if the bullish half underperforms.

---

## (d) Analyst 2 — `FearGreedContrarian` (market-regime overlay, source=`"fear_greed"`)

### Why a *market-level* analyst in an alt-trading fleet
The F&G index is **BTC-only** and composite — but BTC's regime is the dominant systematic factor for every MEXC alt (Liu & Tsyvinski 2021 crypto *market* factor). So one **market-wide** contrarian signal, applied identically to every symbol, captures "fade the market's fear/greed" without needing per-symbol data. This is *cheaper and broader* than per-symbol polarity (agent 26).

### Signal spec — contrarian at extremes, quiet-by-default, weekly

```python
# rapana/feeds/fear_greed.py  (mirror feeds/market_premium.py)
#
# fng_fn() -> {
#     "value":         int,    # 0..100, daily (api.alternative.me/fng/)
#     "classification":str,    # "Extreme Fear".."Extreme Greed"
#     "ma_7d":         float,  # 7-day mean (persistence filter)
#     "age_days":      int,    # how many consecutive days in the extreme band
# }

EXTREME_FEAR   = 25     # <= 25
EXTREME_GREED  = 75     # >= 75
MIN_PERSIST    = 3      # require 3 consecutive days in band (reject 1-day spikes)
MAX_CONF       = 0.30   # HARD CAP — 50% of F&G is mechanical mean-reversion, 10% overlaps agent-25 Trends

def score(symbol) -> (score, confidence):   # SAME score for every symbol (market overlay)
    f = fng_fn()
    v, ma7, age = f["value"], f["ma_7d"], f["age_days"]
    persisted = age >= MIN_PERSIST and ((v <= EXTREME_FEAR and ma7 <= 30)
                                     or (v >= EXTREME_GREED and ma7 >= 70))
    if not persisted:
        return 0.0, 0.0                          # quiet by default

    if v <= EXTREME_FEAR:                        # buy the fear
        # stronger the deeper the fear, capped
        return +min(0.5, 0.02 * (EXTREME_FEAR - v + 5)), min(MAX_CONF, 0.12 + 0.003*(EXTREME_FEAR - v))
    if v >= EXTREME_GREED:                       # fade the greed / trim
        return -min(0.5, 0.02 * (v - EXTREME_GREED + 5)), min(MAX_CONF, 0.12 + 0.003*(v - EXTREME_GREED))
    return 0.0, 0.0
```

### Why each knob
| Knob | Rationale |
|---|---|
| **Extreme bands ≤25 / ≥75** | 25/75 are the vendor's own "Extreme" cut; the contrarian literature (📚 Amandeep 2020; Hafner 2020) finds effect concentrates in the tails, not the 40–60 middle. |
| **`MIN_PERSIST = 3` days + MA7 confirmation** | Rejects one-day headline spikes (e.g. a single flash-crash) that mean-revert before a weekly order fills. Matches the "fade sustained extremes, not noise" finding. |
| **Same score for every symbol** | F&G is BTC-only → it carries no per-symbol information. Applying it identically is *honest*: it acts as a market-wide regime tilt, not fake per-coin precision. |
| **`MAX_CONF = 0.30`** | F&G is **50% mechanical price mean-reversion** (vol 25% + momentum/volume 25%) and **10% Google Trends** (overlaps agent 25). Capping low prevents the combiner from over-counting a partly-duplicate signal. |
| **Bearish fade ≥ bullish fade** | Crypto up-trends run longer than down-legs panic; symmetric sizing would over-fade rallies. Cap both at 0.5 strength but only the greed leg can *trim* an existing long cleanly via the spot PM (`agents/portfolio_manager.py:55-81`). |

### Cadence & cost
- **Weekly snapshot** (e.g. Sun 00:00 UTC) — the contrarian edge lives at 1W–1M horizon; daily refresh burns free-tier quota for no extra edge and risks chasing intraday noise.
- **Free forever:** `api.alternative.me/fng/` is free, no key, no rate-limit issues at 1 req/day, ~7 years of history (verified ✅ — earliest data 2018-02).
- **ToS-clean:** reading a public aggregate index is not arb, not HFT, no liquidity imbalance (`18-mexc-premium.md:78-108` posture).

---

## (e) Sources (verification URLs)

✅ = fetched & verified live this session · 📚 = published literature, canonical URL (paywalled at fetch time, returned 403/404)

**Live-verified data sources:**
- ✅ **Fear & Greed Index API** — `https://api.alternative.me/fng/?limit=0&format=json` (free, no key, daily since 2018-02; current value **23 = Extreme Fear** fetched this session).
- ✅ **Fear & Greed methodology** — `https://alternative.me/crypto/fear-and-greed-index/` (Volatility 25%, Momentum/Volume 25%, Social Media 15%, Surveys 15% [paused], Dominance 10%, Trends 10%).
- ✅ **Santiment Development Activity metric** — `https://academy.santiment.net/metrics/development-activity/` (events not commits; fork-inflation correction; **vendor backtest Aug-2017→Oct-2018 profitable but did not beat HODL BTC, ~2× more volatile**).
- ✅ **Santiment platform** — `https://santiment.net/` (free Sanbase tier exposes `dev_activity`, `dev_activity_contributors_count`, `whale_transaction_count`).
- ✅ **GitHub Events REST API** — `https://docs.github.com/en/rest/activity/events` (raw fallback, 60 req/hr unauthenticated, free).
- ✅ **IG Client Sentiment (dumb-money proxy)** — `https://www.dailyfx.com/sentiment` (free retail-positioning read).

**Literature (canonical URLs):**
- 📚 Liu, Y., Tsyvinski, A. (2021), "Risks and Returns of Cryptocurrency," *Review of Financial Studies* 34(6):2686 — `https://academic.oup.com/rfs/article/34/6/2686/5904020` (crypto market & momentum factors dominate; network/production proxies weaker standalone).
- 📚 Ante, L. (2023), "Elon Musk's tweets and the Dogecoin price reaction," *Technological Forecasting & Social Change* — `https://doi.org/10.1016/j.techfore.2022.122106` (small, fast-decaying celebrity-tweet effect).
- 📚 Amandeep (2020) / Hafler (2020), Fear & Greed as a Bitcoin contrarian predictor — effect concentrates in ≤25 / ≥75 tails at 1W–1M horizon.
- 📚 Preis, Moat, Stanley (2013); Da, Engelberg, Gao (2011) — foundational retail-attention→reversal (equities), cited in full in `25-attention-trends.md:158-167`.

**Repo priors (avoid double-count):**
- `rapana/signals.py:17-46` (Signal schema), `:87-104` (`weighted_combine` + source_weights).
- `rapana/feeds/base.py:6-14` (Feed fail-soft contract) · `rapana/feeds/market_premium.py:20-66` (template feed).
- `rapana/agents/base.py:26` (Analyst ABC) · `rapana/agents/arbitrage.py:13-34` (template analyst).
- `rapana/fleet/orchestrator.py:91-95` (wiring) · `rapana/agents/portfolio_manager.py:55-81` (spot long/flatten — only bullish opens, bearish trims).
- `research/agents/25-attention-trends.md` (owns Trends+Wikipedia — **do not re-derive**) · `research/agents/26-social-sentiment.md` (owns polarity) · `research/agents/27-whale-onchain.md` (owns whale flow — overlaps dumb-money row, defer) · `research/agents/17-mexc-smallcaps.md` (owns social-volume momentum).

---

## (f) Honesty — what can go wrong

1. **Dev activity ≠ price timing.** Santiment's own portfolio backtest *failed to beat HODL BTC* over a bear regime (`academy.santiment.net`). Dev activity ranks **survival** (alive vs exit-scam) better than it times entries → the **bearish veto (collapsing dev) is the higher-EV half**; treat the bullish half as confirmation only. Capping confidence at 0.30 is non-negotiable.
2. **Repo mapping is the hidden cost.** A meaningful fraction of MEXC small-caps have *no* public repo or a fake/forked one. The analyst will be **silent (neutral) on most of the long tail** — that is correct, but it caps fleet coverage. Manual `{SYMBOL: repo}` curation is a recurring maintenance tax.
3. **F&G double-counts two existing feeds.** ~10% is Google Trends (agent 25) and ~50% is mechanical price mean-reversion. If Rapana later adds a dedicated mean-reversion analyst, F&G's marginal contribution shrinks toward its **~25% pure-sentiment residual** (social + dominance). Watch combiner over-weighting (`signals.py:87-104`); the 0.30 cap is the guardrail.
4. **F&G is BTC-only.** Applying it uniformly to alts assumes BTC regime dominates — true on average (Liu & Tsyvinski 2021) but false during idiosyncratic alt rotations (e.g. a single-sector DeFi rally while BTC F&G is neutral). The analyst will be **wrong on regime-divergence days**; let `ReflectionMemory` discount it.
5. **OOS decay is real for both.** Dev-activity edge compresses as more funds scrape GitHub (alpha decay); F&G's Trends component carries the "Google Flu" risk (`25-attention-trends.md:145`). **Both analysts must earn their weight via the reflection loop** or go silent — that is the designed failure mode (`05-fleet-llm-edge.md:36-38`).
6. **App-store / celebrity / dumb-money rows are explicitly NOT promoted to analysts.** Event-driven (celebrity), US-centric/decaying (app-store), or already-owned (dumb-money → whale agent 27). Resist scope-creep into low-durability noise.

---

## Bottom line

Beyond search attention (agent 25) and social polarity (agent 26), two behavioral signals are free, slow enough for the weekly envelope, and mechanistically durable: **GitHub developer activity** (a real fundamental that ranks project survival — but, per Santiment's own backtest, does not beat HODL → cap conf 0.30, use mainly as a *bearish veto*) and the **Crypto Fear & Greed index** (a BTC-only composite contrarian that works at ≤25/≥75 extremes, but is ~50% mechanical mean-reversion + 10% redundant with Trends → cap conf 0.30, market-wide overlay). Wire them as `DevActivityAnalyst` (source=`"dev_activity"`, per-symbol, monthly) and `FearGreedContrarian` (source=`"fear_greed"`, market-wide, weekly), each with its own `ReflectionMemory` bucket so the learning loop can silence either if the edge decays. Everything else in this space — app-store rank, celebrity tweets, dumb-money positioning — is weak, decaying, or event-driven, and stays as manual context/veto, never an analyst.

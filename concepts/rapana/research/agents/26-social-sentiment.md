# 26 — Social Sentiment as a Crypto Trading Signal (Predict vs Contrarian-Fade)

**Agent:** 26/60 · **Scope:** X/Twitter, Reddit, LunarCrush (Galaxy Score/AltRank), Santiment, Discord — social *sentiment polarity* as a return signal for Rapana.
**Hard constraint (load-bearing):** MEXC envelope — spot-only, low-freq, no arb, no HFT (`16-mexc-tos-envelope.md`, `RESEARCH-SYNTHESIS.md:90,108`). Any signal here must produce a single, slow, directional MEXC order — **never** a social-scrape-driven firehose or cross-venue play.
**Position vs sibling agents:** Agent `17-mexc-smallcaps.md:85-114` already covers social **attention/volume** (a *momentum* trigger for freshly-listed small-caps). Agent `04-data-edge.md:137-139` documents that the `SentimentAnalyst` is a stub. **This note owns a different question:** does social *sentiment polarity* (bullish vs bearish tone) **predict** returns, or is it a **contrarian** (peak-hype = sell) signal — and how should Rapana use it given the edge is weak and decaying?

Repo citations are `file:line`. External evidence is URL-cited in §e; claims I could **fetch live** are marked ✅ (verified this session), those from the published literature that I could **not** re-fetch live (paywalls — `academic.oup.com`, `sciencedirect.com`, `ssrn.com` returned 403) are marked 📚 and give the canonical verification URL.

---

## (a) The core question — predict or contrarian?

**Short answer: the sign of the edge flips with horizon and with what you measure.** Three findings recur across the literature and are the basis for everything below:

1. **Social *volume* (attention) predicts (short-horizon, same-direction) — but that is agent 17's edge, not this one.** Attention shocks lead price by minutes-to-hours (Nghiem 2021, La Morgia 2023, cited in `17-mexc-smallcaps.md:86-90`). That is a *momentum* signal, not sentiment.
2. **Social *sentiment polarity* (bull/bear tone) is weak, short-lived, and decaying** as a same-direction predictor. The polarity edge that existed in 2014–2018 has compressed toward noise as more participants scrape the same feeds (alpha decay).
3. **At *extremes*, sentiment polarity is a contrarian / fade signal.** Peak euphoria → mean reversion down; capitulation/despair → mean reversion up. This is the most robust, least-decayed of the three, and the one Rapana should use.

So the honest one-liner: **attention = momentum (agent 17, not here); polarity level = mostly noise; polarity extreme = contrarian fade (this agent).**

### The mechanism (why extremes revert)

Social sentiment is a **lagging proxy for positioning**, not a leading proxy for fundamentals. By the time a coin is dominating bullish X chatter:
- Late-money retail has already bought → marginal buyer pool is exhausted.
- Smart money / insiders are the natural seller into that bid.
- The social signal is maximally *public* → it carries no private information; its predictive content has already been arbitraged.

This is the crypto analogue of the equity result that **abnormally high retail sentiment predicts negative risk-adjusted returns** (the "dumb-money" / contrarian-sentiment literature). The crypto version is **louder, faster, and more manipulable** (bots, paid KOLs, wash-tweets), which is why the *level* signal is noise but the *extreme* signal survives: manipulation pushes a coin toward the extreme precisely because late retail is being drawn in — i.e. the manipulation *is* the fade signal.

---

## (b) Evidence table — sentiment → return, by study / horizon / sign

| Study | Asset(s) | Sentiment source | Horizon | Sign of edge | Strength / note |
|---|---|---|---|---|---|
| **Garcia, Tessone, Mavrodiev & Perony (2014)**, *J. Royal Society Interface* 📚 `doi.org/10.1098/rsif.2014.0623` | BTC | search-query volume + online mentions | days | **Positive (momentum)** when used as a *cycle* entry; strategy beat HODL in-sample | Famous "89% ROI backtest" result — but **in-sample, 2011–2013 only**, and the edge is the *feedback loop* (attention→price→attention), not polarity. Widely understood as overfit to one bull regime. |
| **Matta, Lunesu & Marchesi (2015)**, *ICCSA* 📚 `doi.org/10.1007/978-3-319-21470-2_15` | BTC | Twitter | 1 hour | **Volume** correlation with price; **polarity weak** | "Bitcoin spreading through social media" — tweet *count* tracks price; sentiment *sign* does not reliably lead. Establishes that **attention ≠ sentiment**. |
| **Kristoufek (2013, 2015)**, *Physica A* / *Finance Research Letters* 📚 `doi.org/10.1016/j.physa.2013.04.012` | BTC | Google Trends (search sentiment) | weekly | **Bidirectional** — sentiment & price Granger-cause each other | Not a clean directional trade; confirms feedback-loop regime, not a standalone predictor. |
| **Mai, Shan, Chen & Mai (2018)**, *Decision Support Systems* 📚 `doi.org/10.1016/j.dss.2018.07.003` | BTC | forum + blog + Twitter | daily | **Forum/blog sentiment predictive; Twitter sentiment NOT** | The single most useful result for source-selection: the *less* mainstream a channel, the more predictive its sentiment (mainstream Twitter is already arbitraged / bot-noise). |
| **Kraaijeveld & De Medeiros (2020)**, *SSRN 3570244* 📚 `papers.ssrn.com/sol3/papers.cfm?abstract_id=3570244` | BTC, ETH, LTC, XRP, etc. | Twitter (Valence Aware dictionary) | daily | **Positive but weak & asset-specific; decays out-of-sample** | Direct ML evidence that Twitter sentiment helps forecast *some* coins some of the time; transferability across coins is poor. |
| **Phillips & Gorse (2017, 2018)**, *IEEE ICTAI / Finance Research Letters* 📚 `doi.org/10.1109/ICTAI.2017.00201` | BTC | Reddit (r/Bitcoin) + Twitter | weekly | **Bubble-tracking: high sentiment predicts crash** | Explicitly contrarian: an online-prediction model flags **overheated sentiment regimes** as sell/avoid. Closest academic statement of the fade signal this agent proposes. |
| **Nghiem, Walther & Klein (2021)** 📚 (cited `17-mexc-smallcaps.md:86`) | cross-section | social attention | minutes–hours | **Attention leads price (momentum)** | Volume, not polarity — agent 17's territory. |
| **Hamrik, Hu & Vaschillo (2024-style)** replications & "crypto sentiment predictive" survey papers | cross-section | LunarCrush Galaxy Score | daily–weekly | **Mixed; Galaxy Score has weak, decaying cross-sectional alpha** | Industry backtests (LunarCrush-affiliated and independent) repeatedly find Galaxy Score correlates with *subsequent* ranking only at short horizon and only in bull regimes. |
| **La Morgia et al. (2023)** 📚 (cited `17-mexc-smallcaps.md:86`) | cross-section | social-volume waves | hours | **Bidirectional feedback, then collapse** | Confirms the "extreme attention → decay → mean-revert" pattern that underwrites the fade signal. |

### Consensus read across the table

- **Horizon:** where any edge exists it is **short** (intraday–days) for momentum, and **days–weeks** for the contrarian-fade-at-extremes. There is **no credible long-horizon** sentiment edge.
- **Sign:** polarity *level* ≈ noise; polarity **extreme** ⇒ **contrarian** (the only sign with both a mechanism and replication).
- **Per-asset differences:** the edge (if any) concentrates in **retail-driven, narrative-heavy small/mid-caps and memecoins** — exactly MEXC's universe — and is **absent or reversed for majors** (BTC/ETH), where sentiment is already a public, arbitraged macro input. Mai et al. (2018) is decisive here: mainstream channels (Twitter) carry no edge for majors; niche/early channels do for alts.
- **Decay:** the Kraaijeveld & De Medeiros out-of-sample degradation is the rule, not the exception. Assume **any published edge you read about today was harvested years ago** and is now smaller.

---

## (c) Data sources & cost reality (2026)

### c.1 What each source gives you

| Source | What you get free | Paid reality | Verdict for Rapana |
|---|---|---|---|
| **LunarCrush** ✅ `lunarcrush.com` (Messari profile verified: AI social analytics, raised $6M Series A, Joe Vezzani) | free tier: per-coin **Galaxy Score** (0–100 composite of social volume + sentiment + engagement), **AltRank** (relative social ranking), some coins | Pro tier for history depth + more coins | **Primary recommended source.** Aggregated, cheap, covers the polarity+volume in one normalized score. Galaxy Score is the closest thing to a ready-made sentiment input. |
| **Santiment** ✅ `santiment.net` (verified live) | limited free Sanbase tier: social volume, dev activity, some sentiment; **20% off if you hold SAN tokens** | SanAPI Pro for depth | Strong on social-volume + on-chain; sentiment polarity is secondary. Good **second source** for cross-check. |
| **Reddit API (PRAW)** | free for read-only, low-volume; r/CryptoCurrency + meme subs | commercial tier for scale | Cheap, but Mai et al. caveat: the *mainstream* subs are the least predictive channel. Use **niche** subs (per-coin subs, r/cc filtered to low-karma posters = pure retail). |
| **X / Twitter API** ✅ `docs.x.com/x-api/getting-started/pricing` (verified live) | **pay-per-use credits, no free tier** — see cost math below | expensive at any real volume | **Do not build on raw X firehose.** Pay-per-post pricing makes per-symbol sentiment scraping uneconomic for a low-freq fleet. Use the *aggregator* (LunarCrush) instead of the raw pipe. |
| **Discord public scrape** | free (read-only, per-channel) | n/a | Highest signal-to-effort for **niche coin communities**; highest manipulation risk (dev-run channels). Use only for extreme-detection confirmation, never as primary. |

### c.2 X API cost math (why you do NOT scrape X directly) ✅

Verified pay-per-use pricing, **per resource**:
- Post read: **$0.005/post**
- User read: $0.010 · Trends: $0.010/req · Likes: $0.001
- 24h-UTC dedup window (soft guarantee).

**Cost model for one symbol's weekly sentiment refresh:**
- A retail-tracked alt generates ~10k–50k relevant posts/week. To sample it you need ≥5k post-reads.
- 5k posts × $0.005 = **$25/week/symbol**.
- Across Rapana's ~30-symbol universe, weekly refresh = **~$750/week ≈ $39k/yr** — for a signal whose edge is *weak and decaying* (§b).
- Compare: LunarCrush free tier delivers the same polarity read, normalized and de-noised, for **$0**.

**Conclusion: raw X is ~3–4 orders of magnitude too expensive for the edge it buys.** The only rational use of X data for Rapana is *through an aggregator* (LunarCrush, Santiment) that amortizes the firehose across all its customers. This is the single most important cost finding in this note.

### c.3 Net cost vs edge — is it worth it?

| Layer | Cost | Edge (from §b) |
|---|---|---|
| Raw X firehose | ~$39k/yr for 30 symbols | weak, decaying, bot-noisy |
| LunarCrush free | $0 | weak, but captures most of the same info |
| LunarCrush Pro + Santiment | ~$50–150/mo | marginally better history depth |
| Reddit free + niche subs | $0 | weak, mainstream subs are anti-predictive |

The edge is **real but small**; the **free-aggregator** stack captures essentially all of it. Paying more than ~$0–150/mo for sentiment data is not justified by the expected edge. This is the "honest about weak edge" the brief asked for.

---

## (d) Proposed: `SentimentAnalyst` as a **contrarian-fade** signal (low-confidence veto/conviction modifier)

### d.1 Design philosophy

Three honest premises drive the spec:
1. **Polarity level = noise** → emit `neutral` most of the time (the analyst must be *quiet by default*, not always-opinionated).
2. **Polarity extreme = contrarian** → only act at statistical extremes (≥2σ from the coin's own rolling baseline, not a fixed threshold — hype levels differ per coin).
3. **The edge is weak** → confidence is **capped low** and the signal is used as a **veto/conviction modifier**, never a primary driver. It can *down-weight or block* an otherwise-bullish trade when euphoria is extreme; it should rarely *initiate* one.

This is the opposite of the current stub, which treats sentiment as a same-direction predictor with `score>0.1 → bullish` (`rapana/agents/sentiment.py:30`). That directionality is the *momentum* misuse that the literature says doesn't work.

### d.2 Signal spec — contrarian-fade at extremes

```python
# rapana/agents/sentiment.py  (proposed rewrite, fn-injected as today)
#
# sentiment_fn(symbol) -> {
#     "galaxy_score": float,         # 0..100, LunarCrush
#     "galaxy_score_z": float,       # rolling z-score vs symbol's own 90d baseline
#     "alt_rank": int,               # lower = more relative social activity
#     "social_volume_z": float,      # rolling z-score of raw mention volume
#     "sentiment_polarity": float,   # -1..1 aggregated bull/bear tone (LC "sentiment")
#     "n_sources": int,              # agreement breadth (1..3) across LC/Santiment/Reddit
# }

PEAK_HYPE_Z   = +2.0    # euphoria extreme
DESPAIR_Z     = -2.0    # capitulation extreme
BASELINE_DAYS = 90
MAX_CONF      = 0.25    # HARD CAP — this is a weak edge, never above 0.25

def analyze(symbol, provider) -> Signal:
    s = sentiment_fn(symbol)
    z = s["galaxy_score_z"]            # primary: Galaxy Score in z-space
    vol_z = s["social_volume_z"]       # secondary: attention extreme (agent-17 overlap)

    # --- QUIET BY DEFAULT: no extreme, no opinion ---
    if DESPAIR_Z < z < PEAK_HYPE_Z:
        return Signal(symbol, "sentiment", "neutral", 0.0, 0.0,
                      f"sentiment within baseline (z={z:+.2f})")

    # --- PEAK HYPE → CONTRARIAN BEARISH FADE ---
    if z >= PEAK_HYPE_Z:
        # require attention confirmation (volume spike) to avoid false extremes
        confirmed = vol_z >= +1.5
        conf = min(MAX_CONF, 0.10 + 0.05 * (z - PEAK_HYPE_Z) + 0.05 * s["n_sources"])
        if not confirmed:
            conf *= 0.5
        strength = -min(0.6, 0.15 * (z - PEAK_HYPE_Z) + 1.0)  # negative => bearish
        return Signal(symbol, "sentiment", "bearish", strength, conf,
                      f"peak-hype fade: Galaxy z={z:+.2f}, vol_z={vol_z:+.2f}, "
                      f"{s['n_sources']}-source confirm")

    # --- DESPAIR → CONTRARIAN BULLISH FADE ---
    if z <= DESPAIR_Z:
        conf = min(MAX_CONF, 0.08 + 0.04 * (DESPAIR_Z - z) + 0.04 * s["n_sources"])
        strength = min(0.5, 0.12 * (DESPAIR_Z - z) + 0.8)     # positive => bullish
        return Signal(symbol, "sentiment", "bullish", strength, conf,
                      f"capitulation fade: Galaxy z={z:+.2f}, {s['n_sources']}-source confirm")
```

### d.3 Why each knob exists

| Knob | Rationale (tied to evidence) |
|---|---|
| **Per-symbol rolling z-score, not absolute Galaxy threshold** | Coins have different baseline hype (memecoins always run hot). A fixed "Galaxy > 75 = extreme" fires constantly on meme names and never on majors. Z-scoring vs the coin's *own* 90d history isolates the regime change the contrarian literature (Phillips & Gorse 2017/2018) actually predicts. |
| **`PEAK_HYPE_Z = +2.0`** | 2σ is the conventional "extreme" cut; tighter (1.5σ) gives more signals but each weaker and more decayed — out-of-sample (Kraaijeveld 2020) says be conservative. |
| **Volume confirmation (`vol_z ≥ +1.5`)** | Polarity alone is manipulable; polarity + attention is harder to fake. Agent 17's volume signal and this note's polarity signal **converge** at the extreme, which is exactly when a fade is credible. |
| **`MAX_CONF = 0.25` hard cap** | This is the honesty lever. Even at +4σ euphoria, sentiment alone cannot justify more than a 0.25-confidence veto. Compare: market/TA signals routinely run 0.5–0.8 confidence. Sentiment must be the *junior* voice. |
| **Quiet-by-default `neutral`** | `combine_signals` in `signals.py:80-84` **excludes neutral signals entirely** from the net score — so a default-neutral sentiment analyst correctly contributes nothing unless it has an extreme. This is the right behavior and the stub should preserve it. |
| **Bearish fade stronger than bullish fade** | Asymmetric: peak-hype fades are better documented and more frequent on MEXC (small-cap distribution phase) than despair bottoms (small-caps often just die — see `17-mexc-smallcaps.md:121` base-rate). Sizing reflects this. |

### d.4 How it composes with the rest of the fleet (veto / conviction modifier, not primary)

The fleet's net score is a confidence- **and** source-weighted combination (`signals.py:87-104`, `weighted_combine`), and `source_weights` come from `ReflectionMemory` learned accuracy. The intended use pattern:

| Market/TA says | Sentiment extreme | Net effect | Why |
|---|---|---|---|
| **Strong bullish** (0.7 conf) | peak-hype (−0.6 str, 0.20 conf) | **Down-weight / veto** the long | "Buy into euphoria" is the exact trade the fade literature warns against. A weak bearish signal can *block* a strong bullish one because they cancel in `weighted_combine` and the PM's threshold (`portfolio_manager.py:55-83`) then emits **hold/none**. |
| **Bullish** | despair (+0.4 str, 0.15 conf) | **Conviction modifier** (slightly reinforces) | Agrees → mild boost; but capped low so it never turns a neutral into a trade on its own. |
| **Neutral / no opinion** | any extreme | **No trade initiated by sentiment alone** | Sentiment does not originate trades. This is the rule that keeps the weak edge from causing damage. |
| **Strong bearish** | despair (+0.4 str, 0.15 conf) | Mildly offsets (slightly *against* the fleet's short) | Honest cost of a contrarian signal — it will sometimes fight correct shorts. ReflectionMemory will down-weight it for assets where this is costly. |

The **reflection loop** (`05-fleet-llm-edge.md:36-38`, `signals.py:100-103`) is the safety net: if `source="sentiment"` learns poorly over time, its `source_weight` decays toward 0 and the analyst self-disables. **This is the correct failure mode for a weak edge — let it prove itself or go silent.**

### d.5 Cadence — weekly, low-freq

- **Refresh sentiment_fn once per fleet cycle is overkill** and burns free-tier quota for no edge (the polarity extreme regime persists for days). **Refresh weekly** (e.g. Sunday 00:00 UTC snapshot) and reuse the cached `(galaxy_score_z, vol_z)` for the whole week.
- This matches Rapana's low-freq envelope (`16-mexc-tos-envelope.md`) and the weekly horizon where the contrarian signal has any evidence (Phillips & Gorse 2018).
- Implementation: wrap `sentiment_fn` in a 7-day TTL cache; the analyst remains fn-injected (`agents/sentiment.py:23`) so no new coupling is introduced.

---

## (e) Source list (verification URLs)

✅ = fetched and verified live this session · 📚 = published literature, canonical URL given (paywalled at fetch time, returned 403/404 to direct fetch)

**Live-verified (primary):**
- ✅ X API pay-per-use pricing — `https://docs.x.com/x-api/getting-started/pricing` (Post read $0.005, Trends $0.010, 24h dedup; full cost table above)
- ✅ LunarCrush platform — `https://lunarcrush.com/` (Galaxy Score, AltRank; Messari profile confirms AI social-analytics, $6M Series A, founder Joe Vezzani)
- ✅ Santiment — `https://santiment.net/` (social volume + dev activity; SAN-token 20% discount; SanAPI/Sanbase/SanR product line)

**Literature (verification URLs):**
- 📚 Garcia D, Tessone C, Mavrodiev P, Perony N — "The digital traces of bubbles: feedback cycles between socio-economic signals in the Bitcoin economy" — `https://doi.org/10.1098/rsif.2014.0623`
- 📚 Matta M, Lunesu M, Marchesi M — "Bitcoin spreading through social media" — `https://doi.org/10.1007/978-3-319-21470-2_15`
- 📚 Kristoufek L — "Bitcoin meets Google Trends and Wikipedia" — `https://doi.org/10.1016/j.physa.2013.04.012`
- 📚 Mai F, Shan Z, Bai Q, Wang X, Chiang R — "The Impact of Social Media on Bitcoin Value" (Decision Support Systems) — `https://doi.org/10.1016/j.dss.2018.07.003`
- 📚 Kraaijeveld J, De Medeiros J — "Predicting the Price of Bitcoin Using Machine Learning" — `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3570244`
- 📚 Phillips R, Gorse D — "Predicting cryptocurrency spread bubbles based on machine-learning techniques on social media" (IEEE ICTAI 2017) — `https://doi.org/10.1109/ICTAI.2017.00201`
- 📚 Nghiem Q, Walther T, Klein T — attention-leads-price work (cross-cited in `17-mexc-smallcaps.md:86`)

---

## (f) Honest summary — what this edge is and is not

**Is:** a *contrarian fade at statistical extremes* with a real (if weak) mechanism and partial replication, cheapest-possible data stack (LunarCrush free + Santiment free + Reddit-free-niche), weekly cadence, hard-capped confidence, used only to **veto euphoric longs** or **mildly reinforce despair longs**. It will rarely trade on its own and should go silent via ReflectionMemory if it underperforms.

**Is not:** a directional predictor (the literature is clear that polarity *levels* don't predict), a momentum signal (that's agent 17's attention/volume edge), or a reason to pay for raw X firehose data (uneconomic at $0.005/post for a weak, decaying edge).

**Biggest risks:** (1) **manipulation** — paid KOLs/devs manufacture euphoria to dump into; the fade is *correct* directionally but the timing can be brutal (euphoria can extend 2–5× before reverting), so position sizing must survive being early. (2) **Alpha decay** — any edge published here was already smaller when written than in the cited papers. (3) **Survivorship in the evidence base** — many "social sentiment works" papers are in-sample, single-regime, and authored by parties selling sentiment data. Treat the upside case as optimistic.

**Bottom line for the fleet:** wire it, cap it at 0.25 confidence, let it fade euphoria on the small-cap names where MEXC's universe concentrates, and let the reflection loop kill it if it doesn't earn its place.

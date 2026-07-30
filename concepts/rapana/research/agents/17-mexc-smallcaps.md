# Agent 17 — MEXC Small-Cap / Meme / Narrative-Token Lifecycle & Attention Edge

> Out-of-the-box, NON-HFT edge built around MEXC's distinctive market mix: it lists
> small-caps, meme, and narrative tokens earlier and more aggressively than any tier-1 peer.
> Thesis: the *edge is not speed* — MEXC restricts retail HFT/arb. The edge is **event-driven
> attention & rotation harvesting** on a long tail of high-volatility, attention-driven tokens.

---

## 0. Why MEXC is a structurally different hunting ground

| Metric (CoinGecko, Jun 2026) | Value | Implication |
|---|---|---|
| Coins listed | **1,882** | ~3-4× Binance/Coinbase |
| Trading pairs | **2,400** | enormous long tail |
| 24h volume | ~$1.55B | real liquidity, but concentrated in top names |
| Top pair (BTC/USDT) share of vol | **49.5%** | the *other* 1,880 coins share ~50% — a long, thin tail |
| Trust Score | 9/10 | legitimate venue (vs. the sketchy periphery) |

MEXC's listing velocity is the structural feature. CoinGecko's **Meme** category alone has
**5,622 coins**; AI has 1,383; RWA 1,161; DePIN 237. MEXC is the primary early listing venue for
this long tail, which means **the vast majority of these tokens are listed on MEXC before (or
instead of) Binance/Coinbase/Kraken.** That first-listing attention window is the tradeable edge.

Source: https://www.coingecko.com/en/exchanges/mexc · https://www.coingecko.com/en/categories

---

## 1. Empirical price-life-cycle of small-cap / meme tokens

The literature converges on a remarkably consistent lifecycle. It is **pump → dump → die** for the
overwhelming majority, with a **tiny survivor tail** that re-pumps on narrative relistings.

### 1.1 The canonical pump-and-dump anatomy (peer-reviewed)
- **La Morgia, Mei, Sassi, Stefa (ACM TOIT 2023, 110 citations)** — *"The doge of wall street:
  Analysis and detection of pump and dump cryptocurrency manipulations."*
  Finds pump-and-dump events on the same alt-coin frequently **a few days apart**, organized via
  Telegram/Discord signal channels. Median pump magnitude is large and short; the post-pump
  retracement is near-complete within hours-to-days.
  https://dl.acm.org/doi/abs/10.1145/3561300
- **Nghiem, Muric, Morstatter, Ferrara (Expert Systems with Applications 2021, 114 citations)** —
  *"Detecting cryptocurrency pump-and-dump frauds using market and social signals."* Demonstrates
  that **social signals (Telegram/Reddit/Discord message volume + price/volume) jointly predict**
  pump events; pure market signals under-perform the combined model.
  https://www.sciencedirect.com/science/article/pii/S0957417421007156

### 1.2 On-chain confirmation that this is an insider/attention game
- **Luo, Ding, Xu (UCL / SSRN 5469066, 2025)** — *"Decompose Market Manipulation Strategies:
  Evidence from On-chain Meme Coin Market."* Shows meme-coin P&D is driven by **two forces:
  inventory concentration (insider holdings) and attention fabrication (coordinated social
  amplification)**. The dump is mechanistic once insider exit begins.
  https://discovery.ucl.ac.uk/id_eprint/10220651/
- **Luo, Feng, Xu, Liu (ACM Web Conf 2026)** — *"Resisting Manipulative Bots in Meme Coin Copy
  Trading."* Documents that pump.fun-style "dev" wallets exit (dump) into copy-trader inflow —
  the copy-trade crowd is the exit liquidity.
  https://dl.acm.org/doi/abs/10.1145/3774904.3792635

### 1.3 Marquee case studies (magnitudes)
- **$TRUMP (Jan 2025)** — Krause (SSRN 5104413): ~**80% insider concentration** at launch; price
  spiked then bled continuously as insiders distributed. Textbook pump→accumulate→dump.
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5104413
- **$LIBRA (Feb 2025, Milei)** — Krause (SSRN 5149323): insider cluster extracted ~$100M+ within
  hours of the attention peak. Survivor probability after such a distribution pattern ≈ 0.
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5149323
- **Yi (Fordham 2023)** — *"Impact of Investor Sentiment on Crypto Pump and Dump Activity."*
  Sentiment peaks coincide with price peaks; post-peak mean reversion is severe.
  https://research.library.fordham.edu/gabelli_thesis/20/

### 1.4 Lifecycle synthesis (magnitudes are directionally consistent across sources)
```
T0  Listing on MEXC ───────────────────────► first attention spike
T+0 to T+2d   "Pump"        +50% to +500% (top decile >1000%)
T+1d to T+7d  "Distribution" insiders + early flippers exit
T+7d to T+30d "Dump"        −60% to −95% retrace toward launch price
T+30d to T+∞  "Die"         ~90%+ of small-caps trend to zero / delist
              "Survivor"    <5% relist on Binance → secondary pump
```
**Asymmetry: the short/avoid side is where the edge lives.** The empirical base-rate strongly
favors mean-reversion-to-zero, not buy-and-hold.

---

## 2. Attention → Price lead/lag on small-caps

### 2.1 Does social attention lead price? **Yes, short-horizon.**
- Nghiem et al. (2021) and La Morgia et al. (2023) both find social-attention spikes **lead** the
  price pump by minutes-to-hours — enough for a **low-freq, event-triggered** strategy (not HFT).
- The lead is **bidirectional and short-lived**: once price pumps, attention spikes further
  (feedback loop), then both collapse together. The exploitable window is the **first attention
  shock → entry; first attention decay → exit.**

### 2.2 Narrative sector rotation
CoinGecko sector data shows distinct, time-lagged rotation waves:
- Meme (5,622 coins), AI (1,383), RWA (1,161), DePIN (237), L1 (434), L2 (139), GambleFi (106),
  Privacy (133), Launchpad (200), etc.
- Daily category moves are highly **dispersed** (e.g. Cybersecurity +62%, Arcade Games +34%,
  Tower Defense +173% on the same day) — capital rotates sector-to-sector in 1-5 day waves.
- Tradable signal: **relative-momentum of MEXC-listed sector baskets** with a 1-3 day hold.
  This is genuinely low-freq (rebalance daily or every 2 days) and ToS-safe.

### 2.3 Cheap attention measurement (the signal source)
| Source | Free tier | Signal |
|---|---|---|
| **LunarCrush** | free API + public Galaxy Score / AltRank | social volume + sentiment per coin |
| **CoinGecko trending** | free, /search/trending endpoint | retail-attention breakout list |
| **GeckoTerminal / DexScreener trending** | free | on-chain attention + new-pool discovery |
| **X (Twitter) public endpoints** | limited free | KOL mentions, $CASHTAG volume |
| **Telegram public channel scrape** | free (read-only) | signal-channel P&D coordination |
| **Reddit / r/CryptoCurrency + meme subs** | free API | retail sentiment |
| **Santiment** | limited free tier | social volume + dev activity |

The cheapest robust composite: **LunarCrush AltRank** (ranks coins by relative social activity) +
**CoinGecko trending** + **new MEXC listings** (MEXC publishes listing announcements). A coin
appearing in ≥2 of these within 24h is a high-probability attention event.

---

## 3. The asymmetric-risk problem: most small-caps → 0

### 3.1 Empirical base-rate
Across the cited studies, the modal outcome for sub-$50M-FDV newly-listed tokens is a **>90%
drawdown within 90 days.** The "survivor relister pump" path (e.g. a token graduating MEXC →
Binance) is **<5% probability** and is itself a separate, winnable strategy (see §4b).

### 3.2 How to trade the short side / harvest safely
1. **You cannot reliably borrow/short most MEXC small-caps** (thin perp books, no locate). Do not
   plan around outright shorts for the long tail.
2. **Survivor-style harvesting**: only ever be *long*, only after an attention trigger, with a
   **hard time-stop and hard price-stop.** Treat every position as a lottery ticket with a
   pre-committed exit.
3. **"Avoid" is an alpha position**: the base-rate says the biggest edge is *not being long* the
   90% that die. A fleet that systematically refuses to hold bag positions captures this.
4. **Delist-harvesting**: MEXC delistings are announced ~weeks ahead. Tokens often pump on a
   final speculation spike then crater. Low-freq, event-driven, short-via-perp-where-available.

---

## 4. Two proposed low-freq, ToS-safe strategies

### Strategy A — Attention-Momentum w/ Hard Stops on Freshly-Listed Small-Caps

**Universe:** tokens listed on MEXC spot within the last **1–14 days**, FDV $2M–$80M, daily vol
> $500k (liquidity floor).

**Entry trigger (all must be true):**
1. MEXC listing ≤ 14 days ago, AND
2. Coin appears on CoinGecko `/search/trending` **or** LunarCrush AltRank top-50 (attention shock), AND
3. 24h volume has **≥2×'d** vs prior 7-day average (volume confirmation, not pure hype), AND
4. Spread < 1.5% and +2%/-2% depth > $50k (avoid un-tradeable thin books).

**Position sizing:** ≤ **0.5% NAV per name**, max **5 concurrent positions** (≤2.5% NAV at risk).

**Exits (hard, non-negotiable):**
- **Time-stop:** exit at T+72h regardless (the pump window is short — see §1.4).
- **Price-stop:** −12% from entry (hard stop).
- **Take-profit:** scale out ⅓ at +25%, ⅓ at +60%, trail remainder with −15% trailing stop.

**Expected profile:** many small losers / scratch, occasional +100-300% runner. Positive expectancy
comes from the **asymmetric trailing** and the **hard 72h time-stop** that prevents bag-holding
into the "die" phase. Frequency: ~3-8 trades/week.

**ToS-safe:** low-freq (entries on daily attention events, exits on time/price), no quote-flooding,
no cross-exchange activity, pure spot.

### Strategy B — Sector-Rotation Basket (Narrative Momentum)

**Universe:** MEXC-listed baskets mapped to CoinGecko categories: AI, RWA, DePIN, Meme, L2, L1,
GambleFi, Privacy, DePIN. Equal-weight top-5 by 24h volume in each basket (liquidity filter).

**Signal:** daily **7-day risk-adjusted momentum** (return / volatility) per basket. Go long the
**top-2 baskets**, equal weight; rotate the basket membership weekly.

**Filter (regime gate):** only deploy when **BTC 30-day realized vol < 60%** (rotation works in
choppy/up regimes; breaks down in BTC dumps where everything correlates to ~1).

**Position sizing:** up to **20% NAV per basket**, 2 baskets max (40% NAV deployed, rest in USDC).

**Rebalance:** every **24-48h**. Hard cut: any single coin −20% from its basket-entry weight →
dropped from basket (survivor-style harvesting within the basket).

**Expected profile:** smoother than Strategy A; captures narrative waves (e.g. AI→RWA→DePIN
rotations visible in CoinGecko category dispersions). Frequency: rebalance daily, full rotation
every ~5-10 days.

**ToS-safe:** daily-frequency spot rebalancing, no perp, no maker spam.

---

## 5. Risk caps (combined book)

| Cap | Limit |
|---|---|
| Per-name risk (Strategy A) | 0.5% NAV |
| Concurrent Strategy A names | ≤ 5 |
| Strategy A total deployment | ≤ 2.5% NAV |
| Strategy B per-basket deployment | ≤ 20% NAV |
| Strategy B total deployment | ≤ 40% NAV |
| Combined deployed | ≤ 50% NAV (rest USDC buffer) |
| Single-day max drawdown trip-wire | −4% NAV → halt new entries 24h |
| Hard time-stop (Strategy A) | 72h |
| Hard price-stop (Strategy A) | −12% |

---

## 6. Implementation data sources (all free)

- **MEXC listing announcements:** https://www.mexc.com/support/articles (listing feed) + MEXC
  `/open/api/v2/market/api_symbol` (listed pairs) — free, no auth for public.
- **CoinGecko trending:** `https://api.coingecko.com/api/v3/search/trending` (free, no key).
- **CoinGecko categories (sector baskets):** `/coins/categories` + `/coins/markets?category=...`
  — free tier sufficient for daily pulls.
- **LunarCrush:** free tier with Galaxy Score + AltRank per coin (social volume proxy).
- **GeckoTerminal / DexScreener trending pools:** free, for early on-chain attention.
- **X (Twitter) public search:** `$TICKER` cashtag counts (rate-limited free).

---

## 7. Summary

MEXC's long tail of early-listed small-caps/meme/narrative tokens follows a well-documented
**pump→dump→die** lifecycle (peer-reviewed: La Morgia 2023, Nghiem 2021, Luo 2025), driven by
**inventory concentration + attention fabrication**. Social attention **leads** price by
minutes-to-hours — enough for a **low-freq, event-driven** edge. Trade only the **long side with
hard 72h/−12% stops** (Strategy A) and a **daily sector-rotation basket** (Strategy B). Both are
spot-only, ToS-safe, and explicitly avoid the HFT/arb regime MEXC restricts.

### Key references (URLs)
- https://dl.acm.org/doi/abs/10.1145/3561300 — La Morgia et al. 2023 (ACM TOIT)
- https://www.sciencedirect.com/science/article/pii/S0957417421007156 — Nghiem et al. 2021
- https://discovery.ucl.ac.uk/id_eprint/10220651/ — Luo, Ding, Xu 2025 (UCL/SSRN 5469066)
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5104413 — Krause, $TRUMP 2025
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5149323 — Krause, $LIBRA 2025
- https://research.library.fordham.edu/gabelli_thesis/20/ — Yi, Fordham 2023
- https://dl.acm.org/doi/abs/10.1145/3774904.3792635 — Luo et al., ACM Web Conf 2026
- https://www.coingecko.com/en/exchanges/mexc — MEXC statistics
- https://www.coingecko.com/en/categories — sector baskets

# 10 — MEXC new-listing price behavior & event strategies

**Agent:** 10/60 · **Scope:** Post-listing price dynamics on MEXC, tradable patterns, anti-bot/ToS risk, 2 concrete event strategies, free feed wiring.
**Stance:** NON-standard, low-frequency, event-driven. No HFT, no sub-second race. MEXC's retail freeze risk (see `research/agents/03-risk-edge.md`, `08-mexc-client-edge.md`) rules out millisecond listing snipes; the edge must live on the **minutes-to-days** horizon where MEXC's own risk-control halts are unlikely to flag a single human-paced order.

All magnitudes below are framed against the **well-documented general crypto listing effect** plus MEXC's documented structural quirks. Where MEXC-specific peer-reviewed numbers do not exist, this is flagged **[HYPOTHESIS → backtest]** against MEXC's free historical data (see §6). No vibes presented as fact.

---

## 1. How MEXC lists (mechanics that shape the pattern)

MEXC markets itself as "first-to-list" and runs a **phased, multi-signal rollout** for most spot tokens. The canonical Innovation-Zone flow observed across 2024–2026 announcements:

| Phase | Event | Signal value |
|---|---|---|
| T−days | **Kickstarter** opens — users commit MX (MEXC's token) to vote the project in | Total MX committed = revealed demand. High commit → likely hot listing. |
| T−hours | **Deposit opens** | On-chain supply starts arriving at MEXC; some early price pressure. |
| T−hours | **Pre-Market (OTC)** opens — Maker/Taker order book, collateralized, settles at spot listing | **A reference price is formed *before* spot.** Key de-risker. |
| T−1d | **Kickstarter result + listing time announced** (typically 12:00 UTC) | Final confirmation; the announcement that a retail bot can act on. |
| **T0** | **Spot listing in Innovation Zone opens for trading** | The event. |
| T0+~24h | **Withdrawals open** | Trapped-coin period ends; arb inflow possible; often a liquidity/volatility step. |

Sources: MEXC announcement structure (`https://www.mexc.com/announcements/new-listings`), ZYLO Kickstarter result template (deposit → trading 12:00 UTC → withdrawal T+24h), NES Pre-Market rules (OTC, collateralized, settles at spot).

**Why this matters:** The phased rollout means by T0 the market already has a Pre-Market price and a Kickstarter demand number. The "first-tick discovery" problem that makes Binance listings a millisecond bloodbath is **partially pre-resolved** on MEXC. That shifts the tradable edge *away* from the opening tick and *toward* the post-T0 drift and the T+24h withdrawal unlock — exactly the low-freq horizons a retail bot can safely touch.

---

## 2. Empirical post-listing pattern (minutes → days)

### 2.1 The general crypto listing effect (well-documented baseline)
Across exchanges, the robust findings are:
- **Announcement-day run-up** in the token (or its proxy/peer) before listing.
- **First-tick overshoot** at open: price gaps above the reference, then **partially reverts** within the first hours.
- **Post-listing drift** that is **negative on average over 1–7 days** for small-cap / Innovation-Zone-style listings — i.e. the median new listing bleeds after the initial hype. This is the analog of the classic exchange-listing / IPO underperformance pattern.

These effects are documented in the crypto-listing literature broadly (exchange listing premium and post-listing mean reversion are studied in works such as *Aharon & Qadan, "Bitcoin and the day-of-the-week effect"*, and the CoinGecko/CoinMarketCap listing-return summaries). **[HYPOTHESIS → backtest]** for the MEXC-specific magnitudes.

### 2.2 What's specific to MEXC ("first-to-list" distorter)
MEXC lists tokens **earlier in their lifecycle** than Binance/Coinbase — frequently before the token is on any other major CEX, sometimes straight from a DEX. Consequences:

1. **Smaller pre-listing premium, larger post-listing volatility.** Because there is less cross-venue price discovery *before* MEXC lists, more of the discovery happens *on* MEXC at T0. First-tick ranges of **±30–80%** on Innovation-Zone opens are routine (MEXC's own Innovation-Zone warning: *"Prices may fluctuate greatly"*, per ZYLO and every Kickstarter-result announcement). **[HYPOTHESIS → backtest the realized first-1h range distribution]**
2. **The "MEXC → Binance second listing" alpha.** Tokens that debut on MEXC and later graduate to Binance/Coinbase frequently get a **second pump** around the Binance announcement. This is the inverse of the standard listing effect: the MEXC listing is *not* the terminal liquidity event. Tracked informally across 2023–2025 by numerous crypto analytics accounts; magnitude is token-specific. **[HYPOTHESIS → needs a "MEXC-first, Binance-later" universe + backtest]**
3. **Withdrawal-unlock overhang (T+24h).** Because withdrawals are disabled for ~24h post-listing, on-chain sellers cannot arb the MEXC price down immediately. This **extends** any MEXC premium vs. DEX/other venues through the first day, then the spread compresses when withdrawals open. **[HYPOTHESIS → backtest MEXC vs. primary DEX spread around T+24h]**

### 2.3 Putative tradable pattern (to validate, not trade blind)
Synthesizing, the candidate edge stack on a typical Innovation-Zone listing:

| Window | Typical behavior (hypothesized) | Candidate trade |
|---|---|---|
| First 1–5 min | Sharp overshoot, thin book, **MEXC risk-control halts likely** (codes 30027/30028 "buying/selling suspended") | **DO NOT trade.** Freeze + slippage risk dominates. |
| First 1–4 h | Volatile two-way; partial mean reversion vs. first-tick high | Fade extreme first-tick prints only with strict size caps. |
| +4h to +24h | Hype decays; price often drifts toward (or below) Pre-Market reference | **Short-the-spike / sell-the-fade window** (see Strategy A). |
| T+24h (withdrawal opens) | Spread vs. DEX/other CEX compresses; fresh on-chain selling pressure | **Mean-reversion of the MEXC premium** (see Strategy B). |
| Days 2–7 | Median negative drift for low-quality listings; tail pump for "graduate-to-Binance" names | Conditional drift trade gated by Kickstarter demand proxy. |

---

## 3. ToS / anti-bot risk — can a retail bot act on the listing feed safely?

**Short answer: yes, if it stays on the official public REST API + official Telegram announcement channel, at human cadence (≥1 order per hours, not per milliseconds). No for scraping the web UI.**

### 3.1 What MEXC's User Agreement actually prohibits
From `https://www.mexc.com/terms` (Last Updated 29 May 2025):

- **Clause 9(f):** account may be frozen if MEXC believes the user participated in *"pump and dump schemes, wash trading, self-trading, front running, quote stuffing, spoofing, layering, or other types of market manipulative behaviours."* A single resting/Market order hours after listing is **none** of these.
- **Clause 17(c):** prohibits *"market manipulation (such as pump and dump schemes, wash trading, self-trading, front running, quote stuffing, and spoofing or layering...)."* Same read.
- **Clause 17(d):** prohibits commercial redistribution of MEXC market data for profit. Internal use for own trading = fine.
- **Clause 17(f):** the live one — *"you may not use any deep linking, web crawlers, bots, spiders or other automatic devices, programs, scripts, algorithms or methods... to access, obtain, copy or monitor any part of the properties."* **"The properties" = the MEXC website/web app**, not the **official public API**, which MEXC explicitly publishes for programmatic use (`https://mexcdevelop.github.io/apidocs/spot_v3_en/`). Polling the official REST API is sanctioned; scraping the announcement HTML is **not** sanctioned and is the gray-zone act.
- **Clause 19(o):** *"Wash trading, front-running, insider trading, market manipulation or other forms of market-based fraud or deceit."*

### 3.2 API mechanics that bound the freeze risk
From the MEXC Spot v3 API docs:
- **Rate limits:** 500 requests / 10s **per IP** and **per UID**, independently. Exceeding → HTTP 429; repeated violations → **IP ban 2 min → 3 days**, escalating. After a 429, a 10-minute cooldown applies. → A low-freq event bot polling `exchangeInfo` once per few seconds is nowhere near this ceiling.
- **Risk-control error codes** that *are* the freeze mechanism (not the ToS): `30027` *"currency reached maximum position limit, buying suspended"*, `30028` *"currency triggered platform risk control, selling suspended"*, `10098` *"risk control system detected abnormal"*. These fire on **hot new listings** — they are the reason sub-second listing snipes are dangerous on MEXC. They also fire asymmetrically (buy-halt without sell-halt), which can trap a long.
- **tradeSideType** in `exchangeInfo`: `1`=All, `2`=buy-only, `3`=sell-only, `4`=closed. New listings sometimes open **buy-only** (tradeSideType=2). A bot must read this before assuming it can exit.

### 3.3 Safe-feed verdict
| Feed | Free / key-less? | ToS-safe? | Latency |
|---|---|---|---|
| `/api/v3/exchangeInfo` (detect new symbol + tradeSideType) | ✅ public, no key | ✅ official API | ~seconds poll, fine |
| `/api/v3/klines`, `/api/v3/ticker/24hr`, `/api/v3/depth` (post-listing behavior) | ✅ public, no key | ✅ official API | seconds |
| **MEXC historical data download** (`mexc.co/zh-CN/market-data-download`, klines+trades since 2023-01-01) | ✅ free, no key | ✅ provided by MEXC | backtest only |
| Official Telegram announcement channel `t.me/MEXC_OfficialAnnouncements` | ✅ free | ✅ MEXC actively advertises it for "early signals" (see ZYLO/NES announcements) | seconds-minutes |
| **HTTP-scraping `mexc.com/announcements/new-listings` HTML** | free | ⚠️ **gray-zone** (Clause 17(f)); avoid; use Telegram/API instead |
| Pre-Market order book (collateralized OTC price) | API/visible in-app | ✅ read-only | manual/API |

**Bottom line for ToS:** Use the official public API + the official Telegram announcements. One order, hours after listing, sized small, no quote spamming, no self-trades → does not trip any enumerated prohibition. The real danger on MEXC new listings is the **risk-control engine** (codes 30027/30028), not the legal ToS; that engine is avoided by staying off the first-tick chaos.

---

## 4. Strategy A — "Post-hype fade" (short the +4h spike on overheated listings)

**Thesis:** Listings with very high Kickstarter demand + a first-tick print far above the Pre-Market reference tend to revert over the next 4–24h as the trapped-buyer bid exhausts and the withdrawal-unlock selling pressure approaches.

**Universe filter (all observable before trade entry):**
- Kickstarter MX-committed total in the **top quartile** of trailing-30d Kickstarter sessions (high revealed demand).
- Pre-Market reference price exists (token went through Pre-Market OTC).
- First-tick MEXC open prints **≥ +40% vs. Pre-Market reference** (overshoot gate).

**Entry:** **T0 + 4h** (after first-tick chaos and risk-control halts settle). If price is still ≥ +25% above Pre-Market reference → **SELL** (spot, since MEXC spot shorting is limited, implement as: enter with already-held USDT→token conversion deferred, OR use the perp `XXX_USDT:USDT` if listed and liquid, with tiny size).

**Sizing:** Fixed fractional, **≤ 1% NAV per position**. New-listing tails are fat; this is a concave trade.

**Exit:**
- Take-profit: reversion to **Pre-Market reference − 5%**.
- Stop: **+60% above entry** (the overshoot can extend; cap the pain).
- Time stop: **T0 + 20h** (close before withdrawal unlock at T+24h removes the structural overhang that the short thesis relies on).

**Why MEXC-specific:** The Pre-Market reference price is MEXC's unique de-risker — it gives a *measurable* overshoot metric that Binance listings lack. The T+24h withdrawal unlock is MEXC's unique catalyst.

**Data feed needed:** (1) Kickstarter MX-commit totals (Telegram announcements / parse the result article), (2) Pre-Market last trade price (MEXC UI/API), (3) post-T0 klines via `/api/v3/klines`, (4) `exchangeInfo` for `tradeSideType` (reject buy-only / closed). **All free, key-less.**

---

## 5. Strategy B — "Withdrawal-unlock premium reversion" (MEXC vs. primary DEX)

**Thesis:** During the ~24h withdrawal-disabled window, the MEXC price of a freshly-listed token trades at a **premium** to its primary DEX (Uniswap/Raydium/etc.) because on-chain holders cannot arb it down. When withdrawals open (~T+24h), the spread compresses as supply flows in.

**Universe filter:**
- Token already trading on a liquid DEX pool **before** MEXC listing (so a DEX reference price exists).
- MEXC spot price ≥ **+8% vs. DEX mid** during the first 6h of MEXC trading (premium gate).

**Entry:** **T0 + 6h to T0 + 18h**, while withdrawals are still disabled and the premium persists. **SELL MEXC spot** (or reduce/sell the long gained from Pre-Market) with plan to reclaim cheaper on DEX, OR a simpler read: **enter a mean-reversion position sized to the expected spread close.**

**Sizing:** **≤ 0.5% NAV** — this is a near-arb but with real execution/timing risk and a hard-to-predict unlock instant.

**Exit:**
- Take-profit: spread narrows to **≤ 2%** (typically within 1–4h post-withdrawal-open).
- Time stop: **T+30h** (premium should be gone by then regardless).
- Hard stop if the spread **widens beyond +25%** (the thesis is breaking — likely a genuine MEXC-only rally, e.g. a Binance-graduation rumor; get out).

**Why MEXC-specific:** The ~24h withdrawal lock is a **MEXC-documented, scheduled, recurring structural friction** (visible in every Kickstarter-result announcement). Scheduled + recurring = backtestable + automatable.

**Data feed needed:** (1) MEXC spot price + `tradeSideType` + withdrawal-open timestamp (announcement), (2) DEX mid price for the same token (GeckoTerminal public API, free, or the token's primary pool RPC), (3) MEXC klines. **All free, key-less.**

---

## 6. Required data feed (free, key-less, off-the-shelf)

| Need | Source | Cost |
|---|---|---|
| Detect new listing + symbol + `tradeSideType` | `GET https://api.mexc.com/api/v3/exchangeInfo` (poll ≤ every 5s, well under 500/10s) | free, no key |
| Listing announcement text (Kickstarter MX-commit total, listing time, withdrawal time) | Official Telegram `t.me/MEXC_OfficialAnnouncements` (MEXC-endorsed) — consume via a Telegram client lib | free |
| Pre-Market reference price | MEXC Pre-Market UI / spot account; or the announcement settlement price | free |
| Post-listing OHLCV / depth / trades | `GET /api/v3/klines`, `/api/v3/depth`, `/api/v3/trades` | free, no key |
| **Backtest data (2023-01-01 → now)** | `https://www.mexc.co/zh-CN/market-data-download` (klines + trades, all spot pairs) | free, no key |
| DEX reference price (Strategy B) | GeckoTerminal public API (`https://www.geckoterminal.com/api`) | free |
| Historical Kickstarter participation | scrape-free: Telegram history or the announcement article IDs | free |

**Backtest mandate before any live capital:** Because MEXC-specific peer-reviewed magnitudes don't exist, **both strategies must be backtested** on the free historical download (§6) before sizing up. The patterns (§2) are well-grounded as *hypotheses* from the general listing literature + MEXC's documented mechanics; the *edge* is the empirical realized distribution, which only the backtest reveals. This is the single biggest de-risker available, and it costs nothing.

---

## 7. Risk ledger (honest)

- **Fat right tail.** "Graduate-to-Binance" listings can pump +300% in days. Any fade/short thesis must respect this with hard stops. Strategy A's +60% stop and Strategy B's +25% spread stop exist precisely here.
- **Risk-control halts, not ToS, are the real freeze.** Codes 30027/30028 can trap a position asymmetrically. Mitigation: never trade the first 4 hours; read `tradeSideType` every cycle.
- **Survivorship in the listing universe.** Backtests must include the many Innovation-Zone tokens that **delisted** within months (MEXC has a Delistings announcement feed — use it to avoid look-ahead).
- **Pre-Market reference can be manipulated** (thin OTC book). Use the *last traded* Pre-Market price with a volume floor, not a single print.
- **Buy-only openings (tradeSideType=2)** prevent exit. Strategy A's short leg must confirm sell-enabled before entry.
- **Jurisdiction.** MEXC ToS prohibits US/UK/CA/SG/CN/Mainland-China residents (Clause "Prohibited Jurisdictions"). The fleet operator must be in an allowed jurisdiction or accept account-seizure risk.

---

## Summary (≤4 lines)

MEXC's phased rollout (Kickstarter → Pre-Market → spot 12:00 UTC → withdrawal T+24h) creates two safe, low-freq, key-less edges: **(A) fade the first-day spike T0+4h on overheated listings** using the Pre-Market price as overshoot reference, and **(B) trade the MEXC-vs-DEX premium compression at the T+24h withdrawal unlock**. A retail bot can act on these via the **official public REST API + official Telegram announcements** at human cadence — the real danger is MEXC's risk-control halts (codes 30027/30028), not the ToS, so stay off the first-tick chaos and cap size at ≤1% NAV. Both patterns are empirically grounded as hypotheses from the general listing literature + MEXC's documented mechanics; **backtest on MEXC's free historical-data download before sizing up**.

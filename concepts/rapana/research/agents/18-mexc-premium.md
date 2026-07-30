# 18 — The MEXC Premium/Discount as an INFORMATIONAL Signal (Single-Leg, No Cross-Venue Arb)

**Agent:** 18/60 · **Scope:** cross-venue price deviation as a *mean-reversion signal source*, executed **single-leg on MEXC only** — explicitly **NOT** as executable cross-venue arbitrage.
**Hard constraint (load-bearing):** MEXC restricts retail cross-venue / HFT / "malicious arbitrage" and freezes accounts for it (`RESEARCH-SYNTHESIS.md:90,108`; MEXC anti-bot article, §1–2). This entire note is built around the **informational read** of the gap; the execution leg is one directional MEXC trade, indistinguishable from any other signal-driven order. See §c for the full ToS analysis.

All repo citations are `file:line`. External claims are URL-cited in §f.

---

## (a) Does a systematic MEXC premium/discount exist? Why, and how big?

**Short answer: yes, but it is regime- and tier-dependent.** For the most liquid majors (BTC, ETH, SOL) the MEXC-vs-global gap has collapsed toward noise since 2018. For mid/low-cap altcoins, newly-listed tokens, and MEXC-exclusive listings, a *persistent, mean-reverting* premium/discount is a documented structural feature of fragmented crypto markets — and MEXC is structurally the venue most exposed to those tiers.

### Why a persistent gap exists (mechanism)

| Driver | Effect on MEXC price | Evidence |
|---|---|---|
| **MEXC-exclusive / first listings** | MEXC is the *only* or *first* venue for many tokens → local order flow sets a regional price with no on-venue counterparty to pull it to a global mid | MEXC anti-bot article itself: *"certain digital assets may **only be available for trading on MEXC**"* (§1) |
| **Thinner books on mid-caps** | Smaller depth → same net flow moves price more → larger, slower-to-close deviations | S&P Global: crypto liquidity *"remains fragmented... can lead to price differences, market inefficiencies"* (Liu 2025 §2) |
| **Regional / retail flow asymmetry** | MEXC's user base skews toward regions/segments with different demand pressure than Binance/OKX/Kraken → consistent directional bias per token | Bruzgė & Šapkauskienė (2022): some venues *consistently* cheaper (Kraken, Bitstamp, DSX) vs consistently expensive (CEX.io) — structural/regional, not random |
| **Listing-timing & "first-print" momentum** | A token lists on MEXC days/weeks before larger venues → MEXC price is a noisy leading indicator then mean-reverts once cross-venue liquidity arrives | Repo already detects this event via `load_markets(reload=True)` (`research/agents/08-mexc-client-edge.md:63`) |
| **0-Fee Fest / incentive events** | Fee subsidies skew maker/taker behavior and temporarily inflate or deflate local mid vs global | MEXC anti-bot article §3: *"0-Fee Fest... could be exploited by arbitrage traders"* |

### Magnitudes (from the literature)

| Study / source | Venue set | Finding | Magnitude |
|---|---|---|---|
| **Makarov & Schoar (2020)**, J. Financial Economics | 34 exchanges, BTC | "large and recurring deviations"; spreads **widen during stress/momentum**; within-country spreads much smaller | up to **~40%** cross-border (Korea "Kimchi premium", Dec 2017–Feb 2018); **<1%** within-country |
| **Shynkevich (2023)**, J. Econ & Finance (Springer) | 6 exchanges, BTC & ETH | deviations became **more integrated since 2018**; profitable cross-exchange arb *"declined significantly since 2018"* | convergence (mean-reversion) is the dominant dynamic |
| **Crépellière, Pelster, Zeisberger (2023)** | multi-venue | arb opportunities *"decreased greatly from April 2018 onward"*; now *"barely possible to exploit existing price differences"* | near-zero *executable* edge for majors |
| **Bruzgė & Šapkauskienė (2022)** | 13 exchanges, BTC | **persistent** per-venue bias (cheap vs expensive venues); long tail of larger gaps | median gap a few €/BTC; **25% of gaps > €8–16/BTC** |
| **CoinAPI (2024)** | industry | net margin per arb trade is razor-thin; gross spread needed to net profit after fees+slip | **0.3–0.5% gross** → **~0.01–0.05% net**; HFT needs sub-ms, retail 100–500ms only catches gaps persisting **minutes** |

**Read-through for Rapana:**
- For **Tier-A majors** the *executable* cross-venue edge is dead and illegal anyway — but the **signal** (deviation → reverts) is still weakly present and very cheap to read.
- The **signal concentrates** where the repo already hunts: mid/low-cap universe + newly-listed/MEXC-exclusive tokens. There, persistent deviations of tens to hundreds of bps that revert over minutes-to-hours are realistic and exactly the cadence Rapana runs at.
- The "retail 100–500ms only catches gaps that persist minutes" point is **perfect**: it defines the *informational* (slow, mean-reverting) regime and explicitly excludes the *executable* (sub-ms latency arb) regime MEXC freezes accounts for.

---

## (b) The signal: deviation as a single-leg mean-reversion trade on MEXC

### The core idea
Define the **MEXC premium** of a token against a global reference midpoint:

```
global_mid = median( last_price[Binance], last_price[OKX], last_price[Kraken] )   # free, public, no keys
deviation  = ( mexc_last - global_mid ) / global_mid                                # +ve = MEXC rich, -ve = MEXC cheap
```

Treat a **persistent** deviation as a **fade signal executed entirely on MEXC**:

| Deviation regime | Interpretation | Single-leg MEXC action | Signal |
|---|---|---|---|
| MEXC persistently **rich** (deviation ≫ 0, aged ≥ N bars) | local flow overbid vs the world → reverts as global flow/arbitrageurs (the real ones, institutional) pull it back | **fade / sell** (or trim an existing long) on MEXC | bearish |
| MEXC persistently **cheap** (deviation ≪ 0, aged ≥ N bars) | local flow oversold / capitulation vs the world → reverts up | **buy** on MEXC | bullish |
| |deviation| small or un-aged | noise / MEXC-leading move (see caveat 4) | neutral |

**This is a directional mean-reversion bet on one venue, not arbitrage.** There is no second leg on another exchange, no inventory to cycle, no "riskless profit," and no exploitation of MEXC's liquidity. The external reference price is just *information*, the same way an RSI reading or a funding-rate print is information. The trade lives or dies on whether the MEXC price reverts — same P&L distribution as any other Rapana signal.

### Why this is a *better* mean-reversion signal than price-only TA
The repo's own evidence (`research/agents/01-strategy-edge.md:98-134`) shows the three price-only strategies (trend/meanrev/breakout) failed the honest gate *because* they lack a cross-sectional / structural anchor. A deviation-vs-global-mid is precisely that anchor:
- It is a **cointegration-style** mean-reversion trigger (reversion *to a known external fair value*), not a naive "revert to own moving average."
- It carries genuinely **new information** not in MEXC OHLCV — what the rest of the world thinks the price is.
- It gets its **own `source` bucket** in `ReflectionMemory` (`signals.py:87-104`, `fleet/memory.py:114-121`), so the learning loop can credit/penalize it independently of the (already-disproven) "market" bucket.

### Honest caveats — how much of the gap is untradeable

1. **Withdrawal fees / transfer time are irrelevant here.** They only matter for *executable* cross-venue arb (move coins to the cheap venue, sell on the rich one). For a single-leg informational trade **no transfer ever happens** — you only ever touch MEXC. This removes the single biggest arb-killer.
2. **Reference-price staleness / "MEXC leads."** If MEXC moves *first* (plausible for MEXC-exclusive listings), the instantaneous "deviation" is really the *world lagging MEXC* — fading it would be wrong. **Mitigation:** require the deviation to **persist ≥ N bars** (aging filter) before emitting; a true MEXC-leading move reverts the global mid toward MEXC, not the reverse, and won't stay aged.
3. **Latency.** CCXT REST polling from a retail host is ~100–500ms per call; useless for latency arb (which we are not doing), perfectly adequate for a per-cycle (minutes-to-hours) mean-reversion signal.
4. **Major-pair signal-to-noise is poor.** Post-2018 the gap for BTC/ETH/SOL is near-zero (Shynkevich 2023; Crépellière 2023). The edge lives in mid/low-cap and newly-listed tokens. **Scope the analyst to the universe where MEXC depth is materially thinner than the reference venues.**
5. **MEXC-exclusive tokens have no reference.** If a token trades *only* on MEXC, there is no global mid — the analyst must emit neutral (the feed's fail-soft contract already mandates this, `feeds/base.py:6-14`).
6. **Structural vs transient gaps.** Some persistent deviations are *sticky* (regional flow) and only revert on regime change, not intra-day. Size accordingly and let `ReflectionMemory` down-weight the source if hit-rate is poor.

---

## (c) ToS analysis — is single-leg deviation-fade legal on MEXC?

**Verdict: yes, with discipline.** This is the single most important section of this note. The reasoning rests on what MEXC's own policy actually prohibits.

### What MEXC explicitly prohibits (from the primary source)
The MEXC anti-bot article (mexc.com/support/article/why-mexc-restricts-automated-trading-17827791531135) names the banned behavior precisely:
- *"**malicious arbitrage** behavior may create liquidity imbalances and contribute to abnormal price fluctuations"* (§3)
- *"**high-frequency arbitrage** activity can reduce opportunities for ordinary users, disrupt normal market activity"* (§3)
- banned activity = *"API abuse, bot trading, or algorithmic trading"*; first offense freeze + investigation, repeat = permanent (§2)
- the stated goal is to stop users who *"take advantage of the platform's liquidity and lower trading costs"* and to protect *"0-Fee Fest"* events from *"arbitrage traders or automated bots"* (§1, §3)

The freeze trigger is therefore **(cross-venue/multi-leg) arbitrage + high frequency + liquidity-imbalance exploitation**. Each of those three is an independent reason the single-leg fade is on the right side of the line:

| MEXC's stated concern | Single-leg deviation-fade | Verdict |
|---|---|---|
| "malicious arbitrage" / "liquidity imbalances" | One directional MEXC order, **no offsetting leg** on another venue, **no inventory cycling**, no riskless profit, no imbalance creation | **Not arbitrage** — it's a directional bet |
| "high-frequency" | Emitted per fleet cycle (minutes–hours), **maker-preferred** (rests on book), not sub-second | **Not HFT** |
| "reduce opportunities for ordinary users / disrupt market" | A small maker order adds liquidity and is invisible at market scale | **Not disruptive** |
| "exploit 0-Fee Fest" | Sizing is tiny vs event volume; no racing of subsidized fees | **Not fee-exploitative** |

To MEXC's monitoring, a single maker order placed once per cycle because a global price feed deviated is **indistinguishable** from any other directional signal the fleet emits (sentiment, macro, funding-fade). The defining fingerprint of the banned behavior — *correlated, near-simultaneous, multi-leg activity across venues with rapid inventory turnover* — is structurally absent.

### The line you must not cross (enforcement hygiene)
MEXC's risk engine is opaque and pattern-matches on "looks like a bot exploiting us." Keep the behavior self-evidently benign:
- **Single venue, single leg.** Never place the offsetting trade on Binance/OKX/Kraken from the same control — that is the literal definition of the banned arb. (Reading their *public tickers* is not trading there; it's reading public market data, which is unrestricted.)
- **Low cadence.** Evaluate per cycle, not per tick; cap orders/min via the existing `OrderRateLimiter` (`fleet/orchestrator.py:112`).
- **Maker-preferred.** Use `postOnly` limit orders (the repo's proposed `create_maker_order`, `08-mexc-client-edge.md:88`) so orders *rest* and add liquidity, the exact posture MEXC welcomes.
- **Human-varied, small size.** No laser-precise sizing that tracks the reference to the cent; keep well under `max_notional_per_order`.
- **Don't run during 0-Fee Fest windows** unless explicitly cleared — that is the highest-scrutiny period by MEXC's own statement.

> **Bottom line on ToS:** reading public global prices and using them to inform a *single, slow, maker* MEXC trade is ToS-safe. The freeze risk attaches to *executing the other leg elsewhere* or to *speed*. Rapana does neither.

---

## (d) Cheap "global midpoint reference" — free, no keys, via CCXT

The repo already uses a free, no-key global reference — CoinGecko — in `MarketPremiumFeed` (`feeds/market_premium.py:39-51`). For the deviation signal we want a **point-in-time multi-venue midpoint**, which CCXT public tickers give for free:

### Source options (all free, all public read-only)
| Source | How | Pros | Cons |
|---|---|---|---|
| **CCXT `binance.fetchTicker`/`fetchTickers`** | `ccxt.binance({'enableRateLimit':True})`, no API key needed for public market data | Binance is the documented **price leader / "fair value"** reference (Liu 2025: *"many arbitrage strategies treat Binance price as fair value"*); tightest, most liquid book | Geo-blocks in some regions (fallback below) |
| **CCXT `okx.fetchTicker`** | same pattern | Independent venue → diversifies the midpoint | — |
| **CCXT `kraken.fetchTicker`** | same pattern | US/EU flow anchor; structurally "cheaper" venue per Bruzgė & Šapkauskienė | Lower altcoin coverage |
| **CoinGecko `/simple/price`** (already in repo) | `feeds/market_premium.py:44-48` | Volume-weighted global avg; no key; widest coverage incl. obscure tokens | Aggregated/laggy; not point-in-time; rate-limited |

**Recommended construction:** `global_mid = median(binance_last, okx_last, kraken_last)` when ≥2 venues return a price; **fall back to CoinGecko** when fewer than 2 venues list the token or any is geo-blocked. Median (not mean) rejects a single stale/errant venue. This is strictly an upgrade of the existing `MarketPremiumFeed` (CoinGecko-only) to a multi-venue, point-in-time reference with graceful degradation.

### CCXT reality check (verified from docs.ccxt.com)
- `fetchTicker(symbol)` and `fetchTickers([symbols])` are **public market-data endpoints** on every major exchange; no authentication, no KYC, no special access — confirmed for `binance`, `okx`, `kraken` (and `mexc`) in the CCXT manual. Reading them is not a "trade" on those venues and violates no venue's ToS.
- `enableRateLimit=True` + the repo's existing rate-limit hygiene keep you well under public-endpoint quotas.
- The repo already imports CCXT and wraps `ccxt.mexc` (`mexc/client.py:15-19,38`); adding unauthenticated `ccxt.binance/okx/kraken` instances is a trivial, additive change with **no new auth surface, no new secrets, no KYB**.

---

## (e) Proposal — `GlobalPriceReferenceAnalyst` (single-leg mean-reversion, source="global_ref")

A new `Analyst` + `Feed` pair that drops into the existing injectable architecture with **zero core rewrite**, mirroring the proven `MarketPremiumFeed` + `Arbitrageur` templates.

### Fit with the existing contract (why this is cheap)
- **`Feed` ABC** (`feeds/base.py:6-14`): `score(symbol) -> (score[-1..1], confidence[0..1])`, fail-soft `(0.0,0.0)`. A `GlobalReferenceFeed` is a near-clone of `feeds/market_premium.py` — swap CoinGecko for the CCXT midpoint + add the aging filter.
- **`Analyst` ABC** (`agents/base.py:26`, consumed at `fleet/orchestrator.py:91-95`): `analyze(symbol, provider) -> Signal`. Mirror `agents/arbitrage.py:13-34` (28 lines).
- **`Signal` currency** (`signals.py:17-46`): sign-auto-corrected, clamped, with a free `extras: dict` — stash `deviation_bps`, `n_venues`, `age_bars` here for journaling/audit without touching the combiner.
- **Distinct `source="global_ref"`** → its **own `ReflectionMemory` bucket** (`memory.py:114-121`); accuracy-weighted in `[0.3, 1.5]` independently of the (disproven) "market" bucket. This is the whole point of using an `Analyst`, not a `Strategy` (which would be folded into `source="market"` and lose its learnable identity, `research/agents/01-strategy-edge.md:30-43`).

### Components

**1. `GlobalReferenceFeed(Feed)`** — `rapana/feeds/global_reference.py` (mirror `feeds/market_premium.py`)
- Construct with a `mexc_price` callable (same as today) + a small dict of unauthenticated CCXT instances `{binance, okx, kraken}` (one-time, no keys).
- `_global_mid(symbol)`: query each venue's `fetchTicker`; collect `last` prices for symbols that exist; return `median(prices)` if ≥2 venues respond, else fall back to the existing CoinGecko path (`feeds/market_premium.py:39-51`), else `None`.
- **Aging/persistence filter** (the key addition vs. `MarketPremiumFeed`): keep a small rolling buffer of `deviation` per symbol; only return a non-zero score when the sign of the deviation has been stable for ≥ `min_age_bars` (e.g. 3 cycles). This implements caveat (b)-2 ("don't fade a MEXC-leading move") directly in the feed.
- `score(symbol)`:
  ```
  dev = (mexc_last - global_mid) / global_mid        # + rich, - cheap
  if not persisted(dev, min_age_bars): return 0.0, 0.0
  score       = clamp(-dev * k, -1, 1)               # rich -> bearish (fade), cheap -> bullish
  confidence  = clamp(|dev| * c, 0, 1)              # scale with magnitude; ReflectionMemory calibrates over time
  ```
  This is the **exact** sign convention already in `feeds/market_premium.py:62-65` ("lean opposite to the premium"), generalised with a multi-venue midpoint and an aging gate.

**2. `GlobalPriceReferenceAnalyst(Analyst)`** — `rapana/agents/global_reference.py` (mirror `agents/arbitrage.py`)
- `role = "global_ref_analyst"`, takes the `GlobalReferenceFeed.score` as its callable.
- Emits `Signal(symbol, source="global_ref", direction, strength=score, confidence, rationale, extras={deviation_bps, n_venues, age_bars})`.
- Neutral when feed fails soft or symbol has no reference (MEXC-exclusive) — never forces a trade (`agents/arbitrage.py:27-28` pattern).

**3. Wiring** — `Fleet.analysts` (`fleet/orchestrator.py:91-95`) append the new analyst; register in `agents/__init__.py`. No `Strategy`, no core change, no schema change, no new secrets.

### Execution-side notes (keep it ToS-clean)
- The PM is spot long/flatten (`agents/portfolio_manager.py:55-81`): a **bearish** "MEXC-rich" signal can only *trim/exit* an existing long — which is exactly the right action when local flow is overbid. A **bullish** "MEXC-cheap" signal enters a long. Both are single-leg on MEXC.
- Prefer the proposed maker path (`08-mexc-client-edge.md:88`) for entry/exit so orders rest and add liquidity (ToS hygiene, §c).
- Size via the normal `min(max_weight, |net|)` logic; the deviation analyst is just one vote in `weighted_combine` (`signals.py:87-104`).

### Why this beats the existing `MarketPremiumFeed` for this purpose
| | `MarketPremiumFeed` (today) | Proposed `GlobalReferenceFeed` |
|---|---|---|
| Reference | CoinGecko single avg (laggy, aggregated) | median of 3 live venues (point-in-time) |
| MEXC-leading filter | none | aging gate (caveat b-2) |
| Wiring | not clearly routed to a distinct `source` | own `source="global_ref"` bucket → learnable |
| Failure mode | CoinGecko outage → silent | graceful degrade CoinGecko ← CCXT |

---

## (f) Sources (verified, load-bearing)

- **MEXC "Why MEXC Restricts Automated Trading"** (primary ToS source) — mexc.com/support/article/why-mexc-restricts-automated-trading-17827791531135 · quotes in §a, §c (§1–§3).
- **MEXC User Agreement / Risk Control Guidelines** — mexc.com/terms (Prohibited Jurisdictions; Risk of Account Being Frozen §3(i)).
- **Makarov I., Schoar A. (2020), "Trading and Arbitrage in Cryptocurrency Markets,"** *J. Financial Economics* 135:293–319 — up to ~40% cross-border BTC premium (Korea), <1% within-country, spreads widen under stress.
- **Shynkevich A. (2023), "Law of one price and return on Arbitrage Trading: Bitcoin vs. Ethereum,"** *J. Econ & Finance* 47:763–792 — doi.org/10.1007/s12197-023-09631-0 · deviations integrated/converging since 2018; profitable arb "declined significantly."
- **Crépellière, Pelster, Zeisberger (2023)** — arbitrage opportunities "decreased greatly from April 2018 onward," now "barely possible to exploit" (cited via Liu 2025; UZH ZORA 234451).
- **Bruzgė & Šapkauskienė (2022), "Network analysis on Bitcoin arbitrage opportunities"** — persistent per-venue cheap/expensive bias; 25% of gaps > €8–16/BTC (cited via Liu 2025; Scribd 663353933).
- **Liu J.-H. (2025), "High-Frequency Arbitrage and Profit Maximization Across Cryptocurrency Exchanges"** (survey) — medium.com/@gwrx2005/...4842d7b7d4d9 · Binance as price leader; retail 100–500ms catches only minute-scale gaps; HFT sub-ms; razor-thin net 0.01–0.1%.
- **CoinAPI (2024), "Crypto Arbitrage FAQ"** — coinapi.io/blog/crypto-arbitrage-faq-15-questions-every-trader-asks · 0.3–0.5% gross needed to net ~0.1% after fees+slip.
- **CCXT manual — `mexc` / public market data** — docs.ccxt.com/docs/exchanges/mexc (`fetchTicker`, `fetchTickers` public; `enableRateLimit`).
- **Repo priors** — `RESEARCH-SYNTHESIS.md:90,108,110` (MEXC anti-bot/freeze constraint); `research/agents/01-strategy-edge.md` (Strategy vs Analyst contract, funding/basis analogues); `research/agents/08-mexc-client-edge.md` (reachable read-only edges, proposed maker order).

---

## Bottom line

The executable cross-venue arbitrage is both dead (post-2018 convergence) and illegal on MEXC (freeze trigger) — so **don't do it**. But the *information* in the gap is alive, cheap, and ToS-clean: read a free CCXT midpoint of Binance/OKX/Kraken, age it to reject MEXC-leading noise, and fade persistent MEXC richness (or buy persistent cheapness) as a **single slow maker leg on MEXC**, under its own learnable `source="global_ref"` bucket. Edge concentrates in mid/low-cap and newly-listed tokens where MEXC books are thinnest; majors are near-noise and should be scoped out.

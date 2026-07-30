# 19 — Calendar / Day-of-Week / Hour-of-Day / Turn-of-Month Anomalies in Crypto

**Agent:** 19/60 · **Scope:** deterministic, clock-driven price patterns (weekend / Monday / turn-of-month / hour-of-day) as a **low-frequency spot-only Signal source** for rapana.
**Hard constraint (load-bearing):** MEXC Safe Operating Envelope — spot-only, post-only maker, ≤1 order/symbol/60s, cancel ratio ≤30%, no arb, no symmetric hedge, event blackouts ±5min, **low-frequency** (`research/agents/16-tos-envelope.md`; `RESEARCH-SYNTHESIS.md:90,108`). Calendar signals are the *lowest*-frequency edges in the fleet (monthly / daily), so they fit the envelope by construction — no special ToS risk. Futures angles are research/signal-only (KYB-gated).

Repo citations are `file:line`. External claims are URL-cited in §f. Effect sizes are reported honestly; the literature's headline numbers are pre-2020 and **substantially decayed** — that is the central finding of this note.

---

## (a) Does crypto have a calendar anomaly? Evidence table

**Short answer: yes, several existed and were statistically significant pre-2020; most (weekend, Monday, Halloween) have *decayed toward noise* post-2020 under institutionalisation + ETFs. The survivors are (i) the turn-of-month (TOM) / within-month effect and (ii) structural intraday *volatility/liquidity* periodicity tied to participant geography — which has NOT decayed because geography hasn't.**

| # | Study (year, venue) | Sample | Anomaly | Effect size (as reported) | URL |
|---|---|---|---|---|---|
| 1 | **Baur, Cahill, Godfrey, Liu (2019)** *Finance Research Letters* — "Bitcoin time-of-day, day-of-week and month-of-year effects" | 15M+ obs, 7 exchanges, 2011–2018 | **Weekend effect**: BTC returns higher on Sat/Sun; **time-of-day** spikes; effects concentrate in early era | Weekend daily return **~+0.40%** vs **~0.0%** weekday in the full sample; effect **driven by 2011–2013**, weaker later | sciencedirect.com/science/article/pii/S1544612319301710 |
| 2 | **Aharon & Qadan (2019)** *Finance Research Letters* — "Bitcoin and the day-of-the-week effect" (197 cites) | BTC, 2010–2018 | **Monday effect** in returns AND volatility (reverse of equities) | Monday mean return highest; DOW coefficient significant pre-2017 | sciencedirect.com/science/article/pii/S1544612317307894 |
| 3 | **Caporale & Plastun (2019)** *Finance Research Letters* — "The day of the week effect in the cryptocurrency market" (271 cites) | BTC, 2013–2017 | Monday anomaly; non-persistent after first appearance | Monday return **~0.7–1.0%** above other days in early subsample; **disappears after** detection | sciencedirect.com/science/article/pii/S1544612318304240 |
| 4 | **Kinateder & Papavassiliou (2021)** *Finance Research Letters* — "Calendar effects in bitcoin returns and volatility" (110 cites) | BTC, 2014–2020 | **Weekend effect NOT in returns**; significantly **lower weekend volatility**; Halloween effect in returns | Weekend vol lower; Halloween (Oct–Apr) **+** — magnitude small (~1–2% seasonal) | sciencedirect.com/science/article/pii/S1544612319311316 |
| 5 | **Kaiser (2019)** *Finance Research Letters* — "Seasonality in cryptocurrencies" (124 cites) | top-6 crypto, 2014–2018 | TOM, Halloween, month-of-year | "consistent and robust calendar effects"; TOM window positive abnormal return | sciencedirect.com/science/article/pii/S1544612318304513 |
| 6 | **Kumar (2022)** *Managerial Finance* — "Turn-of-the-month effect in cryptocurrencies" (20 cites) | BTC/ETH/LTC/XRP, 2013–2020 | **TOM effect present** in major cryptos | TOM window (last + first 3 days) yields **positive abnormal returns** vs rest of month | emerald.com/mf/article-abstract/48/5/821/290148 |
| 7 | **Qadan, Aharon, Eichel (2022)** *Finance Research Letters* — "Seasonal and calendar effects and the price efficiency of cryptocurrencies" (81 cites) | 6 cryptos, 2014–2020 | **Within-the-month effect is the ONLY calendar effect common to ALL cryptos**; DOW/weekend/Halloween not universal | TOM/within-month robust; DOW varies by coin | sciencedirect.com/science/article/pii/S1544612321003597 |
| 8 | **Vasileiou (2023)** *IJBAAF* — "Is the turn of the month an anomaly on which an investment strategy could be based? BTC & ETH" | BTC/ETH | TOM strategy backtest; TOM window is **not fixed** — it varies | TOM-based strategy generates abnormal returns; timing must be empirically located | inderscienceonline.com/doi/abs/10.1504/IJBAAF.2023.129336 |
| 9 | **Sahu, Ramírez, Kim (2024)** *JRFM* — "Calendar anomalies & volatility dynamics in cryptocurrencies: DOW before/during COVID" | crypto, 2017–2022 | DOW effect **changed sign/strength** across COVID regimes — i.e. not stable | DOW present in both regimes but **structurally unstable** | mdpi.com/1911-8074/17/8/351 |
| 10 | **Brauneis, Mestel, Theissen (2025)** *Rev. Quant. Finance & Accounting* — "The crypto world trades at tea time: intraday evidence" (13 cites) | multi-venue CEX, hourly | **Intraday volume/return peaks tied to venue geography (UTC)**; volume/returns rise near midnight UTC + US hours | Distinct intraday shape; patterns shift by Americas/Asia/Europe venue | link.springer.com/article/10.1007/s11156-024-01304-1 |
| 11 | **Hansen, Kim, Kimbrough (2024)** *J. Financial Econometrics* — "Periodicity in cryptocurrency volatility and liquidity" (49 cites) | BTC/ETH intraday, 2018–2021 | **Strong intraday + weekly periodicity in vol/liquidity**; low vol **5–12 UTC** (night); weekly trough weekends | Intraday vol in US/EU overlap **~2–3×** the 00:00–06:00 UTC trough | arxiv.org/pdf/2109.12142 · academic.oup.com/jfec/article-abstract/22/1/224/6759403 |
| 12 | **De Nicola (2021)** *Ledger* — "On the intraday behavior of bitcoin" | BTC hourly | Intraday volume seasonality (low night-UTC); **effects expected to disappear as market matures** | Volume trough 00–06 UTC; peak US/EU overlap | ledgerjournal.org/ojs/ledger/article/view/213 |
| 13 | **Mofakham (2022)** SSRN 4209663 — "Bitcoin Investors' Seasonal Trading" | BTC order-flow | **Order imbalance smallest 23:00–24:00 UTC, largest 11:00 UTC** | Imbalance diurnal shape tracks participant geography | papers.ssrn.com/sol3/papers.cfm?abstract_id=4209663 |
| 14 | **Espel (2024)** — "Impact of US Bitcoin ETF introduction on BTC/ETH intraday regime seasonality" | BTC/ETH intraday | Post-ETF, **20:00–21:00 UTC volume surge** (US ETF flow); Asia/Europe overlap 06:00–10:45 UTC | ETF arrival reshaped the intraday shape toward US hours | link.springer.com/chapter/10.1007/978-3-031-73122-8_3 |
| 15 | **Rech, Meng, Musa (2025)** *J. Risk & Financial Mgmt* (adj.) — "Calendar Anomalies in DeFi Assets" | DeFi, 2020–2023 | Calendar anomalies **"peaked mid-20th century and have since largely disappeared"** — in the mature crypto corner, anomalies are gone | Near-zero exploitable calendar alpha in 2020–2023 DeFi | search.ebscohost.com (J. 1804171X, AN 188964902) |

**Read-through for rapana:**
- The three classic equity-style calendar effects — **weekend, Monday, Halloween** — were real in 2011–2018 BTC but (a) were **driven by the early illiquid era** (Baur et al. finding the effect concentrates in 2011–2013), (b) are **not universal across coins** (Qadan 2022), and (c) are **destined to decay** (De Nicola 2021; Rech 2025). Standalone trading of these in 2026 is a bet on a structural break that has already started.
- The **turn-of-month / within-month** effect is the one calendar anomaly Qadan (2022) found **common to every cryptocurrency tested** — the most robust of the lot, and still positive in Kumar (2022) through 2020. This is the candidate for a real, durable, low-frequency edge.
- The **intraday periodicity of volatility and liquidity** (Hansen 2024; Brauneis 2025) is **structural, not an alpha** — it reflects that participants sleep. It has *not* decayed and is exploitable as **execution-timing alpha** (place maker orders in the thin night window for adverse-selection reasons, *avoid* it for liquidity), not as a directional bet.

---

## (b) Durability vs transaction costs + post-2020 decay

### Does the edge survive a round trip on MEXC spot?

Rapana's fee reality (from `research/agents/09-mexc-maker-fee.md`): **0% maker** with MX-deduct (the durable path); **~20bp taker** baseline; BTC/USDT spread **~1bp**, ETH/SOL similar, mid-caps **5–15bp**, exchange-wide avg **~62bp**. Round-trip cost at maker on a major is therefore **≈ 0 explicit + ~2bp adverse selection/spread**; at taker it's **~40bp + spread**. The maker path is decisive for whether calendar edges are tradeable.

| Anomaly | Gross edge (literature) | Round-trip cost (maker, BTC) | Net, honest | Verdict |
|---|---|---|---|---|
| **Weekend / Monday DOW** (pre-2020) | ~0.4–1.0%/day | ~2bp | **Negative post-2020** — decayed to ~0 gross (De Nicola 2021; Rech 2025) | **Do not trade standalone** |
| **Halloween / seasonal** | ~1–2% over 6 months | ~2bp × low turnover | Marginally positive but **one trade / 6 months** → tiny annualised Sharpe; decay risk | **Weak; informational only** |
| **Turn-of-month (TOM)** | ~0.5–2.0% cumulative over ~4-day window (Kumar 2022; Kaiser 2019) | ~2bp × 1 round trip/month | **Net positive even after fees**; ~50–200bp gross − ~2–5bp cost ≈ **+0.5–1.8% per event**, ~6–12%/yr if it holds (big "if") | **Tradeable candidate** |
| **Intraday vol/liquidity periodicity** | Not a directional alpha | n/a | **Execution-timing alpha** — improves fills of *other* signals; ≈ 1–3bp/save | **Route as a timing modulator** |
| **Intraday directional (Asia-open / US-open strength)** | small, unstable (Brauneis 2025; Espel 2024) | ~2bp | Unstable post-ETF; **not robust enough** for a standalone signal | **Informational only** |

### The decay story (why weekend/Monday are mostly gone)

1. **Institutionalisation 2020–2024.** 24/7 market-making desks and basis traders flatten any weekend premium within minutes — the same convergence dynamic that killed cross-venue BTC arb (`research/agents/18-mexc-premium.md:30` citing Shynkevich 2023; Crépellière 2023).
2. **US spot ETFs (Jan 2024).** Espel (2024) shows the ETF reshaped intraday volume toward US hours (20–21 UTC surge). Weekend *returns* collapsed because the marginal price-setter is now a weekday-US-hours institution, not a weekend retail flow.
3. **Effect-halflife.** Caporale & Plastun (2019) explicitly note the Monday anomaly **"disappears after"** first detection — the classic "anomaly decay on publication." Anything published before 2020 has had 5+ years to be arbed.
4. **Regime instability.** Sahu et al. (2024) show the DOW effect **changed sign** across the COVID boundary — so even where "statistically significant," it is not stable enough to bet on with a fixed rule.

**Bottom line on durability:** **only TOM and intraday-volatility-timing survive honest scrutiny.** Everything else is either decayed, unstable, or below the fee+spread floor on majors. Scope expectations accordingly: this is a **small, low-Sharpe tilting signal**, not an alpha engine.

---

## (c) ToS analysis — is a clock-driven spot tilt legal on MEXC?

**Verdict: trivially yes.** Calendar strategies are the *safest* possible MEXC posture because they are the antithesis of everything MEXC's anti-bot article prohibits (`research/agents/16-tos-envelope.md`; `18-mexc-premium.md:82-108`):

| MEXC's stated freeze trigger | Calendar tilt | Verdict |
|---|---|---|
| "malicious arbitrage" / "liquidity imbalances" / multi-leg | One directional maker order on one symbol | **Not arb** |
| "high-frequency" | TOM = **1–2 trades/month**; intraday modulator only *reschedules* existing trades | **Not HFT** — comfortably inside `OrderRateLimiter` (`fleet/orchestrator.py:112`) and the ≤1 order/symbol/60s cap |
| "disrupt normal market" / "exploit 0-Fee Fest" | Tiny maker order in a liquid pair, never during promo windows | **Not disruptive** |
| Cancel-ratio ≤30% | A TOM order rests until filled or the window closes — **one cancel/month max** | **Clean** |
| Event blackouts ±5min | Calendar events are *multi-hour windows*; the ±5min blackout around listings/funding is irrelevant | **Clean** |

A monthly maker order placed because the calendar says "TOM window open" is, to MEXC's monitoring, **indistinguishable from any human swing trade**. There is no fingerprint of automation abuse. The only hygiene rule: keep execution maker-preferred (`post_only=True`, the proposed `create_maker_order` in `08-mexc-client-edge.md:88`) so the order rests and adds liquidity.

---

## (d) Proposal 1 — `CalendarTomAnalyst` (turn-of-month tilt, source="calendar")

The one calendar anomaly with cross-coin robustness (Qadan 2022) and fee-survivable magnitude (Kumar 2022). Drops into the existing injectable `Analyst` contract by **mirroring `agents/macro.py:13-31`** (31 lines).

### The schedule (deterministic, UTC)
```
TOM window  = [last 1 trading-day of month, first 3 trading-days of month]  (UTC)
            ≈ 4-day window straddling the month boundary
Entry bias  : bullish during the window (literature: positive abnormal returns)
Outside     : neutral (emit no calendar signal; other analysts drive the book)
```
The exact window edges are not fixed (Vasileiou 2023) — the ReflectionMemory loop (`fleet/memory.py:114-121`) will learn whether last-day+first-3 or first-3-only is the better locator for the current regime. Start with the **last-day + first-3-days** convention (Kumar 2022).

### Sizing & cadence (envelope-safe)
- **1 round trip per month per symbol** at most → ≤12 trades/symbol/yr, orders of magnitude under the ≤1/symbol/60s cap.
- **Maker-only** (`post_only=True`): entry and exit both rest → **0 explicit fee** with MX-deduct, ~2bp total adverse-selection/spread cost on BTC (`09-mexc-maker-fee.md:102-105`).
- **Sizing:** cap the calendar analyst's contribution so it can only *tilt*, never dominate — `strength ≤ 0.35` (below the 0.15 consensus threshold alone, so it needs corroboration from another source to trigger a trade, `signals.py:66-70`). This enforces the honest "weak signal" posture from §b.
- **Universe:** majors first (BTC/ETH/SOL — tightest spreads, cleanest calendar signal, lowest ToS scrutiny). Do NOT run TOM on thin mid-caps: the spread (5–15bp+) plus the documented TOM decay eats the edge.

### Signal spec — emitted into `combine_signals`
Mirrors `agents/macro.py:26-31` exactly; injectable via a `tom_fn(symbol) -> (score, confidence)` callable.

```python
# rapana/agents/calendar_tom.py  (mirror agents/macro.py, ~35 lines)
class CalendarTomAnalyst(Analyst):
    role = "calendar_tom_analyst"
    def __init__(self, tom_fn=None): self.tom_fn = tom_fn
    def analyze(self, symbol, provider):
        if self.tom_fn is None:
            return Signal(symbol, "calendar", "neutral", 0.0, 0.0,
                          "no calendar feed configured")
        score, confidence = self.tom_fn(symbol)
        direction = "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral"
        return Signal(symbol, "calendar", direction, score, confidence,
                      f"TOM window score={score:.2f}")
```

`tom_fn` for the default (clock-only) implementation:
```python
def tom_fn_factory(now_utc):
    def tom_fn(symbol):
        d = now_utc()
        # last day of month OR first 3 days of month
        is_last_day = (d + timedelta(days=1)).month != d.month
        is_first_3  = d.day <= 3
        in_window   = is_last_day or is_first_3
        if not in_window:
            return 0.0, 0.0
        # weak, regime-uncertain bullish tilt; ReflectionMemory calibrates
        return 0.30, 0.45           # strength, confidence
    return tom_fn
```

| Field | Value | Rationale |
|---|---|---|
| `source` | `"calendar"` | Own `ReflectionMemory` bucket (`memory.py:114-121`); accuracy-weighted in `[0.3,1.5]` independently so decay auto-shrinks it |
| `direction` | `"bullish"` inside TOM window, else `"neutral"` | Matches Kumar 2022 / Kaiser 2019 sign; neutral outside so it never forces a trade |
| `strength` | `+0.30` (capped) | Below the 0.15 consensus threshold *alone*; needs corroboration. Honesty about a weak, decaying edge |
| `confidence` | `0.45` | "Real but regime-dependent and decaying" — lets the learning loop down-weight if post-2024 data disappoints |
| `extras` | `{"window":"tom","day":d.day}` | Audit/journal only (`signals.py:25`); no combiner impact |

**Honest expected magnitude after fees:** If Kumar (2022) holds, **~+0.5–1.5% per TOM event net** on BTC at maker. If the post-2020/ETF decay has continued (plausible — Rech 2025), **~0 to slightly negative**. The whole point of routing it through `source="calendar"` + `ReflectionMemory` is that the fleet **learns whether it still works** and auto-shrinks the weight to ~0 if it doesn't — no manual kill required.

---

## (e) Proposal 2 — `CalendarIntradayFeed` (volatility/liquidity timing modulator, source="calendar_intraday")

This is **not a standalone alpha** — it is the structural, non-decayed finding (Hansen 2024; Brauneis 2025; Mofakham 2022) put to work as a **timing/execution modulator** on the *other* analysts' signals. It encodes: "the 00:00–06:00 UTC window is thin and low-vol (bad for liquidity, fine for resting maker orders); the 13:30–21:00 UTC US/EU overlap is high-vol/high-volume (good for liquidity, bad for catching a spike)."

### Two honest uses (do NOT oversell as directional alpha)

**Use A — `strength` boost to *resting* maker entries in the low-vol window.** When another analyst emits bullish and it's 01:00–05:00 UTC, nudge the proposal toward maker entry: spreads are tight relative to volatility, adverse selection is lowest, fill probability on a resting order is highest. This monetises the periodicity directly as **fill-quality alpha** (~1–3bp/save). Express as a weak bullish `strength` add during 00–06 UTC for symbols already net-bullish from other sources.

**Use B — blackout/avoidance of the 13:30–16:00 UTC intraday vol spike for *new entries*.** The US-open spike (Espel 2024; Hansen 2024) is where new bullish signals get the worst fill. The feed can return a small **bearish/neutral tilt** during the 13:30–16:00 UTC spike window to discourage fresh entries there, letting existing positions ride.

### Signal spec
```python
# rapana/feeds/calendar_intraday.py  (mirror feeds/base.py + market_premium.py shape)
class CalendarIntradayFeed(Feed):
    name = "calendar_intraday"
    LOW_VOL_UTC   = range(0, 6)      # 00:00–06:00 UTC: thin, low vol, good for maker
    SPIKE_UTC     = range(13, 16)    # 13:00–16:00 UTC: US-open vol spike, bad for entries
    def score(self, symbol):
        h = datetime.now(timezone.utc).hour
        if h in self.LOW_VOL_UTC:   return +0.15, 0.35   # mild maker-entry lean
        if h in self.SPIKE_UTC:     return -0.15, 0.35   # mild entry avoidance
        return 0.0, 0.0
```
Wrapped in an `Analyst` (mirror `agents/macro.py`) emitting `Signal(symbol, "calendar_intraday", direction, score, confidence, f"UTC hour {h}:00 regime")`.

| Field | Value |
|---|---|
| `source` | `"calendar_intraday"` — own learning bucket |
| `direction` | `"bullish"` 00–06 UTC, `"bearish"` 13–16 UTC, else `"neutral"` |
| `strength` | `±0.15` — deliberately weak; only nudges execution timing of *corroborated* signals |
| `confidence` | `0.35` — structural but small effect |

**Caveat (do not misuse):** intraday *directional* patterns (e.g. "BTC always up at Asia open") are **not robust** (Brauneis 2025 shows the shape shifts by venue; Espel 2024 shows ETFs reshaped it). Resist the temptation to push `strength` above 0.2 — the directional edge is noise; only the *volatility/liquidity* periodicity is durable. Use B (blackout) is safer than Use A (lean).

---

## (f) Sources (verified, load-bearing)

- **Baur, Cahill, Godfrey, Liu (2019)** — "Bitcoin time-of-day, day-of-week and month-of-year effects in returns and trading volume," *Finance Research Letters* — sciencedirect.com/science/article/pii/S1544612319301710 · weekend +0.40%/day driven by 2011–2013; time-of-day spikes present.
- **Aharon & Qadan (2019)** — "Bitcoin and the day-of-the-week effect," *Finance Research Letters* — sciencedirect.com/science/article/pii/S1544612317307894 · Monday effect in returns & vol.
- **Caporale & Plastun (2019)** — "The day of the week effect in the cryptocurrency market," *Finance Research Letters* — sciencedirect.com/science/article/pii/S1544612318304240 · Monday anomaly disappears after detection.
- **Kinateder & Papavassiliou (2021)** — "Calendar effects in bitcoin returns and volatility," *Finance Research Letters* — sciencedirect.com/science/article/pii/S1544612319311316 · no weekend return effect; lower weekend vol; Halloween.
- **Kaiser (2019)** — "Seasonality in cryptocurrencies," *Finance Research Letters* — sciencedirect.com/science/article/pii/S1544612318304513 · TOM/Halloween/month effects.
- **Kumar (2022)** — "Turn-of-the-month effect in cryptocurrencies," *Managerial Finance* 48(5):821 — emerald.com/mf/article-abstract/48/5/821/290148 · TOM positive abnormal return in majors.
- **Qadan, Aharon, Eichel (2022)** — "Seasonal and calendar effects and the price efficiency of cryptocurrencies," *Finance Research Letters* — sciencedirect.com/science/article/pii/S1544612321003597 · **within-month effect is the only calendar effect common to all cryptos**.
- **Vasileiou (2023)** — "Is the turn of the month an anomaly on which an investment strategy could be based? BTC & ETH," *IJBAAF* — inderscienceonline.com/doi/abs/10.1504/IJBAAF.2023.129336 · TOM window varies; strategy viable.
- **Sahu, Ramírez, Kim (2024)** — "Exploring calendar anomalies and volatility dynamics in cryptocurrencies," *JRFM* 17(8):351 — mdpi.com/1911-8074/17/8/351 · DOW unstable across COVID regime.
- **Brauneis, Mestel, Theissen (2025)** — "The crypto world trades at tea time: intraday evidence from centralized exchanges," *Rev. Quant. Finance & Accounting* — link.springer.com/article/10.1007/s11156-024-01304-1 · intraday shape tied to venue geography (UTC).
- **Hansen, Kim, Kimbrough (2024)** — "Periodicity in cryptocurrency volatility and liquidity," *J. Financial Econometrics* 22(1):224 — arxiv.org/pdf/2109.12142 · academic.oup.com/jfec/article-abstract/22/1/224/6759403 · strong intraday+weekly vol periodicity; low vol 5–12 UTC.
- **De Nicola (2021)** — "On the intraday behavior of bitcoin," *Ledger* — ledgerjournal.org/ojs/ledger/article/view/213 · intraday volume seasonality; expects effects to disappear as market matures.
- **Mofakham (2022)** — "Bitcoin Investors' Style, Skill, Sentiment, Seasonal Trading," SSRN 4209663 — papers.ssrn.com/sol3/papers.cfm?abstract_id=4209663 · order imbalance smallest 23–24 UTC, largest 11 UTC.
- **Espel (2024)** — "Impact of US Bitcoin ETF introduction on BTC/ETH intraday regime seasonality," *FTC Proceedings* — link.springer.com/chapter/10.1007/978-3-031-73122-8_3 · post-ETF 20–21 UTC volume surge.
- **Rech, Meng, Musa (2025)** — "Calendar Anomalies in DeFi Assets," *J. Risk & Financial Management* — calendar anomalies largely disappeared in 2020–2023 mature crypto.
- **Repo priors** — `research/agents/09-mexc-maker-fee.md` (0% maker via MX-deduct, spread table); `research/agents/16-tos-envelope.md` (Safe Operating Envelope); `research/agents/18-mexc-premium.md` (decay of post-2018 convergence, ToS hygiene); `signals.py:17-104` (Signal + combine); `agents/macro.py:13-31` (injectable-analyst template); `fleet/memory.py:114-121` (per-source ReflectionMemory weighting).

---

## Bottom line

Crypto calendar effects were **real pre-2020 but mostly decayed** under institutionalisation + ETFs — only **turn-of-month** (cross-coin robust, Qadan 2022; fee-survivable, Kumar 2022) and **intraday volatility/liquidity periodicity** (structural, Hansen 2024) remain honestly tradeable. Ship a weak `CalendarTomAnalyst` (`source="calendar"`, +0.30/0.45 strength/confidence, last-day+first-3-days UTC, maker-only, majors only) plus a `CalendarIntradayFeed` timing-modulator; route both through `ReflectionMemory` so the fleet auto-shrinks them to ~0 if the post-2024 decay has continued. Expected net is **small and low-Sharpe** (~0.5–1.5%/TOM event if the effect survives, ~0 if not) — honest tilting signals, not alpha.

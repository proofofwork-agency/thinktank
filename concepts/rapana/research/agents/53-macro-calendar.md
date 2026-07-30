# 53 — Macro-calendar regime timing: FOMC / CPI / NFP / ETF-flow cycles as a risk-on/off overlay

**Agent:** 53/60 · **Scope:** the **scheduled US macro calendar** (FOMC, CPI, NFP, PCE) plus the **ETF-flow regime** as a *risk-on/off overlay* for the crypto book — i.e. a slow, deterministic *volatility/throttle* layer and a *regime tilt*, **not** a directional news-sniping alpha. Coordinates with **agent 36** (event-driven, owns *unanticipated* events and the ETF-flow regime as an `event` source, `research/agents/36-event-driven.md:34`) and **agent 19** (calendar-anomaly, owns deterministic *clock* effects like turn-of-month, `research/agents/19-calendar-anomaly.md`). This agent owns the **macro-calendar specifically**: the FOMC/CPI/NFP schedule and the Fed-cycle regime it implies.
**Stance:** NON-standard, **spot-only**, **low-frequency (daily/weekly decision cadence — explicitly NOT the 2:00 PM ET release minute)**. This is one of the most ToS-compatible edges in the fleet: acting on a *public, pre-announced* calendar at human pace, on a single venue, is ordinary risk management — the antithesis of the multi-venue / sub-second racing MEXC restricts (`research/agents/16-mexc-tos-envelope.md`).

All repo citations are `file:line`. External claims are URL/DOI-cited inline and consolidated in §8. Effect sizes marked **[HYPOTHESIS → backtest]** where no Deflated-Sharpe-validated estimate exists, mirroring the discipline of `research/agents/30-liquidations.md:46` and `36-event-driven.md:6`.

---

## 1. The core finding — the edge is *volatility timing + regime*, not direction

> **The scheduled US macro calendar does *not* offer a reliable low-frequency *directional* alpha on crypto — the announcement itself is efficiently priced on arrival (agent 36, row #9, `36-event-driven.md:38`). What it *does* offer, robustly and repeatedly, is (a) a *predictable volatility/liquidity regime* you can defend against (de-risk before, avoid the 2:00 PM ET release), and (b) a *slow Fed-cycle + ETF-flow regime* that tilts the whole book risk-on or risk-off over weeks. The single most valuable sentence in this note: cut size ±24h around FOMC/CPI and *never* carry the position through the 18:00 UTC print. That is free money in expected-utility terms, costs nothing in edge, and is invisible to MEXC's monitoring.**

This falls straight out of the cited literature:

- **Volatility around the print is large, predictable, and asymmetric by event type.** Amberdata's 2025 microstructure study (2,166 minutes of Binance BTC/FDUSD L2 across six 2025 FOMC meetings) found the 5-min rolling volatility multiplied **2.1–2.4× on hold decisions** and **7× on the Sep-17-2025 cut**; **market depth within 10bp collapsed 50% on the cut vs 21% on holds**; bid-ask spreads widened 2.4× (https://blog.amberdata.io/five-signals-of-fomc-impact-how-interest-rate-decisions-reshape-crypto-market-microstructure). The disruption persists **~25 minutes** on a cut. A spot maker sitting through that is paying ~7× the normal adverse-selection risk for zero edge.
- **The directional post-print drift is *not* a clean edge.** XWIN Research (2026, reviewed 24 Fed meetings 2022–2024) found **only 17% caused a *lasting* price shift** — three phases: pre-meeting accumulation, announcement vol, post-meeting *repositioning* (i.e. churn, not drift) — https://www.kucoin.com/news/flash/fomc-meetings-trigger-bitcoin-repositioning-not-direction-study-reveals. CoinGecko documents BTC fell **7 of 8 FOMC meetings in 2025** (−6% to −29% over 48h) despite a *cutting* cycle — a "sell-the-news" year — https://www.coingecko.com/learn/fomc-meetings-impact-on-crypto. That is a *one-year regime sample*, not a law; treat it as a hypothesis, not a rule (§3).
- **The pre-FOMC *equities* drift is real but decaying — and in crypto it points the other way.** Lucca & Moench (2015, *J. Finance*) documented the canonical **pre-FOMC announcement drift** in equities — an upward drift in the 24h before the print, present in *both* easing and tightening cycles and uncorrelated with the policy surprise — https://www.jstor.org/stable/43611030 · PDF https://www.emanuelmoench.com/documents/Lucca_Moench(JF2015).pdf. But follow-up work (Boguth et al. 2019; a 2024 extension on ResearchGate) shows the drift has **weakened / disappeared for non-press-conference announcements** post-publication — classic anomaly decay. Cocoma (2025, *JFQA*) gives the theory: investors *stop paying for information* as the announcement nears, raising the risk premium → drift, but it coexists with *low* volume/vol — https://www.jfqa.org/2025/08/12/disagreement-and-scheduled-announcements-explaining-the-pre-announcement-drift/. **In BTC the pre-FOMC pattern is typically a *dump*, not a drift up**: leveraged longs de-risk, funding cools, market makers pull bids → low-single-digit % bleed into the print (ChartSnipe 2026 practitioner synthesis — https://chartsnipe.com/blog/bitcoin-fomc-playbook). That is **de-leveraging, not directional conviction**, and it reverses (sometimes hard) once uncertainty collapses. It is not a tradeable directional alpha for a low-freq spot agent.

§2 quantifies each macro-family; §3 separates the honest durable edges from the directional mirage; §5–6 build `MacroCalendarOverlay` around the durable subset only.

---

## 2. Macro-calendar event-study table — impact, horizon, edge-type, with citations

Conventions: **Horizon** = window over which the effect plays out. **Edge-type** = `VOL-TIMING` (predictable vol/liquidity regime → de-risk value), `REGIME` (slow multi-week risk-on/off tilt), `DIRECTIONAL` (sign-predictable return — flagged weak/none here), `EFFICIENT` (priced on arrival, no residual edge).

| # | Macro event / regime | Typical impact on BTC/ETH | Horizon | Edge-type | Verdict for the fleet | Key citation(s) |
|---|---|---|---|---|---|---|
| 1 | **FOMC rate decision + dot plot + press conference** (8×/yr, 18:00 UTC statement, 18:30 presser) | **Large vol spike, ±directional whipsaw**; vol ×2.1–2.4 holds / ×7 cuts; depth −21%…−50%; first move reversed >50% of time | minutes–25min (vol) / hours (churn) | **VOL-TIMING** | **De-risk ±24h; flat through 18:00–19:15 UTC** — the load-bearing use | Amberdata 2025 (6-meeting L2 study) — https://blog.amberdata.io/five-signals-of-fomc-impact-how-interest-rate-decisions-reshape-crypto-market-microstructure ; ChartSnipe 2026 — https://chartsnipe.com/blog/bitcoin-fomc-playbook |
| 2 | **FOMC *press conference* (18:30–19:15 UTC)** | Often **larger move than the statement**; zigzag as Powell shifts topics | minutes | VOL-TIMING | Sit out; do not form a view until ~19:15 UTC | ChartSnipe 2026 — https://chartsnipe.com/blog/bitcoin-fomc-playbook |
| 3 | **Post-FOMC "sell-the-news" drift** (2025 regime) | BTC fell 7 of 8 meetings in 2025, −6…−29% / 48h, *in a cutting cycle* | 24–48h | DIRECTIONAL (weak/regime) | **[HYPOTHESIS → backtest]** — one year, regime-specific; do NOT code as a rule until validated | CoinGecko 2026 — https://www.coingecko.com/learn/fomc-meetings-impact-on-crypto |
| 4 | **Pre-FOMC drift** (equities up; BTC typically *down* = de-leverage) | Equities: +drift 24h pre (Lucca-Moench), **decaying** post-2019. BTC: low-single-digit % bleed from de-risking | 24h pre | DIRECTIONAL (weak/decayed) | **Not tradeable** as a low-freq spot alpha; informational only (signals the vol is coming) | Lucca & Moench 2015, *JF* — https://www.jstor.org/stable/43611030 · https://www.emanuelmoench.com/documents/Lucca_Moench(JF2015).pdf ; Cocoma 2025, *JFQA* — https://www.jfqa.org/2025/08/12/disagreement-and-scheduled-announcements-explaining-the-pre-announcement-drift/ |
| 5 | **CPI print** (monthly, 12:30 UTC / 13:30 UTC DST) | Hot CPI → risk-off (BTC −1–3% intraday); cool CPI → risk-on (+1–2%); e.g. Feb-2025 cool CPI → BTC +2% | minutes–hours | VOL-TIMING (±24h throttle) ; DIRECTIONAL weak | **De-risk ±24h**; the *sign* depends on surprise vs consensus, not the headline — not reliably predictable ex-ante | AInvest 2025 — https://www.ainvest.com/news/inflation-report-influences-crypto-market-volatility-investor-strategy-2509/ ; BeInCrypto — https://beincrypto.com/bitcoin-us-april-cpi-inflation/ ; FinanceFeeds — https://financefeeds.com/how-cpi-data-impacts-crypto-prices/ |
| 6 | **PCE / PPI prints** (monthly/quarterly) | Same channel as CPI, slightly smaller magnitude; PPI can be highly inflationary (Aug-2025 PPI → BTC −1.7% in 5min) | minutes–hours | VOL-TIMING | Throttle ±24h on the print day | BitcoinConsensus 2025 — https://www.bitcoinsensus.com/news/regulations/highly-inflationary-ppi-print-sparks-crypto-market-volatility |
| 7 | **NFP** (monthly, 12:30/13:30 UTC) | Risk-on/off via rates channel; smaller crypto impact than FOMC/CPI but real | minutes–hours | VOL-TIMING (mild) | Optional mild throttle; lower priority than FOMC/CPI | (FX-equivalent playbook applies; see ChartSnipe NFP guide) |
| 8 | **Fed-cycle regime** (hiking vs cutting vs hold; dot-plot trajectory; QT vs QE) | **Cutting/easing = multi-week tailwind**; hiking/QT = headwind; a single "crypto factor" explains ~80% of crypto variation and its equity-correlation rose with institutionalisation | weeks–months | **REGIME** | Slow (monthly) risk-on/off tilt: dovish trajectory → risk-on multiplier; hawkish → risk-off | IMF WP/23/184 (Iyer, Pereira, Ruzzier) — https://www.imf.org/en/publications/wp/issues/2023/08/04/the-crypto-cycle-and-us-monetary-policy-534834 ; MDPI JRFM 18(7):393 (2025, ARDL bounds) — https://www.mdpi.com/1911-8074/18/7/393 |
| 9 | **ETF-flow regime** (sustained multi-week net inflow/outflow) | **Flows drive spot** — ETFs lead price discovery ~85% of the time; AUM ↔ price cointegrated; flow regime autocorrelated days–weeks | days–weeks | **REGIME (trend)** | Slow bullish/bearish **macro vote on BTC/ETH only** from rolling 5d net-flow sign. **Owned by agent 36 as `source="event"`** — this agent *consumes* it, does not duplicate | Mohamad 2025 — https://doi.org/10.1007/s10614-025-10998-x ; Guliyev & Ahmadova 2025 — https://doi.org/10.5195/ledger.2025.393 ; full cite chain in `research/agents/36-event-driven.md:34,49-53` |

**Reading the table:** rows **#1, #2, #5, #6, #8** are the durable, fleet-actionable edges (vol-timing de-risk + regime tilt). Rows **#3, #4, #7** are weak / regime-specific / directional and should **not** be traded as standalone alphas — `MacroCalendarOverlay` withholds on them. Row **#9 (ETF flows)** is owned by agent 36; this agent references it, it does not re-emit it (§6).

---

## 3. The honest edges, separated from the mirage

### 3a. DURABLE EDGE #1 — volatility-timing / de-risk (the load-bearing one)

This is the highest-confidence, lowest-capacity-cost piece, and it is essentially **free** in expected-utility terms. The mechanism and evidence:

- **The vol spike is deterministic in *timing* if not in *sign*.** FOMC happens 8×/yr at a known 18:00 UTC; CPI/NFP at known 12:30/13:30 UTC. The vol multiplication (2.1–2.4× holds, 7× cuts) and depth collapse (−21%…−50%) are *reproducible across the six 2025 meetings Amberdata measured* — within-event-type consistency is the signal (Amberdata 2025). A spot maker carrying inventory through that window is **paying 2–7× normal adverse-selection cost for zero directional edge** — a pure negative-EV decision.
- **The first move is a head-fake.** ChartSnipe (2026, multi-cycle synthesis): *more than half* of recent FOMCs saw BTC move one way on the 18:00 statement, then fully reverse during the 18:30 press conference. "Trading the 18:00:01 candle has been close to a coin flip" — https://chartsnipe.com/blog/bitcoin-fomc-playbook. A low-frequency spot agent has no edge in that window by construction; the correct action is **flat**.
- **The pre-FOMC "dump" is de-leverage, not signal.** The 24h-pre bleed in BTC is leveraged longs + market-maker inventory reduction (funding cools, OI declines, spreads widen). It tells you *vol is coming*; it does **not** tell you the post-print direction (ChartSnipe §2). It is the warning sign that triggers the throttle, not a directional trade.

**Actionable consequence:** `MacroCalendarOverlay` runs a **deterministic event blackout** — throttle new entries and *reduce size on existing risk* ±24h around FOMC/CPI/PCE (and optionally NFP), and a **hard flat rule 17:45–19:15 UTC on FOMC days / 12:15–13:15 UTC on CPI days**. This needs *no backtest to justify*: it is risk hygiene, like the daily-loss breaker (`rapana/config.py:59`). §5 specifies it.

### 3b. DURABLE EDGE #2 — Fed-cycle + ETF-flow regime tilt (slow, multi-week)

The slow regime signal, evaluated **monthly** (on each FOMC statement / dot plot), not daily. The mechanism:

- **A single "crypto factor" explains ~80% of crypto price variation, and its equity-correlation has risen with institutionalisation** (Iyer, Pereira & Ruzzier 2023, IMF WP/23/184 — https://www.imf.org/en/publications/wp/issues/2023/08/04/the-crypto-cycle-and-us-monetary-policy-534834). That factor is itself **Fed-cycle-sensitive**: it rallied through 2020–21 (QE/zero-rate), sold off through 2022 hiking, and recovered into the 2024–25 cutting/ETF regime. An ARDL bounds study (JRFM 2025) confirms monetary policy transmits to BTC/ETH (not to stablecoins) — https://www.mdpi.com/1911-8074/18/7/393.
- **The transmission channel is the dollar + real yields + liquidity** (CoinGecko 2026: DXY↔BTC inverse correlation tightens to ≈−1 in the 30 min around FOMC; ChartSnipe 2026: BTC is a "3–5× high-beta Nasdaq" on macro days). So the *regime* the overlay reads is: **policy-rate trajectory (dot-plot slope) + balance-sheet direction (QT/QE) + DXY trend**.
- **ETF flows are the proximate, autocorrelated carrier of that regime into spot** (agent 36 owns this; `36-event-driven.md:49-53`): ETFs lead price discovery ~85% of the time (Mohamad 2025), AUM ↔ price cointegrated (Guliyev & Ahmadova 2025), and flow regimes persist **days–weeks** — exactly the horizon a low-freq overlay operates on.

**Actionable consequence:** `MacroCalendarOverlay` emits a **slow (monthly) regime multiplier** on the `macro` source: `risk-on` (dovish trajectory + positive 5d ETF net flow + falling DXY) → mild bullish strength on BTC/ETH; `risk-off` (hawkish/QT + negative flows + rising DXY) → mild bearish + a `de_risk` flag the Risk Manager reads. This **fuses** with agent 57's cross-asset regime (BTC.D/altseason, `57-cross-asset-regime.md`) — both feed the same `macro`-source regime pathway; §6 spells out the non-overlap.

### 3c. MIRAGE — directional post-FOMC drift, "sell-the-news" as a rule, pre-FOMC drift as a trade

Be explicit so no one re-introduces these as alphas:

- **"BTC falls after FOMC" is a 2025 sample, not a law.** 7-of-8 red meetings in one year (CoinGecko) is a regime result driven by "priced-in cuts → profit-taking" in that specific cycle. Coding "short BTC into every FOMC" would be curve-fitting one year. The honest read: the *post-print directional drift is not reliably predictable ex-ante* (XWIN: only 17% of meetings leave a lasting shift). Withhold.
- **Pre-FOMC drift is decayed in equities (Boguth 2019) and opposite-signed/illiquid in BTC.** It is not a tradeable alpha for a spot maker. It is the *trigger signal* for the throttle (§3a), nothing more.
- **The 18:00:01 UTC candle is a coin flip** (ChartSnipe). No low-freq agent has business there. Hard blackout.

---

## 4. ToS analysis — is a macro-calendar overlay legal on MEXC?

**Verdict: trivially yes — it is the *safest* possible overlay because its primary action is *not trading*.** The de-risk throttle reduces order flow, and the regime tilt is a monthly maker order. Measured against MEXC's stated freeze triggers (`research/agents/16-mexc-tos-envelope.md`):

| MEXC freeze trigger | Macro-calendar overlay action | Verdict |
|---|---|---|
| "malicious arbitrage" / multi-leg | One directional maker order on one symbol, or *no order at all* (flat through the print) | **Not arb** |
| "high-frequency" / "disrupt normal market" | Throttle = **fewer** orders; regime tilt = ~1 order/month/symbol; the overlay actively *withdraws* from the 18:00 UTC spike | **Anti-HFT** — reduces the exact fingerprint MEXC flags |
| Cancel-ratio ≤30% | A blackout means orders rest or are never placed; cancels drop | **Cleaner** than baseline |
| Event blackouts ±5min | The overlay enforces a *much wider* ±24h / 75-min hard flat — strictly more conservative than MEXC's own ±5min listing/funding blackout | **Clean** |
| "exploit 0-Fee Fest" | No interaction with promo windows; maker-only (`post_only=True`, per `research/agents/08-mexc-client-edge.md:88`) | **Clean** |

A maker order placed (or *not* placed) because a public calendar says "FOMC in 24h, throttle" is indistinguishable from any disciplined human swing trader's risk management. The overlay is **defensive by design** — its dominant effect is to *lower* the fleet's order rate and cancel ratio on the riskiest days, which is the opposite of the automation-abuse fingerprint.

---

## 5. `MacroCalendarOverlay` — design

### 5.1 Architecture (deterministic; NO LLM; advisory only)
```
macro_calendar.json  (hard-coded FOMC/CPI/NFP/PCE dates for the year, refresh quarterly from federalreserve.gov / BLS)
   ↓
MacroCalendarOverlay.calendar_fn(now_utc) -> {event, phase, hours_to_event, blackout: bool, severity}
   ↓ (A) THROTTLE:  PortfolioManager reads blackout/severity -> cuts new-entry size / blocks fresh entries; Risk Manager enforces hard flat window
   ↓ (B) REGIME:    MacroCalendarOverlay.regime_fn() -> {fed_cycle, etf_flow_5d, dxy_slope} -> regime label (monthly)
   ↓
Signal(symbol, source="macro", direction, strength, confidence, extras={regime, blackout, de_risk})  -> weighted_combine (signals.py:87) -> PortfolioManager (agents/portfolio_manager.py)
```
Two **independent** sub-modules, because their evidence and cadence differ:

- **(A) `CalendarThrottle`** — deterministic, sub-second, reads the calendar only. High confidence, no validation needed (it is risk hygiene). This is the §3a edge.
- **(B) `RegimeTilt`** — monthly, reads Fed-cycle state + ETF flows + DXY. Lower confidence, hypothesis-stage, gated like every other alpha edge (§7). This is the §3b edge.

### 5.2 Calendar specification (deterministic, UTC)
```python
# Event windows (UTC). FOMC statement 18:00 UTC; CPI/NFP/PCE 12:30 or 13:30 UTC.
THROTTLE_WINDOW_H = 24          # ±24h around the print: cut new-entry size to 0.5× and widen stops
HARD_FLAT_WINDOWS = {
    "FOMC":      ("17:45", "19:15"),   # statement 18:00 + presser through 19:15
    "CPI":       ("12:15", "13:15"),
    "PCE":       ("12:15", "13:15"),
    "NFP":       ("12:15", "13:15"),   # optional, lower severity
}
SEVERITY = {"FOMC": 1.0, "CPI": 0.8, "PCE": 0.6, "NFP": 0.5}   # drives the size multiplier
```
The calendar file is **public, pre-announced** data (FOMC: federalreserve.gov/monetarypolicy/fomccalendars.htm; CPI/NFP/PCE: BLS / BEA release calendars). Refresh once per quarter; a static JSON is sufficient — no websocket, no squawk, no key.

### 5.3 Throttle behavior (the high-confidence piece)
| Phase | Action | Why |
|---|---|---|
| `T−24h … T−1h` (throttle) | New-entry size × `0.5`; existing positions: widen stops, no averaging | Pre-FOMC de-leverage is real (§1); carrying full size into the print is −EV |
| `T−1h … T+1.25h` (hard flat, FOMC) | **No new entries; no adds; market-manage only** | 7× vol, −50% depth, coin-flip first move (Amberdata; ChartSnipe) |
| `T+1.25h … T+24h` (throttle) | Resume entries at ×0.5; full size only after a confirmed follow-through day | The 2:00 PM move reverses >50% of the time; wait for 19:15+ interpretation |
| `>T+24h`, no event | Normal sizing | Calendar quiescent |

This is **enforced in deterministic code**, not emitted as a soft signal — `CalendarThrottle` writes a `blackout`/`severity` flag the Risk Manager reads as a hard gate (same pathway as the daily-loss breaker, `rapana/config.py:59`, and the LLM risk veto, `research/agents/43-llm-risk-veto.md`). No LLM, no hindsight.

### 5.4 Regime tilt behavior (monthly, the hypothesis-stage piece)
Evaluated **once per FOMC cycle** (8×/yr) + on each monthly CPI as a confirmation:

| Regime | Trigger (composite, all slow) | BTC/ETH strength | `de_risk` flag |
|---|---|---|---|
| **RISK-ON (dovish)** | dot-plot slope ↓ (cuts priced) **AND** 5d aggregate ETF net-flow > 0 **AND** DXY 30d-slope < 0 | **+0.25** | off |
| **RISK-OFF (hawkish)** | dot-plot slope ↑ / QT active **AND** 5d ETF net-flow < 0 **AND** DXY 30d-slope > 0 | **−0.25** | **on** |
| **TRANSITIONAL** | mixed | **0.0** (neutral) | off |

Inputs are all free / no-key: FOMC statements + dot plot (federalreserve.gov), ETF flows (Farside https://farside.co.uk/bitcoin-etf-flow-all-data/ — *consumed from agent 36's ingester, not re-fetched*), DXY (free FX feed). Monthly cadence matches the information rate — daily evaluation would trade on noise.

---

## 6. Signal spec — mapping to the `Signal` contract (`signals.py:17-46`)

`MacroCalendarOverlay` reuses the existing **`macro`** source Literal (`signals.py:20`) — it is semantically a macro/top-down input, exactly as agent 57's `CrossAssetRegimeAnalyst` chose (`57-cross-asset-regime.md:205`). No new Literal, no schema change. The two sub-modules emit differently:

### 6.1 CalendarThrottle — primarily a *gate*, secondarily a *signal*
The throttle's main effect is the `blackout`/`severity` flag in `extras`, read by the Risk Manager as a **hard size cap** (not a soft combine input). When *not* in a hard-flat window but inside the ±24h throttle, it also emits a mild bearish-leaning `macro` Signal so the combiner reflects the elevated risk:

```python
# Inside the ±24h throttle (NOT the hard-flat window): mild risk-off opinion
Signal(
    symbol="BTC/USDT",                     # repeat per held symbol
    source="macro",
    direction="bearish",
    strength=-0.15 * severity,             # FOMC: -0.15 ; CPI: -0.12 ; milder for NFP
    confidence=0.55,                       # HIGH confidence — vol timing is the durable edge
    rationale=f"macro-calendar throttle: {event} in {hours_to_event:.0f}h (severity {severity})",
    extras={
        "calendar_event": event,           # "FOMC" | "CPI" | "PCE" | "NFP"
        "hours_to_event": hours_to_event,
        "blackout": False,                 # True only in the hard-flat window
        "severity": severity,
        "size_multiplier": 0.5,            # PortfolioManager caps new entries at 0.5×
        "edge_type": "vol_timing",
        "validated": True,                 # vol-timing de-risk needs no DSR gate (it is hygiene)
    },
)

# Inside the hard-flat window: the Risk Manager blocks all new entries/adds;
# the Signal is emitted for audit but strength is irrelevant — blackout overrides.
Signal(
    symbol="BTC/USDT",
    source="macro",
    direction="neutral",
    strength=0.0,
    confidence=0.9,
    rationale=f"HARD FLAT: {event} release window — no new entries/adds",
    extras={"calendar_event": event, "blackout": True, "severity": severity,
            "edge_type": "vol_timing", "validated": True},
)
```

### 6.2 RegimeTilt — a slow *macro* opinion (monthly)
```python
Signal(
    symbol="BTC/USDT",                     # BTC/ETH only; regime is a majors-level signal
    source="macro",
    direction="bullish" if regime == "risk_on" else "bearish" if regime == "risk_off" else "neutral",
    strength=tilt,                         # ±0.25 capped — deliberately weak; only tilts, never dominates
    confidence=0.35,                       # hypothesis-stage until §7 gate passes
    rationale=(f"macro regime={regime} fed_cycle={fed_cycle} "
               f"etf5d={etf_flow_5d:+,.0f}M dxy_slope={dxy_slope:+.3f}"),
    extras={
        "regime": regime,
        "fed_cycle": fed_cycle,            # "cutting" | "on_hold" | "hiking"
        "etf_flow_5d_musd": etf_flow_5d,
        "dxy_slope_30d": dxy_slope,
        "de_risk": regime == "risk_off",   # Risk Manager reads this for the hard trim
        "edge_type": "regime",
        "validated": False,                # flip True only after §7 backtest passes Deflated Sharpe
    },
)
```

**Notes:**
- **Confidence is deliberately split:** `vol_timing` → 0.55 / `validated=True` (the de-risk is durable, free, and hygiene-grade); `regime` → 0.35 / `validated=False` (it is a hypothesis until §7). The combiner (`signals.py:87-104`) confidence-weights both, so the regime tilt can never dominate a validated edge by itself.
- **No new source bucket.** Reusing `macro` (per agent 57's reasoning, `57-cross-asset-regime.md:205`) means `weighted_combine`'s `source_weights["macro"]` already governs the aggregate top-down contribution. If finer-grained control is later wanted, route throttle vs regime through distinct `extras["edge_type"]` and have the combiner split them — no schema change needed now.
- **Coordination with agent 36 (ETF flows) and agent 57 (cross-asset regime):** agent 36 owns the ETF-flow-regime `Signal(source="event")` (`36-event-driven.md:159-168`); agent 57 owns the BTC.D/altseason `Signal(source="macro")` (`57-cross-asset-regime.md:138-203`). This agent owns the **FOMC/CPI/NFP calendar + Fed-cycle** specifically. All three feed the same `macro`/`event` regime pathway; the `extras` payload disambiguates provenance so the Risk Manager sees *which* top-down input fired. Overlap is **intentional redundancy** — three slow signals agreeing is the point (cf. agent 57's "deliberately redundant" design, `57-cross-asset-regime.md:88`).
- **The throttle never routes an order.** It sets a size cap + a blackout flag; the Portfolio/Risk Managers do the rest. This is the same fencing discipline as the LLM event analyst (`36-event-driven.md:172`).

---

## 7. Validation gate + risk caps (mandatory before live *regime* sizing)

**Status today:** the store has `candles`, `funding`, `meta` (`data/store.py`); there is **no macro-calendar table** and no FOMC/CPI label set. The **throttle (§6.1) can ship immediately** — it is deterministic risk hygiene (no edge claim, no DSR gate needed, exactly like the daily-loss breaker at `config.py:59`). The **regime tilt (§6.2) is hypothesis-stage** and must clear the standard gate:

1. **Add a `macro_events` table** in `store.py` (date, event_type, expected, actual, surprise) + ingest FOMC/CPI/NFP/PCE from federalreserve.gov / BLS static calendars (free, no key).
2. **Reuse agent 36's ETF-flow ingest** (Farside, `36-event-driven.md:106`) — do not re-fetch; share the table.
3. **Write `backtest/macro_calendar.py`** mirroring `funding_spike.py`: point-in-time firewall (decide at month-*end* only from data available *before* the FOMC), split tilt from cost, benchmark vs **CASH + vs the un-throttled book**, **PASS = Deflated Sharpe > 0.95 AND best OOS net beats cash** (`rapana/backtest/validation.py:122,249`). Two *separate* gates: (a) does the **throttle** *reduce* max drawdown net of the missed-opportunity cost? (drawdown bar — cf. agent 57, `57-cross-asset-regime.md:129`); (b) does the **regime tilt** *add* raw return? (return bar).
4. Only on pass: flip `validated=True` on the regime Signal and raise its confidence from 0.35 → 0.45 (never above 0.5 pre-out-of-sample).

**Risk caps** (the print-day tails are fat — 7× vol, 50% depth evaporation; cf. `research/agents/30-liquidations.md:172`):

| Cap | Value | Why |
|---|---|---|
| Position size in throttle (±24h) | ×0.5 of normal | Amberdata 7× vol on cuts; half-size halves the tail |
| Hard flat window | 17:45–19:15 UTC FOMC / 12:15–13:15 UTC CPI | The first move reverses >50%; no edge |
| Daily-loss breaker | still `config.py:59` (3%) | Orthogonal; still enforced |
| Regime tilt strength | ±0.25 capped | Must tilt, never dominate (below the 0.15 consensus threshold *alone*, `signals.py:66-70`) |
| Concurrent macro risk-off | if `de_risk` from *both* this agent and agent 57 → raise stables to ≥20% | Two independent regime reads agreeing = de-risk harder (agent 57's `risk_off` tilt, `57-cross-asset-regime.md:95`) |
| No averaging through the print | forbidden | Martingale into a 7×-vol coin-flip is the blow-up scenario |

Until §7's regime gate passes, `RegimeTilt` runs **advisory/paper-only** — the throttle is live from day one, the tilt is a low-confidence opinion the Bull/Bear debate surfaces for a human to act on at the MEXC UI. Same C1/C2 safe track as the funding fade (`research/agents/12-mexc-funding.md:116`) and the event analyst (`36-event-driven.md:196`).

---

## 8. Sources (consolidated, verified)

**FOMC / pre-announcement drift (academic)**
- Lucca, D. & Moench, E. (2015), *The Pre-FOMC Announcement Drift*, **J. Finance** — https://www.jstor.org/stable/43611030 · PDF https://www.emanuelmoench.com/documents/Lucca_Moench(JF2015).pdf · canonical upward pre-FOMC drift in equities, present in easing & tightening, uncorrelated with surprise.
- Boguth, O., Gregoire, V. & Migneron, C. (2019+), follow-up showing the drift **weakened/disappeared for non-press-conference announcements** — https://www.researchgate.net/publication/228316087_The_Pre-FOMC_announcement_drift
- Cocoma, P. (2025), *Disagreement and Scheduled Announcements: Explaining the Pre-Announcement Drift*, **JFQA** — https://www.jfqa.org/2025/08/12/disagreement-and-scheduled-announcements-explaining-the-pre-announcement-drift/ · theory: investors stop learning pre-announcement → risk premium rises, coexisting with low volume/vol.

**FOMC microstructure / crypto reaction**
- Amberdata / Marshall, M. (2025), *Five Signals of FOMC Impact* (2,166 min Binance BTC/FDUSD L2 across six 2025 FOMC meetings) — https://blog.amberdata.io/five-signals-of-fomc-impact-how-interest-rate-decisions-reshape-crypto-market-microstructure · vol ×2.1–2.4 holds / ×7 cut; depth −21% / −50%; spreads ×2.4; disruption persists ~25 min.
- ChartSnipe (2026), *Bitcoin FOMC Playbook* — https://chartsnipe.com/blog/bitcoin-fomc-playbook · dump-then-rip, DXY↔BTC ≈−1, presser > statement, 3:15 PM rule, first move reverses >50%.
- CoinGecko (2026), *How FOMC Meetings Impact Bitcoin and Crypto Prices* — https://www.coingecko.com/learn/fomc-meetings-impact-on-crypto · 2025 sell-the-news (7/8 red, −6…−29%/48h in a cutting cycle); DXY↔BTC; dot-plot reading.
- XWIN Research via KuCoin (2026), *FOMC Meetings Trigger Bitcoin Repositioning, Not Direction* (24 Fed meetings 2022–2024) — https://www.kucoin.com/news/flash/fomc-meetings-trigger-bitcoin-repositioning-not-direction-study-reveals · only 17% caused a lasting shift.

**CPI / PCE / PPI / inflation prints**
- AInvest (2025), *How the U.S. Inflation Report Influences Crypto Market Volatility* — https://www.ainvest.com/news/inflation-report-influences-crypto-market-volatility-investor-strategy-2509/ · Feb-2025 cool CPI → BTC +2%; Aug-2025 2.7% PCE → $300B crypto selloff.
- BeInCrypto (2026), *Hot CPI Print Shakes Fed Cut Bets* — https://beincrypto.com/bitcoin-us-april-cpi-inflation/
- FinanceFeeds, *How CPI Data Impacts Crypto Prices* — https://financefeeds.com/how-cpi-data-impacts-crypto-prices/
- BitcoinConsensus (2025), *Highly Inflationary PPI Print Sparks Crypto Volatility* (Aug-2025 PPI → BTC −1.7% in 5 min) — https://www.bitcoinsensus.com/news/regulations/highly-inflationary-ppi-print-sparks-crypto-market-volatility

**Fed-cycle regime / monetary-policy transmission**
- Iyer, T., Pereira, A. & Ruzzier, C. (2023), *The Crypto Cycle and US Monetary Policy*, **IMF WP/23/184** — https://www.imf.org/en/publications/wp/issues/2023/08/04/the-crypto-cycle-and-us-monetary-policy-534834 · single "crypto factor" explains ~80% of variation; equity-correlation rose with institutionalisation; Fed-cycle-sensitive.
- MDPI **JRFM** 18(7):393 (2025), *Impact of the Fed's Monetary Policy on Cryptocurrencies* (ARDL bounds, 2019–) — https://www.mdpi.com/1911-8074/18/7/393 · policy transmits to BTC/ETH, not stablecoins.

**ETF flows (owned by agent 36 — cited here for coordination)**
- Full cite chain in `research/agents/36-event-driven.md:224-229`: Mohamad 2025 (`10.1007/s10614-025-10998-x`, ETFs lead price discovery ~85%); Guliyev & Ahmadova 2025 (`10.5195/ledger.2025.393`, cointegration); Mazur & Polyzos 2025 (`10.3905/jai.2025.1.239`); Shi, Wang & Ding 2026 (`10.3390/math14111959`, endogeneity of flows to returns/attention).
- Farside BTC-ETF daily flows — https://farside.co.uk/bitcoin-etf-flow-all-data/

**Practitioner / free data feeds**
- Federal Reserve FOMC calendar & statements — https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- CME FedWatch (rate-path probabilities) — https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html
- US BLS release schedule (CPI/NFP/PPI) — https://www.bls.gov/schedule/news_release.htm
- BEA release schedule (PCE) — https://www.bea.gov/news/schedule

**Repo priors (cited)**
- `rapana/signals.py:17-46,87-104` (`Signal`, `combine_signals`, `weighted_combine`; `macro` source Literal at line 20; 0.15 consensus threshold at 66-70)
- `rapana/agents/macro.py:13-31` (`MacroAnalyst` injectable template)
- `rapana/agents/base.py:21-46` (`Analyst` base, `blend`)
- `rapana/config.py:57-60` (position/total-exposure/daily-loss caps)
- `rapana/backtest/validation.py:53,61,122,249` (`ValidationReport`, `deflated_best`, `is_significant = dsr > 0.95`)
- `rapana/backtest/funding_spike.py:370-381` (the gate template the regime backtest mirrors)
- `research/agents/16-mexc-tos-envelope.md` (Safe Operating Envelope)
- `research/agents/19-calendar-anomaly.md` (deterministic *clock* calendar — TOM; orthogonal to this *macro-event* calendar)
- `research/agents/36-event-driven.md:34,38,49-53,159-168` (ETF-flow-regime `event` source; macro-prints-efficient verdict row #9 — this agent's *regime/throttle* complement)
- `research/agents/57-cross-asset-regime.md:88,95,129,138-205` (BTC.D/altseason `macro` regime; the throttle/tilt *fuses* with this)
- `research/agents/43-llm-risk-veto.md` (Risk Manager veto pathway the `de_risk`/`blackout` flags flow through)
- `research/agents/30-liquidations.md:46,172` ([HYPOTHESIS→backtest] discipline; fat-tail risk caps)
- `research/agents/12-mexc-funding.md:116`, `research/agents/08-mexc-client-edge.md:88` (paper-only C1/C2 track; `post_only` maker)

---

## 9. Bottom line

- **The macro calendar's honest, durable edge for a low-freq spot fleet is *volatility-timing de-risk* and *slow Fed-cycle/ETF-flow regime tilt* — NOT directional post-print prediction.** FOMC/CPI vol is large and *predictable in timing* (Amberdata: vol ×2.1–2.4 holds / ×7 cuts, depth −50%; ChartSnipe: first move reverses >50%); a maker sitting through 18:00 UTC pays 2–7× normal adverse selection for zero edge. Cut size ±24h and hard-flat the release window — free expected-utility, ToS-invisible.
- **Directional claims are mirage:** the 2025 "sell-the-news" (7/8 red, CoinGecko) is one regime-year, not a law (XWIN: only 17% of meetings leave a lasting shift); the equities pre-FOMC drift (Lucca-Moench 2015) has decayed (Boguth 2019) and is opposite-signed/illiquid in BTC. Withhold on both.
- **The regime tilt is the second edge:** a single "crypto factor" explains ~80% of variation and is Fed-cycle-sensitive (IMF WP/23/184); ETFs lead price discovery ~85% and the flow regime autocorrelates days–weeks (agent 36). Fuse dot-plot slope + 5d ETF net flow + DXY slope into a monthly `risk_on/off` multiplier — but ship it **hypothesis-stage** (confidence 0.35, `validated=False`), gated by `backtest/macro_calendar.py` (Deflated Sharpe > 0.95).
- **`MacroCalendarOverlay` ships in two pieces: a deterministic `CalendarThrottle` (live from day one — risk hygiene, needs no gate) that caps size ±24h and hard-flats 17:45–19:15 UTC FOMC / 12:15–13:15 UTC CPI; and a monthly `RegimeTilt` (paper-only until §7 passes)** — both reuse `source="macro"`, coordinate with agent 36 (ETF flows) and agent 57 (cross-asset regime) via the shared `macro`/`event` pathway, and never route an order.

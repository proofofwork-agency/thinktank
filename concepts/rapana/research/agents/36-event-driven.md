# 36 — Event-driven / news trading: which crypto events have a *durable* post-event drift?

**Agent:** 36/60 · **Scope:** event-study of the crypto event families that actually move price — exchange hacks/insolvency, DeFi exploits, ETF approvals & flows, regulatory actions, halving, network upgrades, new listings — and an honest verdict on which leave a **durable post-event drift tradable on a hours-to-days horizon** vs which are **efficient-priced on arrival** (no residual edge). Concludes with an `EventAnalyst` design (LLM extracts structured events from *free* news feeds → `Signal` / veto).
**Stance:** NON-standard, **spot-only**, **low-frequency (hours–days, NOT millisecond news-sniping)**. This is one of the *most* ToS-compatible edges in the fleet: reacting to public news at human pace on a single venue is normal trading, not the order-book racing / cross-venue arbitrage MEXC explicitly restricts (`RESEARCH-SYNTHESIS.md:53`, `research/agents/16-mexc-tos-envelope.md`). The LLM is **fenced outside the order path** — it produces an advisory `Signal` only (`RESEARCH-SYNTHESIS.md:65`); deterministic code decides sizing and execution.

All repo citations are `file:line`. External claims are URL + DOI cited inline and consolidated in §8. Where peer-reviewed magnitudes do not exist (much of the *post-event drift* literature is event-specific / practitioner), numbers are flagged **[HYPOTHESIS → backtest]** against the repo's free data — the same discipline as `research/agents/30-liquidations.md:46`.

---

## 1. The core question — durable drift vs efficient immediate pricing

The single most useful finding of this study, and the one that should drive the whole design:

> **Not all events that move price leave a *tradable* post-event drift.** Crypto markets are now fast enough (and ETF-arbitrage tight enough, §3) that **anticipated / scheduled events are priced on arrival** — the edge there is ~zero by the time a low-frequency agent reacts. The durable, low-freq edge concentrates in **a small subset of *unanticipated* events whose information takes hours-to-weeks to be fully digested**: restrictive regulatory actions, major exchange hacks/insolvency, and sustained ETF-flow regimes. Everything else is either a reversal trade (overreaction) or a veto.

This is not a vibe — it falls straight out of the cited literature:
- **Scheduled/anticipated events price on arrival.** Halving is known 4 years in advance; the Jan-11-2024 spot-BTC-ETF *approval* was "buy the rumor, sell the news" (BTC fell on launch day). Makarov & Schoar (2022) show crypto is already one of the *most* efficiently arbitraged micro-markets that exists (`10.1353/eca.2022.0014`).
- **Unanticipated events with multi-period information leave a drift.** Khan, Khurshid & Cifuentes-Faura (2025) use a Bayesian counterfactual to show the **FTX insolvency pushed actual crypto prices consistently below the no-collapse counterfactual for *weeks*** — Solana & Ethereum most hurt — i.e. a *durable* bearish drift, not a one-bar flash (`10.1186/s40854-024-00690-8`). Auer & Claessens (2020, BIS) find regulatory news effects are **persistent and category-dependent**, not instant noise (`10.24149/gwp381`).

§2 quantifies each family; §5 gives the durable-vs-efficient verdict table; §6–7 build `EventAnalyst` around the durable subset only.

---

## 2. Event-study table — impact, horizon, drift/reversal, with citations

Conventions: **Horizon** = over what window the post-event move plays out (the tradable window for a low-freq agent). **Verdict** = `DURABLE DRIFT` (residual edge after T+0), `EFFICIENT` (≈priced on arrival), or `REVERSAL` (overreacts then mean-reverts). Magnitudes marked **[HYPOTHESIS → backtest]** where not Deflated-Sharpe-validated.

| # | Event family | Typical impact (direction) | Horizon of move | Verdict | Key citation(s) |
|---|---|---|---|---|---|
| 1 | **Restrictive regulatory action** (general ban, securities-law reclassification, AML/CFT clamp, restricting bank–crypto interoperability) | **Large NEGATIVE**, ranked by Auer & Claessens: general bans / securities-law > AML/CFT > interoperability restrictions | **days–weeks** | **DURABLE DRIFT (bearish)** | Auer & Claessens (2020), BIS QMR Sept / WP — https://doi.org/10.24149/gwp381 ; Chokor & Alfieri (2021), QREF — https://doi.org/10.1016/j.qref.2021.05.005 |
| 2 | **Favorable legal framework** (bespoke crypto/ICO regime, official recognition, ETF approval-*process* milestones before launch) | **Strong POSITIVE** (Auer & Claessens: "establishment of specific legal frameworks … coincides with strong market gains") | **days–weeks** | **DURABLE DRIFT (bullish)** | Auer & Claessens (2020) — https://doi.org/10.24149/gwp381 |
| 3 | **Major exchange hack / insolvency (SYSTEMIC venue)** — e.g. Mt. Gox, Bitfinex, FTX, Bybit ($1.4B, 2025) | **Negative, broad risk-off**; the *uncertainty* re-erupts: Grobys documents a **second volatility wave at t+5 days**, with **spillover to Ethereum on a ~5-day lag** | **days–weeks** | **DURABLE DRIFT (bearish) → de-risk trigger** | Grobys (2021), *Quantitative Finance* — https://doi.org/10.1080/14697688.2020.1849779 ; Khan, Khurshid & Cifuentes-Faura (2025), *Financial Innovation* — https://doi.org/10.1186/s40854-024-00690-8 ; Krause (2025), IJCCR — https://doi.org/10.51483/ijccr.5.1.2025.52-62 |
| 4 | **Idiosyncratic DeFi/protocol exploit** (single token, e.g. bridge/flash-loan; hacked asset ≠ venue) | **Sharp NEGATIVE on the token** (~10–50% dump on the specific asset, **[HYPOTHESIS]**); often **partially recovers within 1–7d if fundamentals intact** | **1–7 days** | **REVERSAL (buy-the-dip on the token)** — *only if idiosyncratic*; if it cascades to systemic it becomes #3 | Grobys (2021) — https://doi.org/10.1080/14697688.2020.1849779 ; Akyıldırım, Conlon, Corbet & Hou (2024), *JIMF* "HACKED": equities analog = **−0.24% next day, reverses ~2 weeks** — https://doi.org/10.1016/j.intfin.2024.102082 ; Rekt leaderboard — https://rekt.news/leaderboard/ |
| 5 | **Spot-BTC/ETH ETF *flow regime*** (sustained multi-week net inflow/outflow, post Jan-11-2024 launch) | **Flows drive spot** (price formation): ETFs dominate price discovery **~85% of the time** vs spot; ETF AUM & BTC price are **cointegrated (long-run equilibrium)** | **days–weeks** (flow regime persistence) | **DURABLE DRIFT (direction = sign of net flows)** | Mohamad (2025), *Computational Economics* — https://doi.org/10.1007/s10614-025-10998-x ; Guliyev & Ahmadova (2025), *Ledger* — https://doi.org/10.5195/ledger.2025.393 ; Mazur & Polyzos (2025), *J. Alternative Investments* — https://doi.org/10.3905/jai.2025.1.239 ; Lim (2026), SSRN — https://doi.org/10.2139/ssrn.6592830 |
| 6 | **ETF *approval announcement* itself** (e.g. SEC spot-BTC approval, 11 Jan 2024) | **Sell-the-news**: BTC fell on/after launch day despite the bullish structural news | **hours** | **EFFICIENT** (anticipated, pre-priced; the durable part is the *flow regime* in #5, not the approval pop) | Mohamad (2025) — https://doi.org/10.1007/s10614-025-10998-x |
| 7 | **Halving** (BTC supply cut; scheduled, known 4y ahead) | Anticipation run-up is real (**[HYPOTHESIS]**); post-halving *drift* is weak & contested — supply shock is small vs flows/macros | **weeks (pre-)** / **weak (post-)** | **EFFICIENT** (pre-priced; the cycle is better modeled as a regime/calendar — `research/agents/19-calendar-anomaly.md`) | Meynkhard (2019), *IMFI* — https://doi.org/10.21511/imfi.16(4).2019.07 ; Singla et al. (2023) — https://doi.org/10.36676/sjmbt.v1i1.06 ; Jiménez et al. (2024), *IREF* — https://doi.org/10.1016/j.iref.2024.02.022 |
| 8 | **New exchange listing** (token added to a major venue) | **Positive pop** on the listing; **partially fades** | **hours–1 day** | **EFFICIENT / reversal — AND a ToS-sensitive *speed* game** (this is MEXC-specific, owned by `research/agents/10-mexc-listings.md` & `research/agents/15-mexc-listing-detection.md`; NOT chased as news) | Kim & Kwon (2019) — https://doi.org/10.52558/ism.2019.08.20.2.1 |
| 9 | **Macro announcements** (FOMC, CPI, NFP, PPI) | Crypto now carries a positive equity-β; risk-on/risk-off in minutes | **minutes–hours** | **EFFICIENT** (durable drift weak; cadence/seasonality owned by `research/agents/20-utc-flows.md` & `research/agents/19-calendar-anomaly.md`) | Katsiampa, Corbet & Lucey (2019), *JIMF* high-freq co-movements — https://doi.org/10.1016/j.intfin.2019.05.003 |
| 10 | **Network upgrade / fork** (protocol-level, e.g. ETH Dencun, major mainnet) | Mixed; small avg effect, high idiosyncratic variance | **hours–days** | **idiosyncratic → classify case-by-case** | (no single canonical study; treat as #4 if it fails, #8 if it's a hype listing) |

**Reading the table:** the only rows with a *residual, low-freq, post-event* edge are **#1, #2, #3, #5** (durable drift) and **#4** (reversal, conditional). Rows **#6–#9 are efficient-priced** — an `EventAnalyst` should **withhold/veto** on them, not trade them. This is the honesty section the prompt asked for.

---

## 3. ETF flows — do flows predict next-day returns? (the load-bearing sub-question)

**Short answer: not cleanly as *next-day* return — but yes as a *persistent regime*.** The literature distinguishes three claims:

1. **ETFs now dominate price discovery** (Mohamad 2025, 5-min data, IBIT/FBTC/GBTC lead spot ~85% of the time → https://doi.org/10.1007/s10614-025-10998-x). So *whatever moves ETF demand moves BTC* — the channel is real.
2. **Flows and price are cointegrated / long-run equilibrium** (Guliyev & Ahmadova 2025, FMOLS/DOLS/CCR on daily data 11 Jan 2024–16 May 2025 → "strong positive long-run association … ETF-driven demand exerts a lasting influence" → https://doi.org/10.5195/ledger.2025.393). The relationship is **persistent**, not a one-day pop.
3. **But flows are endogenous** — daily inflows are themselves driven by recent returns + retail attention/sentiment (Shi, Wang & Ding 2026, Reddit sentiment → ETF inflows; Mazur & Polyzos 2025 on price formation → https://doi.org/10.3905/jai.2025.1.239 ; https://doi.org/10.3390/math14111959). So a naïve "yesterday's inflow → buy today" rule is partly buying **momentum/attention** that is already partially priced.

**Honest magnitude [HYPOTHESIS → backtest]:** practitioner trackers (Farside, SoSoValue, CoinShares) document that sustained ~$0.5–1B/day net-inflow weeks coincide with notable same-week BTC strength, and sustained outflow weeks with weakness — but **the contemporaneous correlation overstates the *predictive* (next-day) edge** because of the endogeneity in (3). The tradable structure is the **autocorrelation of the flow regime**: once inflows (or outflows) establish, they persist for **days–weeks**, producing a *trend drift* that survives at low frequency — exactly the hours-days horizon, not seconds.

**Practical consequence for the fleet:** use ETF **net-flow regime** (e.g., rolling 5-day sign × magnitude of aggregate spot-BTC-ETF flow, free via Farside https://farside.co.uk/bitcoin-etf-flow-all-data/ or SoSoValue https://sosovalue.com/assets/etf/us-btc-spot) as one **bullish/bearish macro vote on BTC/ETH only**, **not** as a high-frequency trigger. Treat the "flow → next-day return" coefficient as a hypothesis to backtest on the repo's free data (§7), defaulting to low confidence until validated — same posture as the funding fade pre-validation (`12-mexc-funding.md`).

---

## 4. The exploit/hack contagion pattern — tradable as a de-risk trigger?

**Yes — this is the single most durable post-event drift category, and the cleanest one to act on.** The mechanism and evidence:

- **Systemic venue hacks/insolvency are broad risk-off, not idiosyncratic.** Khan et al. (2025) show the FTX collapse kept actual crypto prices *below the counterfactual for weeks* — Solana & Ethereum most affected (`10.1186/s40854-024-00690-8`). Grobys (2021) finds Bitcoin hacking incidents produce a **contemporaneous volatility jump at t=0 AND a second significant wave at t+5 days**, and **spill into Ethereum's uncertainty with a ~5-day lag** (`10.1080/14697688.2020.1849779`). High-frequency connectedness between majors is large and rises in stress (Katsiampa, Corbet & Lucey 2019 → `10.1016/j.intfin.2019.05.003`). Crypto exchanges that fail share observable ex-ante risk factors (Sapkota 2024 → `10.1016/j.intfin.2024.102093`).
- **That 5-day lag is the low-freq edge.** A major hack is *not* instantaneously arbitraged across the whole universe — the uncertainty propagates over days (Grobys's t+5 wave; the ETH +5d spillover). A spot-only agent that **de-risks broad exposure within hours of a confirmed systemic hack/insolvency** is acting on a *multi-day* drift, not racing the first tick. This is squarely human-paced and ToS-safe.
- **The mirror trade — buy the dip — works only for *idiosyncratic* exploits (row #4).** If a bridge/protocol exploit is contained to one token and its revenue/utility survives, the token's dump frequently reverts partially within days (analogous to the post-liquidation mean-reversion already studied in `research/agents/30-liquidations.md:14-23`, but *event-triggered* rather than funding-triggered). The equities cyberattack literature finds exactly this shape: **−0.24% next day, then reversal within ~2 weeks** (Akyıldırım et al. 2024 → `10.1016/j.intfin.2024.102082`). **But** if the hack cascades (counterparty risk → withdrawals → insolvency, as FTX→Alameda) it flips into systemic (#3) and the dip is a falling knife — so the **scope classifier (idiosyncratic vs systemic) is the load-bearing decision** (§6).

**Verdict:** the contagion pattern is **tradable as a de-risk trigger** on a hours–days horizon for systemic events, and as a **selective buy-the-dip** for idiosyncratic ones. Both are spot-only, low-freq, ToS-compatible.

---

## 5. Durable-vs-efficient verdict (the decision table EventAnalyst codes against)

| Event family | Durable drift? | EventAnalyst action | Default strength/confidence |
|---|---|---|---|
| Restrictive regulation (#1) | **Yes — bearish** | Emit **bearish** `Signal` on affected symbols (esp. the jurisdiction's exposure); *veto* new longs | strength 0.4–0.6 / conf 0.4 |
| Favorable legal framework (#2) | **Yes — bullish** | Emit **bullish** `Signal` (broad BTC/ETH bias) | strength 0.3–0.5 / conf 0.35 |
| Systemic exchange hack/insolvency (#3) | **Yes — bearish, broad** | **De-risk**: bearish on majors; **hard veto** on opening new longs for N days; raise cash | strength 0.5–0.7 / conf 0.45 |
| Sustained ETF-flow regime (#5) | **Yes — trend (sign of flows)** | Emit bullish/bearish **macro** vote on BTC/ETH from rolling net-flow sign | strength 0.2–0.4 / conf 0.3 |
| Idiosyncratic protocol exploit (#4) | **Reversal (token dip)** | Emit **bullish** on the *single token* once scope confirmed idiosyncratic & fundamentals intact; tight stop | strength 0.3–0.5 / conf 0.35 **[HYPOTHESIS]** |
| ETF approval announcement (#6), halving (#7), listing (#8), macro prints (#9), routine upgrades (#10) | **No (efficient/idiosyncratic)** | **WITHHOLD** (neutral) — do not trade the announcement; optionally *veto* if pre-existing position rationale is invalidated | neutral, strength 0 / conf 0 |

The cardinal rule: **EventAnalyst earns its keep by *not* trading the efficient rows.** A news-trader's classic failure is chasing every headline; the durable edge is in the ~4 families above.

---

## 6. `EventAnalyst` — design (LLM extracts structured events → Signal / veto)

### 6.1 Architecture (advisory only; LLM fenced outside order path per `RESEARCH-SYNTHESIS.md:65`)
```
free news feeds (RSS / free-tier APIs)  →  news_ingest  →  events table (new, store.py)
   ↓                                                                                ↑
batch of recent items  →  LLM provider (fleet provider, like agents/market.py)  →  structured JSON events
   ↓
deterministic classifier  (taxonomy §2/§5 + scope = systemic vs idiosyncratic)  →  calibrated Signal(s) / veto
   ↓
Signal(source="event")  →  weighted_combine (signals.py:87)  →  PortfolioManager (agents/portfolio_manager.py:42-55)
```
The LLM does **NLP extraction only** (free text → `{category, assets, scope, severity, ts, source_url, summary}`); a **deterministic** mapping (§5 table) converts each classified event to a `Signal` strength/confidence/direction. This mirrors the repo's deliberate pattern: deterministic core, LLM as a fenced opinion source (`agents/market.py:14-22`), never on the order path.

### 6.2 Free, no-key (or free-tier) news sources — all verified public, ToS-safe to *read*
| Source | What it covers | Cost | Use |
|---|---|---|---|
| **CryptoCompare News API** (min-api.cryptocompare.com, `category=3`) | Categorized crypto news stream, incl. historical | free tier (key, generous) | **Primary news stream** + event backtesting |
| **RSS: CoinDesk / The Block / Decrypt / Reuters-crypto** | Broad news, fast enough at hours-cadence | free | Primary news stream |
| **Rekt.news leaderboard** (rekt.news/leaderboard) | DeFi exploit catalog w/ $ lost, timestamps | free | **Exploit/hack detection** (rows #3/#4) |
| **Farside BTC ETF flow** (farside.co.uk/bitcoin-etf-flow-all-data) | Daily per-issuer spot-BTC-ETF net flow | free | ETF-flow regime vote (#5) |
| **SoSoValue / CoinShares weekly flows** | Aggregate BTC/ETH ETF flows | free | ETF-flow regime vote (#5) |
| **SEC / BIS / ESMA RSS** | Official regulatory announcements | free | Regulatory events (#1/#2) |
| **Official project governance blogs / forums (RSS)** | Upgrades, forks, treasury actions | free | Network events (#10) |
| **Chainalysis annual Crypto Crime report** | Hack/exploit aggregate stats | free | Calibration/backtest labels |

**Explicitly excluded:** paywalled squawk/wire (Bloomberg/WSJ), and any sub-second / websocket race — those are both ToS-risky and outside the low-freq thesis. On-chain sleuth accounts (Lookonchain/PeckShield) are useful color but scraping X is fragile — prefer their blog/RSS where available; treat as confirmation, not primary trigger.

### 6.3 The scope classifier — the load-bearing decision
For exploit/hack events the **first** job is: **systemic vs idiosyncratic?** Pseudo-rule (deterministic, pre-committed, no hindsight):
- **Systemic** (= de-risk, #3) if *any* of: hacked entity is a **custodial exchange / lender / stablecoin issuer / major L1 bridge**; loss **≥ ~$250M** **[HYPOTHESIS]**; signs of **withdrawal halt / insolvency / contagion** (counterparty freezing).
- **Idiosyncratic** (= buy-the-dip candidate, #4) if: exploit confined to a **single isolated protocol/token**, custody intact, no withdrawal halt, and the token's **fee/revenue/TVL not structurally impaired**.

This single split routes the same news item to opposite trades — getting it right is the edge; getting it wrong is the falling knife (§7).

---

## 7. Signal spec — mapping to the `Signal` contract (`signals.py:17-46`)

`EventAnalyst` emits under a **new source bucket `"event"`** (alongside market/sentiment/macro/arbitrage/yield at `signals.py:20`). `weighted_combine` defaults unknown sources to weight 1.0 (`signals.py:87-104`), so set `source_weights["event"] ≈ 0.3` until validated — exactly the down-weighting discipline of `research/agents/14-mexc-orderbook.md:97`. Zero-friction fallback if a schema change is unwanted: `source="macro"` (no new bucket, loses provenance).

```python
# Example A — systemic exchange hack (row #3): DE-RISK
Signal(
    symbol="BTC/USDT",                   # majors first; repeat for ETH, and affected alts
    source="event",
    direction="bearish",
    strength=0.6,                        # systemic → strong-ish, clipped, never >0.7 pre-validation
    confidence=0.45,                     # deliberate: hypothesis-stage until §8 backtest passes
    rationale="systemic exchange hack/insolvency: broad risk-off; Grobys t+5 vol wave",
    extras={
        "event_category": "exchange_hack", "scope": "systemic", "severity": 0.8,
        "loss_usd": float(loss), "source_url": url, "event_ts": int(ts),
        "horizon_h": 24 * 7, "action": "de_risk",
        "validated": False,              # flip True only after §8 backtest passes Deflated Sharpe
    },
)

# Example B — idiosyncratic protocol exploit on token X (row #4): BUY-THE-DIP, tight stop
Signal(
    symbol="XYZ/USDT",
    source="event",
    direction="bullish",
    strength=0.4,
    confidence=0.35,
    rationale="idiosyncratic bridge exploit; token dump, fundamentals (TVL/rev) intact; reversal",
    extras={
        "event_category": "defi_exploit", "scope": "idiosyncratic", "severity": 0.5,
        "source_url": url, "event_ts": int(ts), "entry_delay_h": 4, "horizon_h": 72,
        "stop_ref": "exploit_low", "validated": False,
    },
)

# Example C — sustained ETF inflow regime (row #5): macro vote, BTC/ETH only
Signal(
    symbol="BTC/USDT",
    source="event",
    direction="bullish" if rolling5d_netflow >= 0 else "bearish",
    strength=clamp(abs(rolling5d_netflow) / scale, 0.2, 0.4),
    confidence=0.30,
    rationale=f"spot-BTC-ETF 5d net flow regime = {rolling5d_netflow:+,.0f}M (Farside)",
    extras={"event_category": "etf_flow_regime", "validated": False},
)
```
**Notes:**
- **`confidence` 0.30–0.45 and `validated=False` are load-bearing** — until `backtest/event_drift.py` passes the same Deflated-Sharpe gate as `funding_spike.py:370`, the combiner must treat these as *weak, low-weight opinions*, never a primary driver. `Signal.__post_init__` (`signals.py:27-41`) enforces sign/clip invariants for free.
- **EventAnalyst never routes an order.** The `PortfolioManager` converts a net bearish consensus (where the event vote may be the swing factor) into a flatten/size-down; the executor still enforces the risk caps. For **hard vetoes** (systemic hack → no new longs for N days), emit a `neutral`/`bearish` signal *and* set an `event_veto_until` flag consumed by the risk gate (`research/agents/03-risk-edge.md`) — veto authority lives in deterministic code, not the LLM.

---

## 8. Validation gate + risk caps (mandatory before any live sizing)

**Status today:** the store has `candles`, `funding`, `meta` only (`data/store.py:14,29,39`); there is **no `events` table** and no news ingestion. So — like `research/agents/30-liquidations.md:160` and `14-mexc-orderbook.md:79` — the edge is **un-backtestable as-is**. Sequence:
1. **Add news ingestion** → new `events` table in `store.py` + a `news` ingester polling CryptoCompare/RSS at hourly cadence (no websocket, no key-cost).
2. **Build an event-study label set** from CryptoCompare historical news + Rekt leaderboard + Farside flows (free), labeling each event by family & scope.
3. **Write `backtest/event_drift.py`** mirroring `funding_spike.py`: point-in-time firewall (decide only from items *published* before `t`), split drift from cost, benchmark vs **CASH**, **PASS = Deflated Sharpe > 0.95 AND best OOS net beats cash** (`funding_spike.py:370`). **Per-family gates** (don't let a strong #3 result justify enabling weak #7/#8 rows).
4. Only on pass: flip `validated=True` and raise `source_weights["event"]` family-by-family.

**Risk caps** (falling-knife honesty — exploits/hacks cascade; cf. `30-liquidations.md:172`):

| Cap | Value | Why |
|---|---|---|
| Risk/trade | ≤1% equity (`03-risk-edge.md:19`) | exploit/hack tails are fat |
| Position size | ≤2–3% until validated | conviction-tiered, never full size on a hypothesis |
| Stop (buy-the-dip, #4) | just below exploit low | new low falsifies "fundamentals intact" |
| Time stop | exit by 3–7d (#4) / 2–4w (#1–3) if thesis not playing | failed drift = mis-classified scope |
| Concurrent event trades | max 1 systemic + max 2 idiosyncratic, uncorrelated | contagion hits everything at once |
| Hard veto | systemic hack (#3) → **no new longs N=2–5 days**; daily-loss breaker (`03-risk-edge.md:19`) tripped → skip | the best action is often de-risking |
| No averaging down | forbidden | a hack that cascades is the martingale blow-up scenario |

Until §8 passes, `EventAnalyst` runs **advisory/paper-only** — it emits Signals that surface in the Bull/Bear debate as an *opinion* for a human to act on at the MEXC UI, with zero freeze risk — the same safe C1/C2 track as the funding fade (`12-mexc-funding.md:116`).

---

## 9. Bottom line

- **The honest verdict: only ~4 of ~10 event families leave a durable post-event drift** tradable at hours–days — restrictive regulation (Auer & Claessens 2020, `10.24149/gwp381`), systemic exchange hacks/insolvency (Khan et al. 2025 FTX counterfactual, `10.1186/s40854-024-00690-8`; Grobys 2021 t+5 vol wave + ETH +5d spillover, `10.1080/14697688.2020.1849779`), favorable legal-framework news, and the sustained ETF-flow regime (Mohamad 2025 ETFs lead price discovery ~85%, `10.1007/s10614-025-10998-x`; Guliyev & Ahmadova 2025 cointegration, `10.5195/ledger.2025.393`). Halving, the ETF *approval* itself, listings, and macro prints are **efficient on arrival** — EventAnalyst withholds/vetoes them.
- **The hack/exploit contagion is genuinely tradable as a de-risk trigger** at low frequency: systemic venue failures produce a **multi-day-to-multi-week broad risk-off** (not a flash), with a documented **~5-day lagged spillover** into ETH — so a spot-only agent de-risking within hours of a *confirmed systemic* event is acting on a durable drift, human-paced and ToS-safe. The mirror buy-the-dip works **only** for *idiosyncratic* token exploits with intact fundamentals (reversal analog of `research/agents/30-liquidations.md`); the **systemic-vs-idiosyncratic scope classifier is the load-bearing decision**.
- **ETF flows do *not* cleanly predict next-day returns** (they are endogenous to prior returns/attention — Shi et al. 2026, `10.3390/math14111959`), **but** the *flow regime is autocorrelated for days–weeks* and cointegrated with price — so the tradable structure is a **persistent trend vote on BTC/ETH** from a 5-day net-flow sign, not a high-frequency trigger.
- **`EventAnalyst` design: LLM extracts structured events from free feeds (CryptoCompare/RSS/Rekt/Farside) → deterministic §5 mapping → `Signal(source="event", confidence≤0.45, validated=False)` / veto, fenced outside the order path.** Mandatory sequence: add news ingest → `backtest/event_drift.py` (Deflated-Sharpe gate, per-family) → only then raise the weight. Until then, paper-only, human-executes on the UI — same safe track as every other hypothesis-stage edge in the fleet.

---

## Sources (consolidated)

**Regulatory / event-study core**
- Auer, R. & Claessens, S. (2020), *Cryptocurrency market reactions to regulatory news*, BIS QMR Sept 2020 / WP — https://doi.org/10.24149/gwp381
- Chokor, A. & Alfieri, É. (2021), *Long and short-term impacts of regulation in the cryptocurrency market*, QREF — https://doi.org/10.1016/j.qref.2021.05.005
- Makarov, I. & Schoar, A. (2022), *Cryptocurrencies and Decentralized Finance*, BPEA — https://doi.org/10.1353/eca.2022.0014

**Hacks / insolvency / contagion**
- Grobys, K. (2021), *When the blockchain does not block: on hackings and uncertainty*, Quantitative Finance — https://doi.org/10.1080/14697688.2020.1849779
- Khan, K., Khurshid, A. & Cifuentes-Faura, J. (2025), *Causal estimation of FTX collapse on cryptocurrency*, Financial Innovation — https://doi.org/10.1186/s40854-024-00690-8
- Akyıldırım, E., Conlon, T., Corbet, S. & Hou, Y. (2024), *HACKED: stock market response to cyberattacks* (equities analog), JIMF — https://doi.org/10.1016/j.intfin.2024.102082
- Sapkota, N. (2024), *Decoding cryptocurrency exchange defaults*, JIMF — https://doi.org/10.1016/j.intfin.2024.102093
- Krause, D. (2025), *The $1.4 Billion Bybit Hack*, IJCCR — https://doi.org/10.51483/ijccr.5.1.2025.52-62
- Katsiampa, P., Corbet, S. & Lucey, B. (2019), *High-frequency volatility co-movements in cryptocurrency markets*, JIMF — https://doi.org/10.1016/j.intfin.2019.05.003

**ETF flows / price discovery**
- Mohamad, A. (2025), *Do Bitcoin ETFs Lead Price Discovery?*, Computational Economics — https://doi.org/10.1007/s10614-025-10998-x
- Guliyev, T. & Ahmadova, A. (2025), *From Flows to Value: Cointegration Between Bitcoin Spot ETF Assets and Bitcoin Price*, Ledger — https://doi.org/10.5195/ledger.2025.393
- Mazur, M. & Polyzos, E. (2025), *Spot Bitcoin ETFs: The Effect of Fund Flows on Bitcoin Price Formation*, J. Alternative Investments — https://doi.org/10.3905/jai.2025.1.239
- Lim, B. C. (2026), *The Price Impact of Spot Bitcoin ETF Flows*, SSRN — https://doi.org/10.2139/ssrn.6592830
- Shi, J., Wang, Z. & Ding, D. (2026), *Who Gets the Flows? AI Brand Visibility, Sentiment & ETF Capital Allocation*, Mathematics — https://doi.org/10.3390/math14111959

**Halving / listings**
- Meynkhard, A. (2019), *Fair market value of bitcoin: halving effect*, IMFI — https://doi.org/10.21511/imfi.16(4).2019.07
- Singla, A. et al. (2023), *Unpacking the Impact of Bitcoin Halving*, SJMBT — https://doi.org/10.36676/sjmbt.v1i1.06
- Jiménez, I., Mora-Valencia, A. & Perote, J. (2024), *Bitcoin halving & higher-order moment spillovers*, IREF — https://doi.org/10.1016/j.iref.2024.02.022
- Kim, J. & Kwon, Y. (2019), *Determinants of cryptocurrency price: … New listing*, ISM — https://doi.org/10.52558/ism.2019.08.20.2.1

**Practitioner / free data feeds**
- Farside BTC-ETF daily flows — https://farside.co.uk/bitcoin-etf-flow-all-data/
- SoSoValue spot-BTC-ETF flows — https://sosovalue.com/assets/etf/us-btc-spot
- CoinShares weekly digital-asset fund flows — https://coinshares.com/research/weekly-digital-asset-fund-flows
- Rekt.news exploit leaderboard — https://rekt.news/leaderboard/
- CryptoCompare News API (free tier) — https://min-api.cryptocompare.com/documentation
- Chainalysis Crypto Crime reports — https://www.chainalysis.com/reports/

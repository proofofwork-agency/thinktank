# 20 — Fixed-time institutional flow anomalies (00:00 UTC reset, 8h funding, ETF NAV, index rebalance)

**Agent:** 20/60 · **Scope:** documented, *fixed-clock* spikes in crypto volume / volatility / illiquidity driven by institutional conventions (perp funding settle, CME/BTC-ETF open & NAV, index rebalance) — and a ToS-safe way for rapana to **avoid or fade** them at low frequency. Spot-only, single-leg MEXC, maker-preferred.
**Stance:** NON-standard. This is a *time-of-day risk overlay* plus an optional *post-settlement overshoot fade* — explicitly not HFT, not settlement-racing, not cross-venue. Many of the alpha-capture variants of these effects decay quickly; the **risk-avoidance** variant is durable.

All repo citations are `file:line`. External claims are URL-cited in §6. Where peer-reviewed bp magnitudes don't exist for MEXC spot specifically, claims are flagged **[HYPOTHESIS → backtest]** against the repo's own OHLCV/funding store.

---

## 1. The single most important finding: the pattern is REAL, GLOBAL, and GROWING

The crypto "intraday seasonality" literature has converged on a remarkably robust and counter-intuitive result:

> **Volume, volatility, and illiquidity do *not* peak at 00:00 UTC. They peak at 16:00–17:00 UTC ("London tea time" = the US+Europe equity-overlap window), and trough around 04:00–05:00 UTC. The 00:00 UTC hour has a *secondary* spike driven by the perp funding settlement + the daily reset, not the primary peak.**

Three independent, peer-reviewed, large-sample studies agree on this:

| Study | Sample | Peak (UTC) | Trough (UTC) | Mechanism named |
|---|---|---|---|---|
| **Brauneis, Mestel & Theissen (2025)**, *Rev Quant Fin & Acc* 64:275–304 | 1940 pairs × 38 exchanges × 5 continents, 2018–2022, hourly | vol/volume/spread all peak **16:00–17:00**; returns peak **15:00–16:00**; 1st hour also elevated | vol/volume **≈03:00–06:00** | US+EU equity overlap; Admati-Pfleiderer liquidity pooling |
| **Hansen, Kim & Kimbrough (2024)**, *J Fin Econometrics* 22:224–251 (arXiv:2109.12142) | BTC+ETH, Coinbase/Binance/Uniswap, hourly+intra-hour | "**hour after 16:00 UTC** tends to have the highest level of volatility" | "**bottom near 05:00 UTC**" | **"can be related to algorithmic trading and funding times in futures markets"** |
| **Forino & Morelli (2026)**, *Annals of Operations Research* | multi-venue liquidity/vol | peaks at **midnight, 14:00, and 16:00 UTC** | — | funding settle (00:00) + US/EU overlap (14–16) |

Two load-bearing implications for rapana:

1. **The pattern is global, not local.** Brauneis et al. show the UTC shape is *nearly identical* on exchanges in the Americas, Asia and Europe, and the within-pair dummy-correlation of the intraday shape is high across continents. So it is *not* "Asian traders at night" — it is a *clock-anchored, institutional-convention-driven* effect. That is exactly the kind of edge that survives (it is paid for by structural flow, not by a slow counterparty you can arb away).
2. **The pattern has GROWN STRONGER over time, not decayed.** Hansen et al. (2024) explicitly state the periodicity "has grown stronger over the years and can be related to algorithmic trading and funding times." This is the opposite of the usual "anomaly decays once published" story — the institutionalization of crypto (CME, ETFs, perp dominance) is *intensifying* the clock-anchored flow. See §5 for the honest decay caveats per sub-effect.

URLs: Brauneis et al. https://link.springer.com/article/10.1007/s11156-024-01304-1 (open access, PDF: /content/pdf/10.1007/s11156-024-01304-1.pdf) · Hansen et al. https://academic.oup.com/jfec/article-abstract/22/1/224/6759403 , arXiv: https://arxiv.org/abs/2109.12142 · Forino & Morelli https://link.springer.com/article/10.1007/s10479-026-07030-2 .

---

## 2. The 8h funding-settlement micro-movements (00:00 / 08:00 / 16:00 UTC)

This is the part most directly relevant to rapana, because the repo already settles funding-reads on exactly this cadence (`backtest/funding_spike.py:55` `_DEFAULT_INTERVAL_MS = 8*3600*1000`, doc'd in `research/agents/12-mexc-funding.md:12`).

### 2.1 What is documented
- **De Blasis & Webb (2022)**, *J Futures Markets* — *"we observe trade spikes around funding times (UTC: 00:00, [08:00,] 16:00)"*. Funding times are explicitly named as a driver of intraday trade-volume spikes in perp markets. URL: https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.22305
- **Alexander & Imeraj (2023)**, *Quantitative Finance* 23 — bitcoin option implied-volatility and delta-hedging behaviour clusters at *"hours at funding payment times or once per day at 00:00 UTC."* URL: https://www.tandfonline.com/doi/abs/10.1080/14697688.2023.2181205
- **Alexander, Heck & Kaeck (2022)**, *Applied Mathematical Finance* — reveal a *"remarkable intraday pattern of both trading volume and volatility"* on Binance/Kraken with funding-settlement anchors at midnight, 08:00, 16:00 UTC. URL: https://www.tandfonline.com/doi/abs/10.1080/1350486X.2022.2125885
- **Heck (2023) PhD thesis** — funding periods run *"midnight UTC to midnight UTC"* and the 8h settle shapes the volume curve. URL: https://sussex.figshare.com/articles/thesis/Information_flows_in_cryptocurrency_markets/24551557

### 2.2 The mechanism (why a micro-spike is *predictable*, not random)
At each 8h settlement, two structural forces hit the book simultaneously:
1. **Cost-of-carry repricing.** Longs/shorts who were paying funding settle the tab; the cost-of-carry cliff tilts the marginal economics of holding, so positioning is repriced at the settlement boundary. The repo's funding-fade study already monetizes the *sign* of this (`12-mexc-funding.md:14-23`); the time-of-day angle is the *clock* of it.
2. **Mandatory unwind / top-up of the crowded side.** Leveraged accounts that crossed a maintenance-margin threshold on the settle must rebalance exactly at the boundary — a deterministic, clock-anchored flow. This is the crypto analog of the well-known FX "fixing" flow (WM/Reuters 16:00 London = 15:00/16:00 UTC) that Breedon & Ranaldo (2013) and others document in fiat.

### 2.3 Magnitude (honest)
No peer-reviewed paper gives a clean bp figure for "spot mid drift in the 5 min after a funding settle on a retail venue." What the literature gives is **relative** magnitude:
- Hansen et al. (2024) report the peak/trough hourly volatility **ratio** is a multiple (their Fig. shows the 16:00–17:00 UTC bar materially above the 05:00 UTC bar; exact ratio not restated here to avoid fabrication).
- Brauneis et al. (2025) normalize to z-scores, so again the headline is *shape*, not bp.

**[HYPOTHESIS → backtest]:** on rapana's own minute-bar store (`data/store.py`), bin returns by minute-offset-from-funding-settle and test (a) is realized vol in `[-10min, +30min]` vs the 8h mean elevated, and (b) is there a sign-biased drift (crowded side overshoots then reverts). The store already holds the funding timestamps (`store.py:32`, `funding` table) and OHLCV — this is a free, in-repo check with no new data plumbing.

---

## 3. Index & basket-rebalance drift (the weakest sub-claim — flag it)

This is the part most likely to be already-arbed and should be treated as exploratory.

- **Crypto index providers do publish fixed-clock rebalance schedules.** MarketVector (MV) Digital Asset indices, CoinDesk Indices (e.g. CDX, CIADA), and S&P Cryptocurrency Broad Digital Market (BDM) rebalance **monthly** (typically on the last business day, with the new weights effective at a stated UTC time). A monthly basket rebalance forces the *tracking* wrappers (ETPs, structured products, index funds) to buy/sell constituents at the same clock instant — a textbook deterministic flow.
- **Anecdotal industry read:** several market-maker blogs (Cumberland, Wintermute quarterly letters) report noticeable basket-rebalance flow at end-of-month and at the **15:00–16:00 UTC** window (the same window §1 already flags). This is consistent with — and partly *is* — the tea-time peak.
- **ETF creation/redemption clock (BTC/ETH spot ETFs, post-Jan-2024 US, post-2024 HK):** creations/redemptions settle at the **4:00 PM ET NAV print = 20:00 UTC (summer) / 21:00 UTC (winter)**, and authorized-participant flow is hedged into the CME session (open 23:00 UTC). This is a documented secondary flow anchor at the *US-afternoon / early-UTC-evening* window — weaker and more recent than the 16:00 UTC peak, but real and growing with ETF AUM. Grayscale's daily holdings update (historical GBTC, now BTC/ETH ETFs) publishes at a fixed UTC time and is consumed by quant flows.

**Honest verdict:** the basket-rebalance effect on *individual constituent tokens* (the part you could trade on MEXC spot) is plausible but **not separately identified** in the academic literature from the general tea-time peak. Treat it as a *contributing explanation* for the 16:00 UTC peak, not as a standalone, separately-tradeable signal. **Do not** build a standalone rebalance-drift strategy on this — the evidence is too thin. The robust move is to treat the *whole fixed-clock cluster* as a risk window (§4).

---

## 4. ToS-safe strategy: AVOID first, FADE second

Per the MEXC envelope (`research/agents/16-mexc-tos-envelope.md`, `research/agents/12-mexc-funding.md:100-119`), rapana must stay low-frequency, single-leg, maker-preferred, and must not race settlements or look like a settlement-HFT. The fixed-clock effect maps cleanly onto two compliant postures.

### 4.1 The durable edge — AVOID the bad windows (risk overlay, not alpha)
This is the *load-bearing* recommendation and the one most robust to decay. The literature shows the 15:00–17:00 UTC window is *simultaneously* the highest-volatility, **highest-illiquidity** (Corwin-Schultz spread peaks there too, Brauneis et al. 2025 Fig.1), highest-volume window. A slow maker bot that enters in that window gets:

- **worse fills** (spread is widest exactly then),
- **more adverse selection** (informed flow is concentrated then — Admati-Pfleiderer),
- **bigger slippage** on the entry print,
- **higher chance of being run over** by an institutional flow swing before the thesis plays out.

**Rule (risk overlay):** suppress *new* directional entries (and especially *new* entries on small/mid-caps where MEXC depth is thinnest, `research/agents/17-mexc-smallcaps.md`) in **[15:00, 17:00] UTC**; optionally also widen stops / reduce size in **[23:30, 00:30] UTC** (the daily reset + funding settle + thin Asia handoff, where odd micro-crashes cluster — the "first hour is elevated" result of Brauneis et al.). This costs nothing (you can always enter 1–2h later), is pure risk hygiene, and is *self-evidently benign* to MEXC's risk engine (fewer orders at peak = less bot-like, not more).

This is an **overlay on the existing `Signal`→combiner→PM path**, not a new analyst: it gates *execution timing*, not *direction*. It belongs in `fleet/orchestrator.py` as a clock-aware entry-throttle / size-scaler that the PM (`agents/portfolio_manager.py:55-81`) consults before placing.

### 4.2 The optional, hypothesis-gated edge — FADE post-settlement overshoot
For the cases where rapana already has a directional view, the funding-settle window can *improve* entry timing rather than just be avoided:

> **If a token makes an extreme move in the `[settle, +30min]` window after a 00/08/16 UTC funding settlement, and the move is in the direction of the *crowded* side (i.e., the side that was paying funding per `store.funding`), that move is more likely to be liquidation-driven overshoot than informed flow → fade it.**

This is the *time-windowed* cousin of the already-validated funding-fade (`backtest/funding_spike.py`). The un-validated leg is the "in the 30 min after settle, specifically" sub-horizon. **[HYPOTHESIS → backtest]** on the minute-bar store before going live.

Crucially: even if you trade this, you are still a **single-leg, slow, maker** order placed *after* the settle prints — you are not racing the settlement, not crossing the book at the settle tick, not doing anything that looks like settlement-HFT. You are using the public funding sign + a public clock to time a directional MEXC trade. Indistinguishable from any other signal-driven order. ToS-clean.

### 4.3 What is explicitly *not* proposed (and why)
- **No settlement-racing / book-sniping at 00:00:00 UTC.** That is exactly the HFT/settlement-arb fingerprint MEXC freezes accounts for (`16-mexc-tos-envelope.md`, `12-mexc-funding.md:100-104`). Rapana evaluates per cycle (minutes), not per tick.
- **No CME-open / ETF-NAV racing.** Same reason, plus it requires acting on cross-venue timing cues that look algorithmic.
- **No basket-arb across index constituents.** That is the multi-leg, cross-sectional, looks-like-institutional-arb behaviour that trips risk engines, and the standalone evidence (§3) is too thin anyway.

---

## 5. Durability & decay — honest per-sub-effect

| Sub-effect | Direction of decay | Reasoning |
|---|---|---|
| **15:00–17:00 UTC vol/illiquidity peak** | **INTENSIFYING** (anti-decay) | Hansen et al. 2024 document the pattern growing stronger 2018→2021; ETF/perp institutionalization since has only added more clock-anchored flow. Structurally paid for by equity-overlap + funding-settle conventions that aren't going away. |
| **04:00–06:00 UTC vol trough** | Stable | Mirrors the peak; driven by the absence of US/EU flow, structurally persistent. |
| **00:00 UTC secondary spike (funding + reset)** | Stable-to-mild-decay | Persists as long as 8h funding dominates; could dilute if funding cadence fragments (some venues moving to 4h/1h), but MEXC is firmly 8h (`12-mexc-funding.md:12`). |
| **Post-settle overshoot fade (§4.2)** | **Likely decaying** | This is the most "arbable" piece — it's pure directional alpha from a public clock + public funding sign. Expect hit-rate to compress as more quants trade it. **This is why §4.2 is optional/hypothesis-gated and §4.1 (avoid, not fade) is load-bearing.** |
| **Index constituent rebalance drift (§3)** | **Already mostly arbed for majors; residual in small-caps** | The basket-rebalance literature in equities (Hedge fund / index-fund rebalance flow) shows the *predictable* component is captured by MMs; only the *illiquid-constituent* tail retains alpha. For rapana this is small-caps only, and the evidence is thin. Do not rely on it. |

**The single most durable statement in this whole note:** "Don't take new small-cap entries in the 15:00–17:00 UTC window; you will pay wider spreads and eat more adverse selection." That sentence will still be true in 2030 regardless of how efficient crypto gets, because it's a *risk-avoidance* rule paid for by structural institutional flow, not a *forecast* that competitors can neutralize.

---

## 6. Signal spec — `ClockFlowAnalyst` + execution-time throttle

Splits cleanly into (A) a **risk-overlay gate** in the orchestrator (the durable, recommended piece) and (B) an **optional `Analyst`** that emits the post-settle fade (the hypothesis piece). Both fit the existing injectable architecture with no core rewrite.

### 6.1 Component A — execution-time throttle (durable, do this first)
**Location:** `fleet/orchestrator.py` entry/size path (consumed by `agents/portfolio_manager.py:55-81`).
**Spec:**
```python
# Clock-flow risk overlay. Gate on UTC hour. Zero new infra.
def clock_flow_scale(utc_hour: int, *, is_smallcap: bool) -> tuple[float, str]:
    """Return (size_multiplier, reason) for a *new* directional entry.
    Existing positions are NOT force-exited by this overlay — it gates new entries
    and optionally scales size. Exit logic stays with the PM.
    """
    if 15 <= utc_hour < 17:                       # 15:00-17:00 UTC: peak vol + peak illiquidity
        m = 0.0 if is_smallcap else 0.5            # small-caps: no new entries; majors: half size
        return m, "tea_time_avoid"
    if utc_hour == 0 or utc_hour == 23:            # 00:00 UTC reset + funding settle window
        return 0.5, "midnight_reset_throttle"
    if 4 <= utc_hour <= 6:                         # 04:00-06:00 UTC: vol trough → fine to enter,
        return 1.0, "trough_ok"                    # but spread-tight, so prefer maker
    return 1.0, "normal"
```
- **Effect:** pure risk hygiene; no signal, no direction. Costs nothing on average and *saves* you from the worst-fill, worst-adverse-selection window. This is the durable edge.
- **`is_smallcap`** comes from the universe tier (`research/agents/17-mexc-smallcaps.md`); the asymmetry (no small-cap entries at tea-time, only half-size majors) reflects that small-cap MEXC depth is materially worse and adverse selection scales with illiquidity.

### 6.2 Component B — `ClockFlowAnalyst` (optional, post-settle fade)
**Mirror** the proven `Arbitrageur`/funding-analyst templates (`agents/arbitrage.py:13-34`, `12-mexc-funding.md:151-174`).

**Feed** (`feeds/clock_flow.py`, mirror `feeds/base.py:6-14`): `score(symbol) -> (score[-1..1], confidence[0..1])`, fail-soft `(0.0, 0.0)`.
- Inputs: `store.fetch_funding_range(symbol)` (signed funding, already populated) + `utc_now` + minute-bar close from `data/store.py`.
- Fire only inside `[settle_ts, settle_ts + 30min]` for each of 00/08/16 UTC; return `(0.0, 0.0)` at all other times (the overlay must be SILENT outside its window — never forces a trade).
- Inside the window:
  ```
  ret_30   = (close_now / close_at_settle) - 1
  crowd    = sign(funding_at_settle)             # + => longs were crowded
  overshoot = ret_30 * crowd                      # + => price extended WITH the crowd = liquidation-driven
  if overshoot > k:   score, conf = -1 * min(overshoot/K, 1), 0.4    # fade the overshoot
  elif overshoot < -k: ...                         # symmetric on the short-crowd side
  else:               score, conf = 0.0, 0.0
  ```
- `k`, `K` are pre-committed, not mined (e.g. `k=30bp`, `K=150bp` — i.e., 30bp of crowd-direction move triggers, saturates at 150bp). Validate via Deflated-Sharpe on the minute-bar store before promoting `confidence` above 0.4.

**Analyst** (`agents/clock_flow.py`, mirror `agents/arbitrage.py`): emits
```python
Signal(symbol, source="clock_flow", direction, strength=score,
       confidence=conf,
       rationale=f"post-settle overshoot fade: funding={funding:.4%}, ret30={ret_30:+.2%}",
       extras={"funding_rate": funding, "ret_30min": ret_30, "minutes_since_settle": mss,
               "settle_utc": settle_utc, "source_policy": "post_settle_fade_k30bp"})
```
- `source="clock_flow"` → its **own `ReflectionMemory` bucket** (`fleet/memory.py:114-121`) so the learning loop can down-weight it independently if the fade decay proves real (§5).
- Distinct from `source="yield"` (the funding-fade of agent 12): that fades the *level* of funding on the 8h boundary; this fades the *price action in the 30 min after* the boundary. They are complementary and can both run; the combiner (`signals.py:87-104`) handles the weighted sum.

### 6.3 Wiring (no core change, no new secrets)
- Component A: add `clock_flow_scale` call in `fleet/orchestrator.py` before the PM places a *new* entry; pass `is_smallcap` from the universe classifier. One helper + one call site.
- Component B: register `ClockFlowAnalyst` in `agents/__init__.py`, append to `Fleet.analysts` (`fleet/orchestrator.py:91-95`). Reuses the existing `store` funding + OHLCV tables — **no new data source, no new keys, no new network calls** beyond what the per-cycle loop already does.
- **Both stay inside the envelope:** single-leg MEXC, maker-preferred (`08-mexc-client-edge.md:87-89`), per-cycle cadence, no settlement racing, no cross-venue leg.

---

## 7. Sources (verified, load-bearing)

**Intraday seasonality (the load-bearing cluster):**
- **Brauneis A., Mestel R., Theissen E. (2025)**, "The crypto world trades at tea time: intraday evidence from centralized exchanges across the globe," *Rev Quant Fin & Acc* 64:275–304 — open access: https://link.springer.com/article/10.1007/s11156-024-01304-1 · PDF https://link.springer.com/content/pdf/10.1007/s11156-024-01304-1.pdf · 1940 pairs / 38 exchanges / 5 continents; vol/volume/spread peak 16:00–17:00 UTC, trough ~03:00–06:00 UTC; first hour also elevated; shape global not local.
- **Hansen P.R., Kim C., Kimbrough W. (2024)**, "Periodicity in Cryptocurrency Volatility and Liquidity," *J Fin Econometrics* 22:224–251 — https://academic.oup.com/jfec/article-abstract/22/1/224/6759403 · arXiv https://arxiv.org/abs/2109.12142 · peak hour after 16:00 UTC; trough ~05:00 UTC; **pattern "grown stronger over the years," linked to algo trading + funding times** (key anti-decay evidence).
- **Forino A., Morelli G. (2026)**, "Liquidity and volatility nexus in cryptocurrency markets," *Annals of Operations Research* — https://link.springer.com/article/10.1007/s10479-026-07030-2 · peaks at midnight, 14:00, 16:00 UTC.
- **Eross A., McGroarty F., Urquhart A., Wolfe S. (2019)**, "The intraday dynamics of bitcoin," *Res Int Bus Finance* 49:71–81 — https://doi.org/10.1016/j.ribaf.2019.01.008 · earlier single-asset intraday evidence.
- **Baur D.G. et al. (2019)**, "Bitcoin time-of-day, day-of-week and month-of-year effects," *Finance Res Lett* 31:78–92 — https://doi.org/10.1016/j.frl.2019.04.023 .

**Funding-settlement & futures-microstructure:**
- **De Blasis R., Webb A. (2022)**, "Arbitrage, contract design, and market structure in bitcoin futures markets," *J Futures Markets* — https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.22305 · *"trade spikes around funding times (UTC: 00:00, 08:00, 16:00)."*
- **Alexander C., Imeraj A. (2023)**, "Delta hedging bitcoin options with a smile," *Quantitative Finance* — https://www.tandfonline.com/doi/abs/10.1080/14697688.2023.2181205 · IV/delta-hedge clustering at *"funding payment times or once per day at 00:00 UTC."*
- **Alexander C., Heck D.F., Kaeck A. (2022)**, "The role of Binance in bitcoin volatility transmission," *Applied Mathematical Finance* — https://www.tandfonline.com/doi/abs/10.1080/1350486X.2022.2125885 · remarkable intraday pattern anchored to funding settle.
- **Heck D.F. (2023)**, "Information flows in cryptocurrency markets," PhD thesis, U. of Sussex — https://sussex.figshare.com/articles/thesis/Information_flows_in_cryptocurrency_markets/24551557 · funding periods midnight-to-midnight UTC shape the volume curve.

**Daily reset / settlement / institutional flow:**
- **Lin K. (2026)**, "Extending Exchange Trading Hours," WFE Research (SSRN 6224760) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6224760 · *"00 UTC corresponds with the daily reset of the cryptocurrency trading."*
- **Rösch D. (2025)**, "Dynamics of exchange trading and blockchain settlement," SSRN 5309531 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5309531 · trading + on-chain settlement peak ~15:00 UTC.
- **Alexander C., Heck D.F. (2023)**, "Volume and volatility spillovers between crypto exchanges," U. of Sussex — https://sussex.figshare.com/articles/journal_contribution/Volume_and_volatility_spillovers_between_crypto_exchanges/23495810 .

**Repo priors (the envelope & the funding-fade foundation):**
- `research/agents/16-mexc-tos-envelope.md` — MEXC anti-bot/freeze constraints.
- `research/agents/12-mexc-funding.md:12,55,100-119` — 8h funding cadence, Deflated-Sharpe fade, KYB gate.
- `research/agents/17-mexc-smallcaps.md` — small-cap depth asymmetry (why §4.1 throttles small-caps harder).
- `backtest/funding_spike.py:55,79-84,109-110` — pre-committed fade ladder, point-in-time firewall, `gross_price` vs `gross_funding` split (the decay gauge for §4.2).
- `signals.py:17-46,87-104` — `Signal` contract + `weighted_combine` (where the new `source="clock_flow"` plugs in).
- `fleet/orchestrator.py:91-95,112` — analyst registration + `OrderRateLimiter` (the host for Component A).

---

## 8. Bottom line

The clock-anchored flow anomalies are **real, global, and (unusually) intensifying rather than decaying** — three large peer-reviewed samples independently put the volume/volatility/illiquidity peak at **16:00–17:00 UTC** (US+EU equity overlap + 16:00 funding settle), the trough at **04:00–06:00 UTC**, and a secondary spike at **00:00 UTC** (daily reset + funding settle). The durable, ToS-safe play for rapana is **avoidance**, not alpha-capture: throttle new small-cap entries in `[15:00,17:00] UTC` and half-size around `[23:00,00:30] UTC` as a clock-overlay on the orchestrator — pure risk hygiene that will still hold in 2030. The optional, hypothesis-gated add-on is a **post-settlement overshoot fade** analyst (`source="clock_flow"`) on its own learnable bucket, validated in-repo against the minute-bar store before promotion. No settlement-racing, no cross-venue leg, no new data plumbing.

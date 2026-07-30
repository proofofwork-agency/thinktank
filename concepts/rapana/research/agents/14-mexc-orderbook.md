# 14 — Order-book depth imbalance as a low-freq read-only signal

**Agent:** 14/60 · **Scope:** `rapana/mexc/client.py:136` (`fetch_order_book`, unused), `rapana/fleet/data_provider.py`, `rapana/signals.py`, `rapana/data/store.py`
**Goal:** Decide whether bid/ask depth imbalance can become a *non-standard, low-frequency, read-only* Signal for the fleet — without tripping MEXC's anti-HFT/arb freeze rules — and how to wire it into `combine_signals`.

**Verdict up front:** Depth imbalance *does* predict short-horizon crypto drift, but the edge **decays in seconds**, not minutes. A slow (every-N-minutes) snapshot captures only the **persistent/regime** component — which is too weak to be an entry trigger, but **genuinely useful as a trade VETO and conviction filter**. This matches the repo's read-only, low-freq posture and MEXC's anti-bot envelope. Recommended role: **modulator/veto, never primary alpha**, with deliberately capped confidence, and **only after a book-history ingestion phase** (it is un-backtestable today).

---

## (a) Does bid/ask depth imbalance predict short-horizon crypto drift?

**Yes — repeatedly demonstrated, but the horizon is short and the strength is modest.**

| Study | Venue / asset | Finding | Horizon / strength | URL |
|---|---|---|---|---|
| **Guo, Bifet, Antulov-Fantulin (2018)**, IEEE ICDM | BTC/USD (Bitstamp) | Order-book features (spread, depth, volume, **bid/ask slope**, weighted spread) carry short-term price-fluctuation signal *beyond* realized volatility. | seconds–minutes; OB features materially improve ML direction models. | https://arxiv.org/abs/1802.04065 |
| **Cestari, Barchi, Busetto, Marazzina, Formentin (2023)** | USDT/USD LOB | Hawkes point-process + COE model on LOB forecasts **return sign** and **beats benchmarks in cumulative profit** (50 Monte-Carlo scenarios). Confirms **base imbalance** as a primary regressor. | event-scale (LOB update) | https://arxiv.org/abs/2312.16190 |
| **Koutmos & Wei (2023)**, *Rev. Quant. Financ. Account.* 61:125–154 | BTC (Bitstamp, incl. COVID + FTX) | **Order-flow imbalance + network-value controls** nowcast BTC **crash risk** (GEV + logistic). OFI is a meaningful predictor; type I/II errors shift across probability cutoffs. | daily crash nowcast (slow use) | https://link.springer.com/article/10.1007/s11156-023-01148-1 |
| **Smutný (2025)**, Charles Univ. thesis | BTC, ETH, LTC | "Imbalances between bid and ask **significantly predict**" price. | short-horizon | https://dspace.cuni.cz/handle/20.500.11956/200516 |
| **Bieganowski & Ślepaczuk (2026)** | Crypto | Model relying **primarily on order-book imbalance** predicts direction incl. a dramatic BTC collapse. | short-horizon, explainable | https://arxiv.org/abs/2602.00776 |
| **Wang (2025)**, SSRN 5331939 | Crypto spot pairs | Supply–demand LOB imbalances predict **mid-price changes**; "better inputs matter more than stacking another hidden layer." | LOB-tick to short | https://arxiv.org/abs/2506.05764 |
| **Nejat & Breton (2021)**, HEC Montréal | BTC | Logistic regression on OB + market info predicts price direction. | short | https://reflexion.hec.ca/docs/memoires/nejat_amin_m2021.pdf |

**Foundational equities evidence (the theory the crypto work transfers):**
- **Cont, Kukanov & Stoikov (2014)**, *"The price impact of order book events,"* J. Financial Econometrics — defines **OFI**; high in-sample explanatory power for short-horizon returns at tick frequency. Canonical. (https://academic.oup.com/jfec/article-abstract/12/1/47/2463802)
- **Chordia, Roll & Subrahmanyam (2002)**, *"Order imbalance, liquidity, and market returns,"* J. Financial Econometrics 65:111–130 — order imbalance predicts short-run returns. (https://doi.org/10.1016/S0304-405X(02)00136-8)
- **Cartea, Donnelly & Jaimungal (2018)**, *"Enhancing Trading Strategies with Order Book Signals"* — multi-level OFI features add predictive content; **contribution decays across book levels**, justifying volume-weighting of the top-K levels. (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3008698)

---

## (b) The decay profile (the load-bearing honesty section)

1. **Tick-to-second scale: strong.** OFI/imbalance explains a large fraction of contemporaneous short-horizon return variance in equities (Cont/Kukanov/Stoikov) and adds clear directional signal in crypto (Guo, Cestari, Wang). **This is the part that is real alpha — and it is exactly the part a low-freq poll cannot capture.**
2. **Seconds-to-minutes: weak-but-nonzero.** Aggregated/top-K weighted imbalance retains directional content (Cartea; Cestari's base-imbalance regressor), but the per-snapshot R² collapses fast as the horizon stretches past ~1 min.
3. **Minutes-to-hours: essentially gone as an entry trigger.** By the time a several-minutes-old snapshot is acted on, the informed flow that produced the imbalance has usually already moved price → **adverse selection**. Entering on the stale read means paying the moved price.

**Implication for this fleet:** the *directional drift* edge is HFT-frequency and therefore **off the table** under MEXC's anti-bot rules (and off the table for a REST-polling architecture regardless). What *survives* a slow poll is the **persistent/regime** component of the book — standing walls and one-sided depth that reflect maker conviction over minutes-to-tens-of-minutes. That is too weak to trade *on*, but useful to *veto/filter with* (see §e).

---

## (c) Low-frequency feasibility & MEXC ToS boundary

**Can a slow poll use persistent imbalance as a regime/conviction filter without being HFT? — Yes.**

- **Persistence is real in crypto.** Books are thinner and maker refresh is slower than equities, so standing walls and one-sided depth persist for minutes-to-tens-of-minutes. A 5–15 min cadence samples the regime component; the lost fast component is HFT territory anyway.
- **Read-only GETs on a public endpoint, spaced minutes apart, with zero order churn, are not the pattern MEXC targets.** The repo's established position (`RESEARCH-SYNTHESIS.md:90,108`, citing `mexc.com/support/article/why-mexc-restricts-automated-trading-17827791531135`) is that MEXC restricts **bot/algo/HFT/arbitrage** patterns: high request rates, cancel-replace bursts, sub-second latency, cross-market behavior. Occasional market-data reads are normal usage. The client already floors requests at `rateLimit=200ms` (`client.py:15-19`); a depth analyst must poll **far slower** (minutes) to stay obviously on the right side and to keep headroom for the rest of the fleet.
- **Read-only posture already accepted.** The fleet already does this for tickers/funding (`data_provider.py:47`, `data/ingest.py`); a book poll is the same risk class. **No order placement is involved** (`client.py:32-36` — order placement intentionally absent), so there is no maker/taker behavior to flag.

**Boundary to respect:** cadence ≥ several minutes per symbol, jittered, no burst-polling around events, no websocket (a `ccxt.pro` depth stream would look far more like a market-making infra and is out of scope). Stay REST + slow.

---

## (d) Depth signals that survive latency

All three are **aggregated / regime-level** features, chosen because they decay slowly enough to survive a multi-minute poll:

1. **Book pressure slope / weighted imbalance (primary).** Volume-weighted bid vs ask depth across the **top-K levels** (K≈10), `pressure = (Σwᵢ·bidᵢ − Σwᵢ·askᵢ) / (Σwᵢ·bidᵢ + Σwᵢ·askᵢ) ∈ [−1,1]`, weights decaying with level (Cartea justifies this). **Robust to a single spoofed level** (unlike best-quote imbalance). Decays slowly because it is aggregated.
2. **Wall detection (resting large orders).** Flag levels within ±X% (e.g. ±1%) of mid whose size > N× (e.g. 3×) the local median level size. Walls **persist** (they are resting) and mark where a large participant is defending/absorbing → strong, slow-moving conviction/absorption read. Lifetime is minutes-to-hours.
3. **Spread-regime classification.** Percentile of `(best_ask − best_bid)/mid` vs a short rolling history → {tight, normal, wide}. **Wide-spread regime = low liquidity / high adverse-selection risk** → entry veto. Slow-moving (regime), survives latency trivially.

All three are computable from a single `fetch_order_book` snapshot; spread-regime additionally needs a small per-symbol ring buffer of recent spreads.

---

## (e) Honest role: when a slow book read actually helps

**Not as an entry trigger.** Drift has decayed by the time you read it; adverse selection means you'd take the wrong side of informed flow. Three uses that *do* help:

- **Trade VETO (highest value, lowest risk).** Decline an intended entry when the book is one-sided *against* it (e.g. depth piled on the ask when the fleet wants to go long → overhead absorption), or when spread is in the **wide** regime. A veto sidesteps adverse selection entirely — you're declining, not chasing.
- **Conviction filter (modulator).** Persistent imbalance in the *same* direction as a higher-timeframe thesis (funding/structure/macro edge) → nudge `confidence` up; opposite → nudge down. Never strong enough to flip a Signal alone.
- **Sizing / impact.** Estimate realized-spread/slippage for the intended order size from current depth → size down when the book can't absorb it. (Useful only once the executor leaves market-only; today `execution.py:95` sends `type="market"`.)

Deferred: **wall-aware stop placement** (place stops just beyond large resting walls) — needs maker/postOnly execution which the client lacks today (`client.py:32-36`; see agent 08's `create_maker_order` proposal).

---

## (f) Signal spec — wiring into the existing pipeline

**Critical honesty precondition:** the repo stores **no L2 history**. `store.py` has only `candles`, `funding`, `meta` tables (`store.py:14,29,39`); `fetch_order_book` has **zero production callers** (`client.py:136`; confirmed in `04-data-edge.md:69`, `02-backtest-edge.md:43,92`). **This edge is therefore un-backtestable today** — it conflicts with the repo's walk-forward / Deflated-Sharpe discipline (`git log` `9a6fbf9`). **Sequence: ingest book history to a new table first (pure collection, weeks), evaluate out-of-sample whether the persistent-imbalance filter improves the existing strategy, only then let it influence live sizing.**

### New agent: `DepthAnalyst` (`rapana/agents/depth.py`, mirroring `agents/market.py`)
```
class DepthAnalyst(Analyst):
    role = "depth_analyst"
    def __init__(self, k_levels=10, spread_lookback=96, cadence_minutes=10): ...
    def analyze(self, symbol, provider) -> Signal:
        book = provider.get_order_book(symbol, limit=100)   # new DataProvider method
        pressure, spread_pctile, wall_bias = features(book, history)
        # VETO wins: wide spread OR pressure strongly opposite to fleet thesis
        if spread_pctile >= 0.90: return neutral_veto("wide-spread regime")
        ...
        return Signal(symbol, "depth", direction, strength,
                      confidence=0.15,  # deliberately low — modulator, not alpha
                      rationale=..., extras={"pressure":..., "wall_bias":..., "veto":bool})
```
- `source="depth"` is a **new source** alongside market/sentiment/macro/arbitrage/yield (`signals.py:21`).
- **Confidence capped ~0.15–0.3** so `combine_signals` (`signals.py:73`) and `weighted_combine` (`signals.py:87`) treat it as a gentle modulator. Default `source_weights["depth"] ≈ 0.5` until validated by the reflection loop.

### Touch points (file:line)
| Change | Where |
|---|---|
| `fetch_order_book` (already read-only) | `rapana/mexc/client.py:136` — **no change needed** |
| Add `get_order_book(symbol, limit)` to `DataProvider` + per-symbol spread ring buffer | `rapana/fleet/data_provider.py:33` (StoreDataProvider), `:57` (InMemoryProvider) |
| New `book` snapshot table (ts, symbol, json bids/asks, pressure, spread) | `rapana/data/store.py` (after `:39`) + ingest path |
| New analyst file | `rapana/agents/depth.py` (mirror `agents/market.py`) |
| Register analyst + set slow cadence in fleet loop | `rapana/fleet/orchestrator.py` / `runner.py` |
| Combiner | `combine_signals` (`signals.py:73`) consumes unchanged; `weighted_combine` (`signals.py:87`) down-weights until validated |

### Cadence & rate budget
- One `fetch_order_book` GET per symbol per cycle, cycle ≥ 5–15 min, **jittered** (not burst-synchronized around funding/bar events). With the universe Scout's pair count this stays far under the 300/10s IP weight budget (`client.py:13`).
- **No websocket.** A `ccxt.pro` depth stream would re-introduce exactly the HFT-infrastructure footprint MEXC's rules target.

---

## Bottom line

Depth imbalance genuinely predicts short-horizon crypto drift (Guo 2018; Cestari 2023; Koutmos & Wei 2023; Smutný 2025) but **the alpha decays in seconds** — out of reach of any REST-polling, freeze-safe design. A slow (≥5 min) read-only poll of the already-wrapped `fetch_order_book` (`client.py:136`) is **inside MEXC's anti-bot envelope** and captures the **persistent regime component**: usable as a **trade VETO and conviction filter with deliberately capped confidence**, never as an entry trigger. Hard prerequisite: **ingest book history to a new `store.py` table first** — the edge is un-backtestable today and must not touch live sizing until forward-validated out-of-sample.

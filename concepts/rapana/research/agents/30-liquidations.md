# 30 — Liquidation cascades & post-flush spot bounces (mean-reversion edge)

**Agent:** 30/60 · **Scope:** Forced-liquidation cascades on crypto perps as a **bullish spot mean-reversion trigger** — mechanism, evidence, low-frequency detection, a `LiquidationFlushAnalyst` Signal spec, and an honest falling-knife risk treatment.
**Stance:** NON-standard, low-frequency (hourly cadence), **spot-only** execution. The fleet already trades spot and already reads perp funding key-less (`MexcFuturesClient`); this study reuses that posture. No futures position, no arbitrage, no sub-minute racing — all inside MEXC's anti-bot envelope (`RESEARCH-SYNTHESIS.md:108`).

All citations are `file:line` for repo code and bare URLs for external sources. Where peer-reviewed magnitudes do not exist (most of the *bounce* literature is practitioner, not academic), numbers are flagged **[HYPOTHESIS → backtest]** against the repo's free data. No vibes presented as fact — same discipline as `research/agents/12-mexc-funding.md`.

---

## 1. Mechanism — why a liquidation cascade should bounce

A perpetual-futures liquidation cascade ("long squeeze") is a **positive-feedback deleveraging**: price drops → leveraged longs hit maintenance margin → the venue force-sells their positions → price drops further → more longs are liquidated. The textbook end-state is well modeled: Klages-Mundt & Minca formalize the symmetric phenomenon as a **deleveraging spiral driven by a submartingale**, producing "faster collateral drawdown … accompanied by higher price variance," and note the spiral "resembles a short squeeze" on the flip side (arXiv:2004.01304, *Mathematical Finance* 2024 — https://arxiv.org/abs/2004.01304).

The bounce thesis rests on a single, mechanical claim:

> **A cascade is *transient forced flow*, not information.** Once the over-leveraged cohort is flushed, the *selling pressure that caused the drop disappears in a step*, while the underlying demand/supply curve has not moved. The price therefore snaps back toward the pre-flash level — a classic short-horizon reversal, but concentrated and time-stamped by the cascade itself.

Two structural reasons this is *more* than generic mean reversion:

1. **Forced ≠ willing.** Liquidation selling is involuntary and exhaustive — when the last marginal long is liquidated there is no remaining *forced* seller, only willing ones. The order-book imbalance flips abruptly. This is the mirror image of the funding-crowding unwind the repo already trades (`backtest/funding_spike.py`): funding identifies the *crowded* side; a liquidation flush is the *moment that crowd is force-closed*.
2. **Capital structure asymmetry for a spot trader.** The cascade plays out on the perp book; the spot book is dragged along by basis arbitrage but is *not* itself liquidating. A spot buyer post-flush takes the reversion leg **without** any liquidation/takeout risk of his own — he cannot be force-closed. This is what makes the edge compatible with the fleet's spot-only mandate.

**Horizon:** the bounce, when it occurs, is a **2–24h** phenomenon on liquid majors (BTC/ETH/SOL), stretching to ~48h on thinner alts. **[HYPOTHESIS → backtest]** This matches the funding-fade horizon already validated in-repo ("1–3 intervals, 8–24h," `research/agents/12-mexc-funding.md:23`).

---

## 2. Evidence — how strong / durable is the bounce?

### 2.1 Internal anchor (the reversion leg is already validated in-repo)
The strongest evidence that *the reversion itself* is real and net-of-cost is **already passing** the repo's honest gate:

- `backtest/funding_spike.py:1-384` — the contrarian funding fade **passed Deflated Sharpe > 0.95 AND best OOS net beats cash** (`funding_spike.py:370`), splitting price-leg from funding-leg so a "pass" can't be disguised carry (`funding_spike.py:109-110`).
- The liquidation flush is **the same reversion thesis with a sharper trigger**: where the funding fade bets that *crowded positioning* will unwind, the flush bets that the unwind *already started* and is near exhaustion. If the funding fade is net-profitable at 8h, entering spot *at the cascade* — the moment the crowd is being force-closed — is the highest-conviction instance of that same edge.

So the *load-bearing* claim (reversion after crowded-long unwind) is not in doubt; what is **not yet validated in-repo** is whether the *cascade-completion timing* adds enough edge over the simpler funding fade to justify the extra machinery and the falling-knife risk. That is the open question this study proposes to backtest (§6).

### 2.2 External evidence
| Source | Finding | Horizon / strength | URL |
|---|---|---|---|
| **Klages-Mundt & Minca (2020/2024)**, *Math. Fin.* | Formal stochastic model of deleveraging spirals; identifies the deflationary spiral as a **submartingale** that drives faster drawdown + higher variance; explicitly states it "resembles a short squeeze." Establishes the cascade is a *predictable feedback structure*, not noise. | mechanism (theoretical) | https://arxiv.org/abs/2004.01304 |
| **Giagkiozis & Said (2024)**, *Ledger* 9:1–15 | Tick-by-tick across 7 venues: OI/liquidations are **systematically misreported or delayed** by major derivatives exchanges — some report "wholly implausible" OI, others "delay messages of forced trades, i.e., liquidations." | data-honesty (load-bearing for §3) | https://arxiv.org/abs/2310.14973 |
| **Nimmagadda & Ammanamanchi (2019)**, q-fin.ST | Funding **Granger-causes** perp price at short lags; funding is heteroskedastic/persistent. Supports the reversion leg that funds the post-flush bounce. | short-horizon causal | https://arxiv.org/abs/1912.03270 |
| **Kim & Park (2025)**, q-fin.MF | Funding is the no-arb boundary that re-anchors perp to spot; extreme funding = extreme expected reversion by construction. | theoretical | https://arxiv.org/abs/2506.08573 |
| **CoinGlass aggregated liquidation feed** | The de-facto practitioner dataset: aggregate long/short liquidation $ across 30+ venues, liquidation maps, OI OHLC. Documents that large flushes (≥$100M–$1B aggregate) routinely print on sharp moves and are followed by partial retraces. Practitioner, not peer-reviewed. | event-scale (practitioner) | https://www.coinglass.com/LiquidationData · API: https://docs.coinglass.com |

### 2.3 The honest gap (no vibes)
There is **no peer-reviewed table of "post-flush bounce magnitude by horizon and win rate."** The practitioner literature (CoinGlass/Desk analyses of the recurring "$1B+ long rekt" events) consistently describes partial retraces of roughly **30–70% of the flush within 4–24h on liquid majors**, larger and far noisier on alts — but these are not Deflated-Sharpe-validated backtests and the samples are selection-biased toward the dramatic events people write about. Treat all such numbers as **[HYPOTHESIS → backtest]** against the repo's free data (§6). The only claim that *is* multiply-sourced is the **direction of the asymmetry**: forced-flow exhaustion produces a bounce *more often than continuation* in the immediate aftermath, which is why the trade is structured around **asymmetric R:R (small loss, partial-retrace target), not a high win rate** (§4.4).

---

## 3. Detection at low frequency — can you spot a flush hourly, for free?

**Yes — and critically, you do not need the liquidation feed to do it.** The single most useful finding here is from Giagkiozis & Said (arXiv:2310.14973): **per-exchange liquidation feeds are unreliable** (delayed/misreported). Depending on a raw liquidation counter is exactly the wrong design. The robust approach is to detect the **imprint** a cascade leaves on *four series the fleet can already get for free at hourly cadence* — funding, open interest, price, and volume/volatility:

### 3.1 The flush signature (the 4-feature rule)
A liquidation flush leaves a *coincident* signature across all four — any one alone is noise, the **combo** is the signal:

| Feature | What it measures | Free source (already wired?) | Flush signature |
|---|---|---|---|
| **Drawdown** | price vs rolling K-high | `candles` table (`data/store.py:14`) — **YES** | close ≥ **−8% to −15%** vs rolling-k-high over the window (majors; alts wider) |
| **OI collapse** | forced position close | `fetch_open_interest` / `fetch_open_interest_history` via ccxt `swap` — **NOT wrapped** (`research/agents/04-data-edge.md:77`) | OI down **≥10%** over the window = leveraged cohort was force-closed |
| **Funding spike → normalize** | the crowd that got flushed | `fetch_funding_rate_history` — **YES** (`client.py:195`) | funding was **extreme positive** (crowded long) *before*, now collapsing/negative |
| **Volume / range spike** | the forced-flow volume itself | `candles` (`store.py:14`) — **YES** | candle volume **≥3× rolling median**, candle range in top decile |

This is hourly-feasible: drawdown + volume come from the `candles` table that `MarketDataIngester` already populates (`data/ingest.py:49`); funding is already ingested (`data/ingest.py:162`); **only OI is new** — and it is "trivial on `swap` type" per `04-data-edge.md:77`, a one-line addition to `MexcFuturesClient`. No websocket, no sub-minute data, no liquidation counter required.

### 3.2 Free vs paid detection sources
| Source | What | Cost | Verdict |
|---|---|---|---|
| **MEXC perp funding** (settled history) | crowd readout | **FREE, key-less, already wired** (`client.py:195`) | **Primary crowd input** |
| **MEXC perp OI** (history) | forced-close readout | **FREE, key-less, trivial to add** (`04-data-edge.md:77`) | **Primary exhaustion input** — must be wrapped |
| **MEXC spot OHLCV + volume** | price/vol/range | **FREE, already wired** (`store.py:14`) | Drawdown + volume legs |
| **MEXC `liquidationOrders` WS push** | real-time liquidations | FREE, but WS-only (REST historical unreliable per Giagkiozis) | **Optional confirmation**, *not* a prerequisite; WS looks like bot infra (skip for now) |
| **CoinGlass API** | aggregated cross-exchange liquidation $, OI OHLC, liquidation map | **PAID** (tiered key, https://docs.coinglass.com) | Best-quality aggregate; the *reliable* liquidation $ series. Optional overlay once the free 4-feature signal is validated. Endpoints: `aggregated-liquidation-history`, `oi-ohlc-aggregated-history`, `liquidation-order` (7d REST), `ws-liquidation-order`. |

**Bottom line on detection:** the edge is detectable **for free, hourly, key-less, no new data vendor** — funding (have) + OI (one line away) + price/vol (have). The unreliable liquidation *feed* is explicitly **not** load-bearing; the *combo signature* is.

---

## 4. The edge — buy spot after a flush, tight risk, asymmetric

### 4.1 The trade
When the 4-feature flush signature fires for a **crowded-long** unwind (the common, statistically tractable case), **buy spot** of the same symbol a configurable **N hours after** detection (default **N = 2–4h**, or on a completion trigger — see 4.3). Hold for a partial-retrace of the flush.

### 4.2 Magnitude & horizon (honest priors — **[HYPOTHESIS → backtest]**)
| Leg | Prior | Source |
|---|---|---|
| Flush depth (majors) | −8% to −20% peak-to-trough over 1–12h | practitioner (CoinGlass); validate on repo candles |
| Bounce magnitude | **+30% to +70% of the flush** within 4–24h (majors); altcoin bounces larger but ~40% of the time continue down (falling knife) | practitioner priors, **not** validated |
| Win rate (net of cost) | **~50–58%** — the edge is *not* the win rate, it is the R:R | **[HYPOTHESIS → backtest]** |
| R:R | target ≈ 1.5–2.5× the hard stop | by construction (4.4) |

### 4.3 Why "N hours after," not "at the flush"
Giagkiozis (arXiv:2310.14973) shows liquidations are **reported late**; cascades can also **chain** (a flush begets a flush next session). Buying *at* the first flush maximizes falling-knife risk. Waiting **N = 2–4h** (or until a completion trigger: funding normalizes *and* a bullish reversal candle closes above the flush candle's midpoint) filters the ~40% of events that keep bleeding. This is the deliberate speed/cost of a low-frequency spot trader — exactly the opposite of the sub-second racing MEXC's rules forbid.

### 4.4 Risk envelope — asymmetric, not high-win-rate
- **Hard stop:** just below the flush low, `flush_low × (1 − 0.01..0.03)`. The thesis is *falsified* if price makes a new low → get out.
- **Target:** `entry + (0.3 to 0.7 × flush_depth)`. Scale out, don't greed for the full retrace.
- **Time stop:** exit by **24–48h** if neither target nor stop hit (reversion failed to materialize → the move was information, not forced flow).
- **Cost:** spot taker ~2 bp + ~2 bp slip one way (MEXC 0% maker promo reachable later via `research/agents/08-mexc-client-edge.md`); round-trip ~8 bp taker, ~4 bp maker.

---

## 5. Strategy spec — `LiquidationFlushAnalyst`

### 5.1 Agent
New analyst file `rapana/agents/liquidations.py` mirroring `agents/market.py` / `agents/yield_strategist.py`. Registered in the fleet loop at an **hourly cadence** (not per-tick). Detection function consumes the store + the new OI fetch; emits one `Signal` per symbol per cycle.

### 5.2 Detection rule (pre-committed, no post-hoc mining — mirror `funding_spike.py:79-84`)
```
flush_long(symbol, window=12h) := ALL of:
    dd      = (close - max(high[-window:])) / max(high[-window:])  <=  -0.08   # majors threshold
    oi_drop = (oi[-1] - oi[-window]) / oi[-window]                 >=  +0.10   # forced close
    fund    = max(funding[-window:]) >= +0.0010  AND  funding[-1] <= 0.3*max   # crowd existed, now flushed
    vol     = volume[-1] >= 3 * median(volume[-window:])                       # forced-flow volume
    # + completion gate (one of):  elapsed_since_low in [2h, 6h]  OR  reversal candle closed above mid
```
A symmetric `flush_short` (crowded short → bullish-by-squeeze-reversal is *weaker* and harder to time; **start long-only**). Thresholds are a pre-committed ladder (soft/primary/high-conviction at −8%/−12%/−16% drawdown) so the live rules match the backtested ones exactly, same discipline as the funding fade.

### 5.3 Mapping to the `Signal` contract (`rapana/signals.py:17-46`)
```python
# after flush_long(symbol) fires and completion gate passes
Signal(
    symbol=spot_symbol,                 # e.g. "BTC/USDT" — SPOT, not the perp
    source="positioning",               # new bucket (sibling to funding "yield"); fallback "market"
    direction="bullish",
    strength=clamp(flush_depth / 0.20, 0.25, 0.8),   # deeper flush → stronger, clipped, never >0.8
    confidence=0.45,                    # deliberate: this is a HYPOTHESIS-stage signal until backtested
    rationale=f"post-liquidation-flush spot mean-reversion: dd={dd:.1%} oi_drop={oi_drop:.1%}",
    extras={
        "flush_depth": dd, "oi_drop": oi_drop, "peak_funding": float(peak_fund),
        "entry_delay_h": N, "horizon_h": 24, "stop_ref": "flush_low",
        "source_policy": "flush_long_primary",
        "validated": False,             # flip True only after §6 backtest passes DSR
    },
)
```
Notes:
- **`source="positioning"` is a NEW source** alongside market/sentiment/macro/arbitrage/yield (`signals.py:21`). `weighted_combine` (`signals.py:87-103`) defaults its weight to 1.0 — set `source_weights["positioning"] ≈ 0.4` until the §6 backtest passes Deflated Sharpe, exactly as `research/agents/14-mexc-orderbook.md:97` down-weights unvalidated sources. Zero-friction fallback: `source="market"` (no schema change, but loses the "this is a distinct alpha family" provenance).
- **`confidence=0.45` and `validated=False` are load-bearing:** until `backtest/liquidation_flush.py` passes the same Deflated-Sharpe gate as `funding_spike.py`, the combiner must treat this as a weak, low-weight opinion, never a primary driver. `Signal.__post_init__` (`signals.py:27-41`) enforces the clip/sign invariants for free.
- It emits **bullish only** (the validated direction). Bearish post-short-squeeze reversal is *not* emitted until separately validated — short squeezes are faster and the post-squeeze continuation (momentum) often dominates the reversal.

### 5.4 How the pieces fit
```
ingest-funding + new ingest-oi + candles  →  store.{funding, oi*, candles}
   (cli.py / new ingester)                   (store.py:29, new oi table, store.py:14)
        ↓
LiquidationFlushAnalyst.analyze(symbol, provider)   (rapana/agents/liquidations.py)
        ↓  flush signature + completion gate
        ↓
Signal(source="positioning", bullish)  →  combine_signals / weighted_combine (signals.py:73,87)
        ↓
PortfolioManager  →  spot TradeProposal (buy, small size, stop attached)
[Live, KYB-gated only:]  → LiveExecutor → MexcClient (spot, authenticated)
```
\* OI ingest = new `oi` table in `store.py` + a `fetch_open_interest_history` wrapper on `MexcFuturesClient` (`04-data-edge.md:77`). This is the **only new data plumbing** required; everything else reuses the existing pipeline.

---

## 6. Validation gate (mandatory before any live sizing)

The edge is **un-backtestable today** — the store has `candles`, `funding`, `meta` only (`data/store.py:14,29,39`); there is no OI or liquidation table. This mirrors the `research/agents/14-mexc-orderbook.md:79` precondition. **Sequence:**

1. **Ingest OI history** to a new `store.py` table (weeks of collection, free, key-less) — `04-data-edge.md:77`.
2. **Write `backtest/liquidation_flush.py`** mirroring `funding_spike.py`: point-in-time firewall (decide from data *available* at `t`, never the current unclosed bar), split `gross_reversion` from cost, benchmark vs **CASH** (the overlay is flat unless a flush fires — same correct bar as `funding_spike.py:31-37`), and **PASS = Deflated Sharpe > 0.95 AND best OOS net beats cash** (`funding_spike.py:370`).
3. Only if it passes: flip `Signal.extras["validated"]=True` and raise `source_weights["positioning"]`.

Until then, the agent runs in **advisory/paper only** — it emits Signals that flow to the Bull/Bear debate as an *opinion* for a human to act on at the MEXC UI, with zero freeze risk (same C1/C2 research track as the funding fade, `12-mexc-funding.md:116`).

---

## 7. Risk caps — the falling-knife honesty section

This is the part that determines whether the edge survives contact with reality. Cascades **chain**: a flush is frequently followed by another flush the next session (Giagkiozis, delayed/misreported liquidations mean the "exhaustion" call can be premature). The structure must assume each trade *can* be a falling knife:

| Cap | Value | Why |
|---|---|---|
| **Risk/trade** | **≤1% of equity** (repo default, `03-risk-edge.md:19`) | falling-knife tail is real |
| **Position size** | ≤ `max_position_pct` = 10% (`03-risk-edge.md:15`); **cap at 2–3% until validated** | conviction-tiered, never full size on a hypothesis |
| **Hard stop** | `flush_low × (1−0.01..0.03)`; **mandatory, non-negotiable** | new low falsifies the thesis |
| **Time stop** | exit by 24–48h if neither target nor stop | failed reversion = information, not forced flow |
| **Concurrent flush trades** | **max 2**, and **not on correlated names** (no BTC+ETH+same-direction stack) | cascades are market-wide; one macro flush can hit all |
| **Veto (skip entry)** | (a) daily-loss breaker tripped (`03-risk-edge.md:19`); (b) macro regime risk-off / symbol in strong downtrend (cascade likely continues); (c) illiquid alt (wider falling knife); (d) flush already partially retraced >50% before entry (edge captured) | the highest-value action is often *not* trading |
| **No averaging down** | forbidden | a flush that keeps flushing is the exact scenario that blows up martingale sizing |
| **Daily-loss kill-switch** | inherited 3% (`03-risk-edge.md:19`) | the repo's breaker protects the sleeve even if 2–3 flushes chain |

**The honest expected-value framing:** this is **not** a high-win-rate strategy. It is an *asymmetric* one — many small, tightly-stopped losses (and some time-stops) paid for by partial-retrace wins that are ~2× the stop. If the §6 backtest cannot show a Deflated-Sharpe-passing OOS result under these exact caps and a conservative 8 bp taker round-trip, **the edge does not exist for this fleet and the agent is not enabled.**

---

## 8. Bottom line

- **Mechanism is sound and partly validated in-repo:** forced-liquidation cascades are transient *forced* flow whose exhaustion produces a snap-back; the *reversion* leg is the same edge the repo already trades profitably (`backtest/funding_spike.py` passes Deflated Sharpe), and the cascade-completion moment is its highest-conviction instance. Klages-Mundt & Minca (arXiv:2004.01304) formalize the spiral; Nimmagadda (1912.03270) and Kim & Park (2506.08573) underwrite the reversion leg.
- **Detectable for free, hourly, key-less:** the flush leaves a *4-feature signature* (drawdown + OI-collapse + funding-spike-then-normalize + volume/range spike) on data the fleet already has — funding (`client.py:195`) and candles (`store.py:14`) — plus OI, which is one ccxt line away (`04-data-edge.md:77`). The unreliable per-exchange *liquidation feed* is explicitly **not** load-bearing (Giagkiozis & Said, arXiv:2310.14973, show liquidation/OI reporting is delayed/misreported); the *combo* is.
- **The edge is asymmetric, not high-win-rate:** buy spot 2–4h after a long-flush, hard stop just below the flush low, target 30–70% retrace, time-stop 24–48h. Honest prior ~50–58% win rate net of cost — all the EV is in R:R and in *not trading* the ~40% that chain down.
- **Honest status: hypothesis-stage, spot-only, advisory until backtested.** No liquidation/OI history exists in the store today, so the edge is un-backtestable as-is. Mandatory sequence: ingest OI → write `backtest/liquidation_flush.py` (Deflated-Sharpe gate vs cash, mirroring `funding_spike.py`) → only then raise the Signal weight from 0.4 and flip `validated=True`. Until then it runs paper-only, human-executes on the UI, zero freeze risk — the same safe C1/C2 track as the funding fade.

# 31 — Academic Crypto Market-Microstructure Edges (2020–2026), OOS-Survival-Filtered

**Agent:** 31/60 · **Scope:** mine the peer-reviewed / arXiv / SSRN crypto-microstructure literature (2020–2026) for **non-standard** edges — order-flow imbalance, price-discovery lead/lag, stablecoin flow, on-chain settlement, wallet concentration, gas-fee regimes, MEV-adjacent — and filter for what *survived out-of-sample replication* and what a **low-freq, spot-only, post-only-maker, ≤1 order/symbol/60s, cancel-ratio ≤30%, no-arb/hedge** MEXC bot could actually capture.
**Stance:** read-only microstructure, no HFT, no arbitrage, no symmetric hedging (`research/agents/16-mexc-tos-envelope.md`). All repo citations are `file:line`; external claims are URL-cited.

**Verdict up front.** The literature is loud but the OOS-survival filter is brutal. Three things survive it for a slow spot bot, in priority order:
1. **Stablecoin (USDT) net inflow to exchanges → short-horizon *bullish* returns (1–6h)** — the only microstructure-family edge with intraday OOS academic support *and* a horizon long enough for the MEXC envelope (Chi & Hao 2024; corroborated Griffin & Shams 2020, Lyons & Viswanath-Natraj 2023). **Capturable.**
2. **Cross-venue price-discovery lead/lag (continuation)** — derivatives + the large perp venues *lead* MEXC spot on most pairs; the *direction* the leader moved persists into the next 5–15 min (Dimpfl & Peter 2021; Alexander et al. 2020; Plazuelo et al. 2025). **Capturable at the fast end of low-freq, mid/low-cap only**; majors are noise (fee- and decay-eaten).
3. **Order-flow toxicity (VPIN) as a tail-risk VETO** — sustained one-sided/toxic flow flags adverse selection; survives 14 years of cross-asset replication and transfers to crypto (Easley/O'Hara/Yang/Zhang 2026 *JFM*). **Capturable only as a read-only veto, never a trigger** — its alpha leg decays in seconds (same wall agent 14 hit with book imbalance).

Edges that **fail** the OOS/feasibility filter: raw tick-level OFI/imbalance (decays in seconds → HFT-only, ToS-hostile), wallet/whale concentration (literature finds *retail*, not whales, drives ETH returns — Chernoff & Jagtiani 2024), gas-fee regimes (the literature models gas *prices*, not gas→returns; no OOS return edge), MEV-adjacent (execution-layer; no clean read-only return predictor for a spot bot). Honest reasoning in §3.

---

## 1. The load-bearing cross-cutting finding: what OOS actually means in this literature

Across ~30 papers screened and 12 surveyed below, the crypto-microstructure "predictability" literature has a **two-camp split** that maps almost perfectly onto OOS survival:

- **Mechanism-grounded** edges survive OOS. "Stablecoins are moved to exchanges to buy crypto" (Chi & Hao 2024; Griffin & Shams 2020; Lyons & Viswanath-Natraj 2023), "derivatives/wholesale venues innovate and spot follows" (Dimpfl & Peter 2021; Alexander et al. 2020), and "one-sided/toxic flow precedes adverse selection" (Easley/O'Hara 2026). These are **structural** — the causality survives sample changes — even when effect sizes are modest.
- **Curve-fit / in-sample** edges do not. Several 2024–2025 ML papers report absurd numbers (e.g., Dubey & Enke 2025 claims an annualized return of **1,682.7% / Sharpe 6.47** from on-chain features — a textbook overfitting red flag, treat as non-replicable). Griffin & Shams (2020, *JF*) itself, while seminal, is **sample-specific to the 2017 Tether era** and heavily contested; its durable residue is the *directional* mechanism, not the magnitude.

**Implication for rapana:** reject any edge whose evidence is "we trained an ML model and the Sharpe is huge." Accept only edges with (a) a stated mechanism, (b) horizon **≫ minutes**, and (c) independent corroboration. The three below clear that bar.

---

## 2. Annotated paper survey (edge / horizon / OOS survival / fee-sensitivity / URL)

### A. Price discovery & lead/lag across venues

| # | Paper (venue, year) | Claimed edge | Horizon | OOS survival | Fee-sensitivity | URL |
|---|---|---|---|---|---|---|
| 1 | **Dimpfl & Peter** — *J. Financial Markets* (2021), "Nothing but noise? Price discovery across cryptocurrency exchanges" | Uses Putniņš (2013) **information-share** (noise-adjusted). **Bitfinex leads**; ranks each venue's price-discovery share. | seconds–minutes (1–5 min data) | **Leadership structure stable** 2017–19; the *who leads* is durable, the per-tick lead is not. | High as a *trade* (net edge dies after fees+taker at HF); the *direction* read is what's left at low-freq. | https://www.sciencedirect.com/science/article/pii/S1386418120300537 (SSRN 3565209) |
| 2 | **Alexander & Heck** — *J. Financial Stability* (2020), "Price discovery in Bitcoin: the impact of unregulated markets" | Unregulated venues (**Huobi, OKEx, BitMEX**) are the strongest discovery instruments; CME futures + US spot **lag**. | minutes | Robust across sample windows (cited 135×) | Net-tradeable only at HF; durable as a *leadership map*. | https://www.sciencedirect.com/science/article/pii/S1572308920300759 |
| 3 | **Alexander, Choi, Park, Sojak** — *J. Futures Markets* (2020), "BitMEX bitcoin derivatives: price discovery…" | BitMEX **perpetual derivatives lead** major BTC spot venues. | minutes | Consistent with #2 (cited 147×) | Same as #2 | https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.22050 |
| 4 | **Plazuelo Pascual, Tardon, Toro, Hernando** — arXiv:2506.08718 (2025), "Price Discovery in Cryptocurrency Markets" | Hasbrouck IS + Gonzalo-Granger + Hayashi-Yoshida. **CEX leads DEX** (Binance vs Uniswap v2); CME futures lead BTC spot but **mixed in high-vol** regimes. | event/minutes | Mechanism corroborated by #1–#3 | — | https://arxiv.org/abs/2506.08718 |

### B. Order-flow imbalance & flow toxicity (VPIN)

| # | Paper (venue, year) | Claimed edge | Horizon | OOS survival | Fee-sensitivity | URL |
|---|---|---|---|---|---|---|
| 5 | **Easley, O'Hara, Yang, Zhang** — *J. Financial Markets* (2026), "Microstructure and market dynamics in crypto markets" | **VPIN** (volume-synchronized probability of informed trading): when crypto order flow is **imbalanced**, returns "shift to one side" → toxic-flow predicts adverse moves. | **tick–second** | **Strongest OOS pedigree in the set:** VPIN has 14 yrs (2012–26) cross-asset replication; this *JFM* paper confirms it transfers to crypto. | Tradeable only at HF; **the sustained-toxicity *regime* survives latency** → veto use. | https://www.sciencedirect.com/science/article/pii/S1386418126000261 (SSRN 5337672) |
| 6 | **John, Li, Liu, Yang** (NYU Stern) — SSRN 5771502 (2025), "The Impact of Spoofing on Bitcoin Market Microstructure" | Order-book **imbalances predict BTC returns**; manipulative (spoofing) flow raises VPIN and distorts price. | tick–second | Independent corroboration of #5's mechanism | HF; veto only | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5771502 |

### C. Stablecoin / on-chain flow (the low-freq winner)

| # | Paper (venue, year) | Claimed edge | Horizon | OOS survival | Fee-sensitivity | URL |
|---|---|---|---|---|---|---|
| 7 | **Chi & Hao** — arXiv:2411.06327 (2024), "Return and Volatility Forecasting Using On-Chain Flows" | **USDT net inflow to exchanges → +predicts BTC & ETH returns at 1–6h** and lowers volatility; BTC-coin inflow → negative BTC returns. | **1–6h intraday** (best fit for the MEXC envelope) | 2017–23 sample, multiple horizons, intraday; the **only** microstructure-family paper with an OOS-tested *intraday* horizon a slow bot can use | **Low** — horizon is hours, not ticks; MEXC maker 0% (`09-mexc-maker-fee.md`) keeps round-trip ≈ 2–4 bp | https://arxiv.org/abs/2411.06327 |
| 8 | **Griffin & Shams** — *Journal of Finance* (2020), "Is Bitcoin really untethered?" | Tether flows "can largely explain Bitcoin prices" (seminal, cited 931×). | daily | **Sample-specific to 2017 Tether era**, contested; *directional* mechanism (stablecoin → market buying → strength) is the durable residue, corroborated by #7, #10, #11. | daily → low | https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12903 |
| 9 | **Grobys & Huynh** — *Finance Research Letters* (2022), "When tether says JUMP! bitcoin asks how low?" | **Daily:** +1% Tether return *prior day* → **negative** BTC next day (mean-reversion of the Tether-driven pump). | daily | Daily, peer-reviewed (cited 61×) | low | https://www.sciencedirect.com/science/article/pii/S1544612321005778 |
| 10 | **Lyons & Viswanath-Natraj** — *J. Int. Money & Finance* (2023), "What keeps stablecoins stable?" | Treasury↔investor trades govern the peg; quantifies how arbitrage restores $1. | minutes–daily | Robust (cited 439×); defines the *mechanism* a flow signal rests on | — | https://www.sciencedirect.com/science/article/pii/S0261560622001802 |
| 11 | **Mizrach** — arXiv:2201.01392 (2022), "Stablecoins: survivorship, transactions costs and exchange microstructure" | Studies Tether/USDC/Dai microstructure; corroborates the Tether→BTC linkage of #8. | intraday | corroborating | — | https://arxiv.org/abs/2201.01392 |

### D. Also-rans surveyed and explicitly rejected (honesty)

| # | Paper | Why it does **not** make the cut |
|---|---|---|
| 12 | **Chernoff & Jagtiani** — SSRN 4924078 (2024), "Beneath the crypto currents: the hidden effect of crypto whales" | ETH returns appear **driven by small retail, not whales** → wallet concentration is a *weak/noisy* return predictor. Downgrades the "whale-concentration" edge. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4924078 |
| 13 | **Koutmos** — *JRFM* (2023), "Network activity and ethereum gas prices" | Models **gas prices from network activity**, not gas→*returns*; the gas-fee-regime-as-return-edge is **unsupported OOS**. https://www.mdpi.com/1911-8074/16/10/431 |
| 14 | **Dubey & Enke** — *ML with Applications* (2025), "Bitcoin price direction prediction using on-chain data" | Claims Sharpe **6.47 / +1,682%** — an **implausible overfit** red flag; excluded as non-replicable. https://www.sciencedirect.com/science/article/pii/S266682702500057X |
| — | MEV-adjacent (e.g., flashbots/sandwich literature) | Execution-layer; produces **no clean read-only return predictor** a spot bot can monetize — it's about *being* the extractor, not reading it. Out of scope for a low-freq spot-only fleet. |

---

## 3. Top-3 ranked by edge-strength × feasibility × OOS-durability

### Ranking table

| Rank | Edge | Edge strength | MEXC-envelope feasibility | OOS durability | Net |
|---|---|---|---|---|---|
| **1** | Stablecoin→exchange inflow (bullish, 1–6h) | moderate | **high** (hours horizon ≫ envelope; read-only on-chain) | moderate–high (mechanism corroborated ×3) | **best** |
| **2** | Cross-venue lead/lag (continuation, 5–15 min) | strong but fast | moderate (only the fast end of low-freq; mid/low-cap) | high (leadership structure stable 2015–25) | strong |
| **3** | VPIN flow-toxicity (tail-risk veto) | strong as veto, weak as α | **high** (read-only veto, no order churn) | **highest** (14-yr cross-asset replication) | strong risk-control |

All three share one hard prerequisite with agent 14: **the supporting data does not exist in the repo yet** (no trades table, no on-chain feed, no multi-venue reader, no book history — `store.py:14,29,39` holds only candles/funding/meta). Each must run a **collection-first** phase before touching live sizing, exactly as agent 14 prescribed for depth.

---

### #1 — Stablecoin (USDT) net inflow to exchanges → short-horizon bullish

**Mechanism (why it survives OOS).** Stablecoins are moved to an exchange for essentially one purpose — to buy crypto. A net USDT *inflow to exchanges* is therefore the physical arrival of purchasing power ("dry powder"), and Chi & Hao (2024) show it **positively predicts BTC/ETH returns at 1–6h** and dampens volatility. The signal is the *cleanest* of the on-chain family precisely because intent is constrained (a BTC inflow could be custody/OTC/sale; a USDT inflow is almost always a buy). Corroborated structurally by Lyons & Viswanath-Natraj (2023) and — at daily horizon — Griffin & Shams (2020).

**Feasibility under the MEXC envelope.** **Fully capturable.** Horizon is hours; rapana rebalances daily (`config.py:77`, `rebalance_bars=24`) and the 15–60 min on-chain data latency (Glassnode BTC median ~22 min, agent 27 §c) is *trivially* absorbed. No HFT, no second leg, no order churn — one slow maker buy when the signal aligns. It is a **bullish entry/veto modifier**, regime-conditioned: strongest when stablecoin inflow coincides with an existing bullish market/sentiment read.

**Distinct from agent 27.** Agent 27 covers *whale coin-inflow* as a **risk-off** (bearish) signal. This is the **mirror, academically the strongest leg**: stablecoin-inflow as **bullish dry powder**, at the intraday horizon agent 27 deferred. Route it the same way — through the existing `MacroAnalyst` + `source="macro"` — so it reinforces (not double-counts) the macro bucket.

**Signal spec — `stablecoin_macro_fn` injected into `MacroAnalyst` (`rapana/agents/macro.py:23-30`)**

```python
# rapana/feeds/onchain.py — stablecoin-flow leg (complements agent 27's FlowSnapshot)
@dataclass(frozen=True)
class StablecoinFlow:
    usdt_inflow_exchange_usd: float   # +ve = stablecoins arriving at exchanges = buying power
    spike_zscore: float              # anomaly vs trailing N-day baseline
    ts: int

def stablecoin_macro_fn(flow: StablecoinFlow | None, regime: str) -> tuple[float, float]:
    # Returns (strength[-1..1], confidence[0..1]) for MacroAnalyst.analyze (macro.py:29).
    if flow is None or flow.ts < (now_ms() - 2 * 3600_000):
        return 0.0, 0.0                                      # stale/missing -> neutral, zero weight
    if flow.usdt_inflow_exchange_usd <= 0 or flow.spike_zscore < 1.0:
        return 0.0, 0.0                                      # no anomalous buying-power arrival
    severity = min(1.0, (flow.spike_zscore - 1.0) / 3.0)     # 0..1 over z=1..4
    s = +0.5 * severity                                      # bullish: dry powder staged to buy
    # confidence is the lever that makes this a modifier, not a driver (signals.py:73-84).
    # stronger when the market regime is already constructive; muted in risk-off.
    c = {"bull": 0.45, "range": 0.38, "bear": 0.20, "risk-off": 0.12}.get(regime, 0.25)
    return clamp(s, -1, 1), c
```
Emitted (via `MacroAnalyst.analyze`, `macro.py:30` → `Signal(symbol, "macro", "bullish", s, c, …)`):
```jsonc
{ "symbol": "BTC/USDT", "source": "macro", "direction": "bullish",
  "strength": 0.18, "confidence": 0.45,
  "rationale": "on-chain: 2.3σ USDT exchange inflow spike; regime=bull",
  "extras": { "subsource": "onchain.stableflow", "spike_z": 2.3,
              "usdt_inflow_usd": 410000000, "horizon_h": 4, "regime": "bull" } }
```
- **Confidence capped ~0.45** so `combine_signals` (`signals.py:73-84`) treats it as a *conviction modifier*: it tips consensus only when market/sentiment signals are weak or aligned — never single-handedly.
- **Data path:** ship `WhaleAlertArchiveFeed` (free, backtest) → `EtherscanSelfBuiltFeed` (free, live, EVM-only) → `$29.95/mo` Whale Alert only if the OOS edge survives (full cost/latency analysis in `research/agents/27-whale-onchain.md:48-71`). **Validate before paying.**
- **Envelope discipline:** influences the *next* daily rebalance, never a tick-reactive order — the 15–60 min data floor + spot-only/low-freq envelope make tick-trading both impossible and ToS-hostile.

---

### #2 — Cross-venue price-discovery lead/lag (continuation, 5–15 min)

**Mechanism (why it survives OOS).** Crypto price discovery is **hierarchical and stable**: perpetual-derivative venues and the deepest spot venues (Binance; historically Bitfinex/BitMEX/OKEx) *innovate*, and thinner spot venues — including MEXC on most pairs — *follow* over minutes (Dimpfl & Peter 2021; Alexander & Heck 2020; Alexander et al. 2020; Plazuelo et al. 2025). The *direction* of leadership is the durable part; the per-tick lead decays fast.

**Distinct from agent 18 (this is the key non-duplication).** Agent 18 fades the MEXC *premium/discount* — a **level** deviation that **mean-reverts**. This edge is the **opposite sign and a different object**: it reads the leader venue's recent **return** and bets MEXC **catches up** (continuation/momentum), not reversion. They can coexist and even cooperate: lead/lag gives the *direction* of the next move; agent 18 gives a *timing/reversion* filter. Because the mechanism is different, it gets **its own learnable `source`** so the reflection loop credits them independently.

**Feasibility under the MEXC envelope — conditional.** **Capturable only at the fast end of low-freq (5–15 min) and only on mid/low-cap pairs where MEXC depth lags** (on majors BTC/ETH/SOL the lead is sub-second and fee-eaten — agent 18's point). The read is pure public-ticker polling (no second leg, no arb — `16-mexc-tos-envelope.md`): Binance is the documented "fair value"/leader (Liu 2025, cited in agent 18), with the perp as the leading instrument.

**Signal spec — new `PriceDiscoveryAnalyst`, new `source="microstructure"`**

```python
# rapana/agents/price_discovery.py  (mirror agents/arbitrage.py; reuse agent 18's multi-venue reader)
class PriceDiscoveryAnalyst(Analyst):
    role = "price_discovery"
    LEADER = "binance"                 # documented price leader (Liu 2025, agent 18)
    LOOKBACK_MIN = 15                  # leader return window; decay kills anything much longer
    THRESH_BPS = 25                    # |leader 15-min move| must clear this to emit (fee gate)
    def analyze(self, symbol, provider) -> Signal:
        leader_ret = provider.venue_return(symbol, self.LEADER, self.LOOKBACK_MIN)  # new getter
        mexc_ret   = provider.venue_return(symbol, "mexc", self.LOOKBACK_MIN)
        if leader_ret is None or mexc_ret is None:
            return neutral(symbol, "no multi-venue price")
        lag = leader_ret - mexc_ret                          # >0: leader up more than MEXC (MEXC catch-up long)
        if abs(leader_ret) < (self.THRESH_BPS / 1e4):
            return neutral(symbol, "leader move sub-threshold")   # fee/decay gate
        direction = "bullish" if lag > 0 else "bearish" if lag < 0 else "neutral"
        strength = clamp(lag * k, -1, 1)                     # scale with catch-up gap
        return Signal(symbol, "microstructure", direction, strength,
                      confidence=0.30,                       # capped: continuation is noisier than reversion
                      rationale=f"leader {self.LEADER} led by {lag*1e4:.0f}bp over {self.LOOKBACK_MIN}min",
                      extras={"leader": self.LEADER, "leader_ret": leader_ret,
                              "mexc_ret": mexc_ret, "lag_bps": lag*1e4,
                              "mechanism": "continuation", "scope": "mid/low-cap only"})
```
- **`source="microstructure"`** is a **new bucket** vs agent 18's `"global_ref"` — essential so `ReflectionMemory` (`fleet/memory.py:114-121`) learns continuation and reversion **separately** (a single bucket would let one mechanism's failures penalize the other). Default `source_weights["microstructure"] ≈ 0.6` until forward-validated.
- **Scope guard:** emit only for mid/low-cap pairs (where MEXC lags); emit **neutral** for majors. Hard-code the exclusion — the academic evidence says the lead is sub-second on BTC/ETH and not capturable.
- **Reuses agent 18's infrastructure:** the multi-venue CCXT reader (`binance/okx` `fetchTicker`, keyless) that agent 18 already proposed (`research/agents/18-mexc-premium.md:112-129`); add `venue_return(symbol, venue, mins)` to `DataProvider` (`fleet/data_provider.py:13`).
- **Envelope hygiene:** read public tickers, place one maker leg on MEXC, ≤1 order/symbol/60s — identical footprint to agent 18, which is ToS-cleared. **No second leg.**

---

### #3 — Order-flow toxicity (VPIN) as a read-only tail-risk VETO

**Mechanism (why it survives OOS).** VPIN buckets the trade tape into equal-volume bins, classifies each bin buy- vs sell-side, and measures `Σ|buy−sell|/total`. Sustained **one-sided/toxic flow** signals informed trading and forecasts **adverse selection / violent moves**. It has the **longest OOS pedigree in the entire set** — 14 years across asset classes — and Easley, O'Hara, Yang & Zhang (2026, *JFM*) confirm it transfers to crypto ("when crypto order flow is imbalanced, returns shift to one side"). John et al. (2025) add that spoofing inflates VPIN, i.e. toxic-flow regimes are exactly when maker entries get run over.

**Feasibility under the MEXC envelope — veto only.** The *directional* alpha leg decays in **seconds** (same wall agent 14 hit with book imbalance); a REST-polling, freeze-safe bot **cannot** trade it as a trigger. But the **toxicity regime** (sustained VPIN elevation over tens of minutes) survives latency and is a **pure read-only veto**: when VPIN is in its high regime, *decline* the intended entry (sidestep adverse selection) — exactly agent 14's wide-spread veto pattern, now applied to the *trade tape* instead of the *book*.

**Distinct from agent 14.** Agent 14 reads **static book pressure** (bid/ask depth) and explicitly leaves OFI/toxicity to a separate pass. This reads the **trade tape** (executed flow), which is the information book pressure only *implies*. They are complementary vetoes: book says "makers are one-sided"; VPIN says "informed flow is actually printing."

**Signal spec — new `FlowToxicityAnalyst`, veto via `source="market"`**

```python
# rapana/agents/flow_toxicity.py — read-only VPIN veto (mirror agent 14's DepthAnalyst)
class FlowToxicityAnalyst(Analyst):
    role = "flow_toxicity"
    NBINS = 50                        # volume buckets per VPIN window
    LOOKBACK_TRADES = 1000            # recent trades to build the window
    VETO_PCTILE = 0.90                # top-10% toxicity regime -> veto new entries
    def analyze(self, symbol, provider) -> Signal:
        trades = provider.recent_trades(symbol, self.LOOKBACK_TRADES)   # NEW; needs fetch_trades
        if not trades or len(trades) < self.NBINS * 4:
            return neutral(symbol, "insufficient trade history")
        vpin = compute_vpin(trades, self.NBINS)              # Easley/López de Prado/O'Hara
        pctile = vpin_percentile(symbol, vpin)               # vs per-symbol rolling history
        if pctile >= self.VETO_PCTILE:
            # VETO: high adverse-selection regime -> decline entries (never a short; spot-only)
            return Signal(symbol, "market", "neutral", 0.0, 0.0,
                          "VPIN veto: toxic-flow regime",
                          extras={"veto": True, "vpin": vpin, "pctile": pctile})
        # Non-veto: gentle modulator only (alpha leg decayed; do not use as a trigger).
        mod = clamp((pctile - 0.5) * 0.4, -0.2, 0.2)
        return Signal(symbol, "market", "bullish" if mod >= 0 else "bearish", mod,
                      confidence=0.12,                     # deliberately low — modulator, not alpha (agent 14 pattern)
                      rationale=f"VPIN regime pctile={pctile:.2f}",
                      extras={"vpin": vpin, "pctile": pctile})
```
- **`compute_vpin`** uses Lee–Ready tick classification on the trade tape; the **regime** (rolling percentile) is the part that survives latency. Standard reference implementation; no exotic data.
- **`source="market"`** + `extras={"veto": True}` mirrors agent 14's veto mechanism; a veto is a `direction="neutral"` signal that the PM/executor interprets as "stand aside." Zero cost — it declines trades.
- **New plumbing required (collection-first):** add `fetch_trades(symbol, limit)` to `MexcClient` (ccxt exposes it; **absent today** — `client.py:31-155` has tickers/ohlcv/book but **no trades**) and a `trades` table to `store.py` (beside `funding`, `store.py:29`). **Ingest history for weeks and forward-validate the veto before letting it gate live entries** — identical discipline to agent 14's book table.
- **Cadence:** one `fetch_trades` GET per symbol per cycle, cycle ≥ 5–15 min, jittered; far under MEXC's 300/10s IP weight budget (`client.py:13`). **No websocket.**

---

## 4. What a low-freq MEXC bot must *not* do with this literature (envelope discipline)

- **No latency-alpha.** Raw OFI/imbalance and the tick-level lead/lag are **seconds-scale** (papers #1, #5, #6). Acting on them requires the exact HFT/arb fingerprint MEXC freezes (`16-mexc-tos-envelope.md`). Use only the *regime/persistent* residue (veto, or the 5–15 min continuation tail).
- **No second leg.** Lead/lag (#2) and the stablecoin edge (#1) are **single-leg on MEXC**. Reading Binance/OKX/on-chain is *public data*, not trading there — the banned pattern is the correlated multi-leg execution, which we never do (agent 18 §c).
- **No majors for lead/lag.** The discovery lead on BTC/ETH is sub-second and fee-eaten; agent 18's premium-reversion is the better tool there. Reserve #2 for mid/low-cap.
- **No raw bp thresholds imported from equities.** Crypto microstructure differs (thinner books, slower maker refresh, 24/7) — threshold via per-symbol **rolling z/percentile**, not absolutes (same lesson as agent 29).
- **Ingest before trading.** All three need data infrastructure that doesn't exist (`store.py:14,29,39` holds only candles/funding/meta). Run a collection phase and clear the repo's walk-forward / Deflated-Sharpe gate (`git log 9a6fbf9`, `backtest/funding_spike.py:370`) before any live sizing.

---

## 5. Cited files (rapana)
- `rapana/agents/macro.py:13-31` — `MacroAnalyst` + `macro_fn` injection → **integration site for edge #1** (stablecoin flow).
- `rapana/feeds/base.py:6-20` — `Feed.score(symbol)->(score,conf)` ABC, fail-soft → shape for the stablecoin feed.
- `rapana/feeds/market_premium.py:20-66` — premium feed (agent 18's CoinGecko base); **upgrade target** to multi-venue CCXT reader shared with edge #2.
- `rapana/signals.py:17-46` (`source` enum :21, `__post_init__` sign-correction :27-41) / `:73-84` (`combine_signals`) / `:87-104` (`weighted_combine`) — why capped `confidence` = modifier-not-primary.
- `rapana/fleet/memory.py:114-121` — `ReflectionMemory.weight` is **per-`source`** → justifies a new `source="microstructure"` bucket for edge #2 (separate from `"global_ref"`).
- `rapana/mexc/client.py:58,62,136` — ticker/ohlcv/book getters exist; **no `fetch_trades`** → edge #3 needs a new wrapper. `:171-256` read-only `MexcFuturesClient` (funding).
- `rapana/data/store.py:14,29,39` — candles/funding/meta only; edges #2/#3 need new `trades`/multi-venue tables; edge #1 needs an on-chain feed (agent 27).
- `rapana/config.py:77` — `rebalance_bars=24` (daily) is the cadence edges #1–#3 overlay; their horizons (1–6h, 5–15min, veto) all fit inside or act on the next rebalance.
- Cross-refs: `research/agents/14-mexc-orderbook.md` (book-imbalance veto, OOS discipline), `18-mexc-premium.md` (multi-venue reader, ToS clearance, the level-reversion complement to #2), `27-whale-onchain.md` (on-chain feeds, latency, the risk-off mirror of #1), `29-funding-crossvenue.md` (rolling-z thresholding, per-source learning), `16-mexc-tos-envelope.md` (anti-bot envelope).

## 6. Sources (verified, load-bearing)
- Chi & Hao (2024), on-chain flows → BTC/ETH returns 1–6h: https://arxiv.org/abs/2411.06327
- Griffin & Shams (2020), *JF* "Is Bitcoin really untethered?": https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12903
- Lyons & Viswanath-Natraj (2023), stablecoin stability mechanics: https://www.sciencedirect.com/science/article/pii/S0261560622001802
- Grobys & Huynh (2022), Tether→BTC daily reversion: https://www.sciencedirect.com/science/article/pii/S1544612321005778
- Mizrach (2022), stablecoin microstructure: https://arxiv.org/abs/2201.01392
- Easley, O'Hara, Yang, Zhang (2026), *JFM* "Microstructure and market dynamics in crypto markets" (VPIN): https://www.sciencedirect.com/science/article/pii/S1386418126000261 (SSRN 5337672)
- John, Li, Liu, Yang (2025), spoofing & BTC microstructure: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5771502
- Dimpfl & Peter (2021), *JFM* price discovery across exchanges: https://www.sciencedirect.com/science/article/pii/S1386418120300537 (SSRN 3565209)
- Alexander & Heck (2020), *J. Financial Stability* price discovery: https://www.sciencedirect.com/science/article/pii/S1572308920300759
- Alexander, Choi, Park, Sojak (2020), *J. Futures Markets* BitMEX: https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.22050
- Plazuelo Pascual et al. (2025), price discovery CEX/DEX/CME: https://arxiv.org/abs/2506.08718
- Rejected: Chernoff & Jagtiani (2024, whale/retail) https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4924078 · Koutmos (2023, gas prices) https://www.mdpi.com/1911-8074/16/10/431 · Dubey & Enke (2025, overfit Sharpe 6.47) https://www.sciencedirect.com/science/article/pii/S266682702500057X

---

## Bottom line

Surveyed 12 crypto-microstructure papers (2020–26). The OOS filter kills raw OFI/tick-imbalance and lead/lag-as-trigger (seconds-scale, HFT/ToS-hostile), wallet-concentration (retail, not whales, drives returns), gas-fee regimes, and MEV (execution-layer). **Top-3 capturable by a low-freq spot MEXC bot:** (1) **USDT net inflow→exchange = bullish at 1–6h** (Chi & Hao 2024) — route via existing `MacroAnalyst`, `source="macro"`, capped confidence ~0.45; (2) **cross-venue lead/lag continuation** at 5–15 min on mid/low-cap (Dimpfl/Alexander) — new `PriceDiscoveryAnalyst`, new `source="microstructure"` so it learns separately from agent 18's reversion; (3) **VPIN toxicity as a read-only veto** (Easley/O'Hara 2026 *JFM*) — needs a new `fetch_trades`+`trades` table, ingest-first, veto-only. All three need collection-first infrastructure and must clear the repo's Deflated-Sharpe gate before live sizing.

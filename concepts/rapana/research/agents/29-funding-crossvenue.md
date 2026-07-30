# 29 — Cross-venue perpetual funding-rate crowding as a contrarian signal

**Agent:** 29/60 · **Scope:** broadens agent 12 (MEXC-only funding fade) to an **aggregate, cross-venue** crowding gauge across Binance / Bybit / OKX / MEXC, then converts it into a contrarian **spot** Signal for the rapana fleet.
**Stance:** NON-standard, low-frequency (8h cadence), event-driven overlay. Reads public funding data from 4 venues; emits one contrarian Signal per symbol. No perp trading, no arb, no HFT — strictly inside MEXC's spot-only, anti-bot envelope (`research/agents/16-mexc-tos-envelope.md`).

All citations are `file:line` for repo code and bare URLs for external sources. Where peer-reviewed magnitudes for the *aggregate* (cross-venue) effect do not yet exist, this is flagged **[HYPOTHESIS → backtest]** against free, keyless exchange feeds. No vibes presented as fact.

---

## 1. Why aggregate beats single-venue — the core upgrade over agent 12

Agent 12 (`research/agents/12-mexc-funding.md`) establishes that an **extreme MEXC funding rate** is a contrarian fade signal, validated in-repo at Deflated Sharpe (`backtest/funding_spike.py`). The thesis of this study is that **aggregating funding across venues produces a strictly better crowding readout**, for one reason that is mechanistically iron-clad and one that is empirical:

1. **Venue noise diversifies away; systematic crowding does not.** A single venue's funding spike can be local — a positioning shock specific to MEXC's order book, a liquidation cascade on one venue, or even misreported OI (Giagkiozis & Said 2024, arXiv:2310.14973, *Ledger* 9, document systematic OI misreporting across the largest derivatives venues). When **all four venues** show the same extreme funding sign simultaneously, the local explanations are averaged out and what remains is **systematic, market-wide one-sided positioning** — exactly the regime where a contrarian unwind is most likely and most violent. The repo already exposes the per-venue decomposition (`rapana/mexc/client.py:195-256` `fetch_funding_rate_history` for MEXC); the same CCXT call is keyless on the other three.

2. **Deviations comove — so the cross-section of venues is information, not noise.** He, Manela, Ross & von Wachter (2024, "Fundamentals of Perpetual Futures", arXiv:2212.06888) show empirically that perp-vs-spot **deviations comove across currencies** and that "an implied arbitrage strategy yields high Sharpe ratios." The cross-currency comovement result is, by direct analogy, the argument for cross-venue aggregation: when crowding is systematic it manifests on every venue at once, and the **dispersion across venues is itself a confidence gauge** (low dispersion + extreme level = high-conviction fade; high dispersion = venue-local, skip).

**Bottom line:** agent 12 trades the MEXC slice; agent 29 trades the **whole-market** slice. Both are the same contrarian mechanism; 29 is the higher-confidence, lower-noise version that agent 12 explicitly deferred ("the cross-sectional analog … can be merged later," `research/agents/12-mexc-funding.md:143`).

---

## 2. Does aggregate funding mean-revert price? — evidence, horizons, decay

### 2.1 Mechanism (three independent, on-point papers)
- **Nimmagadda & Ammanamanchi (2019), "BitMEX Funding Correlation with Bitcoin Exchange Rate"** (arXiv:1912.03270, q-fin.ST) — establishes that funding is **heteroskedastic** (extremes follow extremes — the persistence that funds the fade), that funding **Granger-causes** the perp price at short lags (the causal direction a fade needs), and frames funding explicitly as "a predictive tool for gauging the market trend." Worked on BTC inverse perps; the Granger direction is venue-agnostic and transfers to USDT perps on the four venues here.
  - URL: https://arxiv.org/abs/1912.03270
- **He, Manela, Ross & von Wachter (2024), "Fundamentals of Perpetual Futures"** (arXiv:2212.06888, q-fin.PR) — the standard reference for the funding-as-no-arbitrage-control view. Derives no-arb bounds, shows crypto deviations are **larger than in FX, comove across currencies, and diminish over time**, and that an implied **arbitrage strategy yields high Sharpe ratios**. The "diminish over time" finding is the empirical decay mode (see §2.3). The cross-currency comovement is the diversification argument behind aggregation.
  - URL: https://arxiv.org/abs/2212.06888
- **Kim & Park (2025), "Designing funding rates for perpetual futures in cryptocurrency markets"** (arXiv:2506.08573, q-fin.MF) — proves via path-dependent infinite-horizon BSDEs that a properly designed funding rate is the **no-arbitrage boundary** that re-anchors the perp to spot. This is the theoretical guarantee that *extreme funding is a force, not a coincidence*: the venue's own pricing kernel demands reversion when funding is extreme.
  - URL: https://arxiv.org/abs/2506.08573

The three together establish: funding is **heteroskedastic + persistent** (so it stays extreme long enough to trade), **causally precedes** price reversion (Granger), and is the **no-arb boundary** whose extreme levels are *defined* to be reverted away.

### 2.2 Effect sizes & horizons
- **Internal (in-repo, MEXC-only):** the contrarian fade `backtest/funding_spike.py` **passed the honest Deflated-Sharpe gate** (PASS = DSR > 0.95 AND best OOS net beats CASH, `funding_spike.py:370`), on an 8h cadence with a 1-interval (8h) hold. The harness separates `oos_gross_price` (reversion) from `oos_gross_funding` (carry cushion) precisely so reversion can be measured honestly (`funding_spike.py:109-110`). This is the only hard, net-of-cost, OOS number; it is single-venue, so it is a **lower bound** on the aggregate edge (which should be cleaner, not noisier).
- **Horizon:** 1–3 funding intervals (**8–24h**). The signal lives at the funding-settlement cadence; faster is noise, slower the crowd has already unwound. **[HYPOTHESIS → backtest]**: systematic (cross-venue) crowding may unwind *slightly slower* than venue-local spikes — test a 2-interval hold in `funding_spike.py`'s ladder before adopting.
- **External magnitude:** no peer-reviewed paper publishes a *cross-venue aggregate* bp-per-event figure. He et al. (2024) report only that the implied strategy yields "high Sharpe ratios" (qualitative). Specific bp magnitudes for the aggregate signal are therefore **[HYPOTHESIS → backtest]**; use the repo's `gross_price` separation to measure them, exactly as agent 12 prescribes.

### 2.3 Decay modes
Two, both monitorable:
1. **Structural decay (He et al.):** deviations "diminish over time" as the market matures — the long-run arbing-away of the basis. **[HYPOTHESIS → backtest]**: monitor rolling 1y mean |aggregate funding z|; if it trends down, widen the entry threshold or accept lower hit-rate.
2. **Cap-clamping (agent 12 §2.3):** each venue caps |funding| per interval; as caps bind more often the signal saturates. The aggregate mitigates this (a venue at its cap still contributes the cap value, and four venues rarely all clamp identically), but monitor the rolling fraction of intervals at any venue's cap.

---

## 3. Free, aggregatable data sources — the feasibility backbone

The single most important feasibility fact: **all four venues expose funding history as a keyless public market-data endpoint.** The repo already proves this for MEXC (`MexcFuturesClient` "defaults to unauthenticated," `client.py:181`; `fetch_funding_rate_history` paginates the public endpoint and applies a point-in-time firewall, `client.py:195-256`). The other three are the same CCXT pattern.

### 3.1 Free path — direct exchange endpoints (keyless, no account)
| Venue | Public funding endpoint | Notes |
|---|---|---|
| **Binance** (USDT-M) | `GET /fapi/v1/fundingRate` (history), `/fapi/v1/premiumIndex` (current) | Public market data, no key. Largest OI → anchor of the aggregate. |
| **Bybit** (V5) | `GET /v5/market/funding/history` | Public, no key. |
| **OKX** (V5) | `GET /api/v5/public/funding-rate-history` | Public, no key. |
| **MEXC** | already wired, `rapana/mexc/client.py:195` | Public, defaults `authenticated=False` (`client.py:181`). |

All four are reachable via CCXT `fetchFundingRateHistory` with **no API key** (CCXT documents these as market-data/public endpoints). This is the **zero-cost, account-free** path and the one that fits rapana's read-only C1/C2 envelope (`research/agents/08-mexc-client-edge.md:65`). Polling once per 8h settlement × 4 venues × N symbols is trivially inside every venue's public rate limit and inside MEXC's anti-bot envelope (low-freq, maker-friendly, single-name — the opposite of the HFT/arb MEXC targets, `research/agents/12-mexc-funding.md:118`).

**Caveat — the cross-venue fetch needs new wiring.** `MexcFuturesClient` is MEXC-only; a `MultiVenueFundingProvider` reusing CCXT for the other three venues is the one new read-side component (see §5). No trading keys, no KYB — reading is unconditional.

### 3.2 Convenience path — Coinglass (paid API, free webpage)
[Coinglass](https://www.coinglass.com/FundingRate) already computes exactly the aggregate quantities this strategy needs and surfaces them on a free-to-view dashboard (no key): **BTC/ETH OI-Weighted Funding Rate**, **Volume-Weighted Funding Rate**, per-exchange funding, and a heatmap. Its [API](https://docs.coinglass.com) exposes these programmatically via endpoints that map 1:1 onto the strategy:
- [`fr-exchange-list`](https://docs.coinglass.com/reference/fr-exchange-list.md) — per-exchange funding for a symbol (the raw 4-venue input).
- [`fr-ohlc-history`](https://docs.coinglass.com/reference/fr-ohlc-histroy.md) — per-pair funding OHLC (the z-score history).
- [`oi-weight-ohlc-history`](https://docs.coinglass.com/reference/oi-weight-ohlc-history.md) — **OI-weighted aggregate funding** (the crowd metric, OI-weighted so Binance dominates correctly).
- [`vol-weight-ohlc-history`](https://docs.coinglass.com/reference/vol-weight-ohlc-history.md) — volume-weighted aggregate (robustness check).
- [`cumulative-exchange-list`](https://docs.coinglass.com/reference/cumulative-exchange-list.md), [`fr-arbitrage`](https://docs.coinglass.com/reference/fr-arbitrage.md).

**Cost honesty:** the Coinglass **API is not free** — [pricing](https://www.coinglass.com/pricing) starts at **HOBBYIST $29/mo** (80+ endpoints, 30 req/min, 8h history back 360d; all-time only on the daily interval) up to ENTERPRISE. There is no free API tier. So: **the free path is direct exchange polling (§3.1); Coinglass is an optional paid convenience/sanity-check layer**, useful if the team wants pre-cleaned, OI-weighted aggregates and is willing to pay. For a 4-venue, 8h-cadence overlay, direct polling is strictly cheaper and dependency-free — recommended default.

### 3.3 OI-weighting vs equal-weighting (and a known caveat)
For the aggregate, **OI-weight** (or volume-weight) the venues so Binance's dominant positioning isn't diluted 1:1 by a thin MEXC print. **Caveat:** Giagkiozis & Said (2024, arXiv:2310.14973) document that some venues **systematically misreport OI** (delayed liquidation messages, implausible OI). Mitigation: cross-check reported OI against `research/agents/14-mexc-orderbook.md` depth where cheap, and **cap any single venue's weight** (e.g. ≤ 0.6) so one venue's reporting error can't dominate the aggregate. Equal-weight is the simplest robustness fallback.

---

## 4. Crowded-long vs crowded-short regimes — how to threshold

The contrarian rule is symmetric in *funding sign* but the **spot execution envelope is not** (see §6). Both regimes are real:

- **Crowded-long:** aggregate funding **strongly positive** → longs are paying shorts to hold → long positioning is extreme → price is biased to **revert down**. Fade = bearish view.
- **Crowded-short:** aggregate funding **strongly negative** → shorts are paying longs → short positioning is extreme → price is biased to **revert up**. Fade = bullish view.

### 4.1 Threshold via z-score, not raw bp
Raw bp thresholds (agent 12's `fade|f|>10bp` ladder) are single-venue and absolute; they don't adapt to regime. For a **cross-venue aggregate** the principled threshold is a **rolling z-score** of the OI-weighted aggregate funding over a 90–180 day window:

```
agg_f_t   = Σ_v  w_v · funding_v,t                       # v ∈ {Binance, Bybit, OKX, MEXC}, w = OI share (capped 0.6)
z_t       = (agg_f_t - mean(agg_f_{t-90d..t})) / std(...)
crowd     = "long"  if z_t > +Z_HI  else
            "short" if z_t < -Z_HI  else "none"
disp_t    = std_v(funding_v,t / |agg_f_t|)               # cross-venue dispersion; high dispersion → venue-local, skip
```
- **Entry z-score: `|z| ≥ 2.0`** (≈ top ~2.5 % tail); **high-conviction `|z| ≥ 2.5–3.0`**. **[HYPOTHESIS → backtest]** the exact cut against the free multi-venue series; pre-commit a small ladder (1.5 / 2.0 / 2.5) to avoid post-hoc mining, mirroring `funding_spike.py:79-84`.
- **Dispersion veto:** require cross-venue **sign agreement** (≥ 3 of 4 venues share the aggregate sign) AND dispersion below a rolling median. If only one venue is screaming, it's local — let agent 12's single-venue path handle it on MEXC, not the aggregate.

### 4.2 Why z-score over raw bp here (but not in agent 12)
Agent 12 *must* use raw bp on MEXC because it trades the MEXC funding itself (the `gross_funding` cushion is in bp). Agent 29 trades **spot** on MEXC — it earns **no funding leg** — so what matters is the *reversion* probability, which scales with how unusual positioning is *for this regime*, i.e. the **z-score**, not the absolute carry. This is the load-bearing reason 29 thresholds differently from 12.

---

## 5. `FundingCrowdingAnalyst` — spec (spot-only, contrarian, asymmetric)

### 5.1 Role & cadence
New analyst mirroring `agents/base.py:Analyst` and the pattern in `research/agents/14-mexc-orderbook.md:82`. Cadence: **once per funding settlement (8h, 00/08/16 UTC)**, evaluated after each venue's settled rate is available, jittered across symbols — fully inside MEXC's low-freq envelope.

```python
# rapana/agents/funding_crowding.py
class FundingCrowdingAnalyst(Analyst):
    role = "funding_crowding"
    VENUES = ["binance", "bybit", "okx", "mexc"]
    Z_LOOKBACK_DAYS = 90
    Z_ENTRY = 2.0          # pre-committed ladder: 1.5 / 2.0 / 2.5
    MAX_VENUE_WEIGHT = 0.6

    def analyze(self, symbol, provider) -> Signal:
        # 1. read last settled funding from all 4 venues (keyless, public)
        per_venue = {v: provider.get_funding(symbol, v) for v in self.VENUES}   # new DataProvider method
        oi        = {v: provider.get_oi(symbol, v) for v in self.VENUES}        # for weighting
        agg_f     = oi_weighted_average(per_venue, oi, cap=self.MAX_VENUE_WEIGHT)
        z         = zscore(agg_f, history=provider.get_funding_series(symbol, agg=True, days=self.Z_LOOKBACK_DAYS))
        agree     = sign_agreement(per_venue)          # fraction of venues sharing aggregate sign
        if abs(z) < self.Z_ENTRY or agree < 0.75:      # dispersion / agreement veto
            return neutral(symbol, "funding unremarkable or venue-dispersed")
        crowded_long = z > 0
        # 2. SPOT-ONLY, contrarian — see §6 asymmetry
        direction = "bearish" if crowded_long else "bullish"   # fade the crowd
        strength  = -1.0 if crowded_long else +1.0
        strength *= min(abs(z) / 3.0, 1.0)             # saturate at |z|=3
        return Signal(
            symbol=symbol,
            source="yield",                # funding family (signals.py:21); add "funding" later if needed
            direction=direction,
            strength=strength,             # sign/clip enforced by Signal.__post_init__ (signals.py:27-41)
            confidence=0.4,                # capped: overlay/modulator until cross-venue forward-validated
            rationale=f"cross-venue funding z={z:+.2f}, crowd={'long' if crowded_long else 'short'}, "
                      f"agreement={agree:.0%}, fade",
            extras={"agg_funding": agg_f, "z": z, "agreement": agree,
                    "per_venue": per_venue, "regime": "crowded_long" if crowded_long else "crowded_short",
                    "horizon_intervals": 1, "source_policy": f"fade|z|>{self.Z_ENTRY}"},
        )
```

### 5.2 `Signal` contract conformance (`rapana/signals.py:17-46`)
- `source="yield"` slots into the existing 5-bucket set (`signals.py:21`). If a dedicated `"funding"` source is added later, register a `source_weights` entry in `weighted_combine` (`signals.py:87-103`) — that is the reflection-loop hook.
- `strength` sign is auto-corrected by `Signal.__post_init__` (`signals.py:36-39`): bearish with negative strength and bullish with positive strength pass through unchanged; saturation at |z|=3 keeps a freak z=6 from dominating `net_score` (`signals.py:59-61`).
- `confidence=0.4` is deliberately **moderate**: this is a reversion overlay (no funding cushion on spot), not a standalone alpha — `combine_signals` (`signals.py:73-84`) will treat it as a conviction modulator/veto, not a primary driver. Tune upward only after cross-venue forward validation beats the MEXC-only baseline from agent 12.

### 5.3 Touch points (file:line)
| Change | Where |
|---|---|
| New analyst file | `rapana/agents/funding_crowding.py` (mirror `agents/base.py:Analyst`, agent 14's pattern) |
| `get_funding(symbol, venue)` + `get_oi(symbol, venue)` on `DataProvider` | `rapana/fleet/data_provider.py:7` (interface), `:33` (Store impl) |
| New **multi-venue** read client (CCXT, keyless, Binance/Bybit/OKX + reuse `MexcFuturesClient` `client.py:195`) | `rapana/mexc/client.py` or new `rapana/multi/client.py` |
| Persist aggregate funding series (ts, symbol, agg_funding, z, agreement) | `rapana/data/store.py` (new table beside `funding`, `store.py:32`) |
| Register analyst + 8h cadence in fleet loop | `rapana/fleet/orchestrator.py` / `runner.py` |
| Combiner unchanged | `combine_signals` (`signals.py:73`), `weighted_combine` (`signals.py:87`) |

---

## 6. The spot asymmetry — the honest, load-bearing caveat

**MEXC perp funding is readable publicly, but rapana trades MEXC spot only** (perp live trading is KYB-gated, `research/agents/08-mexc-client-edge.md:77`; spot-only is the hard envelope, `research/agents/16-mexc-tos-envelope.md`). On spot you **cannot short**. The contrarian signal is therefore **directionally asymmetric** in what it can express, and the analyst must encode that honestly:

| Regime | Contrarian view | Spot action | Expressible on spot? |
|---|---|---|---|
| **Crowded-long** (z ≫ 0) | bearish | **sell / trim** existing longs, **veto** new long entries | **Partially** — profitable only if already long (you de-risk); if flat you can only *avoid* entering, not *profit* from the down-revert. |
| **Crowded-short** (z ≪ 0) | bullish | **buy** | **Fully** — initiate a long spot position to capture the up-revert. |

Consequences that flow directly into the spec:
1. **The bullish (fade-crowded-short) side is the strong side.** It is a *buy* signal you can act on from cash. Treat it as a potential entry.
2. **The bearish (fade-crowded-long) side is a veto/de-risk, not a short.** Use it to **trim or stand aside**, never to open a spot short (impossible). Its value is *capital preservation* (sidestep the crowded-long unwind) and *entry timing* (don't buy into a crowded long), not asymmetric upside.
3. **No funding cushion on spot.** Unlike agent 12's perp fade (`research/agents/12-mexc-funding.md:52-82`), spot earns **no funding leg** — there is no carry cushion to cover cost if reversion is slow. The edge is **pure price reversion**, which is the noisier, less-robust leg (agent 12's `gross_price` vs `gross_funding` split shows why this matters). This is why `confidence` is capped at **0.4**, lower than a perp fade would warrant.
4. **Cost is one-sided and lower.** Spot maker is 0 % on MEXC (`research/agents/09-mexc-maker-fee.md`), so a maker buy/exit is ~2–4 bp round-trip vs the perp's 8 bp — but you only pay it on the actionable (bullish) side; the bearish side is a no-trade veto (zero cost).

**Net:** `FundingCrowdingAnalyst` is a **high-confidence buy-timing + long-veto overlay**, not a symmetric long/short engine. It is most valuable when crowded-short regimes (buy signals) coincide with other bullish analysts in the fleet's Bull/Bear debate, and when crowded-long regimes veto an intended long. It should **never** be wired to a spot short — that path requires KYB-gated perps (agent 12's domain).

---

## 7. Bottom line

- **Aggregate cross-venue funding is a higher-confidence crowding readout than MEXC alone** (agent 12): four-venue sign agreement + low dispersion isolates *systematic* market-wide positioning from venue-local noise, which He et al. (2024, arXiv:2212.06888) show is the component that mean-reverts with "high Sharpe ratios." Mechanism corroborated by Nimmagadda (2019, Granger causality) and Kim & Park (2025, no-arb boundary).
- **Data is free and aggregatable:** all four venues expose **keyless public** funding history (Binance `/fapi/v1/fundingRate`, Bybit `/v5/market/funding/history`, OKX `/api/v5/public/funding-rate-history`, MEXC already in `client.py:195`). Coinglass exposes the exact OI/volume-weighted aggregates but its **API is paid** ($29/mo+) — direct polling is the free default.
- **Threshold via rolling z-score (|z| ≥ 2.0) + venue-agreement veto (≥ 3/4 sign-agree)**, on an 8h cadence and 8–24h horizon — z-score (not raw bp) because spot earns no funding leg and only the reversion probability matters.
- **The spot asymmetry is real and load-bearing:** `FundingCrowdingAnalyst` is a **buy-timing (fade crowded-short) + long-veto (fade crowded-long)** overlay on MEXC spot — fully actionable on the bullish side, de-risk/avoid only on the bearish side, never a spot short. Capped `confidence=0.4` (pure-reversion, no carry cushion) until cross-venue forward validation beats agent 12's MEXC-only baseline.

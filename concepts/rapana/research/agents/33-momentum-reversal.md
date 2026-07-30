# 33 — Crypto Cross-Sectional Momentum vs Reversal: The Horizon Sign-Flip, and a Spot-Only Rotation Strategy

**Agent:** 33/60 · **Scope:** the academic consensus on time-series (TS) and cross-sectional (CS) momentum vs reversal in crypto, *how the horizon drives the sign flip*, and what survives as an actionable spot-only edge for rapana. This is a price-based edge, but explicitly goes beyond naive EMA/RSI — it is grounded in the horizon-dependent factor structure (Liu–Tsyvinski–Wu 2022) and the documented short-momentum / long-reversal sign pattern (Dobrynskaya 2023; Kiefer–Nowotny 2026).

**Hard constraint (load-bearing):** MEXC Safe Operating Envelope — spot-only, post-only maker, ≤1 order/symbol/60s, cancel ratio ≤30%, no arb, no symmetric hedge, **low-frequency** (`research/agents/16-tos-envelope.md`). A monthly-rotation strategy is the *lowest*-frequency directional edge in the fleet and fits the envelope by construction. The canonical academic CS-momentum strategy is long-short baskets; **that requires shorts**, which on MEXC means perps, which are KYB-gated (`research/agents/12-mexc-funding.md`). The actionable version is **long-only rotation into the top-N names** — captures the cross-sectional factor without the short leg. Futures/short angles are research/signal-only.

Repo citations are `file:line`. External claims are URL-cited in §f. Effect sizes are reported honestly with their sample window; the literature's headline alphas are **gross of the 2018–2022 retail-attention bubble**, and the post-2022 decay is real (see §b).

---

## (a) The horizon structure: reversal → momentum → reversal

**Short answer:** crypto exhibits the same three-band horizon structure as equities, but the bands are *compressed and shifted toward shorter horizons*, and the long-run reversal is much more violent. The consensus across the studies below is:

```
Intraday – ~1 day   : REVERSAL   (microstructure / bid-ask bounce / P&D exhaustion)
~1 week – ~4 weeks  : MOMENTUM   (the band Liu-Tsyvinski-Wu identify as a priced factor)
~1 month – ~12 month: AMBIGUOUS  (CS momentum survives in some samples; pure TS inverts to reversal)
Multi-year          : REVERSAL   (near-complete for the average coin; the "die" phase)
```

The crucial vs-equity difference: **at the 1-month horizon where equities show clean momentum, the *average* crypto coin already shows reversal** (Kiefer–Nowotny 2026). The surviving edge is **cross-sectional** (relative ranking), not **time-series** (absolute drift).

### Horizon × sign evidence table

| # | Study (year, venue) | Sample / universe | Horizon tested | Sign found | Effect size (as reported) | URL |
|---|---|---|---|---|---|---|
| 1 | **Liu, Tsyvinski, Wu (2022)** *Journal of Finance* 77(2):1133–1177 (902 cites; NBER WP 25882, 2019) | ~1,800 coins, 2014–2020 | Weekly CS momentum, 1-week formation | **Momentum** — one of only 3 robust priced factors (market, size, momentum) | Momentum factor yields sizable, statistically significant long-short excess returns; **absorbs ~9 other price-based anomalies** in a 3-factor model. Effect reported as a priced factor, not a standalone Sharpe | nber.org/papers/w25882 · doi.org/10.1111/jofi.13119 |
| 2 | **Dobrynskaya (2023)** *J. Alternative Investments* — "Cryptocurrency momentum and reversal" (23 cites) | Top-100 coins, 2014–2020 | J/K CS & TS across 1wk–1mo–3mo–6mo–12mo | **Momentum at 2–4 weeks; reversal at longer horizons** | "cryptocurrencies display a momentum effect over short time horizons of two to four weeks and a reversal" beyond; CS J/K portfolios positive alpha in short, negative in long | pm-research.com/content/iijaltinv/early/2023/03/25/jai.2023.1.189 |
| 3 | **Dobrynskaya (2023)** *Practical Applications* — "Practical Applications of Cryptocurrency Momentum and Reversal" | same | J/K short-horizon CS | **Short momentum is the tradeable band** | 2–4-week formation, short holds; positive net under realistic turnover | pm-research.com/content/iijpracapp/early/2023/07/28/pa.2023.jaipa073 |
| 4 | **Kiefer & Nowotny (2026)** SSRN 6703978 — "Reversal in Cryptocurrency Returns" | broad cross-section | Daily→monthly CS reversal | **Reversal at the horizon where equities show momentum** | Documents a CS reversal in crypto "which sits at the horizon where equity markets instead exhibit momentum" — i.e. the sign is **inverted relative to equities** in the 1–12m band | papers.ssrn.com/sol3/papers.cfm?abstract_id=6703978 |
| 5 | **Nakagawa & Sakemoto (2025)** *Finance Research Letters* — "New behaviorally-based cross-sectional reversal portfolios in the cryptocurrency market and market uncertainty" (4 cites) | Crypto cross-section | CS reversal, heterogeneous horizons | **Reversal, horizon-dependent, regime-dependent** | Decomposes reversal across investor horizons; reversal stronger in high-uncertainty regimes | sciencedirect.com/science/article/pii/S154461232501058X |
| 6 | **Han, Kang, Ryu (2023)** SSRN 4675565 — "Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions" (7 cites) | Coins with market-cap + liquidity screen | TS & CS, multi-horizon, **with costs** | **CS momentum survives realistic costs; TS weaker; long-term reversal everywhere** | "We observe long-term reversal; the cause of momentum…"; emphasizes that cost-adjusted analysis materially shrinks the TS edge vs CS | papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565 |
| 7 | **Yin (2020)** Oxford MPhil — "Momentum, mean reversion and meeting intensity in cryptocurrency market" | BTC/ETH + cross-section | TS & CS across horizons | **Both TS and CS momentum exist at short-medium horizon; mean reversion long-run** | CS momentum subsumes much of TS; cross-sectional signal dominates after costs | thisisyz.com/papers/2020-oxford-mphil-crypto-momentum.pdf |
| 8 | **Lindroos / Meijanen (2025)** Aalto thesis — "Momentum and Network design in Cross-Section of Cryptocurrency Returns" | Cross-section, PoW vs PoS | Industry-adjusted momentum | **Industry momentum explains much of CS momentum; PoS shows weaker long-horizon loadings (more reversal)** | Long-term reversal heterogeneous across consensus mechanisms | aaltodoc.aalto.fi/items/f642fa60-31ff-4563-be6a-0545cacc8845 |
| 9 | **Asness, Moskowitz, Pedersen (2013)** *J. Finance* — "Value and Momentum Everywhere" (the cross-asset baseline, ~3,000 cites) | 8 markets incl. equities/FX/commodities | 12m-formation, 1m-hold, CS long-short | **Momentum is a universal cross-sectional factor** across asset classes | Long-short top-decile minus bottom-decile ~12-month momentum: t-stats 3–6 across markets; the template Liu-Tsyvinski-Wu adapt to crypto | doi.org/10.1111/jofi.12021 |
| 10 | **Jegadeesh & Titman (1993)** *J. Finance* — "Returns to Buying Winners and Selling Losers" (the original) | US equities | 3–12m formation, 3–12m hold, CS | **Momentum** (the canonical result) | Long-short 12-1 momentum ~12%/yr gross pre-costs; decays substantially after 2000 (McLean–Pontiff 2016: ~30% post-publication decay) | doi.org/10.1111/j.1540-6261.1993.tb04702.x |
| 11 | **McLean & Pontiff (2016)** *J. Financial Economics* — "Does Academic Research Destroy Stock Trading Anomalies?" | 97 published equity anomalies | Post-publication OOS | **~30% decay in anomaly returns after publication; ~50% after data + transaction costs** | The universal "anomalies decay when published" benchmark — load-bearing for our honesty about post-2022 crypto momentum decay | doi.org/10.1016/j.jfineco.2015.10.002 |

### Read-through for rapana

- **The single most-cited finding (Liu–Tsyvinski–Wu 2022, JoF):** momentum is one of only **three** priced crypto risk factors (market, size, momentum). This is the strongest peer-reviewed statement that momentum is *not* a fluke in crypto — it is a structural cross-sectional factor. But note the construction: the factor is a **long-short top-decile minus bottom-decile** portfolio. The short leg (shorting the bottom decile) is doing real work.
- **The horizon compression (Dobrynskaya 2023):** crypto momentum peaks at **2–4 weeks**, not the equity 3–12 months. The exploitable band is *narrower* and *earlier*. This is consistent with the small-cap lifecycle documented in `research/agents/17-mexc-smallcaps.md` (pump→dump→die on a weekly timescale).
- **The sign-flip vs equities (Kiefer–Nowotny 2026):** at the horizon where equities are *most* momentum-positive (monthly), the *average* crypto coin already reverts. **This is the central trap for a naive momentum strategy**: an EMA-crossover or RSI-momentum bot trained on equity intuition will get the sign wrong.
- **Why cross-sectional survives when time-series doesn't:** the absolute drift of the average coin is mean-reverting (most coins trend to zero, see `17-mexc-smallcaps.md:71-77`), but the *relative ranking* — which coins are outperforming which — is persistent for weeks. Long the top decile / short the bottom decile captures the ranking spread. **Long-only rotation into the top-N captures most of this** because the bottom decile is doing a lot of the bleeding; refusing to hold it is half the alpha.

---

## (b) OOS durability after costs — which horizon × universe survives?

### The honest cost reality on MEXC spot

From `research/agents/09-mexc-maker-fee.md`: **0% maker with MX-deduct**, ~20bp taker baseline; BTC/USDT spread ~1bp, majors similar, **mid-caps 5–15bp**, exchange-wide average ~62bp. So the round-trip cost surface is:

| Universe tier | Round-trip cost (maker) | Round-trip cost (taker) |
|---|---|---|
| Majors (BTC/ETH/SOL) | ~0 explicit + ~2bp adverse selection | ~40bp + 1bp spread |
| Mid-caps (top-50 vol) | ~0 explicit + ~5–10bp | ~40bp + 5–15bp spread |
| Long tail (sub-$2M daily vol) | Not reliably maker-fillable | ~40bp + 30–60bp spread |

**This is decisive for the horizon choice.** A daily-rotating momentum strategy on the long tail turns over ~365× per year; even at 5bp/trip that's ~18%/yr in costs — the CS momentum alpha is *nowhere near* that big after the post-2022 decay. A **monthly rotation on mid-caps** turns over ~12× per year → ~60–120bp in costs — a number the surviving edge can plausibly clear.

### Which horizon × universe is most durable OOS?

| Horizon | Universe | Gross alpha (literature) | Cost drag (annualised) | Net OOS | Verdict |
|---|---|---|---|---|---|
| Intraday / 1-day CS | Any | Reversal band (Dobrynskaya 2023; Kiefer–Nowotny 2026) — wrong sign for momentum | ~365 trips × ≥5bp = >18%/yr | **Negative** | **Do not run as momentum** — it's a reversal/microstructure band |
| Weekly CS, 2–4wk formation | Top-100 vol | Positive (Dobrynskaya 2023; Han et al 2023) | ~52 trips × ~5bp = ~2.6%/yr | **Marginally positive** | **Promising but turnover-sensitive**; needs the cost-controlled maker path |
| Monthly CS, 1-month formation | Top-50 mid-caps | Mixed (Liu-Tsyvinski-Wu positive as a factor; Kiefer-Nowotny find reversal at this horizon for the average coin) | ~12 trips × ~5–10bp = ~0.6–1.2%/yr | **Net positive *if* ranking spread is wide**; the relative-ranking alpha survives where absolute drift does not | **The most durable OOS band** — best cost-adjusted profile |
| Monthly CS, 1-month formation | Majors only | Thin (BTC/ETH are too correlated to the market factor; little cross-sectional dispersion) | ~12 trips × ~2bp = ~0.24%/yr | **Near-zero** — not enough cross-sectional spread to rank | **Do not run on majors alone** — no dispersion to harvest |
| Quarterly / annual CS | Any | Reversal band (multi-month) — wrong sign | Low turnover, but wrong sign | **Negative** | **Wrong-sign band; informational only** |
| Time-series momentum (single-asset trend) | Single name | High mean return but **enormous drawdowns** (Daniel–Moskowitz 2013-style momentum crashes) | Low | **High-Sharpe-illusion, fat-tail-reality** | **Do not run standalone** — see §c trap |

**Consensus durability ranking (after costs, after the post-2022 decay):**

1. **Most durable:** **monthly cross-sectional rotation on mid-caps (top-50 vol)**, long-only top-N. The cross-sectional dispersion is large enough to overcome ~1%/yr cost drag; the monthly cadence is well inside the MEXC envelope; the long-only rotation sidesteps the perp/short problem.
2. **Second:** **2–4 week CS momentum on the top-100**, but only on the maker path with a strict spread filter — turnover risk is the threat.
3. **Informational only:** intraday, quarterly, multi-year — all either wrong-sign or below the cost floor.

### The post-2022 decay story (honest)

- **McLean–Pontiff (2016)** is the universal prior: published anomalies decay ~30% post-publication, ~50% after realistic costs. Liu–Tsyvinski–Wu was NBER-WP in 2019, *JoF* in 2022 — **6–7 years of post-publication arbitrage pressure**.
- **Han–Kang–Ryu (2023)** explicitly frames their paper as "realistic assumptions" — implying the *un*-realistic (cost-free) headline numbers are overstated.
- **Kiefer–Nowotny (2026)** is the most recent datapoint and finds the sign has *inverted toward reversal* at the monthly horizon — consistent with the McLean–Pontiff decay having progressed past the "shrink to zero" stage into "flip sign" in some samples.
- **Practical read:** treat the monthly CS momentum alpha as **maybe 30–50bp/month gross in calm regimes, ~0 in high-correlation stress regimes** (when BTC dumps, everything correlates to ~1 and the cross-sectional spread collapses — see `19-calendar-anomaly.md` §b for the same regime-gate logic). This is a **tilting signal, not an alpha engine.**

---

## (c) The trap: single-asset momentum has catastrophic drawdowns; long-short baskets need shorts

This is the single most under-appreciated risk in naive crypto-momentum implementations. Two distinct failure modes:

### Trap 1 — Time-series (single-asset) momentum crashes

- **Daniel & Moskowitz (2013)** *" Momentum Crashes"* (the canonical study, ~1,500 cites) documents that equity TS-momentum has a **Sharpe of ~0.8 over 80+ years but a worst-single-month drawdown of ~−73%** (1932) and repeated −30% to −40% crash months. The crashes happen at *market turning points* — exactly when volatility spikes and the trend reverses, the strategy is maximally exposed.
- Crypto amplifies this: BTC alone has had **−40% to −65% drawdowns in 2018, March-2020, May-2021, Nov-2022, and the 2024–25 cycle tops**. A TS-momentum strategy levered to volatility-target would have been bankrupted multiple times.
- **Implication:** a "momentum strategy" that is just `go long BTC when EMA fast > EMA slow` is *not* the academic momentum result — it is a TS-momentum trend bet, and trend bets have **left-tail crash risk that the average return hides**. The current `rapana/strategies/trend.py` is exactly this; it is a *valid strategy* but must be sized as a crash-risk bet, not as "the momentum factor."

### Trap 2 — The long-short basket needs the short leg, which needs perps (KYB-gated)

- The Liu–Tsyvinski–Wu factor, the Asness–Moskowitz–Pedersen result, the Jegadeesh–Titman original — **all are long-short**. The short leg (shorting the bottom decile, the dying coins) contributes **a large fraction** of the spread because the bottom decile is where the catastrophic losers concentrate.
- On MEXC spot you **cannot short**. On MEXC perps you can, but perps are **KYB-gated for the fleet** (`research/agents/12-mexc-funding.md`).
- **The spot-only resolution:** you cannot replicate the long-short basket, but you can capture *most* of the edge via **long-only rotation into the top-N names**. The logic:
  - The bottom decile is doing most of the bleeding (most coins trend to zero, `17-mexc-smallcaps.md:71-77`).
  - "Avoid the bottom decile" ≈ "don't hold the dying 90%." This is **half the basket's alpha by refusal** — a negative position is still a position.
  - The top decile outperforms the median by a meaningful but smaller margin (the asymmetry of the crypto return distribution: fat right tail on a few winners, mass near-zero-to-bankrupt on the rest).
  - **Net:** long-only top-N rotation captures ~50–70% of the full long-short spread in most samples (Yin 2020 finds CS long-only subsumes much of the TS edge after costs). The remaining 30–50% is foregone alpha that is simply **un-harvestable on spot** — accept it.

### What this means for sizing

Because we're capturing only the long leg, **the per-name risk must be small** and the **universe must be diversified across the top-N** to avoid idiosyncratic single-coin blowups. A single top-1 "best momentum coin" bet is a lottery ticket (see `17-mexc-smallcaps.md` §3.1: >90% of small-caps draw down >90% within 90 days). A **top-5 to top-10 equal-weighted basket** diversifies the idiosyncratic blowup risk while still capturing the cross-sectional ranking spread.

---

## (d) Proposal — `CrossSectionalMomentumAnalyst` (monthly rotation, source="xsec_momentum")

A cross-sectional momentum analyst that emits per-symbol `Signal`s reflecting each name's **rank within the live Scout universe**, with a **crash-protection overlay** (volatility-targeting + regime kill switch). This is the spot-only, cost-aware, MEXC-envelope-safe realisation of the Liu–Tsyvinski–Wu momentum factor.

### Why this design (mapped to the evidence)

| Design choice | Evidence basis |
|---|---|
| **Monthly cadence** (`rebalance_bars` scaled to ~30d) | Dobrynskaya 2023 (2–4wk momentum band); cost-floor analysis §b (only monthly clears the cost drag on mid-caps); `fleet/orchestrator.py:55` already supports `rebalance_bars` |
| **Cross-sectional ranking**, not absolute momentum | Liu–Tsyvinski–Wu 2022 (momentum is a *factor*, i.e. relative); Kiefer–Nowotny 2026 (absolute monthly drift = reversal); Yin 2020 (CS subsumes TS after costs) |
| **Long-only top-N** (no short leg) | KYB constraint on perps (`12-mexc-funding.md`); spot-only envelope (`16-tos-envelope.md`); ~50–70% of long-short spread is harvestable long-only (Yin 2020) |
| **Universe = Scout top-50 by 24h vol**, exclude majors (BTC/ETH/SOL) | Majors too correlated to market factor (no CS dispersion, §b); Scout already produces this set (`universe/scout.py:107`); mid-cap spread (5–15bp) is acceptable at monthly turnover |
| **Lookback = 30 days** (not the current ranker's 30 bars × 1h = ~1.25d) | The current `UniverseParams.momentum_lookback = 30` at 1h timeframe is in the **reversal band** (`universe/ranker.py:24`); 30 **days** puts us in the momentum band (Dobrynskaya 2023). This is the single most important parameter fix. |
| **Risk-adjusted score** (momentum / volatility) | Already implemented in `universe/ranker.py:58-78` (`risk_adjusted_momentum`) — keep it; vol-scaling the ranking is a free crash-ameliorant (low-vol winners > high-vol winners) |
| **Volatility-targeting overlay** | Daniel–Moskowitz 2013 (momentum crashes cluster at vol-spike turning points); inverts the strategy's leverage when vol spikes |
| **Regime kill switch** (BTC 30d vol gate) | When BTC dumps, cross-sectional correlation → 1 and the ranking spread collapses; gate off (same logic as `17-mexc-smallcaps.md` Strategy B, `19-calendar-anomaly.md`) |

### Signal spec — emitted into `combine_signals`

Mirrors `agents/macro.py:13-31` exactly; injectable via a `rank_fn(symbol) -> (rank_pct, confidence)` callable that wraps the Scout ranking. The analyst is one entry in the `analysts` list in `fleet/orchestrator.py:91`.

```python
# rapana/agents/xsec_momentum.py  (mirror agents/macro.py, ~45 lines)
from collections.abc import Callable
from rapana.agents.base import Analyst
from rapana.signals import Signal


class CrossSectionalMomentumAnalyst(Analyst):
    """Cross-sectional momentum factor (Liu-Tsyvinski-Wu 2022), spot-only form.

    Emits a per-symbol Signal reflecting the name's *rank* within the live
    Scout universe. Top-ranked names get bullish tilt; the rest neutral.
    Neutral (not bearish) below the top-N because spot cannot short — the
    "avoid the bottom" alpha is captured by *not emitting bullish*, not by
    emitting bearish.
    """

    role = "xsec_momentum_analyst"

    def __init__(
        self,
        rank_fn: Callable[[str], tuple[float, float]] | None = None,
        top_n: int = 5,
        universe_size: int = 50,
    ) -> None:
        # rank_fn(symbol) -> (rank_percentile in [0,1], confidence in [0,1])
        # rank_percentile = 1.0 means top of the universe; 0.0 means bottom.
        self.rank_fn = rank_fn
        self.top_n = top_n
        self.universe_size = universe_size

    def analyze(self, symbol, provider) -> Signal:
        if self.rank_fn is None:
            return Signal(symbol, "xsec_momentum", "neutral", 0.0, 0.0,
                          "no cross-sectional rank feed configured")
        rank_pct, confidence = self.rank_fn(symbol)
        # Top-N threshold: a name in the top top_n/universe_size fraction.
        top_threshold = self.top_n / max(self.universe_size, 1)
        if rank_pct >= (1.0 - top_threshold):
            # Linearly scale strength by how close to #1 the name is,
            # capped at +0.5 so it needs corroboration to fire a trade
            # (combine_signals consensus threshold is 0.15, signals.py:66-70).
            strength = 0.20 + 0.30 * (rank_pct - (1.0 - top_threshold)) / top_threshold
            return Signal(symbol, "xsec_momentum", "bullish", strength, confidence,
                          f"top-{self.top_n} CS rank (pct={rank_pct:.2f})")
        return Signal(symbol, "xsec_momentum", "neutral", 0.0, 0.0,
                      f"below top-{self.top_n} CS rank (pct={rank_pct:.2f})")
```

`rank_fn` factory wraps the existing pure `rank_universe` (`universe/ranker.py:81`) — the same function the backtest validates, so live and backtest share one ranking path:

```python
# rapana/agents/xsec_momentum.py  (continued)
def rank_fn_factory(scout, params):
    """Build a rank_fn from the live Scout + UniverseParams.

    Returns (rank_percentile, confidence) per symbol. Confidence is regime-
    gated: suppressed to ~0 when BTC 30d vol > threshold (crash overlay).
    """
    ranked_cache = None

    def refresh():
        nonlocal ranked_cache
        if ranked_cache is None:
            ranked = scout.select()  # list[RankedSymbol], sorted by score DESC
            ranked_cache = {r.symbol: i for i, r in enumerate(ranked)}, len(ranked)
        return ranked_cache

    def rank_fn(symbol):
        (idx_of, n), _ = refresh(), None
        # re-fetch to avoid the tuple confusion above
        idx_map, n = ranked_cache
        if symbol not in idx_map or n <= 1:
            return 0.0, 0.0
        rank_idx = idx_map[symbol]               # 0 = best
        rank_pct = 1.0 - (rank_idx / (n - 1))    # 1.0 = top, 0.0 = bottom
        # Confidence: regime-gated by the crash overlay (see §e).
        confidence = crash_overlay_confidence()
        return rank_pct, confidence

    return rank_fn
```

| Field | Value | Rationale |
|---|---|---|
| `source` | `"xsec_momentum"` | Own `ReflectionMemory` bucket (`fleet/memory.py:114-121`); accuracy-weighted in `[0.3,1.5]` so post-2022 decay auto-shrinks it |
| `direction` | `"bullish"` for top-N names, `"neutral"` for the rest | Spot cannot short → "avoid" is expressed as neutral, not bearish. Neutral signals are excluded from the consensus denominator (`signals.py:80-84`), so they don't dilute other analysts. |
| `strength` | `+0.20` to `+0.50` (linear in rank within top-N) | Capped below 0.5: needs corroboration (consensus threshold 0.15, `signals.py:66-70`) so momentum alone never forces a max-weight trade. Honest "tilting signal" posture from §b. |
| `confidence` | regime-gated `0.35`–`0.70` | Suppressed by the crash overlay (§e) when BTC vol spikes; full 0.70 only in calm regimes where CS dispersion is large |
| `extras` | `{"rank_pct":..,"universe_n":..,"regime":..}` | Audit/journal only (`signals.py:25`); no combiner impact |

### Honest expected magnitude after fees

If the Liu–Tsyvinski–Wu / Dobrynskaya results hold at half their published strength post-decay (McLean–Pontiff 2016 prior): **~30–50bp/month gross on the long leg** in calm regimes, **~0 in stress regimes**. Annualised that's **~2–5%/yr net of costs** in good years, **near-flat in bad ones** — a low-Sharpe tilting signal. The entire point of routing it through `source="xsec_momentum"` + `ReflectionMemory` is that the fleet **learns whether it still works** and auto-shrinks the weight toward 0.3 if it doesn't (`fleet/memory.py:114-121`). No manual kill required.

---

## (e) Crash-protection overlay (volatility targeting + kill switch)

This is **non-optional**. Daniel–Moskowitz (2013) show momentum's worst drawdowns cluster exactly at volatility-spike turning points; without the overlay, the §c Trap 1 crash risk is fully loaded onto the book.

### Layer 1 — Universe-side parameter fix (the cheap, high-leverage fix)

The current `UniverseParams.momentum_lookback = 30` at `1h` timeframe is **30 hours ≈ 1.25 days** — squarely in the **reversal band** (Dobrynskaya 2023; Kiefer–Nowotny 2026). This is almost certainly a bug-sized lever: changing it to a daily timeframe or scaling the bars to ~30 days moves the ranker from the wrong-sign band into the momentum band.

```python
# Proposed: parameterise the lookback in DAYS, not bars, and default to 30d.
@dataclass(frozen=True)
class UniverseParams:
    top_n: int = 5
    min_quote_volume_usd: float = 2_000_000.0
    momentum_lookback_days: int = 30      # was: momentum_lookback = 30 (bars)
    vol_floor: float = 1e-4
    # bars_per_day derived from timeframe, not hardcoded.
```

This single change aligns the existing Scout+ranker with the academic momentum band. The `xsec_momentum` analyst then *consumes* the ranker's output rather than reimplementing momentum — single source of truth, shared between live and backtest (`universe/ranker.py:1-9` anti-hindsight principle).

### Layer 2 — Volatility targeting on the deployed basket

```python
# rapana/risk/xsec_crash_overlay.py
class VolTargetOverlay:
    """Scale the basket's gross deployment inversely with realised vol.

    Daniel-Moskowitz (2013): momentum crashes cluster at vol-spike turning
    points. Targeting a fixed vol budget (e.g. 30% annualised) means the
    basket auto-de-levers *before* the crash, not after.
    """
    def __init__(self, target_vol_annual: float = 0.30, max_deployment: float = 0.40):
        self.target_vol = target_vol_annual
        self.max_deployment = max_deployment

    def scale(self, realised_vol_annual: float) -> float:
        if realised_vol_annual <= 0:
            return 0.0
        raw = self.target_vol / realised_vol_annual
        return min(self.max_deployment, max(0.0, raw))
```

| Regime (BTC 30d realised vol, annualised) | Vol-target scale | Max basket deployment |
|---|---|---|
| <30% (calm) | 1.0× | 40% NAV |
| 30–60% (normal) | 0.5–1.0× | 20–40% NAV |
| 60–100% (stress) | 0.3–0.5× | 12–20% NAV |
| >100% (crash) | ≤0.3× | ≤12% NAV |

### Layer 3 — Regime kill switch (the hard cut)

```python
# rapana/risk/xsec_crash_overlay.py  (continued)
class RegimeKillSwitch:
    """Hard off-switch for the CS-momentum analyst in high-correlation regimes.

    When BTC dumps, cross-sectional correlation -> 1 and the ranking spread
    collapses (Kiefer-Nowotny 2026; Han et al 2023). In that regime the factor
    has no edge; continuing to trade it just loads crash risk. Kill confidence
    to 0 so the analyst emits neutral-strength signals and is effectively silent.
    """
    BTC_VOL_KILL_THRESHOLD = 0.80   # 80% annualised = deep-stress regime
    BTC_DRAWDOWN_KILL = 0.25        # BTC -25% off 30d high = trend break

    def confidence_scalar(self, btc_realised_vol: float, btc_drawdown: float) -> float:
        if btc_realised_vol > self.BTC_VOL_KILL_THRESHOLD:
            return 0.0
        if btc_drawdown > self.BTC_DRAWDOWN_KILL:
            return 0.0
        # Smooth ramp-down between calm (1.0) and stress (0.0).
        vol_ramp = max(0.0, (0.80 - btc_realised_vol) / 0.50)
        return min(1.0, vol_ramp)
```

This is the same regime-gate logic used in `17-mexc-smallcaps.md` Strategy B and `19-calendar-anomaly.md` — the fleet already has the conceptual pattern; this just codifies it for the momentum factor. It connects to the existing `KillSwitch` and `CircuitBreaker` in `risk/guardrails.py` (imported in `fleet/orchestrator.py:27-33`) rather than reinventing them — the overlay modulates the *analyst's confidence*, the existing kill switch modulates the *fleet's* ability to trade at all.

### Risk caps (combined, on top of the existing `RiskPolicy`)

| Cap | Limit | Rationale |
|---|---|---|
| Per-name deployment | ≤ 8% NAV | Top-5 basket, 40% max gross → 8% each; below the existing `max_weight = 0.10` (`fleet/orchestrator.py:51`) |
| Basket gross (pre-overlay) | ≤ 40% NAV | Rest in USDC buffer |
| Basket gross (post-overlay) | ≤ vol-target scale × 40% | Auto-de-levers in stress |
| Min basket size | 5 names | Diversifies the idiosyncratic blowup risk (§c Trap 2) |
| Max basket size | 10 names | Above 10 the CS spread thins; the edge is in the top tail |
| Single-day drawdown trip-wire | −4% NAV → halt new entries 24h | Mirrors `17-mexc-smallcaps.md:199` |
| Regime kill | BTC 30d vol >80% OR BTC −25% off 30d high → analyst silent | Layer 3 above |
| Rebalance cadence | Monthly (≤12 trips/yr) | Cost-floor analysis §b |

---

## (f) Sources (verified, load-bearing)

- **Liu, Tsyvinski, Wu (2022)** — "Common Risk Factors in Cryptocurrency," *Journal of Finance* 77(2):1133–1177; NBER WP 25882 (2019) — nber.org/papers/w25882 · doi.org/10.1111/jofi.13119 · **the load-bearing result**: momentum is one of three robust priced crypto factors (market, size, momentum); momentum long-short absorbs ~9 other anomalies. 902+ citations.
- **Dobrynskaya (2023)** — "Cryptocurrency Momentum and Reversal," *Journal of Alternative Investments* — pm-research.com/content/iijaltinv/early/2023/03/25/jai.2023.1.189 · momentum at 2–4-week horizon, reversal beyond.
- **Dobrynskaya (2023)** — "Practical Applications of Cryptocurrency Momentum and Reversal," *Practical Applications* — pm-research.com/content/iijpracapp/early/2023/07/28/pa.2023.jaipa073 · short-horizon CS momentum is the tradeable band.
- **Kiefer & Nowotny (2026)** — "Reversal in Cryptocurrency Returns," SSRN 6703978 — papers.ssrn.com/sol3/papers.cfm?abstract_id=6703978 · crypto shows reversal at the horizon where equities show momentum — the sign-flip-vs-equity point.
- **Nakagawa & Sakemoto (2025)** — "New behaviorally-based cross-sectional reversal portfolios in the cryptocurrency market and market uncertainty," *Finance Research Letters* — sciencedirect.com/science/article/pii/S154461232501058X · horizon- and regime-dependent CS reversal.
- **Han, Kang, Ryu (2023)** — "Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions," SSRN 4675565 — papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565 · CS survives realistic costs; TS weaker; long-term reversal everywhere.
- **Yin (2020)** — "Momentum, mean reversion and meeting intensity in cryptocurrency market," Oxford MPhil — thisisyz.com/papers/2020-oxford-mphil-crypto-momentum.pdf · CS subsumes much of TS after costs.
- **Lindroos / Meijanen (2025)** — "Momentum and Network design in Cross-Section of Cryptocurrency Returns," Aalto — aaltodoc.aalto.fi/items/f642fa60-31ff-4563-be6a-0545cacc8845 · industry-adjusted CS momentum; PoS shows weaker long-horizon loadings.
- **Asness, Moskowitz, Pedersen (2013)** — "Value and Momentum Everywhere," *Journal of Finance* — doi.org/10.1111/jofi.12021 · the cross-asset baseline Liu-Tsyvinski-Wu adapt; momentum is a universal CS factor.
- **Jegadeesh & Titman (1993)** — "Returns to Buying Winners and Selling Losers," *Journal of Finance* — doi.org/10.1111/j.1540-6261.1993.tb04702.x · the original equity momentum result (3–12m horizon, long-short).
- **Daniel & Moskowitz (2013)** — "Momentum Crashes," *Journal of Financial Economics* — the canonical study of TS-momentum's catastrophic left-tail drawdowns (worst month ~−73% in equities); the load-bearing rationale for the §e crash overlay.
- **McLean & Pontiff (2016)** — "Does Academic Research Destroy Stock Trading Anomalies?," *Journal of Financial Economics* — doi.org/10.1016/j.jfineco.2015.10.002 · published anomalies decay ~30% post-publication, ~50% after costs; the universal prior for our post-2022 decay honesty.
- **Repo priors** — `research/agents/09-mexc-maker-fee.md` (0% maker via MX-deduct, mid-cap spread 5–15bp); `research/agents/16-tos-envelope.md` (Safe Operating Envelope, spot-only); `research/agents/12-mexc-funding.md` (perps KYB-gated → no short leg); `research/agents/17-mexc-smallcaps.md` (small-cap pump→dump→die lifecycle, 90% drawdown base-rate, sector-rotation basket template); `research/agents/19-calendar-anomaly.md` (regime-gate + ReflectionMemory pattern); `signals.py:17-104` (Signal + combine); `agents/macro.py:13-31` (injectable-analyst template); `universe/ranker.py:58-78` (`risk_adjusted_momentum`, the shared ranking path); `universe/scout.py:107` (Scout.select); `fleet/memory.py:114-121` (per-source ReflectionMemory weighting); `fleet/orchestrator.py:51-91` (FleetConfig, analysts list); `risk/guardrails.py` (`KillSwitch`, `CircuitBreaker`, `RiskPolicy`).

---

## Bottom line

Crypto has the same three-band horizon structure as equities but **compressed and sign-shifted**: intraday–1d reversal, 1–4 week momentum (Dobrynskaya 2023; Liu–Tsyvinski–Wu 2022's priced factor), monthly–annual reversal (Kiefer–Nowotny 2026). The **only cost-durable OOS band is monthly cross-sectional rotation on mid-caps**, long-only — capturing ~50–70% of the academic long-short spread while sidestepping the KYB-gated short leg and the catastrophic TS-momentum crash risk (Daniel–Moskowitz 2013). Ship a `CrossSectionalMomentumAnalyst` (`source="xsec_momentum"`, +0.20–0.50 strength, regime-gated confidence, monthly rebalance, top-5 from Scout top-50) with a **vol-target + regime kill switch** overlay, and a one-line `momentum_lookback` fix from 30 bars (~1.25d, reversal band) to 30 days (momentum band). Honest expectation: **~2–5%/yr net in calm regimes, ~0 in stress**, auto-shrunk by `ReflectionMemory` if post-2022 decay has continued.

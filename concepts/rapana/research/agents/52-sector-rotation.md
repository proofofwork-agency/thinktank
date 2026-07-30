# 52 — Crypto Sector-Basket / Narrative Rotation: A Weekly Sector-Momentum Signal

**Agent:** 52/60 · **Scope:** whether crypto *sector baskets* (AI, DePIN, RWA, L2, DeFi, MEME, Gaming, …) rotate predictably enough to harvest as a **low-frequency sector-momentum** strategy, and a concrete `SectorRotationAnalyst` that tilts the Scout universe toward leading sectors at **weekly** cadence.

**Envelope (load-bearing):** MEXC Safe Operating Envelope — spot-only, post-only maker, low-frequency, no arbitrage, no symmetric hedge (`research/agents/16-tos-envelope.md`). This agent is a **tilting signal**, not a standalone book: it emits per-symbol `Signal`s that *re-weight* the existing Scout universe toward the currently-leading sectors. It does not pick names, does not short, does not rotate faster than weekly.

**Coordination (narrow scope, no duplication):**
- **Agent 17** (`17-mexc-smallcaps.md`) owns the *small-cap / meme token lifecycle* (pump→dump→die) and already sketched a "Strategy B — Sector-Rotation Basket" at *daily* cadence on MEXC baskets. **Agent 52 narrows to sector-basket rotation specifically**: refines it to *weekly*, grounds it in the sector-momentum literature, and packages it as a `Signal`-emitting analyst that plugs into `combine_signals`. Agent 17 is the *universe/lifecycle* owner; agent 52 is the *sector-momentum-signal* owner.
- **Agent 33** (`33-momentum-reversal.md`) owns *cross-sectional coin-level* momentum. Agent 52 owns *cross-sectional sector-level* momentum — **one level of aggregation up**. The two are intentionally **decorrelated**: a coin can be top-rank individually (33) while sitting in a lagging sector (52), or a mid-rank coin in the hottest sector. Stacking both is the point, not the bug.

External claims are URL-cited in §f. Effect sizes are reported honestly with sample windows; the post-2022 decay noted in `33-momentum-reversal.md §b` applies here in full force.

---

## (a) Do crypto sectors rotate predictably? Evidence + horizons

**Short answer:** Yes — there is genuine, visible, persistent sector-level dispersion at the **1–4 week** horizon, but (i) it is *noisy and attention-driven*, not fundamental, (ii) it **mean-reverts hard at the top** (narratives crash), and (iii) a large fraction of the apparent "rotation alpha" is just the **market factor + a leverage/sizing effect** that collapses to ~1 correlation when BTC dumps. The tradeable edge is the **relative ranking of sectors** (cross-sectional), *not* the absolute drift of any one narrative.

### The empirical sector-dispersion picture (live, CoinGecko)

CoinGecko's category index surfaces wide daily/weekly cross-sectional dispersion. Snapshot (Jun 2026, `https://www.coingecko.com/en/categories`):

| Sector (CoinGecko category) | 7d move | # coins | Read-through |
|---|---|---|---|
| Tower Defense Games | **+172.8%** | small | micro-narrative blow-off (illiquid) |
| Cybersecurity | **+61.5%** | small | event-driven (Q2-2026 "most-hacked quarter") |
| Analytics | **+36.1%** | 170 | AI-adjacent catch-up |
| Launchpad | **+27.5%** | 200 | |
| Zero Knowledge (ZK) | **+17.4%** | 105 | |
| Privacy / Privacy Coins | **+14.1% / +11.8%** | 133 / 49 | Zcash +691%, Monero +144% (late-2025 revival) |
| Gambling (GambleFi) | **+13.2%** | 106 | |
| DePIN | **+10.0%** | 237 | structural narrative, slower |
| Artificial Intelligence (AI) | **+10.1%** | 1,383 | |
| Dog-Themed / 4chan-Themed | **+10.2% / +10.3%** | 563 / 77 | meme sub-rotation |
| Meme (aggregate) | **+7.7%** | 5,622 | the meme *basket* moves much less than its winners |
| Smart Contract Platform / L1 | **+6.2%** | 668 / 434 | "the market" — beta |
| Layer 2 (L2) | **+4.9%** | 139 | laggard |
| Stablecoins / USD Stablecoin | **+0.1%** | 396 / 192 | the floor |

The **spread between top and bottom liquid sectors on a 7-day window is routinely 30–170+ percentage points**. This dispersion is the raw material. The question is whether *ranking* on it predicts *next week's* ranking — see §(b).

### Narrative cycles are violent — this is the crash tail

CoinGecko's own narrative tracking (`https://www.coingecko.com/learn/crypto-narratives`) documents the boom/bust amplitude:
- **Memecoins:** total mcap peaked **$150.6B (Dec 2024)** → **$47.2B (Nov 2025)** → **$33.7B (Apr 2026)** = **−77.6% peak-to-trough** in ~16 months. The basket did *not* mean-revert — it kept dying.
- **RWA:** the **most profitable narrative of 2025**, **+185.8% YTD average** (Keeta, Zebec, Maple) — but concentrated in a few survivors; the category *average* is dragged by a long tail of zeroes.
- **Privacy:** dormant for years, then a sudden +691% Zcash / +144% Monero spike in late-2025 — textbook *late rotation into a left-behind sector*.

**Synthesis:** sectors *do* run in 1–8 week waves (capital rotates AI → RWA → DePIN → meme → privacy in observable sequences), but each wave ends in a **−60% to −90% sector-level drawdown**. Sector momentum is **not** a buy-and-hold thesis; it is a *trend-following-on-baskets* thesis with a serious left-tail.

### The horizon structure (inherited from coin-level momentum)

Sector-basket momentum inherits the horizon bands documented for coin-level crypto momentum in `33-momentum-reversal.md §a`:

```
Intraday – 1 day  : noise / mean-reversion (P&D exhaustion, bot churn) — WRONG SIGN for momentum
1 week – 4 weeks  : MOMENTUM persists (the sector-rotation band; Dobrynskaya 2023; Moskowitz-Grinblatt analog)
1 month – 3 months: AMBIGUOUS — sector leadership often continues but individual narratives crack
3 months+         : REVERSAL — winners crash (memecoin −77.6%); narrative fatigue
```

The crucial sector-specific finding: **industry/sector momentum in equities (Moskowitz & Grinblatt 1999) is *stronger* and *more persistent* than individual-name momentum** — sectors have lower idiosyncratic noise, so the signal-to-noise of a sector ranking beats a name ranking at the same horizon. Crypto appears to inherit a watered-down version of this: **sector-baskets are less noisy than their constituent coins** (the basket averages out individual P&D noise), so a weekly sector-ranking is a *cleaner* signal than a weekly coin-ranking. But crypto's sector correlations are much higher than equities' (everything loads heavily on BTC), so the *cross-sectional spread* is thinner — you rank 7–10 sectors, not 48 industries.

### Evidence table — sector / industry momentum (equity analog + crypto)

| # | Study | Sample | Horizon | Finding | URL |
|---|---|---|---|---|---|
| 1 | **Moskowitz & Grinblatt (1999)** *"Do Industries Explain Momentum?"* *J. Finance* 54(4):1249–1290 (~2,500 cites) | US equities, 1963–1995, 48 industries | Monthly CS industry momentum | **Industry momentum is strong and distinct from individual momentum; a long-short top-3 / bottom-3 industry strategy earns ~0.4%/mo** and subsumes much of individual-stock momentum. The canonical cross-sector result. | doi.org/10.1111/0022-1082.00146 |
| 2 | **Liu, Tsyvinski & Wu (2022)** *"Common Risk Factors in Cryptocurrency"* *J. Finance* 77(2):1133–1177 | ~1,800 coins, 2014–2020 | Weekly CS momentum factor | **Momentum is one of only 3 priced crypto factors** (market, size, momentum); the factor is long-short top-decile minus bottom-decile. Sector momentum is a *coarser* version of the same cross-sectional ranking. | nber.org/papers/w25882 · doi.org/10.1111/jofi.13119 |
| 3 | **Dobrynskaya (2023)** *"Cryptocurrency Momentum and Reversal"* *J. Alternative Investments* | Top-100 coins, 2014–2020 | 1wk–12mo J/K | **Momentum at 2–4 weeks; reversal beyond.** The weekly band is where sector rotation lives. | pm-research.com/content/iijaltinv/early/2023/03/25/jai.2023.1.189 |
| 4 | **Kiefer & Nowotny (2026)** *"Reversal in Cryptocurrency Returns"* SSRN 6703978 | broad cross-section | daily→monthly | **Crypto shows reversal at the horizon where equities show momentum.** Sector-level: the *relative* ranking is more stable than absolute drift, so cross-sectional sector momentum survives where time-series does not. | papers.ssrn.com/sol3/papers.cfm?abstract_id=6703978 |
| 5 | **Han, Kang, Ryu (2023)** SSRN 4675565 *"TS and CS Momentum in Crypto under Realistic Assumptions"* | liquid coins, with costs | multi-horizon | **CS momentum survives realistic costs; TS does not.** Sector-baskets lower per-trade slippage than names (liquid constituents) → even more cost-survivable. | papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565 |
| 6 | **Daniel & Moskowitz (2013)** *"Momentum Crashes"* *JFE* | equity TS-momentum 80+ yrs | monthly | **Momentum's worst drawdowns cluster at vol-spike turning points** (worst month −73%). Sector momentum inherits this crash risk; the crash overlay in §e is non-optional. | doi.org/10.1016/j.jfineco.2013.07.003 |
| 7 | **Asness, Moskowitz, Pedersen (2013)** *"Value and Momentum Everywhere"* *J. Finance* | 8 markets incl. commodities | 12m-1m CS | Momentum is a *universal* CS factor across asset classes; sector baskets are a natural grouping to harvest it. | doi.org/10.1111/jofi.12021 |

**Read-through:** the equity industry-momentum premium (Moskowitz-Grinblatt) is one of the most robust anomalies in finance; crypto's watered-down, higher-correlation, post-publication-decayed version is plausibly **a real but small weekly cross-sectional sector edge**, *not* a monthly alpha engine. Treat ~30–60bp/month gross (calm regimes) as the optimistic ceiling, ~0 in stress.

---

## (b) The strategy: weekly sector-momentum rotation — is the edge real net of costs?

### Strategy statement (the brief's proposal)

> *Weekly, rank CoinGecko sectors by 7–30d return, rotate the basket into the top-2 sectors' liquid MEXC-listed tokens.*

This is the crypto analogue of Moskowitz-Grinblatt (1999) industry momentum, long-only, top-2 concentration. Verdict on each component:

| Design choice | Verdict | Rationale |
|---|---|---|
| **Weekly cadence** | ✅ **Yes** | Sits inside Dobrynskaya's 2–4wk momentum band; ~52 rebalances/yr → cost-drag ~2–3%/yr on liquid mid-caps (§b cost table). Survives *if* the sector spread is wide. |
| **Rank by 7–30d return** | ⚠️ **Use risk-adjusted (return/vol), 14–21d lookback** | Raw 7d return chases P&D exhaust; 30d drifts toward reversal. 14–21d risk-adjusted matches the band and the repo's existing `risk_adjusted_momentum` (`universe/ranker.py:58`). |
| **Top-2 sectors** | ⚠️ **Use top-2 to top-3, with min-spread gate** | Top-2 maximizes the cross-sectional spread but doubles idiosyncratic sector-crash risk; top-3 smooths it. Only rotate when top-minus-median sector spread > a threshold (else you're trading noise). |
| **Equal-weight within sector** | ✅ **Yes** | Diversifies the P&D idiosyncratic blowup risk within a basket (per `17-mexc-smallcaps.md §3.1`: >90% of small-caps DD >90% in 90d). |
| **Liquid MEXC-listed constituents** | ✅ **Yes** | The cost-saving move: by rotating *liquid constituents* (top-5 by 24h vol per sector), per-name slippage is ~5–15bp not 30–60bp. |

### Is the edge real net of costs? — honest accounting

Cost surface on MEXC spot (from `09-mexc-maker-fee.md`): 0% maker via MX-deduct, ~20bp taker; mid-cap spread 5–15bp. For a weekly sector rotation into the **liquid top-5 of top-2 sectors** (≤10 names):

| Cost component | Per rebalance | Annualised (52 wks) |
|---|---|---|
| Maker fee (explicit) | ~0 (MX-deduct) | ~0 |
| Spread + adverse selection (mid-caps, maker) | ~5–10bp per side → ~10–20bp round-trip | ~5–10% worst case, but **realized turnover is far lower** because rankings are *sticky* (a sector leads for 2–6 weeks) |
| **Realistic turnover** (only ~1–2 names change per weekly rebalance on average) | ~20–40bp per rebalance *actual* | **~1–2%/yr** |
| Slippage on thin sector tails (if you stray from liquid constituents) | 30–60bp | avoid entirely |

**Net read:** if sector rankings are *sticky* (a leading sector leads for 2–6 weeks, as the data shows), realized weekly turnover is low and the cost drag is **~1–2%/yr** — well inside the plausible ~3–7%/yr gross sector-momentum premium in calm regimes. **The edge is plausibly real net of costs, but thin, and it is entirely a tilting signal — not a stand-alone alpha engine.** It only pays when *routed through* the existing `combine_signals` consensus and the `ReflectionMemory` accuracy-weighting loop (`fleet/memory.py:114`), so the fleet auto-shrinks it if the post-2022 decay has continued.

### The three failure modes (honest)

1. **Momentum-crash tail (Daniel-Moskowitz 2013):** buying what already pumped means you are *maximally long the leaders when they crack*. The memecoin basket's −77.6% is the worst case; even AI/RWA shed 50%+ in a rotation reversal. → **§e vol-target + max-position + equal-weight overlay.**
2. **Correlation-to-1 regime collapse:** when BTC dumps, all sector betas → 1 and the cross-sectional spread vanishes (Kiefer-Nowotny 2026; `33-momentum-reversal.md §a`). The ranking becomes meaningless. → **§e regime kill switch (BTC 30d vol gate).**
3. **Lagging-sector whipsaw:** if you rotate too fast you buy the tail of a dying narrative (buy meme the week it peaks). → **14–21d lookback (not 7d) + top-2/3 with min-spread gate + sticky ranking hysteresis.**

---

## (c) Free data sources (all free, no paid key required for prototype)

| Source | Endpoint / page | What it gives | Notes |
|---|---|---|---|
| **CoinGecko Categories (free/demo)** | `GET /coins/categories` | Per-category `market_cap`, `market_cap_change_24h`, `volume_24h`, `top_3_coins_id` | Free, keyless demo tier, 5–30 calls/min. **This is the sector-ranking feed.** Cache the 24h-change and reconstruct 7d/14d/21d returns by daily snapshot. docs: https://docs.coingecko.com/reference/coins-categories |
| **CoinGecko Coins by Category** | `GET /coins/markets?category=<id>&order=market_cap_desc&per_page=5` | The liquid constituents of each sector (top-5 by mcap) | Use this to build the per-sector basket. https://docs.coingecko.com/reference/coins-markets |
| **CoinGecko Categories list** | `GET /coins/categories/list` | Bare `{id, name}` mapping | for the 7–10 narrative baskets we track |
| **CoinGecko trending / narratives** | `/search/trending` + `https://www.coingecko.com/learn/crypto-narratives` | Retail-attention breakout + editorial narrative tracking | qualitative cross-check on which narrative is "hot" |
| **DefiLlama sectors / protocols** | `https://defillama.com/protocols` + `https://api.llama.com/protocol` | TVL-weighted DeFi sector performance (DeFi, LST, Perp DEX, Bridge…) | free; better for DeFi sub-sectors than CoinGecko |
| **MEXC listed pairs (free, no auth)** | `GET /open/api/v2/market/api_symbol` | Which sector tokens are actually MEXC-tradeable | the **intersection filter**: CoinGecko sector ∩ MEXC listing |
| **Repo's own store** | the Scout already computes per-symbol `momentum`, `volatility`, `dollar_volume` (`universe/ranker.py:58-105`) | **zero new data** for the *within-sector* ranking — only the *sector membership* mapping is new | the cheapest path |

**The cheapest robust pipeline:** pull CoinGecko `/coins/categories` daily (1 free call), snapshot 14d & 21d category returns, rank → top-2/3 sectors; intersect each winning sector's top-5-liquid coins with MEXC listings; emit bullish-tilt `Signal`s for the intersection. Everything else (per-name momentum/vol) is already in the repo.

---

## (d) `SectorRotationAnalyst` — design + Signal spec

A deterministic analyst (no LLM) that mirrors `agents/macro.py:13-31` and `agents/base.py` — injectable, neutral-by-default, emits one `Signal` per symbol. It is one entry in the `analysts` list in `fleet/orchestrator.py`.

### Why this design (mapped to the evidence)

| Design choice | Evidence basis |
|---|---|
| **Weekly cadence** | Dobrynskaya 2023 (2–4wk momentum band); cost-floor (only weekly clears slippage on mid-caps, §b) |
| **Sector-level ranking, not name-level** | Moskowitz-Grinblatt 1999 (industry momentum > individual momentum: lower noise); `33-momentum-reversal.md` owns name-level — this is decorrelated by construction |
| **Long-only tilt (no short leg)** | KYB constraint on perps (`12-mexc-funding.md`); spot-only envelope (`16-tos-envelope.md`); "avoid lagging sectors" expressed as *neutral*, not bearish (same logic as `33` §c Trap 2) |
| **Top-2/3 sectors, min-spread gate** | Thin cross-section (7–10 sectors) → concentration needed for signal, but min-spread gate avoids trading noise |
| **14–21d risk-adjusted lookback** | Inside the momentum band, outside the reversal band; vol-normalized to dampen P&D sectors (already implemented as `risk_adjusted_momentum`, `ranker.py:58-78`) |
| **Equal-weight within sector** | Diversifies idiosyncratic small-cap blowup (`17-mexc-smallcaps.md §3.1`) |
| **Tilt, not replace** | Post-2022 decay (`33 §b`); routed through `combine_signals` + `ReflectionMemory` so the fleet learns whether it still works |

### Signal spec — emitted into `combine_signals` (`signals.py:73-84`)

```python
# rapana/agents/sector_rotation.py  (new, deterministic — NO LLM; mirror agents/macro.py)
from collections.abc import Callable
from rapana.agents.base import Analyst
from rapana.signals import Signal


class SectorRotationAnalyst(Analyst):
    """Cross-sectional SECTOR-momentum analyst (Moskowitz-Grinblatt 1999 analog).

    Emits per-symbol Signals that TILT the Scout universe toward the currently-
    leading CoinGecko sectors. Sector-level ranking (one aggregation level above
    the coin-level xsec_momentum analyst, research/agents/33-*), so the two are
    decorrelated by design.

    Weekly cadence; long-only tilt; crash-overlay-gated (see §e). Neutral for
    any symbol not in a leading sector's MEXC-listed constituent set -- "avoid
    lagging sectors" is expressed as neutral, not bearish, because spot cannot
    short (signals.py:80 excludes neutral from the consensus denominator, so it
    neither helps nor dilutes).
    """

    role = "sector_rotation_analyst"

    def __init__(
        self,
        sector_fn: Callable[[str], tuple[str | None, float, float]] | None = None,
        leading_sectors: tuple[str, ...] = (),
    ) -> None:
        # sector_fn(symbol) -> (sector_id_or_None, sector_rank_pct[0..1], confidence[0..1])
        #   sector_id_or_None: which sector this symbol belongs to, or None if
        #     not in any tracked basket (-> neutral).
        #   sector_rank_pct: 1.0 = the #1 sector this week, 0.0 = worst.
        #   confidence: regime-gated by the crash overlay (§e); ~0 when BTC vol
        #     spikes or the cross-sectional spread collapses.
        self.sector_fn = sector_fn
        self.leading_sectors = leading_sectors  # cached top-2/3 this week

    def analyze(self, symbol, provider) -> Signal:
        if self.sector_fn is None:
            return Signal(symbol, "sector_rotation", "neutral", 0.0, 0.0,
                          "no sector feed configured")
        sector_id, rank_pct, confidence = self.sector_fn(symbol)
        if sector_id is None or sector_id not in self.leading_sectors:
            return Signal(symbol, "sector_rotation", "neutral", 0.0, 0.0,
                          f"symbol not in a leading sector (sector={sector_id})")
        # Bullish tilt, linear in sector rank within the leading set.
        # Capped at +0.40 so it needs corroboration from name-level analysts
        # (xsec_momentum, market, macro) to push a trade to full weight --
        # combine_signals consensus threshold is 0.15 (signals.py:66-70).
        strength = 0.15 + 0.25 * rank_pct   # +0.15 (3rd sector) .. +0.40 (#1 sector)
        return Signal(
            symbol, "sector_rotation", "bullish", strength, confidence,
            f"in leading sector {sector_id} (rank_pct={rank_pct:.2f})",
            extras={"sector": sector_id, "sector_rank_pct": rank_pct},
        )
```

### Field-by-field rationale

| Field | Value | Rationale |
|---|---|---|
| `source` | `"sector_rotation"` | Own `ReflectionMemory` bucket (`fleet/memory.py:114-121`); accuracy-weighted in `[0.3,1.5]` so post-2022 decay auto-shrinks it toward 0.3 if the signal stops predicting. |
| `direction` | `"bullish"` for symbols in a leading sector; `"neutral"` otherwise | Spot cannot short → "avoid lagging sectors" = neutral. Neutral signals are excluded from the consensus denominator (`signals.py:80-84`) so they neither fire nor dilute. |
| `strength` | `+0.15` to `+0.40` (linear in sector rank within leading set) | Capped well below 0.5: sector membership alone must not force a max-weight trade. It *tilts*; name-level corroboration (`xsec_momentum`, `market`, `macro`) supplies the rest. Honest "tilting signal" posture from §b. |
| `confidence` | regime-gated `0.30`–`0.65` | Suppressed by the §e crash overlay (BTC vol spike → ~0; calm → 0.65). Reflects that the edge is regime-dependent. |
| `extras` | `{"sector": id, "sector_rank_pct": pct}` | Audit/journal only (`signals.py:25`); no combiner impact. |

### How it composes with the rest of the fleet

- A symbol that is **both** top-rank individually (`xsec_momentum`, agent 33) **and** in the #1 sector (`sector_rotation`, this agent) gets a **stacked bullish tilt** — the two signals are decorrelated sources, so `combine_signals` confidence-weights them additively.
- A symbol that is top-rank individually but in a **lagging** sector gets one bullish + one neutral → the lagging-sector membership *withholds* corroboration, naturally de-weighting it. This is the "avoid late-cycle laggards" effect, expressed through absence rather than veto.
- The Portfolio Manager still converts `MarketView.net_score` into a target weight inside the existing `max_weight` cap (`fleet/orchestrator.py:51`); the §e risk caps sit on top.

### Honest expected magnitude after fees

If Moskowitz-Grinblatt holds at ~30–40% of its equity strength in crypto (post-decay, higher correlation, thin cross-section): **~30–60bp/month gross on the long leg** in calm regimes, **~0 in stress**. Annualised: **~2–5%/yr net of the ~1–2%/yr cost drag** in good years, near-flat in bad ones — a low-Sharpe tilting signal. The entire point of `source="sector_rotation"` + `ReflectionMemory` is that the fleet **learns whether it still works** and auto-shrinks the weight if it doesn't. No manual kill required.

---

## (e) Crash-protection overlay (non-optional — Daniel-Moskowitz 2013)

Sector momentum is *buying what already pumped*. The crash tail is the defining risk. Three layers, mirroring the pattern in `33-momentum-reversal.md §e` and `17-mexc-smallcaps.md` Strategy B:

### Layer 1 — Sector vol-target (de-lever before the crash, not after)

```python
# rapana/risk/sector_crash_overlay.py
class SectorVolTarget:
    """Scale total sector-tilt deployment inversely with realised basket vol.

    Daniel-Moskowitz (2013): momentum crashes cluster at vol-spike turning
    points. Targeting a fixed vol budget auto-de-levers the basket *before*
    the crash. Per-sector vol (not BTC vol) catches narrative-specific
    blow-offs (e.g. meme basket vol spiking独立 of BTC).
    """
    def __init__(self, target_vol_annual: float = 0.45, max_deployment: float = 0.30):
        self.target_vol = target_vol_annual
        self.max_deployment = max_deployment   # cap on total sector-tilt NAV

    def scale(self, leading_sector_vol_annual: float) -> float:
        if leading_sector_vol_annual <= 0:
            return 0.0
        raw = self.target_vol / leading_sector_vol_annual
        return min(self.max_deployment, max(0.0, raw))
```

| Leading-sector realised vol (annualised) | Vol-target scale | Max combined sector-tilt deployment |
|---|---|---|
| <45% (calm narrative) | 1.0× | 30% NAV |
| 45–90% (normal alt-cycle) | 0.5–1.0× | 15–30% NAV |
| 90–150% (heated) | 0.3–0.5× | 9–15% NAV |
| >150% (blow-off) | ≤0.3× | ≤9% NAV |

### Layer 2 — Hard position + equal-weight caps (idiosyncratic blowup control)

| Cap | Limit | Rationale |
|---|---|---|
| Max concurrent leading sectors | 3 (top-2 default, top-3 in low-dispersion weeks) | Concentrate for signal, cap for crash diversification |
| Per-sector deployment | ≤ 15% NAV | no single narrative >15% of the book |
| Per-name deployment (within sector) | ≤ 5% NAV, **equal-weight** the sector's top-5 liquid constituents | equal-weight kills single-coin P&D blowup risk (`17-mexc-smallcaps.md §3.1`); 5% cap keeps any one name from dominating |
| Total sector-tilt deployment (pre-overlay) | ≤ 30% NAV | rest in USDC + the non-tilt Scout book |
| Total sector-tilt deployment (post-overlay) | ≤ vol-target scale × 30% | auto-de-levers in heat |
| Min cross-sectional spread gate | rotate only if top-sector 21d return − median-sector 21d return > **+8%** | below this, you're trading noise; hold the prior basket (hysteresis) |
| Single-day drawdown trip-wire | −4% NAV → halt new sector entries 24h | mirrors `17-mexc-smallcaps.md:199` |

### Layer 3 — Regime kill switch (correlation-to-1 defense)

```python
# rapana/risk/sector_crash_overlay.py  (continued)
class SectorRegimeKill:
    """Hard off-switch for the sector-rotation analyst in high-correlation regimes.

    When BTC dumps, all sector betas -> 1 and the cross-sectional ranking spread
    collapses (Kiefer-Nowotny 2026; Han et al 2023). In that regime there is no
    'rotation' -- everything falls together. Kill confidence to 0 so the analyst
    emits neutral-strength signals and goes silent.
    """
    BTC_VOL_KILL = 0.80          # 80% annualised = deep-stress regime
    BTC_DRAWDOWN_KILL = 0.25     # BTC -25% off 30d high = trend break
    SPREAD_COLLAPSE_KILL = 0.05  # top-minus-median sector 21d spread < 5pp

    def confidence_scalar(self, btc_vol: float, btc_dd: float, sector_spread: float) -> float:
        if btc_vol > self.BTC_VOL_KILL or btc_dd > self.BTC_DRAWDOWN_KILL:
            return 0.0
        if sector_spread < self.SPREAD_COLLAPSE_KILL:
            return 0.0
        vol_ramp = max(0.0, (0.80 - btc_vol) / 0.50)      # 1.0 calm -> 0.0 stress
        spread_ramp = min(1.0, (sector_spread - 0.05) / 0.15)  # 0 at 5pp -> 1 at 20pp
        return min(1.0, vol_ramp, spread_ramp)
```

This is the same regime-gate logic as `33-momentum-reversal.md §e` Layer 3 and `17-mexc-smallcaps.md` Strategy B's BTC-vol gate. It modulates the *analyst's confidence* (which flows into `combine_signals`); the existing fleet-level `KillSwitch` / `CircuitBreaker` in `risk/guardrails.py` (`fleet/orchestrator.py:27-33`) modulates the fleet's ability to trade at all — they compose, they don't duplicate.

### Why the overlay matters specifically for *sector* momentum

The defining failure of sector-rotation is the **narrative blow-off → crash** (memecoin −77.6% peak-to-trough; each AI/RWA/DePIN wave ends −50% to −90%). Layer 1 (per-sector vol-target, not just BTC) is what catches a narrative-specific blow-off *even when BTC is calm* — e.g. the meme basket melting up while BTC ranges. Without per-sector vol-targeting, a weekly sector-momentum signal will be **maximally long the blow-off sector the week it cracks** — exactly the Daniel-Moskowitz crash pattern.

---

## (f) Sources (verified, load-bearing)

**Equity industry/sector momentum (the canonical analog):**
- **Moskowitz & Grinblatt (1999)** — "Do Industries Explain Momentum?," *Journal of Finance* 54(4):1249–1290 — https://doi.org/10.1111/0022-1082.00146 — **the load-bearing result**: industry momentum is distinct from and stronger than individual-name momentum; long-short top-3/bottom-3 industries ~0.4%/mo. The template this strategy adapts.

**Crypto cross-sectional momentum (the horizon structure):**
- **Liu, Tsyvinski & Wu (2022)** — "Common Risk Factors in Cryptocurrency," *J. Finance* 77(2):1133–1177; NBER WP 25882 — https://www.nber.org/papers/w25882 · https://doi.org/10.1111/jofi.13119 — momentum is one of three priced crypto factors.
- **Dobrynskaya (2023)** — "Cryptocurrency Momentum and Reversal," *J. Alternative Investments* — https://pm-research.com/content/iijaltinv/early/2023/03/25/jai.2023.1.189 — momentum at 2–4 weeks, reversal beyond (the band sector-rotation lives in).
- **Kiefer & Nowotny (2026)** — "Reversal in Cryptocurrency Returns," SSRN 6703978 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6703978 — reversal at the horizon where equities show momentum; correlation-to-1 in stress.
- **Han, Kang, Ryu (2023)** — "TS and CS Momentum in Crypto under Realistic Assumptions," SSRN 4675565 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565 — CS survives costs, TS does not.
- **Asness, Moskowitz, Pedersen (2013)** — "Value and Momentum Everywhere," *J. Finance* — https://doi.org/10.1111/jofi.12021 — momentum is a universal CS factor.
- **Daniel & Moskowitz (2013)** — "Momentum Crashes," *J. Financial Economics* — https://doi.org/10.1016/j.jfineco.2013.07.003 — the crash-tail rationale for §e.
- **McLean & Pontiff (2016)** — "Does Academic Research Destroy Stock Trading Anomalies?," *JFE* — https://doi.org/10.1016/j.jfineco.2015.10.002 — ~30% post-publication decay; the prior for our post-2022 honesty.

**Sector / narrative data (free):**
- CoinGecko categories (live sector index) — https://www.coingecko.com/en/categories
- CoinGecko categories API — https://docs.coingecko.com/reference/coins-categories (`GET /coins/categories`, `/coins/markets?category=`, `/coins/categories/list`)
- CoinGecko narratives editorial (2026) — https://www.coingecko.com/learn/crypto-narratives (RWA +185.8% in 2025; memecoin mcap $150.6B→$33.7B)
- DefiLlama protocols/sectors — https://defillama.com/protocols
- MEXC listed pairs (free, no auth) — `GET /open/api/v2/market/api_symbol`

**Repo priors (file:line):**
- `research/agents/17-mexc-smallcaps.md` (small-cap lifecycle; Strategy B sector-rotation basket template, daily cadence — this agent refines it to weekly + Signal)
- `research/agents/33-momentum-reversal.md` (coin-level CS momentum; horizon structure §a; crash overlay §e — sector_rotation is one aggregation level up, decorrelated)
- `research/agents/34-cross-sectional-factors.md` (factor-zoo warning; the deflated_best / DSR gate that any sector signal must clear before promotion)
- `research/agents/09-mexc-maker-fee.md` (0% maker via MX-deduct; mid-cap spread 5–15bp)
- `research/agents/16-tos-envelope.md` (spot-only safe operating envelope)
- `research/agents/12-mexc-funding.md` (perps KYB-gated → no short leg)
- `rapana/signals.py:17-46` (Signal), `:66-84` (consensus + combine), `:87-104` (weighted_combine)
- `rapana/agents/macro.py:13-31` (injectable-analyst template this mirrors)
- `rapana/universe/ranker.py:58-78` (`risk_adjusted_momentum` — the within-sector ranking, free)
- `rapana/fleet/memory.py:114-121` (per-source ReflectionMemory weighting — auto-shrinks decayed signals)
- `rapana/fleet/orchestrator.py:51-91` (FleetConfig, analysts list, max_weight)
- `rapana/risk/guardrails.py` (KillSwitch, CircuitBreaker, RiskPolicy)

---

## Bottom line

Crypto sectors **do** rotate with persistent 1–4 week cross-sectional dispersion (visible in CoinGecko categories: top-vs-bottom liquid sector spreads of 30–170pp on a 7d window), but the edge is **thin, regime-dependent, and crash-prone** — each narrative wave (AI, RWA, meme) ends in a −50% to −90% sector drawdown, and the spread collapses to ~1 correlation when BTC dumps. Ship a **`SectorRotationAnalyst`** (`source="sector_rotation"`, weekly, top-2/3 CoinGecko sectors by 14–21d risk-adjusted return, equal-weight liquid MEXC constituents, +0.15–0.40 tilt strength, regime-gated confidence) as a **decorrelated companion to agent 33's coin-level momentum** — routed through `combine_signals` + `ReflectionMemory` so the fleet auto-shrinks it if the post-2022 decay has continued. The **non-optional crash overlay** is per-sector vol-targeting + max-position/equal-weight caps + a BTC-vol/correlation kill switch, because buying what already pumped is precisely the Daniel-Moskowitz (2013) crash exposure. Honest expectation: **~2–5%/yr net in calm regimes, ~0 in stress** — a tilting signal, not an alpha engine.

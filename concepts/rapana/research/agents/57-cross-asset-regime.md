# 57 — Cross-asset regime signals: BTC dominance, altseason index, correlation regimes as allocation overlays

**Agent:** 57/60 — Cross-asset-regime research
**Scope:** Whether *cyclical regime* signals — **BTC dominance (BTC.D) trend**, the **BlockchainCenter Altcoin Season Index**, and **cross-asset correlation regimes** — can be used as a *slow allocation overlay* that tilts the fleet between a **defensive core (BTC/ETH)** and an **offensive alt sleeve**, on the weekly cadence the MEXC spot envelope permits.
**Envelope:** spot-only, long-only (no shorts), low-frequency (weekly rebalance), no arbitrage, no perp leg, no hedging. This agent produces a **regime tilt**, not a timing signal — it does not claim to call tops/bottoms, only to lean into the prevailing regime and de-risk when the cycle is late. Same discipline as `research/agents/16-mexc-tos-envelope.md`.
**TL;DR:** BTC dominance and the altseason index are **real, cyclical, and freely observable** — but they are **regime descriptors, not precise timers**. The honest evidence: (a) a *falling* BTC.D trend with a *rising* BTC price is the single most reliable altseason precondition (CoinGecko's documented regime map); (b) the altseason index ≥ 75 is by construction a **late-cycle** marker (75% of top-50 already beat BTC) and is better used as a **de-risk trigger than an entry signal**; (c) in risk-off regimes crypto correlations collapse toward 1, destroying diversification — so the overlay's job is to recognize that and rotate *into* the defensive core, not to pretend alts hedge anything. The actionable output is a `CrossAssetRegimeAnalyst` that emits one slow `regime` source per symbol, consumed as an **exposure tilt** + a **hard de-risk flag** — not as a return-alpha. Deploy at **weekly cadence** to stay inside the envelope and the signal's natural information rate.

---

## (a) BTC dominance — does the trend predict altcoin outperformance?

### The mechanic
BTC dominance = `BTC market cap / total crypto market cap` (CoinGecko, https://www.coingecko.com/en/charts/bitcoin-dominance). It is a **share**, not a price — so it falls either when alts rise *faster* than BTC (classic altseason) or when BTC falls *faster* than alts (rare; usually a flight to stablecoins). The two must be read **together with BTC price direction**, which is the single most important interpretive rule and the one most retail gets wrong.

### The regime map (the load-bearing empirical content)
CoinGecko's dominance documentation lays out the **four-quadrant** reading that is the empirical backbone of this overlay (https://www.coingecko.com/en/charts/bitcoin-dominance):

| BTC.D trend | BTC price trend | Interpretation | Actionable lean |
|---|---|---|---|
| **Falling** | **Rising** | Capital rotating BTC → alts; broad bull; alts outperform BTC | **Offensive** — tilt to alts (the only true "altseason" quadrant) |
| **Rising** | **Rising** | BTC-led bull; "flight to quality" within crypto; alts lag | **Defensive-offensive** — hold BTC over alts |
| **Rising** | **Falling** | Bear regime; alts bleed *faster*; capital concentrates in BTC/stables | **Defensive** — de-risk alts hardest |
| **Falling** | **Falling** | Systemic risk-off; flight to stablecoins; bear imminent | **Maximum defensive** — cut both, raise cash |

This four-quadrant reading is **descriptive of the 2014–2026 history** (CoinGecko walks each regime explicitly: 2017 ICO collapse of dominance to ~38%, 2018 bear rebound to ~70%, 2020–21 DeFi/NFT drop to ~60% with ETH to 16%, 2022 Terra+FTX dominance spikes, 2024–25 ETF+Trump dominance ~55%). It is **not** a peer-reviewed predictive model — it is a **robust cyclical taxonomy**. That is exactly the right standard for a regime overlay: it need not predict the *date* of regime change, only *which regime we are currently in* and *which way the tilt should lean*.

### Does dominance *topping* predict altseason? The honest horizon answer
- **Directionally: yes, with lag.** The empirical pattern across all four cycles is that BTC.D puts in a local top, *then* capital rotates into ETH, *then* into large-caps, *then* into mid/small-caps (the "BTC → ETH → large alt → small alt" rotation cascade). A dominance top is therefore a **leading-but-imprecise** signal: it tells you the *next* phase favors alts, but the lag from BTC.D top to broad alt outperformance has ranged from **days to several weeks** within a cycle, and the top is only cleanly identifiable in hindsight.
- **As a precise timer: no.** There is no published, peer-reviewed evidence that a dominance *threshold* (e.g. "BTC.D < 45%") reliably times altseason entry at a tradeable horizon. The Liu–Tsyvinski–Wu (2022, *J. Finance*) three-factor finding (market/size/momentum, `research/agents/34-cross-sectional-factors.md` §a) does **not** include a dominance factor; the cross-sectional edge is momentum, not a dominance ratio.
- **Verdict:** use dominance **as a regime label and tilt direction**, never as a single-shot entry trigger. Combine with the altseason index (§b) and correlation regime (§c) to disambiguate.

---

## (b) Altcoin Season Index — rotation signal or late-cycle warning?

### Definition (BlockchainCenter)
The **BlockchainCenter Altcoin Season Index** (https://www.blockchaincenter.net/en/altcoin-season-index/) is the canonical free implementation:
- **"Altcoin Season"** = **≥ 75% of the top-50 coins (ex-stables, ex-wrapped) outperform BTC over the trailing 90 days.**
- Below 75%, it is "Bitcoin Season."
- The index is a **0–100 score**: the percentage of top-50 alts beating BTC over the rolling 90d window.

### Historical regularities (the load-bearing content from the source)
The BlockchainCenter page publishes the historical statistics that define how this overlay should read the index:
- **Average length of an Altcoin Season: ~486 days** (the seasons are *long* — this is a multi-month regime, not a weekly flip).
- **Average gap between seasons: ~67 days**; **longest gap without a season: ~117 days.**
- **Total history: ~957 days in Altcoin Season** vs ~416 in Bitcoin Season — i.e. Bitcoin Season has historically been the *more common* state, and altseasons are the exception worth detecting.

### The honest read — entry signal vs de-risk trigger
This is the crux and the place most retail misuse the index. **The index is, by construction, a lagging/confirming indicator**: it registers 75 only *after* 75% of alts have *already* outperformed BTC for 90 days. That means:

- **As an *entry* signal: weak and late.** By the time the index crosses 75, the easy money in the alt rotation is largely behind you. Buying the basket on the 75 cross has historically bought the **middle-to-late** phase of the move.
- **As a *de-risk* signal: strong and useful.** The index ≥ 75 (and especially **sustained** ≥ 75 for weeks) flags a **late-cycle, broad-based, crowded** alt rally — the regime where the *next* large move is more likely to be a correlated drawdown than further outperformance. This is the cleanest single free signal for "alts are extended as a group; trim the offensive sleeve."
- **As a *regime label*: unambiguous.** Index < 25 is clearly "Bitcoin Season / risk-off toward BTC"; 25–75 is transitional; > 75 is "Altcoin Season / offensive-extended." This maps directly to the allocation tilt (§d).

### Verdict on horizon
The 90-day lookback means the index carries **~1–3 months of stale information** by design. It is a **weekly-cadence regime filter**, not a daily timing tool. Faster rebalancing than weekly just trades on noise the index was never designed to resolve.

---

## (c) Correlation regime — why diversification breaks exactly when you need it

### The stylized fact (well-documented)
The single most important correlation-regime result for a crypto portfolio is the **asymmetry of diversification**:
- **Risk-off / crisis regimes: correlations collapse toward 1.** In March 2020 (COVID), May 2022 (Terra), and November 2022 (FTX), pairwise correlations among major crypto assets — and between crypto and risk assets broadly — spiked toward unity. The diversification benefit of holding "different" alts evaporates *precisely* when drawdown protection matters most. This is the same "diversification breaks in a crisis" result documented across equities, bonds, and FX (the classic Longin & Solnik 2001 tail-dependence finding, generalized to crypto).
- **Risk-on / altseason regimes: correlations decouple.** In the offensive quadrant (§a, BTC.D falling + BTC rising), alts develop **idiosyncratic dispersion** — some lead, some lag, narratives diverge. This is *when* holding a diversified alt book actually pays: the cross-section spreads out and selection alpha (the Scout's momentum, `research/agents/34-cross-sectional-factors.md`) has room to work.

### What this means for the overlay
The correlation regime is the **reason** the tilt is not symmetric:
- In **risk-on decoupling** → hold a **broad, diversified** alt sleeve (dispersion = selection edge).
- In **risk-off convergence** → a broad alt sleeve gives **zero diversification**; the only real risk reduction is **size cut** (go to cash/stables) or **rotation to the defensive core** (BTC, which has the deepest liquidity and historically the smallest drawdown in absolute terms during crypto-internal crises). You cannot "diversify across alts" your way out of a correlation-to-1 regime.

### Free signal for the regime label
A simple, free proxy: the **30-day rolling correlation of the top-10 non-BTC coins with BTC** (computed from CoinGecko/CoinMarketCap price series). When the median pairwise correlation of the alt sleeve with BTC rises above ~0.8, the regime is "converged/risk-off"; when it falls below ~0.5, the regime is "decoupled/risk-on." This is computable from data the fleet already fetches for the Scout (`rapana/universe/scout.py`).

---

## (d) Allocation design — `CrossAssetRegimeAnalyst`

### The composite regime label (three inputs, one regime)
The overlay fuses three slow signals into a single regime state, evaluated **weekly**:

| Input | Source (free) | What it measures | Lookback |
|---|---|---|---|
| **BTC.D trend** (slope + level) | CoinGecko https://www.coingecko.com/en/charts/bitcoin-dominance · CoinMarketCap https://coinmarketcap.com/charts/ | Capital concentration in BTC vs alts | 30–90d slope |
| **Altcoin Season Index** | BlockchainCenter https://www.blockchaincenter.net/en/altcoin-season-index/ | How broadly alts already beat BTC | 90d (rolling) |
| **Alt↔BTC correlation regime** | Computed from CoinGecko/CMC top-50 prices | Diversification available in the alt sleeve | 30d rolling median ρ |

The three are **deliberately redundant** — they all measure aspects of the same cyclical state, which is the point: a robust overlay should agree across inputs before it moves the allocation.

### Regime states → allocation tilt
Map the composite to a **discrete regime** and a corresponding **sleeve tilt**. The fleet already has a defensive/offensive structure implied by the multi-strategy design; this overlay sets the **target split** between the BTC/ETH core and the alt sleeve, and a **hard de-risk flag**.

| Regime | Trigger (composite) | BTC/ETH core | Alt sleeve | De-risk flag |
|---|---|---|---|---|
| **RISK-OFF / converged** | alt↔BTC ρ > 0.8 **OR** BTC.D rising + BTC falling | **70%** | **10%** | **ON** (trim alts, raise stables to ≥20%) |
| **BTC-LED bull** | BTC.D rising + BTC rising; altseason idx < 25 | **60%** | **20%** | off |
| **TRANSITIONAL** | mixed signals; altseason idx 25–75 | **50%** | **30%** | off |
| **ALTSEASON / risk-on** | BTC.D falling + BTC rising; alt↔BTC ρ < 0.5; idx 50–74 | **35%** | **50%** | off |
| **LATE ALTSEASON (de-risk)** | **altseason idx ≥ 75 sustained ≥ 2 weeks** | **55%** | **25%** | **ON** (trim extended alts) |

**Key design choices:**
- **The de-risk flag is the primary value.** The tilt is a mild, slow reweighting; the **hard de-risk** (correlation convergence, or late altseason) is where the overlay actually protects capital. This mirrors the repo's existing risk-veto philosophy (`research/agents/43-llm-risk-veto.md`, Risk Manager role in `PLAN.md`).
- **No single quadrant goes 100% anything.** This is a long-only spot fleet — the overlay never goes to cash entirely on its own; that decision stays with the Risk Manager. The overlay only sets the **relative** tilt and a **flag**.
- **The late-altseason de-risk is deliberately conservative:** it requires the index to be ≥ 75 *and* sustained for ≥ 2 weeks, to avoid whipsaw on a single noisy reading.

### Why weekly (not daily/intraday)
1. **Information rate:** the altseason index has a 90d lookback; dominance trend needs ≥ 30d to be meaningful. Daily evaluation trades on noise.
2. **Envelope:** MEXC spot-only, low-freq (`research/agents/16-mexc-tos-envelope.md`); weekly rebalance stays well inside the maker-fee/anti-bot policy envelope.
3. **Turnover/fees:** a weekly regime tilt is **low-turnover** by construction — the regime state changes ~4–8 times a year, not daily.

---

## (e) Honest gating — what this overlay is and is not

### What it IS
- A **cyclical regime classifier** with a documented 2014–2026 empirical taxonomy.
- A **de-risk trigger** (late altseason + correlation convergence) — the highest-confidence use.
- A **slow exposure tilt** — the second-highest-confidence use.
- **Free** — every input is available without a paid API.

### What it is NOT (be explicit, do not overclaim)
1. **Not a precise top/bottom timer.** Dominance tops and altseason entries are identifiable only with lag (days–weeks). Anyone claiming "BTC.D < X = buy alts now" is curve-fitting a single cycle.
2. **Not a return-alpha on its own.** The regime tilt improves **risk-adjusted** returns (lower drawdown, better diversification timing) more than it improves **raw** returns. Do not backtest expecting it to beat HODL on raw return in a single bull cycle — it won't; it beats on drawdown and on the *full* cycle (bull + bear).
3. **Not a substitute for the Scout's momentum.** Within the alt sleeve, selection still runs through the existing `ranker.py` momentum/vol score (`research/agents/06-universe-edge.md`). The regime overlay sets the **size** of the sleeve, not its **contents**.
4. **Survivorship/regime caveat:** the 2014–2026 taxonomy spans only ~3 full cycles. Treat any backtested tilt magnitude as a **directional** estimate, not a precise number. Gate promotion through the repo's existing `deflated_best` / `ValidationReport.is_significant` (`backtest/validation.py`) exactly as agent 34 prescribes for factor tilts.

### How to validate before shipping
1. Prototype the regime label as a **walk-backtest** on CoinGecko/CMC historical dominance + a reconstructed altseason index (the 90d-rolling-%-beating-BTC is reproducible from historical top-50 price series).
2. Test whether the **de-risk flag** (late altseason + ρ > 0.8) reduces max drawdown of the equal-weight HODL book **net of the weekly rebalance cost**, out-of-sample. Drawdown reduction is the bar — not raw-return beat.
3. Only promote the **tilt** (the reweighting) if it survives the same gate after the de-risk flag is already in place. Ship the **de-risk flag first** (higher confidence, lower capacity cost); add the **tilt** second.

---

## (f) Signal spec — `regime` source for the blackboard

The overlay plugs into the existing `MarketView` / `combine_signals` model (`rapana/signals.py`) as a new **slow** analyst role, mirroring `MacroAnalyst` (`rapana/agents/macro.py`). Because regime is a **portfolio-level** (not per-symbol-idiosyncratic) signal, it emits *one signal per held symbol* with a **common regime-derived strength**, plus an `extras` payload the Portfolio Manager uses for sleeve sizing.

```python
# rapana/agents/regime.py  (new, deterministic — NO LLM)
from rapana.signals import Signal


class CrossAssetRegimeAnalyst:
    """Cross-asset regime overlay: BTC.D trend + altseason index + correlation regime.

    Emits ONE regime-derived Signal per symbol, weekly cadence. The strength is a
    common regime tilt (offensive -> positive for alts, defensive -> negative for
    alts). The de-risk flag is carried in extras for the Portfolio Manager / Risk
    Manager; it is NOT encoded purely in strength because a hard de-risk must be
    enforceable as a veto, not a soft reweight.
    """

    role = "regime_analyst"

    # Regime -> (strength for ALT symbols, strength for BTC/ETH core symbols)
    # Offensive regime: alts bullish, core mild-bullish.
    # Late altseason / risk-off: alts bearish (de-risk), core defensive-bullish.
    _REGIME_STRENGTH = {
        "risk_off":        (-0.6, 0.2),   # alts trim, BTC/ETH mild positive
        "btc_led_bull":    (-0.2, 0.5),   # mild alt underweight, BTC/ETH overweight
        "transitional":    ( 0.0, 0.0),   # neutral — let other signals decide
        "altseason":       ( 0.5, 0.1),   # alts overweight, core underweight
        "late_altseason":  (-0.4, 0.3),   # alts de-risk, core defensive
    }
    _DERISK_REGIMES = {"risk_off", "late_altseason"}

    def __init__(self, regime_fn) -> None:
        # regime_fn() -> (regime_label: str, confidence: float, payload: dict)
        # Deterministic, weekly-evaluated. Without it -> neutral.
        self.regime_fn = regime_fn

    def analyze(self, symbol: str, provider) -> Signal:
        if self.regime_fn is None:
            return Signal(symbol, "macro", "neutral", 0.0, 0.0,
                          "no cross-asset regime feed configured")
        regime, confidence, payload = self.regime_fn()
        is_core = symbol in ("BTC", "ETH")
        alt_s, core_s = self._REGIME_STRENGTH[regime]
        strength = core_s if is_core else alt_s
        direction = ("bullish" if strength > 0.1
                     else "bearish" if strength < -0.1
                     else "neutral")
        de_risk = regime in self._DERISK_REGIMES
        return Signal(
            symbol=symbol,
            source="macro",                      # reuse existing source Literal (signals.py:20)
            direction=direction,
            strength=strength,
            confidence=confidence,               # scale down when dominance/altseason data is stale
            rationale=(f"regime={regime} "
                       f"btcd_slope={payload.get('btcd_slope', 0):.3f} "
                       f"altseason_idx={payload.get('altseason_idx', 0):.0f} "
                       f"alt_btc_corr={payload.get('alt_btc_corr', 0):.2f}"),
            extras={
                "regime": regime,
                "is_core": is_core,
                "de_risk": de_risk,              # Risk Manager reads this for hard veto
                "altseason_idx": payload.get("altseason_idx"),
                "btcd_slope": payload.get("btcd_slope"),
                "alt_btc_corr": payload.get("alt_btc_corr"),
            },
        )
```

**Why `source="macro"` and not a new `"regime"` Literal:** the `Signal.source` field is a fixed Literal (`signals.py:20`: `"market" | "sentiment" | "macro" | "arbitrage" | "yield"`). A regime overlay is semantically a *macro* input (cross-asset, slow, top-down), so it reuses the `macro` source rather than expanding the Literal — least-surface-area change, consistent with how `MacroAnalyst` already ingests external macro feeds. The regime-specific content lives in `extras` for the Portfolio/Risk Managers.

**How the de-risk flag flows:** `extras["de_risk"]` is read by the Risk Manager (role 8, `PLAN.md`) as a **hard trim signal** — when true across the sleeve, it overrides the PM's target weights toward the defensive core and stables. This is the same veto pathway as the LLM risk veto in `research/agents/43-llm-risk-veto.md`; the regime overlay is simply a *deterministic* contributor to that pathway.

**Cadence wiring:** the analyst is evaluated **once per week** (e.g. on the weekly UTC boundary, mirroring the calendar-aware logic in `research/agents/20-utc-flows.md`), and the resulting `Signal`s are cached and re-emitted unchanged on the intervening days. This keeps `combine_signals` (`signals.py:73`) seeing a stable regime view without daily churn.

---

## (g) Free data sources (consolidated)

| Input | Source | URL | Notes |
|---|---|---|---|
| BTC dominance (level + history) | CoinGecko | https://www.coingecko.com/en/charts/bitcoin-dominance | Free, no key; CSV/Excel export; also global chart https://www.coingecko.com/en/charts |
| BTC dominance (alt) | CoinMarketCap | https://coinmarketcap.com/charts/ | Free historical dominance chart |
| Altcoin Season Index | BlockchainCenter | https://www.blockchaincenter.net/en/altcoin-season-index/ | The canonical free index; 75% of top-50 beat BTC over 90d; historical stats published on-page |
| Top-50 prices (for ρ + reconstructed altseason) | CoinGecko | https://www.coingecko.com/en/all-cryptocurrencies | Free API (rate-limited); used to compute the 30d alt↔BTC correlation regime |
| Total / alt market cap | DefiLlama | https://www.defillama.com/ | Free, no key; stable-coins-vs-crypto splits for sanity-checking the regime label |
| Stablecoin market cap (risk-off proxy) | CoinGecko | https://www.coingecko.com/en/categories/stablecoins | Rising stablecoin share = risk-off confirmation |

**Cost note:** all inputs are free / key-less / rate-limited-friendly, matching the repo's existing data-frugal convention (`research/agents/04-data-edge.md`). No Glassnode/Santiment dependency is required for the *baseline* overlay — those only matter if you later add on-chain confirmation (optional, de-risk the late-altseason call).

---

## (h) Bottom line for Rapana
- **Do** deploy a **weekly `CrossAssetRegimeAnalyst`** that fuses BTC.D trend + altseason index + alt↔BTC correlation into a discrete regime label, emitted as a `macro`-source `Signal` with a `de_risk` flag in `extras`.
- **Ship the de-risk trigger first** (correlation ρ > 0.8, or altseason idx ≥ 75 sustained) — it is the highest-confidence, lowest-capacity-cost piece, and it flows through the existing Risk Manager veto path.
- **Add the exposure tilt second**, only after the de-risk flag clears the `deflated_best` drawdown-reduction gate out-of-sample. The tilt is a mild reweighting between the BTC/ETH core and the alt sleeve — never an all-in/all-out switch.
- **Do NOT** treat dominance or altseason as entry timers — they are regime descriptors with days-to-weeks of lag. The honest edge is **drawdown reduction + diversification timing**, not raw-return alpha.

---

## Evidence — URLs (consolidated)
- BlockchainCenter Altcoin Season Index (definition + historical stats: avg season ~486d, longest gap ~117d) — https://www.blockchaincenter.net/en/altcoin-season-index/
- CoinGecko Bitcoin Dominance chart + the four-quadrant regime interpretation + full 2014–2026 dominance history (2017 ICO ~38%, 2018 bear ~70%, 2020–21 DeFi/NFT ~60%, 2022 Terra/FTX spikes, 2024–25 ETF/Trump ~55%) — https://www.coingecko.com/en/charts/bitcoin-dominance
- CoinGecko Global Charts (total crypto market cap, BTC.D, stablecoin share, alt market cap) — https://www.coingecko.com/en/charts
- CoinMarketCap Historical Dominance chart — https://coinmarketcap.com/charts/
- DefiLlama (total/alt/stable market cap, free, no key) — https://www.defillama.com/
- Liu, Tsyvinski & Wu (2022), "Common Risk Factors in Cryptocurrency," *J. Finance* (the cross-section is market/size/momentum — **no dominance factor**, which is why dominance is a *regime* signal, not a cross-sectional factor) — https://www.nber.org/papers/w25882 · DOI https://doi.org/10.1111/jofi.13119
- Longin & Solnik (2001), "Extreme Correlation of International Equity Markets," *J. Finance* 56(2):649–676 (the canonical "correlations rise in crises / diversification breaks in the tail" result, generalized to crypto) — DOI https://doi.org/10.1111/0022-1082.00340

## Cited repo files
- `rapana/signals.py:17-46,73-84` (`Signal`, `MarketView`, `combine_signals`; source Literal at line 20)
- `rapana/agents/macro.py:13-31` (`MacroAnalyst` — the template the `CrossAssetRegimeAnalyst` mirrors)
- `rapana/agents/base.py` (`Analyst` base)
- `rapana/universe/scout.py` (price/volume fetch the correlation-regime computation reuses)
- `rapana/universe/ranker.py:77` (momentum/vol Scout — the regime overlay sizes the sleeve, not its contents)
- `rapana/backtest/validation.py` (`deflated_best`, `ValidationReport.is_significant` — the gate the tilt must clear)
- `rapana/config.py:57` (position-size cap the tilt respects)
- `research/agents/16-mexc-tos-envelope.md` (spot-only / low-freq envelope)
- `research/agents/34-cross-sectional-factors.md` §a (Liu–Tsyvinski–Wu; why dominance is regime, not factor)
- `research/agents/43-llm-risk-veto.md` (Risk Manager veto pathway the `de_risk` flag flows through)
- `research/agents/06-universe-edge.md` (Scout selection — overlay is orthogonal to it)
- `PLAN.md` (Risk Manager role 8; Portfolio Manager target weights)

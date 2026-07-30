# 23 — Options/futures expiry, max-pain & settlement effects as a spot BIAS/VETO on MEXC

**Agent:** 23/60 · **Scope:** Deribit BTC/ETH options + CME futures expiry mechanics, max-pain, and their documented (weak) effect on crypto *spot* — used purely as an **informational bias and risk veto** on MEXC spot trades. No futures/options trading anywhere; only **read-only public derivatives data** feeds an opinion about MEXC spot.
**Stance:** NON-standard, LOW-frequency (event-driven, monthly/quarterly cadence), explicitly **secondary signal**. This is a regime/veto layer, not a primary alpha source. Honest about how weak these effects are net of noise (§5).

All repo citations are `file:line`; external claims are URL-cited in §6. Where peer-reviewed crypto magnitudes don't exist, claims are flagged **[HYPOTHESIS → backtest]** against free public data.

---

## 1. The mechanism — what is supposed to move spot at expiry, and why it is weak

### 1.1 The three distinct (often conflated) effects
Crypto-twitter "expiry drives price to max-pain" is a mash-up of three different mechanisms. They must be separated because they have different signs, horizons, and evidence:

| Effect | Mechanism | Predicted spot drift | Strength in crypto |
|---|---|---|---|
| **(A) Pinning / gamma hedging** | Option market-makers (MMs) are short gamma near the strike; as expiry approaches they must *sell into rallies and buy into dips* to stay delta-neutral, damping price movement **toward the high-OI strike** | **Toward** the max-gamma strike (≈ max-pain when put/call OI balanced) | Real in equities (Ni–Pearson–Poteshman 2005); **plausible but contested** in BTC |
| **(B) Max-pain / "manipulation"** | Loose claim that large option holders (or the venue) push spot to the strike where the *aggregate* payout to option buyers is minimised (= max gain to writers) | **Toward** the max-pain price | Folk theory; the "manipulation" framing is not how liquid crypto venues work — no single actor has the balance sheet to move BTC spot to a strike |
| **(C) Settlement / roll flow** | CME futures expire last-Friday-of-month at the BRR (a spot-index print); Deribit options settle daily 08:00 UTC; positions must roll → directional order flow + herding | **Indirect** — raises *volume and cross-venue correlation*, not a guaranteed direction | The most robust crypto finding (Blasco 2022); see §2.1 |

**Key clarification:** effects (A) and (B) predict *convergence* to a strike/level; effect (C) predicts a *behavioural regime change* (herding, volume, volatility) without a deterministic direction. The crypto evidence is strongest for (C) and weakest/most noisy for (A)/(B). This is the single most important honesty point in the note and §5 returns to it.

### 1.2 The Deribit expiry calendar (the actual schedule to bias against)
Deribit settles options and futures **daily at 08:00 UTC**, but the *liquid, high-OI* expiries are the **last Friday of each month** (the "monthly"), with the big ones being **quarter-end** (last Friday of Mar/Jun/Sep/Dec). This is the standard "monthly/quarterly options expiry" the brief asks about. Deribit's own public `get_expirations` endpoint returns the live list (§4.1). CME BTC/ETH futures expire on the **same last-Friday cadence** at **15:00 London time (= 14:00 UTC during BST, 15:00 UTC otherwise)**, settled against the **CME CF Bitcoin Reference Rate (BRR)** — an aggregate of Bitstamp/Coinbase/itBit/Kraken/Gemini spot prints. The calendar coincidence is why both events are studied together.

### 1.3 Why "max-pain drift" is structurally weaker in crypto than equities
The equity max-pain/pinning literature (Ni–Pearson–Poteshman 2005; Avellaneda–Lipkin 2003) works because (a) single-name equity option MM gamma is large relative to the underlying's float turnover, and (b) the underlying cash market is concentrated on one listing venue where the MM's hedging flow is a non-trivial fraction. **Neither holds cleanly for BTC/ETH:**
- BTC spot is fragmented across 50+ venues; Deribit MM delta-hedges on Deribit perps + a handful of liquid spot venues, so the "pinning flow" is diluted across the order-flow of every venue, including MEXC.
- Deribit notional is large (~$20–40B notional OI on a typical month for BTC) but it is still a fraction of aggregate spot turnover; the gamma-to-spot-turnover ratio is lower than for a mid-cap stock.
- The 24/7, no-circuit-breaker, no-single-market-maker-of-last-resort structure means there is no institutional actor both willing and able to "defend" a strike.

This is why the literature review in §2 returns a **weak, contested, mostly-vanishing** directional effect, and why this note's strategy (§5) treats expiry as a *veto/regime flag*, not a directional alpha.

---

## 2. Empirical evidence — magnitudes, direction, durability

### 2.1 The one strong peer-reviewed crypto result: the "witching week" herding effect
**Blasco, Corredor & Satrústegui (2022), "The witching week of herding on bitcoin exchanges," *Financial Innovation* 8:26** (Springer, open access, cited 24×) — the most directly on-point peer-reviewed study. https://link.springer.com/article/10.1186/s40854-021-00323-4

- **Data:** hourly BTC prices/volume on 7 spot exchanges (Binance, Bitfinex, Bitstamp, Coinbase, itBit, Kraken, Gemini), Dec 2017 – Oct 2020, conditioned on **CME futures expiration** (last Friday of month).
- **Unconditional (whole sample):** *anti-herding* — exchanges normally move **less** together than a dispersion model predicts; investors act independently.
- **Pre-expiration:** significant **herding** appears from ~137 hours (~5–6 days) before expiry, peaking in the final 24h. This is the literal "witching week" of the title.
- **Volume effect (the cleanest number):** spot volume on the constituent exchanges rises **≈ +2% at the start of expiry week** and **≈ +5.5% in the final 24h before expiry**, then reverts at a similar pace post-expiry.
- **Post-expiration:** brief renewed herding from **+7h to +12h** after expiry (position re-opening), then reverts to anti-herding.
- **Robustness:** confirmed via quantile regression and the Christie–Huang (1995) alternative; robust to USD-vs-BTC volume weighting.

**Read-through for MEXC:** this is *not* a directional drift-to-max-pain result. It is a **regime/volatility/volume** result: in expiry week, BTC spot everywhere (MEXC included) becomes (a) higher-volume, (b) more cross-venue correlated, (c) more prone to mimetic spikes. Translation for rapana: **expect noisier spot, faster mean reversion of idiosyncratic MEXC deviations, and lower signal-to-noise on price-only TA during expiry week.** That is a *veto* signal (stand down / cut size), not a direction.

### 2.2 The directly-on-point BTC max-pain study (working paper, contested framing)
**Lachowicz (2025), "Do Gamma Walls Actually Move Bitcoin Prices at Deribit?" SSRN 5782822.** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5782822 (abstract confirmed via Google Scholar index; full text paywalled, magnitudes below are **[HYPOTHESIS → backtest]** pending re-derivation from free data, §4).

- Asks the exact question of effect (A): do large option OI concentrations ("gamma walls") at specific strikes pin BTC spot as expiry approaches, as they do for equities?
- Examines max-pain theory in the context of Bitcoin options expirations on Deribit and tests whether the spot index gravitates to the high-OI strike.
- **Headline (from abstract):** the effect exists *statistically* but is **economically small and dominated by spot's own volatility** for most of the sample — i.e. consistent with §1.3 (structural weakness in crypto). The title phrased as a question is itself the conclusion.

**[HYPOTHESIS → backtest]:** rapana can reproduce this for free (§4) on Deribit's public OI snapshot vs. BTC index, for the last-Friday-of-month expiries, and measure `|spot_at_expiry − max_pain| / spot` to get a concrete magnitude distribution. **Expect the median to be large (>1–2%, well outside any tradeable band net of fees)** — if so, max-pain is not a directional edge.

### 2.3 The equity max-pain literature (cross-asset reference)
The equity analog is the only place with peer-reviewed directional magnitudes, and even there it is contested:

- **Ni, Pearson & Poteshman (2005), "Stock Price Manipulation by Pre-Expiration Option Traders,"** *unpublished → circulated* — the foundational pinning paper. Finds that stocks with high option OI relative to trading volume exhibit a **"pinning to strike"** effect on expiration Fridays: realised volatility is suppressed and the stock gravitates to the nearest high-OI strike. Magnitude: the effect explains a *few per cent* of the daily variance for the most heavily-optioned names, negligible for the rest. (Cited as the canonical reference in Filippou et al. and most subsequent work.)
- **Avellaneda & Lipkin (2003)** — theoretical model of delta-hedging-induced pinning; the formal reason MMs damp movement toward the high-gamma strike. (Cited in Filippou et al. theoretical framework.)
- **Filippou, Garcia-Ares & Zapatero, "No Max Pain, No Max Gain: Stock Price Predictability at Options Expiration"** (PDF via algos.org). Builds a **Max-Pain decile strategy**: on the second week before expiration, sort stocks by a max-pain-distance metric, allocate into deciles, hold to expiry. **Result: a statistically detectable spread between top/bottom deciles, but net-of-cost edge is thin** and concentrated in small/illiquid names — exactly the names where pinning flow is a larger share of turnover. The crypto analog: if any edge exists it would concentrate in **mid/low-cap alts** with paper-thin spot books (the same universe rapana already targets, see `research/agents/17-mexc-smallcaps.md`), **not** BTC/ETH majors.
- **Pan & Poteshman (2006)** — extends the pinning result to informed-option-trading flow. (Cited in Filippou et al.)
- **Hu (2014)** — options-expiration and stock returns; documents that the effect is time-decaying and noisy at the daily level, reinforcing that **intraday/horizon discipline matters**.

**Net equity read-through:** the effect is real-but-small, horizon-critical (concentrates in the final hours), name-specific (high OI/turnover), and net-of-cost-thin. There is no reason to expect crypto to be *stronger* and several reasons (§1.3) to expect it *weaker*.

### 2.4 Bitcoin options-implied risk premia (corroborating context)
**Almeida, Grith, Miftachov & Wang (2024), "Risk Premia in the Bitcoin Market,"** arXiv:2410.15195 (econ.GN). https://arxiv.org/abs/2410.15195
- BTC options (Deribit) embed a large, regime-varying **variance risk premium** (VRP) — bigger than SPX's — split across volatility regimes.
- The options market is *informationally rich* (pricing kernels, implied densities) — i.e. **reading** Deribit options data is genuinely informative about the spot distribution, even if the *expiry* effect per se is weak.
- Supports the framing in §5: options OI / implied-vol *structure* is useful context; the literal "price → max-pain" drift is not.

### 2.5 Durability assessment
- **Settlement/roll herding effect (§2.1): durable.** It is driven by the calendar + institutional roll behaviour, both structural; not arbed away because it is a *behavioural* (second-order) effect, not a mispricing. Decay mode: as more volume migrates to 24/7 perps (vs dated futures), the "expiry event" sharpens; if anything the effect should *strengthen* modestly.
- **Max-pain drift (§2.2/§2.3): decaying/weak.** As crypto MMs professionalise and hedge more efficiently across venues, residual pinning flow dilutes further. Treat as a low-confidence bias, never a stand-alone signal.

---

## 3. What is readable for free (public, no key, no KYB) — the full data stack

This is the clean part: **every input the strategy needs is public and free**, mirroring the funding-rate pipeline in `research/agents/12-mexc-funding.md`. No MEXC futures access, no Deribit account, no CME subscription required.

### 3.1 Deribit public API (read-only, no auth)
Deribit's own docs (`docs.deribit.com`, fetched 2026-06-23) confirm these are **`Public`** methods usable without authentication. The exact endpoints the strategy needs:

| Endpoint | Returns | Use |
|---|---|---|
| `public/get_book_summary_by_currency?currency=BTC&kind=option` | per-instrument `open_interest`, `mark_price`, `mid_price`, `underlying_price`, `mark_iv` (https://docs.deribit.com/api-reference/market-data/public-get_book_summary_by_currency.md) | **OI per strike/expiry → compute max-pain & gamma walls** |
| `public/get_expirations?currency=BTC&kind=option` | array of expiration timestamps (https://docs.deribit.com/api-reference/market-data/public-get_expirations.md) | **Expiry calendar** — flag last-Friday-of-month, quarter-end |
| `public/get_last_settlements_by_currency?currency=BTC&type=delivery` | historical delivery/settlement events incl. `index_price`, `mark_price`, `position`, platform-aggregate `profit_loss`, `session_profit_loss` (https://docs.deribit.com/api-reference/market-data/public-get_last_settlements_by_currency.md) | **Backtest the effect**: match spot print at settlement vs. pre-expiry max-pain |
| `public/get_index_price?index_name=btc_usd` | Deribit BTC index (spot reference) | Fair-value anchor for the max-pain distance metric |

**Max-pain computation (free, deterministic from the OI snapshot):**
```
for each candidate settlement price S:
    total_writer_payout(S) = Σ_strikes [ open_interest(strike) * intrinsic_payout(S, strike, type) ]
max_pain = argmin_S total_writer_payout(S)        # strike minimising buyer payout
```
This is the textbook definition and is identical to what CoinGlass/Laevitas display for free (§3.3); computing it locally from Deribit's public OI removes any third-party dependency and gives a point-in-time audit trail.

### 3.2 CME public data (delayed, free)
- **CME CF Bitcoin Reference Rate (BRR)** — the settlement index, free on cmegroup.com and via CF Benchmarks. This is the *actual* print CME futures settle against.
- **CME "Pace of the Roll" tool** — free, daily-updated open-interest roll progression during each roll window, with a 20-roll historical average + IQR channel. https://www.cmegroup.com/markets/cryptocurrencies/paceofroll.html — directly visualises *when* the roll flow hits.
- **CME Crypto Historical Pricing tool** — free backtest feed using the CME CF Crypto Reference Rate. https://www.cmegroup.com/tools-information/quikstrike/cryptocurrency-historical-pricing.html
- **CME settlement calendar** — the last-Friday-of-month schedule + the quarterly "triple/quadruple witching" coincidences (futures + options + Micro options on same Friday).

### 3.3 Aggregators (free, no key) — for sanity-checking the local computation
- **CoinGlass** — free Deribit/Binance/OKX option OI, max-pain, gamma exposure (GEX) per expiry. https://www.coinglass.com/ (search "max pain Bitcoin"). Useful as a cross-check on the local Deribit OI computation; **do not** make it the only source — the local point-in-time compute is what the audit trail needs.
- **Laevitas** — Deribit options analytics, gamma profile, max-pain per expiry. https://laevitas.ch/ (free tier).
- **datamish / options charts** — secondary gamma/spot diagram cross-checks.

### 3.4 What is NOT needed (and what we explicitly do not touch)
- **No Deribit trading key** — read-only public market data suffices for every metric in this note.
- **No MEXC futures key** — the strategy trades MEXC *spot* only (or vetoes spot), as in `research/agents/16-mexc-tos-envelope.md` and `research/agents/12-mexc-funding.md`.
- **No cross-venue leg** — Deribit/CME are *read*; the only execution leg is a MEXC spot order indistinguishable from any other signal-driven order. This is the same single-leg discipline that keeps `research/agents/18-mexc-premium.md` ToS-clean.

---

## 4. Strategy — expiry proximity + max-pain as a BIAS/VETO on MEXC spot

### 4.1 The honest framing first
This is **not** "trade toward max-pain." The evidence in §2 does not support that as a stand-alone edge net of noise. Instead, the strategy uses derivatives-expiry as a **two-sided overlay**:

1. **VETO (risk-off) mode** — when expiry proximity + cross-venue herding is high, *reduce* confidence in other signals: spot is noisier, deviations are less sticky, and the cost of being whipsawed rises. This is the directly-supported use of the Blasco (2022) result.
2. **BIAS mode** — *only* when spot is far from max-pain *and* the expiry is a major quarterly *and* there is confirming gamma-wall structure, emit a weak directional bias *toward* max-pain. Treat this as a low-confidence vote, never a primary driver. This is the [HYPOTHESIS → backtest] part.

### 4.2 Decision rule (event-driven, evaluated per fleet cycle, low frequency)

| State | Trigger | MEXC spot action | Signal |
|---|---|---|---|
| **Expiry within 24h, quarterly or monthly** | `hours_to_expiry ≤ 24` AND expiry in `expirations(kind=option)` is last-Friday-of-month | **VETO new directional entries**; tighten stops on existing positions; cap size at 50% of normal | neutral (veto flag in `extras`) |
| **Expiry within 5–6 days (witching week)** | `24 < hours_to_expiry ≤ 144` | **Reduce confidence** of every other signal by ~25% (multiply `confidence` in `extras`); expect higher vol | neutral (regime flag) |
| **Far from expiry AND `|spot − max_pain| / spot > 3%` AND quarterly expiry ≤ 7d out** | the only directional case | **Weak bias toward max-pain** (mean reversion to the pinning level) | bullish if `spot < max_pain`, bearish if `spot > max_pain`, strength ≤ 0.3 |
| **Post-expiry +1h to +12h** | `0 < hours_since_expiry ≤ 12` | brief regime of renewed herding (Blasco §2.1) — **no new entries**, allow exits | neutral |

### 4.3 Sizing & cost
- **Never** size the directional bias leg above `0.5 × min(max_weight, |net|)` — it is a weak, contested effect and must not dominate the book.
- **Maker-preferred** entry/exit (the proposed `create_maker_order` path, `research/agents/08-mexc-client-edge.md:87-89`) — essential because the edge, if it exists, is in the single-digit-bp range and cannot survive taker cost.
- **Scope to majors only** for the directional bias (BTC, ETH) — Deribit options OI is deep enough there for max-pain to be meaningful. **Do not** apply the directional bias to alts with no liquid options market (max-pain is undefined/noisy). The expiry *veto*, by contrast, applies fleet-wide (BTC-led herding is contagious, §2.1).

### 4.4 Mapping to the `Signal` contract (`rapana/signals.py:17-46`)
The overlay emits one `Signal` per evaluated symbol, slots into the existing `source` set, and is consumable by `combine_signals` / `weighted_combine` (`signals.py:73-104`):

```python
# Inputs (all free, public, point-in-time):
#   spot            = MEXC BTC last price
#   max_pain        = computed from Deribit public OI snapshot (§3.1)
#   hours_to_expiry = nearest last-Friday-of-month Deribit expiry (quarterly/monthly)
#   is_quarterly    = expiry is last-Fri of Mar/Jun/Sep/Dec
dist = (spot - max_pain) / spot                       # +ve = spot above max-pain

# --- VETO / regime flags (always computed; stored in extras for the PM) ---
in_witching_week = 0 < hours_to_expiry <= 144
in_final_24h     = 0 < hours_to_expiry <= 24
in_post_expiry   = 0 < hours_since_expiry <= 12

# --- Directional BIAS: only in the narrow case §4.2 row 3 ---
emit_directional = (
    not in_final_24h and not in_post_expiry
    and hours_to_expiry <= 168        # within 7 days
    and is_quarterly                  # quarterly only — monthly effect is too weak
    and abs(dist) > 0.03              # spot at least 3% off max-pain
)

if emit_directional:
    direction = "bullish" if dist < 0 else "bearish"     # drift TOWARD max-pain
    strength  = min(abs(dist) / 0.10, 0.30)              # cap at 0.3 — weak signal
    confidence = 0.25                                     # honest: low prior
else:
    direction, strength, confidence = "neutral", 0.0, 0.0

Signal(
    symbol=spot_symbol,
    source="macro",          # expiry/macro-regime bucket (or add "derivatives" later)
    direction=direction,
    strength=strength,       # auto-clamped + sign-corrected by Signal.__post_init__
    confidence=confidence,
    rationale=(f"expiry overlay: hours_to_expiry={hours_to_expiry:.0f}, "
               f"max_pain_dist={dist:+.2%}, veto={'final24h' if in_final_24h else 'witching' if in_witching_week else 'post' if in_post_expiry else 'off'}"),
    extras={
        "max_pain": max_pain, "max_pain_dist": dist,
        "hours_to_expiry": hours_to_expiry, "is_quarterly": is_quarterly,
        "veto_final_24h": in_final_24h, "veto_witching_week": in_witching_week,
        "regime_post_expiry": in_post_expiry,
        "source_policy": "expiry_veto+vweak_directional_bias",
    },
)
```

Notes:
- `source="macro"` reuses an existing bucket (`signals.py:21`); the veto nature (neutral direction, information in `extras`) means it contributes nothing to `net_score` directly (`combine_signals` excludes neutral signals, `signals.py:80`), which is **correct** — the veto is consumed by the PM/portfolio layer reading `extras`, not by the score combiner. This matches the fail-soft / informational design of `feeds/base.py`.
- The directional bias, when emitted, is capped at `strength=0.3, confidence=0.25` → `weighted_score ≤ 0.075` (`signals.py:44-46`), a deliberately tiny vote so it can never flip a book on its own. `ReflectionMemory` (`fleet/memory.py`) can down-weight `source="macro"` further if the OOS hit rate is poor — which is exactly the learnable safety valve this weak effect needs.
- **[HYPOTHESIS → backtest]:** the `0.03` distance threshold, `0.30` strength cap, and `0.25` confidence are priors, not fitted values. They must be validated (or re-fitted, with Deflated-Sharpe discipline like `backtest/funding_spike.py:370`) against a backtest that pairs Deribit OI snapshots with MEXC spot prints for the last 2–3 years of monthly expiries. **Until that backtest passes, ship the VETO only and emit neutral for the directional leg.**

### 4.5 How the pieces fit (research track today, no new auth surface)
```
Deribit public API ─┐
   get_book_summary │
   get_expirations  ├→ compute max_pain + hours_to_expiry
   get_last_settl.  │       (rapana/feeds/expiry.py — new, mirrors feeds/market_premium.py)
                    │
CME Pace-of-Roll ───┘       ↓
                    ExpiryAnalyst.analyze(symbol) → Signal(source="macro", extras={veto flags})
MEXC spot ticker ──────────────────────────────────┘
                                                        ↓
                              PortfolioManager reads extras.veto_* → cuts size / blocks entries
                              (fleet/orchestrator.py PM path, single-leg MEXC spot)
```
No new secrets, no Deribit key, no MEXC futures key. The only new code is one `Feed` (mirror of `feeds/market_premium.py`) and one `Analyst` (mirror of `agents/arbitrage.py:13-34`) — additive, no core rewrite, exactly the pattern proven in `research/agents/18-mexc-premium.md:133-176`.

---

## 5. Honesty caveat — how weak this is, stated plainly

This is the most important section and is intentionally blunt:

1. **The directional max-pain drift is, on the best available evidence, not a stand-alone tradeable edge in BTC/ETH.** The Lachowicz (2025) paper exists *because* the effect is in doubt; its title is a question. The equity analog (Ni–Pearson–Poteshman 2005; Filippou et al.) survives only as a small, name-specific, horizon-critical anomaly net-of-cost. **Nobody has published a peer-reviewed crypto max-pain drift result that survives transaction costs at retail cadence.** Treat the directional leg of §4 as speculation that must pass a Deflated-Sharpe backtest before going live.
2. **The "expiry-week effect" that IS robust is behavioural, not directional.** Blasco (2022) shows herding + ~5.5% volume in the final 24h — that is a *noise/regime* finding. Using it as a VETO (reduce size, expect whipsaw) is evidence-supported; using it as a "spot will go X" directional bet is not.
3. **Max-pain computation can be gamed by stale/illiquid option prints.** A single far-OTM strike with a fat stale quote can move the computed max-pain by hundreds of dollars. The implementation must filter to liquid strikes (bid > 0, volume in last 24h > threshold) and ideally re-compute via CoinGlass/Laevitas as a cross-check (§3.3). Bad max-pain inputs would silently destroy the directional leg.
4. **Quarterly ≠ monthly.** The effect (if any) concentrates at quarter-end when futures + options + Micro options all expire the same Friday ("quadruple witching"). Monthly expiries are weaker; weekly/daily Deribit settles are noise for this purpose. The directional rule (§4.2 row 3) is quarterly-only for a reason — do not relax this without re-validation.
5. **MEXC is not a CME-BRR constituent.** The CME settles against Bitstamp/Coinbase/itBit/Kraken/Gemini — MEXC is *not* in that basket. So MEXC spot at CME expiry is a noisy cousin of the actual settlement print; expect the herding/volume effect to reach MEXC (it is cross-venue, Blasco §2.1) but any *pinning* of MEXC specifically to be weaker than for the constituent venues.
6. **Publication bias.** The crypto-expiry literature is thin and skewed toward "we found an effect" abstracts; the working-paper status of the most on-point BTC max-pain study (Lachowicz 2025) and the paywall on its magnitudes is itself a yellow flag. Prefer the peer-reviewed, data-rich Blasco (2022) result as the load-bearing claim.
7. **Bottom line on confidence:** ship the **VETO** with high confidence (it is a defensive use of a well-documented behavioural regime). Ship the **directional BIAS** with low confidence and only after the §4.4 backtest passes the same Deflated-Sharpe gate the funding fade already passes (`backtest/funding_spike.py:370`).

---

## 6. Sources (verified, load-bearing)

**Primary crypto (peer-reviewed / on-point):**
- **Blasco N., Corredor P., Satrústegui N. (2022), "The witching week of herding on bitcoin exchanges,"** *Financial Innovation* 8:26 (Springer, open access) — https://link.springer.com/article/10.1186/s40854-021-00323-4 · the load-bearing peer-reviewed result (§2.1): herding + ~5.5% volume in final 24h pre-CME-expiry, anti-herding otherwise.
- **Almeida C., Grith M., Miftachov R., Wang Z. (2024), "Risk Premia in the Bitcoin Market,"** arXiv:2410.15195 [econ.GN] — https://arxiv.org/abs/2410.15195 · BTC options-implied risk premia; corroborates that Deribit options data is informationally rich even though the *expiry drift* is weak.

**Primary crypto (working paper, contested):**
- **Lachowicz P. (2025), "Do Gamma Walls Actually Move Bitcoin Prices at Deribit?"** SSRN 5782822 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5782822 · directly tests BTC max-pain/gamma-wall pinning at Deribit; the title-as-question framing is itself the conclusion (effect statistically present, economically small).

**Cross-asset equity max-pain / pinning (foundational):**
- **Ni S.X., Pearson N.D., Poteshman A.M. (2005), "Stock Price Manipulation by Pre-Expiration Option Traders."** — the canonical pinning paper (cited in Filippou et al.; listed in Filippou PDF bibliography).
- **Avellaneda M., Lipkin A. (2003)** — theoretical delta-hedging pinning model (cited in Filippou et al.).
- **Pan J., Poteshman A.M. (2006)** — informed option trading & pinning (cited in Filippou et al.).
- **Filippou I., Garcia-Ares P.A., Zapatero F., "No Max Pain, No Max Gain: Stock Price Predictability at Options Expiration"** — https://www.algos.org/api/v1/file/e79b035a-25b7-4fd8-9f09-986930343fa4.pdf · Max-Pain decile strategy in equities; thin net-of-cost edge, concentrated in illiquid names.

**Free public data sources (verified reachable):**
- **Deribit API docs** — https://docs.deribit.com/ (fetched 2026-06-23). Specific public endpoints: `public/get_book_summary_by_currency` (OI, mark, mid per instrument) — https://docs.deribit.com/api-reference/market-data/public-get_book_summary_by_currency.md ; `public/get_expirations` (expiry calendar) — https://docs.deribit.com/api-reference/market-data/public-get_expirations.md ; `public/get_last_settlements_by_currency` (delivery/settlement history with platform-aggregate P&L) — https://docs.deribit.com/api-reference/market-data/public-get_last_settlements_by_currency.md . All `Public`-tagged (no auth).
- **CME CF Bitcoin Reference Rate (BRR)** & **Pace of the Roll** tool (free, daily-updated roll OI progression with 20-roll historical IQR) — https://www.cmegroup.com/markets/cryptocurrencies/paceofroll.html .
- **CME Crypto Historical Pricing tool** (free backtest feed) — https://www.cmegroup.com/tools-information/quikstrike/cryptocurrency-historical-pricing.html .
- **CoinGlass** & **Laevitas** — free Deribit option OI / max-pain / GEX per expiry (cross-check only, not primary).

**Repo priors (cross-referenced):**
- `research/agents/12-mexc-funding.md` — the template: free public derivatives data → low-freq `Signal` → Deflated-Sharpe gate (`backtest/funding_spike.py:370`).
- `research/agents/18-mexc-premium.md` — single-leg informational trade discipline, ToS-clean reading of cross-venue public data.
- `research/agents/16-mexc-tos-envelope.md` & `research/agents/08-mexc-client-edge.md` — the MEXC anti-bot envelope; this strategy stays inside it by being low-freq, maker-preferred, single-leg spot.
- `rapana/signals.py:17-46` — `Signal` contract (source/direction/strength/confidence/extras, auto-clamped).
- `RESEARCH-SYNTHESIS.md:90,108,110` — the MEXC anti-bot / freeze constraint that vetoes any cross-venue arb or HFT framing.

---

## Bottom line

The **directional** max-pain drift (spot → max-pain) is a weak, contested, mostly-vanishing effect in BTC/ETH with no peer-reviewed retail-net-of-cost result — use it only as a tiny quarterly-only bias, and only after a Deflated-Sharpe backtest against free Deribit OI + MEXC spot. The **robust** finding is Blasco (2022)'s "witching week": expiry-week herding + ~5.5% volume in the final 24h pre-CME-expiry — use *that* as a high-confidence **veto** (cut size, expect noise, block new entries in the final 24h and in the +7–12h post-expiry re-opening window). All inputs are free and read-only (Deribit public API + CME BRR/Pace-of-Roll + CoinGlass cross-check); the only execution leg is a single slow maker MEXC spot order, ToS-clean by construction.

# 37 — Funding-rate carry / cash-and-carry basis: the spot-only remnant

**Agent:** 37/60 · **Scope:** the academic **carry / basis literature** applied to rapana — what survives once the classic cash-and-carry arb is removed by policy (MEXC spot-only, futures KYB-gated, no symmetric hedging).
**Stance:** NON-standard, low-frequency (daily–weekly rebalance), **spot-only portfolio-tilt** overlay. This is **not** a perp fade (agent 12), not a cross-venue crowding z-score (agent 29), not a liquidation bounce (agent 30) — it is a **cross-sectional selection/rotation** that uses funding as a *crowding penalty* in the universe ranker. No arbitrage, no perp leg, no hedging — strictly inside the MEXC spot envelope (`research/agents/16-mexc-tos-envelope.md`).

All citations are `file:line` for repo code and bare URLs for external sources. Where peer-reviewed magnitudes for the *spot-only selection* variant do not exist, this is flagged **[HYPOTHESIS → backtest]** against the repo's free, key-less funding feed. No vibes presented as fact — same discipline as `research/agents/12-mexc-funding.md`.

---

## 1. The honest starting point — what the brief removes, and why it matters

The brief is explicit and correct: **classic cash-and-carry (long spot + short perp of the same coin) is symmetric-hedged arbitrage** — it is **BANNED on MEXC retail** and the perp leg is **KYB-gated** (`research/agents/08-mexc-client-edge.md:77`; MEXC's 2026-05-26 anti-bot policy, https://www.mexc.com/support/articles/17827791531135). That is the *entire* mechanism the carry literature is about. So before anything else, two load-bearing facts from the repo itself:

1. **The delta-neutral carry book is already implemented AND already failed the honest gate.** `rapana/backtest/carry.py:1-7` defines the strategy as *"A delta-neutral book — short perp + long spot of the same coin — has ~zero price exposure and collects the perpetual funding rate each interval"* and the harness asks *"Does harvesting funding beat CASH, net of all costs, out-of-sample?"* The carry family is listed among the edges that **"all failed the honest gate"** (`funding_spike.py:3-4`). So even *with* the perp leg, blind funding harvest had no net edge here. The carry **income leg is not just policy-banned — it is already empirically dead in this repo** (basis drag + 2-leg taker cost ate it).
2. **Therefore the only spot-actionable remnant of the carry thesis is the reversion leg**, which is *directional*, not hedged — and directional reversion is exactly what agents 12 / 29 / 30 already trade. The question this agent answers is narrower and distinct: *can funding be used not as a per-symbol timing signal (12/29) but as a **cross-sectional selection / rotation weight** for the spot book?*

That is the clean division of labor: **12/29 = per-symbol fade; 30 = event reversion; 37 = portfolio tilt.** Same reversion mechanism, three different surfaces.

---

## 2. The carry anomaly — does high-funding systematically predict under/over-performance?

The academic answer is *yes, but the edge you can keep is the reversion, not the carry.* Three independent lineages:

### 2.1 The no-arb-control view (funding is *designed* to mean-revert)
- **He, Manela, Ross & von Wachter (2024), "Fundamentals of Perpetual Futures"** (arXiv:2212.06888, *Ledger*) — the standard reference. Derives no-arb bounds for perps, shows deviations are *"larger than in traditional currency markets, comove across currencies, and **diminish over time**,"* and that *"an implied arbitrage strategy yields high Sharpe ratios."* Two findings are load-bearing here: (a) the deviations **comove cross-sectionally** — funding is a *system-wide* crowding signal, not a per-coin idiosyncrasy (this is the theoretical hook for cross-sectional selection); (b) **the basis has been decaying over years** — the structural carry trade is being arbed away, so the *income* leg is shrinking while the *reversion* leg persists as long as the funding mechanism exists.
  - URL: https://arxiv.org/abs/2212.06888
- **Angeris, Chitra, Evans & Lorig (2022), "A primer on perpetuals"** (arXiv:2209.03307, q-fin.MF) — model-free replication: funding is the *carrying cost that makes a perp replicable by a rolling spot+cash position*. This is the formal statement that funding = basis = expected reversion; it is also the formal statement that capturing it *requires the hedge* (which spot-only forgoes).
  - URL: https://arxiv.org/abs/2209.03307
- **Kim & Park (2025), "Designing funding rates for perpetual futures"** (arXiv:2506.08573, q-fin.MF) — proves via path-dependent infinite-horizon BSDEs that a well-designed funding rate is the **no-arbitrage boundary** that re-anchors the perp to spot. The venue's own pricing kernel *demands* reversion when funding is extreme — by construction, not by coincidence.
  - URL: https://arxiv.org/abs/2506.08573

### 2.2 The causal-direction view (funding precedes price)
- **Nimmagadda & Ammanamanchi (2019), "BitMEX Funding Correlation with Bitcoin Exchange Rate"** (arXiv:1912.03270, q-fin.ST) — the most directly on-point *predictive* paper. Establishes that funding is **heteroskedastic** (extremes cluster — the persistence that makes reversion tradeable at low frequency), and that funding **Granger-causes** the perp price at short lags. The causal arrow funding→price-revert is what a selection overlay is silently betting on whenever it tilts toward low/negative-funding names.
  - URL: https://arxiv.org/abs/1912.03270

### 2.3 Cross-sectional / data-honesty caveats
- **Giagkiozis & Said (2024), "Reconciling Open Interest with Traded Volume in Perpetual Swaps"** (*Ledger* 9, arXiv:2310.14973) — documents that **OI and liquidation feeds are systematically misreported/delayed** by major derivatives venues. Funding *settlements* are not in this fault class (they are signed, persisted, settled), so funding is the reliable input; but if the selection overlay ever weights by OI, cap any single venue's weight (mirror agent 29's `MAX_VENUE_WEIGHT = 0.6`).
  - URL: https://arxiv.org/abs/2310.14973

### 2.4 Synthesis — what is solidly known vs flagged
| Claim | Status | Source |
|---|---|---|
| Extreme funding is the no-arb boundary; reversion is *built-in* | **SOLID (theoretical)** | He 2024; Angeris 2022; Kim & Park 2025 |
| Funding Granger-causes short-horizon price reversion | **SOLID (empirical, BTC)** | Nimmagadda 2019 |
| The basis/carry income has been **decaying** as the market matures | **SOLID (empirical)** — *"diminish over time"* | He 2024 |
| Cross-sectionally, low-funding coins outperform high-funding coins | **[HYPOTHESIS → backtest]** — the cross-currency *comovement* of deviations is shown (He 2024) but a peer-reviewed *cross-sectional funding-rank spot long-only return* table is not. This is the exact gap `_rank_funding_signal` in `cross_sectional.py:189-205` was built to test. |
| A specific bp/yr spot-tilt alpha from funding-rank | **[HYPOTHESIS → backtest]** — no published figure; measure on the repo's free funding series |

---

## 3. Honest capture — what spot-only can and cannot keep

### 3.1 What you forgo (be explicit, do not bury it)
On spot-only, with no perp leg, you **forfeit every property that made classic carry attractive**:
- **No funding income.** You collect zero basis/funding. The "+15 bp per 8h just for holding the fade" floor that props up agent 12's perp fade (`research/agents/12-mexc-funding.md:71-76`) does **not exist** here. There is no cushion if reversion is slow.
- **No delta neutrality.** You are running a **directional spot book** — you eat the full price variance of the names you hold. Carry's whole appeal was ~zero price exposure; spot-only carry-aware selection is just *informed directional investing* with funding as a feature, not a hedge.
- **No anti-correlated second leg.** Agent 12's structural edge is that the funding leg and the price leg are *anti-correlated at the extremes* (one pays when the other doesn't, `12-mexc-funding.md:81-82`). Spot-only has one leg only — no insurance.

### 3.2 What you keep — the reversion leg, expressed as *selection*
Spot-only carry-aware selection is, transparently, **the same directional reversion bet as agents 12/29/30, but placed at the *portfolio-construction* layer instead of the *per-symbol signal* layer**:

- Where 12/29 say *"this coin's funding is extreme → trade this coin,"* agent 37 says *"across the universe, tilt weight toward low/negative-funding coins (crowded-short → expected bounce) and away from high/positive-funding coins (crowded-long → expected fade)."*
- The mechanism underwriting both is identical: Nimmagadda's Granger funding→price + He/Kim-Park's no-arb boundary. The difference is purely the *expression surface*.

### 3.3 Overlap confirmation (the brief asked: confirm/distinct vs 12/29)
| Agent | Input | Expression | Surface | Carry income? |
|---|---|---|---|---|
| **12** MEXC funding | MEXC funding | per-symbol **perp** fade (needs KYB) | timing | **YES** (the double payoff) |
| **29** cross-venue funding | 4-venue agg funding z | per-symbol **spot** contrarian | timing | no (spot) |
| **30** liquidation flush | funding+OI+price+vol | per-symbol **spot** post-flush | event timing | no (spot) |
| **37** carry-basis (this) | cross-sectional funding rank | **portfolio weight tilt** across universe | **selection/rotation** | no (spot) |

**Confirmed overlap:** 37 shares the reversion mechanism with 12/29/30 — it is *not* a new alpha family, it is a different *deployment* of the same one, and should be calibrated so it does not double-count funding crowding in the combined `net_score` (see §5.4).

**Distinct value:** 37 is the only one that expresses a **relative-value / cross-sectional** view ("hold the basket of less-crowded coins"). Single-symbol analysts (12/29/30) structurally cannot say "rotate *from* A *to* B"; 37 can. The repo's own `_rank_funding_signal` (`cross_sectional.py:189-205`, comment *"long lowest latest funding"*) is the literal prototype of this view — already built as a backtest, never wired live.

---

## 4. Selection-overlay strategy — `CarryAwareRanker`

### 4.1 What it does (and the one-line reason it is *not* arbitrage)
The ranker computes a **funding crowding penalty** per universe symbol and folds it into the existing `universe/ranker.py` score as a *tilt* (typically ±10–20 % weight), then the portfolio holds the top-N. There is **no opposite-side position, no hedge, no simultaneous buy+sell** — you simply *prefer* less-crowded names. That is the textbook distinction between a **selection factor** (legal on spot) and an **arbitrage** (banned): a factor changes *which* longs you hold; an arb holds *both* sides. Carry-aware selection is the former.

### 4.2 Signal direction (asymmetric, mirror the spot truth in §6 of agent 29)
Because spot cannot short, the carry-aware tilt is **directionally asymmetric** and must be encoded honestly:

| Funding regime | Crowding read | Spot selection action | Expressible? |
|---|---|---|---|
| **Strongly negative** (crowded short) | expected **up-revert** | **Over-weight** the coin in the spot book | **Fully** — a long you can take from cash |
| **Near zero** | unremarkable | neutral weight | n/a |
| **Strongly positive** (crowded long) | expected **down-revert** | **Under-weight / exclude** the coin; **do not initiate** | **Partially** — only acts if you would otherwise hold it (de-risk / avoid); cannot profit from a name you don't own |

This is the *exact* asymmetry agent 29 §6 derives for the per-symbol case, transplanted to the portfolio layer: the **negative-funding (over-weight) side is the strong, actionable side**; the positive-funding (under-weight) side is a veto/exclusion, not a profit center.

### 4.3 Threshold via cross-sectional rank, not raw bp
For a *selection* factor the principled quantity is a **cross-sectional rank/quantile**, not an absolute bp level (a per-symbol signal wants bp; a portfolio factor wants *relative* crowding). Use the bottom/top decile of the universe's latest settled funding:

```
f_t(sym)      = latest SETTLED funding strictly before t  (point-in-time, funding_spike.py:176-188)
rank_t(sym)   = cross-sectional percentile of f_t across the live universe, in [-1, +1]
crowd_score   = -rank_t(sym)                 # negative funding (crowded short) -> positive tilt
# optional winsorize: clip at ±0.2 of the universe's |funding| extreme to avoid one outlier coin dominating
```
- **Over-weight** the **bottom-decile** (most negative funding, crowded-short) names; **exclude/under-weight** the **top-decile** (crowded-long).
- **Agreement veto (reuse 29's discipline):** in a multi-venue build, require ≥3/4 venue sign-agreement before letting a single-venue print move the rank; on the MEXC-only default, accept the single-venue funding but flag it as lower-confidence.
- **Cadence:** rebalance **daily to weekly** (funding settles every 8h but cross-sectional ranks are sticky; over-frequent rebalance just pays spread). This is well inside MEXC's low-freq maker envelope.

### 4.4 Magnitude priors (honest — **[HYPOTHESIS → backtest]**)
| Quantity | Prior | Why |
|---|---|---|
| Funding-rank cross-sectional spot long-only alpha | **[HYPOTHESIS → backtest]** — no published bp/yr figure | He 2024 shows comovement + the implied perp arb has "high Sharpe"; the *spot long-only tilt* return is unmeasured |
| Horizon of the tilt's edge | days–weeks (rank stickiness) | Nimmagadda's funding persistence + He's slow basis decay |
| Decay of the edge | **structural, monitor** | He 2024 *"diminish over time"* — re-validate the ranker's IC annually; expect secular shrink |

---

## 5. `CarryAwareRanker` — Signal & ranker spec

### 5.1 Where it plugs in (no core rewrite)
Two clean options, both additive:

1. **Selection-layer (preferred):** fold `crowd_score` into `rapana/universe/ranker.py` as an additional factor with a small weight, so the *universe itself* tilts toward less-crowded names before any per-symbol analyst runs. This is where a cross-sectional view belongs (single-symbol `Analyst.analyze` cannot express it, `research/agents/01-strategy-edge.md:240-247`).
2. **Signal-layer (fallback):** emit a `Signal(source="yield", …)` per symbol whose `strength` is the `crowd_score`, letting `combine_signals` (`signals.py:73-84`) tilt the per-symbol consensus. Lower-friction (no ranker change) but loses the explicit "rotate from A to B" framing — it tilts each coin independently.

### 5.2 Selection-layer spec (preferred path)
```python
# rapana/universe/ranker.py  (extend existing ranker; funding from store)
def carry_aware_tilt(symbol, funding_series, universe_funding, t):
    f_sym = latest_settled_before(funding_series, t)          # point-in-time
    rank  = cross_sectional_percentile(f_sym, universe_funding)  # in [-1,+1]
    return -rank   # crowded-short (negative funding) -> over-weight
# fold into the composite rank score with weight w_carry (start 0.10–0.15)
```

### 5.3 Signal-layer spec (fallback / audit path) — maps to `rapana/signals.py:17-46`
```python
# crowd_score from §4.3, clipped to [-1,1]
if crowd_score > 0:                      # crowded short -> bullish tilt
    direction, strength = "bullish", min(crowd_score, 0.6)   # capped: pure-reversion, no carry cushion
elif crowd_score < 0 and already_held:   # crowded long -> only a de-risk veto, never a short
    direction, strength = "bearish", max(crowd_score, -0.4)  # weaker: can only trim, not profit
else:
    direction, strength = "neutral", 0.0
Signal(
    symbol=symbol,
    source="yield",               # funding/carry family (signals.py:21)
    direction=direction,
    strength=strength,            # sign/clip enforced by Signal.__post_init__ (signals.py:27-41)
    confidence=0.3,               # capped: hypothesis-stage, no carry cushion, overlaps 12/29/30
    rationale=f"cross-sectional funding rank={rank:+.2f}; crowd={'short' if rank<0 else 'long'}; "
              f"{'over-weight (bounce)' if rank<0 else 'under-weight/exclude (fade)'}",
    extras={"funding_rate": f_sym, "xs_rank": rank,
            "leg": "reversion_only",          # HONEST: no carry income on spot
            "source_policy": "xs_funding_rank_decile",
            "validated": False},              # flip True only after §6 backtest passes DSR
)
```
Notes:
- `source="yield"` reuses the existing bucket (`signals.py:21`). Because this is the **same funding signal** 12/29/30 emit, the combiner will co-add them — set `confidence` low (0.3) until the cross-sectional variant is independently validated, to avoid implicitly double-counting crowding. If a dedicated `"funding"` source is added later, register a `source_weights` entry (`signals.py:87-103`).
- `confidence=0.3` and `validated=False` are **load-bearing:** the carry-income leg is dead (`carry.py:1-7`) and the reversion leg is already spoken for by 12/29/30. This agent's incremental value (the cross-sectional *tilt*) is **un-backtested**, so it must start as a weak opinion the reflection loop (`memory.py:114`) can shrink, never a primary driver.

### 5.4 Touch points (file:line)
| Change | Where |
|---|---|
| Selection factor (preferred) | `rapana/universe/ranker.py` (add `carry_aware_tilt`, weight `w_carry`) |
| Fallback Signal path | new `rapana/agents/carry_aware.py` mirroring `agents/base.py:Analyst` |
| Funding input (already wired) | `store.fetch_funding_range` via `rapana/mexc/client.py:195` (key-less, public) |
| Cross-sectional prototype to promote | `_rank_funding_signal` / `_latest_funding` (`cross_sectional.py:180-205`) |
| Combiner unchanged | `combine_signals` (`signals.py:73`), `weighted_combine` (`signals.py:87`) |
| Validation harness to write | `backtest/carry_aware_tilt.py` (mirror `funding_spike.py`, see §6) |

---

## 6. Validation gate (mandatory before any live tilt weight > 0.1)

The spot-only carry-aware **tilt specifically is un-backtested.** The repo has the *per-symbol* funding fade validated (`funding_spike.py:370` Deflated-Sharpe PASS) and the *cross-sectional funding-rank* prototype (`cross_sectional.py:189-205`) — but **not** the "spot long-only book tilted by cross-sectional funding rank, benchmarked vs equal-weight universe, net of cost, out-of-sample." Mandatory sequence:

1. **Write `backtest/carry_aware_tilt.py`** reusing `cross_sectional.py`'s machinery + `funding_spike.py`'s discipline: point-in-time firewall (decide from funding settled strictly *before* `t`), separate `gross_reversion` from cost, **benchmark vs EQUAL-WEIGHT universe of the same names** (not cash — the correct null for a selection factor is the un-tilted book, otherwise you conflate "funding ranks" with "being long crypto at all").
2. **PASS = Deflated Sharpe > 0.95 AND tilted OOS net beats equal-weight OOS net** (mirror `funding_spike.py:370`). Pre-commit the tilt-weight ladder (`w_carry ∈ {0.05, 0.10, 0.20}`) to avoid post-hoc mining, exactly as `funding_spike.py:79-84` pre-commits the fade ladder.
3. Only on PASS: raise `w_carry` and/or flip `Signal.extras["validated"]=True`. **Decay monitor:** log annual cross-sectional IC of funding-rank vs forward spot return; He 2024's *"diminish over time"* predicts secular shrink — widen the decile band or cut `w_carry` if IC trends toward zero.

Until then, run the ranker **paper-only** — it tilts a shadow book, the human executes on the MEXC UI, zero freeze risk (same C1/C2 track as 12, `12-mexc-funding.md:116`).

---

## 7. KYB boundary (the non-negotiable)

- **Spot-only = the hard envelope.** The carry-aware tilt trades MEXC **spot** only (`16-mexc-tos-envelope.md`). It contains **no perp position, no short, no simultaneous buy+sell, no hedge.** It is a *factor*, not an *arb*, by construction.
- **Funding is READ for free, key-less.** `MexcFuturesClient` defaults to `authenticated=False` (`client.py:181`); `fetch_funding_rate_history` paginates the public endpoint with a point-in-time firewall (`client.py:195-256`). The whole research + selection pipeline runs on a no-key connection today (`12-mexc-funding.md:86-94`). Reading funding does **not** require KYB.
- **Capturing the carry *income* requires KYB.** The moment you want the actual funding payment (short perp + long spot), you cross into futures live trading — KYB + qualification review + a Contract-scoped key set (`08-mexc-client-edge.md:77,95-97`). That path is agent 12's domain, **not** this agent's. **Never** reuse the spot key for a futures client (`mexc/__init__.py:6-21` returns one shared cred — the split-auth fix is a precondition to any perp work).
- **Spot automation itself is gray-zone.** Even spot-only API trading is frequency-policed by MEXC. The daily–weekly, maker-oriented, single-direction rebalance of a *selection* factor is the polar opposite of HFT/arb (`12-mexc-funding.md:118`) — but the policy is frequency-agnostic ("bot trading" is restricted, full stop). Treat low-freq spot execution as a human-accepted risk, not a default, and prefer the research/paper + human-UI-execution track until KYB is in hand.

---

## 8. Bottom line

- **Classic carry is doubly unavailable here:** it is policy-banned on MEXC retail (spot-only, futures KYB-gated, no symmetric hedging) *and* the repo's own delta-neutral carry book **already failed** the honest gate (`carry.py:1-7`, `funding_spike.py:3-4`) — basis drag + 2-leg cost ate the funding income even with the perp leg present. The **carry-income leg is gone**; do not pretend otherwise.
- **What survives is the reversion leg**, and its spot-only expression as a **cross-sectional selection/rotation tilt** — over-weight bottom-decile (negative funding, crowded-short) coins, under-weight/exclude top-decile (crowded-long). The mechanism is multiply-corroborated (He 2024 no-arb + comovement; Nimmagadda 2019 Granger funding→price; Kim & Park 2025 boundary) and the prototype `_rank_funding_signal` already exists (`cross_sectional.py:189-205`).
- **Honest boundary:** spot-only forgoes funding income, delta-neutrality, and the anti-correlated second leg — it is **informed directional investing with funding as a feature, not a hedge.** Asymmetric like agent 29 §6: actionable on the over-weight (crowded-short) side, veto-only on the under-weight (crowded-long) side. Distinct from 12/29/30 (per-symbol/event timing) because it operates at the **portfolio-selection** layer — the only one that can express "rotate from A to B."
- **Ship as paper-only until `backtest/carry_aware_tilt.py` passes Deflated Sharpe vs equal-weight universe.** Start `w_carry ≈ 0.10`, `confidence=0.3`, `validated=False`; expect secular decay (He 2024 *"diminish over time"*) and re-validate annually. No KYB, no perp, no hedge — strictly inside the spot envelope.

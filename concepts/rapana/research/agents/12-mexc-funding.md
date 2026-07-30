# 12 — Funding-rate crowding as a contrarian signal on MEXC perpetuals

**Agent:** 12/60 · **Scope:** MEXC perp funding rate as a contrarian fade signal — mechanism, evidence, the "double payoff", strategy spec, and an honest KYB/feasibility verdict.
**Stance:** NON-standard, low-frequency (8h cadence), event-driven overlay. Builds directly on the existing `backtest/funding_spike.py` Deflated-Sharpe-validated fade. No HFT, no sub-second race.

All citations are `file:line` for repo code and bare URLs for external sources. Where peer-reviewed magnitudes do not exist, this is flagged **[HYPOTHESIS → backtest]** against the repo's free, read-only funding feed. No vibes presented as fact.

---

## 1. Mechanism — why crowded funding should mean-revert

A perpetual swap has no expiry, so the venue keeps the perp glued to spot via a **funding rate**: when the perp trades above spot (premium), longs pay shorts (`funding > 0`); when it trades below, shorts pay longs (`funding < 0`). MEXC settles funding every **8 hours** (00:00 / 08:00 / 16:00 UTC) — this cadence is hard-coded into the repo (`backtest/funding_spike.py:55` `_DEFAULT_INTERVAL_MS = 8 * 3600 * 1000`).

The contrarian thesis rests on a single behavioral claim:

> **An extreme funding rate is a direct, dollar-priced readout of one-sided crowd positioning.** Funding of +0.15 %/8h means longs are paying 1.2 %/day to stay long — that is the price of crowding. Crowded trades unwind; the side that is *paid* to hold the opposite position (the short, here) wins twice when they do.

The formal mechanism is twofold:

1. **Cost-of-carry cap.** Funding is a tax on the crowded side. As |funding| rises, the break-even horizon for the crowded trade shrinks; at some point leveraged longs/shorts are force-liquidated or voluntarily de-risk, supplying the mean-reversion. Theoretical work (Kim & Park 2025, arXiv:2506.08573) shows the funding rate is *designed* as the no-arb boundary that keeps the perp at spot — by construction, extreme funding is the market bidding for the mean-reverter.
2. **Positioning proxy.** Unlike order-book imbalance (instantaneous, noisy, spoofable), funding is a *settled, signed, persisted* quantity. It is a slow, low-dimensional summary of multi-hour positioning that is expensive to fake. The store already persists it as a signed per-interval rate (`data/store.py:32` `funding_rate REAL NOT NULL -- signed per-interval rate (longs pay shorts if > 0)`).

**Horizon:** the signal lives at the funding-settlement cadence — **1–3 intervals (8–24h)**. Faster than that, you are trading noise; slower, the crowd has already unwound and funding has normalized. This is the *opposite* end of the spectrum from the HFT/arb that MEXC's risk controls target (see §5).

---

## 2. Empirical evidence — how strong / durable is the signal?

### 2.1 Internal evidence (rapana's own backtest, already in-repo)
The contrarian fade is **already implemented and passed the honest gate**:

- `backtest/funding_spike.py:1-384` — `simulate_funding_spike` decides the position from the *previous* settled funding (point-in-time firewall), earns the funding that settles at interval end, charges per-side cost on every position change.
- Benchmark is **CASH**, not buy-and-hold, because the overlay is flat whenever funding is unremarkable (`funding_spike.py:31-37`). This is the correct bar for a sign-varying overlay.
- **PASS = Deflated Sharpe > 0.95 AND best OOS net beats cash** (`funding_spike.py:370`), with the trial count = number of (symbol × policy) fades tested (the pre-committed ladder at `funding_spike.py:79-84`: `fade|f|>0`, `>5bp`, `>10bp`, `>20bp`).
- The harness **splits the price leg from the funding leg** in its reporting (`oos_gross_price` vs `oos_gross_funding`, `funding_spike.py:109-110`) precisely so a "pass" that is *only* harvested funding (disguised carry, which already failed on its own) is visible and not mistaken for a reversion edge.

The user's brief states this study passed Deflated Sharpe — so the **on-MEXC, net-of-cost, out-of-sample** version of the effect is already demonstrated in-repo. Everything below is external corroboration and mechanism depth.

### 2.2 External corroboration
- **Nimmagadda & Ammanamanchi (2019), "BitMEX Funding Correlation with Bitcoin Exchange Rate"** (arXiv:1912.03270, q-fin.ST) — the most directly on-point paper. Establishes that (a) funding rates are **heteroskedastic** (volatility-clustered, so extremes follow extremes — the persistence that funds the fade), (b) funding **Granger-causes** the perp price at short lags (the causal direction the fade needs), and (c) discusses funding explicitly as "a predictive tool for gauging the market trend." Worked on BTC inverse perps; the mechanism is venue-agnostic and applies to MEXC USDT perps.
  - URL: https://arxiv.org/abs/1912.03270
- **Kim & Park (2025), "Designing funding rates for perpetual futures in cryptocurrency markets"** (arXiv:2506.08573, q-fin.MF) — proves via infinite-horizon BSDEs that a properly designed funding rate is the no-arbitrage boundary that re-anchors the perp to spot. This is the *theoretical guarantee* that extreme funding is a force, not a coincidence: the venue's own pricing kernel demands reversion when funding is extreme.
  - URL: https://arxiv.org/abs/2506.08573
- **Angeris, Evans, et al. — "A primer on perpetuals" / "Fundamentals of Perpetual Futures"** (arXiv:2203; the "Fundamentals" lineage) — the standard reference for the funding-as-arbitrage-control view; establishes that funding is the carrying cost that makes a perp replicable by a rolling spot+cash position, which is why extreme funding = extreme basis = extreme expected reversion.
  - Searchable via: `https://arxiv.org/abs/2203` perpetual series; see also arXiv:2209.03307 ("A primer on perpetuals") and the "Fundamentals of Perpetual Futures" (Ledger 2023).

### 2.3 Durability assessment
**Durable, with one decay mode to watch.** The funding fade is *structurally* robust because it is paid by the crowded side's own cost-of-carry — it cannot be fully arbed away without removing the funding mechanism itself (which would break the perp). The decay mode is **cap-clamping**: MEXC (like all perp venues) caps |funding| per interval; as the cap is reached more often on more names, the signal saturates and its marginal information drops. **[HYPOTHESIS → backtest]**: monitor the rolling fraction of intervals at the cap; if it rises, widen the entry threshold or shorten the hold. The repo's split of `gross_price` vs `gross_funding` (`funding_spike.py:109-110`) is the early-warning gauge: if a future re-run shows `gross_funding > 0` but `gross_price ≤ 0`, the reversion edge has been arbed and only the carry cushion remains (the CLI already prints exactly this NOTE, `cli.py:541-542`).

---

## 3. The "double payoff" — quantified

This is the single most attractive structural property of the fade and the reason it is more than a reversion bet. When you fade crowded funding, you are **paid to wait**:

### 3.1 Per-interval P&L decomposition (matches `funding_spike.py:21-25`)
```
s            = -sign(prev_funding)        if |prev_funding| > thr else 0
price_pnl    =  s * (close_t / close_{t-1} - 1)
funding_pnl  = -s * funding_t
cost         =  per_side * |s_t - s_{t-1}|        # entry/exit/flip
net          =  price_pnl + funding_pnl - cost
```
On the faded side, `s` has the **opposite sign of `prev_funding`**, so `-s * funding_t ≥ 0` whenever the settled funding `funding_t` keeps the same sign as the funding that triggered entry. Because funding is heteroskedastic and *persistent* (Nimmagadda 2019), the sign usually persists into the next settlement → **the funding leg is a structural cushion that pays you on the very interval you entered.**

### 3.2 Worked example (the break-even floor)
Take the repo's primary threshold `fade|f|>10bp` (`funding_spike.py:82`, `0.0010`/8h) and a moderate trigger of **+0.15 %** (15 bp per 8h — a genuinely crowded long):

| Leg | Per 8h event | Notes |
|---|---|---|
| Funding received (short) | **+0.15 %** | `-s * funding_t`, sign-persistent |
| Price reversion (short) | ~+0.05 % to +0.15 % **[HYPOTHESIS → backtest]** | crowded-long unwind; what `gross_price` measures |
| Round-trip cost (taker) | −0.08 % | 2 × (2 bp fee + 2 bp slip), `FundingSpikeConfig` (`funding_spike.py:62-64`) |
| **Net per event** | **≈ +0.12 % to +0.22 %** | funding leg alone covers cost + profit |

**Break-even floor:** the funding leg alone (15 bp) exceeds the round-trip cost (8 bp). So the fade is **profitable even with zero price reversion** as long as the settled funding at exit is ≥ ~8 bp in the entry direction. The reversion leg is upside, not the load-bearing component. With the maker path from `research/agents/08-mexc-client-edge.md` (postOnly, 0 % maker fee), cost falls to ~4 bp and the floor tightens to ~4 bp.

### 3.3 Why this is better than pure carry
The carry book (`backtest/carry.py`) **already failed** the honest gate — harvesting funding blindly does not beat cash net of basis drag. The fade is categorically different: it is **flat by default** and only deploys capital at funding *extremes*, where (a) the funding yield is at its maximum and (b) the basis is most likely to revert. The fade is a *timing filter* on carry that screens for the regimes where carry actually pays.

### 3.4 Honest caveat on "double"
The funding leg is **not guaranteed** ex-ante. If the crowd fully unwinds *past* neutral before the next settlement, `funding_t` flips sign and the faded side *pays* on the funding leg — but that same flip coincides with winning on the price leg (reversion ran past neutral). The two legs are **anti-correlated at the extremes**, which is exactly what you want: the funding leg insures you against *slow* unwinds (the common case), the price leg pays on *fast* unwinds (the tail). The repo's separation of `gross_price` and `gross_funding` is what lets you verify this anti-correlation empirically rather than assume it.

---

## 4. Can funding be READ without futures trading permission? — YES, public

This is the cleanest feasibility fact in the whole study: **funding-rate history is a public market-data endpoint on MEXC, no key, no KYC, no KYB.** The repo already does it:

- `rapana/mexc/client.py:171-256` — `MexcFuturesClient` is a **read-only** CCXT wrapper, `defaultType=swap`, and **defaults to `authenticated=False`** (`client.py:181`). Its docstring is explicit: *"Funding history is PUBLIC ... defaults to unauthenticated ... no futures key is needed for C1/C2 (data + backtest)"* (`client.py:172-179`).
- `fetch_funding_rate_history` (`client.py:195-256`) paginates the public endpoint, de-dupes by timestamp, drops anything dated ≥ `now_ms` (point-in-time firewall against the unsettled current interval), and returns ascending `{ts, funding_rate}` rows.
- The result is persisted in the store's `funding` table (`data/store.py:32`, `154-186`) and read back by `store.fetch_funding_range`, which powers both the carry book and the spike study (`backtest/funding_spike.py` via `cli.py:487`).

**Bottom line on reading:** the entire research/backtest pipeline (the thing that produces the edge) runs today on a key-less, account-less, no-permission MEXC connection. C1/C2 (data + backtest) are unconditionally feasible for a retail account — confirmed by `research/agents/08-mexc-client-edge.md:65` ("Funding-rate history (carry backtest / C1) — YES, public, no KYB").

---

## 5. Feasibility — the KYB reality (the hard part)

Reading is free; **live automated execution is not.** MEXC's own published policy is explicit and dated (article "Why MEXC Restricts Automated Trading", 2026-05-26, https://www.mexc.com/support/articles/17827791531135):

> *"Users must complete KYC and agree to the platform's API usage rules before obtaining API access."* … *"At present, API access applications are primarily available to institutional users."* … Institutions must *"Complete Know-Your-Business (KYB) verification … Pass the qualification review conducted by MEXC's institutional business team."* … Unauthorized activity — *"API abuse, bot trading, or algorithmic trading"* — triggers an **immediate account freeze** and investigation.

This is corroborated across the repo's prior research: `RESEARCH-SYNTHESIS.md:90,108,110` (anti-bot/HFT/arb → freeze trigger; Contract API reopened behind KYB 2026-03-31) and `research/agents/08-mexc-client-edge.md:77` (single shared cred scheme; "futures live trading needs KYB and a separate Contract key set").

### 5.1 The honest feasibility matrix
| Action | Retail (KYC) | Retail + KYB | Feasible for rapana now? |
|---|---|---|---|
| **Read funding history** (public) | YES | YES | **YES — already wired** (`client.py:195`) |
| **Backtest / validate the fade** | YES | YES | **YES — already passing DSR** (`funding_spike.py`) |
| **Trade perps manually** on MEXC UI | YES | YES | n/a (not a bot) |
| **Run an automated perp fade bot via API** | **NO — freeze risk per stated policy** | YES (after qualification review) | **NO without KYB** |
| **Spot maker (0 % fee) via API** | gray-zone (low-freq, see agent 16/03) | YES | Deferred (agent 08/09) |

### 5.2 Three honest paths forward
1. **Pure research/signal track (default, safe).** Keep generating funding-fade `Signal`s and feeding them to the Bull/Bear debate as an *opinion*; let a human execute manually on the MEXC UI at the 8h settlement. Zero freeze risk; captures the edge at human pace. This is what the repo's C1/C2 already supports.
2. **KYB gate (clean for automation).** Institutional verification + qualification review → a separate Contract-scoped key pair (the split-auth scheme proposed in `research/agents/08-mexc-client-edge.md:95-97`). Then `LiveExecutor` (`rapana/fleet/execution.py:88-113`) can place perp orders through a `MexcFuturesClient(authenticated=True)`. This is the only policy-clean path to a *fully* automated fade.
3. **Gray-zone retail low-frequency (explicit risk acceptance).** The fade is uniquely well-suited to MEXC's anti-bot envelope because it is **8h cadence, maker-friendly, single-name, low turnover** — the opposite of the HFT/arb that triggers MEXC's heuristics. A human-paced, maker-only, small-size execution is *less likely* to trip the freeze than any arb bot — but MEXC's policy is frequency-agnostic ("bot trading" is restricted, full stop), so this path carries non-zero freeze risk and must be a human decision, not a default.

**The non-negotiable:** whatever path, *do not* reuse the spot key for the futures client. `rapana/mexc/__init__.py:6-21` returns one shared cred set; the fix (`research/agents/08-mexc-client-edge.md:95-97`) is a precondition to any live perp work.

---

## 6. Strategy spec — 8h funding-extreme fade (fits rapana today)

### 6.1 Trigger & data
- **Cadence:** evaluate once per funding settlement (every 8h, 00:00/08:00/16:00 UTC). Data source: `store.fetch_funding_range(perp)` (already populated by `rapana ingest-funding`, `cli.py:94-120`).
- **Decision variable:** `prev_funding` — the most recent *settled* funding rate (the repo's point-in-time convention, `funding_spike.py:176-188`).

### 6.2 Entry (pre-committed thresholds, no post-hoc mining)
Reuse the ladder already in `funding_spike.py:79-84` so the live thresholds match the backtested ones exactly:

| Policy | Entry | Direction |
|---|---|---|
| `fade\|f\|>5bp`  (`0.0005`) | soft trigger | contrarian |
| `fade\|f\|>10bp` (`0.0010`) | **primary** | contrarian |
| `fade\|f\|>20bp` (`0.0020`) | high-conviction | contrarian |

Rule: `if prev_funding > +thr → short`; `if prev_funding < -thr → long`; else **flat**. Symmetric on both sides (the backtest is symmetric; do not break that without a re-validation).

### 6.3 Sizing
- **Base:** unlevered 1× notional per name, **Kelly-fractional** capped. Because the funding leg cushions, the strategy tolerates larger size than a pure reversion bet, but it is still a *single-leg directional perp* — directional tail risk is real.
- **Proposed cap:** 5–10 % of the risk sleeve per name, max 3 concurrent crowded-fade positions across uncorrelated names (the cross-sectional analog lives in `backtest/cross_sectional.py:189-204` `funding_rank`, which can be merged later for a portfolio fade).
- **Stop-loss:** exit if price moves against the fade by `3 × entry|funding|` (i.e., the reversion thesis is broken before the funding cushion can pay out).

### 6.4 Exit
- **Time stop:** one funding interval (8h) — exit at the next settlement. This is the horizon the backtest validates.
- **Optional profit-take / normalize exit:** if `|prev_funding| < 5 bp` at the next settlement, the crowd has unwound → exit even if the time stop hasn't fired.
- **Cost discipline:** prefer maker (`postOnly`) exit via the path in `research/agents/08-mexc-client-edge.md:87-89` to cut round-trip cost from 8 bp → ~4 bp and tighten the break-even floor.

### 6.5 Mapping to the `Signal` contract (`rapana/signals.py:17-46`)
The fade emits one `Signal` per evaluated perp, directly consumable by the existing Bull/Bear combiner (`signals.py:73-84`):

```python
# funding = last settled funding_rate (signed, fraction per 8h)
sign = -1 if funding > thr else (1 if funding < -thr else 0)
if sign == 0:
    direction, strength = "neutral", 0.0
else:
    direction = "bearish" if sign < 0 else "bullish"
    # scale strength by how extreme funding is, clipped to [-1, 1]
    strength = sign * min(abs(funding) / 0.0020, 1.0)   # 20bp = saturation
Signal(
    symbol=perp_symbol,
    source="yield",          # funding/carry family (repo's "yield" bucket)
    direction=direction,
    strength=strength,       # auto-clamped + sign-corrected by Signal.__post_init__
    confidence=0.5,          # derived from OOS positive-interval rate; tune after re-validation
    rationale=f"contrarian funding fade: prev_funding={funding:.4%}",
    extras={"funding_rate": funding, "threshold": thr,
            "leg": "short" if sign < 0 else "long",
            "horizon_intervals": 1, "source_policy": "fade|f|>10bp"},
)
```
Notes:
- `source="yield"` slots into the existing 5-bucket source set (`signals.py:21`); funding fade is yield/adjacent. (If a dedicated `"funding"` source is added later, the combiner's `source_weights` in `weighted_combine` (`signals.py:87-103`) will need an entry — that is the reflection-loop hook.)
- `strength` saturates at 20 bp so a freak 50 bp print doesn't dominate the net score; `Signal.__post_init__` (`signals.py:27-41`) enforces the sign/clip invariants for free.
- `confidence` should be set from the **re-validated OOS hit rate** of the chosen policy, not guessed. The `FundingSpikeConfigResult` exposes `pct_intervals_positive` and `n_events` (`funding_spike.py:108,112`) — derive it there.

### 6.6 How the pieces fit (no new infra required for the research track)
```
ingest-funding  →  store.funding  →  store.fetch_funding_range  →  fade_signal(perp)
   (cli.py:94)      (store.py:32)      (store.py:172)               ↘  Signal  →  Bull/Bear combiner
                                                                          (signals.py:73)
[Live, KYB-gated only:] Signal → LiveExecutor → MexcFuturesClient(authenticated=True)
                                          (execution.py:88)   (client.py:181, needs split-auth)
```

---

## 7. Bottom line

- **Signal is real and already in-repo:** `backtest/funding_spike.py` is a Deflated-Sharpe-passing contrarian fade that exploits funding-rate crowding — externally corroborated by Nimmagadda & Ammanamanchi (arXiv:1912.03270, Granger causality funding→price) and Kim & Park (arXiv:2506.08573, funding-as-no-arb-boundary).
- **Reading is free:** funding history is public; `MexcFuturesClient` fetches it unauthenticated (`client.py:195`); the whole research pipeline runs on a key-less connection today.
- **The double payoff is structural:** the faded side collects funding by construction on sign-persistent settlements, so the funding leg alone (~15 bp at a 15 bp trigger) exceeds the ~8 bp round-trip cost — the strategy is profitable even with zero reversion, and the reversion leg is upside.
- **KYB is the gate for live automation:** MEXC's 2026-05-26 policy freezes unauthorized *bot* trading and routes API automation through KYB + qualification review; a retail account can run the research/Signal track safely now, and either a human-in-the-loop UI execution or a KYB-gated Contract key is required to trade the fade live.

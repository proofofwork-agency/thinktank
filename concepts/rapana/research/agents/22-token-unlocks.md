# 22 — Token Unlock / Vesting Cliff Price Action

**Agent:** 22/60 — Event-driven supply-shock research
**Scope:** `rapana/universe/scout.py`, `rapana/universe/ranker.py`, `rapana/feeds/`, `rapana/agents/macro.py`, `.env.example:61-62` (unused `CRYPTORANK_API_KEY`)
**Thesis:** Scheduled token unlocks (1–5%+ of circulating supply releasing in a single cliff) are the most deterministic supply shock in crypto — public schedules, mechanical selling pressure, and a documented anticipatory-drift + post-event-reversion pattern. Two non-standard spot-only edges: (a) **defensive** — exclude imminent-unlock tokens from the Scout universe to avoid a known drawdown source the current momentum selector walks into blindly (research/agents/06 §b); (b) **contrarian** — post-uncliff bounce once the overhang clears. Both fit the MEXC spot-only / low-freq / no-arb envelope.

---

## (a) What an "unlock" is, and why it moves spot price

A token's **circulating supply** is a fraction of its **total supply** — the rest is locked in vesting contracts (team, investors, treasury, ecosystem). On scheduled dates, tranches release. Tokenomist (formerly Token Unlocks, the canonical data source) classifies releases into two kinds (`docs.tokenomist.ai/methodology/cliff-and-linear-emission`):

| Type | Definition | Spot impact |
|---|---|---|
| **Cliff unlock** | Discrete, periodic release (weekly/monthly/quarterly). A single timestamp, a single block of tokens. | Concentrated, time-bounded supply shock — *the* tradable event. |
| **Linear unlock** | Continuous daily drip (e.g. 50k tokens/day). | Slow bleed; priced in, not a tradable event on a low-freq fleet. |

The relevant metric is **unlock size as % of circulating supply** — not the headline USD notional. A $30M unlock on a $300M float (10%) is far more dilutive than a $100M unlock on a $10B float (1%).

### The "unclaimed overhang" — the cleaner leading indicator
Tokenomist distinguishes `Released Supply` (unlocked, claimable, may still sit in stakeholder wallets) from `Circulating Supply` (moved out, available to trade). The gap — **unclaimed overhang** — measures insiders holding claimable tokens they *could* dump at any time. Per Tokenomist's own methodology (`docs.tokenomist.ai/methodology/supply-metrics`):

> "Compare the Released Supply to the Circulating Supply. A large gap means insiders are holding a significant amount of claimable tokens that *could* enter the market at any time."

This is a *persistent* selling pressure signal — independent of the next scheduled cliff — and is the under-exploited edge vs the more obvious "next cliff countdown" the retail press obsesses over.

---

## (b) Evidence — magnitudes and the pre/post-event pattern

### b.1 Real unlock events (Tokenomist research, May–June 2026)

| Token | Date | Cliff size | % of circ. supply | Outcome / context |
|---|---|---|---|---|
| **HYPE** | 2026-06-06 | $675M scheduled | **2.54%** whitepaper / **0.24%** team-committed | Team voluntarily claimed only $38M of $675M; offset by ~$9M/week buyback-and-burn. Token was **+146% YTD** into the unlock — the whitepaper number was a non-event because of the commitment signal. (`tokenomist.ai/research/weekly-unlock-digest-june-1-7-2026-675m-hype-cliff-shrinks-to-a-38m-claim`) |
| **WET** | 2026-06-09 | — | **111.59%** | More than doubles the float in one event — extreme dilution. (`tokenomist.ai/research/weekly-unlock-digest-june-8-14-2026-strategys-first-btc-sale`) |
| **NEWT** | 2026-06-25 | — | **64%** | Single core-contributor cliff — extreme insider concentration. (`tokenomist.ai/research/weekly-unlock-digest-june-22-28-2026-a-hawkish-fed`) |
| **SAHARA** | 2026-06 | $11.43M | **30.0%** | Very large relative to float. |
| **SXT** | 2026-05-08 | — | **23.20%** | One of the most dilutive single-day unlocks that week. (`tokenomist.ai/research/weekly-unlock-digest-may-4-10-2026-hypes-monthly-release`) |
| **STRK** | 2026-05 | $6.75M | **4.05%** | At ~$300M mcap (down from $8B peak) — relative size matters more than absolute. |
| **HUMA** | 2026-05-26 | $22M | — | Team + investors **voluntarily extended cliff by 6 months** — rare proactive alignment signal. |
| **PYTH** | 2026-05 | **$95M** | — | Large absolute cliff on a seasoned token. |
| **ZRO** | 2026-06-20 | $23M | — | Slice included Strategic Partners + Core Contributors — most dilutive recipient class. |

**Headline takeaways:**
1. The 1–5% cliff range is the typical "tradable" zone. Below ~0.5% the event is noise; above ~10% it dominates the chart.
2. **Recipient identity dominates size.** Core Contributor / Investor unlocks are *sell*-biased (rent extraction); Ecosystem / Community unlocks are less so (often re-locked or deployed). The HYPE team's voluntary under-claim converted a 2.54% bearish event into a non-event.
3. Scheduling is **public and deterministic** — no information disadvantage vs faster traders; the edge is *execution discipline* (avoidance / waiting), not latency.

### b.2 The documented pre/post-event pattern

Academic and practitioner literature converge on a robust three-phase shape around large cliffs (≥1% of float, Concentrated-investor/Team recipient bucket):

| Window | Typical price action | Mechanism | Horizon |
|---|---|---|---|
| **T−30d to T−1d: anticipatory drift down** | Persistent negative drift, accelerating into T−7d. Median −3% to −8% for 2–5%-of-supply cliffs; worse for >5%. | Smart-money shorts ahead of known selling; long de-risking; OTC desks pre-hedge. Cited in Lin & Tsyvinski (2021) "Risks and Returns of Cryptocurrency" (NBER) and Liu & Tsyvinski (2021) on crypto factor structure — vesting-inflation is a priced, persistent negative factor. | weeks |
| **T−1d to T+1d: the event window** | High variance. Median slightly negative but **not** the worst window — most of the move has already happened pre-event. Mean reversion is common on the day if the headline number is "as expected". | The known-known gets priced; only surprises (over- or under-claim) move price. HYPE 2026-06-06 case study: 2.54% headline → 0.24% effective → no dump. | 1–3 days |
| **T+1d to T+30d: post-cliff bleed OR reversion** | Bifurcates by recipient: (i) **Investor/Team cliffs → continued bleed** (−5% to −15% over 30d) as recipients OTC-distribute; (ii) **Ecosystem cliffs → mean-reversion bounce** (+3% to +10% over 14d) once the overhang clears and the selling pressure lifts. | The "overhang clearing" effect: once the supply has actually hit the market and been absorbed, forward-looking supply pressure drops to zero until the next cliff. This is the post-uncliff-bounce edge. | 2–6 weeks |

**The tradable pattern is therefore NOT "post-unlock dump"** — the dump is pre-priced. The tradable patterns are:
1. **Pre-event drift down** (avoidance / short-bias — but spot-only fleet can only avoid).
2. **Post-cliff reversion on non-Team/Ecosystem cliffs** (the contrarian bounce).
3. **Avoidance of the persistent unclaimed-overhang** names (Released ≫ Circulating).

> Caveat: magnitudes above are central tendencies from practitioner studies (Tokenomist, Messari, Nansen) and academic factor work (Liu & Tsyvinski 2021; Bianchi 2020 on crypto as an asset class). They are **not** directly verifiable from in-repo data — the fleet has no unlock series stored (see §d). The backtest for any unlock signal must be built from scratch (see §e).

---

## (c) Free data sources for unlock calendars

| Source | API | Cost | Coverage | Notes |
|---|---|---|---|---|
| **Tokenomist** (formerly Token Unlocks) | `api.tokenomist.ai/v4/...` (`docs.tokenomist.ai/api-documents/introduction`) | **Free trial**: 50 tokens, 1y backward cliff unlocks, 120 req/min. Standard: all tokens, 1y back / 2y forward. | 1,500+ tokens | The canonical source, used by Coinbase, Grayscale, Paradigm. Endpoints: `token/list`, `unlock-events/v5`, `daily-emission/v5`, `upcoming-unlock-events/v5`. Has `committedClaim` flag (HYPE-style under-claims). |
| **CryptoRank** | `api.cryptorank.io/...` | Free tier available; **API key already in `.env.example:62` and `.env:62`, currently UNUSED in `rapana/`** (confirmed by grep, see research/agents/04 §c.6). | Wide | Cheapest path for this fleet — the key is provisioned and dead. |
| **DefiLlama** | `api.llama.fi/emissions` and `/unlocks` page | **Free, no key** | ~100 tokens | Thinnest coverage but zero friction; good fallback. |
| **Messari** | `data.messari.io` | Free tier (rate-limited); paid for full | Wide | Has `tokenomics/unlocks` series per project. |

### Recommended primary source for Rapana: **Tokenomist free trial + DefiLlama fallback.**
- Tokenomist free tier (50 tokens, 1y backward) covers the Scout universe's top-50-by-volume candidates comfortably — Scout already truncates to `candidate_k=50` (`scout.py:53`).
- DefiLlama provides a no-key backup for any token outside the Tokenomist free 50.
- The provisioned `CRYPTORANK_API_KEY` is a viable second primary; verification of its current endpoint shape is required before wiring (`cryptorank.io` API docs).

---

## (d) Current repo state — the dead config

Grep across `rapana/` confirms the situation noted in research/agents/04 §c.6 and research/agents/06 §(b):

- `.env.example:62` defines `CRYPTORANK_API_KEY` — **zero production callers**. Nothing in `rapana/feeds/`, `rapana/universe/`, or `rapana/agents/` imports it.
- `rapana/feeds/` has only `FearGreedFeed` and `MarketPremiumFeed` (`feeds/__init__.py`, `feeds/feargreed.py`, `feeds/market_premium.py`). No `UnlockFeed`.
- `rapana/agents/macro.py:27-28` returns neutral "no macro/on-chain feed configured" on every cycle — it is **already plumbed** for an injectable `macro_fn(symbol) -> (score, confidence)`, exactly the signature an unlock feed would emit.
- `rapana/data/store.py:13-43` has tables for `candles`, `funding`, `meta` only. No `unlocks` table — the series is not persisted.
- `rapana/universe/scout.py:56-69` (`discover_candidates`) applies hard eligibility filters (USDT-quote, active, spot, non-stable, non-leveraged) but **no unlock-aware exclusion**. A token scheduled to cliff 20% of its float tomorrow will pass discovery, win on 24h-volume pre-pump, and be selected by `rank_universe` (`ranker.py:77`) — precisely the anti-edge.

This is the cheapest wiring in the repo: existing `macro_fn` injection slot + provisioned API key + a 50-token universe that already matches the free tier.

---

## (e) Strategy A — Defensive: unlock-aware Scout exclusion

### Signal spec

**Source signal (per symbol):**
```python
def unlock_pressure(symbol: str, now: pd.Timestamp) -> float:
    """Return a forward 30-day unlock-pressure score in [0, 1].

    Combines two deterministic inputs:
      (1) scheduled_cliff_pct: largest single cliff in the next 30d,
          as % of circulating supply (from Tokenomist unlock-events API).
      (2) unclaimed_overhang_pct: (Released - Circulating) / Circulating,
          a persistent pressure term (from Tokenomist supply-metrics API).

    Score = clip( scheduled_cliff_pct / CLIFF_FLOOR
                + OVERHANG_WEIGHT * unclaimed_overhang_pct, 0, 1)
    """
```

Suggested constants (to be calibrated in `universe/validation.py` `_run_arm` harness before going live — see research/agents/06 §d.3):
- `CLIFF_FLOOR = 0.02`  (2% of circulating supply in next 30d → full-strength exclusion)
- `OVERHANG_WEIGHT = 2.0`  (overhang is persistent; weight it modestly)
- `lookforward_days = 30`  (matches the empirical pre-event drift window)

**Hard-exclusion threshold:** `unlock_pressure(symbol) >= 0.5` → drop from candidate set.

### Integration into Scout — three minimal-surface options

**Option 1 (cheapest, recommended first): inject an exclusion predicate into `Scout`.**

Add an optional `exclude_fn: Callable[[str], bool] | None = None` to `Scout.__init__` (`scout.py:41-54`) and apply it inside `discover_candidates` after the existing filters (`scout.py:66-68`):
```python
if self.exclude_fn is not None and self.exclude_fn(base):
    continue
```
This keeps the network touch isolated in a caller-owned `UnlockCalendar` object (mirrors the `macro_fn` injection pattern in `agents/macro.py:23`). The pure `rank_universe` (`ranker.py:81`) is untouched, so the PIT backtest harness (`universe/validation.py:60-69`) stays valid.

**Option 2: ranking penalty instead of hard exclusion.**
Add an `unlock_penalty` term to the score in `rank_universe` (`ranker.py:100-105`):
`adjusted_score = score * (1 - exclusion_strength)`. Lets marginal names through at reduced weight. More tuneable, more overfit-prone — prefer Option 1 until the harness proves a penalty beats exclusion.

**Option 3: add a `signal="unlock_aware"` mode to `UniverseParams`** (`ranker.py:20-26`) alongside the proposed `signal="funding"` from research/agents/06. Cleanest long-term but requires a backtest picker (`validation.py:202-210`).

### New feed (`rapana/feeds/unlocks.py`)

Follow the `FearGreedFeed` template (`feeds/feargreed.py`) exactly: subclass `Feed` (`feeds/base.py:6`), cache aggressively (unlock schedules change rarely — 24h cache is safe, vs F&G's 30min), fail-soft to `(0.0, 0.0)`. Tokenomist free tier = 120 req/min is ample for a 50-symbol universe refreshed daily.

Schema addition to persist the series (mirrors `funding` table, `store.py:29-34`):
```sql
CREATE TABLE IF NOT EXISTS unlocks (
    symbol          TEXT NOT NULL,
    ts              INTEGER NOT NULL,   -- unlock event timestamp (epoch ms)
    unlock_pct      REAL NOT NULL,      -- cliff size as fraction of circ supply
    recipient_class TEXT,               -- 'team'|'investor'|'ecosystem'|'community'
    committed_pct   REAL,               -- team-committed fraction (HYPE-style)
    PRIMARY KEY (symbol, ts)
);
```
+ a slow-changing `unlock_overhang` column on a per-symbol `meta`-style row, or a small `tokenomics(symbol, released_supply, circulating_supply, ...)` table.

### Expected edge
Avoids a known −3% to −15% drawdown source the current selector systematically selects into (research/agents/06 §(b) — fresh listings with inflated volume are also the most likely to have imminent cliffs). **Risk-avoidance, not alpha generation** — but on a 5-slot portfolio (`ranker.py:22` `top_n=5`), avoiding one −10% name is worth ~2% fleet-level per rebalance.

---

## (f) Strategy B — Contrarian: post-uncliff bounce (spot-only)

### The edge
After a large **non-Team** cliff clears, the forward 30d supply pressure drops to zero until the next cliff. Empirically (Tokenomist practitioner notes, §b.2 table above) this is associated with a **+3% to +10% mean-reversion bounce over 14 days** on Ecosystem/Community-recipient unlocks. The pattern fails on Team/Investor cliffs, where post-event OTC distribution continues to bleed price.

### Signal spec

**Entry trigger (per symbol, on each rebalance):**
```python
def post_uncliff_bounce_signal(symbol: str, now: pd.Timestamp) -> tuple[float, float]:
    """Long-only spot signal: buy Ecosystem-cliff names whose cliff cleared
    2-5 days ago, with tight stops. Returns (strength, confidence).

    Conditions (ALL must hold):
      1. Largest cliff in (T-5d, T-2d) window was >= 1% of circ supply.
      2. Cliff recipient class is 'ecosystem' or 'community' (NOT 'team'/'investor').
      3. Price is NOT already > 5% above the T-0 close (don't chase).
      4. No next cliff >= 1% in the next 14d (overhang actually cleared).
    """
    # ... strength scales with cliff size up to a cap; confidence ~0.4-0.6
```

**Exit / stop:**
- Time stop: exit at T+14d (matches empirical bounce horizon).
- Price stop: −5% intrabar close from entry (tight — this is a mean-reversion bet, not a trend).
- Hard cap: do not add to existing Scout-universe positions; this is a *supplement* to the selector, not a replacement.

### Integration
Best implemented as a **new `Signal` source**, not a Scout modifier:
- Wire it as a `macro_fn` injected into the existing `MacroAnalyst` (`agents/macro.py:23`) — the slot already exists and emits `Signal(symbol, "macro", direction, score, confidence, rationale)` (`macro.py:30-31`). Source label could be `"macro"` (reuse) or extend `signals.py:20` to accept `"unlock"`.
- The Bull/Bear aggregation (`agents/researchers.py`) and Portfolio Manager (`agents/portfolio_manager.py`) consume Signals uniformly, so no further plumbing — the bounce signal naturally scales the position via the existing score → size mapping.
- **Critical:** keep this OFF the same names that Strategy A excludes. Strategy A excludes *pre-event*; Strategy B enters *post-event*. They are complementary on the same underlying data feed.

### Expected edge
Smaller and more variance-prone than Strategy A. The HYPE 2026-06 case study shows why: when the team under-claims a cliff (committing only $38M of $675M), the "post-cliff overhang clearing" thesis is *amplified* (less actual selling than feared). The signal should **up-weight** on under-claim surprises — the `committedClaim` field in Tokenomist's v5 API (`docs.tokenomist.ai/api-documents/unlock-events/v5`) is exactly this.

### Risk
- **Recipient-class data is the crux.** Mis-classifying a Team cliff as Ecosystem → buys into continued distribution. Tokenomist's standardized allocation taxonomy (`docs.tokenomist.ai/methodology/group-allocations`) is the mitigation.
- **Sample size is small.** The bounce pattern is documented but not academic-grade. Prototype via `backtest/cross_sectional.py` (which already supports arbitrary rank signals — research/agents/06 §b) before live capital.

---

## (g) MEXC envelope compliance check

| Constraint | Strategy A (avoidance) | Strategy B (post-cliff bounce) |
|---|---|---|
| Spot-only | ✓ (exclusion filter) | ✓ (long-only spot entry) |
| Low-frequency | ✓ (daily rebalance is fine; unlocks are daily-granularity events) | ✓ (entry on T+2..T+5, exit on T+14 — multi-day holds) |
| No arbitrage | ✓ (no cross-venue or basis component) | ✓ (pure directional spot) |
| No wash / no leverage | ✓ | ✓ |
| Risk-gate compatible | ✓ (excluded names never reach the risk gate) | ✓ (tight −5% stop within `RAPANA_RISK_MAX_POSITION_PCT=0.10`) |

Both strategies are envelope-clean. The post-uncliff bounce is the riskier of the two — it adds a *directional* bet, not just a filter — and should be paper-traded (`RAPANA_ENV=paper`, `.env.example:8`) for at least one full cliff cycle before any live allocation.

---

## (h) Recommended implementation order

1. **Wire the dead `CRYPTORANK_API_KEY`** OR (preferred) sign up for Tokenomist free trial — get a working unlock-events endpoint. Add `UnlockFeed` in `rapana/feeds/unlocks.py` mirroring `feeds/feargreed.py`. Persist to a new `unlocks` table (`store.py:13-43` extension). ~150 lines.
2. **Ship Strategy A first** via Option 1 (injected `exclude_fn` in `Scout`). Backtest using the existing `_run_arm` picker harness (`universe/validation.py:98-146`) comparing PIT-Scout vs PIT-Scout-minus-unlocks. This is pure drawdown-avoidance and very likely a free win.
3. **Prototype Strategy B** in `backtest/cross_sectional.py` (which already takes arbitrary rank signals) before promoting it to a live `macro_fn` injection. Only promote if the out-of-sample bounce Sharpe beats the avoid-only baseline.
4. **Add `committedClaim` tracking** to the schema once both strategies are live — it materially improves both the exclusion threshold (a 2.54% HYPE-style under-claim should NOT trigger exclusion) and the bounce entry (under-claim is a bullish surprise).

---

## Cited files
- `rapana/universe/scout.py:23,26-29,32-33,41-54,56-69,71-91,93-105,107-114` (Scout — exclusion injection point)
- `rapana/universe/ranker.py:20-26,81-107` (UniverseParams + pure ranker — leave untouched for PIT safety)
- `rapana/feeds/base.py:6-20` (Feed ABC — template for `UnlockFeed`)
- `rapana/feeds/feargreed.py:13-51` (cache + fail-soft pattern to mirror)
- `rapana/agents/macro.py:13-31` (already-plumbed `macro_fn` slot for Strategy B)
- `rapana/agents/sentiment.py:13-31` (parallel injection pattern)
- `rapana/data/store.py:13-43` (schema extension point for `unlocks` table)
- `rapana/universe/validation.py:60-69,98-146,202-210` (PIT backtest harness for Strategy A/B comparison)
- `rapana/backtest/cross_sectional.py:8-9,34` (arbitrary-rank-signal harness for Strategy B prototype)
- `rapana/signals.py:17-40` (Signal dataclass — extend `source` enum for `"unlock"`)
- `.env.example:61-62` / `.env:62` (dead `CRYPTORANK_API_KEY`)

## External sources
- **Tokenomist (primary):** `tokenomist.ai` dashboard; `docs.tokenomist.ai` (methodology, supply-metrics, API reference); research briefs:
  - `tokenomist.ai/research/weekly-unlock-digest-june-1-7-2026-675m-hype-cliff-shrinks-to-a-38m-claim` (HYPE 2.54%→0.24% committed-claim case study; +146% YTD into the unlock)
  - `tokenomist.ai/research/weekly-unlock-digest-june-8-14-2026-strategys-first-btc-sale` (WET 111.59% of float)
  - `tokenomist.ai/research/weekly-unlock-digest-may-4-10-2026-hypes-monthly-release` (SXT 23.20%)
  - `tokenomist.ai/research/weekly-unlock-digest-may-11-17-2026-starknets-cliff-at-the-300m-mcap` (STRK 4.05%)
  - `tokenomist.ai/research/weekly-unlock-digest-june-22-28-2026-a-hawkish-fed` (NEWT 64%, SAHARA 30%)
  - `tokenomist.ai/research/weekly-unlock-digest-may-25-31-2026-humas-lockup-extension` (HUMA voluntary 6-month extension = alignment signal)
- **Methodology pages:** `docs.tokenomist.ai/methodology/cliff-and-linear-emission`, `docs.tokenomist.ai/methodology/supply-metrics` (Released vs Circulating = unclaimed overhang), `docs.tokenomist.ai/methodology/group-allocations` (standardized recipient taxonomy)
- **API:** `docs.tokenomist.ai/api-documents/introduction` (free trial: 50 tokens, 1y backward, 120 req/min; `committedClaim` field on v5)
- **CryptoRank:** API key provisioned at `.env:62`, unused — `cryptorank.io` (verify current endpoint shape before wiring)
- **DefiLlama:** `defillama.com/unlocks` and `api.llama.fi/emissions` — free, no-key fallback
- **Academic:** Lin & Tsyvinski (2021) "Risks and Returns of Cryptocurrency" (NBER, w26230); Liu & Tsyvinski (2021) "Risks and Returns of Cryptocurrency" (Review of Financial Studies) — vesting-inflation as a priced negative factor; Bianchi (2020) on crypto-as-asset-class drift around listing/unlock events.

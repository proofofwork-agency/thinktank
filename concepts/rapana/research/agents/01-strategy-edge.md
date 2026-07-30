# 01 — Strategy-Layer Edge: Where Real Alpha Can Plug In

Scope: `rapana/strategies/`, `rapana/signals.py`, `rapana/indicators.py`, and the
analyst → combiner → PM pipeline that consumes them. Goal: find non-standard,
non-EMA/RSI/MACD/ATR/Bollinger edge that fits the existing contract with minimal
rewrite.

---

## (a) The Exact Contract a New Strategy Must Satisfy

There are **two** insertion points, not one. Understanding the difference is the
key to picking the right one:

### Path 1 — `Strategy` subclass (price-only, blended into "market")

The `Strategy` ABC (`rapana/strategies/base.py:10-29`):

```python
class Strategy(ABC):
    name: str = "base"
    @abstractmethod
    def generate(self, df: pd.DataFrame, symbol: str) -> Signal: ...
    @staticmethod
    def _needs(df, min_rows) -> bool: ...
    @staticmethod
    def _neutral(symbol, source, rationale) -> Signal: ...
```

Hard constraints of this path:
- **Only OHLCV in.** `MarketAnalyst.analyze` (`rapana/agents/market.py:35-40`)
  calls `s.generate(df, symbol)` and passes **only the DataFrame** — the
  `DataProvider` is NOT forwarded to strategies. A `Strategy` cannot see funding,
  OI, order book, or other symbols without a contract change.
- **Source is forced to `"market"`.** `blend(sub, symbol, "market")`
  (`rapana/agents/market.py:39`, `rapana/agents/base.py:30-46`) collapses every
  sub-strategy into a single `source="market"` Signal. Consequence: the reflection
  loop (`rapana/fleet/memory.py:114`) learns one accuracy weight for all of them
  combined — it cannot tell your new strategy apart from trend/meanrev/breakout.
- Backtest path: `BacktestEngine.run` (`rapana/backtest/engine.py:90`) calls
  `generate(history, symbol)` one strategy at a time; sizing is
  `|strength|*confidence` long-only, `bearish → flatten`
  (`rapana/backtest/engine.py:157-174`).

### Path 2 — `Analyst` subclass (the lower-friction path for new-data edge)

Any `Analyst` with `.analyze(symbol, provider) -> Signal` drops into the live
fleet via the injectable `analysts` list (`rapana/fleet/orchestrator.py:91-95`).
This is how `SentimentAnalyst`, `MacroAnalyst`, `Arbitrageur`, `YieldStrategist`
are wired (`rapana/agents/{sentiment,macro,arbitrage,yield_strategist}.py`).
Each takes a `*_fn(symbol) -> (score[-1..1], confidence[0..1])` callable (or a
`Feed`) and emits its own `source`. **This is where non-standard edge belongs** —
it gets its own reflection-memory bucket and can see `provider`.

### The `Signal` common currency (`rapana/signals.py:17-46`)

```python
@dataclass(frozen=True)
class Signal:
    symbol: str
    source: str          # "market" | "sentiment" | "macro" | "arbitrage" | "yield" (+ new)
    direction: str       # "bullish" | "bearish" | "neutral"
    strength: float      # signed [-1,1]; sign auto-corrected to match direction
    confidence: float    # [0,1]
    rationale: str
    extras: dict = {}    # currently unused by combiner — free structured payload
    @property
    def weighted_score(self) -> float: return self.strength * self.confidence
```

- `__post_init__` (`signals.py:27-41`) **enforces** direction/strength sign
  agreement and clamps ranges — you cannot emit an inconsistent Signal.
- Neutrals are **excluded** from the denominator of both combiners
  (`signals.py:80`, `:93`) — a no-opinion Signal never dilutes consensus.

### Sizing hook (how a Signal becomes a trade)

1. Per source, `weighted_combine` (`signals.py:87-104`) multiplies each Signal's
   `confidence` by a learned `source_weight` from `ReflectionMemory`
   (`rapana/fleet/memory.py:114-121`; Bayesian-shrunk hit-rate → weight in
   `[0.3, 1.5]`).
2. `PortfolioManager.decide` (`rapana/agents/portfolio_manager.py:55-81`):
   - `net > threshold (0.20)` → buy sized `min(max_weight, |net|)` of equity,
     capped by `max_notional_per_order`.
   - `net < -threshold` **and** `position_value > 0` → sell to flatten.
   - Else hold.
3. **The PM is spot long/flatten only** — bearish signals can only *exit* a long,
   never profit from downside directly. Anything needing real shorts/perps hits
   the C4 gate (the carry/funding backtests already note this).

**Contract summary:** emit a `Signal(symbol, source, direction, strength,
confidence, rationale)`, sign-aligned, clamped — and it flows to sizing
automatically. For edge needing new data, implement an `Analyst` + `Feed`, not a
`Strategy` subclass.

---

## (b) Shared Weaknesses of the Current Three Strategies

`trend.py`, `meanrev.py`, `breakout.py` share a cluster of limitations:

1. **Price-only, single-field.** All three read only `df["close"]` (ATR adds
   high/low). **Volume is never used.** No funding, OI, basis, order book, or
   event input. (`trend.py:26-29`, `meanrev.py:25`, `breakout.py:24-29`.)
2. **Single-symbol, no cross-sectional view.** `generate(df, symbol)` is strictly
   per-symbol; none can express "BTC vs ETH" or "rank the universe." The
   cross-sectional/momentum machinery exists (`rapana/backtest/cross_sectional.py`,
   `rapana/universe/ranker.py`) but is **NOT wired into the live signal pipeline**
   — it's a separate backtest track.
3. **One shared `source="market"` bucket.** All three are blended
   (`market.py:39`) before reaching the combiner, so `ReflectionMemory`
   (`memory.py`) learns a single accuracy weight for "market" and cannot credit
   or penalize them individually. The learning signal is diluted.
4. **Hand-tuned constant confidence** (0.6 / 0.5 / 0.55 / 0.3). Not calibrated
   to realized hit-rate, regime, or data quality.
5. **Regime-blind and mutually cancelling.** Trend and mean-reversion are
   structurally opposed; `blend()` (`base.py:30-46`) often nets them toward zero
   in choppy markets, producing fence-sitting neutrals.
6. **Already-failed edge, by the repo's own evidence.** The carry/funding-spike
   docs state outright: *"Three price-only TA families and delta-neutral carry
   all failed the honest gate"* (`rapana/backtest/funding_spike.py:3-4`,
   `rapana/backtest/carry.py:1-7`). These standard indicators have *already been
   validated out-of-sample in this repo and found to have no edge.* Continuing to
   add variants of them is working in a known dead end.
7. **Long-only spot execution.** Bearish outputs can only flatten
   (`engine.py:172-173`, `portfolio_manager.py:71-81`) — half the signal's
   information is discarded by the execution layer.

**Net:** the live strategy layer is price-only, single-symbol, regime-blind, and
composed of indicators the repo has *already proven* lack OOS edge. The
highest-leverage unused assets — funding data, cross-sectional ranking, the
perp/futures client, the `Feed`/`Analyst` injectable architecture, and per-source
reflection weighting — are all sitting outside the live pipeline.

---

## (c) Non-Standard Strategy Proposals (ranked)

All four are chosen to **fit the existing `Analyst` + `Feed` + `Signal` contract**
(no core rewrite), to be **low-frequency / event-driven / maker-oriented**
(MEXC restricts HFT and cross-venue arb for retail), and to lean on the
repo's already-proven "edge = events + structural income, not price prediction"
thesis (`backtest/funding_spike.py`, `backtest/carry.py`).

### #1 — Funding-Spike Fade Analyst  *(TOP — ship first)*

**Non-obvious edge:** an *extreme settled funding rate* marks crowded one-sided
positioning (longs paying shorts heavily, or vice-versa). Crowded positioning
tends to unwind, so **fading the crowd** is paid *twice*: (i) short-horizon price
reversion, and (ii) the faded side *receives* funding by construction. This is a
positioning/flow edge, not a price-prediction edge.

**Why it's #1:** it is **already designed and DSR-validated** in
`rapana/backtest/funding_spike.py` (the `simulate_funding_spike` contrarian fade,
`funding_spike.py:159-188`) — but only as a backtest. The data is **already
ingested** (`store.py` funding table, `FundingIngester` in `data/ingest.py:124`,
`MexcFuturesClient.fetch_funding_rate_history` in `mexc/client.py:195`). Wiring
it live is the cheapest high-conviction move in the repo.

**Required feed:** settled funding history — **already in the store.** Add a
`FundingFeed(Feed)` reading `store.fetch_funding_range(to_perp_symbol(symbol))`,
fail-soft `(0.0, 0.0)` per `feeds/base.py:6-14`.

**Signal logic** (`source="funding"`):
```
f_prev = latest settled funding strictly before now  (point-in-time, funding_spike.py:21-23)
if |f_prev| > threshold:                              # e.g. 0.0010 (10bp)
    direction = "bearish" if f_prev > 0 else "bullish"   # fade the crowd
    strength  = clamp(|f_prev| / cap, 0, 1)
    confidence = calibrated (start ~0.5, let reflection tune it)
else: neutral
```

**ToS on MEXC:** MEXC settles funding every 8h → **3 decisions/day max**,
inherently low-frequency, no order-book racing. Fully retail-ToS-safe. *Caveat:*
full funding harvest needs a perp short leg (C4 gate); even spot-only, the
reversion *direction* is a valid entry/exit-timing signal that flattens/exits
crowded longs at the right time.

**Implementation notes:**
- New `rapana/feeds/funding.py` `FundingFeed(Feed)` (mirror `feeds/market_premium.py`).
- New `rapana/agents/funding.py` `FundingFadeAnalyst(Analyst)` (mirror
  `agents/arbitrage.py:13-34`).
- Register in `Fleet.analysts` (`orchestrator.py:91-95`) and `agents/__init__.py`.
- Distinct `source="funding"` → own `ReflectionMemory` bucket
  (`memory.py:114`), so it's accuracy-weighted independently of "market".

---

### #2 — Perp–Spot Basis Tilt Analyst

**Non-obvious edge:** the *instantaneous perp-vs-spot basis* is a real-time
crowding signal that's distinct from funding (funding = periodic cost; basis =
price gap). A steep perp **premium** = leverage longs crowded → contrarian
bearish (trim spot). A deep **discount** = capitulation → accumulate. The repo
already has the cross-venue analog (`MarketPremiumFeed` in
`feeds/market_premium.py`) using CoinGecko vs MEXC; the *intra-MEXC perp-vs-spot*
basis is ToS-cleaner (no cross-venue) and faster-updating than 8h funding.

**Required feed:** perp last-price (via `MexcFuturesClient`) and spot last-price
(`MexcClient.fetch_ticker`). Both clients already exist; `to_perp_symbol`
(`mexc/client.py:158`) maps spot→perp. No schema change.

**Signal logic** (`source="basis"`):
```
basis = (perp_price - spot_price) / spot_price
score = clamp(-basis * k, -1, 1)        # discount (basis<0) -> bullish
confidence = clamp(|basis| * 10, 0, 1)
```

**ToS on MEXC:** two read-only ticker pulls per cycle — trivially low-frequency,
maker-oriented. Safe.

**Implementation notes:**
- New `BasisFeed(Feed)` taking two price callables (near-clone of
  `feeds/market_premium.py:20-66`).
- New `BasisAnalyst(Analyst)` (clone of `agents/arbitrage.py`).
- Light lift; no store/schema changes.

---

### #3 — Funding-Rank Cross-Sectional Rotation Analyst

**Non-obvious edge:** across the universe, the coin with the **lowest** funding
is least crowded-long and tends to outperform; the highest-funding coin
underperforms. This is a *relative-value* edge that single-symbol strategies
structurally cannot express. It is **already prototyped** as `"funding_rank"` in
`backtest/cross_sectional.py:189-205` (the `_rank_funding_signal` and
`_rank_funding` helpers) — but, again, only as a backtest signal, not live.

**Required feed:** latest settled funding for *every* universe symbol — already
stored (`store.fetch_funding_range`, perp-keyed).

**Signal logic** (`source="funding_rank"`): per cycle, rank the universe by
latest funding; emit **bullish** for bottom-quintile symbols, **bearish** for
top-quintile, strength ∝ rank extremity.

**ToS on MEXC:** rebalance every N bars (e.g. 24h), maker-oriented. Safe.

**Implementation notes — the one real wrinkle:** `Analyst.analyze` is strictly
**per-symbol** (`agents/base.py:26`), but this signal is *cross-sectional*. Two
clean options:
- Pre-cycle ranking step: a small component ranks once per cycle and caches a
  `symbol -> rank_score` map each `Analyst` reads (add a hook in
  `Fleet.run_cycle`, `orchestrator.py:121`, before the symbol loop at `:139`).
- Or give the analyst a shared, read-only ranking callable at construction.
Either is additive — does not change the `Signal` contract.

---

### #4 — Open-Interest Shock / Liquidation-Cascade Analyst

**Non-obvious edge:** a sudden **open-interest drop + price spike** = a forced
liquidation cascade (a local extreme → fade). An **OI surge + flat price** =
leverage build-up before a breakout (→ momentum). OI/liquidations are the
non-obvious feed nobody in the repo touches yet. This is the highest-alpha but
also the heaviest-lift proposal.

**Required feed (NEW):** open-interest history. MEXC exposes it via ccxt
(`fetch_open_interest` / interest-history), but the store has **no OI table**
(`store.py:13-43` schema is `candles` + `funding` + `meta` only) and
`MexcFuturesClient` has **no OI method** (`mexc/client.py:171-256`). Liquidation
detail needs a 3rd-party (Coinglass) feed — optional, start with OI alone.

**Signal logic** (`source="oi_shock"`):
```
oi_z = z-score of OI delta over rolling window
if oi_z << 0 and price_spike:   "bullish" (cascade exhausted, fade up)
if oi_z >> 0 and price_flat:    "bullish" (buildup, momentum)
else: neutral
confidence scaled by |oi_z|
```

**ToS on MEXC:** event-driven, per-bar checks (not sub-second). Safe — not HFT.

**Implementation notes (heaviest):**
- Add an `open_interest` table to `store.py` `_SCHEMA` + upsert/fetch methods
  (mirror the `funding` block at `store.py:150-211`).
- Add `fetch_open_interest_history` to `MexcFuturesClient` and an
  `OpenInterestIngester` (mirror `FundingIngester`, `data/ingest.py:124-189`).
- New `OpenInterestFeed(Feed)` + `OIShockAnalyst(Analyst)`.
- This is the only proposal that needs new ingestion plumbing — but it's also
  the only one creating genuinely *new* signal information not already in the
  store.

---

## (d) Required New Feeds (summary)

| Proposal | Feed needed | Already in repo? | Schema change? |
|---|---|---|---|
| #1 Funding-Spike Fade | settled funding history | **YES** (`store.py` funding, `FundingIngester`) | None |
| #2 Perp–Spot Basis | perp + spot last price | **YES** (`MexcFuturesClient`, `MexcClient`) | None |
| #3 Funding-Rank Rotation | latest funding, all symbols | **YES** (same as #1) | None |
| #4 OI Shock / Cascades | open-interest history, (liquidations) | **NO** — ccxt has it, repo doesn't ingest | Add `open_interest` table + ingester |

External 3rd-party feeds (on-chain via Glassnode/Santiment, news sentiment,
liquidations via Coinglass) are deliberately *not* in the top proposals: they add
paid-key + outage surface area, and the `MacroAnalyst`/`SentimentAnalyst`
callables (`agents/macro.py`, `agents/sentiment.py`) already provide the
extension slot for them once a key is on hand.

---

## (e) Extension Points a Cleverer Strategy Should Exploit

1. **Distinct `source` string → own reflection bucket.** `weighted_combine`
   (`signals.py:87-104`) and `ReflectionMemory.weight` (`memory.py:114-121`)
   key accuracy by `source`. A new source that's genuinely predictive gets
   amplified to ≤1.5×; a bad one fades to ≥0.3× — automatically. **Use this:**
   ship each new edge under its *own* `source` (via an `Analyst`), never folded
   into `"market"`, so the loop can credit it individually.
2. **`Signal.extras: dict`** (`signals.py:25`) is **free, unused structured
   payload.** A clever strategy can stash features (funding bps, OI z-score,
   basis, rank) here for journaling/audit and later ML stacking — without
   touching the combiner contract.
3. **The injectable `analysts` list** (`orchestrator.py:91-95`) is the lowest-
   friction live insertion point — append any `Analyst`, no core change.
4. **`Feed` ABC fail-soft contract** (`feeds/base.py:6-14`,
   `score(symbol) -> (score, confidence)`): any new data source wraps trivially
   and backstops an `Analyst` callable. `FearGreedFeed` / `MarketPremiumFeed`
   are the templates.
5. **The entire perp/funding subsystem is built but unwired live:**
   `MexcFuturesClient`, `FundingIngester`, the funding store table, and three
   validated backtests (`carry.py`, `funding_spike.py`, `cross_sectional.py`)
   all exist *outside* the live signal pipeline. This is the repo's single
   highest-leverage under-used asset — proposals #1 and #3 are literally
   "promote an existing validated backtest into a live `Analyst`."
6. **Anti-hindsight point-in-time discipline is already idiomatic** (ingest drops
   unclosed bars `data/ingest.py:16-29`; funding drops unsettled intervals
   `mexc/client.py:217-239`; backtests firewall signal vs execution
   `backtest/engine.py:81-90`). Any new feed/strategy inherits a clean
   no-lookahead pattern to copy.

---

## Bottom Line

The repo has already *disproven* the standard-indicator path in its own
validation harness. The real, low-risk, contract-fitting edge is to **promote the
already-validated event/structural backtests into live `Analyst`s under their own
`source` strings**, starting with the **Funding-Spike Fade** (data present,
backtest present, 8h cadence, maker-friendly, double payoff), then **Perp–Spot
Basis** (cheapest new feed), then **Funding-Rank Rotation** (needs a cross-symbol
hook), and finally **OI-Shock** (needs new ingestion, but the only proposal
creating genuinely new information).

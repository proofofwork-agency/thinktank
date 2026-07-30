# Research Agent 03 — Risk Constraints & Hidden Edge Levers

**Scope:** `rapana/risk/guardrails.py`, `rapana/fleet/capital.py`, `rapana/fleet/execution.py`
**Date:** 2026-06-23
**Question:** Map every hard risk constraint so any new profit strategy respects it — and find where a constraint is itself a profit lever.

---

## (a) Constraint Table — every hard limit with current values

All `RiskPolicy` fields are `frozen=True` (`guardrails.py:17`); the LLM brain cannot override them. Defaults live in `rapana/config.py` (`Settings.risk_*`, lines 57–62) and `.env.example:30–36`.

| # | Limit | Default | Defined | Enforced (file:line) | Notes |
|---|------|---------|---------|----------------------|-------|
| 1 | Per-symbol exposure (`max_position_pct`) | **10%** of equity | `guardrails.py:21`, `config.py:57` | `guardrails.py:225–231` | **Buys only.** `sym_new = symbol_exposure[sym] + notional`; deny if `> equity*0.10`. |
| 2 | Total exposure (`max_total_exposure_pct`) | **50%** of equity | `guardrails.py:22`, `config.py:58` | `guardrails.py:217–224` | **Buys only.** `new_total = current_exposure + notional`; deny if `> equity*0.50`. |
| 3 | Per-order notional (`max_notional_per_order`) | **$250** | `guardrails.py:25`, `config.py:61` | `guardrails.py:200–204` | **Both sides** — vetoes buys *and* sells above $250. PM pre-truncates to this (`portfolio_manager.py:61–62, 74–75`). |
| 4 | Order rate (`max_orders_per_min`) | **6 / 60 s rolling** | `guardrails.py:24`, `config.py:60` | Consulted `guardrails.py:194–197`; consumed on actual fill `orchestrator.py:261` | Limiter built once per fleet (`orchestrator.py:112`), clock overridden to **decision-time** (`orchestrator.py:137`) so replay isn't throttled. |
| 5 | Daily loss (`max_daily_loss_pct`) | **3%** of starting equity | `guardrails.py:23`, `config.py:59` | `guardrails.py:138–146, 151–152` | **Realized PnL only.** Trips when `realized_today ≤ -(starting_equity*0.03)`. |
| 6 | Drawdown halt (`halt_drawdown`) | **20%** MTM | `autopilot.py:29`, `config.py:54` | `autopilot.py:79–80, 103–108` | **Off by default** (`autopilot_enabled=False`). Trips the kill switch on current_drawdown. |
| 7 | Drawdown demote (`demote_drawdown`) | **8%** MTM | `autopilot.py:28` | `autopilot.py:81–82, 109–123` | Autopilot-only; resets capital stage to 0. |
| 8 | Sanity price band (`sanity_price_band`) | **±5%** vs ref | `guardrails.py:26`, `config.py:62` | `guardrails.py:207–215` | Symmetric (`abs(price-ref)/ref`). |
| 9 | Staged capital fraction | **1% → 5% → 25% → 100%** | `capital.py:21` | `execution.py:128` (`can_trade`) | **Buys only.** Paper mode forces fraction=1.0 (`capital.py:30–31`). |
| 10 | Kill switch | file flag (off) | `guardrails.py:104–126`, `config.py:28` | `guardrails.py:190–191` | Out-of-band; halts whole fleet. |
| 11 | Preflight gate (live) | env=live, key present, KS clear, fraction>0 | `live_safety.py:34–61` | `live_safety.py:86–94` | Only `LiveGuard` runs it; not wired in CLI builders (DEEP_DIVE ¶51). |

---

## (b) Which edges each limit blocks vs enables

### High-frequency maker strategy (quote both sides, capture spread)
| Limit | Effect |
|-------|--------|
| **#4 orders/min = 6** | **Hard kill.** A maker needs tens of cancel/replace actions per minute across symbols. 6/min total makes a quote stream impossible. (Limiter is *fleet-wide*, not per-symbol — `orchestrator.py:112`.) |
| #3 notional/order = $250 | Soft — maker wants many small orders, so per-order cap is fine; but combined with #4 it forbids scaling quote size. |
| #8 band ±5% | Fine — maker quotes *inside* the spread, well inside 5%. |
| **#1, #2 exposure caps (10% / 50%)** | **Hard kill.** Market-making requires warehousing inventory; forcing flatten at 10% per symbol kills the sleeve's ability to absorb directional flow. |
| #5 daily loss 3% realized | Tolerable — a hedged maker rarely realizes 3%/day, but see (c): open-position risk is untracked. |

→ **The maker edge is structurally blocked by #4 and #1/#2.** None of these exists as a tunable per-sleeve.

### Low-frequency event strategy (funding spike / listing / unlock)
| Limit | Effect |
|-------|--------|
| #4 orders/min = 6 | Fine — events fire rarely. |
| **#3 notional/order = $250** | **Soft block.** To put on $1000 of risk on a spike you need 4 chunked orders; latency between chunks slips the edge. |
| #1, #2 exposure (10% / 50%) | Fine — concentrated bets within 10% per symbol are exactly the use case. |
| **#8 band ±5%** | **Hard block on the cleanest signals.** Real funding/launch moves gap >5% from the rolling last-trade reference; the gate vetoes the entry. |
| #5 daily loss 3% realized | OK in isolation; see (c) for MTM hole. |

→ **Event edge is blocked by #3 granularity and #8 band.**

### Latent issue affecting both
- `reference_price` on the PM path equals `price` exactly (`portfolio_manager.py:56`, `reference = price`; consumed at `portfolio_manager.py:68, 80`). Therefore `deviation = abs(price-price)/price = 0` and **the sanity band never fires in the current pipeline** (`guardrails.py:210`). The control only binds if some other caller emits a proposal where price ≠ reference. So today the band is dead code that *appears* to be protecting you — and conversely, it costs nothing to widen it for the PM path. (It does protect a future live-signal path that may set them differently.)

---

## (c) Flagged risky / profit-relevant behaviors

1. **No maker rebate anywhere.** `LiveExecutor.execute` hardcodes `type="market"` (`execution.py:93–95`) → always pays taker. `PaperExecutor` charges a symmetric 10 bp on every fill (`execution.py:50, 62, 68`) with adverse slippage on both sides (`execution.py:59–60`). **There is no order-type field on `TradeProposal`, no maker/taker distinction in sizing, and no path to earn the maker tier.** Any "0% maker fee" MEXC promo is structurally unreachable. (Confirmed: `grep -i 'maker\|taker\|post_only'` returns only docs and backtest cost models — `backtest/carry.py:50`, `backtest/funding_spike.py:62`, `backtest/engine.py:31` — never execution.)

2. **CircuitBreaker is realized-only and never re-baselines in live mode** (DEEP_DIVE ¶73 confirmed).
   - Tracks only `realized_today` (`guardrails.py:135, 138–146`). A 50% open-position drawdown can sit all day without tripping; only sells feed it (`orchestrator.py:265–268`).
   - Anchored to **construction-time** equity (`guardrails.py:132–134`). No re-baseline on a new day.
   - `reset_day()` (`guardrails.py:157–159`) is invoked **only from `run_replay`** (`runner.py:66–67`). **`run_scheduled` never calls it** — so in live/scheduled paper mode the breaker accumulates indefinitely and, once tripped, stays tripped forever (no auto-clear). One bad day = permanent halt. This is simultaneously a safety bug and the single biggest profit blocker for long-run edge.

3. **A second, MTM-based breaker exists but is off by default.** `Autopilot.evaluate` reads `performance.current_drawdown()` (peak-to-last, mark-to-market) and trips the kill switch at `halt_drawdown=20%` (`autopilot.py:75, 79–80, 103–108`). But `autopilot_enabled=False` (`config.py:49`). So today the only live-mode breaker is the realized-only one in (#2).

4. **Notional cap gates sells too.** `guardrails.py:200–204` vetoes any proposal above $250 regardless of side. An emergency exit on a >$250 position must be chunked by the PM (`portfolio_manager.py:74–75`) — fine in slow paper, dangerous in a fast crash where you need out *now*.

5. **Exposure caps only bind on buys.** `guardrails.py:217` (`if proposal.side == "buy"`). Sells are never gated by exposure — but they're also irrelevant to exposure growth, so this is correct, just worth noting: the gate is one-sided by design.

6. **`LiveGuard` mints a fresh `clientOrderId` per call** (`live_safety.py:96`, `uuid.uuid4().hex[:8]`). Retries are not idempotent → double-fill risk (DEEP_DIVE ¶63). Any live retry logic on a maker quote or event entry would double-trade. (Latent — live path is not wired into CLI builders today, DEEP_DIVE ¶51.)

7. **Paper-fee realism.** Paper charges 10 bp; the backtests assume 2 bp taker (`backtest/carry.py:50`, `backtest/funding_spike.py:62`). A 5× fee mismatch means paper *under-counts* cost vs the backtest gate, so a strategy that passes paper could still lose money at backtest-2bp-fee assumption, or vice versa. Whichever edge you validate, pick one fee model.

---

## (d) Proposed risk-policy changes (unlock edge, hold safety)

### Change 1 — Add an `order_type` field + maker tier on `TradeProposal`
- Add `order_type: Literal["market", "limit_post_only"] = "market"` to `TradeProposal` (`guardrails.py:42`) and `maker_fee_pct`/`taker_fee_pct` to `RiskPolicy` (`guardrails.py:17`).
- `LiveExecutor` selects `type="limit", params={"postOnly": True}` when requested (`execution.py:93`); `PaperExecutor` charges `maker_fee_pct` for post-only fills.
- **Unlocks:** any pure-maker / spread-capture / FIFO-queue edge, and lets the system actually benefit from MEXC's 0% maker promos.
- **Safety:** post-only *cannot* cross — no taker slippage, no surprise fills. Backwards-compatible (default `market` + taker).
- **Cost:** needs the kill on #2 (MTM breaker) first, because a maker sleeve carries open inventory.

### Change 2 — Time-fenced "event sleeve" that relaxes #3 and #8 for a window
- New `EventWindow(symbol, start_ts, end_ts, notional_override, band_override)` registry consulted by `PreTradeChecker` ahead of the static caps. When active for a symbol, `max_notional_per_order` is raised (e.g. $250 → $2000) and `sanity_price_band` widened (e.g. 5% → 15%) **for that symbol only**, still bounded by `max_position_pct` / `max_total_exposure_pct` / `max_daily_loss_pct`.
- **Unlocks:** funding-spike / listing / unlock edges that currently die at the 5% band and the $250 chunking.
- **Safety:** strictly relaxes *granularity*, not absolute risk envelopes; window expires; journaled.
- **Cost:** requires fixing the band's dead reference (`portfolio_manager.py:56` sets `reference=price`) — the event sleeve must populate `reference_price` from a pre-event anchor, or the band check is meaningless.

### Change 3 — Per-sleeve inventory cap for market-making (split `max_position_pct`)
- Add `max_inventory_pct` (e.g. 3%) distinct from `max_position_pct` (10%). A maker sleeve's net position is capped at `min(max_position_pct, max_inventory_pct)`; the directional sleeve keeps the full 10%.
- **Unlocks:** running a maker sleeve and an event sleeve simultaneously without one polluting the other's exposure budget.
- **Safety:** strictly additive — only tightens the MM sleeve; never raises the binding cap.

---

## Pre-conditions (must-fix before any of the above is safe)

These are themselves flagged in (c) but called out as gates:

- **Add mark-to-market to `CircuitBreaker`** (`guardrails.py:138`). Without it, relaxing #3/#8 or adding a maker sleeve that warehouses inventory is unsafe — the realized-only breaker won't see the open risk until you close at a loss. Minimal version: `breaker.check_mtm(equity)` after `state.equity = ...` (`orchestrator.py:142`), tripping if `equity ≤ starting_equity*(1-max_daily_loss_pct)`.
- **Call `reset_day()` from `run_scheduled`** (`runner.py` around line 110). Without per-day rebaseline, live trading permanently halts after one bad day — which is itself an edge-killer, not just a safety bug.
- **Stable `clientOrderId` for retries** (`live_safety.py:96`). Until retries are idempotent, any live maker/event execution risks double-fills.

---

## Bottom line

The constraint set is *internally* coherent for the low-frequency, taker-only, market-order pipeline it was built for — but it has three structural blind spots that are simultaneously the biggest safety holes **and** the biggest edge blockers: (1) no maker path exists, so 0%-maker promos are unreachable; (2) the daily-loss breaker is realized-only and never re-baselines in scheduled mode, so it both *misses* open-position drawdowns and *over-fires* permanently after one bad day; (3) the 5% sanity band is currently dead code on the PM path (`reference==price`) yet would hard-block any genuine event edge if it ever started firing.

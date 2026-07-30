# 58 — Execution Quality: Capacity-aware, Low-footprint Maker Execution

**Agent:** 58/60 · **Topic:** EXECUTION QUALITY — capturing the agent-9 maker edge without
bleeding to slippage, footprint, or MEXC anti-bot flags.
**Posture:** LOW-FREQUENCY, MAKER-ORIENTED, event-driven. Every design choice here must pass
the Safe Operating Envelope in `16-mexc-tos-envelope.md:§5`.
**Status:** The edge from `09-mexc-maker-fee.md` (~1–4 bp/round trip on mid pairs) is **smaller
than typical execution slippage**. A clumsy executor destroys it *before* adverse selection
even gets a vote. This doc is the load-bearing translation of "maker edge" → "maker capture."

---

## 0. TL;DR

> **A maker edge of 1–4 bp can only be captured if execution cost stays < 1–4 bp.** That
> means: (1) **never cross the spread** — `postOnly=True` or reject; (2) **never move the
> book** — single clip ≤ ~0.25% ADV *and* ≤ ~5% of best-price depth, parent ≤ ~1% ADV (well
> inside MEXC's hard 2%-of-24h-volume line, `16:§5.1`); (3) **never look like HFT** — one
> post-only order per symbol per ≥60 s, re-peg only on the signal cadence (≥5–15 min), and
> keep cancel ratio ≤30% by biasing pegs to *fill*, not to *quote*. For size beyond a single
> safe clip, **TWAP into N children spaced ≥60 s apart**; for size beyond a bounded TWAP
> horizon, **do nothing** (capacity guard → hand to human, don't bleed). Concretely: a
> `MakerRouter` sits in front of `LiveExecutor`, turns one `TradeProposal` into a small
> post-only ladder + optional TWAP plan, and rejects the rest — a ~120-line, 3-file addition
> on top of the agent-9 minimal diff.

---

## 1. Capacity & slippage rules (what actually moves price)

### 1.1 The decomposition we are minimizing: implementation shortfall

Implementation shortfall (IS) is the gap between the **decision price** (the mid the PM saw
when it emitted the signal) and the **final execution price**, including fees and the cost of
the unfilled remainder. It decomposes into three additive costs (Wikipedia, *Implementation
shortfall*):

```
IS = delay cost  +  execution cost  +  opportunity cost
   = (price drift         (spread + market       (unfilled qty ×
      while we wait)        impact + fees)          adverse move)
```

A market order minimizes delay+opportunity but **maximizes** execution cost (pays full
half-spread + taker fee + any depth we eat). A naive maker order minimizes execution cost
but **maximizes** delay+opportunity (we wait, we get adverse-selected, we miss fills). The
whole game is choosing the mix. For rapana's edge magnitude, **execution cost must stay
sub-1-bp**, which is why the maker path is mandatory *and* why it must be sized small.

- Source: https://en.wikipedia.org/wiki/Implementation_shortfall
- CFA Institute, *Trade Strategy and Execution* (IS decomposition, TCA):
  https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/trade-strategy-execution

### 1.2 The participation-rate rule of thumb (the one number to internalize)

The single most-used heuristic for "did I move price?": **keep your participation rate tiny.**

| Rule | Source / basis | rapana target |
|---|---|---|
| **Single child clip ≤ ~1% ADV** is the *upper bound* above which permanent impact becomes visible on liquid equities. | Square-root law of market impact (Almgren et al. 2005; Bouchaud / Zarinelli et al. 2015). Wikipedia (*Market impact*): *"keep activity below one-third of daily turnover"* — that is a *large-institution, accept-some-impact* ceiling, **not** a footprint-light target. | **≤ 0.25–0.5% ADV per clip**, i.e. 2–4× below the visibility threshold. |
| **Per-bar participation ≤ ~10%** of 1-min volume is the "no smear" line for a single bar. Beyond it you are the bar. | Standard institutional execution convention (participation-rate / POV algos). | **≤ 2–5% of current 1-min volume** per child — a full order of magnitude under the smear line, because we are *resting maker*, not crossing. |
| **Parent (full intended size) ≤ ~1% ADV**, then capacity-reject. | Internal: stay ~2× under MEXC's hard ">2% of 24h volume" line (`16:§5.1`), which itself is calibrated to the 2025-05-30 case where **50% share = flagged** (`16:§4`). | **Hard reject** if parent notional > `min(1% ADV, 2% 24hVol, 0.5 × best-level-depth × N_children)` → `do nothing`. |

### 1.3 The square-root law (why "a little bigger" costs a lot)

Empirical market impact on most venues scales as the **square root** of participation:

```
impact ≈ η · σ_daily · sqrt(Q / V_ADV)        η ≈ 0.5–1.0
```

where `Q` = order notional, `V_ADV` = average daily volume, `σ_daily` = daily return
volatility. The dominant reference is **Almgren, Thum, Hauptmann, Li (2005), "Direct
Estimation of Equity Market Impact"**; the crypto/equities cross-venue refinement is
**Zarinelli, Treccani, Farmer, Lillo (2015), "Beyond the Square Root"** (finds log dependence
at *high* participation, i.e. the sqrt law *understates* impact when you get big — all the
more reason to stay small). Kyle's λ (price-impact per unit flow) is the linearised version of
the same idea.

**Plug in a MEXC mid pair:** `σ_daily ≈ 4%`, `η ≈ 0.6`. At `Q/V = 0.1%` (one basis-point of
ADV): impact ≈ 0.6·0.04·√0.001 ≈ **0.8 bp** — already comparable to the whole 1–4 bp edge. At
`Q/V = 1%` it is ~2.4 bp; at `Q/V = 10%` it is ~7.6 bp. **Conclusion: the edge is only
survivable at ≤0.25% ADV per clip.** This is the mathematical justification for the rules in
§1.2, not a guess.

- Almgren et al. (2005), *Direct Estimation of Equity Market Impact* (the square-root law):
  http://www.math.nyu.edu/~almgren/papers/costestim.pdf
- Zarinelli, Treccani, Farmer, Lillo (2015), *Beyond the Square Root* (arXiv 1412.2152):
  https://arxiv.org/abs/1412.2152
- Kyle (1985), *Continuous Auctions and Insider Trading* (Kyle's λ):
  https://doi.org/10.2307/1913210
- Wikipedia (*Market impact*): https://en.wikipedia.org/wiki/Market_impact

### 1.4 Depth-aware sizing (the per-book check that ADV can't give you)

ADV is a coarse, lagging capacity proxy. The *instantaneous* capacity is set by the live order
book: a 0.25% ADV order on a pair whose top level only holds 0.05% ADV of depth will eat
multiple levels and leave a footprint regardless of the ADV number. **Fetch the book and cap
the child to a fraction of the top levels.**

`MexcClient.fetch_order_book(symbol, limit=100)` already exists (`rapana/mexc/client.py:136`).
Use it. Concrete depth rule for a post-only peg:

```
child_qty ≤ min(
    0.25% × ADV_notional,
    20% × depth_at_best_price,        # top level only — leave most of it for others
    5%  × depth_top_5_levels,
)
```

Sitting *on* the book (post-only, not crossing) means we do **not** consume depth on
placement — the depth cap is a fill-probability / adverse-selection guard (smaller = more
likely the level trades through us = higher fill rate), not an impact-on-placement guard.
This is the one structural advantage maker has over taker and it is why the design is maker.

---

## 2. Maker fill quality under MEXC's anti-bot envelope

The maker edge is unlocked by *post-only* (guarantees 0% maker fee or rejection, never a
surprise taker fill — `09-mexc-maker-fee.md:§4`). But *how* you place that post-only order
decides whether it fills (captures spread) or sits forever (opportunity cost) or cancels
(trips the cancel-ratio flag). The envelope (`16:§5`) is not a soft preference — it is the
freeze boundary. Every maker rule below is the intersection of "fill me" × "stay invisible."

### 2.1 The four envelope constraints that shape every maker decision

| Envelope rule (`16:§5.1`) | What it forces on maker execution |
|---|---|
| **≤ 1 new order / symbol / 60 s**, ≤ 30 orders/hour global | **No re-quote stream.** You get *one* post per symbol per minute. Make it count: correct peg first time. Re-pricing "to chase the mid" is structurally impossible at HFT cadence — which is the point. |
| **Cancel ratio ≤ 30%** (cancels / (cancels + fills), rolling 24h) | **Bias the peg to fill, not to quote.** For every order you cancel you need ≥ ~2.3 fills to stay legal. Far-outside ladders (agent-9's wide-band) cancel a *lot*; a peg at/near the touch fills a *lot*. **The cancel-ratio rule selects "at-touch-ish" pegs over "wide-band" pegs for this fleet.** |
| **≥ 30 s create→cancel spacing**; ≥ 60 s between executed trades on a symbol; ≥ 5 min between rounds | A maker order must **rest meaningfully** before any cancel. No instant cancel-on-mid-move. If you place it, you own it for ≥ 30 s. → peg it where you are happy to be filled for 30 s+ . |
| **postOnly only** (no crossing); never > 2% of 24h volume; event blackouts ±5 min | Reinforces §1 capacity rules and forbids the "market out on cancel" trick. Exits are also maker where possible, market only as risk-close (`16:§5.1`). |

### 2.2 Peg placement (maximizing fill rate *with* a legal cancel ratio)

Three peg modes, ordered by fill probability (highest first). Pick by intent, not by greed:

1. **Join-touch (highest fill rate, ~0 adverse-spread capture).** `price = best bid` (buy) /
   `best ask` (sell). Queue-fifo behind whoever is already there. Fills on any incoming taker
   sell/buy that takes the level. **Use for exits and inventory-reduce sides** where you want
   to *be out*. Captures ≈ 0 spread but 0% fee — still beats a market exit by the taker fee.
2. **Peg-just-outside-touch (the spread-capture default).** `price = best_bid + 1 tick` (buy,
   i.e. become the new best bid) / `best_ask − 1 tick` (sell). You *are* the touch, queue
   position #1. Captures ≈ half-spread on fill. **Use for fresh entries on a low-freq
   signal.** This is the mode the cancel-ratio rule wants: high fill rate + real spread
   capture.
3. **Wide-band outside-touch (agent-9 ladder).** `price = mid ± k·σ̂`, k≈2–3. Fills only on
   mean-reverting noise. **High cancel rate** → **incompatible with the 30% cancel-ratio cap
   at any sustained cadence.** Keep this for the *rare* one-shot per signal (single order, no
   refresh), not a maintained ladder.

**Reconciliation note on agent 9:** `09-mexc-maker-fee.md:§4` proposes a "wide-band passive
ladder, re-ladder on events every 5–15 min." That design is correct *on the edge* but
**trips the cancel-ratio rule** (`16:§5.2.1`: "any strategy that needs to churn orders … is
not allowed"). The resolution: **mode 2 (peg-just-outside-touch) is the default, mode 3 is a
one-shot per signal (no refresh loop), and re-peg cadence is ≥ the signal cadence (5–15 min),
never sub-minute.** This preserves agent-9's edge math while keeping the cancel ratio legal.

### 2.3 Queue priority is *time-at-level*, not message rate

A durable maker insight worth stating because the envelope rewards it: on FIFO matching
engines (MEXC spot is price-time priority), **queue position is earned by resting longer at
the level, not by re-quoting faster.** The envelope forbids the latter anyway; the former is
free. Therefore: place the peg once, let it rest, and *resist the urge to re-peg on every mid
tick*. Each unnecessary cancel both burns queue position and eats cancel-ratio budget.

### 2.4 The cancel-ratio budget is a global — re-quote cadence falls out of it

With ≤ 30% cancels allowed and a 5–15 min signal cadence, the math is: if you re-peg **once
per signal** and most of your orders fill (modes 1/2), your cancel ratio is ~10–20% — legal.
If you re-peg **continuously** (mode 3 as a maintained ladder), your cancel ratio is ~70–90%
— illegal and freeze-prone. **So the cadence *is* the signal cadence (5–15 min), and the
re-peg *is* a cancel-and-replace only when the live touch has moved past the resting order's
price by more than the spread-capture target.** Below that threshold, leave it alone.

---

## 3. The minimal maker path: `MakerRouter` + TWAP + capacity guard

### 3.1 Where it sits

`MakerRouter` is a **pure planning layer** in front of `LiveExecutor`. It consumes a
risk-approved `TradeProposal` (`guardrails.py:42`) plus a fresh order-book snapshot, and emits
an `ExecutionPlan` — a list of post-only child proposals with pegs and inter-child spacing.
`LiveExecutor` gains one branch that places post-only limits and correctly handles the
"resting, not filled yet" state (return `None`, no `Fill`, let the next tick retry/cancel).
It does **not** run a background quoting loop; it is driven by the existing orchestrator tick
(`orchestrator.py:254-264` already calls `self.trader.execute(...)` on the cadence).

This keeps the LLM outside the order path (`RESEARCH-SYNTHESIS.md:65`) and keeps the executor
the single chokepoint that the rate limiter (`guardrails.py:65`, consumed at
`orchestrator.py:261`) and risk gate already guard.

### 3.2 `MakerRouter.plan()` — the decision tree

```
plan(proposal, book, adv_notional, bar_1m_notional) -> ExecutionPlan:

  # ---- 0. Capacity guard (hard; "do nothing if too big") ----
  parent = proposal.notional
  depth_best = sum(best-level size) * best_price              # from `book`
  if parent > 1% * adv_notional:        return REJECT("too_big_vs_adv")
  if parent > 2% * adv_notional:        return REJECT("over_mexc_2pct_line")  # 16:§5.1
  if parent > 20x depth_best and parent > max_single_clip:    # cannot exit fast
      return REJECT("depth_too_thin")

  # ---- 1. Single-clip maker (the common case) ----
  max_single = min(0.25% * adv_notional, 20% * depth_best, 5% * bar_1m_notional)
  if parent <= max_single:
      child = pegged_child(proposal, book, mode="outside_touch_+1tick")
      return PLAN(children=[child], mode="maker_single", horizon_s=0)

  # ---- 2. TWAP ladder for larger-but-still-feasible size ----
  n_children = ceil(parent / max_single)
  horizon_s = n_children * 60                       # ≥60 s spacing (envelope)
  if n_children > MAX_CHILDREN (e.g. 15) or horizon_s > MAX_HORIZON (e.g. 900 s):
      return REJECT("twap_horizon_unsafe")          # do nothing → human

  children = [pegged_child(child_i, book, mode="outside_touch_+1tick")
              for each child_i, spaced ≥60 s]
  return PLAN(children=children, mode="twap_maker", horizon_s=horizon_s)

  # ---- 3. Unreachable branches ----
  #   market/taker orders: ONLY for explicit risk-close (kill-switch flatten),
  #   never for spread capture. Routed outside MakerRouter.
```

Notes on the tree:
- **`REJECT` ⇒ "do nothing."** The single most important property. A rejected plan logs,
  journals, and returns `None`. It does *not* fall back to a market order — that would convert
  an IS-unsafe trade into a taker bleed. Better to miss the edge than pay it out.
- **TWAP, not VWAP.** Volume-weighted schedules need reliable intrabar volume forecasts and
  continuous re-sizing — both high-footprint and cancel-heavy. Time-sliced TWAP (Wikipedia,
  *Time-weighted average price*) is footprint-light, trivially fits the ≥60 s order spacing,
  and the literature agrees it minimizes impact-vs-info-leakage for *small* parents. For
  rapana's size regime, the difference vs VWAP is well below the noise floor of the edge.
- **Spacing = 60 s exactly** (not "as fast as possible"). This is the *binding* envelope
  constraint (`16:§5.1` ≤1 order/symbol/60s) and it is what makes a 15-clip TWAP take 15 min,
  which is the cap. Beyond that → reject.

### 3.3 TWAP math (concrete numbers, $10k sleeve, $250 notional cap)

Current `RiskPolicy.max_notional_per_order = $250` (`guardrails.py:25`,
`03-risk-edge.md:§a#3`). On a mid pair with ADV $40M:
- `max_single = min(0.25%×40M, 20%×depth_best, 5%×bar)` → typically $100–250 (the notional
  cap binds first → $250).
- Parent $1,000 (4% of a $25k working sleeve) → `n=4`, horizon **4 min**. Comfortable.
- Parent $2,500 → `n=10`, horizon **10 min**. Legal but near the cap; consider halving size.
- Parent $3,750 → `n=15`, horizon **15 min** = `MAX_HORIZON`. The ceiling.
- Parent $4,000 → **REJECT.** Do nothing, alert human.

This is a *much* tighter ceiling than naive intuition. It is correct: agent-9's edge is
1–4 bp and the square-root law says 0.25% ADV already costs ~0.8 bp of impact. There is no
free lunch in sizing — the capacity guard is the edge's immune system.

---

## 4. Minimal code change vs current `LiveExecutor`

The repo today is **market-only** by direct inspection (`rapana/fleet/execution.py:93-95`
hardcodes `type="market"`; `TradeProposal` has no `order_type` field,
`guardrails.py:42-56`; `MexcClient` has no order methods, `client.py:31-155`). This builds
**on top of** the agent-9 minimal diff (`09-mexc-maker-fee.md:§6`), not in place of it.

### 4.1 Layered diff (4 files, ~150 lines total incl. agent-9's ~40)

**Layer A — agent-9 prerequisites (already specced, do first):**
1. `client.py`: `create_maker_order(...)` + `fetch_symbol_commission(...)` (per `09:§6.1`).
2. `guardrails.py:42`: `TradeProposal.order_type: str = "market"` (`09:§6.2`).
3. `execution.py:88`: branch on `order_type == "maker"` → place post-only limit, **return
   `None` when `status != "closed"`** (no `Fill`) — the resting-order semantics that agent-9
   flags as out-of-scope for the minimal change (`09:§6.3`).

**Layer B — this agent (the missing execution-quality layer):**

4. **`rapana/fleet/maker_router.py` (NEW, ~100 lines):** `ExecutionPlan` dataclass +
   `MakerRouter.plan()` (§3.2 tree) + `pegged_child()` helper (modes 1/2/3 from §2.2). Pure
   function of (proposal, book, adv, bar_vol). No I/O. Trivially unit-testable. Reads depth
   via the existing `MexcClient.fetch_order_book` (`client.py:136`); ADV/bar via existing
   `fetch_ticker`/`fetch_ohlcv` (`client.py:58,71`).

5. **`execution.py` — add `LiveExecutor.execute_plan(plan)` (~25 lines):** iterates the plan's
   children on the orchestrator tick (one child per ≥60 s — naturally enforced by the existing
   `OrderRateLimiter`, `guardrails.py:65`, consumed at `orchestrator.py:261`). For each child:
   - place via `client.create_maker_order(...)` (post-only);
   - if `status == "open"` → store order id in a per-symbol "resting" map, return `None`
     (no `Fill`, no rate-budget consumption on a non-fill);
   - if `status == "closed"` → return `Fill(fee=0)` (the 0% maker capture);
   - on the next tick, if a resting order is stale beyond the signal cadence (≥5–15 min) *and*
     the touch has drifted past it by > spread-capture target → **cancel it once** (respects
     ≥30 s create→cancel, `16:§5.1`), log the cancel, decrement the cancel-ratio budget.

6. **`guardrails.py` — add a `CancelRatioMeter` (~15 lines), sibling of `OrderRateLimiter`:**
   rolling-24h `cancels / (cancels + fills)`; `would_breach()` consulted in `PreTradeChecker`
   ahead of any new maker child, same pattern as the rate limiter at `guardrails.py:194-197`.
   **This is the load-bearing compliance primitive** — without it, MakerRouter is unsafe by
   construction.

7. **`PaperExecutor.execute` (`execution.py:56`) — add maker branch (~5 lines):** when
   `order_type == "maker"`, charge `fee_pct=0` (per `09:§6.4`) *and* apply a fill-probability
   model (e.g. fill iff `abs(child_price - arrival_mid) ≤ 1 tick OR random < p_fill`) so the
   backtest reflects the **opportunity cost** of resting, not just the fee saving. Today the
   paper path deterministic-fills every maker order at 0 fee — that *overstates* the edge by
   exactly the IS opportunity-cost term. Cheap to fix, expensive to ignore.

### 4.2 What this does NOT add (by design)

- **No background quoting loop / asyncio.** MakerRouter is tick-driven by the existing
  orchestrator. A loop is the #1 way to look like HFT and trip `16:§5.6.1`.
- **No VWAP, no POV, no adaptive scheduling.** Overkill at this size; TWAP is the
  policy-respecting floor.
- **No websocket.** `08-mexc-client-edge.md:§c#3` flags ws absence; for *execution* (not
  signal latency) it is unnecessary — resting orders do not need ms-level book feeds, and a
  ws would *increase* footprint risk.
- **No multi-account / parallel children.** One account, one IP, one symbol-stream
  (`16:§5.1`); TWAP children are strictly sequential.

### 4.3 Compliance reconciliation (envelope × execution, row by row)

| Envelope (`16:§5.1`) | How MakerRouter satisfies it |
|---|---|
| postOnly only | Layer-A branch sets `postOnly=True`; MakerRouter never emits a market child. |
| ≤1 order/sym/60s | TWAP spacing = 60 s; single-clip is 1 order; enforced by existing `OrderRateLimiter`. |
| cancel ratio ≤30% | New `CancelRatioMeter` (Layer B.6) gates every cancel; default peg = mode 2 (fill-biased). |
| ≥30 s create→cancel | Stale-order cancel only fires after the ≥5–15 min signal cadence. |
| never >2% 24h vol | Capacity guard §3.2 step 0 REJECTs on `parent > 1% ADV` (2× margin). |
| event blackouts ±5 min | Reuse the event calendar from `36-event-driven.md` (existing agent); MakerRouter consults it before placing. |
| jittered cadence | TWAP child spacing jittered ±30% (`16:§5.1` last row). |
| idempotent retries | Use stable `clientOrderId` per child (fixes `03-risk-edge.md:§c#6`). |

---

## 5. Evidence index (URLs)

**Execution quality / slippage / capacity:**
- Almgren, Thum, Hauptmann, Li (2005), *Direct Estimation of Equity Market Impact* (the
  square-root law of impact): http://www.math.nyu.edu/~almgren/papers/costestim.pdf
- Zarinelli, Treccani, Farmer, Lillo (2015), *Beyond the Square Root: Evidence for Logarithmic
  Dependence of Market Impact on Size and Participation Rate*, arXiv:1412.2152:
  https://arxiv.org/abs/1412.2152
- Kyle (1985), *Continuous Auctions and Insider Trading* (Kyle's λ — price impact per unit
  flow), *Econometrica* 53(6): https://doi.org/10.2307/1913210
- CFA Institute (2026 refresher reading), *Trade Strategy and Execution* (implementation
  shortfall decomposition, TCA): https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/trade-strategy-execution
- Wikipedia, *Implementation shortfall*: https://en.wikipedia.org/wiki/Implementation_shortfall
- Wikipedia, *Market impact* (participation-rate "below one-third of daily turnover"
  institutional ceiling; Kyle's λ; sqrt vs log impact):
  https://en.wikipedia.org/wiki/Market_impact

**TWAP / scheduling:**
- Wikipedia, *Time-weighted average price* (TWAP minimises large-order impact; even slicing
  vs VWAP): https://en.wikipedia.org/wiki/Time-weighted_average_price
- Wikipedia, *Volume-weighted average price* (cross-reference for why TWAP is the
  footprint-light choice at small size): https://en.wikipedia.org/wiki/Volume-weighted_average_price

**Maker / queue mechanics / cancel-ratio reality:**
- Hummingbot FAQ (market making = liquidity provision; the open-source reference for retail
  CEX maker bots and the cancel/refresh trade-off): https://hummingbot.org/faq/
- Hummingbot strategy docs (pure market making, order refresh / cancel parameters — community
  reference for the cadence-vs-fill-rate tuning that the MEXC envelope forces tighter):
  https://hummingbot.org/strategies/
- Avellaneda & Stoikov (2008), *HFT in a Limit Order Book* (inventory-aware quote placement —
  cited in `09:§3`): the spread you can safely capture is a *fraction* of the half-spread.

**MEXC envelope + repo grounding (in-repo, primary):**
- `research/agents/16-mexc-tos-envelope.md` — the Safe Operating Envelope (the rule).
- `research/agents/09-mexc-maker-fee.md` — the maker edge magnitude (1–4 bp) + Layer-A diff.
- `research/agents/08-mexc-client-edge.md` — client method inventory; confirms
  `fetch_order_book` exists, no order methods.
- `research/agents/03-risk-edge.md` — risk constraints (`max_notional_per_order=$250`,
  `max_orders_per_min=6`, circuit-breaker holes, non-idempotent `clientOrderId`).
- `rapana/fleet/execution.py:88-113` — market-only `LiveExecutor` (the change target).
- `rapana/risk/guardrails.py:42,65,194-204` — `TradeProposal`, `OrderRateLimiter`,
  `PreTradeChecker` notional cap (the integration points).

---

## 6. Bottom line

Execution quality is the **immunity system** for the maker edge: the edge is 1–4 bp, the
square-root law says ~0.8 bp of impact already appears at 0.25% ADV, and MEXC's anti-bot
envelope forbids the HFT tools (fast re-quotes, cancel-storms, depth-eating) that a naive
maker would reach for. The compliant, edge-preserving design is narrow and exact: **post-only
at just-outside-touch, single-clip ≤0.25% ADV / ≤20% best-depth, TWAP at 60 s spacing for
larger-but-feasible size, REJECT-and-do-nothing for everything beyond a ~15-min horizon, and a
`CancelRatioMeter` as the load-bearing compliance primitive.** It is ~150 lines layered on
agent-9's ~40, all tick-driven off the existing orchestrator — no loops, no websockets, no
multi-account — and it is the difference between the maker edge being *captured* vs *paid
out*.

# 50 — `PassiveProvider`: a slow, inventory-capped maker-MM design that survives MEXC's anti-bot envelope

**Agent:** 50/60 · **Scope:** a systematic but **low-frequency, inventory-capped, post-only**
passive-providing strategy that captures the 0% maker spread (agent 9) while staying
inside the Safe Operating Envelope (agent 16).
**Posture:** SLOW, WIDE, GENUINE-INTENT. This is **not** a market-maker in the HFT sense —
it is a handful of high-fill-rate resting orders, re-quoted every 5–15 min, with hard
inventory stops and a trend gate. Honest expected edge: **Sharpe ~0.3–0.6**, small but
**decorrelated** from every directional strategy in the fleet.

---

## 0. TL;DR

- **Honest MM reality (confirmed against agent 9 + agent 31 literature):** adverse
  selection caps pure market-making; the 0% maker fee flips it from *negative* to
  *marginally positive* expectancy, it does **not** make it a profit engine. On majors
  (BTC/ETH, 1 bp) it is ~0; on mid-liquidity pairs (3–10 bp) it nets **~1–4 bp/round-trip**
  *after* inventory drawdowns; on the long tail it is **negative**.
- **The binding constraint is the ≤30% cancel ratio (agent 16 §5.1), not adverse
  selection.** Classic churning/grid MM trips §5.2.6 (quote-stuffing) by construction
  (agent 16 §5.2 corollary 1 calls it "structurally impossible"). The cap is equivalent to
  **requiring ≥70% fill probability** (`cancel_ratio = 1 − fill_prob`). This single fact
  reshapes the entire design: you cannot post far-from-mid orders (low fill prob → trips
  the ratio); you must post **fill-mostly, cancel-rarely** orders.
- **The compliant pattern is the *inventory-targeted round-trip*** (§3.7): post the side
  that pulls inventory back toward flat, near enough to mid to fill (≥70% prob), let it
  fill, then post the opposite to complete the round trip. Two fills, ~zero cancels per
  completed cycle → cancel ratio ~0. Cancels only occur on the rare missed unwind, which
  the inventory stop converts to a one-shot market flatten.
- **Design:** 2–3 mid-liquidity pairs · Avellaneda-Stoikov-**lite** (slow) reservation
  price with inventory skew · 5–15 min re-quote cadence (≤1 order/symbol/60s, jittered,
  create→cancel ≥30s) · trend-filter/regime gate (agent 41) disables in strong trends ·
  hard inventory cap → market-flatten + cooldown. **Never crosses the spread, never
  cancels within 30s, never churns.**
- **ToS verdict (§4):** slow passive providing sits in agent 16's **safe zone** (§3:
  "maker limit orders, post-only … adds liquidity … aligns with MEXC's 0% maker fee
  intent"). The **only** ToS tripwire is the cancel-ratio pattern — and the design is
  built specifically to hold it ≤30% by construction. Likely safe; the cancel meter must
  be a **code contract**, not a hope.

---

## 1. Honest market-making reality (no fiction)

Three results from agent 9's literature pass and agent 31's microstructure synthesis are
load-bearing here, and they are why this strategy is sized as *discipline + decorrelation*,
not *alpha*:

1. **The 0% maker fee is necessary but not sufficient** (Menkveld 2013; Hummingbot
   community backtests, agent 9 §3). On equilibriated venues the maker rebate/spread is
   competed down to ≈ the adverse-selection cost → naive passive provision earns **~0
   net**. The 0% fee removes the fee drag that would otherwise *guarantee* a loss; the
   remaining edge is the raw half-spread minus adverse selection, which is **small and
   pair-dependent**.

2. **Adverse selection is the killer mechanism** (Avellaneda-Stoikov 2008; Cartea,
   Jaimungal & Penalva 2015, agent 9 §3, agent 31 §5). A maker fill is *not* symmetric
   information — you are filled because a taker *chose to cross*, which is correlated with
   the mid moving against you. Net profit requires **skewing/cancelling on one-sided flow**,
   otherwise half-spread revenue ≈ adverse-selection loss. Sustained one-sided/toxic flow
   (VPIN, agent 31 §5) is exactly the regime where maker entries get run over.

3. **The edge scales inversely with liquidity** (agent 9 §2): majors ~1 bp (edge ≈ 0),
   mid-liquidity 3–10 bp (**~1–4 bp net**), long tail 10–250 bp (**negative** — widest
   spreads are widest *because* informed flow dominates them). The naive intuition "wide
   spread = free money" is precisely backwards.

**Synthesis:** a slow, wide, inventory-managed ladder at 0% maker can be **marginally
positive** and is structurally lower-risk than any directional strategy — but it will
**not** be a large P&L contributor. Its fleet value is **decorrelation + enforced
discipline + capturing an edge that is currently 0% captured** (agent 9 §6: no maker path
exists today).

---

## 2. The binding constraint is the cancel ratio, not adverse selection

Agent 16 §5.2 corollary 1 is blunt:

> "Any strategy that needs to *churn* orders (grid re-pricing, MM quote refresh) is **not
> allowed on MEXC** in the retail sleeve. The cancel-ratio cap (≤30%) makes classic
> grid/MM structurally impossible — that is by design."

This is the single fact that decides the design. Derive it explicitly. If each resting
order independently either **fills** (prob `p`) or is **cancelled once** (prob `1−p`):

```
cancel_ratio = E[cancels] / (E[cancels] + E[fills])
             = N·(1−p) / (N·(1−p) + N·p)
             = 1 − p
```

**∴ `cancel_ratio ≤ 0.30`  ⟺  `fill_probability ≥ 0.70`.** (agent 16 §5.1 row:
"cancels/(cancels+fills) on rolling 24h".)

This has three immediate, uncomfortable consequences that shape every parameter below:

| Consequence | Why it bites | Design response |
|---|---|---|
| **You cannot post far from mid.** Far orders (the "safe" wide band that minimises adverse selection) have low fill prob → trip the ratio. | The adverse-selection-minimising band and the cancel-ratio-minimising band are in **direct conflict**. | Post in a **narrow band** close enough to mid to fill ≥70% of the time (§3.2). Accept the adverse selection this invites; offset it with the trend gate (§3.6) + inventory stop (§3.5). |
| **A symmetric 2-sided ladder is risky.** Per cycle, typically *one* side fills and the *other* cancels → ~50% ratio, over the cap. | The "always quote both sides" MM reflex violates the envelope. | Use **inventory-targeted single-side posting** (§3.7): post only the side that pulls inventory toward flat. A completed round trip = 2 fills, ~0 cancels. |
| **"Cancel-and-replace to chase mid" is forbidden.** Re-pricing on every mid tick is quote-stuffing (§5.2.6) and trips both the cancel ratio and the ≥30s create→cancel rule. | Classic MM quote refresh is the exact pattern MEXC flags. | Re-quote on a **fixed, jittered 5–15 min cadence only**; let orders rest the full cycle; cancel **once** at cycle end only if unfilled (§3.3). |

**This is why `PassiveProvider` is "passive providing", not "market making".** It does not
make a continuous market. It places a handful of genuine-intent resting orders that are
*expected to fill*, lets them fill, and only rarely cancels. Agent 16 §5.2 corollary 2 is
the north star: *"Maker orders must represent genuine intent to take the position, sit for a
meaningful time, and either fill or be cancelled once — never refreshed in a loop."*

---

## 3. `PassiveProvider` design

### 3.1 Universe — mid-liquidity only, 2–3 pairs

| Class | Spread | Run? | Reason |
|---|---|---|---|
| Majors (BTC/ETH) | 1 bp | **No** | Edge ≈ 0 after adverse selection (agent 9 §2). |
| **Mid-liquidity (SOL, XRP, DOGE, LINK, ADA, BNB)** | **3–10 bp** | **Yes** | The only band with positive net (~1–4 bp/RT). |
| Long tail / new listings | 10–250 bp | **Never** | Adverse selection > spread; informed-flow donation (agent 9 §2, agent 16 §3). |

Pick **2–3** of the most liquid mid pairs (highest 24h volume, tightest spread within the
3–10 bp band). Cap each at **≤2% of the pair's 24h volume** (agent 16 §5.1) — for these
pairs that is a generous cap; the inventory stop (§3.5) binds long before it.

### 3.2 Quoting — Avellaneda-Stoikov-lite reservation price + skew

Compute a slow **reservation (indifference) price** à la Avellaneda-Stoikov (2008), but
intentionally coarse and slow (no tick-level anything):

```
r = mid − q · γ · σ̂² · τ          # reservation price; q = inventory units (+=long)
bid = r − δ_half                  # δ_half = target half-spread, inventory-widened
ask = r + δ_half
```

- `mid` — last mid at re-quote tick.
- `q` — signed inventory in **units** (not notional), capped at the inventory stop (§3.5).
- `γ` — risk-aversion, tuned small so skew is *gentle* (a few bp), not panic-selling.
- `σ̂` — **slow** volatility: EWMA of 1h returns over a multi-hour window. Slow on
  purpose; the trend gate (§3.6) handles the fast-regime risk σ̂ can't see.
- `τ` — time-to-horizon scaled so the skew term is a few bp at the inventory stop, ~0 at
  flat. Coarse; this is AS-**lite**, not a calibrated HFT model.
- `δ_half` — half-spread, set **inside the adverse-selection-favourable band but close
  enough to mid to keep fill prob ≥0.70** (the §2 constraint). Concretely: post at the
  touch ± 0–2 ticks (top of book or one tick behind), not at ±1–3%. *Wide* here means
  "off-touch by a tick or two", not "% away" — the % figure from the brief is honoured in
  spirit (outside the touch) but must collapse toward the touch to satisfy the cancel ratio.

**The skew does the inventory management.** When long (`q>0`), `r<mid` → both quotes shift
down → the ask is closer to mid (more likely to sell/unwind) and the bid drops away (less
likely to buy more). This is the slow AS skew; it is the *primary* inventory control. The
hard inventory stop (§3.5) is the *backstop*.

**post-only is non-negotiable** (agent 16 §5.1): every order carries `postOnly=True`, so it
either rests at 0% maker or is **rejected** — zero taker-fee risk, zero accidental cross
(see agent 9 §6 `create_maker_order`).

### 3.3 Re-quote cadence & rate discipline (the envelope)

| Envelope rule (agent 16 §5.1) | `PassiveProvider` setting |
|---|---|
| ≤1 new order / symbol / 60s | Re-quote every **5–15 min** per symbol → ≤1 order/300s, trivially satisfied. |
| ≤30 orders/hour global | 2–3 symbols × ~1–2 orders/cycle × ~4–6 cycles/hour ≈ 8–24 orders/hr — **inside, with headroom**. |
| No >3 orders / 10s window | One symbol re-quotes per cycle; cycles **staggered + jittered ±30%** (agent 16 §5.1 "cadence pattern"). Never burst. |
| ≥30s create→cancel | Orders rest the **full 5–15 min cycle**; cancel happens only at cycle end → ≥300s, always satisfied. |
| ≥60s between executed trades / symbol | Round-trip legs are different cycles (≥5 min apart) → satisfied. |
| Event blackouts (±5 min: listings, 0-Fee, funding, UTC rollover) | **Hard skip** — the scheduler must suppress re-quotes in these windows (agent 16 §5.1). |
| Jittered cadence (anti "synchronized") | ±30% randomization on the 5–15 min schedule. |

**One cancel per cycle, maximum.** At cycle end, if the resting order is unfilled, cancel
it **once** and post the next cycle's order. Never cancel-mid-cycle to chase mid.

### 3.4 Inventory skew (the slow AS engine, day-to-day)

On every re-quote tick, recompute `q`, `σ̂`, and the reservation price, and decide which
side (if any) to post for the cycle:

- **`q ≈ 0` (flat):** post the side with the better近期 mean-revert probability, or simply
  alternate. (A symmetric bid+ask here would risk the §2 cancel problem; prefer one side.)
- **`q > 0` (long):** skew down → post (or favour) an **ask** to unwind toward flat.
- **`q < 0` (short):** skew up → post (or favour) a **bid** to unwind toward flat.

Because spot has no native short, `q<0` only arises after a sell-to-flat of accumulated
long inventory is **partial** — in practice the sleeve runs **long-or-flat** and the
"short" branch is the unwind of a long. This keeps the strategy unambiguously
directional-risk-carrying (genuine market risk), which is what keeps it off the §5.6.2
"locked/hedged exposure" tripwire (agent 16 §5.1).

### 3.5 Inventory stop + flatten (the tail control)

This is the **single most important risk control** — it is what separates "passive
providing" from "accidentally taking a position in a trend" (agent 9 §4).

```
if |q| >= INV_STOP_UNITS  or  |notional(q)| >= INV_STOP_PCT * equity:
    1. cancel any resting order (once)
    2. market-flatten the inventory (the explicit "give up the maker edge to kill the risk" case)
    3. HALT the provider for this symbol for a COOLDOWN (e.g. 1–4 hours)
    4. log the event for human review
```

- `INV_STOP_UNITS` / `INV_STOP_PCT` — set tight: e.g. **2–3 round-trip units**, or **≤3–5%
  of equity** per symbol, whichever binds first. The whole point is to never let a one-sided
  tape accumulate a real position.
- The market-flatten is the **only** sanctioned taker order in the strategy, and it is
  explicitly a risk-close (allowed by agent 16 §5.1: "Market orders only for explicit
  risk-close"). It is rare by construction (only on stop breach).
- Cooldown prevents the "stop → re-enter → stop" whipsaw that would otherwise churn both
  the account and the cancel ratio.

### 3.6 Trend-filter / regime gate (agent 41 — forward dependency)

**Disable the provider in strong-trend regimes.** In a trend, resting orders get run over
(adverse selection) and inventory accumulates one way until the stop fires repeatedly — a
slow bleed. The provider only makes sense in **range / mean-revert** regimes.

- **Dependency:** this requires a **regime classifier** (`research/agents/41-*`, not yet
  written as of this report — the agents directory ends at 40). Until it exists, use a
  crude proxy: **ADX/Hurst on 1h bars**, or a simple "rolling drift vs σ̂" test
  (drift/σ̂ above a threshold → trend → gate off). Flag this as a hard prerequisite for
  live deployment.
- **Secondary toxicity veto:** borrow agent 31 §5's VPIN-toxicity read as a *veto* — when
  sustained toxic flow is detected, decline to post (sidestep adverse selection). Same
  role as agent 14's wide-spread veto. Read-only, veto-only, never a trigger.

**The regime gate is what makes the §2 narrow-band quoting survivable.** You post close to
mid (high fill prob) *only when* the regime says "mean-revert"; in a trend you stand down.
Without it, the narrow band gets you run over.

### 3.7 The compliant round-trip pattern (how the cancel ratio stays ~0)

This is the operational heart. For one symbol, one cycle:

```
1. Regime gate: if trend/toxic → stand down this cycle (no order, no cancel).
2. Read q (inventory), σ̂ (slow vol), mid.
3. Compute reservation price r = mid − q·γ·σ̂²·τ.
4. Decide side: the side that pulls q toward 0 (ask if long, bid if flat-alternate, etc.).
5. If |q| >= INV_STOP → flatten + halt + cooldown (§3.5). Else:
6. Post ONE post-only limit at bid=r−δ or ask=r+δ (off-touch by ≤2 ticks; fill prob ≥0.70).
7. Rest the full cycle (5–15 min). Do NOT re-price mid-cycle.
8. At cycle end:
     - if filled   → book the fill; inventory moved toward/through target; next cycle recomputes.
     - if unfilled → cancel ONCE (≥30s after create, trivially satisfied); next cycle reposts.
```

A **completed round trip** (buy fill then sell-to-flat fill, across two cycles) = **2
fills, 0 cancels** → contributes 0 to the cancel ratio. Only the occasional *missed unwind*
(a posted ask the price ran away from) produces a cancel. With fill prob ≥0.70 and the
trend gate suppressing the run-away cases, the rolling-24h cancel ratio stays **well under
30%** by construction. **The cancel-ratio meter must be a code contract** (agent 16 §6:
"enforce §5.1 at the order-path level … a code contract, not a doc") — if it drifts above
~25%, the provider self-throttles (widens cycle, raises fill-prob target) before hitting
the cap.

---

## 4. ToS-safety analysis (does slow passive providing trip MEXC anti-bot?)

**Verdict: in the safe zone, with one tripwire that the design is built around.** Checked
row-by-row against agent 16 §5.1 and §3:

| Envelope row (agent 16 §5.1) | `PassiveProvider` posture | Safe? |
|---|---|---|
| **Spot only** | Spot only. No futures/perp. | ✅ |
| **`postOnly` limit only; market only for risk-close** | Every quote `postOnly=True`; the only market order is the §3.5 inventory-stop flatten. | ✅ |
| **≤1 order/symbol/60s; ≤30/hr global** | 5–15 min cadence → ≤1/300s/symbol; ~8–24/hr global. | ✅ |
| **Cancel ratio ≤30%** | **Built to hold ≤30% by construction** (§2, §3.7): fill-prob ≥0.70 target, inventory-targeted round-trips, one cancel/cycle max, self-throttle at 25%. | ✅ (the load-bearing one — must be enforced as code) |
| **≥30s create→cancel** | Orders rest 5–15 min; cancel at cycle end only. | ✅ |
| **≥60s between executed trades; ≥5 min between rounds** | Round-trip legs are separate cycles (≥5 min). | ✅ |
| **No >3 orders/10s; no sub-second** | Staggered, jittered; one symbol/cycle. | ✅ |
| **Event blackouts** | Hard skip in ±5 min windows. | ✅ |
| **Arbitrage — ALL forms** | None. Single venue, single account, directional inventory risk. | ✅ |
| **Hedging / market-neutral** | **Not hedged.** Carries genuine directional inventory risk (long-or-flat). Avoids §5.6.2. | ✅ |
| **One account / one IP / no spoofing** | Single client pattern; genuine-intent orders that fill (the opposite of spoofing/layering). | ✅ |
| **≤2% of 24h volume** | Hard cap; inventory stop binds far earlier on mid pairs. | ✅ |
| **Jittered cadence** | ±30% on the 5–15 min schedule. | ✅ |

**Why it's safe (the framing):** agent 16 §3 lists "maker limit orders, post-only" and
"low-frequency, manual-style API trading" explicitly in the **allowed** column — making
liquidity at a human cadence is the *opposite* of the HFT/arb/quote-stuffing patterns
MEXC's policy targets (S1 §3, S2 §5.6). The first-offense-leniency clause (S1 §2) favours
exactly this profile: small, slow, non-arb, non-impact, clearly behavioural.

**The one tripwire — and how it's defused:** the only realistic ToS exposure is the
**cancel-ratio / §5.2.6 / §5.6.1** pattern ("frequent placement & cancellation,
short-duration"). Classic MM trips it by design. `PassiveProvider` survives only because
§3.7 makes fills dominate cancels. **If the cancel meter ever drifts >25–30%, the strategy
is by definition mis-tuned (fill prob too low) and must self-throttle or halt** — a drifting
cancel ratio is both a ToS breach risk *and* a signal that the quotes are too far from mid
to fill, i.e. the edge is also gone. Treat the cancel meter as a **dual-purpose** control:
ToS compliance + edge-health.

---

## 5. Expected edge (honest magnitude)

| Pair class | Gross spread | − Adverse selection | − Inventory cost | **Net / round trip** |
|---|---|---|---|---|
| Majors (BTC/ETH) | 1 bp | ~1 bp | ~0 | **~0 bp** (do not run) |
| **Mid-liquidity (SOL/XRP/DOGE/LINK/ADA)** | **3–10 bp** | **1–4 bp** | **1–3 bp** | **~1–4 bp** |
| Long tail / new listings | 10–250 bp | > spread | high | **negative** (never run) |

**Volume realistic under the envelope:** with a 5–15 min cadence, ~4–6 re-quote
cycles/hour/symbol, but only the high-fill-prob posts trade, expect **~1–2 round trips per
pair per day** (the cadence and the regime gate both suppress activity — that is the cost of
compliance). Across **2–3 pairs** on a **$5–10k sleeve**:

```
~1–4 bp/RT × 1–2 RT/pair/day × 2–3 pairs × ~$5–10k notional/RT
≈ $3–$30 / day gross  →  low-single-digit % / month
```

This matches the literature ceiling for 0%-maker retail MM (agent 9 §4) and the Hummingbot
community pattern. **Sharpe ~0.3–0.6** — modest, but the return stream is **decorrelated**
from the fleet's directional/momentum/event strategies (it harvests mean-revert noise,
precisely when directional is flat or chopping). Its fleet value is **diversification +
discipline + monetising a 0%-captured edge**, not headline P&L.

**Honest caveat:** "Sharpe 0.3–0.6" assumes the trend gate (§3.6) works and the inventory
stop (§3.5) holds. Without the regime gate, a single multi-day trend can produce a string
of inventory-stop flattens that wipes months of spread capture. **The strategy is
regime-gated mean-revert harvesting; it bleeds in trends and must stand down in them.**

---

## 6. Implementation touch-points in rapana (all forward dependencies)

`PassiveProvider` is **strategy code on top of primitives that do not yet exist**. Three
gated prerequisites, in order:

1. **The maker execution primitive (agent 9 §6) — hard prerequisite.** Today
   `LiveExecutor` is market-only (`execution.py:95`), `TradeProposal` has no `order_type`
   (`guardrails.py:42`), and `MexcClient` has no order methods (`client.py:32-36`). Agent
   9's ~40-line, 3-file change (`create_maker_order` + `postOnly=True`, `order_type` field,
   maker branch in `LiveExecutor`, 0 bp maker mode in `PaperExecutor`) must land first.
   Without it this strategy is **unbuildable**, not merely unprofitable.

2. **The regime classifier (`research/agents/41-*`) — hard prerequisite for live.** Until
   it exists, a crude ADX/Hurst proxy on 1h bars is acceptable for paper/forward-test, but
   **live deployment should block on a validated regime gate** (the trend gate is what
   makes the narrow-band quoting survivable, §3.6).

3. **Maker backtest path + L2/history.** `PaperExecutor` must charge 0 bp in maker mode
   (agent 9 §6 item 4) so the edge is *measurable* before risking capital. A true maker
   backtest also needs fill-probability modelling — there is **no L2 history** in the store
   today (`store.py` has only candles/funding/meta; agent 14 §f) — so the edge estimate
   above is literature-calibrated, not yet repo-backtested. **Sequence: ingest book
   history (weeks), forward-validate the fill-probability assumption out-of-sample, only
   then size up live.**

**Where the strategy code lives (on top of the primitives):** a new
`rapana/agents/passive.py` mirroring the analyst/agent pattern, owning the reservation
price, skew, regime gate, inventory state, cancel-ratio meter, and the §3.7 cycle loop. It
emits `TradeProposal(order_type="maker")` proposals; the existing `OrderRateLimiter`
(`guardrails.py:65`), `PreTradeChecker` sanity band (`guardrails.py:206`), `KillSwitch`
(`guardrails.py:104`), and `CircuitBreaker` (`guardrails.py:129`) all apply unchanged as
the hard veto layer.

**New state the strategy must own (not in the repo yet):**
- per-symbol inventory `q` (units + notional),
- rolling-24h cancel/fill counters (the dual-purpose ToS + edge-health meter),
- slow `σ̂` EWMA per symbol,
- regime label per symbol (from agent 41),
- cooldown timers per symbol (post-inventory-stop).

---

## 7. Open risks / what this does NOT protect against

- **The cancel ratio is a guess at the boundary.** MEXC publishes no thresholds (agent 16
  §2, §7); ≤30% is our conservative internal line. The strategy must self-throttle well
  below it (target rolling ≤20–25%) and halt on any drift.
- **Adverse selection is unbudgetable ex-ante.** The ~1–4 bp net assumes the *average*
  informed-flow cost; a single toxic event (agent 31 §5 VPIN spike) can exceed a week's
  capture. The toxicity veto (§3.6) is the only mitigation, and it is read-only/latent.
- **Regime-gate false negatives.** If the trend gate (agent 41) mis-classifies a trend as
  range, the provider accumulates inventory until the stop fires — possibly repeatedly
  across the cooldown. Trend-gate quality is load-bearing for the Sharpe estimate.
- **Fee promo expiry.** The 0% maker is a *campaign/MX-deduct state*, not a permanent tier
  (agent 9 §1). `create_maker_order` must verify the live per-account maker rate via
  `Query Symbol Commission` and **fail closed** if maker > 0 (agent 9 §5). If the promo
  ends, this strategy reverts to **negative** expectancy and must auto-disable.
- **MiCA 2026-07-01** (agent 16 §7) is a jurisdictional access risk independent of trading
  behaviour — it can interrupt the venue irrespective of how safe the order pattern is.
- **Not a hedge, not a diversifier of drawdown timing.** "Decorrelated" means uncorrelated
  *expected returns*, not that it profits when directional loses. In a fleet-wide risk-off
  / de-gross, it provides little cushion.

---

## 8. Bottom line

A slow, wide, inventory-managed post-only ladder at 0% maker is **marginally positive**
(~1–4 bp/round-trip on 2–3 mid-liquidity pairs, Sharpe ~0.3–0.6) and **decorrelated** from
the fleet's directional edges — real but modest. It is **not** classic market-making: the
MEXC ≤30% cancel-ratio cap (agent 16 §5.1, "structurally impossible" for churning MM per
§5.2 corollary 1) mathematically forces a **≥70% fill-probability, fill-mostly/cancel-rarely,
inventory-targeted-round-trip** design (§2, §3.7) that is in agent 16's safe zone but only
as long as the cancel meter is enforced as code. It is **unbuildable today** — it depends on
the maker primitive (agent 9 §6, absent), a regime gate (agent 41, unwritten), and L2
history for backtesting (agent 14, absent). Build those three, forward-validate the
fill-probability assumption out-of-sample, then deploy small as **discipline + decorrelation
+ a 0%-captured edge**, not as a profit engine.

---

## 9. Sources / cross-references

- **Agent 9** (`09-mexc-maker-fee.md`) — 0% maker mechanism, adverse-selection literature
  (Avellaneda-Stoikov 2008; Cartea/Jaimungal/Penalva 2015; Menkveld 2013), spread table,
  the minimal maker-primitive diff (§6). Load-bearing for §1, §3.2, §5, §6.
- **Agent 16** (`16-mexc-tos-envelope.md`) — the Safe Operating Envelope (§5.1, §5.2), the
  "classic grid/MM is structurally impossible" corollary (§5.2.1), the safe-zone framing
  (§3). Load-bearing for §2, §3.3, §4.
- **Agent 14** (`14-mexc-orderbook.md`) — depth imbalance decays in seconds; only the
  persistent regime survives a slow poll; wide-spread veto pattern. Load-bearing for §3.6.
- **Agent 31** (`31-academic-microstructure.md`) — VPIN/toxicity as a read-only veto (§5);
  mechanism-grounded edges survive OOS. Load-bearing for §1, §3.6, §7.
- **Agent 41** (`research/agents/41-*`) — regime classifier; **forward dependency**, not
  yet written (agents dir ends at 40). Crude ADX/Hurst proxy until it exists.
- **In-repo code:** `execution.py:95` (market-only), `guardrails.py:42` (no `order_type`),
  `guardrails.py:65` (`OrderRateLimiter`), `guardrails.py:104/129` (kill switch + breaker),
  `client.py:32-36` (no order methods), `store.py:14,29,39` (no L2 table).
- **Literature:** Avellaneda & Stoikov (2008), *Quantitative Finance* 8(3); Cartea,
  Jaimungal & Penalva (2015), *Algorithmic and HFT*, CUP Ch.10–11; Menkveld (2013), *J.
  Financial Transformation* 36; Easley, O'Hara, Yang, Zhang (2026), *J. Financial Markets*
  (VPIN → crypto).

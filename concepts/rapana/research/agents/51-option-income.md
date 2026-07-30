# 51 — Option-like income (covered-call / put-write equivalents) under the spot-only MEXC envelope

**Agent:** 51/60 · **Scope:** the **convex-income / option-premium-harvest** family — covered-call,
buy-write, cash-secured-put / put-write, basis — and what is *feasible* once the classic
form is removed by policy (MEXC spot-only, futures KYB-gated, no symmetric hedging,
`research/agents/16-mexc-tos-envelope.md`).
**Stance:** NON-standard, low-frequency, **spot-only synthetic**. MEXC has **no native options**
and **no structured products** (§1, live-verified). The honest finding is that *true* option
income is **unreachable** here — but a **limit-ladder overlay** on a spot basket produces a
*payoff profile that resembles* a covered call (capped upside, mean-reversion harvest,
maker-rebate income at 0%). It is **not** the same thing and the gap is stated explicitly in §6.

All citations are `file:line` for repo code and bare URLs for external sources. Magnitudes for
the *synthetic* variant that have no peer-reviewed spot-only backtest are flagged
**[HYPOTHESIS → backtest]** — same discipline as `research/agents/37-carry-basis.md:6`.

---

## 0. TL;DR

- **MEXC has no options and no structured products** (§1). The canonical crypto options venue
  is Deribit (now Coinbase-owned); Cboe offers regulated **Bitcoin U.S. ETF Index Options**
  (https://www.cboe.com/tradable-products/cryptocurrency/bitcoin-etf-index-options/). MEXC's
  product surface is **Spot · Futures (KYB) · Earn · Fiat · Events** — no "Options" category
  exists anywhere in its support taxonomy.
- **The three synthetic routes the brief names:**
  - **(a) spot + perp short** = true covered call → **BANNED** (perp leg is KYB-gated;
    `16-mexc-tos-envelope.md:47` §5.6.2 bans "locked/hedged exposure without genuine market
    risk"). Do not pursue.
  - **(b) spot basket + limit-sell ladder above market** = **the feasible path** ("sell-into-
    strength" ≈ synthetic covered call). Captures **capped upside + 0% maker rebate**.
  - **(c) cash + limit-buy ladder below market** = **feasible** (synthetic put-write /
    cash-secured-put). Captures **mean-reversion entry at a discount**.
- **The single binding constraint is the ≤30% cancel ratio** (`16-mexc-tos-envelope.md:112`),
  *not* payoff theory. A wide multi-rung ladder that gets repriced every tick is classic
  quote-stuffing (§5.2.6) and is **structurally impossible** on MEXC retail
  (`16-mexc-tos-envelope.md:129`). The compliant shape is a **sparse, post-only ladder with a
  handful of rungs, re-quoted on a slow (5–15 min) cadence** — the same envelope agent 50's
  `PassiveProvider` already lives in (`research/agents/50-maker-mm-design.md:31`).
- **Honest verdict:** the synthetic is **not option income**. A true covered call collects the
  full option premium **regardless** of whether the market ever touches the strike; the
  synthetic collects **only if price travels to a rung and a taker crosses it**. Expected
  "premium" is the fill probability × the spread edge — materially smaller and
  path-dependent. It is best framed as **"maker income + mean-reversion harvest on a
  directional spot book,"** *not* "free option premium." Calibrate accordingly.

---

## 1. MEXC options reality (live-verified, 2026-06-23)

### 1.1 What MEXC does *not* have
- **No native crypto options.** `https://www.mexc.com/options` → **HTTP 404** (fetched
  2026-06-23). MEXC has never listed vanilla BTC/ETH options; the only venues with liquid crypto
  option books are **Deribit** (now Coinbase; https://www.deribit.com), **OKX**, **Binance**
  (European-style, BTC/ETH only, https://www.binance.com/en/options), and the regulated
  **Cboe Bitcoin U.S. ETF Index Options** (https://www.cboe.com/tradable-products/cryptocurrency/).
- **No structured products / notes.** The MEXC Help Center FAQ taxonomy
  (https://www.mexc.com/support, fetched 2026-06-23) lists exactly: **KYC · Account · Crypto
  Deposit & Withdrawals · Futures Trading · Spot · Fiat · Events · MEXC Earn · Referral · App/Web
  · Notifications · Fraud Prevention · Legal/Compliance · Risk Control · Other Services.** There
  is no "Options," no "Structured Products," no "Notes/ELN" category. MEXC Earn
  (https://www.mexc.com/staking) offers staking / flexible savings / Kickstarter — these are
  **lending/yield** products, not option-payoff structures.
- **No "earn-secured" option surface.** Unlike a structured-note issuer, MEXC does not let a
  retail user pre-commit Earn yield against a written call. The yield leg and the spot leg are
  independent; combining them is the *user's* bookkeeping, not a venue product.

### 1.2 The one "option-like" thing MEXC *does* have — and why it is not enough
- **Futures funding** is the closest native convex-income primitive on MEXC, and it is the
  closest the venue comes to an option premium: a short-perp holder is *paid* funding when the
  perp trades at a premium (crowded-long → positive funding → shorts harvest). Agent 12 covers
  this (`research/agents/12-mexc-funding.md`) and agent 37 proves the income leg is **already
  decaying** and **already failed the repo's honest gate** with the hedge attached
  (`research/agents/37-carry-basis.md:14`). It is **KYB-gated for the API** and **banned as a
  symmetric hedge** (`16-mexc-tos-envelope.md:47`), so it is **out of scope** for the retail
  spot sleeve.
- **Conclusion:** under the spot-only envelope, **there is no native option-primitive to
  harvest.** Anything option-like must be **synthesized from spot limit orders** — which is the
  entire subject of §4.

---

## 2. Covered-call evidence — the durable crypto income strategy

The covered call / buy-write is one of the **most studied** option-income structures in both
equity and crypto. The literature is unanimous on three points this agent needs: (1) it is a
**short-implied-volatility** position with a payoff **identical to a short put**; (2) it
**enhances return and dampens variance in flat/down markets** at the cost of capping upside;
(3) in crypto the **premium is rich** (high IV) but so is the **foregone upside**, so the net
edge is **regime-dependent** and concentrates in chop/sideways regimes.

### 2.1 Equity canon — the Cboe BXM benchmark
- **Whaley, R. (2002), "Risk and Return of the CBOE BuyWrite Monthly Index,"** *Journal of
  Derivatives* (Winter) pp. 35–42 — the foundational paper. Defines the **CBOE S&P 500 BuyWrite
  Index (ticker BXM)**: a long-S&P-500 + write-1M-ATM-call overlay, rolled monthly. Establishes
  that buy-write delivers **comparable long-run return to buy-and-hold with lower variance** →
  higher Sharpe, because the premium cushions drawdowns.
  - Index/dashboard (live): https://www.cboe.com/us/indices/dashboard/bxm/
  - Wikipedia summary: https://en.wikipedia.org/wiki/CBOE_S%26P_500_BuyWrite_Index
- **Covered-option mechanics (Wikipedia, primary definition):** a covered call is a **short
  implied-volatility strategy** whose payoff is **identical to selling a naked put**
  (put-call parity; Natenberg 1994). It is "generally considered conservative because the
  seller … reduces both their risk and their return."
  https://en.wikipedia.org/wiki/Covered_option
- **Feldman & Roy (2005), Hill et al. (2006, "Finding Alpha via Covered Index Writing,"
  *Financial Analysts Journal*)** — the cited institutional studies behind BXM: covered writing
  is an **alpha source in low-trend regimes**; the premium harvest dominates when realized vol
  < implied vol. The whole strategy's edge is **the implied-volatility risk premium (IVRP)** —
  the gap between expensive (implied) and cheap (realized) vol.

### 2.2 Crypto canon — the premium is real, but so is the foregone upside
Crypto covered-call literature is thinner (the market is young) but the consensus is strong:
- **Crypto IVRP is large.** BTC/ETH implied vol structurally exceeds realized vol by a durable
  margin — this is the "volatility risk premium" that makes covered-call overwriting one of the
  few **durable** crypto income strategies (versus funding arb, which agent 37 shows is decaying).
  The benchmark implementations are **Deribit BTC/ETH Covered Call Indices** (Deribit Insights)
  and the **Galaxy / 1token** covered-call research notes.
- **The painful side is the same as equity, only bigger:** the premium cushions you in chop and
  *ruins* you in explosive up-trends — exactly the regime that defines crypto bull markets.
  Empirically, BTC covered-call indices **underperform spot HODL in strong bull legs** (you are
  assigned at the strike and forfeit everything above it) and **outperform in range/grind-down
  regimes**. This is the structural "volatility risk premium for bearing tail-call risk" trade.
- **Cboe Bitcoin U.S. ETF Index Options** (now live, regulated) institutionalize exactly this:
  the venue lets you write calls on a BTC ETF index — i.e., *true* option income on BTC now
  exists on a regulated venue, just **not on MEXC** and **not to a spot-only retail bot**.
  https://www.cboe.com/tradable-products/cryptocurrency/bitcoin-etf-index-options/

### 2.3 Synthesis — what is solidly known vs flagged
| Claim | Status | Source |
|---|---|---|
| Covered-call payoff ≡ short-put payoff; it is short-IV | **SOLID** | Wikipedia/Covered_option; Natenberg 1994 |
| Covered writing ≈ buy-and-hold return at lower variance (equity, monthly) | **SOLID** | Whaley 2002 (BXM) |
| Crypto IVRP is large → covered-call is one of the few *durable* crypto income edges | **SOLID (qualitative)** | Deribit indices; Cboe BTC ETF options launch |
| BTC covered-call *beats* HODL net | **REGIME-DEPENDENT** — wins in chop, loses badly in bull legs | Deribit CC index methodology |
| A **spot-limit-ladder synthetic** captures a *comparable* premium | **[HYPOTHESIS → backtest]** — payoff is path-dependent, no peer-reviewed figure | this agent §4–§5 |

---

## 3. What the brief removes — the honest starting point

The brief names three synthesis routes. Verdict on each, anchored to the envelope:

### 3.1 (a) Spot + perp short = **true** covered call → **BANNED**
This is the only route that produces a *genuine* option payoff (long-spot + short-perp ≈
long-spot + short-call because a perp with funding ≈ a perpetual forward; short the perp caps
upside exactly like a written call). It is precisely what the envelope forbids:
- **Perp leg is KYB-gated** for API (`16-mexc-tos-envelope.md:63`; futures API institution-only).
- **It is symmetric hedging** → `16-mexc-tos-envelope.md:47` §5.6.2 explicitly bans
  *"simultaneous long+short forming locked/hedged exposures without genuine market risk."*
- Agent 37 already established that even *with* the perp leg, blind carry already failed the
  repo's honest gate (`37-carry-basis.md:14`). **Do not pursue this route.**

### 3.2 (b) Spot basket + limit-sell ladder above market → **feasible** (the design target)
Hold a spot position; post a **scale-out ladder of post-only limit-sells above mid**. Each rung
that fills sells *into strength* at a premium to entry — capturing a piece of upside and
realizing a spread edge at **0% maker fee**. This is the closest spot-only analog to a written
call: you **cap your upside participation** (you lighten as price rises) in exchange for
**captured spread**. It is the design subject of §4. **Status: feasible, design it carefully
against the cancel ratio.**

### 3.3 (c) Cash + limit-buy ladder below market → **feasible** (synthetic put-write)
Hold USDT; post a **scale-in ladder of post-only limit-buys below mid**. Each rung that fills
buys *into weakness* at a discount — the spot analog of a **cash-secured put**: you commit
capital to buy at a strike below market, "earning" the discount (≈ premium) if price falls to
you, and simply holding cash (≈ keeping premium) if it never does. Mechanically this is
**mean-reversion accumulation** (`rapana/strategies/meanrev.py:10` already trades the signal;
this route *expresses* it as passive limit orders instead of market entries). **Status:
feasible.**

### 3.4 What you forfeit by going synthetic (be explicit, do not bury it)
| Property | True covered call | Spot-limit synthetic |
|---|---|---|
| Premium received | **Guaranteed, up-front**, cash today | **Conditional** — only earned *if* a taker crosses your rung |
| Upside cap | Hard, at strike | Soft — you *lighten*, you do not strictly cap |
| Downside | Full spot delta (same as synthetic) | Full spot delta |
| Delta at inception | < 1 (call premium reduces basis) | = 1 (pure spot until a rung fills) |
| Theta decay income | **Yes** (premium erodes into your account daily) | **No** (no time-decay income; only fill-event income) |
| Path-dependence | Low (premium is yours regardless of path) | **High** (income only on touch-and-cross) |
| Needs the hedge leg | Yes (or a venue option) | **No** — pure spot, envelope-safe |

**The crucial asymmetry:** a true covered call is a **short-volatility** bet that pays you the
IVRP *for bearing the risk of being assigned*. The synthetic pays you only the **realized
spread on fills**, which is the *execution* edge, not the *volatility* edge. You are harvesting
**liquidity provision + mean-reversion**, not **implied-volatility premium**. §6 names this gap
precisely.

---

## 4. `SyntheticCoveredCall` — spot-only design

### 4.1 One-line description (and why it is *not* arbitrage)
Hold a **directional spot basket** (selected by the existing universe ranker) and overlay a
**two-sided post-only limit ladder**: sells *above* mid (scale-out), buys *below* mid
(scale-in). There is **no opposite-side hedge, no second venue, no simultaneous buy+sell of the
same asset** — every order expresses **genuine directional intent** to adjust inventory. That is
the textbook line between a **permitted selection/execution overlay** and a **banned arbitrage**
(`16-mexc-tos-envelope.md:80` — "directional trades that carry genuine market risk" are the safe
zone). It is the *same legal posture* as agents 29/37/50: spot-only, maker, single account.

### 4.2 Ladder geometry (the "synthetic strike ladder")
For a held spot position of size `Q` in symbol `S`, current mid `P0`:

```
SELL ladder (scale-out, "synthetic covered call" side):
  rung_k = P0 * (1 + a_k),  a_k ∈ {+1.0%, +2.0%, +4.0%}      # 3 rungs, geometric
  size_k = Q * w_k,         w_k ∈ {0.20, 0.20, 0.10}         # lighten 50% total

BUY ladder (scale-in, "synthetic put-write" side, funded by idle USDT):
  rung_j = P0 * (1 - b_j),  b_j ∈ {1.0%, 2.0%, 4.0%}         # mirror
  size_j = (cash_budget) * w_j                                # accumulate on weakness
```

- **Rung spacing** is the **synthetic strike selection**. Wide spacing (4%) = OTM, lower fill
  prob, bigger edge-per-fill; tight spacing (1%) = near-the-money, higher fill prob, smaller
  edge. This is the *direct analog* of moneyness selection in real covered-call writing
  (Wikipedia/Covered_option: "OTM covered calls have higher profit potential but protect less").
- **Sizes** are inventory-targeted: sells lighten toward a target weight, buys build toward it.
  This makes every fill *mean-revert the inventory back toward neutral* — exactly the
  round-trip pattern agent 50 §3.7 identifies as the only cancel-safe shape
  (`50-maker-mm-design.md:27`).
- **Total open orders ≤ ~6 per symbol** (3 up + 3 down). With ≤1 order/symbol/60s placement
  rate the whole ladder takes **~6 min to stage** — comfortably inside the cadence envelope.

### 4.3 Payoff profile vs a true covered call
At horizon `T`, comparing spot HODL vs synthetic, for spot ending at `P_T`:

| Outcome | True covered call (strike K) | Spot-limit synthetic |
|---|---|---|
| `P_T ≤ P0` (down) | Spot loss **−** premium cushion | Spot loss **+** any buy-rung fills (you averaged down) **−** no premium |
| `P0 < P_T < K` (chop up) | Spot gain **+** keep full premium (**best regime**) | Captured sell-rung spread **+** residual spot delta (partial scale-out) |
| `P_T ≥ K` (explosive up) | **Capped at K** (assigned, forfeit upside above K) (**worst regime**) | Partially scaled out at +1/+2/+4% — upside **dampened, not hard-capped** |

**Read:** the synthetic reproduces the *shape* (income in chop, dampened upside in rallies) but
**not the guarantee**. In the chop regime the true call pays you the full premium even if price
never moves; the synthetic pays you only on fills. In the explosive-up regime the synthetic is
**strictly better** (no hard assignment cap) but captures less "premium" along the way.

### 4.4 Income accounting (honest)
Per completed round-trip (a sell-rung fill later matched by re-entry), on a mid-liquidity pair:
```
edge_per_round_trip ≈ rung_spacing − adverse_selection
                    ≈ (100–400 bp) − (estimated 50–150 bp)      # agent 50 §1
maker_fee           = 0% (verified per-account, agent 9)        # 09-mexc-maker-fee.md:62
taker_fee on unwind = 0% if unwound passively (another buy-rung fills)
                    else 20 bp if force-flattened via market    # 09-mexc-maker-fee.md:43
```
This is **identical to agent 50's `PassiveProvider` economics** (`50-maker-mm-design.md:18`) —
**~1–4 bp net per round-trip after inventory drawdowns on mid-liquidity pairs, ~0 on majors,
negative on the long tail.** The synthetic does **not** conjure option premium out of maker
rebates; it re-packages the **same maker edge** into a covered-call-shaped payoff. The two
agents share an edge family; the difference is the *inventory policy* (mean-revert-to-target
here vs flat in agent 50).

### 4.5 Cadence & envelope compliance (the binding part)
The design is dominated by `16-mexc-tos-envelope.md` §5.1, not by payoff theory:

| Envelope rule (§5.1) | This design's compliance |
|---|---|
| Spot only, `postOnly` limit | **All ladder rungs are `postOnly`** — never cross the spread |
| ≤1 new order / symbol / 60 s | Stage rungs sequentially, **≥60 s apart**, jittered ±30% |
| **Cancel ratio ≤30%** | **The load-bearing constraint.** A wide ladder that gets re-priced every tick dies here. Solution: **post rungs wide enough to fill, repriced only every 5–15 min**, cancels reserved for inventory-stop / regime-flip only. This is agent 50's §2 result restated (`50-maker-mm-design.md:77`) |
| ≥30 s create→cancel | Hard rule in the cancel path; never cancel an order <30 s old |
| Burst ban (>3 orders/10 s) | Sequential staging guarantees compliance |
| Event blackouts (±5 min) | Scheduler hard-blocks ladder (re)placement around listings / 0-Fee / funding / UTC rollover |
| ≤2% of 24h volume | Rung sizes sized against rolling 24h volume per symbol |
| Trend / regime gate | **Disable sell ladder in strong uptrend** (you'd just scale out of a rally you want to ride) and **disable buy ladder in a crash with no bounce** (don't catch falling knives) — uses agent 41's LLM-regime gate |

### 4.6 How it composes with the existing fleet (overlap confirmation)
| Agent | Surface | Overlap with 51 |
|---|---|---|
| **9** maker fee | edge source | **Load-bearing** — 51's entire income is the 0% maker rebate |
| **12 / 29 / 30 / 37** funding/reversion | signal | 51 *expresses* the same mean-reversion as **passive limits**; 12/29/30/37 express it as **active market entries**. Distinct surface, shared mechanism — calibrate so `net_score` does not double-count |
| **41** LLM regime | gate | 51 needs the trend filter to decide ladder side / disable |
| **50** `PassiveProvider` | MM design | **Closest peer.** 51 = agent 50's maker mechanics applied to a **directional inventory target** instead of flat. Reuse the cancel-meter and cadence code verbatim |

---

## 5. ToS verdict (does this survive §5?)

**Likely safe, with one code-contract requirement.** The design is *directional spot + post-only
limits + genuine inventory intent* — squarely inside agent 16's safe zone
(`16-mexc-tos-envelope.md:80`: "directional trades that carry genuine market risk"). It is the
**opposite** of every banned pattern in §5.6.2 (no hedge, no arb, no locked exposure). The single
tripwire is §5.2.6 / §5.6.1 — the **cancel/frequent-placement** pattern — and the design is built
to hold the **≤30% cancel ratio by construction** (wide rungs, slow re-quote, cancels only on
inventory stop). Per agent 50 §4, that meter must be a **code contract** enforced at the order
path, not a hoped-for discipline. If the cancel meter ever drifts >30% on rolling 24h, the ladder
**must auto-halt** and re-arm only on human review — same kill-switch as agent 50.

**One additional ToS risk specific to 51:** a two-sided ladder (buys below + sells above) on the
*same symbol* could, if naïvely implemented, look like **simultaneous two-sided quoting** (a
market-maker pattern). Mitigation: (i) sizes are **inventory-asymmetric** (you post the side that
restores target weight, not symmetric pegs); (ii) never have buy+sell rungs **both within the
spread** of each other (keep ≥1% apart, which the geometry §4.2 already guarantees); (iii) log
intent ("restoring target weight after rung-k fill") on every order for the audit trail
(`16-mexc-tos-envelope.md:133`).

---

## 6. Honest comparison — synthetic vs true options (do not conflate)

The brief asks for honesty. The synthetic covered call is **a legitimate payoff shape**, but it
is **not** option income in three load-bearing ways:

1. **No theta / IVRP harvest.** A real covered call is paid for **bearing implied-volatility
   risk** — the IVRP (§2.2) is the *entire* durable edge. The synthetic earns **execution
   spread**, which is the liquidity-provision edge (agent 9/50), a *different and smaller*
   edge family. Calling the synthetic "option income" overstates it.
2. **Path-dependent, not guaranteed.** The true premium is banked at write; the synthetic's
   "premium" is realized **only when price touches a rung and a taker crosses it**. In a quiet,
   flat market — the true covered call's *best* regime — the synthetic may earn **near zero**
   (no fills). The strategies are **anti-correlated in their best regimes.**
3. **No defined-risk downside.** A cash-secured *put* has defined risk (you buy at strike,
   worst case is owning the asset at the strike you chose). The synthetic buy-ladder has the
   **same** — but a *real* put-write's premium is yours *whether or not* you're assigned; the
   synthetic's "discount" is yours **only if assigned**. Again, the guarantee differs.

**Correct framing for the fleet ledger:** `SyntheticCoveredCall` is a **"maker-income +
mean-reversion overlay on a directional spot book, whose payoff shape resembles a covered call
in chop and a put-write on dips."** It is a **discipline + decorrelation + capture** strategy
(reusing agent 50's edge), *not* a new alpha family. Expected contribution: small, Sharpe
~0.3–0.6 (mirroring agent 50), valued for **decorrelation and enforcing maker-side execution on
the spot book**, not for replicating Deribit's covered-call index returns.

---

## 7. What would be needed to ship this (minimal, scoped)

1. **Maker-side execution** — currently `LiveExecutor` is **market-only**
   (`rapana/fleet/execution.py:95`, `type="market"`); agent 9 §TL;DR already specifies the
   minimal change (a `postOnly` branch + a `maker_price` field on `TradeProposal`). This is a
   **hard prerequisite** — without it the synthetic cannot exist.
2. **A ladder-order builder** — new module that turns an inventory target + rung geometry into a
   staged sequence of `postOnly` limits respecting §4.5 cadence. No such builder exists today
   (the repo's "grid"/"ladder" hits are **parameter-search grids** for backtests, e.g.
   `rapana/backtest/validation.py:216`, not trading ladders).
3. **Cancel-ratio meter as a code contract** — reuse agent 50's meter verbatim; auto-halt >30%.
4. **Regime gate integration** — wire agent 41's LLM-regime output to choose ladder side / disable.
5. **Backtest first** — the synthetic's edge is **[HYPOTHESIS → backtest]** (§2.3). Before any
   live order, simulate the ladder against historical MEXC spot klines with realistic fill
   modeling (limit-fill only when trade price crosses the rung, adverse selection on fills) and
   apply the **same honest gate** as the rest of the fleet (DSR > 0.95, beats HODL
   `rapana/backtest/validation.py:63`). If it fails the gate, it joins carry/funding-spike on
   the "did not survive" shelf — do not soften the gate for an option-flavored name.

---

## 8. Sources cited (consolidated)

- **MEXC Help Center** (product taxonomy, live 2026-06-23, no Options category):
  https://www.mexc.com/support
- **MEXC `/options`** → HTTP 404 (no native options), fetched 2026-06-23
- **MEXC Earn** (staking/savings, not option-payoff): https://www.mexc.com/staking
- **Cboe BXM (S&P 500 BuyWrite Index) dashboard**: https://www.cboe.com/us/indices/dashboard/bxm/
- **Whaley (2002), "Risk and Return of the CBOE BuyWrite Monthly Index,"** *J. Derivatives*
  Winter, pp. 35–42 — foundational covered-call benchmark paper
- **Wikipedia, "Covered option"** (payoff ≡ short put; short-IV strategy):
  https://en.wikipedia.org/wiki/Covered_option
- **Wikipedia, "CBOE S&P 500 BuyWrite Index"** (BXM history, $50B+ AUM by 2016):
  https://en.wikipedia.org/wiki/CBOE_S%26P_500_BuyWrite_Index
- **Cboe Bitcoin U.S. ETF Index Options** (regulated crypto options, *not* on MEXC):
  https://www.cboe.com/tradable-products/cryptocurrency/bitcoin-etf-index-options/
- **Deribit** (now Coinbase) — primary liquid crypto options venue: https://www.deribit.com
- **Binance Options** (European-style, BTC/ETH): https://www.binance.com/en/options
- Repo (internal): `16-mexc-tos-envelope.md` (envelope), `09-mexc-maker-fee.md` (0% maker),
  `50-maker-mm-design.md` (maker-MM mechanics this reuses), `37-carry-basis.md` (failed-carry
  precedent), `rapana/fleet/execution.py:95` (market-only executor), `rapana/strategies/meanrev.py:10`
  (mean-reversion signal), `rapana/backtest/validation.py:63` (honest gate).

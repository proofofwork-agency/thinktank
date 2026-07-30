# 56 — Dynamic idle-cash sweep (`IdleCashSweep`): route non-trading cash to the best safe yield automatically

**Agent:** 56/60 · **Scope:** The **automation layer** between MEXC's idle spot balance and the best available safe yield (MEXC Earn vs DeFi vs self-custody). This is the *controller* counterpart to agent **38** (`38-defi-yield.md`), which established the **static** yield landscape and the two-sleeve *split*. Agent 56 answers a different question: *given that split exists, how does idle cash move between tiers in real time, and how do we never get caught short when a signal needs capital?*
**Stance:** NON-standard, structural, capital-preservation. Spot-only; no arb, no leverage, no perps. The sweep emits **no per-symbol trading signal** — it is a fleet-level **treasury controller** that sits beside the orchestrator and operates on the quote-asset balance. Honors `16-mexc-tos-envelope.md` §5 (yield products are MEXC's own / read-only DeFi; no multi-account farming, no order-rate noise).

**Status of evidence:** Yield APYs are **live DefiLlama API snapshots (`GET https://yields.llama.fi/pools`, fetched 2026-06-23, 15,976 pools)** — the most authoritative public yield oracle; verifiable to the cent at the cited URLs. MEXC Earn mechanics are quoted from the live **Auto-Earn FAQ** ("full flexibility—you can trade, withdraw, or use your tokens anytime while still accruing interest") and the **Earn landing page** ("up to 600% APR" = new-user promo on capped principal). Withdrawal-latency figures are **protocol-mechanism facts** (redeem path + utilization gating), flagged **[HYPOTHESIS]** where a stressed-day lag is inferred rather than measured. Idle-drag numbers are **deterministic arithmetic** from stated fleet sizes.

---

## 0. TL;DR (4 lines)

> Idle USDT left on the MEXC spot balance earns exactly **0%** — a silent, compounding drag that costs a $50k fleet **~$1,500–2,000/yr** at the current safe real-yield floor of **3.0–3.6%** (live 2026-06-23: Sky **sUSDS 3.6%** / Spark Savings USDC **3.6%** / Ethena sUSDe **3.54%** / Aave v3 USDC base **3.14%** / Aave v3 USDT base **2.12%**; MEXC Hold-and-Earn ~1–3% steady, **zero redemption latency** because funds stay in Spot). The fix is an **`IdleCashSweep`** controller that runs **3 tiers by withdrawal latency** — **T0 working buffer** on MEXC Auto-Earn (instant, trade-ready), **T1 reserve** in self-custody Aave/Spark/sUSDS (~minutes, removes CEX counterparty risk), **T2 cold** locked-term only for capital with a known horizon > the lock — and **pulls back** the instant a fleet signal raises capital-demand above the T0 buffer, using a 1-step-ahead demand forecast so redeems complete *before* the order is needed. It is pure structural yield: **risk-free-ish incremental return with no directional exposure and zero change to the trading envelope**.

---

## 1. The idle-drag problem — why 0% on idle is the default (and why that's a bug)

Most retail trading bots, including rapana in its current form, leave uninvested quote balance (`PaperPortfolio.cash`, `rapana/fleet/portfolio.py:12`) sitting on the MEXC spot balance. **That balance earns nothing.** It is not a feature MEXC advertises; it is the absence of one. The fleet's whole backtest/promotion machinery (`07-profit-benchmark.md`) then judges strategies against `cash_return`, which **defaults to `0.0`** (`rapana/cli.py:1063`, `backtest/carry.py:115`, `backtest/unlock_event.py:269`). Agent 38 established that this default is the bug — idle stables are not zero-return in 2026. **Agent 56's job is the operating consequence: if idle stables *can* earn 3–4%, then leaving them at 0% is an ongoing, measurable cash leak.**

### 1.1 Quantifying the drag (deterministic arithmetic)

The cost of 0% is just `idle_balance × yield × time`. It compounds silently because it shows up as *absence of return*, never as a red line in the P&L:

| Fleet quote-equity | Idle fraction (typical) | Idle $ at risk | Annual drag @ **3.0%** floor | Annual drag @ **3.6%** (sUSDS) | 3-yr drag @ 3.6% (compounded) |
|---|---|---|---|---|---|
| $10,000 | 50% | $5,000 | **$150** | **$180** | $561 |
| $50,000 | 40% | $20,000 | **$600** | **$720** | $2,247 |
| $100,000 | 35% | $35,000 | **$1,050** | **$1,260** | $3,938 |
| $250,000 | 30% | $75,000 | **$2,250** | **$2,700** | $8,429 |

**Two things make this worse than the table looks:**

1. **It is risk-adjusted free money.** The comparison is not "3.6% vs 0%"; it is "3.6% in single-asset blue-chip stable lending vs 0% on the *same counterparty* (MEXC)". Moving idle cash from MEXC-spot-0% to MEXC-Auto-Earn-2% changes **nothing** about counterparty risk (funds still on MEXC) and captures most of the gap. Moving it to self-custody sUSDS *reduces* counterparty risk while *raising* yield. There is no Sharpe-tradeoff here — only latency.
2. **It compounds against the strategy's own promotion bar.** Because `cash_return` defaults to 0, a strategy returning +2.5% net "passes" promotion while *underperforming* the 3.6% it could have earned by doing nothing. The idle drag is therefore not just a treasury leak — it is a **mis-calibration of the entire promotion gate**, silently funding fake alpha (agent 7's thesis, seconded by agent 38 §1).

### 1.2 The honest framing

> For every dollar the fleet leaves idle on MEXC spot, rapana pays MEXC a ~3%/yr **opportunity tax** for the privilege of holding its money. Over a multi-year run this tax exceeds most realistic net trading alpha on that same dollar. The `IdleCashSweep` exists to collect that tax back.

---

## 2. Live yield comparison — with the column agent 38 omitted: **withdrawal latency**

Agent 38 §2.1 published the static yield table. Agent 56 re-queries the same DefiLlama feed **(fetched fresh 2026-06-23)** and adds the load-bearing column for a *dynamic* sweep: **how fast can I get the money back when a signal needs it?** Latency, not headline APY, is the constraint that governs sweep sizing.

### 2.1 The yield × latency table (live, 2026-06-23)

All DeFi rows: `GET https://yields.llama.fi/pools`, filtered to `tvlUsd > $30M`, base-only (`apyReward ≈ 0`) to isolate *real* yield (agent 38 §2.2 rule). MEXC rows from the live Auto-Earn FAQ + Earn landing page.

| Tier | Venue (token / chain) | Live APY (base) | TVL | **Withdrawal latency (normal)** | **Withdrawal latency (stressed)** | Custody | URL |
|---|---|---|---|---|---|---|---|
| **T0** | **MEXC Hold-and-Earn / Auto-Earn (USDT/USDC)** | ~1–3% steady (peer-CEX parity) | n/a (spot balance) | **Instant — funds stay in Spot** ("trade, withdraw, or use your tokens anytime", FAQ) | Instant (same) | **MEXC** | [MEXC Auto-Earn](https://www.mexc.com/earn/auto-earn) |
| **T0** | **MEXC Flexible Savings (USDT)** | ~2% steady | n/a | Same-day redeem (per Earn FAQ redemption flow) | Possible redeem lag on stressed days **[HYPOTHESIS]** | MEXC | [MEXC Earn](https://www.mexc.com/earn) |
| **T1** | **Aave v3 — USDC (Ethereum)** | **3.14%** | $212M | **1 block (~12s)** if utilization < 100% | Blocked at 100% util until repays; rare for USDC | Self-custody | [Aave v3](https://app.aave.com/) |
| **T1** | **Aave v3 — USDT (Ethereum)** | 2.12% | $754M | 1 block (~12s) | Same util-gating as USDC | Self-custody | [Aave v3](https://app.aave.com/) |
| **T1** | **Spark Savings — USDC (Ethereum)** | **3.60%** | $324M | 1 block (~12s) | Same util-gating | Self-custody | [Spark](https://spark.fi/) |
| **T1** | **Spark Savings — USDS (Eth/Arb/Base)** | **3.60%** | $360M+ | 1 block (~12s) | Same util-gating | Self-custody | [Spark](https://spark.fi/) |
| **T1** | **Sky sUSDS (Ethereum)** ⭐ benchmark | **3.60%** | **$5,886M** | Next-block via Sky DSR | Sky governance pause only (extreme) | Self-custody | [Sky](https://sky.money/) · [sUSDS](https://defillama.com/yields) |
| **T1** | **Compound v3 — USDC (Ethereum)** | 3.18% | $39M | 1 block | Same util-gating | Self-custody | [Compound](https://app.compound.finance/) |
| **T1'** | **Ethena sUSDe (Ethereum)** ⚠️ cyclical | 3.54% | $1,716M | Ethena redeem queue (mins–hours) | **Queue lengthens under funding stress; use DEX exit at premium** | Self-custody (hedge on CEX) | [Ethena](https://app.ethena.fi/) |
| **T2** | **Pendle PT (sUSDe/sUSDS, fixed term)** | ~6–9% fixed | varies | **Locked until maturity** — illiquid by design | Locked | Self-custody | [Pendle](https://app.pendle.finance/) |
| **T2** | **MEXC Fixed Savings / On-Chain staking** | ~3–15% promo | n/a | Locked term (early-redemption penalty per FAQ) | Locked | MEXC | [MEXC Earn](https://www.mexc.com/earn) |
| (ref) | BlackRock **BUIDL** (RWA T-bill) | 3.5–3.7% | — | Token redemption gate (T+days) | Issuer gate | Self-custody / fund | [DefiLlama](https://defillama.com/yields) |
| (ref) | Maple / Centrifuge (institutional credit) | 5–6% | — | Pool redemption cycle | Default lock-up | Self-custody | [Maple](https://www.maple.finance/) |

### 2.2 The three numbers worth memorising

1. **The safe real-yield floor is 3.0–3.6%** (sUSDS / Spark Savings / Aave USDC base). This is the ceiling of the sweep's T1 target. Anything higher in the table is either **cyclical (sUSDe, funding-dependent)**, **credit-risky (Maple)**, or **illiquid (Pendle PT, MEXC Fixed)**. (Mirrors agent 38 §2.2.)
2. **The MEXC Auto-Earn latency is effectively zero** because funds never leave Spot. This is the single most important operational fact for the sweep: **T0 captures ~1–3% with no latency cost at all** — it should be the default state of any quote balance not actively being deployed.
3. **The T1 latency ceiling is ~minutes** for Aave/Spark/sUSDS under normal conditions. The only real T1 failure mode is **Aave/Spark utilization hitting 100%** (withdrawals temporarily blocked until borrowers repay) — a rare event for deep USDC/USDS pools but **nonzero**, and the exact moment you'd want liquidity. Mitigation: spread T1 across ≥2 pools/protocols and keep a utilization monitor (§5.3).

### 2.3 Why this table differs from agent 38's

Agent 38 ranked venues by **(safety, then yield)** to justify the *split*. Agent 56 ranks the **same** venues by **(latency, then yield)** to justify the *routing*. Both arrive at the same two-sleeve conclusion; the contribution of 56 is the **third dimension** — *how fast the money comes back* — and the controller that uses it.

---

## 3. `IdleCashSweep` — design

### 3.1 Concept

A **treasury controller** that runs *beside* the orchestrator (`rapana/fleet/orchestrator.py:73,86`), not inside the per-symbol loop. It has one job: **minimize the time-weighted idle balance at 0%** without ever stranding capital the fleet needs. It reads fleet state (`FleetState`), the autopilot's capital stage (`rapana/fleet/capital.py:11`, `autopilot.py:17`), and a 1-step capital-demand forecast; it emits **transfer proposals**, not trade signals.

```
                  rapana quote-equity (USDT on MEXC + USDS in self-custody)
                  ┌───────────────────────────────────────────────────────────┐
                  │                                                           │
   ┌──────────────┴───────────────┐                       ┌──────────────────┴──────────┐
   │  T0  WORKING BUFFER (MEXC)    │   sweep ↑ / pull ↓    │  T1  RESERVE (self-custody) │
   │  Auto-Earn USDT/USDC ~1–3%    │ ◄──────────────────► │  Aave / Spark / sUSDS 3.6%  │
   │  latency: INSTANT (funds in   │   forecast-gated      │  latency: ~minutes          │
   │  Spot — trade/withdraw anytime│   rebalance band      │  removes CEX counterparty   │
   │  per MEXC Auto-Earn FAQ)      │                       │  risk from the bulk         │
   │  size = max(signal-demand,    │                       │  size = (reserve_fraction × │
   │         k·σ(daily demand))    │                       │         equity) − T0        │
   └──────────────┬───────────────┘                       └──────────────────┬──────────┘
                  │                                                           │
                  │            (known-horizon capital only → T2)              │
                  └───────────────────────┐               ┌───────────────────┘
                                          ▼               ▼
                            ┌──────────────────────────────────────┐
                            │  T2  COLD (optional, capped)          │
                            │  Pendle PT / MEXC Fixed / BUIDL       │
                            │  ~6–9% fixed BUT locked to maturity   │
                            │  ONLY for capital with horizon > lock │
                            └──────────────────────────────────────┘
```

### 3.2 The three tiers (latency-first, then yield)

| Tier | Vehicle | Latency | Yield | Purpose | Sizing rule |
|---|---|---|---|---|---|
| **T0 — Working buffer** | MEXC Auto-Earn (Hold-and-Earn) | **Instant** | ~1–3% | Capital that must be trade-ready *this cycle* | `max(forecast_demand_next, k · σ_60d(daily_drawdown))` + dust |
| **T1 — Reserve** | Self-custody Aave USDC / Spark sUSDS / Sky sUSDS | ~minutes | **3.0–3.6%** | Long-horizon preservation; removes MEXC counterparty from the bulk | `reserve_fraction × equity − T0` (default `reserve_fraction ≈ 0.5–0.7` of *non-deployed* equity) |
| **T2 — Cold** (optional) | Pendle PT / MEXC Fixed / BUIDL | locked-term | ~6–9% | Capital with a *known* horizon exceeding the lock | Only dollar-amounts whose re-entry date is ≥ lock maturity; hard cap (e.g. ≤10% of reserve) |

**The sweep's central decision is always T0↔T1.** T2 is a separate, human-approved allocation for capital the fleet has explicitly declared idle for a known window (e.g. a drawdown reserve the autopilot has parked for a quarter).

### 3.3 The sweep/pullback loop (runs at low cadence — hourly, not per-tick)

```
IDLE CASH SWEEP — each cycle:
  1. READ  equity, deployed_notional, fleet_stage (StagedCapital), open signals
  2. COMPUTE idle_now       = equity_quote − deployed_notional
  3. FORECAST demand_next   = Σ (signal_strength_i × max_notional_i) for bullish i
                              + forecast_demand_buffer
                              (1-step-ahead; conservative; never underestimates)
  4. TARGET T0 = max( demand_next,  k · σ_60d(daily_demand),  floor_dust )
  5. IF idle_now > T0_target + rebalance_hysteresis:
        sweep_up_amount = min(idle_now − T0_target, T1_headroom)
        → propose: withdraw(sweep_up_amount) to self-custody → supply Aave/Spark/sUSDS
  6. ELIF idle_now < T0_target − rebalance_hysteresis:
        pull_down_amount = T0_target − idle_now
        → propose: redeem Aave/Spark/sUSDS(pull_down_amount) → deposit MEXC spot
        (redeem completes in ~minutes — see §4 latency handling)
  7. JOURNAL every proposal + executed transfer + accrued yield (rapana/journal/)
  8. NEVER auto-execute T1↔MEXC bank transfers without the human-approved
     bridge path (reserve movements are slow; only T0 Auto-Earn is fully automatic)
```

**Key properties:**
- **Conservative forecast.** `demand_next` over-estimates re-entry need; T0 is sized so a normal day never triggers a pull-down. Pull-downs are *reactive* — they fire only when a real signal raises demand above the buffer, by which point the capital is needed and the redeem latency is the cost of having had it earning 3.6%.
- **Hysteresis.** A `rebalance_hysteresis` band (e.g. ±2% of equity) prevents flapping. The sweep only moves when idle drifts *outside* the band — not every cycle.
- **Cadence is low.** Hourly is plenty. Intraday flapping between tiers would burn gas and MEXC withdrawal limits for no yield gain. Yield accrues by *time held*, not by *number of moves*.
- **ToS-clean.** Auto-Earn enrollment + DeFi self-custody adds **zero order-rate, cancel-ratio, or multi-account exposure** (`16-mexc-tos-envelope.md` §5). It is config + off-exchange transfers, not a trading-strategy change.

### 3.4 Tiered risk (matches agent 38 §5, re-derived for the sweep)

| Risk | Hits tier | Mitigation built into the sweep |
|---|---|---|
| **MEXC counterparty failure / hot-wallet hack** | T0 | Keep T0 at the *minimum* that satisfies demand-next; bulk lives in T1 (self-custody), which is the entire point |
| **Smart-contract exploit (Aave/Spark/Sky)** | T1 | Spread T1 across ≥2 protocols + ≥2 stables; prefer the longest-tenured, most-audited pools; cap per-protocol exposure |
| **Stablecoin depeg** (USDC/USDS — agent 21) | T0, T1 | Diversify stable legs; never hold algorithmic stables; monitor `21-stablecoin-depeg.md` triggers; on trigger, sweep T1 → T0 → USDT only |
| **Aave/Spark utilization gating** (withdrawal blocked at 100% util) | T1 | Monitor utilization each cycle; if >95%, pre-emptively pull to T0; spread across pools so one being full doesn't strand the reserve |
| **Ethena sUSDe funding inversion** | T1' (if used) | Treat sUSDe as *cyclical*, capped ≤10% of T1; rotate to sUSDS when funding flips negative |
| **Bridge / gas risk on bank transfers** | T0↔T1 boundary | Human-approved bridge path only; sweep proposes, human (or a guarded automation policy) executes bank moves |
| **Lock-up on T2** | T2 | Only allocate capital with a *declared* horizon > lock; never let T2 absorb the working buffer |

---

## 4. Withdrawal-latency handling — the part that makes the sweep safe

The sweep's only failure mode is **capital stranded in T1 when a signal needs it in T0**. The design defeats this three ways:

### 4.1 Forecast-ahead sizing (the primary defence)
T0 is sized to `max(forecast_demand_next, k·σ_60d(daily_demand), floor_dust)` — i.e. **before** a signal fires, T0 already holds what the signal will need. A pull-down from T1 only fires when demand *exceeds* the forecast (a genuine surprise), in which case the ~minutes redeem latency is the cost of an edge case, not the steady state.

### 4.2 Latency-budget matching per tier
Every dollar is routed to the tier whose **p95 withdrawal latency < that dollar's re-entry horizon**:
- Capital the fleet might deploy **this cycle** → T0 (instant).
- Capital reserved against drawdowns / stage-advancement → T1 (~minutes; drawdowns unfold over hours/days, so minutes is fine).
- Capital with a declared multi-week horizon → T2 (locked).

The sweep **never** puts re-entry-capital into T2, and **never** puts more in T1 than the demand-forecast says it will need inside the T1 redeem window.

### 4.3 Redeem-path redundancy
T1 is split across ≥2 protocols/stables so that a single pool being gated (100% utilization) or a single chain being congested doesn't strand the whole reserve. sUSDS via Sky DSR is the benchmark T1 leg specifically because the redeem path is simplest and least util-gated.

### 4.4 The honest latency numbers
- **MEXC Auto-Earn → Spot: instant** (funds never leave Spot — per the live FAQ: *"full flexibility—you can trade, withdraw, or use your tokens anytime while still accruing interest"*). **This is why T0 is effectively free yield.**
- **Aave v3 / Spark / sUSDS redeem: ~1 block (~12s on Ethereum) under normal conditions**; can be temporarily delayed by gas spikes or, rarely, 100% utilization. **p95 ~minutes.**
- **Ethena sUSDe redeem: queue-based, mins–hours;** under funding stress the queue lengthens — keep a DEX-exit fallback (sell sUSDe → USDC at a small premium) and cap sUSDe ≤10% of T1.
- **Pendle PT / MEXC Fixed / BUIDL: locked to maturity** — exclude from any tier the sweep auto-routes to.

> Operational rule of thumb: **the sweep may move idle cash into T1 only to the extent that T0 still covers the next cycle's p95 demand.** Everything else stays liquid. Yield is captured on the margin, never at the expense of trade-readiness.

---

## 5. Implementation touch points (real file:line)

| Change | Where | What |
|---|---|---|
| **The sweep controller (new)** | new `rapana/fleet/idle_sweep.py` | `IdleCashSweep` class: `tick(fleet_state, orchestrator) -> list[TransferProposal]`; reads `PaperPortfolio.cash` (`portfolio.py:12`) and `StagedCapital.fraction` (`capital.py:21`); implements the §3.3 loop with hysteresis + forecast-ahead sizing. Emits proposals only (no direct execution). |
| **Working-buffer tier (MEXC Auto-Earn)** | new `rapana/treasury/mexc_earn.py` (or extend `mexc/client`) | Enroll/redeem Auto-Earn USDT/USDC. **Zero-order** side-effect (Earn API, not trading API) — does not touch order-rate / cancel-ratio envelope (`16` §5). Confirmed instant-liquid by FAQ. |
| **Reserve tier (self-custody DeFi)** | new `rapana/treasury/defi_yield.py` | Thin read-only-or-write client over Aave v3 / Spark / Sky DSR; live rates via `GET https://yields.llama.fi/pools` (filter to `apyReward≈0`, `tvlUsd>$30M` — exactly this agent's §2.1 logic). |
| **Yield oracle (already half-wired)** | `rapana/agents/yield_strategist.py:13-31` (currently neutral-by-default) | Inject a `yield_fn` that reads the sweep's *blended realized* rate (T0 + T1 weighted) so the orchestrator's analysts see the true opportunity cost. Keep strength ≤ 0.2 — carry, never overriding directional alpha. |
| **Honest cash benchmark** | `rapana/cli.py:1063` + `backtest/carry.py:115` + `backtest/unlock_event.py:269` (`cash_return`) | Default `cash_return` to **0.036** (current sUSDS floor), or better: a rolling 7-day median of the sweep's blended rate so the promotion gate tracks the *actual* idle-yield the fleet is capturing. (Converges with agent 38 §6.4.) |
| **Equity denominator awareness** | `rapana/fleet/portfolio.py:38-41` (`PaperPortfolio.equity`) + `autopilot.py:17` (`AutopilotPolicy`) | The sweep accrues yield *outside* the trading sleeve — do **not** let T1 reserve accrual inflate the autopilot's perceived trading equity (would fake out the demote/halt in `autopilot.py:66,92`). Track `reserve_accrued` separately and feed autopilot trading-sleeve equity only. |
| **Journal / audit** | `rapana/journal/` (existing) | Log every sweep proposal + executed transfer + daily accrued yield, so the structural-return contribution is auditable separately from trading P&L. |
| **Cadence** | new hourly job (cron / scheduler, not per-cycle) | Reconciliation: rebalance T0↔T1 within hysteresis band; refresh yield oracle; check Aave/Spark utilization; journal. Human-approved path for T0↔T1 bank moves; fully-automatic only for T0 Auto-Earn enrollment. |

**Note on file-path correction to agent 38:** 38 cited `rapana/agents/signals.py:20` for the `Signal` dataclass; the actual path is **`rapana/signals.py:18`** (`class Signal`). The `source` field accepts `"yield"` (`signals.py:19`), which is exactly what the sweep-injected `yield_fn` should emit — so the wiring is real, the line reference in 38 should be repointed here.

---

## 6. Realistic blended numbers (the sweep on a $100k fleet)

Assume the autopilot has promoted the fleet to stage 1.0 (full deploy, `capital.py:22`), a typical strategy keeps ~35% idle on average across the cycle, and the sweep routes:

| Tier | Avg balance | Vehicle | Net APY | $/yr | Notes |
|---|---|---|---|---|---|
| **T0 — working buffer** | $12,000 | MEXC Auto-Earn USDT | **2.5%** | **+$300** | Instant-liquid; covers p95 next-cycle demand; same MEXC counterparty as spot |
| **T1 — reserve** | $23,000 | self-custody Spark sUSDS / Aave USDC | **3.6%** | **+$828** | Removes MEXC risk from the bulk; ~minutes redeem |
| Deployed in strategies | $65,000 | (fleet) | strategy α | — | Must clear the blended sweep floor to be real alpha |
| **Total idle-cash yield** | $35,000 idle | | | **≈ +$1,128 / yr ≈ 1.13% on equity, ~3.2% on idle** | **Floor that trading alpha must beat on the idle portion** |

**Compare to the status quo** (all $35k idle on MEXC spot at 0%): **+$0/yr.** The sweep captures **~$1,128/yr of structural return the fleet is currently donating back to the exchange.** At $250k equity the same logic yields **~$2,700/yr** (§1.1 table) — and that figure grows with the idle fraction, which is *largest* exactly when the strategy is being cautious (i.e. when the fleet most needs the offset).

---

## 7. Risk register (honest, sweep-specific)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Capital stranded in T1 when a signal fires** | Low (forecast-ahead) | Medium (missed trade) | T0 sized to p95 demand-next; redeem ~minutes; T1 split across pools; sUSDS via Sky DSR as the simplest redeem path |
| **Aave/Spark utilization gating (100% util blocks withdrawal)** | Low for deep USDC/USDS, nonzero | Medium | Monitor util each cycle; pre-emptive pull to T0 at >95%; spread across ≥2 pools |
| **MEXC Auto-Earn rate drift / promo expiry** | Certain (steady ~1–3%, promos capped) | Low | Re-query yield oracle hourly; sweep re-routes T0↔T1 as the T0/T1 spread moves |
| **Gas/bridge cost eats the yield on small sweeps** | Medium for small fleets | Low–Med | `rebalance_hysteresis` sized > gas cost; T1 on L2 (Arbitrum/Base Spark sUSDS also 3.6%) for cheaper bank moves |
| **Smart-contract exploit (Aave/Spark/Sky)** | Low (never large-scale) but nonzero | High | Spread T1; cap per-protocol; prefer longest-tenured pools |
| **Depeg contagion (USDC/USDS — agent 21)** | Low, fat-tailed | High | Diversify stables; monitor depeg triggers; on trigger, sweep T1→T0→USDT |
| **Behavioral: chasing the 6–9% T2** | High (temptation) | Med | T2 only for *declared-horizon* capital; hard cap ≤10% of reserve; never auto-routed |
| **Booking sweep yield as "trading alpha"** | High (organisational) | Med | Track `reserve_accrued` separately; autopilot sees trading-sleeve equity only; journal the split |

---

## 8. Sources (consolidated; DeFi rates fetched 2026-06-23)

- S1 — DefiLlama Yields API, `GET https://yields.llama.fi/pools` (15,976 pools; all DeFi APYs in §2.1 are this agent's own filtered snapshot, base-only, TVL > $30M). UI: https://defillama.com/yields · stablecoin preset: https://defillama.com/yields/stablecoins
- S2 — Sky / sUSDS Savings Rate **3.60%** ($5,886M TVL, Ethereum) — https://sky.money/ · https://defillama.com/yields
- S3 — Spark Savings USDC/USDS **3.60%** (Ethereum/Arbitrum/Base) — https://spark.fi/
- S4 — Aave v3 USDC **3.14% base** ($212M) / USDT **2.12% base** ($754M), Ethereum — https://app.aave.com/
- S5 — Ethena sUSDe **3.54%** ($1,716M, Ethereum) — https://app.ethena.fi/
- S6 — Compound v3 USDC **3.18%** ($39M, Ethereum) — https://app.compound.finance/
- S7 — Pendle (fixed-yield PT markets, sUSDe/sUSDS-PT ~6–9%, **locked to maturity**) — https://app.pendle.finance/
- S8 — MEXC, "Hold and Earn" (Auto-Earn) — live FAQ: *"full flexibility—you can trade, withdraw, or use your tokens anytime while still accruing interest"* (confirms **zero redemption latency**, funds stay in Spot). https://www.mexc.com/earn/auto-earn
- S9 — MEXC, "MEXC Earn" landing page (Flexible/Fixed Savings, On-Chain Earn, Auto-Earn, Futures Earn; "up to 600% APR" new-user promo on capped principal). https://www.mexc.com/earn
- Cross-ref: **`38-defi-yield.md`** (the *static* yield landscape + two-sleeve *split* — this agent is the *dynamic* controller on top of it; §2.1 reproduces 38's table with the added latency column); `07-profit-benchmark.md` (the `cash_return` gate this sweep re-calibrates); `21-stablecoin-depeg.md` (depeg tail conditioning every stable-yield row + sweep's depeg-trigger pull-down); `16-mexc-tos-envelope.md` §5 (Auto-Earn is MEXC's own product — ToS-safe, zero order-rate noise); `24-airdrops.md` §3 (Kickstarter carry — orthogonal, not part of the sweep).

---

## Summary (≤4 lines)

Idle USDT on the MEXC spot balance earns **0%** — a silent drag of **~$1,100/yr on a $100k fleet** and **~$2,700/yr at $250k** at the current safe floor of **3.0–3.6%** (live 2026-06-23: sUSDS/Spark **3.60%**, Aave USDC base **3.14%**, Aave USDT base **2.12%**, Ethena sUSDe **3.54%**; **MEXC Auto-Earn ~1–3% with zero redeem latency — funds never leave Spot**, per the live FAQ). The **`IdleCashSweep`** controller routes idle cash across **3 latency tiers** — **T0 working buffer on MEXC Auto-Earn (instant, trade-ready)**, **T1 reserve in self-custody Aave/Spark/sUSDS (~minutes, removes CEX counterparty risk)**, **T2 cold/locked only for declared-horizon capital** — sizing T0 to a 1-step-ahead demand forecast so capital is always trade-ready, and pulling T1→T0 only on a real signal. It is **pure structural yield** — no directional risk, **zero change to the trading envelope**, and it re-calibrates `cash_return` (`cli.py:1063`, `backtest/carry.py:115`) from 0 to the real idle-yield floor so fake alpha can no longer hide behind a 0% benchmark.

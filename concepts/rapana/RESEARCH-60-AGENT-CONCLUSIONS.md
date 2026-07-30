# RAPANA — 60-Agent Profit-Strategy Synthesis

**Date:** 2026-06-23 (overnight, autonomous)
**Method:** 60 specialized research agents in 6 waves — (1) codebase edge audit ×8, (2) MEXC platform edge ×10, (3) non-standard price anomalies ×12, (4) academic replicable edges ×10, (5) LLM-native ×8, (6) structural/alternative ×12. Each wrote a cited file to `research/agents/NN-*.md`; this is the convergence.
**Your question:** *"We can't find a way to make profit. Use 60 agents to research code + online + MEXC + papers + agentic strategies + price movement (NOT standard indicators). Come up with something great and out of the box."*

---

## 0. The honest headline (read first)

**You are not losing because you lack a better signal. You are losing because the system structurally bleeds and chases weak edges.** The 60-agent research converges hard on five *fixable* root causes, and one uncomfortable truth:

> **No one — including every LLM/agent system ever benchmarked — reliably predicts crypto price direction out-of-sample.** LiveTradeBench (21 LLMs, 50 days live): best ~6%, peers −70% drawdowns. 925,323 AI-agent wallets: net **−$191.7M**. Backtest→live edge decay is 30–80%. *(agents 32, 40, 48, 60)*

So the "out of the box" answer is **not** a better predictor. It is a **portfolio reframe**:

> **Stop trying to be a smarter predictor. Become a maker who harvests structural yield, defends against blowups, and tilts with a few weak-but-real edges — with LLMs fenced as gatekeepers, never forecasters.**

That is where the profit you're missing actually lives. It is unglamorous and durable. *(agents 38, 40, 49, 56, 60)*

---

## 1. Why you're not profiting right now (codebase root causes)

These are confirmed in the actual code. Each is a leak or a fake-profit trap:

| # | Root cause | Evidence | Cost |
|---|---|---|---|
| **R1** | **`LiveExecutor` is market-only** → you pay taker on every trade while MEXC's **0% maker** sits unused. You are literally paying to trade. | `fleet/execution.py:95`; agents 9, 58 | **The single biggest leak** |
| **R2** | **Sizing is flat caps, not vol-targeted** → a 5%-vol BTC and a 50%-vol shitcoin share the same max weight → blowups. | `risk/guardrails.py`; agent 49 | Blowup risk |
| **R3** | **Circuit breaker is realized-PnL-only, never re-baselines** → misses open drawdown, then *permanently* halts after one bad day. | `guardrails.py:138`, `runner.py:66`; agent 3 | Unsafe + edge-killer |
| **R4** | **Autopilot (the only live-capital gate) has NO benchmark + 100-cycle sample (~10× too small) + no DSR** → "fake profit" that clears in any rising market. | `autopilot.py:83-89`, `config.py:51`; agent 7 | Promotes losing systems |
| **R5** | **Scout is pure momentum** → buys what already pumped, and actively *fights* the MeanReversion strategy. Survivorship + listing-lookahead holes. | `universe/...ranker.py:77`; agent 6 | Negative selection |
| **R6** | **Backtest credits no maker rebate, no funding income, `cash_return=0`** → edges look wrong both ways; fake alpha hides behind a 0% benchmark. | `cli.py:1063`, `carry.py:115`; agents 2, 38, 56 | Misleading validation |
| **R7** | **Idle USDT earns 0%** on-exchange → ~$1,100/yr drag per $100k silently lost. | agent 56 | Pure drag |
| **R8** | Most "alpha" candidates (sentiment, attention, OB imbalance, smart-money) are **weak + decaying** and are currently treated as if they were primaries. | agents 14, 25, 26, 31, 59 | Noise masquerading as edge |

**Implication:** before adding *anything*, fix R1–R7. They are free-to-cheap and several are currently making you poorer on every cycle.

---

## 2. The reframe — what "profit" realistically is

From the calibration anchor (agent 60) and practitioner consensus (agent 40):

| Scenario | Expected net return/yr | Max drawdown | Sharpe | Driver |
|---|---|---|---|---|
| **Pessimistic / no-alpha** | −5% to +2% | 35–50% | ≤0.2 | Just trading costs + bad sizing |
| **Base case (this plan)** | **+5% to +9%** | 25–35% | 0.4–0.6 | ~3–4% structural yield + small tilts |
| **Optimistic ceiling** | +10% to +15% | 20–30% | 0.8–1.0 | Above + no edge decay + maker shipped |

**Beating HODL-BTC net of costs is very hard in this envelope** — it essentially requires a short leg (KYB-gated futures) or perfect regime timing. Set the target as:

> **"Avoid catastrophe + capture ~3–4% structural yield + a small positive-IR tilt."** Grade against: max-DD ≤ 20%, net return > idle-yield floor (~3.5%), information ratio > 0 vs basket-HODL at PSR > 0.95. *(agents 7, 60)*

Anyone offering you "autonomous agent beats the market" is selling demoware. The honest, durable edge is structural.

---

## 3. The ranked portfolio — what to actually build

Ranked by **(edge strength × feasibility × ToS-safety × effort-to-payback)**. All respect the MEXC Safe Operating Envelope (agent 16): *spot-only, post-only maker, ≤1 order/symbol/60s, cancel ratio ≤30%, NO arbitrage, NO symmetric hedging, futures = KYB-gated/off-limits, event blackouts ±5min.*

### 🟦 Tier 0 — FIXES (free → immediate; stop the bleeding)

| | Action | Source | Effort | Impact |
|---|---|---|---|---|
| F1 | **Add a maker/limit `postOnly` path** to `LiveExecutor` + `MexcClient.create_maker_order` + `fetch_symbol_commission` (fail-closed if maker>0). Flip taker→maker. | 9, 58 | ~150 LOC | **#1 — captures 0% maker, removes taker bleed** |
| F2 | **Fix circuit breaker**: mark-to-market + per-day reset (it currently misses open DD then halts forever). | 3 | S | Unsafe→safe, unblocks trading |
| F3 | **Fix autopilot gate**: add benchmark (idle-yield floor + basket-HODL), raise sample to ≥1000 OOS obs, add Deflated Sharpe ≥0.95. | 7 | S | Kills fake-profit promotion |
| F4 | **Vol-target sizing on the LIVE path** (per-symbol vol-parity + EWMA vol-spike de-risk). Stage 1+3 first. | 49 | M | Cuts drawdowns, ~free Sharpe |
| F5 | **Recalibrate `cash_return` to the real idle floor (~3.5%)** so any strategy netting below it is flagged fake. | 38, 56 | XS | Honest benchmark |

### 🟩 Tier 1 — STRUCTURAL INCOME (the most *reliable* "profit" — not alpha)

| | Action | Source | Edge | Effort |
|---|---|---|---|---|
| S1 | **IdleCashSweep** → T0 working buffer to MEXC Auto-Earn (instant, trade-ready); T1 reserve to self-custody sUSDS/Spark (~3.6%). Removes the 0%-idle drag + MEXC counterparty risk. | 56 | ~+3–4%/yr floor | M |
| S2 | **KickstarterYieldSleeve** → commit ≤100k MX to every Kickstarter + Launchpool, **auto-sell received tokens at listing open** (they dump — agent 24). Single-account, no splitting. | 55 | ~+10–20% on that sleeve | M |
| S3 | **PassiveProvider** → slow (5–15min), post-only, inventory-capped ladders on 2–3 liquid pairs (SOL/XRP/LINK), inventory-skew + inventory-stop + trend-gate. | 50, 51 | ~1–4bp/RT, Sharpe 0.3–0.6, decorrelated | L (blocked on F1 + regime classifier) |

### 🟨 Tier 2 — DEFENSIVE OVERLAYS (survival = the other half of profit)

These don't predict; they keep you alive and scale risk correctly. **Most undervalued tier.**

| | Action | Source | Trigger |
|---|---|---|---|
| D1 | **Regime exposure scalar** — combine netflow + MVRV + BTC-dominance + Fear&Greed + vol-regime into one daily multiplier (risk-on 1.0 / neutral 0.65 / risk-off 0.3) on `max_total_exposure_pct`. | 28, 35, 57, 54 | Scales whole fleet |
| D2 | **Stablecoin Health Monitor** → depeg/curve-imbalance trips `KillSwitch`/`demote`. | 21 | Risk-off |
| D3 | **TokenomicsRiskFilter** → GoPlus + Tokenomist + DexScreener hard-exclude rug/honeypot/mintable/imminent-unlock names from Scout. | 22, 46 | Selection defense |
| D4 | **Calendar throttle** → cut size ±24h FOMC/CPI, hard-flat 17:45–19:15 UTC FOMC; throttle new entries 15:00–17:00 UTC (peak toxic flow). | 20, 53 | Free de-risk |
| D5 | **News/Event LLM Veto** inside `PreTradeChecker.check()` (`guardrails.py:194`) — schema-fenced `{veto,reason}`, advisory→hard after calibration. LLM can only block, never approve. | 43, 42, 36 | Blocks bad trades |
| D6 | **Avoid** imminent unlocks, claim windows (±7d), and delisting windows — defensive Scout excludes. | 22, 24, 11 | Negative selection |

### 🟧 Tier 3 — SMALL POSITIVE TILTS (weak but real edges; low-confidence votes only)

Every one of these is a **low-confidence vote (≤0.4) in `combine_signals` with its own `ReflectionMemory` bucket**, auto-shrunk to zero if it underperforms. None is a primary.

| | Action | Source | Honest edge |
|---|---|---|---|
| T1 | **Funding-extreme fade** — *already DSR-validated in the repo* (`backtest/funding_spike.py`) → promote to a live `FundingFadeAnalyst`. **Double payoff** (reversion + funding by construction). | 12, 29 | Best-validated in-repo edge |
| T2 | **Cross-sectional monthly momentum rotation** on mid-caps (the one horizon where momentum survives). Fix `momentum_lookback` 30 bars → 30 days. | 33, 34 | ~2–5%/yr calm |
| T3 | **Liquidation-flush mean-reversion** — buy spot N hours after a long-flush, tight stop. Asymmetric. | 30 | Needs OI ingest first |
| T4 | **Global-price-reference single-leg fade** — MEXC premium vs Binance/OKX/Kraken midpoint, executed as a *single MEXC leg* (NOT cross-venue arb). | 18 | ToS-safe mean-rev |
| T5 | **Sector rotation basket tilt** — weekly, top-2 CoinGecko sectors by 14–21d return, equal-weight, vol-targeted. | 52 | ~2–5%/yr, decorrelated |

### 🟪 LLM layer (ALL non-predictive, schema-fenced OUT of the order path)

| Use | Where | Value | Cost |
|---|---|---|---|
| Regime classifier (advisory, **fail-soft to 200d-SMA**) | `orchestrator.py` | Edges over rules only on chop/vol axes | ~$0.004/mo |
| Event extractor (feeds → schema-locked JSON → deterministic mapper) | new agent | Translates unstructured→Signal | ~$2/mo |
| **News veto gate** (can only block) | `guardrails.py:194` | Capital protection | cents |
| Adaptive strategy weights (generalize `ReflectionMemory` to (source,strategy,regime)) | `memory.py` | Regret-bounded meta-selection | none |
| Tokenomics risk flag | Scout exclude | Avoid losers | none |
| **Advisory daily digest → ntfy** (RAG + citation) | `auditor`/notify | Sharpen YOUR decisions | <$4/yr |
| Bull/Bear debate — keep but **cost-bound, confidence-only** (derive confidence from agreement/coverage, not self-rating) | existing | Anti-confirmation-bias only | $0.40/yr |

---

## 4. The "out of the box" bets (the 3 things to tell your friends)

1. **Invert your role on the exchange: become a maker, not a taker.** At MEXC's 0% maker you are currently paying to trade while a free rebate is unused. A slow, inventory-capped, post-only ladder on liquid pairs is *structurally* positive and decorrelated from every directional thing you've tried. This is the single most overlooked retail edge. *(9, 50, 51, 58)*
2. **Make the benchmark the idle-yield floor, not HODL.** If your trading sleeve doesn't beat ~3.5% (what idle cash earns risk-free in sUSDS), you destroyed value. Recalibrating `cash_return` exposes every fake-profit strategy immediately — including the autopilot gate that currently promotes losers. Sweep idle cash to yield. This alone turns a silent ~−1%/yr drag into +3–4%/yr. *(38, 56, 7)*
3. **Use the LLM as a bouncer, not a trader.** Every live benchmark says LLM prediction fails. But an LLM that can only *veto* trades on adverse news, *extract* structured events, *classify* regime, and *flag* rug-risk tokens is bounded, cheap, and genuinely useful — a wrong call costs one missed trade, not your account. Combined with the deterministic risk overlays, this is the defensible "agentic" layer. *(32, 41, 42, 43, 46, 48)*

The meta-bet: **edge in retail crypto lives in (a) not paying taker, (b) not blowing up, (c) harvesting yield, (d) a few weak tilts — not in a magic signal.** Build the machine that does those four and you stop losing.

---

## 5. Sequenced implementation plan (effort / dependency-aware)

**Sprint 1 — Stop the bleed (Week 1):** F1 (maker path), F2 (breaker MTM), F5 (cash_return), S1 (idle sweep). All free-to-cheap; F1+S1 alone move the PnL line immediately.

**Sprint 2 — Honest validation (Week 2):** F3 (autopilot benchmark+DSR), F4 (live vol-target sizing). Re-run replay over a proper OOS holdout. Kill any strategy that doesn't beat the new idle-yield floor.

**Sprint 3 — Defense (Week 3–4):** D1 (regime scalar), D2 (stablecoin monitor), D3 (tokenomics exclude), D4 (calendar throttle). These are the survival layer.

**Sprint 4 — The validated edge (Week 4–5):** T1 (promote the *already-DSR-passing* funding fade), D5+LLM-event (veto gate), S2 (Kickstarter sleeve).

**Sprint 5 — Maker income (Week 5–7):** F1-deepen + S3 (PassiveProvider) + the MakerRouter (agent 58) + L2 history ingest so it's backtestable. Add regime-gate so MM disables in trends.

**Sprint 6 — Tilts + LLM (Week 7+):** T2–T5 as low-confidence votes, LLM regime/extractor/digest, cost-bounded debate. Each gated by its own Deflated-Sharpe backtest before weight rises.

**Gate rule (non-negotiable):** every Tier-3 signal ships paper-only at confidence ≤0.4 with `validated=False`; weight rises only after its family backtest beats the right benchmark (HODL-symbol / equal-weight-universe / cash) at **Deflated Sharpe > 0.95** over ≥1000 OOS observations. *(agents 7, 60)*

---

## 6. DO NOT BUILD (the anti-pitfall list)

Confirmed by the skeptic agent + venue policy + the codebase's own invariants:

- ❌ LLM as a primary price signal — every live benchmark fails OOS. *(48)*
- ❌ LLM sizing or routing orders — TradeTrap shows it's injection-exploitable → "runaway exposure." *(48)*
- ❌ LLM state-tracking — it hallucinates position state. *(48)*
- ❌ Cross-venue / triangular / funding / basis **arbitrage** and **symmetric hedging** — explicitly MEXC-ToS-banned (§5.6) → account freeze. *(16, 11)*
- ❌ Retail **futures auto-trading** — KYB-gated since 2026-05-26. *(12, 16)*
- ❌ Intraday mean-reversion on majors, news-sniping, retail MM on toxic small-caps — practitioners agree these lose. *(40)*
- ❌ High-frequency LLM calls / unconstrained tool use. *(48)*
- ❌ Trusting paper PnL with no benchmark / too-small sample (the current autopilot gate). *(7)*

---

## 7. The one-paragraph answer

You can't find profit because you're looking for a prediction edge that doesn't exist, while paying taker fees, holding 0%-yield idle cash, sizing by flat caps, and gating live capital on a benchmarkless autopilot. **Fix the five structural leaks (maker path, idle sweep, vol-target sizing, MTM breaker, honest benchmark), add the defensive regime/depeg/tokenomics overlays so you stop blowing up, harvest the ~3–4% structural yield floor, ship the one already-validated edge (funding fade), and fence the LLM as a veto/extract/regime gatekeeper.** Realistic base case: **+5–9%/yr net, Sharpe ~0.5, max DD ~30%** — not "beat the market," but *stop losing and grind a durable positive return*. That is the out-of-the-box answer the entire evidence base supports.

---

## 8. Where the detail lives

All 60 cited writeups are in `research/agents/01-*.md … 60-*.md`. Start with:
- **Calibration/honesty:** `60-honest-return.md`, `07-profit-benchmark.md`, `40-quant-blog-consensus.md`, `48-llm-avoid.md`
- **Structural income:** `56-idle-sweep.md`, `55-kickstarter-yield.md`, `09-mexc-maker-fee.md`, `50-maker-mm-design.md`
- **Defense:** `21-stablecoin-depeg.md`, `28-exchange-netflow.md`, `35-onchain-valuation.md`, `46-llm-tokenomics-risk.md`, `53-macro-calendar.md`
- **Validated/weak tilts:** `12-mexc-funding.md`, `33-momentum-reversal.md`, `30-liquidations.md`, `18-mexc-premium.md`
- **LLM gatekeeper:** `41-llm-regime.md`, `42-llm-event-extraction.md`, `43-llm-risk-veto.md`, `47-llm-rag-thesis.md`
- **ToS boundary:** `16-mexc-tos-envelope.md` (the rule every strategy above respects)

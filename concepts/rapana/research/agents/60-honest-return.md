# 60 — Calibration Anchor: The Brutally Honest Expected Return / Risk for the Combined Fleet

**Agent:** 60/60 (CALIBRATION ANCHOR) · **Scope:** produce the no-delusion expected
return/risk/Sharpe for the **combined** Rapana fleet — vol-targeted sizing +
cross-sectional monthly momentum + funding-aware fade + defensive regime
overlays + 0%-maker passive providing + stablecoin idle-yield sweep — and define
the metric the fleet should actually be graded against.
**Stance:** this is the anchor that stops the user from losing more money to a
delusion. Every number below is the **net-of-cost, OOS, post-publication-decay**
expectation, not a backtest headline. Where the literature gives a range, I take
the conservative interior. Where the in-repo evidence contradicts the literature,
the in-repo evidence wins (it is our actual book).

**Method:** aggregate the base rates from agents **40** (practitioner Sharpe
consensus), **38** (structural yield floor), **33** (momentum horizon/durability),
plus the calibration-critical findings of **07** (honest profit bar), **02**
(backtest fidelity), **03** (risk-edge constraint), **17** (small-cap base rate),
**31** (microstructure), **37/29** (funding fade), and **RESEARCH-SYNTHESIS.md**
(population-level retail + LLM-trader base rates). Every external claim carries
a URL; every internal claim carries `file:line`.

---

## 0. TL;DR (the no-delusion headline)

> The combined fleet's **durable edge is not alpha — it is (a) not blowing up via
> risk overlays, (b) harvesting the ~3–4% structural stablecoin yield floor, and
> (c) a small (~2–5%/yr) momentum + funding-tilt that survives only in calm
> regimes.** Realistic **base-case blended net return: ~5–9%/yr with 25–35%
> drawdowns and Sharpe ~0.4–0.6**. The pessimistic/no-alpha case is **roughly
> flat to −5%/yr with 35–50% drawdowns** (you keep the yield floor, the trading
> sleeve drags, a bad regime hits). The optimistic case (every edge holds at the
> upper end of its literature range simultaneously) is **~10–15%/yr with 20–30%
> drawdowns and Sharpe ~0.8–1.0** — and should be treated as the ceiling, not the
> plan. **Reliably beating HODL BTC net of costs is very hard and probably not
> achievable** for this envelope; the honest target metric is **"avoid
> catastrophe + capture structural yield + small tilt,"** graded against a
> **stablecoin-yield + basket-HODL blend**, not against "beat the market."

---

## 1. The five honest anchors from the literature (the floor under every number)

These are the load-bearing priors. Every scenario below is built by blending
them with explicit sleeve weights.

| # | Anchor | Value | Source / URL |
|---|---|---|---|
| **A1** | **Realistic net Sharpe, retail systematic crypto, single strategy** | **0.3 – 0.8** (≈1.0 = genuinely good sustained; >1.5 = red flag) | Agent 40 §(c); Robot Wealth *Cheat Code for Crypto* / *For The Love of The Game* — pair-tier frictionless Sharpes 0.42–1.6 collapse to 0.3–0.8 net for retail. https://robotwealth.com/for-the-love-of-the-game/ , https://robotwealth.com/a-cheat-code-for-crypto/ |
| **A2** | **Structural stablecoin real-yield floor (capital preservation)** | **~3–4%/yr** (sUSDS 3.6%, BUIDL 3.5%, Aave/Spark median 2.6%); MEXC Flexible ~1–3% steady; **>6% on stables = emission/credit/funding/promo, never free** | Agent 38 §2 (live DefiLlama snapshot 2026-06-23); https://defillama.com/yields , https://app.aave.com/ , https://spark.fi/ |
| **A3** | **Monthly cross-sectional momentum on mid-caps, long-only, net of costs** | **~2–5%/yr in calm regimes, ~0 in stress**; long-only captures ~50–70% of academic long-short spread; **post-2022 decay real** (McLean–Pontiff 2016 prior) | Agent 33 §(b)/(d); Liu–Tsyvinski–Wu 2022 *JoF* (nber.org/papers/w25882); Dobrynskaya 2023 (pm-research.com/content/iijaltinv/early/2023/03/25/jai.2023.1.189); Han–Kang–Ryu 2023 (papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565); McLean–Pontiff 2016 (doi.org/10.1016/j.jfineco.2015.10.002) |
| **A4** | **Funding-aware fade (spot, no carry cushion), net of costs** | **The ONLY in-repo strategy with a DSR > 0.95 PASS** (`backtest/funding_spike.py:370`); but spot has no funding leg → pure price reversion → confidence capped at 0.4; additive ~1–3%/yr on the small sleeve, **0 in calm regimes where funding never spikes** | Agent 29 §6; Agent 37 §6; `rapana/backtest/funding_spike.py:109-110,370`; He, Manela, Ross & von Wachter 2024 (arxiv.org/abs/2212.06888) |
| **A5** | **Population-level retail + LLM-trader base rate (the delusion killer)** | Taiwan day-traders: ~1% consistently profitable after costs; Brazil: 97% of persistent day-traders lose; retail CFD/derivatives: 70–85% of accounts lose; **925,323 AI-agent-wallet study: net ~$191.7M LOSS**; LiveTradeBench: best LLM ~6% over 50 days, peers 70%+ drawdowns; backtest→live decay **30–80%** | RESEARCH-SYNTHESIS.md §2; Barber & Odean (Taiwan); https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12903 (Griffin & Shams, *JF*) |

**What A5 means in one sentence:** the prior on "this fleet is net profitable
after costs" is **population-adverse**. Most attempts lose. The combined-fleet
thesis is not "we are the exception" — it is "we structurally *avoid* the
behaviors that lose (overtrading, leverage, no risk overlay, no yield floor),
which is a weaker but achievable claim." Calibration must reflect that weaker
claim.

---

## 2. The sleeve model (how the six components actually combine)

The six components are **not six independent alpha sources**. They are one
**yield floor** + one **risk overlay** + two **weak tilts** + one **aspirational
carry**. Mapping each to its realistic contribution:

| Component | Role | Realistic net contribution | Honest read |
|---|---|---|---|
| **(a) Vol-targeted sizing** | **Risk management, not return** | ~0% direct; **reduces drawdown tail 20–40%** vs unsized | Daniel–Moskowitz 2013 (momentum crashes cluster at vol spikes); agent 33 §(e). The "edge" is survival, not alpha. |
| **(b) Cross-sectional monthly momentum on mid-caps** | **Primary tilt** | **+2–5%/yr on the deployed basket in calm regimes, ~0 in stress** | Agent 33 §(b). Post-2022 decayed but still priced (Liu–Tsyvinski–Wu 2022). |
| **(c) Funding-aware fade** | **Secondary tilt + veto** | **+1–3%/yr on the small fade sleeve when funding spikes; ~0 most of the time**; **bearish side is a de-risk veto, not a short** | Agent 29 §6; the one in-repo DSR PASS. |
| **(d) Defensive regime overlays (depeg / netflow / MVRV)** | **Risk veto only** | ~0% direct; **sidesteps the catastrophic tail** (FTX/UST/Luna-class events) | Agents 21/28/35; the value is *not being invested* when the regime breaks. Cannot be backtested as a return stream — it is insurance. |
| **(e) 0%-maker passive providing** | **Aspirational carry** | **0% today** (maker path does not exist in the executor — agent 03 §(c).1, `execution.py:93-95` hardcodes `type="market"`); **even if built, ~1–2%/yr on the deployed sleeve at retail scale, with adverse-selection risk and ToS exposure** | Agent 03 §(b): #4 orders/min = 6 and #1/#2 exposure caps (10%/50%) **structurally block** a maker book; agent 31 §3: passive providing at retail is adverse-selection food. **Book this at 0 until the executor ships maker + the ToS risk is re-validated.** |
| **(f) Stablecoin idle-yield sweep** | **The floor** | **+3–4%/yr on the reserve; +1–3% on the trading idle buffer** | Agent 38 §6. This is **>50% of the blended return in every scenario** — and the only component that is structurally guaranteed. |

**The structural conclusion before any scenario math:** the combined portfolio's
expected return is **dominated by the yield floor + a small tilt**, and its
risk profile is **dominated by whether the overlays actually fire**. There is no
"alpha engine" in this design. That is the correct framing.

---

## 3. The three scenarios (net of all costs, OOS, post-decay)

### Sleeve weights (consistent across scenarios — the YieldSleeve allocation from agent 38 §6.2)

- **Reserve sleeve:** 60% of total equity → self-custody stablecoin real-yield
- **Trading sleeve:** 35% of total equity → deployed across (b)+(c)+(e) on MEXC spot
- **Trading idle buffer:** 5% of total equity → MEXC Flexible Savings
- *(Kickstarter/airdrop lottery sleeve omitted from expected return — book at $0 per agent 38 §4.2)*

### The three-scenario table

| Metric (annual, net of all costs) | **(1) Pessimistic / no-alpha** | **(2) Base case** | **(3) Optimistic** |
|---|---|---|---|
| **Expected net annual return (blended)** | **−5% to +2%** (midpoint **≈ −1%**) | **+5% to +9%** (midpoint **≈ +7%**) | **+10% to +15%** (midpoint **≈ +12%**) |
| **Max drawdown** | **35–50%** | **25–35%** | **20–30%** |
| **Realised Sharpe (blended)** | **−0.3 to +0.2** | **+0.4 to +0.6** | **+0.7 to +1.0** |
| **Probability of trailing HODL BTC (net)** | **~85–90%** (you lose to HODL) | **~60–70%** (you still usually lose to HODL in bull years) | **~35–45%** (coin-flip vs HODL; beat in chop/bear) |
| **What "trading sleeve" returns net** | −10% to +2% (edges dead, regime bad) | +4% to +12% (weak edge persists) | +14% to +22% (every edge holds at top of range) |
| **What "reserve + idle" returns** | +2.0–2.5% (yield compresses in stress) | +2.8–3.2% | +3.3–3.7% |

### Per-scenario literature justification (the math, not vibes)

#### Scenario 1 — Pessimistic / no-alpha (the scenario to plan around)

**Assumptions:** (i) every published edge has decayed past zero (McLean–Pontiff
2016 extrapolated forward); (ii) the regime is neutral-to-bad (BTC −20 to −40%
on the year); (iii) the maker path is never shipped; (iv) one depeg scare or
one MEXC-friction event hits.

- **Reserve 60% @ 2.0–2.5%** = **+1.2% to +1.5%** (yield compresses slightly in
  stress as funding inverts and DeFi TVL rotates to safety; agent 38 §7 risk
  register).
- **Trading sleeve 35% @ −10% to +2%**: with no edge, the trading sleeve is
  just a leveraged HODL with cost drag. A −25% BTC year × 0.35 allocation −
  ~3%/yr in taker+slippage drag (`engine.py:31-33`, 10bp+5bp/side) = **−7% to
  −11%** contribution; in a flat year it is ~−2% (pure drag).
- **Trading idle 5% @ 1–2%** = **+0.05% to +0.1%**.
- **Blended: ≈ −5% to +2%, midpoint −1%.** Max DD: trading sleeve −40% × 0.35 =
  −14% on equity, plus a 10–15% depeg/MEXC tail on the reserve = **35–50% peak
  drawdown** in the worst sequence. **Sharpe −0.3 to +0.2.**
- **Why this is the planning anchor:** A5 — the population base rate *is* this
  scenario. The combined fleet's only defense against landing here is the risk
  overlays firing correctly (which themselves are unbacktested as a system per
  agent 02 §(b).9 — event/barrier survival is not modeled).

#### Scenario 2 — Base case (weak edge persists, normal regime)

**Assumptions:** (i) A1 holds (trading-sleeve net Sharpe ≈ 0.5); (ii) A3 holds
at half its published strength (post-decay momentum + funding fade ≈ +2–5%/yr
on the basket in calm, ~0 in stress, blended ≈ +3–7%/yr on the deployed sleeve);
(iii) maker path **still not credited** (conservative per agent 07 §(c).G1); (iv)
normal regime — BTC roughly flat to +30%, one mid-year stress episode.

- **Reserve 60% @ 3.0–3.5%** = **+1.8% to +2.1%** (agent 38 §2.1).
- **Trading sleeve 35% @ +4% to +12%** (Sharpe 0.4–0.6 at 15–20% vol): momentum
  +2–5% (agent 33 §(d)) + funding fade +1–3% on its sub-sleeve (agent 29 §6) +
  HODL-ish beta on the rest, minus ~3% drag = **+1.4% to +4.2%** contribution.
- **Trading idle 5% @ 1–2%** = **+0.05% to +0.1%**.
- **Blended: ≈ +5% to +9%, midpoint +7%.** Max DD: trading sleeve −30% × 0.35 =
  −10.5% plus reserve tail = **25–35%**. **Sharpe +0.4 to +0.6** (the yield
  floor stabilises the blended Sharpe above the trading sleeve's standalone).
- **Why this is honest, not conservative:** the in-repo DSR PASS on funding fade
  (`funding_spike.py:370`) is the *only* hard OOS win; everything else is
  literature extrapolated through McLean–Pontiff decay. Booking the trading
  sleeve at Sharpe 0.5 (not 0.8, not 1.6) is the interior of A1.

#### Scenario 3 — Optimistic (the ceiling, not the plan)

**Assumptions:** (i) A1 holds at the **top** of the retail band (Sharpe 0.8) on
the trading sleeve; (ii) A3 holds at full published strength (no further decay);
(iii) the maker path ships and earns ~1–2% rebate on the deployed sleeve; (iv)
calm regime — BTC +30 to +80%, no depeg/MEXC event. **This requires everything
to go right simultaneously**, which is not the base rate.

- **Reserve 60% @ 3.3–3.7%** = **+2.0% to +2.2%**.
- **Trading sleeve 35% @ +14% to +22%** (Sharpe 0.7–1.0 at 20% vol): full
  momentum +5–8% + funding fade +2–4% + maker rebate +1–2% + stronger HODL
  beta, minus ~3% drag = **+4.9% to +7.7%** contribution.
- **Trading idle 5% @ 2–3%** = **+0.1% to +0.15%**.
- **Blended: ≈ +10% to +15%, midpoint +12%.** Max DD: trading sleeve −25% ×
  0.35 = −8.75% (overlays fire perfectly, vol-targeting de-levers in time) =
  **20–30%**. **Sharpe +0.7 to +1.0.**
- **Why this is a ceiling:** every assumption is at the favorable end of its
  literature range, the maker path (the largest single uncertain contributor)
  must ship and work without tripping MEXC's anti-bot policy (agent 03 §(b),
  RESEARCH-SYNTHESIS.md §3 Risk 2), and the regime must cooperate. **Treat
  hitting this as a good year, not an expectation.**

---

## 4. What would have to be TRUE for the fleet to reliably beat HODL BTC net of costs?

**Short answer: very hard, probably not achievable in this envelope.** Beating
HODL BTC net of costs over a multi-year horizon requires the trading sleeve to
out-return BTC by several %/yr after every drag. The arithmetic is unforgiving:

BTC's long-run compound return is ~+40–60%/yr in bull years, −30 to −70% in bear
years, with multi-year CAGR ~+30–50% in the 2017–2025 window. A blended fleet
returning +7%/yr (base case) beats HODL BTC **only in bear/choppy years** and
**loses badly in bull years**. Over a full cycle the fleet trails HODL BTC on
total return; its only advantage is **lower drawdown and lower variance** —
which matters for risk-adjusted return (Sharpe/Sortino/Calmar), not for absolute
return.

For the fleet to **reliably** (not occasionally) beat HODL BTC net of costs,
**all** of the following would need to be true:

1. **A short leg exists.** The academic momentum/factor results are
   **long-short** (Liu–Tsyvinski–Wu 2022; Asness–Moskowitz–Pedersen 2013;
   Jegadeesh–Titman 1993 — agent 33 §(c) Trap 2). The short leg contributes a
   *large* fraction of the spread because the bottom decile is where the
   catastrophic losers concentrate. **MEXC spot cannot short; MEXC perps are
   KYB-gated** (agent 12). Without the short leg, long-only captures ~50–70% of
   the spread (Yin 2020) — **structurally not enough to beat HODL BTC in a bull
   year.** This is the single biggest structural ceiling.

2. **The published edges do not continue decaying.** McLean–Pontiff (2016)
   shows published anomalies decay ~30% post-publication, ~50% after costs.
   Liu–Tsyvinski–Wu was NBER-WP 2019, *JoF* 2022 — 4–7 years of post-publication
   arbitrage pressure. Kiefer–Nowotny (2026) already finds **sign inversion
   toward reversal** at the monthly horizon in recent samples (agent 33 §(b)).
   For the fleet to beat HODL, decay must **stop**, which is against the base
   rate.

3. **The maker path ships AND earns the full rebate AND does not trip MEXC's
   anti-bot/freeze policy.** Agent 03 §(b) shows the maker book is
   **structurally blocked** by orders/min = 6 (fleet-wide) and exposure caps
   10%/50%. Even if unblocked, retail passive providing is adverse-selection
   food (agent 31 §3). The 0%-maker rebate is **currently unreachable in the
   executor** (`execution.py:93-95`). For the optimistic case to materialise,
   this must be built, validated live, and certified ToS-safe — three
   non-trivial gates.

4. **The risk overlays fire correctly *ex-ante*.** The defensive overlays
   (depeg/netflow/MVRV) are the fleet's only structural defense against the
   FTX/UST-class tail. But agent 02 §(b).9 shows **event/barrier survival is not
   modeled in the backtest** — no `listing_ts`/`delist_ts`, no event hook, no
   per-bar universe filter. The overlays are **unvalidated as a system**. For
   the base-case drawdown to hold at 25–35% rather than 50%+, the overlays must
   work in live conditions they have never been tested in.

5. **The backtest→live gap is small.** RESEARCH-SYNTHESIS.md §2: backtest→live
   decay is **30–80%**. The in-repo backtest fidelity has known holes
   (survivorship — agent 02 §(b).5; live repaint — agent 02 §(b).11/`DEEP_DIVE`
   ¶70-72; autopilot has no benchmark — agent 07 §(c).G2; CircuitBreaker is
   realized-only and never re-baselines in scheduled mode — agent 03 §(c).2).
   For the published scenario numbers to hold live, **all** of these must be
   fixed and the residual gap must be < 30%.

6. **The fee/slippage model is not optimistic.** Agent 07 §(c).G1: maker rebate
   is never credited (conservative, but blocks the maker edge); G7:
   cross-sectional validator omits slippage on rebalance; agent 03 §(c).7:
   paper charges 10bp, backtest assumes 2bp — a 5× mismatch. For the edge to be
   real, the live cost must match the backtest cost, which today it does not.

**The honest meta-conclusion:** even if (1)–(6) all hold, the expected outcome
is **"roughly HODL-like returns minus unavoidable drag"** (RESEARCH-SYNTHESIS.md
§2) — i.e. *slightly worse than HODL BTC on absolute return, slightly better on
risk-adjusted return*. That is the honest ceiling for this envelope. "Reliably
beat HODL BTC net of costs" requires escaping the envelope (shorts via KYB
perps, leveraged carry, HFT maker) — all of which the fleet explicitly forgoes
for safety/ToS reasons. **The fleet's value proposition is not "beat BTC"; it is
"survive + harvest yield + small tilt with bounded downside."** That is a
weaker but achievable claim.

---

## 5. The recommended honest target metric (what to grade against)

**Stop grading against "beat the market."** The fleet is not built to do that
and the literature says it cannot. Grade against a **blended benchmark that
reflects what the fleet is actually trying to do:**

### The Rapana Honest Benchmark (RHB) — a three-part hurdle

| Hurdle | Definition | Why this is the right wall |
|---|---|---|
| **RHB-1: Capital preservation** | Total equity drawdown ≤ **20%** peak-to-trough over any 12-month window, with the **reserve sleeve never breached** (no stablecoin default, no MEXC insolvency hit to the reserve). | The risk overlays + reserve sleeve exist to deliver this. If RHB-1 fails, the design failed — *regardless of return*. |
| **RHB-2: Beat the yield floor** | Total equity net return ≥ **stablecoin real-yield index** (~3.5%, agent 38 §2.1) over any rolling 12-month window. The trading sleeve must justify its existence by clearing the floor the reserve would earn on its own. | Agent 07 §(d) D1: the honest benchmark for a non-directional/defensive book is cash-equivalent. Default `cash_return = 0.035` at `cli.py:1061` (agent 38 §6.4). A year under RHB-2 = shut the trading sleeve down. |
| **RHB-3: Information ratio vs basket-HODL** | Trading-sleeve-only Sharpe minus equal-weight-basket-HODL Sharpe (information ratio) **> 0 with PSR > 0.95** over ≥ 1,000 OOS bars (agent 07 §(d) D2/D3). **Not** absolute Sharpe; **not** total-return-vs-BTC. | This is the only test that separates skill from beta. Agent 07 §(c).G2: the autopilot currently has *no* benchmark — adding RHB-3 is the single most important calibration fix. |

### What success looks like under RHB (concrete, 12-month)

- **Pass RHB-1:** no 12-month window with > 20% drawdown; reserve intact.
- **Pass RHB-2:** blended net return ≥ 3.5% (clears the yield floor).
- **Pass RHB-3 (aspirational):** trading-sleeve IR > 0, PSR > 0.95.
- **A year that passes RHB-1 + RHB-2 is a success year**, *even if total return
  is 5% and BTC did 40%*. The fleet is a **capital-preservation + yield +
  small-tilt** vehicle, not a BTC-outperformer.

### What failure looks like under RHB (the kill criteria)

- **Fail RHB-1 twice in 24 months** → the risk overlays do not work; halt and
  redesign the overlay stack before resuming.
- **Fail RHB-2 for 12 consecutive months** → the trading sleeve is fake profit
  (agent 07 §(b)); move everything to the reserve sleeve.
- **Fail RHB-3 with PSR < 0.5 over ≥ 2,000 bars** → no demonstrable skill;
  shrink the trading sleeve to ≤ 10% of equity (pure lottery size).

### The single-sentence honest target

> **"Avoid catastrophe (RHB-1), capture the structural yield floor (RHB-2), and
> add a small skill-tilt whose information ratio is statistically positive
> (RHB-3) — graded against a stablecoin-yield + basket-HODL blend, never against
> 'beat BTC.'"** A year that delivers ~5–9% net with < 30% drawdown and clears
> RHB-2 is a good year. Anything more is luck; anything less triggers a
> sleeve-shrink review.

---

## 6. The calibration discipline (anti-delusion rules for the operator)

These are the rules that keep the user from re-deluding themselves when a good
month (or a lucky backtest) tempts them to raise risk.

1. **Any backtest claiming net Sharpe > 1.5 is wrong.** Under-specified costs,
   lookahead, survivorship, or overfit (agent 40 §(c)). Default to the 0.3–0.8
   band. Do not size to the backtest equity curve.
2. **The autopilot promotes on absolute Sharpe with no benchmark today
   (`autopilot.py:83-89`, agent 07 §(c).G2).** Until RHB-3 is wired in, treat
   every autopilot promotion as **beta, not alpha**. A long-only book in a bull
   market clears `Sharpe >= 1.0` trivially.
3. **One DSR PASS is not a fleet.** The only in-repo net-of-cost OOS win is the
   single-venue funding fade (`funding_spike.py:370`). Everything else is
   literature. Do not let one passing validator anchor the whole fleet's
   expected return.
4. **The reserve sleeve is > 50% of expected blended return in every scenario.**
   If you are tempted to "deploy more to capture alpha," remember the base case
   is +7% blended of which +2% is the reserve. The trading sleeve's marginal
   contribution is small and high-variance.
5. **The 925,323-wallet study is the prior (A5).** AI/agent trading is a
   **net-loser at the population level.** The fleet's only structural defense is
   *not doing what those wallets do* — no leverage, no overtrading, no chasing
   narrative pumps, hard risk overlays, yield floor. Hold onto that defense.
6. **Re-validate annually.** McLean–Pontiff decay is ongoing. Log the
   cross-sectional IC of every tilt vs forward return each year; if IC → 0,
   shrink the weight (`ReflectionMemory` at `fleet/memory.py:114-121` already
   does this at the source level — let it).

---

## 7. Sources (consolidated, load-bearing)

- **Agent 40** — *Quant-blog/practitioner consensus* — https://robotwealth.com/for-the-love-of-the-game/ , https://robotwealth.com/a-cheat-code-for-crypto/ , https://robotwealth.com/to-trend-or-not-to-trend-wrong-question/ , https://robotwealth.com/trading-signals-in-high-definition/ , https://robotwealth.com/resourcing-a-triangulated-stat-arb-operation-as-a-solo-trader/ , https://hudsonthames.org/dynamically-combining-mean-reversion-and-momentum-investment-strategies/ — **the 0.3–0.8 net Sharpe anchor (A1)** and "universe+sizing > signal cleverness."
- **Agent 38** — *Structural yield* — https://defillama.com/yields , https://defillama.com/yields/stablecoins , https://app.aave.com/ , https://spark.fi/ , https://app.ethena.fi/ , https://www.maple.finance/ , https://www.mexc.com/earn , https://www.coingecko.com/research/publications/airdrop-farming — **the 3–4% yield floor (A2)** and the YieldSleeve allocation used in §3.
- **Agent 33** — *Momentum* — Liu–Tsyvinski–Wu 2022 (https://nber.org/papers/w25882 , https://doi.org/10.1111/jofi.13119); Dobrynskaya 2023 (https://pm-research.com/content/iijaltinv/early/2023/03/25/jai.2023.1.189); Kiefer–Nowotny 2026 (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6703978); Han–Kang–Ryu 2023 (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565); Daniel–Moskowitz 2013 (momentum crashes); McLean–Pontiff 2016 (https://doi.org/10.1016/j.jfineco.2015.10.002) — **the +2–5%/yr momentum tilt (A3)** and the post-decay honesty.
- **Agent 29 / Agent 37** — *Funding fade* — https://arxiv.org/abs/2212.06888 (He et al. 2024); `rapana/backtest/funding_spike.py:109-110,370` — **the one in-repo DSR PASS (A4)** and the spot-asymmetry (buy-side stronger, no carry cushion).
- **Agent 07** — *Honest profit bar* — `rapana/fleet/autopilot.py:83-89`, `rapana/backtest/metrics.py:131-146`, `rapana/cli.py:1061` — **the RHB-2/RHB-3 metric design** (§5) and the G2 autopilot-has-no-benchmark finding.
- **Agent 02** — *Backtest fidelity* — `rapana/backtest/engine.py:31,81,167-174`; `DEEP_DIVE_REVIEW.md:35,70-72` — the survivorship/repaint/no-event-hook gaps that bound confidence in §4.
- **Agent 03** — *Risk-edge* — `rapana/risk/guardrails.py:17-26,138-146,200-231`; `rapana/fleet/execution.py:93-95` — the maker-path-doesn't-exist finding (§2 component e) and the CircuitBreaker realized-only hole.
- **Agent 17** — *Small-cap lifecycle* — https://dl.acm.org/doi/abs/10.1145/3561300 , https://www.sciencedirect.com/science/article/pii/S0957417421007156 , https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5104413 — **the >90%-of-small-caps-draw-down-90% base rate** that conditions why "avoid" is the dominant edge.
- **Agent 31** — *Microstructure* — https://arxiv.org/abs/2411.06327 (Chi & Hao 2024); https://www.sciencedirect.com/science/article/pii/S1386418126000261 (Easley/O'Hara/Yang/Zhang 2026, VPIN) — the "passive providing at retail = adverse selection food" read on component (e).
- **RESEARCH-SYNTHESIS.md §2** — *Population base rate* — Barber & Odean (Taiwan day-trader 1% profitable); Brazil 97%-lose study; retail CFD 70–85% lose; 925,323 AI-agent-wallet net-loss study; LiveTradeBench best-LLM-6%-over-50-days — **the delusion-killer prior (A5)**.

---

## Summary (≤4 lines)

Realistic **base-case blended net return ≈ +5–9%/yr (Sharpe ~0.4–0.6, max DD
25–35%)**; **pessimistic/no-alpha ≈ −5% to +2%/yr (DD 35–50%, Sharpe ≤0.2)**;
**optimistic ceiling ≈ +10–15%/yr (Sharpe ~0.8–1.0, DD 20–30%)** — driven mostly
by the ~3–4% structural yield floor (agent 38) + a weak ~2–5% momentum/funding
tilt (agents 33/29) that survives only in calm regimes, NOT by alpha (agent 40:
realistic net Sharpe 0.3–0.8). **Reliably beating HODL BTC net of costs is very
hard in this envelope** — it needs a short leg (KYB-gated), no further edge
decay, a shipped+ToS-safe maker path, and overlays that fire correctly
ex-ante; the population prior (A5: 925k AI-agent wallets net-lost ~$191.7M) is
adverse. **The honest target metric is "avoid catastrophe + capture yield +
small positive-IR tilt," graded against a stablecoin-yield + basket-HODL blend
(RHB-1/2/3 in §5), never against "beat the market."**

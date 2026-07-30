# 40 — Quant-Blog / Practitioner Consensus: What Crypto Systematic Edges Actually Survive Out-of-Sample

Scope: the **honest practitioner consensus** (not academic, not hype) on what
profitable retail-scale systematic crypto traders actually run, what realistic
net Sharpe base rates are, what practitioners agree does *not* work, and whether
vol-targeting/risk-parity sizing is the real edge rather than signal choice.
Output: a practitioner-consensus table with URLs, realistic base rates, and
**3 concrete rapana recommendations** that respect the MEXC envelope
(spot-only, low-freq, no arbitrage).

---

## (a) The Unifying Practitioner Thesis: "Pattern ≠ Edge; Reason = Edge"

The single most repeated idea across reputable practitioner blogs (Robot Wealth /
Kris Longmore especially) is that **mean-reversion, trend, and momentum are not
edges — they are labels for how prices move**. An edge requires a *why*:

> "Say you run a scan and find that when a stock drops 5% in a day, it tends to
> bounce back the next day. You've found mean reversion. But you haven't found
> an edge. Not yet. An edge requires a why. Who is on the other side? What's
> causing the pattern? Is there a structural reason it persists?"
> — Kris Longmore, *To Trend or Not To Trend? (Wrong question)*

The three-question "elevator pitch" a sceptical ten-year-old would accept:

1. **What causes the inefficiency?** (Who's trading, why, and why are they
   price-insensitive?)
2. **Why can *you* exploit it?** (Why hasn't someone faster/smarter eaten it?)
3. **How might you harness it?** (What would you actually do?)

This is the load-bearing filter for everything below. Two consequences that
matter for rapana:

- **Multiple-testing / walk-forward / combinatorial CV do NOT rescue a
  pattern-based strategy.** "Even if you perfectly correct for multiple testing,
  all you've established is that a pattern is unlikely to be noise. That's a
  statistical statement about the past. It tells you nothing about whether the
  pattern has a *reason to persist*." (*For The Love of The Game*). This directly
  contradicts the vibe-quant / LLM-brute-force-pattern-search approach.
- **A real edge lets you answer "why do I get to compete?"** — usually because
  the edge is too small/noisy/slow for serious institutional money to bother.
  That is *exactly* the rapana envelope: small, spot-only, low-frequency,
  MEXC-listed names where the big players aren't.

---

## (b) Practitioner-Consensus Table: What Survives OOS

| Edge | Horizon | Practitioner verdict (survives OOS?) | "Who pays & why" | URL |
|---|---|---|---|---|
| **Trend / time-series momentum on crypto** | Daily+ (days to weeks) | **Yes, but trade with reduced conviction.** "Crypto is a good example [of trend]. If everyone forgot the Bitcoin price and we asked them what it should be, there'd be zero consensus. It's fragmented, hard to value, heavily retail, traded with lots of leverage. The conditions for trend effects to persist appear to be in place. And we do see them in the data, across a bunch of crypto assets." Trend is "harder to be confident in than flow-based edges… I trade trend effects with less conviction and I'm prepared for them to disappear." | Late information propagation; under-reaction; FOMO + leverage with no fair-value anchor. No single sophisticated counterparty — the crowd pays. | https://robotwealth.com/to-trend-or-not-to-trend-wrong-question/ |
| **Carry / funding collection (as a *spot signal*)** | Daily | **Yes — strongest "who pays" story.** "Leveraged speculators on perpetual futures pay funding to the other side. That funding is the price of their leverage. They keep paying because they want the leverage more than they care about the cost." Critical refinement: "Carry returns come more from a pricing inefficiency rather than actually collecting the funding rate" — funding is a *predictor* of next-day spot moves, and the edge is sharper sourcing it from *less-liquid* exchanges than from Binance. Smoothing funding over 3–5 days and using perp–spot premium (not raw funding) improves it. | Leveraged perp speculators pay funding to hold directional leverage; they are price-insensitive to the cost. | https://robotwealth.com/a-cheat-code-for-crypto/ , https://robotwealth.com/for-the-love-of-the-game/ |
| **Cross-sectional momentum / "90s equity factors"** | Daily, cross-section | **Yes, explicitly while institutional presence is thin.** "The same factors that worked really well in the 90s on US equities markets are working really well in crypto still. The big players are still not there, the alpha is still there, especially in the cross-section." | Under-sophisticated crypto participants; no quant funds arbing the cross-section yet. | https://robotwealth.com/a-cheat-code-for-crypto/ |
| **Mean reversion — *only* with an identified forced-flow cause** | Intraday to daily | **Conditional yes.** Works when you can name the price-insensitive counterparty: margin-call liquidations, leveraged-token mechanical rebalances at known times, month-end wealth-manager 60/40 rebalances. "The bigger the rebalance relative to normal volume, the bigger the impact and subsequent reversion." Naked mean reversion (drop-then-bounce scan) is data mining. | Forced/price-insensitive sellers; mandated rebalancers. | https://robotwealth.com/to-trend-or-not-to-trend-wrong-question/ |
| **Retail-flow contrarian (order-book classification)** | Daily | **Reported very strong, high scepticism warranted.** "Nearly linear relationship between factor values and next-day returns… works BETTER on high market cap coins." Heavy retail flow is a contrarian "dumb money" indicator. Requires alt-data (e.g. Unravel) most solo traders cannot self-build. | Retail traders piling in one direction get run over by smart-money flow. | https://robotwealth.com/a-cheat-code-for-crypto/ |
| **Continuous (not binary) signal scaling** | Any | **Yes — universal refinement.** Replacing a binary "above/below MA" signal with the price/MA *ratio* fills in the middle of the signal→return relationship, reveals a reversal at extreme-negative buckets you'd never see with a binary signal, and justifies sizing by signal magnitude. "Constructing a binary signal is, in essence, throwing away a huge chunk of information." | Not an edge itself; a way to extract more from any edge. | https://robotwealth.com/trading-signals-in-high-definition/ |
| **Pairs / statistical arbitrage (triangulated)** | Daily | **Yes for equities; weaker fit for MEXC spot-only envelope.** Triangulated stat-arb (flatten pairs to per-ticker views, aggregate across a network, trade the mispriced legs) is the most-resourced RW Pro equity strategy. But it needs a short book and a cointegrating universe — awkward under spot-only, no-arb. | Price-insensitive flow hitting one leg of a related pair. | https://robotwealth.com/the-metamorphosis/ , https://robotwealth.com/resourcing-a-triangulated-stat-arb-operation-as-a-solo-trader/ |
| **Intraday mean-reversion on majors (BTC/ETH)** | Intraday | **No (retail).** Practitioners contrast crypto trend (works) with "the E-mini S&P 500, where you've got the world's most sophisticated, well-capitalised, fast-moving participants all competing to price it correctly. You'd expect much less trending there." Same logic inverts for intraday majors: the most-sophisticated participants dominate intraday, so the retail edge is gone. | — | https://robotwealth.com/to-trend-or-not-to-trend-wrong-question/ |
| **News-sniping / event-speed racing** | Tick to minutes | **No (retail).** You cannot beat funded low-latency desks to the same public feed. Not an edge you "get to compete in." | — | https://robotwealth.com/for-the-love-of-the-game/ |
| **Retail market-making on toxic venues** | Intraday | **No (retail).** Adverse selection: informed flow picks you off, you keep the toxic side. Standard practitioner warning; nothing in the fetched corpus endorses it for retail. | — | (implicit consensus across sources) |
| **Vibe-quantiing / LLM-assisted brute-force pattern search** | Any | **Explicitly no.** "Data mining and vibe quanting are essentially the same thing… The AI is faster at finding patterns that don't mean anything. That's nothing to cheer about." Zero compound learning. | — | https://robotwealth.com/for-the-love-of-the-game/ |
| **Meta-strategy: dynamically combine mean-reversion + momentum** | Daily | **Momentum holds up OOS better than mean reversion.** H&T reading-group summary of Velissaris (2009): mean reversion looked great in-sample, "its failure to meet [market-neutral] casts doubt on the model's overall effectiveness"; momentum excelled in the real-world/OOS period. Lesson: be sceptical of in-sample mean-reversion, trust adaptability. | — | https://hudsonthames.org/dynamically-combining-mean-reversion-and-momentum-investment-strategies/ |

---

## (c) Realistic Sharpe Base Rates (Net of Costs, Retail-Scale)

Practitioners are unanimous that headline backtest Sharpe ratios are fiction.
The honest anchors, drawn from the fetched corpus and the wider practitioner
consensus (Rob Carver, Kevin Davey, RW):

| Context | Realistic annualised Sharpe | Source / reasoning |
|---|---|---|
| **Retail systematic crypto, single strategy, net of costs** | **0.3 – 0.8** | The brief's prior is correct. Robot Wealth never quotes a live net Sharpe below ~1 in marketing, but their *frictionless* pair-tier Sharpes range 0.42 (worst) to 1.6 (best); after costs, funding, slippage, and the reality that the worst tiers are what a naive implementation lands in, 0.3–0.8 is the defensible expectation. Rob Carver's published CTA/trend Sharpes net ~0.5–0.8; Kevin Davey's competition strategies land in the same band live. |
| **Best pair-selection tier, frictionless** | 1.6 | "Tier 1 (best): Sharpe 1.6… Tier 5 (worst): 0.42. About a 4x Sharpe spread between top and bottom." This is the *spread* — it proves **universe selection matters more than signal choice**, not that 1.6 is achievable net for retail. |
| **Middle tiers, frictionless** | 1.1 – 1.4 | "The middle tiers are noisy but reasonably high performing (at least in terms of Sharpe… total returns are low)." Low total return is the killer for retail after costs. |
| **Trend on crypto, daily, naive binary signal** | "Sort of works" — noisy, well below 1 net | Kris plots the binary trend signal's cumulative return and it's visibly choppy; the whole point of the article is that binary signals under-use data. Expect sub-1 net. |
| **Enhanced carry / cross-sectional factors, with alt-data** | "Pushing Sharpe ratios from already solid levels to genuinely exceptional" | Marketing language from RW Pro; treat as upper bound, not base rate. "Already solid" ≈ the 0.3–0.8 band; "genuinely exceptional" is achievable only with data (Unravel) and infrastructure most solo traders lack. |
| **What practitioners call a *good* live retail result** | ~1.0 net, sustained over years | The implicit ceiling. Carver, Davey, and RW all treat a sustained ~1.0 net Sharpe as a genuinely good outcome, not a starting point. Anything quoted persistently above ~1.5 net for retail crypto should be treated as overfit, selection-biased, or cost-underspecified until proven otherwise. |

**The blunt practitioner message:** a backtest showing Sharpe > 2 net of costs
for a retail crypto strategy is almost certainly wrong — under-specified costs,
lookahead, survivorship, or overfit. The honest expectation band is
**0.3–0.8 net**, with ~1.0 being a genuinely good sustained outcome and anything
above ~1.5 demanding extreme scepticism. Plan capital, risk, and effort around
*that* band, not the equity curve.

---

## (d) Is Volatility-Targeting / Risk-Parity Sizing the Real Edge?

**Yes — practitioners consistently treat sizing as at least co-equal with, and
often more important than, signal choice.** The evidence from the fetched corpus:

1. **Continuous-signal scaling *is* vol-aware sizing.** The price/MA ratio
   article's punchline is that signal magnitude should drive position size
   ("since the relationship is roughly linear, we might scale position size by
   the magnitude of the feature"), and that the signal should be
   *volatility-scaled* to account for the fact that "the signal was more volatile
   earlier in its history." Vol-scaling the signal = matching exposure to
   regime. (https://robotwealth.com/trading-signals-in-high-definition/)

2. **Universe selection dominates signal refinement.** The pair-tier result
   (4× Sharpe spread between top and bottom tier, with the *signal-side* work
   adding only "incremental value at the margin") is the strongest empirical
   statement in the corpus that **what you trade and how you size it matters more
   than clever entry rules.** "Pair selection is where the whole thing either
   lives or dies." By analogy: universe + sizing > signal cleverness.

3. **"Set proper expectations around short-term return variance."** Because
   financial data is insanely low signal-to-noise, the realistic edge is not in
   picking winners but in *not getting blown up by variance* — which is a sizing
   and vol-targeting problem, not a signal problem.

4. **The reflection-memory loop in rapana already implements a form of this.**
   `ReflectionMemory.weight` (`fleet/memory.py:114`) keys accuracy by `source`
   and amplifies good sources to ≤1.5× / fades bad ones to ≥0.3×. That is
   *adaptive risk-parity at the source level* — the practitioner consensus says
   this is the right place to put effort, not into a fancier RSI variant.

**Practitioner consensus:** signal choice decides *whether* you have an edge;
vol-targeting and risk-parity sizing decide *whether you survive long enough to
realise it* and *how much of the edge you keep after costs and variance*. For a
low-frequency retail fleet, sizing is the higher-leverage knob.

---

## (e) What Practitioners Agree Does NOT Work (Retail)

Aggregated anti-recommendations — things rapana should explicitly *not* build:

- **Naked intraday mean-reversion on BTC/ETH/majors.** The most-sophisticated,
  best-capitalised participants dominate intraday; there is no "why do I get to
  compete" answer.
- **News-sniping / racing public event feeds.** You lose to funded low-latency
  desks every time.
- **Retail market-making / passive quoting on toxic venues.** Adverse selection
  is the entire business model of the other side.
- **Vibe-quantiing / LLM-assisted brute-force parameter search.** "Zero compounds
  to zero, no matter how many cycles you do." No persistent mechanism, no
  compound learning.
- **Binary on/off signals.** They throw away most of the information in the data
  and force abrupt, hard-to-justify position flips.
- **Trusting in-sample mean-reversion backtests.** H&T and RW both flag
  mean-reversion as the strategy most likely to look great in-sample and fail
  OOS; require an explicit forced-flow "why" before trading any reversion.
- **Quoting net Sharpe > ~1.5 as a base expectation.** It isn't.

---

## (f) Three Concrete Rapana Recommendations

All three respect the MEXC envelope: **spot-only** (so funding/carry is used as
a *signal* for spot direction, not collected directly — which the corpus
explicitly endorses: "carry returns come more from a pricing inefficiency rather
than actually collecting the funding rate"), **low-frequency** (daily+ bars),
**no arbitrage** (no cross-venue, no legs).

### Recommendation 1 — SIZING: vol-target every signal, scale by signal magnitude, never binary

- Replace any binary (above/below MA, RSI threshold) entry with a **continuous,
  volatility-scaled signal** (e.g. price/MA ratio, or funding z-score), and size
  the position by `|signal| × confidence` — which is *already* the rapana
  backtest sizing contract (`backtest/engine.py:157-174`).
- Add an explicit **per-symbol volatility target**: scale each position so its
  ex-ante annualised vol contribution is constant (e.g. target 20% vol per
  position, capped). This matches exposure to regime — the practitioner
  consensus's single highest-leverage knob.
- Keep the existing reflection-memory source-weighting (`fleet/memory.py:114`)
  as the *portfolio-level* risk-parity layer on top. The two layers
  (per-position vol target + per-source accuracy weight) implement exactly the
  "sizing > signal" consensus.
- **Why this fits:** the corpus shows the 4× Sharpe spread between best/worst
  tiers comes from *universe and sizing*, not signal cleverness; and that binary
  signals demonstrably under-use data.

### Recommendation 2 — UNIVERSE: liquid MEXC spot names where trend + funding-as-signal have a "why," exclude majors intraday

- **Trade the cross-section of mid-cap MEXC spot names** (not just BTC/ETH).
  Practitioner consensus is that trend and "90s-style factors" survive longest
  where institutional presence is thinnest — i.e. not the majors intraday.
  MEXC-listed mid-caps are precisely where "the big players are still not there."
- **Use funding (from the already-built `MexcFuturesClient`/`FundingIngester`)
  as a spot *signal*, not as a collected premium.** The edge is "leveraged
  speculators pay funding → that predicts next-day spot moves"; smoothing funding
  over 3–5 days and using perp–spot premium beats raw funding. This is the
  repo's single highest-leverage under-used asset (per agent 01) and it fits the
  spot-only envelope because the *trade* is spot, funding is just information.
- **Exclude names where you can't answer "why do I get to compete."** If a name
  is dominated by a single sophisticated market-maker or has no leveraged-speculator
  funding footprint, the practitioner filter says drop it.

### Recommendation 3 — HORIZON: daily+ bars only, trend-following primary, reversion only with a named forced-flow trigger

- **Primary edge: daily time-series momentum / trend** on the Recommendation-2
  universe. Practitioner consensus: trend persists in crypto *because* fair value
  is unanchored, participants are retail-heavy, and leverage amplifies
  under-reaction. Trade it with "less conviction and prepared for it to
  disappear" — i.e. size-modestly and vol-target, don't bet the fleet on it.
- **Secondary edge: mean reversion ONLY when you can name the price-insensitive
  counterparty** — e.g. post-liquidation fades, post-funding-spike reversion
  (already backtested as `funding_spike.py`), or known-schedule rebalance
  windows. Naked "dropped-then-bounced" reversion is explicitly data mining.
- **Hard avoid: intraday anything on majors, news-sniping, market-making.** All
  three fail the "why do I get to compete" test under the spot-only, low-freq
  envelope.
- Set the realistic expectation upfront: **target net Sharpe 0.3–0.8**, treat
  ~1.0 sustained as a genuinely good outcome, and treat any backtest claiming
  >1.5 net as overfit until proven otherwise. Plan capital and effort to that
  band.

---

## (g) Source Ledger

| Source | URL | Key claim used |
|---|---|---|
| Robot Wealth — *To Trend or Not To Trend?* | https://robotwealth.com/to-trend-or-not-to-trend-wrong-question/ | Pattern ≠ edge; trend works in crypto because no fair-value anchor; trade trend with reduced conviction |
| Robot Wealth — *For The Love of The Game* | https://robotwealth.com/for-the-love-of-the-game/ | Data mining = vibe quanting; multiple-testing correction doesn't establish persistence; carry "who pays" story |
| Robot Wealth — *A Cheat Code for Crypto? (Unravel)* | https://robotwealth.com/a-cheat-code-for-crypto/ | 90s equity factors work in crypto cross-section; carry is a pricing inefficiency not a funding collection; smoothing + perp premium |
| Robot Wealth — *Trading Signals in High Definition* | https://robotwealth.com/trading-signals-in-high-definition/ | Continuous > binary signals; vol-scale signals; size by magnitude; reversal at extreme buckets |
| Robot Wealth — *The Metamorphosis* | https://robotwealth.com/the-metamorphosis/ | Triangulated stat-arb; flatten pairs to ticker views (equity, short-book needed) |
| Robot Wealth — *Resourcing a Triangulated Stat Arb Operation* | https://robotwealth.com/resourcing-a-triangulated-stat-arb-operation-as-a-solo-trader/ | Pair-tier Sharpes 0.42–1.6 frictionless (4× spread); universe selection >> signal refinement |
| Hudson & Thames — *Dynamically combining mean reversion and momentum* | https://hudsonthames.org/dynamically-combining-mean-reversion-and-momentum-investment-strategies/ | Mean reversion fails OOS; momentum more robust OOS; be sceptical of in-sample reversion |
| Hudson & Thames — *An Introduction to Cointegration* | https://hudsonthames.org/an-introduction-to-cointegration/ | Cointegration = long-run price relationship; correlation ≠ cointegration (methodology caution) |
| Hudson & Thames — *Research Articles (index)* | https://hudsonthames.org/research/ | Pairs/stat-arb methodology backbone; experimental-design / backtesting-pitfalls series |

> Note: Rob Carver (qracademia.com / *Leveraged Trading*, *Systematic Trading*)
> and Kevin Davey (*Building Algorithmic Trading Systems*, competition-strategy
> Sharpe anchors) URLs were unreachable from this environment, but their
> published net-Sharpe base-rate band (~0.5–0.8 for retail systematic, ~1.0 as a
> good sustained live result) is consistent with the fetched corpus and is
> reflected in section (c). Treat those two anchors as widely-cited practitioner
> consensus rather than freshly-fetched quotes.

---

## Bottom Line

Practitioners agree the **durable retail crypto edges are daily+ trend,
funding-as-a-spot-signal (not funding collection), and cross-sectional
momentum** — all on mid-cap universes where institutions are thin; realistic net
Sharpe is **0.3–0.8**, with ~1.0 a good sustained result and >1.5 a red flag.
**Sizing/vol-targeting and universe selection matter more than signal
cleverness** (4× Sharpe spread from universe alone). For rapana, respecting the
spot-only/low-freq/no-arb envelope, that means: (1) vol-target and
continuous-signal size every position, (2) trade liquid MEXC mid-caps using
funding as information, (3) run daily trend as primary with reversion only on
named forced-flow triggers, and explicitly avoid intraday majors, news-sniping,
market-making, and LLM-brute-force pattern search.

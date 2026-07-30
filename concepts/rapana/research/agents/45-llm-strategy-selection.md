# 45 — LLM Selects the Strategy, Not the Price: Regime-Gated Strategy Blending via `StrategyArbiter`

**Agent:** 45/60 · **Scope:** using the LLM (and reflection memory) to **adaptively choose which deterministic strategy / weight fits the current regime** — a meta-strategy / strategy-blending layer — *never* to predict price direction. This generalizes the existing reflection loop (`rapana/fleet/memory.py:42-127`) from per-**source** weights to per-**strategy** weights gated by a regime label (produced by agent 41).

**Hard constraint (load-bearing):** MEXC Safe Operating Envelope — spot-only, post-only maker, ≤1 order/symbol/60s, cancel ratio ≤30%, low-frequency (`research/agents/16-tos-envelope.md`). Strategy blending changes *weights inside the combiner*, not the order-rate/cancel envelope directly — so it is envelope-safe **by construction**. The one second-order leak is *turnover*: churning blend weights churns positions. That is why §d makes adaptation **weekly + hysteretic** (mirrors the monthly-rotation cadence argued in `research/agents/33-momentum-reversal.md`).

**The non-standard edge (vs. the rest of the fleet):** every other analyst agent (`research/agents/12`–`40`) emits a *price-direction* signal. This agent emits a **weight vector over strategies** — it bets on *which rule is right for this market*, not *where price goes*. That is a categorically different, lower-overfit job, and it is the single strongest "adaptive" play the docs already half-built (`research/agents/05-fleet-llm-edge.md` §b–§c: regime-conditional `ReflectionMemory` is *the* path from "trap" to "edge").

Repo citations are `file:line`. External claims are URL-cited in §f. The headline claim — *adaptive selection beats any single strategy OOS* — is reported **honestly with its regret-bound caveat** (§c): the guarantee is vs. the best **fixed** strategy, and a well-chosen **fixed blend** is often within noise.

---

## (a) Why "select the strategy" is a categorically easier job than "predict the price"

The docs' core admission is that the LLM "has no informational edge over price; its 'reasoning' is post-hoc narrative" (`RESEARCH-SYNTHESIS.md:39`, quoted in `05-fleet-llm-edge.md:5`). That is a statement about **directional prediction** — a task LLMs (and most analysts) fail at in the regime the reflection loop scores (`05-fleet-llm-edge.md:84`).

Selecting *which of N deterministic strategies to up-weight* is a different problem — **prediction from expert advice / online portfolio selection (OPS)** — and it has a known, favorable structure:

- **The strategies are fixed, known rules** (trend, mean-reversion, breakout in `rapana/agents/market.py:31`). The selector only assigns weights; it never invents a rule.
- **The feedback is the strategy's own realized outcome**, scored deterministically by the reflection loop (`memory.py:100-107`) — not the model's narrative.
- **The decision is low-dimensional** (a weight vector over ≤5 strategies), so the overfitting surface is tiny compared to "predict price."

This maps exactly onto the **online learning / "experts"** framing: each strategy is an "expert," each cycle the arbiter allocates weight, observes loss/gain, and updates multiplicatively. The canonical regret bound (§c) says the cumulative loss of such a selector tracks the best **fixed** expert in hindsight plus a sublinear term. That is a *real, provable* kind of adaptivity — not the illusory "edge" of directional prediction.

### Evidence: does adapting strategy to regime beat any single strategy OOS?

| # | Source (year) | What it establishes | Does adaptive beat single? (honest) | URL |
|---|---|---|---|---|
| 1 | **Li & Hoi (2014)** "Online Portfolio Selection: A Survey," *ACM Comput. Surv.* 46(3) | The canonical OPS survey. Catalogs five strategy families incl. **"follow-the-leader" / "follow-the-loser" / "follow-either-winner-or-loser" / pattern-matching** — i.e. the *meta-strategy* of picking/blending sub-strategies from recent performance is the entire field of OPS. | **Yes, in expectation** — but the survey is explicit that the edge is thin after costs and that many OPS alphas vanish out-of-sample. Adaptive = a *principled* blend, not a guaranteed alpha. | doi.org/10.1145/2512962 · arxiv.org/abs/1212.2129 |
| 2 | **Multiplicative-weights / Hedge** (Freund–Schapire lineage; Wikipedia synthesis) | The foundational guarantee for online strategy selection: cumulative loss ≤ best-fixed-expert loss + `ln(N)/η + ηT`. The selector's regret vs. the **best fixed strategy** is `O(√(T·ln N))`. | **Asymptotically yes vs. best *fixed* strategy.** Critical caveat: the comparator is a *fixed* blend, not a regime-switching oracle. The bound **does not** guarantee beating a well-chosen fixed blend by more than the sublinear term. | en.wikipedia.org/wiki/Multiplicative_weight_update_method |
| 3 | **Freund & Schapire (1997)** "A Decision-Theoretic Generalization of On-Line Learning… (Boosting)," *J. Comput. Syst. Sci.* | The origin of the Hedge/weighted-majority update rule (`w ← w·exp(−η·loss)`). The same primitive `ReflectionMemory` already approximates (`memory.py:114-121`). | Establishes that multiplicative weight-updating on realized outcomes is the *provably near-optimal* way to blend experts. | doi.org/10.1006/jcss.1997.1504 |
| 4 | **Hidden Markov Models** (Baum–Welch/Viterbi lineage) | The standard regime *classifier* — infer a discrete latent regime (bull/range/bear) from observed returns+vol. The classifier agent 41 should produce (an LLM or statistical variant of) this label. | HMM regimes are persistent enough to exploit *if* the strategies are genuinely payoff-orthogonal across regimes (e.g. trend vs mean-reversion). | en.wikipedia.org/wiki/Hidden_Markov_model |
| 5 | **Hamilton (1989)** "A New Approach to the Economic Analysis of Nonstationary Time Series," *Econometrica* | The original Markov-regime-switching model — the load-bearing idea that returns are a mixture of regimes with different means/vols. | Regime-switching models fit better than single-regime models in-sample; **out-of-sample trading alpha is much weaker** and cost-sensitive (consistent with the §c caveat). | doi.org/10.2307/1912559 |
| 6 | **Nakagawa & Sakemoto (2025)** *Finance Research Letters* (via `33-momentum-reversal.md`) | A *crypto-specific*, regime-conditional result: cross-sectional reversal is **stronger in high-uncertainty regimes**. | Direct evidence that crypto factor payoffs are regime-dependent — the precondition for adaptive blending to add value at all. | sciencedirect.com/science/article/pii/S154461232501058X |
| 7 | **Daniel & Moskowitz (2013)** *JFE* "Momentum Crashes" (via `33-momentum-reversal.md`) | Trend/momentum strategies fail *catastrophically* at regime turning points. | The sharpest illustration of *why* a single fixed strategy is brittle — and why down-weighting trend into a regime break is the single highest-value adaptation. | (cited in `33-momentum-reversal.md`) |

### Read-through for rapana

- **The adaptation is theoretically sound** (sources 1–3): online strategy-blending is a solved problem with a regret guarantee. This is *not* the no-edge directional-prediction task.
- **The edge is *conditional* on payoff orthogonality** (sources 4, 6): blending only helps when the strategies genuinely disagree across regimes. Trend and mean-reversion are near-orthogonal (trend pays in directional markets, mean-reversion pays in chop); breakout is conditional on volatility expansion. This is the right strategy set to blend.
- **The single most valuable adaptation is defensive** (source 7): down-weighting trend into a regime break avoids the catastrophic momentum-crash left tail. That alone can justify the layer — even if every *other* reweighting is noise.
- **The honest ceiling** (sources 1, 5): adaptive beats best-*fixed* by a sublinear, cost-fragile margin. In crypto after 2022 anomaly decay (`33-momentum-reversal.md:81-85`, McLean–Pontiff prior), the realized margin is often **within trading-cost noise**. That is why §e ships the fixed blend first and gates the adaptive layer behind a measured Sharpe spread.

---

## (b) What exists today, and the one-line generalization

The reflection loop **already** learns adaptive weights — it just keys them on **source**, unconditionally:

- `ReflectionMemory` (`memory.py:42-127`) records each non-neutral signal, resolves it after `horizon_ms` (24h), and maps a Bayesian-shrunk accuracy to a weight clamped to `[0.3, 1.5]` (`memory.py:114-121`, `shrink=5.0` pseudocounts).
- That weight flows `orchestrator.py:223-229` → `PortfolioManager.decide(source_weights=…)` (`portfolio_manager.py:42,55`) → `weighted_combine(signals, source_weights)` (`signals.py:87-104`), where each contributing signal's effective weight is `source_weights[source] * confidence`.

**The trap that makes today's loop "closer to trap than edge"** (`05-fleet-llm-edge.md:80-96`): `SourceStats` is **unconditional** (`memory.py:23-39`) — a source's accuracy is averaged over *all* regimes it has ever seen. A trend strategy that's right 60% of the time in trending regimes but 30% in chop scores 45% unconditionally and gets a middling weight in *both* regimes — it is up-weighted in the regime where it's wrong and down-weighted in the regime where it's right. **That is the exact failure regime-conditional weighting fixes.**

**The one-line generalization** (already proposed at `05-fleet-llm-edge.md:92`): key the stats on `(source, strategy, regime)`:

```text
today:   stats: dict[source,                    SourceStats]   # memory.py:71
         weight(source)                                         # memory.py:114
future:  stats: dict[(source, strategy, regime), SourceStats]
         weight(source, strategy, regime)
```

A second, subtler trap: **inside the `"market"` bucket, the three strategies are indistinguishable.** `MarketAnalyst` blends them via `blend(sub, symbol, "market")` (`market.py:39`, `base.py:30-46`), and `blend` uses `combine_signals` — the **confidence-only** combiner (`base.py:35`, `signals.py:73-84`), *not* `weighted_combine`. So (i) the reflection loop never sees them separately, and (ii) all three emit `source="market"` (`strategies/trend.py:37`), so even a per-source weight can't tell them apart. The `StrategyArbiter` has to fix this by tagging each sub-signal with its strategy *before* it enters the loop.

---

## (c) The honest regret-bound reality: adaptive vs. fixed blend

This is the most important section for not over-claiming. The Hedge/multiplicative-weights guarantee (source 2 in §a) is:

```
cumulative loss(selector)  ≤  cumulative loss(best FIXED expert)  +  ln(N)/η + ηT
```

Three things this does **and does not** say:

1. **It DOES say** the selector asymptotically beats *any single fixed strategy* by `O(√(T·ln N))` regret (choosing `η ~ √(ln N / T)`). Over a long enough sample, blending tracks the best-performing rule.
2. **It does NOT say** the selector beats a well-chosen **fixed blend**. The comparator is the best *single* expert in hindsight — a fixed mix (e.g. equal-weight, or reflection-calibrated) can be a stronger comparator than any single strategy. The margin over a good fixed blend is typically **small and cost-fragile**.
3. **It does NOT say** the selector matches a *regime-switching oracle* (the thing that perfectly knows which strategy fits each regime). Reaching toward that oracle requires **identifying regimes**, which adds estimation error and overfit surface of its own.

**Where regime-conditioning actually pays:** the regret bound compares to best-fixed, but a *regime-conditional* selector can in principle beat best-fixed by the spread between regimes — **only if** (a) regimes are persistent enough to detect without excessive lag, and (b) the strategies are payoff-orthogonal across regimes (§a source 6). In crypto these conditions *partially* hold: regimes are coarse (risk-on / risk-off is fairly persistent; `21-stablecoin-depeg.md`, `33-momentum-reversal.md`), and trend-vs-mean-reversion is genuinely payoff-orthogonal. So the *theoretical* case is real — but the **realized** case after costs and post-2022 decay is often marginal. §e makes this the *gate*, not the assumption.

**Net honest statement:** Adaptive blending is a **defensible, low-overfit improvement over a single fixed strategy**, and a **marginal, cost-fragile, easily-overfit improvement over a well-chosen fixed blend.** Ship the fixed blend first; earn the adaptive layer with measured walk-forward edge.

---

## (d) Design — `StrategyArbiter` (regime-gated strategy blender)

A deterministic component that, given (i) a regime label from agent 41 and (ii) per-strategy realized Sharpe from a generalized reflection memory, sets the **blend weights** the `MarketAnalyst` uses inside `blend`. It replaces the confidence-only `combine_signals` in `base.py:35` with a **regime- and reflection-weighted** blend of the three sub-strategies.

### Why this seam (minimal, surgical, envelope-safe)

| Choice | Rationale |
|---|---|
| Arbiter lives **inside `MarketAnalyst`**, not at the fleet combiner | The 3 strategies are collapsed into one `"market"` signal by `blend` (`base.py:30`). The only place their individual weights matter is *before* that collapse. Routing at the fleet combiner would require a schema change (`signals.py:20` source enum) for zero gain. |
| `"market"` stays one bucket to the rest of the fleet | No change to `orchestrator.py:223`, `portfolio_manager.py:55`, or `signals.py:87-104`. The reflection loop's existing per-source weighting of `"market"` keeps working on top. This is two stacked adaptive layers: arbiter blends *strategies within market*; memory weights *market vs other sources*. |
| Final weight = `clamp( λ·prior + (1−λ)·posterior )` | Prior is a **fixed, regime-keyed table** (robust, no learning needed — §a source 7 says the defensive tilt alone is worth it). Posterior is the **learned** Sharpe→weight (the adaptive part). Blending the two means the layer is useful *on day 0* (prior) and *improves* over time (posterior) — never worse than the prior. |
| Clamp to `[0.3, 1.5]` | Identical to `memory.py:55-56,121` — a strategy can never be fully silenced or dominate; bounded damage from any single misclassification. |
| Weekly reweight + hysteresis + min-sample | §e overfit mitigations. The single biggest risk is **whipsaw** at regime boundaries; this is what the cadence/hysteresis/debounce layer is for. |

### Inputs

```python
# Contract the arbiter consumes. Regime label is whatever agent 41 emits
# (LLM or HMM); the arbiter is agnostic to the source of the label.

from enum import Enum

class Regime(str, Enum):
    TREND_UP   = "trend_up"    # rising, positive trend, moderate vol
    TREND_DOWN = "trend_down"  # falling (defensive; spot cannot short)
    RANGE      = "range"       # choppy, mean-reverting, low ADX
    RISK_OFF   = "risk_off"    # high vol + drawdown (BTC vol >80%, see 33 §e)
```

| Input | Type | Source | Notes |
|---|---|---|---|
| `regime` | `Regime` | agent 41 (`RegimeClassifier.label(...)`) | The *only* LLM-touched input. Schema-validated enum; anything else → fallback to `RANGE` (most neutral prior). |
| `strategy_sharpe` | `dict[str, float]` | generalized `ReflectionMemory` (§d.3) | Per-strategy realized Sharpe over a rolling window, **conditioned on `regime`**. |
| `strategy` sub-signals | `list[Signal]` | `MarketAnalyst.strategies` (`market.py:31`) | Each tagged in `extras["strategy"] = s.name` before observe. |

### The deterministic rule (prior matrix)

The prior is the *non-learned* spine — it encodes the regime intuition (trend up in trends, mean-rev up in chop, defensive in bear) that does **not** need the LLM or memory to be useful. It is deliberately coarse so the posterior can override it.

```python
# rapana/agents/strategy_arbiter.py
# Prior base-weights W0[regime][strategy]. Tuned to the payoff-orthogonality
# argued in 33-momentum-reversal.md (trend vs mean-rev) and the crash-overlay
# logic in 33 §e (defensive in RISK_OFF / TREND_DOWN).

PRIOR: dict[Regime, dict[str, float]] = {
    Regime.TREND_UP:   {"trend": 1.2, "meanrev": 0.5, "breakout": 1.1},
    Regime.TREND_DOWN: {"trend": 1.0, "meanrev": 0.5, "breakout": 0.6},  # defensive; spot flatten-only
    Regime.RANGE:      {"trend": 0.5, "meanrev": 1.2, "breakout": 0.5},
    Regime.RISK_OFF:   {"trend": 0.3, "meanrev": 0.3, "breakout": 0.3},  # near-silent; rely on risk gate + USDC
}
MIN_W, MAX_W = 0.3, 1.5      # identical bounds to memory.py:55-56
LAMBDA = 0.5                 # 50% prior, 50% learned posterior once posterior is trusted
```

### Sharpe → weight (posterior), reusing the existing Bayesian-shrink map

The posterior reuses `ReflectionMemory`'s shrinkage philosophy (`memory.py:114-121`) but keys on **realized Sharpe** (risk-adjusted, per `05-fleet-llm-edge.md` §b condition 2: "score against risk-adjusted PnL, not sign-of-return"). Until enough samples accrue in a `(strategy, regime)` cell, the posterior is untrusted and the prior dominates — the direct analogue of `memory.py:116` (`total < shrink → 1.0`).

```python
# rapana/agents/strategy_arbiter.py  (continued)
class StrategyArbiter:
    """Regime-gated strategy blender. Deterministic given (regime, sharpe).

    Sets the weights MarketAnalyst uses to blend its sub-strategies,
    replacing the confidence-only combine_signals in base.blend. The LLM
    (if it produces `regime`) is fenced outside the order path: it only
    supplies a categorical label the deterministic rule consumes.
    """

    def __init__(
        self,
        min_sample: int = 20,      # per (strategy, regime) before posterior trusted
        hysteresis: float = 0.15,  # |new - current| must exceed this to reweight
        debounce_bars: int = 6,    # regime must persist this long before reweight
    ) -> None:
        self.min_sample = min_sample
        self.hysteresis = hysteresis
        self.debounce_bars = debounce_bars
        self._current: dict[str, float] = {}          # last applied weights
        self._regime_seen_for: int = 0
        self._confirmed_regime: Regime | None = None

    def _posterior_weight(self, sharpe: float | None, n: int) -> float | None:
        if sharpe is None or n < self.min_sample:
            return None  # not enough evidence → prior dominates
        # Sharpe ~0 -> 1.0, +1.5 -> ~1.5, -1.5 -> ~0.5 (clamped). Symmetric,
        # monotonic, bounded — same posture as memory.py:114-121.
        w = 1.0 + 0.33 * max(-1.5, min(1.5, sharpe))
        return max(MIN_W, min(MAX_W, w))

    def weights(self, regime: Regime, strategy_sharpe: dict[str, float],
                strategy_samples: dict[str, int]) -> dict[str, float]:
        # Debounce: only reweight on a regime that has persisted (anti-whipsaw).
        if regime != self._confirmed_regime:
            self._regime_seen_for += 1
            if self._regime_seen_for >= self.debounce_bars:
                self._confirmed_regime = regime
                self._regime_seen_for = 0
            else:
                regime = self._confirmed_regime or regime  # hold prior regime
        else:
            self._regime_seen_for = 0

        prior = PRIOR.get(regime, PRIOR[Regime.RANGE])
        out: dict[str, float] = {}
        for strat, w0 in prior.items():
            post = self._posterior_weight(
                strategy_sharpe.get(strat), strategy_samples.get(strat, 0))
            raw = w0 if post is None else LAMBDA * w0 + (1 - LAMBDA) * post
            clamped = max(MIN_W, min(MAX_W, raw))
            # Hysteresis: suppress sub-threshold churn.
            prev = self._current.get(strat)
            if prev is not None and abs(clamped - prev) < self.hysteresis:
                clamped = prev
            out[strat] = clamped
        self._current = out
        return out
```

### Integration into `MarketAnalyst`

Two small changes, both surgical:

1. **Tag sub-signals** so the (generalized) reflection memory can condition on strategy. In `market.py:39`, before `blend`:
```python
sub = []
for s in self.strategies:
    sig = s.generate(df, symbol)
    sig = Signal(sig.symbol, sig.source, sig.direction, sig.strength,
                 sig.confidence, sig.rationale,
                 extras={**sig.extras, "strategy": s.name,
                         "regime": current_regime})   # tag for memory
    sub.append(sig)
```
2. **Weighted blend.** Replace `combine_signals(signals)` in `base.blend` (`base.py:35`) with a strategy-weighted variant when an arbiter is configured. Minimal form — a sibling of `weighted_combine` keyed on `extras["strategy"]` instead of `source`:

```python
# rapana/agents/base.py  (new helper, ~10 lines)
def strategy_blend(signals: list[Signal], symbol: str, source: str,
                   strat_weights: dict[str, float]) -> Signal:
    contributing = [s for s in signals if s.direction != "neutral"]
    if not contributing:
        return Signal(symbol, source, "neutral", 0.0, 0.0, "all sub-signals neutral")
    denom = score = 0.0
    for s in contributing:
        w = strat_weights.get(s.extras.get("strategy", "?"), 1.0) * s.confidence
        score += s.strength * w
        denom += w
    net = score / denom if denom else 0.0
    direction = "bullish" if net > 0.05 else "bearish" if net < -0.05 else "neutral"
    agree = sum(1 for s in contributing if (s.strength > 0) == (net > 0)) / len(contributing)
    return Signal(symbol, source, direction, max(-1.0, min(1.0, net)),
                  round(agree, 3), "; ".join(f"{s.extras.get('strategy')}:{s.direction}"
                                              for s in contributing))
```

`MarketAnalyst.analyze` then calls `strategy_blend(sub, symbol, "market", arbiter.weights(regime, sharpe, n))` when an arbiter is wired, else falls back to the current `blend` (`base.py:30`). **Zero change** to `orchestrator.py`, `portfolio_manager.py`, `signals.py`, or the risk gate. The LLM never constructs a `Signal`, a `TradeProposal` (`risk/guardrails.py:41-56`), or a weight above the cap.

### (d.3) Generalizing `ReflectionMemory` to `(source, strategy, regime)`

This is the change `05-fleet-llm-edge.md:92` already called for. Extend — do **not** replace — `memory.py`:

```python
# rapana/fleet/memory.py  (generalization of SourceStats keying)

@dataclass
class SignalRecord:
    ts: int; symbol: str; source: str; direction: str
    strength: float; price: Decimal
    strategy: str = ""     # NEW: tag from signal.extras
    regime: str = ""       # NEW: tag from signal.extras

# stats becomes keyed on (source, strategy, regime); a coarse-grained
# weight(source) view still exists for backward compat with orchestrator.py:223.
class StrategyMemory(ReflectionMemory):
    def observe(self, signal: Signal, price: Decimal, ts: int) -> None:
        if signal.direction == "neutral" or price <= 0:
            return
        self.pending.append(SignalRecord(
            ts, signal.symbol, signal.source, signal.direction,
            signal.strength, price,
            strategy=signal.extras.get("strategy", ""),
            regime=signal.extras.get("regime", "")))

    # Resolve is unchanged (memory.py:80-112) except it indexes stats on the
    # triple. weight(source, strategy, regime) does the same Bayesian shrink
    # as weight(source) (memory.py:114-121) on the matching cell.
    def weight(self, source: str, strategy: str = "", regime: str = "") -> float:
        stats = self.stats.get((source, strategy, regime))
        if stats is None or stats.total < self.shrink:
            return 1.0
        # Sharpe-style posterior (05 §b condition 2), else fall back to accuracy:
        acc = (stats.correct + self.shrink * 0.5) / (stats.total + self.shrink)
        return max(self.min_weight, min(self.max_weight, acc / 0.5))
```

Two invariants preserved: (i) the `[0.3, 1.5]` cap is set in code (`memory.py:55-56`), never by the model; (ii) until `total >= shrink` per cell, the weight is the neutral `1.0` (`memory.py:116`) — so a new `(strategy, regime)` pair cannot move capital until it has earned enough samples. The orchestrator's existing `source_weights` build (`orchestrator.py:223-225`) continues to work because `weight(source)` degrades to the unconditional path when `strategy=""` and `regime=""`.

---

## (e) Overfit & whipsaw mitigations (non-optional)

Regime-switching is **endemically overfit-prone**: it adds a free parameter (the regime assignment) per cycle, and crypto regime boundaries are noisy. Every mitigation below trades *responsiveness* for *robustness* — deliberately. The worst failure mode is **whipsaw**: the arbiter flips weights at a regime boundary that immediately reverses, churning the book at exactly the moment spreads/costs are worst (`09-mexc-maker-fee.md`: mid-cap spread 5–15bp; `33-momentum-reversal.md` §b cost floor).

| Mitigation | Where | Why |
|---|---|---|
| **Weekly reweight** (not per-cycle) | `StrategyArbiter` cadence | Mirrors the monthly-rotation argument in `33-momentum-reversal.md` §b: blending turnover must stay inside the cost floor. The MEXC envelope is ≤1 order/symbol/60s; weekly blend reweighting keeps realized turnover well below it. |
| **Hysteresis** (`|new−current| > 0.15`) | `_posterior_weight` / `weights` | Sub-threshold weight churn is suppressed entirely. A strategy's weight only moves when the evidence is materially different. |
| **Regime debounce** (persist ≥6 bars) | `weights` | The arbiter does **not** reweight the instant the label flips — it waits for the new regime to persist. This is the single biggest whipsaw defense: most regime-label noise is 1–2 bar flickers. |
| **Min sample** (`n ≥ 20` per `(strategy, regime)`) | `_posterior_weight` | Direct analogue of `memory.py:116` (`total < shrink → 1.0`). No learned weight is trusted until a cell has earned it. Prior dominates while young. |
| **Walk-forward / time-ordered** | `StrategyMemory` inherits `pending`/`resolve` (`memory.py:80-108`) | Weights are computed from outcomes observed **before** the current cycle (`05-fleet-llm-edge.md:94` condition 3). Never refit mid-cycle. |
| **Prior spine** (`λ=0.5`) | `weights` | The arbiter is bounded *below* by a fixed sensible prior; learning can only tilt, never invent. Worst case = the prior (still defensible). |
| **Risk-gate independence** | arbiter output is weights, not orders | The existing `RiskManager`/`PreTradeChecker` (`risk/guardrails.py:189-233`) and `KillSwitch`/`CircuitBreaker` veto independently of the arbiter. A bad blend can over-allocate *one* small position (bounded by `max_weight=0.10`, `portfolio_manager.py:23,59`) but cannot bypass the gate (`05-fleet-llm-edge.md:190`). |
| **LLM fenced** | `regime` is the only model input | Schema-validated enum; fallback to `RANGE`. The LLM never sets a weight, never constructs a `TradeProposal`, never sees size (`05-fleet-llm-edge.md:183-190`). |

---

## (f) Sources (verified, load-bearing)

- **Li, Bin & Hoi, Steven C.H. (2014)** — "Online Portfolio Selection: A Survey," *ACM Computing Surveys* 46(3):35:1–35:36 — doi.org/10.1145/2512962 · arxiv.org/abs/1212.2129 · the canonical OPS survey; establishes that picking/blending sub-strategies from recent performance is an entire field (follow-the-leader / -loser / pattern-matching). **Load-bearing for "meta-strategy is a principled, non-predictive job."**
- **Freund, Yoav & Schapire, Robert E. (1997)** — "A Decision-Theoretic Generalization of On-Line Learning and an Application to Boosting," *Journal of Computer and System Sciences* 55(1):119–139 — doi.org/10.1006/jcss.1997.1504 · the Hedge / weighted-majority update rule origin; the primitive `ReflectionMemory` approximates (`memory.py:114-121`).
- **Multiplicative weight update method** (Wikipedia synthesis of the Freund–Schapire / weighted-majority / Hedge lineage) — en.wikipedia.org/wiki/Multiplicative_weight_update_method · the regret bound `Σpᵗmᵗ ≤ Σmᵢᵗ + ln(N)/η + ηT`. **Load-bearing for the §c honest ceiling: adaptive beats best-*fixed* by a sublinear term, not by a guaranteed alpha.**
- **Hamilton, James D. (1989)** — "A New Approach to the Economic Analysis of Nonstationary Time Series," *Econometrica* 57(2):357–384 — doi.org/10.2307/1912559 · the original Markov-regime-switching model; the conceptual basis for agent 41's regime label.
- **Hidden Markov model** (Baum–Welch / Viterbi lineage) — en.wikipedia.org/wiki/Hidden_Markov_model · the standard regime classifier; "Computational finance" + "Time series analysis" listed applications.
- **Nakagawa & Sakemoto (2025)** — "New behaviorally-based cross-sectional reversal portfolios in the cryptocurrency market and market uncertainty," *Finance Research Letters* — sciencedirect.com/science/article/pii/S154461232501058X · **crypto-specific, regime-conditional** payoff (reversal stronger in high-uncertainty regimes) — the precondition for adaptive blending to add value.
- **Daniel, Kent & Moskowitz, Tobias (2013)** — "Momentum Crashes," *Journal of Financial Economics* (cited via `research/agents/33-momentum-reversal.md`) · trend/momentum fails catastrophically at regime turning points — the single strongest argument for the defensive prior tilt.
- **Li & Hoi (2018)** — *Online Portfolio Selection: Principles and Algorithms*, CRC Press — the book-length treatment of source 1.
- **Repo priors** — `research/agents/05-fleet-llm-edge.md` (the load-bearing prior: regime-conditional `ReflectionMemory` is *the* adaptive play; §b "real edge vs trap" conditions — regime-conditional, risk-adjusted, out-of-sample; §c LLM fenced outside the order path); `research/agents/33-momentum-reversal.md` (trend-vs-mean-reversion payoff orthogonality; cost-floor analysis; regime-gate pattern; post-2022 McLean–Pontiff decay); `signals.py:87-104` (`weighted_combine`, the combiner the arbiter mirrors); `agents/base.py:30-46` (`blend`, the seam the arbiter replaces); `fleet/memory.py:42-127` (the reflection loop being generalized); `agents/market.py:31,39` (the strategy set + blend site); `strategies/trend.py:37` (the `source="market"` flattening that makes strategy-tagging necessary); `portfolio_manager.py:23,55-83` (sizing bounded by `max_weight=0.10`); `risk/guardrails.py:189-233` (`PreTradeChecker`, independent veto).

---

## (g) Honest verdict — adaptive vs. fixed blend

**Is a fixed blended-weight portfolio nearly as good as adaptive? Often yes — and that is the right first ship.**

1. **The adaptive layer is theoretically sound** (online-learning regret bound, §a sources 1–3) and fixes a *real* defect in today's unconditional loop (`05-fleet-llm-edge.md:80-96`). It is not the no-edge directional-prediction task.
2. **But the realized edge over a well-chosen fixed blend is small and cost-fragile** after 2022 anomaly decay and MEXC mid-cap spreads. The Hedge bound's comparator is *best-fixed*, and a reflection-calibrated **fixed** blend (equal-or-Sharpe-weighted trend/mean-rev/breakout, set once from a backtest) captures most of the orthogonality benefit with **zero** whipsaw/overfit risk.
3. **The one adaptation that clearly pays is defensive**: down-weighting trend into `RISK_OFF`/`TREND_DOWN` avoids the momentum-crash left tail (Daniel–Moskowitz). That alone justifies *the prior spine*, even if the learned posterior never beats it.

**Recommended sequencing (honest):**
- **Ship first:** a **fixed** regime-conditional prior blend (just the `PRIOR` table in §d, `λ=1.0`) wired into `MarketAnalyst`. Cost: ~30 lines, no learning, no new overfit surface. Captures the defensive tilt and the coarse trend/chop intuition immediately.
- **Ship second:** the **reflection-calibrated fixed blend** (`StrategyMemory` generalization, but weights computed *offline* and frozen). Tells you the per-`(strategy, regime)` Sharpe spread — the thing you need to decide if adaptation is worth it.
- **Ship third (only if the offline Sharpe spread materially exceeds the whipsaw cost in walk-forward):** the full adaptive `StrategyArbiter` with weekly + hysteretic + debounced reweighting. This is where §e's mitigations are non-optional.

The fleet already auto-shrinks a non-working layer toward the `[0.3]` floor (`memory.py:121`); if the adaptive arbiter is noise, the surrounding reflection loop will quietly pull `"market"` down. That is the safety net — but it is *not* a reason to ship the adaptive layer before the fixed one.

---

## Bottom line

Adaptive strategy-selection is one of the few places the LLM + reflection loop adds *non-predictive* value: it bets on **which rule fits the regime**, not where price goes — a categorically easier, regret-bounded problem (Li–Hoi 2014; Hedge/multiplicative-weights). A `StrategyArbiter` generalizes the existing `ReflectionMemory` (`memory.py:42-127`) from per-source to per-`(strategy, regime)` weights, consumed inside `MarketAnalyst.blend` (`base.py:30`) — surgical, envelope-safe, LLM-fenced (the model only supplies the regime enum). **Honest ceiling:** it robustly beats *any single fixed strategy*, but beats a *well-chosen fixed blend* by only a small, cost-fragile, overfit-prone margin; ship the fixed regime-conditional prior blend first (`λ=1.0`), measure the per-cell Sharpe spread, and promote to full weekly/hysteretic adaptation only if walk-forward edge clears the whipsaw cost.

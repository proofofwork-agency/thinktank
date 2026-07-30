# 41 — LLM as market-REGIME classifier (not price predictor): design spec for rapana

**Agent:** 41/60 · **Scope:** `rapana/fleet/orchestrator.py`, `rapana/fleet/memory.py`, `rapana/agents/market.py`, `rapana/agents/portfolio_manager.py`, `rapana/agents/brain.py`, `rapana/feeds/feargreed.py`, `rapana/indicators.py`
**Goal:** Agent-32 named regime classification the *single highest-value defensible LLM use* (`32-llm-papers.md:64`, deferred to Phase-2). This note does the work agent-32 deferred: it surveys the live evidence on whether LLMs classify market *state* better than they predict *returns*, designs a concrete `RegimeClassifierAgent` for rapana that is advisory-only and OUT of the order path, and answers the honest question — *when does this beat a 200d-SMA trend filter?*

All repo citations are `file:line`. All paper citations are arXiv `id` + URL (abstracts fetched live this session, ✅). Load-bearing base facts inherited from prior agents: **LLM price-prediction has no OOS edge** (`RESEARCH-SYNTHESIS.md:11,39`; `32-llm-papers.md:14-16`); **regime-conditional `ReflectionMemory.weight` is the path from curve-fit to real adaptive edge** (`05-fleet-llm-edge.md:92,96`).

---

## (a) Evidence: LLMs classify STATE better than they predict RETURNS

The literature splits cleanly along the *predict-direction vs label-environment* axis. Every paper that asks the LLM "will the price go up" fails OOS (catalogued in `32-llm-papers.md:24-35`). The papers that ask the LLM (or a router built on one) "what *kind* of market is this / which strategy is appropriate" report the durable results:

| Paper (arXiv, ✅ fetched) | Year | Task for the model | Verdict on classification vs prediction |
|---|---|---|---|
| **MM-DREX** `2509.05080` ✅ [arxiv.org/abs/2509.05080](https://arxiv.org/abs/2509.05080) | 2025 | VLM **router** classifies market state from candlesticks + temporal features, **routes** to 4 experts (trend / reversal / breakout / positioning) | *"explicitly decouples market state perception from strategy execution"*; beats 15 baselines (incl. SOTA fin-LLMs + DRL) on return/Sharpe/maxDD across stocks+futures+**crypto**. The durable idea is the **perception/execution decoupling + state→expert routing**, not the per-trade alpha. |
| **DOSS** `2606.03704` ✅ [arxiv.org/abs/2606.03704](https://arxiv.org/abs/2606.03704) (ICLR-2026 FinAI workshop) | 2026 | Select optimization *objective* (return-seeking / loss-averse / risk-adjusted) from *"interpretable statistical summaries of recent returns"*; LLM confined to **accept/override-to-safe-default** oversight | **Cautionary, pro-our-design.** Authors argue latent-regime estimates *"can be noisy or delayed"* and frequent switching *"increases turnover and operational instability."* They (i) formulate selection as **classification over a small fixed set**, (ii) emit a **confidence score**, (iii) gate on confidence with a **fail-safe conservative default**, (iv) keep the LLM as **oversight, never generator**. This is almost exactly the spec in §c. |
| **LabelFusion** `2512.10793` ✅ [arxiv.org/abs/2512.10793](https://arxiv.org/abs/2512.10793) | 2025 | 10-class financial-news classification; zero-shot LLM vs fine-tuned RoBERTa | LLM **zero-shot F1 75.9%**, *"surprisingly competitive"* vs fine-tuned encoder *"until ~80% of training data is available."* Direct evidence that off-the-shelf LLMs are competent **closed-set classifiers** — the regime task is the same shape. |
| **Koki et al. (NHHM)** `2011.03741` ✅ [arxiv.org/abs/2011.03741](https://arxiv.org/abs/2011.03741) | 2020 | 4-state Bayesian HMM on BTC/ETH/XRP — the **non-LLM baseline** an LLM must beat | *"4-state NHHM distinguishes bull, bear and calm regimes"* and has the best 1-step-ahead density forecast. **This is the rule/statistical bar.** Cheap, deterministic, reproducible. |
| **LiveTradeBench** `2511.03628` ✅ (in `32-llm-papers.md:32`) | 2025 | 21 LLMs, 50-day live trading | Prediction fails OOS (best ~6%, peers 70%+ DD) **but** models show *"distinct portfolio styles reflecting risk appetite"* ⇒ the *risk-appetite/environment label* is the signal LLMs leak, even when their directional calls are noise. |
| **Monetary-Policy-Expectations** `2604.08825` ✅ [arxiv.org/abs/2604.08825](https://arxiv.org/abs/2604.08825) | 2026 | LLM classifies 118k central-bank messages hawkish/dovish | LLM-derived *classification* Granger-causes BTC returns and is *"a potent leading macroeconomic indicator."* Classification of narrative ⇒ useful; the same model asked to *predict* BTC returns would revert to the no-edge result. |

**Reading the table.** Three convergent findings:
1. **Closed-set classification is the task LLMs survive.** News-class (LabelFusion), state-router (MM-DREX), objective-selector (DOSS), hawkish/dovish (MPE) — all are *fixed-vocabulary labelling*, all work. None of them ask "what will the price be."
2. **The defensible architecture is perception/execution *decoupled* with a confidence-gated safe default.** DOSS spells this out as a design *principle* ("confidence-aware gating with a fail-safe that overrides low-confidence proposals to a conservative default"); MM-DREX implements it as a router. This maps 1:1 onto rapana's "LLM fenced outside the order path" invariant (`05-fleet-llm-edge.md:183-190`).
3. **The rule-based/statistical baseline is strong and cheap.** A 4-state HMM (Koki) or a 200d-SMA trend filter already captures most of the *directional* regime signal. The LLM's incremental value is on the *non-directional* axes (vol regime, funding-stress regime, narrative regime) where deterministic rules are blind — see §e.

---

## (b) Use case in rapana: regime label → strategy / exposure

Today the fleet runs the **same** strategy blend (Trend+MeanRev+Breakout, `agents/market.py:31`) and the **same** unconditional source weights (`fleet/memory.py:114-121`) in every market. That is the curve-fit trap agent-05 names (`05-fleet-llm-edge.md:80-86`): a strategy/weight that is marginally good on average is often *conditionally* wrong — trend-following bleeds in chop, mean-reversion blows up in trend, the macro feed is signal in one regime and noise in another.

A discrete regime label unblocks two *already-half-built* mechanisms without putting the LLM near an order:

1. **Strategy selection.** `MarketAnalyst.strategies` is already an injectable `list[Strategy]` (`agents/market.py:27,31`). The orchestrator can build a per-regime strategy set at the top of `_process_symbol` (`orchestrator.py:189-192`) *before* analysts run (`orchestrator.py:198`): `{trend→[TrendFollowing,Breakout], range→[MeanReversion], risk-off→[] or size-cut, high-vol→[size-cut + Breakout disabled]}`. The LLM only picks the bucket; the deterministic strategies still generate every `Signal`.
2. **Regime-conditional reflection weighting.** This is agent-05's single highest-upgrade: key `SourceStats` on `(source, regime)` instead of `source` (`fleet/memory.py:23-39,114`), and call `weight(source, regime)` at `orchestrator.py:223-225`. The label converts the unconditional, on-average curve-fit into a *conditional* estimator: *"in regime X the macro feed is signal; in regime Y it is noise."* The clamp `[0.3,1.5]` (`memory.py:55-56`) still bounds the worst case.

Neither path lets the LLM touch `signals`, `weighted_combine` (`signals.py:87-104`), the `TradeProposal` (`portfolio_manager.py:67-81`), or the risk gate. The label is a **categorical hint** consumed by deterministic logic — exactly the "schema-fenced gatekeeper" role the docs mandate (`RESEARCH-SYNTHESIS.md:65`; `PLAN.md:127-130`).

---

## (c) Design spec — `RegimeClassifierAgent`

**Siting:** advisory only. Runs **once per day per scope** (see §d for why not per-cycle), *outside* `_process_symbol`. Output is cached in `FleetState` and read by the orchestrator/PM. It is a sibling of `MacroAnalyst`/`SentimentAnalyst`, NOT a participant in `weighted_combine`.

### Inputs (all numeric, pre-computed by deterministic code — the LLM never reads raw candles)

```python
@dataclass(frozen=True)
class RegimeFeatures:
    # Directional (the part a 200d-SMA already captures — included so the LLM
    # can agree/disagree, not because it has an edge there)
    ret_30d: float          # 30d log return, BTC (market bellwether)
    price_vs_sma200: float  # (price - SMA200)/SMA200, the rule baseline
    # Non-directional (the part rules are blind to — the LLM's actual job)
    real_vol_30d: float     # annualized, from indicators.rolling_volatility
    vol_ratio: float        # 30d vol / 90d vol  (>1 = vol expanding)
    funding_z: float        # MEXC funding rate, z-scored 30d (stress/leverage)
    btc_dominance_delta: float  # 30d change in BTC.D (risk-on/off rotation)
    fear_greed: float       # 0..100 from feeds/feargreed.py
    fear_greed_delta: float # 7d change
```

All seven are scalars the code already has or can compute in 5 lines (`indicators.py:15 sma`, `indicators.py:63 rolling_volatility`, `feeds/feargreed.py:44 score`, funding from `rapana/mexc/client.py`). **Critical anti-hallucination property:** the LLM receives *numbers + their definitions*, never free text or news. It cannot invent a funding rate because it never sees the raw series.

### Model & prompt

- **Model:** cheapest OpenAI-compatible model that obeys JSON schema — `gpt-4o-mini` (already the rapana default, `agents/brain.py:122,135`) or `openai/gpt-4o-mini` via OpenRouter, or a local `llama3.1` via Ollama (`brain.py:127`). Temperature **0.0** (classification, not prose). Reuse `OpenAICompatibleBrain`'s HTTP path (`brain.py:51-95`) — do NOT build a new client.
- **Prompt (schema-fenced, few-shot pinned to the enum):**

```
SYSTEM: You are a closed-set market-regime classifier for a crypto trading
fleet. Output JSON ONLY matching this schema:
  {"regime": "<bull|bear|chop|range|high_vol|risk_off>",
   "confidence": <0.0-1.0>,
   "rule_disagreement": "<none|sma200|vol|funding>",
   "one_line": "<<=120 chars, cite the feature that decided it>"}
"rule_disagreement" = which deterministic signal you are OVERRIDING (else "none").
Do NOT predict price direction. Do NOT mention entries/exits/sizing. If the
features are internally contradictory, pick "range" and confidence <=0.4.
USER (features, as JSON): { ...RegimeFeatures... }
Few-shot: 3 pinned examples covering bull/range/risk_off, each mapping
explicit feature values → label, so the enum is grounded, not free-associated.
```

- **Anti-hallucination measures:** (i) enum is the only legal `regime` value — anything else fails `json.loads` + enum validation and falls back to the **rule baseline**; (ii) `confidence` is requested but the consumer **caps its influence** (§c-consumer) so a confident-wrong call is bounded; (iii) `one_line` is logged for audit, never parsed; (iv) `rule_disagreement` forces the model to name *what* it is overriding — a hallucinated override shows up in the ledger and is reviewable.

### Output & validation (fail-soft to the rule baseline)

```python
REGIMES = frozenset({"bull","bear","chop","range","high_vol","risk_off"})

def classify(self, f: RegimeFeatures) -> RegimeLabel:
    raw = self.brain.reason(self._prompt(f))          # OpenAICompatibleBrain
    try:
        d = json.loads(_extract_json(raw))            # tolerate ```json fences
        regime = d["regime"]
        assert regime in REGIMES
        conf = float(min(max(d.get("confidence",0.5),0.0),1.0))
    except (ValueError, KeyError, AssertionError, TypeError):
        # ANY malformed/unknown output → silent fallback to the SMA rule.
        # A broken LLM can never produce an illegal regime; it produces the rule.
        return self._rule_fallback(f, reason="llm_parse_fail")
    return RegimeLabel(regime, conf, d.get("rule_disagreement","none"), d.get("one_line",""))
```

The `_rule_fallback` is a pure-Python 200d-SMA + vol-percentile classifier — the **same** logic the LLM is supposed to beat. So on every failure mode (timeout, parse error, unknown enum, API down) the system degrades to the deterministic baseline, never to garbage. This is the DOSS *"fail-safe conservative default"* principle (`2606.03704`) made concrete.

### Consumer (orchestrator/PM — deterministic, bounded)

1. **Strategy gating** — at `orchestrator.py:189-192`, pick the strategy list from a `REGIME_STRATS: dict[str, list[Strategy]]`. `risk_off`/`high_vol` remove `Breakout` and cap `MeanReversion`. The LLM never edits a strategy's parameters.
2. **Exposure scalar** — `REGIME_EXPOSURE: dict[str, float] = {bull:1.0, range:0.7, chop:0.4, high_vol:0.3, risk_off:0.0, bear:0.0}` multiplied into `max_weight` at the PM (`portfolio_manager.py:59`). Capped so a "bull" call can lift sizing by at most +0% (never above the existing 0.10 cap, `orchestrator.py:51`), while "risk_off"/"bear" **force flatten** — the only directions where the label has hard power, and only ever *defensively*.
3. **Reflection conditioning** — key `memory.stats` on `(source, regime)` and call `weight(source, current_regime)` at `orchestrator.py:223-225` (the §b upgrade). Bounded by the existing `[0.3,1.5]` clamp.
4. **Audit** — every label + raw model output journaled to the hash-chained ledger (`agents/auditor.py:23-25`) so post-hoc review can score the classifier itself.

**Confidence handling.** `confidence < 0.5` ⇒ ignore the label and use the rule baseline for strategy/exposure, but *still* journal the LLM call (cheap training data for later). This is DOSS's *"confidence-aware gating"* (`2606.03704`) and is the single most important guard: it makes low-confidence LLM noise a no-op rather than a sizing shock.

---

## (d) Cost / latency — run **daily**, not per-cycle

- **Cadence: once per day, market-wide (BTC features), reused across all symbols for 24h.** Regime is a slow-moving latent state; Koki's HMM (`2011.03741`) and MM-DREX's router both operate on daily/temporal features. Per-cycle (1h bars) calls would (i) burn ~24× the cost for ~0 incremental signal, (ii) introduce label-flip churn that DOSS explicitly warns destabilizes turnover (`2606.03704`), and (iii) put a network call inside the order-adjacent loop. Daily, out-of-band, cached — full stop.
- **Cost (gpt-4o-mini, ~$0.15/1M in · $0.60/1M out):** prompt ≈ 700 tokens in, ≈ 60 tokens out ⇒ ~**$0.0001/call**. Daily ⇒ **~$0.004/month**. With local Ollama (`brain.py:127`) it is $0 + ~1–3s latency on consumer GPU/CPU. Either is negligible vs. the rest of the fleet.
- **Latency:** 0.5–2s on hosted mini; the call runs in a daily cron, not in `run_cycle`, so it never blocks execution (`fleet/execution.py`) or the rate limiter (`risk/guardrails.py`).
- **Prompt-design cost-saving:** cache the 3 few-shot examples as a constant; keep the feature payload as compact JSON; never send candle history. The 7-scalar budget above keeps every call under 1k tokens.

---

## (e) Honest comparison: when does this beat a 200d-SMA trend filter?

**Short answer: rarely, on the *directional* axis; meaningfully, on the *volatility/stress* axis; net-positive only with the §c guards.**

1. **For pure bull/bear direction at daily horizon, the SMA wins.** A 200d-SMA filter (price>SMA = bull) is one of the most robust, cheapest, most reproducible signals in finance. Koki's HMM (`2011.03741`) — a *stronger* rule baseline than an SMA — already captures bull/bear/calm with best-case density forecasts. There is **no evidence** that an off-the-shelf LLM classifies binary daily trend more accurately than an SMA; LiveTradeBench (`2511.03628`) shows LLM directional judgment is noise OOS. If the only output were `{bull,bear}`, ship the SMA and skip the LLM.
2. **The LLM earns its cost on axes the SMA cannot see:** (i) **chop vs range** — mean-reversion works in one, bleeds in the other, and the SMA reads both as "sideways"; (ii) **high-vol / risk-off** — funding-z, vol-ratio, and F&G collapses flag de-grossing regimes an SMA ignores; (iii) **regime transitions** — DOSS's whole motivation (`2606.03704`) is that latent-regime estimates lag; the LLM reading multiple weak signals *together* can call a transition a few days earlier than any single threshold, *if* gated on confidence. This is the MM-DREX finding: the router's value is **multi-feature fusion**, not any one feature (`2509.05080`).
3. **Net verdict for rapana.** Build the rule baseline **first** (`_rule_fallback` in §c is non-optional — it IS the v0 product). Add the LLM classifier **second**, daily, advisory, confidence-gated, with its *only* hard power being **defensive** (`risk_off`/`bear`/`high_vol` → flatten/cut). Measure it like agent-05 demands: does conditioning `ReflectionMemory.weight` on the LLM label beat conditioning on the SMA label, walk-forward, OOS? If not after 60–90 days, turn the LLM off — the rule baseline keeps running and nothing is lost. **The design's entire value proposition is that this is a reversible, measurable, bounded experiment — not a load-bearing dependency.**

---

## (f) Sources (all fetched live ✅ this session unless noted)

- ✅ MM-DREX — Chen et al., 2025 — `https://arxiv.org/abs/2509.05080`
- ✅ DOSS (Dynamic Objective Selection w/ Safeguards) — Sakurai et al., 2026 (ICLR-2026 FinAI workshop) — `https://arxiv.org/abs/2606.03704`
- ✅ LabelFusion — Schlee et al., 2025 — `https://arxiv.org/abs/2512.10793`
- ✅ Bayesian HMM crypto regimes — Koki, Leonardos, Piliouras, 2020 — `https://arxiv.org/abs/2011.03741`
- ✅ Monetary Policy Expectations (LLM hawkish/dovish → BTC) — Nicolas et al., 2026 — `https://arxiv.org/abs/2604.08825`
- ✅ LiveTradeBench — `2511.03628` (abstract fetched in `32-llm-papers.md:32`)
- Repo base facts: `RESEARCH-SYNTHESIS.md:11,39,65` · `05-fleet-llm-edge.md:80-96,183-196` · `32-llm-papers.md:24-35,64`

---

## (g) Calibration

**Is:** a defensible, cheap, advisory-only `RegimeClassifierAgent` spec for rapana, grounded in 5 live-fetched papers that converge on *perception/execution decoupling + confidence-gated safe default + closed-set classification*. Concrete plug-in points are pinned to `file:line`; the LLM never enters the order path, never produces an illegal regime (fail-soft to the SMA rule), and its only hard power is **defensive** sizing/flatten. Cost ≈ $0.004/month, runs daily out-of-band.

**Is not:** a claim that the LLM beats an SMA at binary trend. It almost certainly does not (§e1). The label's value is on the *non-directional* axes (chop/range/high-vol/risk-off) where deterministic rules are blind, and only after the rule baseline is shipped first and measured against walk-forward.

**Calibration notes:** (i) MM-DREX (`2509.05080`) and the hawkish/dovish study (`2604.08825`) report *backtested* downstream returns — treated here as non-OOS per the repo's 30–80% decay rule (`RESEARCH-SYNTHESIS.md:38`); only their *architectural* claims (decoupling, classification) are load-bearing. (ii) DOSS (`2606.03704`) is the closest precedent to the §c design and is a workshop paper — its principles are sound but its empirical regime-beats-fixed-objective claim is itself in-sample-class. (iii) I did not find a paper that directly benchmarks "off-the-shelf LLM regime classifier vs 200d-SMA on crypto, OOS" — that gap is the experiment rapana should run; the absence of such a paper is itself evidence the edge is not obvious.

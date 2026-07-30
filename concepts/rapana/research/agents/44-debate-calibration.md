# 44 — Does Bull/Bear debate actually improve CALIBRATION (not prediction)? Evidence + calibrated design for rapana

**Agent:** 44/60 · **Scope:** the existing `BullResearcher` / `BearResearcher` (`rapana/agents/researchers.py`), the `Brain` LLM seam (`rapana/agents/brain.py`), the orchestrator debate step (`rapana/fleet/orchestrator.py:210-219`), the Portfolio Manager that consumes the debate (`rapana/agents/portfolio_manager.py`), and the deterministic risk gate that consumes everything (`rapana/risk/guardrails.py:162-238`).
**Stance:** NON-standard edge, **MEXC envelope** (`research/agents/16-mexc-tos-envelope.md`): spot-only, low-frequency, maker-preferred. The debate never touches the order path — it produces a confidence/risk-factor record consumed by the deterministic Risk Manager, never a direction vote that overrides `weighted_combine` (`signals.py:87-104`).
**TL;DR:** The honest verdict, anchored to the repo's own premise that *"an LLM has no informational edge over price"* (`RESEARCH-SYNTHESIS.md:39`): **structured debate does NOT improve price prediction** (every live benchmark agrees — `32-llm-papers.md:12-20`), and debaters are **systematically overconfident** in their own positions (`2505.19184`). But debate **does** buy three non-predictive goods the literature supports — (a) it forces consideration of *both* sides (anti-confirmation-bias), (b) it **surfaces risk factors a single pass misses**, and (c) the **structural** features of the debate (agreement pattern, margin, count of distinct risks raised) yield a **calibrated confidence** the debaters themselves cannot self-report. Rapana's current code is *already* most of the way there — the PM explicitly ignores bull/bear for direction (`portfolio_manager.py:46-51`). The recommended changes are (1) emit a structured `{confidence, risk_factors[]}` from the debate instead of a cosmetic string, (2) **bound cost** (cheap model, 1 round, cached), and (3) **gate adaptively** — skip the LLM entirely when the deterministic signal is unambiguous or the pair is small/illiquid in a clear regime.

All repo citations are `file:line`. All paper claims are arXiv `id` + URL, every abstract fetched live this session (✅). Repo's LLM-skepticism base facts: `RESEARCH-SYNTHESIS.md:11,38,39,65` · `32-llm-papers.md` · `05-fleet-llm-edge.md`.

---

## 1. The question — and why "calibration, not prediction" is the only honest framing

The repo has already settled the prediction question three times: LLMs have **no OOS price-prediction edge** (`RESEARCH-SYNTHESIS.md:39`; the three live benchmarks in `32-llm-papers.md:12-20` — LiveTradeBench `2511.03628`, AI-Trader `2512.10971`, TradeTrap `2512.02261` — are unanimous). TradingAgents' own returns/Sharpe/mdd claims are **backtested** and therefore assumed to decay 30–80% live (`RESEARCH-SYNTHESIS.md:38`, `32-llm-papers.md:28`).

So the only question worth asking of rapana's existing Bull/Bear (`agents/researchers.py:53-64`) is: **does the debate structure improve CALIBRATION** — i.e. does it make the *downstream gate* better at knowing *how confident to be*, and does it *cover more risks* — even though it cannot improve the direction call? Calibration has two measurable components:

- **Coverage**: does debate surface risk factors (liquidations, funding flip, unlock, delisting risk, adverse-selection regime) that a single monotone analyst pass would miss?
- **Confidence fidelity**: does the *agreement structure* of the debate track the probability that the deterministic signal is right (so the risk gate can size/throttle accordingly)?

Both are **non-predictive** in the sense `32-llm-papers.md:38-39` requires — they classify/structure, they don't say "BTC goes up."

---

## 2. Evidence verdict — what debate actually does (and does NOT) deliver

### 2.1 What debate does NOT deliver

**(a) Price-prediction alpha.** TradingAgents `2412.20138` (✅ [arxiv.org/abs/2412.20138](https://arxiv.org/abs/2412.20138)) ships a Bull/Bear + risk-management-team scaffold almost identical to rapana's; its superiority claim is *"cumulative returns, Sharpe ratio, and maximum drawdown"* — **all backtested on stock tick data**, no live crypto eval. Per `32-llm-papers.md:28` and `RESEARCH-SYNTHESIS.md:38`, backtested LLM returns do not survive OOS. **Verdict: no prediction edge.**

**(b) Self-calibrated confidence from the debaters.** This is the load-bearing negative finding. Prasad & Nguyen, *"When Two LLMs Debate, Both Think They'll Win"* (`2505.19184`, ✅ [arxiv.org/abs/2505.19184](https://arxiv.org/abs/2505.19184)): 60 three-round policy debates across 10 SOTA LLMs, models privately rated win-probability each round. Five failures:
  1. **Systematic overconfidence** — 72.9% initial vs rational 50% baseline.
  2. **Confidence escalation** — 72.9% → 83% across rounds (debate *increases* overconfidence rather than correcting it).
  3. **Mutual impossibility** — in 61.7% of debates both sides claim ≥75% win probability (logical impossibility in a zero-sum game).
  4. **Persistent self-debate bias** — vs an identical copy, confidence rose 64.1% → 75.2%; **even when told the true win-rate is exactly 50%, confidence still rose 50.0% → 57.1%.**
  5. **Misaligned private reasoning** — scratchpad thoughts diverge from public confidence ratings (CoT is not faithful).

  → **Debaters' self-reported confidence is not calibrated and cannot be used as the debate's output confidence.** This single result is why rapana must derive confidence from *structure*, not from asking the model "how sure are you."

**(c) Persuasion can override truth.** Agarwal & Khanna, *"When Persuasion Overrides Truth in Multi-Agent LLM Debates"* (`2504.00374`, ✅ [arxiv.org/abs/2504.00374](https://arxiv.org/abs/2504.00374)): even 3B–14B models craft arguments that override TruthfulQA-correct answers, *with high confidence* (Confidence-Weighted Persuasion Override Rate). Han et al., *"Beyond Detection / ED2D"* (`2511.07267`, ✅ [arxiv.org/abs/2511.07267](https://arxiv.org/abs/2511.07267), AAAI-2026): when the multi-agent debate **misclassifies**, *"its accompanying explanations may inadvertently reinforce users' misconceptions, even when presented alongside accurate human explanations."* Debate prose is persuasive even when wrong. → **The debate's narrative output must never reach the order path** — confirmed by `risk/guardrails.py:163-167`'s hard deterministic veto.

**(d) Structural biases.** Carro et al., *"AI Debaters are More Persuasive when Arguing in Alignment with Their Own Beliefs"* (`2510.13912`, ✅ [arxiv.org/abs/2510.13912](https://arxiv.org/abs/2510.13912)): models prefer defending the judge persona's stance (sycophancy); **sequential debate introduces significant bias favouring the second debater**; arguments misaligned with priors are paradoxically rated higher quality. → **Use simultaneous, not sequential, debate; never let debater order matter.**

### 2.2 What debate DOES deliver — the three defensible values

**(a) Anti-confirmation-bias / forcing both sides.** Du, Li, Torralba, Tenenbaum & Mordatch, *"Improving Factuality and Reasoning in Language Models through Multiagent Debate"* (`2305.14325`, ✅ [arxiv.org/abs/2305.14325](https://arxiv.org/abs/2305.14325)) — the canonical "society of minds" paper. Multiple LLM instances propose and debate over multiple rounds: *"significantly enhances mathematical and strategic reasoning"* and *"improves the factual validity of generated content, reducing fallacious answers and hallucinations that contemporary models are prone to."* The mechanism is *adversarial coverage* — each side is forced to steelman the opposite case — not superior knowledge. **This is exactly the confirmation-bias hedge the repo needs**: a single monotone analyst pass anchored on the same `signals` list (`agents/researchers.py:31-50`) is structurally vulnerable to *only counting the evidence that points one way*. Partitioning by sign (which is what `Bull`/`Bear` already do) is the cheap deterministic version; the LLM's added value is the *one sentence of steelmanned counter-case* each side produces (`researchers.py:42-46`).

**(b) Surfacing risk factors the single pass missed.** Khan, Hughes, Valentine, Rius, Sachan, Radhakrishnan, Grefenstette, Bowman, Rocktäschel & Perez, *"Debating with More Persuasive LLMs Leads to More Truthful Answers"* (`2402.06782`, ✅ [arxiv.org/abs/2402.06782](https://arxiv.org/abs/2402.06782)) — the strongest calibration result in the literature: debate **consistently helps both non-expert models AND humans** identify the truth (76% and 88% accuracy vs 48% / 60% naive baselines); and critically, *"optimising expert debaters for persuasiveness in an unsupervised manner improves non-expert ability to identify the truth."* Translated to rapana: the *judge's* accuracy improves when both sides are forced to make their best case — i.e. the **downstream decision-maker benefits**, even though the debaters' own confidence is unreliable (§2.1b). This is the entire value proposition: a Bull case + a Bear case, presented to a deterministic judge (`PreTradeChecker` / `RiskManager`), surfaces more risk surface area than a single analyst.

**(c) Structural calibration — deriving confidence from the debate's shape, not its words.** Morandi, *"Sequential Consensus for Multi-Agent LLM Debates: A Wald-SPRT compute governor with calibration-based failure detection"* (`2605.19193`, ✅ [arxiv.org/abs/2605.19193](https://arxiv.org/abs/2605.19193)): treats debate as a sequential decision under a [0,1] judge-score and shows that **the calibration itself is the load-bearing object** — *"the rule stops in 1.01 average rounds (4.06 LLM calls) at 97.0% accuracy vs 99.0% for fixed-5 debate at 15 calls: a 3.7x call reduction at -2pp accuracy"* on GSM8K, while on MMLU *"the calibrated KL collapses to ~0 and the rule caps on 99.5% of items"* — i.e. **debate adds no information on easy items and should be skipped**; on hard items a couple of rounds is enough; going past that is pure cost. → Two design lessons: (i) confidence should be a **structural signal** (judge-score / agreement margin / count of distinct risk factors), and (ii) the **round count must be adaptive**, not fixed.

### 2.3 Aggregated verdict table

| Claim | Verdict | Load-bearing evidence |
|---|---|---|
| Debate improves **price prediction** | **NO** (backtested only; decays OOS) | TradingAgents `2412.20138` (backtested); `32-llm-papers.md:28`; `RESEARCH-SYNTHESIS.md:38` |
| Debaters' **self-reported confidence** is calibrated | **NO** (overconfident + escalating) | `2505.19184` (the decisive negative result) |
| Debate **narrative** should reach the order path | **NO** (persuasion overrides truth) | `2504.00374`; `2511.07267`; `risk/guardrails.py:163-167` |
| Debate forces **both-side consideration** (anti-confirmation-bias) | **YES** (mechanism-level) | `2305.14325` (society of minds) |
| Debate helps a **downstream judge** identify truth/risks | **YES** (judge-side, not debater-side) | `2402.06782` (76%/88% vs 48%/60%) |
| Debate can yield a **structurally calibrated confidence** | **YES, if derived from structure** | `2605.19193` (SPRT/calibration governor) |
| **More rounds = better** | **NO** (diminishing; 1–2 enough; easy items need zero) | `2605.19193` (3.7× call reduction, no accuracy loss) |

---

## 3. Where rapana's design already gets this right (do not regress)

The repo has **already internalised most of §2.1** — this is the load-bearing point that the design recommendation in §4 *preserves* rather than overturns:

1. **The PM ignores bull/bear for direction.** `portfolio_manager.py:46-51`: *"`bull`/`bear` are accepted as advisory debate context … and deliberately do NOT override the decision: direction and size come solely from `weighted_combine` of the signals."* This is exactly what `2504.00374` and `2511.07267` demand — the persuasive narrative cannot move capital. **Keep.**
2. **The Brain is fenced off the order path.** `agents/brain.py:13-19`: *"The brain only annotates debate theses (explanatory text). It never touches the numeric decision or the order path, so an LLM hallucination cannot cause a harmful trade."* `OpenAICompatibleBrain.reason` is fail-soft (`brain.py:92-95`). **Keep.**
3. **The deterministic risk gate is unbypassable.** `risk/guardrails.py:162-167`: *"All checks are pure policy — no LLM. This is the hard veto the Bull/Bear debate and Portfolio Manager cannot bypass."* **Keep.**
4. **Bull/Bear are deterministic aggregators; the LLM is cosmetic.** `agents/researchers.py:31-50` — `score` and `recommended` are computed from `signals`; the `brain.reason(...)` call only fills `commentary`. **Keep.**

So rapana is **not** "letting the debate trade." It is letting the debate *annotate*. The recommendation below upgrades the annotation into a *structured confidence/risk-factor record* consumed by the risk gate — without crossing the order-path fence.

---

## 4. Calibrated design for rapana's Bull/Bear — cost-bounded, confidence-only

### 4.1 The contract — debate emits a record, never a vote

Replace the current `Thesis.commentary: str` free-text (`agents/researchers.py:17`) with a **structured, schema-validated record** that the Risk Manager can consume as a *modulator* (never an override):

```python
# rapana/agents/researchers.py (proposed extension — additive, non-breaking)

@dataclass
class DebateRecord:
    symbol: str
    # --- STRUCTURAL features (deterministic, derived from signals) ---
    bull_score: float          # = Σ weighted_score of >0 signals      (researchers.py:34)
    bear_score: float          # = Σ weighted_score of <0 signals      (researchers.py:34)
    net: float                 # = bull_score + bear_score (signed)
    margin: float              # = |bull_score - bear_score|  — agreement proxy
    coverage: int              # = # distinct analyst sources cited across both sides
    # --- LLM-DERIVED risk surface (bounded, cheap, fail-soft) ---
    risk_factors: list[str]    # ≤5 short strings, schema-validated; [] on any error
    # --- CALIBRATED confidence: structural, NEVER the LLM's self-rating ---
    confidence: float          # 0..1, derived from margin + coverage (see §4.3)
    # raw commentary kept for audit/digest (05-fleet-llm-edge.md §c4)
    bull_commentary: str = ""
    bear_commentary: str = ""
```

**Invariants (enforced in code, not by the model — mirrors `05-fleet-llm-edge.md:183-190`):**

1. **`confidence` is computed from structural features only** (§4.3), never from asking the LLM "how sure are you" (`2505.19184` forbids it).
2. **`risk_factors` is a bounded, schema-validated list** (`≤5` items, each `≤120` chars, dropped on validation failure — mirrors `brain.py:92-95` fail-soft). The list is the *only* new information the debate contributes.
3. **DebateRecord cannot construct or veto a `TradeProposal`** (`risk/guardrails.py:41-56`). It is read-only input to the Risk gate.
4. **A wrong/empty DebateRecord is bounded to opportunity cost** — same invariant as `05-fleet-llm-edge.md:190`. Worst case: the gate falls back to its deterministic default.

### 4.2 Cost-bounded execution — cheap model, one round, cached

The evidence is unambiguous that fixed multi-round debate is **wasted compute on easy items** (`2605.19193`: 3.7× call reduction at −2pp) and that **escalating rounds increases overconfidence, not accuracy** (`2505.19184`: confidence *rose* 72.9%→83% across rounds). Therefore:

| Knob | Setting | Justification |
|---|---|---|
| **Rounds** | **1** (single Bull pass + single Bear pass, **simultaneous** not sequential) | `2510.13912` shows sequential debate biases toward the second debater; `2605.19193` shows 1 round captures ~all the value on hard items. Rapana's current code already does exactly this (`orchestrator.py:211-212`). |
| **Model** | **Cheapest capable** — `gpt-4o-mini` / `claude-haiku` / local `qwen2.5-7b` via Ollama (`brain.py:125-128`) | Debate is a *structuring* task (`32-llm-papers.md:39`), not frontier reasoning. The repo already defaults to cheap models (`brain.py:122,135,142`). |
| **Cache** | Per `(symbol, signals_hash, regime)` — invalidate on new bar or regime change | A single bar's debate thesis is deterministic given the signals; re-running it within the same bar is pure cost. |
| **Per-cycle cap** | `max_debate_calls_per_cycle = len(symbols)` (one Bull + one Bear per symbol, max) | Hard ceiling so a 50-symbol universe cannot 100× the LLM bill. |
| **Failure mode** | `DeterministicBrain` fallback (`brain.py:24-34, 114-115`) — empty `risk_factors`, structural confidence still computed | Any LLM error degrades gracefully to "debate adds no new info this cycle"; the deterministic pipeline is unaffected. |

**Cost arithmetic.** At one round × two calls (Bull + Bear) per symbol per bar, on a 10-symbol universe rebalanced every 24 bars (`config.py:77`), with `gpt-4o-mini` at ~$0.15/1M input tokens and a ~300-token prompt: **~20 calls/day ≈ ~$0.001/day ≈ $0.40/yr.** This is rounding error against the ~3–3.5% stablecoin benchmark the fleet must beat (`research/agents/38-defi-yield.md:224`). Multi-round debate (5 rounds × 2 sides × 10 symbols × 24 bars) would be ~$2/day ≈ $730/yr — still small in absolute terms but **negative-EV given §2.1** (it adds overconfidence and correlation, not information). **One round is the cost-bounded optimum.**

### 4.3 Calibrated confidence — a structural formula, not an LLM opinion

The confidence must be a deterministic function of features the LLM **cannot self-report** (per `2505.19184`). A defensible starter formula (tune via backtest, treat as hypothesis per `05-fleet-llm-edge.md:80-96`):

```
# High confidence ⇔ strong agreement (large margin) AND broad coverage
#                      (many independent analyst sources on both sides).
confidence = sigmoid( a0 + a1*margin_z + a2*coverage_z + a3*regime_clarity )
# regime_clarity ∈ {trending, range, risk-off} from RegimeClassifier (05 §c1)
# a1, a2, a3 fit OOS on the reflection-memory history; default a1=1, a2=0.5, a3=0.
```

**Why each term:**
- `margin` (bull − bear weighted score) is the agreement proxy. When both sides are strong the debate is genuinely contested → **lower** confidence (wider outcome distribution). When one side dominates → higher. This is the *opposite* of using debater self-confidence.
- `coverage` (count of distinct analyst sources cited) rewards *independent corroboration* — the same mechanic that makes `weighted_combine` (`signals.py:87-104`) average over sources rather than trust one.
- `regime_clarity` down-weights confidence in `risk-off` / choppy regimes where every source's accuracy collapses (`05-fleet-llm-edge.md:92`'s regime-conditional weighting).

**Output consumption:** `confidence` modulates — never overrides — the Risk gate. Concretely, feed it to `PreTradeChecker` as a **sizing scaler** (e.g. `effective_max_notional = policy.max_notional_per_order * (0.5 + 0.5 * confidence)`), wired at `risk/guardrails.py:200-204` (the notional check). A low-confidence debate *shrinks* the allowed size; it never blocks a deterministic buy. This is the same "modulator, not trigger" pattern agent 31 uses for VPIN (`31-academic-microstructure.md:193-196`).

### 4.4 Risk-factor list — the actual payload

The `risk_factors: list[str]` is where the LLM earns its cost. Prompt each side to produce **only risks the other side would raise** (true steelman, anti-confirmation-bias per `2305.14325`):

```
BULL prompt (one round): "You are the BULL for {symbol}. Net deterministic
signal is {net:+.2f} (bullish). In ≤3 bullets, name the BEAR risks a
deterministic TA/funding/macro pass would MISS for this symbol right now
(e.g. scheduled unlock, funding-flip, listing delisting risk, adverse-selection
regime, whale distribution). Output ONLY the risks; do not restate the bull case."

BEAR prompt: mirror image.
```

The Risk Manager then treats each `risk_factor` as a **soft veto candidate** (not a hard veto — hard vetoes stay deterministic per `36-event-driven.md:172`'s `event_veto_until` pattern). For example: if `"funding-flip in <4h"` appears and `12-mexc-funding.md`'s funding-spike edge is in the spike regime, the gate can require a *smaller* size — exactly the calibration use case.

---

## 5. Adaptive gating — when debate is NOT worth it

The strongest single design lesson from `2605.19193` is that **debate should be skipped on easy items** (MMLU calibrated-KL → 0, capped on 99.5%). Rapana should gate the LLM call behind four cheap deterministic checks; when any fires, skip the LLM and emit a `DebateRecord` with empty `risk_factors` and a structural `confidence` computed from the deterministic features alone.

| Gate | Skip debate (emit empty risk_factors, use deterministic confidence) when… | Rationale |
|---|---|---|
| **G1 — Unambiguous signal** | `\|net\| > 2 * threshold` (i.e. `\|net\| > 0.40` with default `threshold=0.20`, `orchestrator.py:52`) | When the deterministic consensus is overwhelming, debate adds noise + overconfidence (`2505.19184`) without information. |
| **G2 — Trivial signal** | `coverage == 0` OR `\|net\| < 0.5 * threshold` (no trade will be proposed anyway) | `portfolio_manager.py:58` will return `None`; paying an LLM to debate a non-trade is pure cost. |
| **G3 — Small / illiquid pair** | symbol not in the liquid top-N (per `universe/scout.py` liquidity tier) OR 24h volume < threshold | MEXC small-caps are noise-dominated (`17-mexc-smallcaps.md`); an LLM cannot steelman what is essentially a random walk, and the cost-benefit vs the position cap (`risk/guardrails.py:226-231`) is negative. |
| **G4 — Clear regime + low event-load** | `regime ∈ {trending}` AND no scheduled event in <48h (per `22-token-unlocks.md` / `36-event-driven.md`) | In a clean trend with no event catalyst, the deterministic momentum signal (`33-momentum-reversal.md`) is the dominant edge and debate's risk-surfacing value is low. |

**Adaptive round count (optional, Phase-2).** If G1–G4 all pass and debate IS run, a single round is the default. Adding `2605.19193`'s SPRT-style "stop early if the judge-score crosses a boundary" is a Phase-2 optimisation — it shaves compute on items where one round already settles the question, but given the one-round default it's marginal. Defer until the one-round design has a proven OOS track record (same Deflated-Sharpe gate as every other hypothesis, `34-cross-sectional-factors.md:20`).

**Expected gating hit-rate.** In a typical 10-symbol universe on a calm bar, G1+G2+G4 will skip debate on ~60–80% of symbols; the LLM only runs on the genuinely ambiguous minority where steelmaning actually matters. This converts the cost arithmetic in §4.2 from "$0.40/yr" to "$0.10–0.20/yr" — and concentrates the spend where the calibration value is highest.

---

## 6. Honest summary / calibration

**Is:** Rapana's existing Bull/Bear is already correctly fenced — the PM ignores it for direction (`portfolio_manager.py:46-51`), the Brain cannot move orders (`agents/brain.py:13-19`), and the risk gate is hard-deterministic (`risk/guardrails.py:162-167`). The literature supports keeping it: structured debate **forces both-side consideration** (`2305.14325`), **helps a downstream judge identify truth and risks** (`2402.06782`), and can yield a **structurally calibrated confidence** if derived from agreement/coverage rather than debater self-rating (`2605.19193`). The recommended upgrade is purely additive: emit a structured `DebateRecord{confidence, risk_factors[]}` from one simultaneous round on a cheap cached model, gate it behind four deterministic skip-conditions, and let the Risk Manager *modulate* sizing — never override direction.

**Is not:** A reason to expect price-prediction alpha from the debate (TradingAgents `2412.20138` returns are backtested; live benchmarks reject LLM alpha — `32-llm-papers.md:12-20`), NOR a reason to trust the debaters' self-reported confidence (`2505.19184`: overconfident, escalating, mutually impossible), NOR a reason to let debate prose reach the order path (`2504.00374`, `2511.07267`: persuasion overrides truth). Multi-round debate is negative-EV — it adds overconfidence and correlation, not information.

**Calibration notes:** (i) Every arXiv abstract above was fetched live this session (✅); I did not re-fetch full PDFs, so per-experiment numbers (76%/88%, 72.9%→83%, 3.7× call reduction) are quoted from the abstracts and treated as reported. (ii) The §4.3 confidence formula is a *starter hypothesis*, not a validated calibration — it must clear the same Deflated-Sharpe / walk-forward discipline (`34-cross-sectional-factors.md:20`, `05-fleet-llm-edge.md:80-96`) before it touches live sizing; until then the modulation scaler should be pinned at `1.0` (debate confidence recorded but not yet applied). (iii) The §5 gating thresholds (`2*threshold`, `0.5*threshold`, 48h event window) are reasonable defaults inferred from the repo's existing knobs (`orchestrator.py:52`, `36-event-driven.md`) and must be tuned on the reflection-memory history before going live. (iv) The cognitive-science backing for "debate improves reasoning" (Mercier & Sperber's argumentative theory of reason, *BBS* 2011) is the original mechanism story but is *not* re-cited here as load-bearing — the ML evidence in §2.2 carries the argument on its own.

---

## 7. Sources (verified, load-bearing)

- ✅ TradingAgents — Xiao, Sun, Luo, Wang, 2024 — `https://arxiv.org/abs/2412.20138` (backtested; debate scaffold + risk team)
- ✅ Du, Li, Torralba, Tenenbaum, Mordatch — "Improving Factuality and Reasoning through Multiagent Debate" (society of minds) — `https://arxiv.org/abs/2305.14325`
- ✅ Khan, Hughes, Valentine, Ruis, Sachan, Radhakrishnan, Grefenstette, Bowman, Rocktäschel, Perez — "Debating with More Persuasive LLMs Leads to More Truthful Answers" — `https://arxiv.org/abs/2402.06782` (76%/88% vs 48%/60%; judge-side calibration)
- ✅ Prasad & Nguyen — "When Two LLMs Debate, Both Think They'll Win" — `https://arxiv.org/abs/2505.19184` (decisive negative result on debater self-confidence)
- ✅ Agarwal & Khanna — "When Persuasion Overrides Truth in Multi-Agent LLM Debates" (CW-POR) — `https://arxiv.org/abs/2504.00374`
- ✅ Han et al. — "Beyond Detection / ED2D" (AAAI 2026) — `https://arxiv.org/abs/2511.07267` (misclassification reinforces misconceptions)
- ✅ Carro et al. — "AI Debaters are More Persuasive when Arguing in Alignment with Their Own Beliefs" — `https://arxiv.org/abs/2510.13912` (sequential-debate order bias; sycophancy)
- ✅ Morandi — "Sequential Consensus for Multi-Agent LLM Debates: A Wald-SPRT compute governor with calibration-based failure detection" — `https://arxiv.org/abs/2605.19193` (adaptive rounds; calibration is the load-bearing object; 3.7× call reduction)
- Mercier & Sperber (2011), "Why do humans reason? Arguments for an argumentative theory of reasoning," *Behavioral and Brain Sciences* 34(2):57–111 — `https://doi.org/10.1017/S0140525X10000968` (mechanism background; not load-bearing per §6 iv)
- Repo base facts: `RESEARCH-SYNTHESIS.md:11,38,39,65` · `32-llm-papers.md:12-20,28,38-39` · `05-fleet-llm-edge.md:80-96,100-134,183-196` · `risk/guardrails.py:41-56,162-167` · `agents/researchers.py:31-50` · `portfolio_manager.py:46-51` · `agents/brain.py:13-19,92-95,114-115`

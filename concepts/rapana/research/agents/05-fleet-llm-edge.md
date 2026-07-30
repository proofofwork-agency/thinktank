# 05 — Fleet decision pipeline & where an LLM is *actually* worth it

**Agent:** 5/60 · **Scope:** `rapana/fleet/orchestrator.py`, `rapana/fleet/portfolio.py`, `rapana/agents/`, `rapana/fleet/memory.py`, `rapana/signals.py`
**Goal:** Pin down the one place LLMs add genuine value once we accept the docs' own premise — "an LLM has **no informational edge over price**; its 'reasoning' is post-hoc narrative" (`RESEARCH-SYNTHESIS.md:39`).

All citations are `file:line`.

---

## (a) Decision-pipeline map

`Fleet.run_cycle()` (`orchestrator.py:121`) loops once per cycle and dispatches `_process_symbol(symbol)` per held symbol (`orchestrator.py:139-140`). The pipeline inside `_process_symbol` is exactly the 5-stage chain advertised in the class docstring (`orchestrator.py:61-68`):

```
   DataProvider (price + history)            orchestrator.py:190-192
            │
            ▼
 1) ANALYSTS  ──────────────►  Signal[]      orchestrator.py:198-208
    MarketAnalyst (TA blend)                  agents/market.py:35-40
    SentimentAnalyst (fn-injected)           agents/sentiment.py:26-31
    MacroAnalyst   (fn-injected)             agents/macro.py:26-31
            │ each Signal: source, direction, strength(-1..1),
            │              confidence(0..1), rationale          signals.py:17-25
            │
            ▼  (signals also fed to memory.observe for later scoring)
 2) BULL / BEAR DEBATE  ─────►  Thesis{}     orchestrator.py:210-219
    BullResearcher.argue  want_positive=True  agents/researchers.py:53-57
    BearResearcher.argue  want_positive=False agents/researchers.py:60-64
    score = Σ weighted_score of agreeing signals   researchers.py:31-50
    (Bull/Bear are ADVISORY — recorded but never move the order directly;
     see PM docstring researchers.py:21-26 + portfolio_manager.py:46-51)
            │
            ▼
 3) PORTFOLIO MANAGER ──────►  TradeProposal?  orchestrator.py:221-235
    net = weighted_combine(signals, source_weights)   signals.py:87-104
          ↑ confidence-weighted, AND multiplied by each source's
            learned accuracy from ReflectionMemory      signals.py:100-103
    if net > +threshold → buy sized by min(max_weight, |net|) * equity
    if net < -threshold → sell to flatten
    else                → None (hold)               portfolio_manager.py:55-83
            │
            ▼
 4) RISK GATE (deterministic veto)           orchestrator.py:237-252
    RiskManager(checker).review(proposal)    agents/risk_manager.py:19-22
    PreTradeChecker.check(): kill-switch, circuit-breaker,
      rate-limiter, notional cap, sanity-price-band,
      total-exposure cap, per-symbol cap      risk/guardrails.py:189-233
    LLM CANNOT bypass — comment at guardrails.py:163-167
            │  approved?
            ▼
 5) EXECUTION  ─────────────►  Fill          orchestrator.py:254-268
    ExecutionTrader.execute → Paper/Live Executor  fleet/execution.py:116-135
    fill → PaperPortfolio.apply_fill → realized PnL  portfolio.py:31-53
    realized PnL → CircuitBreaker.record_realized   orchestrator.py:262-268
            │
            ▼
   ComplianceAuditor.journals every stage to hash-chained ledger
   (signal, debate, trade_proposal, risk_decision, risk_veto, fill)
   agents/auditor.py:23-25, orchestrator.py:201-264
```

**The combining logic that actually decides** is two functions and nothing else:

- `weighted_combine(signals, source_weights)` — `signals.py:87-104`. Neutral signals are excluded from both numerator and denominator (`signals.py:93-95`). Each contributing signal's weight is `source_weights[source] * confidence`; the score is `Σ(strength·w) / Σ w` (`signals.py:98-104`).
- `PortfolioManager.decide` then maps that score to a side/qty against `±threshold` (`portfolio_manager.py:55-83`).

The Bull/Bear debate is **explicitly advisory**: the PM docstring says *"narrative research informs humans; deterministic math moves capital"* (`portfolio_manager.py:46-51`). So the LLM-injected prose in `researchers.py:40-46` cannot, by construction, change a trade. That is the load-bearing safety design the rest of this document builds on.

---

## (b) Reflection loop — real edge vs curve-fitting trap

The reflection loop is `ReflectionMemory` in `rapana/fleet/memory.py:42-127`, surfaced into the PM via `source_weights` (`orchestrator.py:222-229`, `portfolio_manager.py:55`). Mechanics:

1. **Observe.** Every non-neutral signal is appended with its price and timestamp (`memory.py:73-78`, called from `orchestrator.py:208`).
2. **Resolve.** After `horizon_ms` (default 24h, `memory.py:53-54`), the outcome is `(price_now - price_then)/price_then`; "correct" = sign matches the predicted direction; the signed magnitude feeds `profit_sum` (`memory.py:80-108`).
3. **Weight.** A Bayesian-shrunk accuracy maps to a weight clamped to `[0.3, 1.5]`, with `shrink=5.0` pseudocounts and a flat `1.0` until `total >= shrink` (`memory.py:114-121`).
4. **Apply.** `weighted_combine` uses those weights *next* cycle (`signals.py:100-103`).

### Why this is *not* inherently a real edge

The reflection loop is, by itself, an **in-sample rule fitted on its own history**. Three failure modes the docs warn about directly:

- "Backtest→live decay is the rule (30–80% edge decay reported); overfitting is endemic" (`RESEARCH-SYNTHESIS.md:38`).
- The scoring metric — *did price go up/down over 24h after a bullish call* — is exactly the task the docs say LLMs and most analysts fail at (`RESEARCH-SYNTHESIS.md:39`). A source that lucked into 60% hit-rate over `shrink=5` samples gets a 1.2× multiplier; with five sources and a 24h horizon, you accumulate ~5 samples/day — well within noise.
- The clamp `[0.3, 1.5]` (`memory.py:55-56, 121`) bounds the damage but also bounds the upside: a genuinely good source can only ever count 3× more than a bad one (1.5/0.5).

### How it *could* become a real (adaptive) edge

The adaptive-weighting framing is defensible **only if three structural conditions hold**, and the code already half-supports each:

1. **Classify, don't predict direction.** Real edge comes from learning *"in regime X, the macro feed is signal; in regime Y, it is noise"* — i.e. **conditional** accuracy, not marginal. Today `SourceStats` is unconditional (`memory.py:23-39`). Making `stats: dict[tuple[source, regime], SourceStats]` and keying `weight(source)` on the *current* regime (`memory.py:114`) converts a curve-fit into a regime-conditional estimator. Combined with an LLM regime classifier (§c below), this is the strongest adaptive-weighting play.
2. **Score against risk-adjusted PnL, not sign-of-return.** `profit_sum` already captures magnitude (`memory.py:107`) but the `correct`/`accuracy` path is binary sign (`memory.py:101-106`). Replace `accuracy` in `weight()` (`memory.py:118-120`) with a Sharpe-like `mean_outcome / std(outcome)` so a source that is "right 51% but with good R:R" stops being shrunk to death.
3. **Out-of-sample discipline.** Walk-forward: weight sources on outcomes observed **before** the current cycle only, never refit mid-cycle. The current `pending`/`resolve` split is time-ordered (`memory.py:80-108`), so this is mostly a policy change — evaluate `weight()` against a rolling window (e.g. last 60 resolved records per source) instead of the all-time cumulative in `SourceStats`.

The honest summary: the loop as written is **closer to trap than edge** because it scores on the exact no-edge task. It only becomes a real edge when (i) conditioning on regime, (ii) scoring risk-adjusted, and (iii) staying out-of-sample. None of those need an LLM — but (i) is *materially amplified* by one (see §c).

---

## (c) The 3–4 places an LLM adds NON-predictive value

The docs' core admission: *"the LLM is fenced outside the order path (advisory only: **regime/news vetoes, summaries, explanations — never order routing**)"* (`RESEARCH-SYNTHESIS.md:65`). All four plug-in points below are *veto / classification / structuring* roles — none of them *predict price direction*. Each one already has an exact insertion point in the code.

### (c1) Regime classification — *not* price direction

A classification like "trending / range / risk-off / breakout-benign" is **not** the prediction task LLMs fail at; it's a labelling task they're decent at given price + vol + macro context, and it is **orthogonal** to "will BTC go up."

**Plug-in point:** Add a `RegimeClassifier` whose `.label(symbol, provider)` returns one of a fixed enum. Wire it at **`orchestrator.py:189` (top of `_process_symbol`)**, *before* the analysts run, so the regime can (i) bias the strategy set inside `MarketAnalyst` (`agents/market.py:31`, which is already an injectable `list[Strategy]`), and (ii) feed the **regime-conditional** `ReflectionMemory.weight(source, regime)` from §b. The LLM never touches `signals`, `weighted_combine`, or the proposal; it only sets a categorical label the deterministic logic consumes.

### (c2) News / narrative extraction to VETO bad trades

The cleanest non-predictive use of language models: read a feed, decide *"is there a material adverse event for this symbol right now"*, and emit a hard veto. This is a **gate**, not a forecast. `RESEARCH-SYNTHESIS.md:65` explicitly lists "news vetoes" as in-scope.

**Plug-in point:** The `PreTradeChecker` chain in `risk/guardrails.py:189-233` is the *one* place a deterministic veto already lives. Add a `NewsVetoChecker` as a sibling of `CircuitBreaker`/`KillSwitch` and consult it inside `PreTradeChecker.check()` between the rate-limiter and notional checks (`risk/guardrails.py:194-197`). A veto returns `self._deny("llm_news_veto: <reason>")` (`guardrails.py:235-238`) — same ledger entry, same audit trail. **Critical:** the LLM only ever returns a boolean + reason string; it never constructs a `TradeProposal` (`risk/guardrails.py:41-56`) and never sees the size. A wrong veto just misses a trade; a wrong "buy" call is structurally impossible.

### (c3) Unstructured event feeds → structured signals (listing announcements, unlock calendars)

MEXC is listing-heavy and token-unlock calendars are unstructured text/HTML. Translating "MEXC lists X/USDT at 14:00 UTC" or "1.2% of FET supply unlocks Friday" into a structured `Signal` is a *transcription* job, not a prediction — and it's exactly what the three `fn`-injected analysts (`macro.py:23`, `sentiment.py:23`, `yield_strategist.py:23`) and the universe scout are missing today.

**Plug-in points (two distinct ones):**

- **As an analyst feed.** Build `LLMEventAnalyst(Analyst)` that calls a calendar/news API, uses the LLM to extract `{symbol, event_type, ts, severity}`, and emits a `Signal` with `source="event"` and a *conservative* confidence. It plugs into the analyst list at **`orchestrator.py:91-95`** and runs through the same `weighted_combine` pipeline as everything else (`signals.py:87-104`). A hallucinated bullish event is bounded by `max_weight=0.10` sizing (`portfolio_manager.py:23, 59`) and the risk gate, so it cannot do more than slightly over-allocate one small position.
- **As a universe filter.** Inject an LLM-based *blacklist* into `Scout.discover_candidates()` at **`universe/scout.py:56-69`**: e.g. "skip symbols with a scheduled unlock in <48h." This sits *upstream* of `_maybe_rebalance_universe` (`orchestrator.py:153-180`) and prevents the fleet from ever picking up the bad name. Veto-only, never predictive.

### (c4) Post-hoc explanation / logging

Already partially wired: `Brain.reason()` annotates Bull/Bear theses with prose that is explicitly *"purely cosmetic thesis prose — it cannot move a number or place an order"* (`agents/brain.py:51-58`, consumed at `researchers.py:40-46`). The Compliance Auditor then surfaces up to 3 of these in the daily digest (`agents/auditor.py:42-55`).

**Augmentation points:**

- `ComplianceAuditor.digest()` (`agents/auditor.py:27-55`) currently concatenates raw fields. An LLM can summarize the day's fills/vetoes into a 3-bullet human-readable brief — *after* the deterministic digest is built. The LLM never edits the ledger; it produces a parallel `digest_prose` field.
- The reflection loop's `analytics()` dump (`memory.py:126-127`) is opaque numbers. An LLM can render "macro feed lost influence this week (accuracy 0.41, weight 0.82→0.62)" into a sentence for the digest — pure translation.

This is the lowest-risk, immediate-value use: it costs nothing in safety and meaningfully improves the "human reviews daily digest" loop that the docs make load-bearing (`PLAN.md:101`, `RESEARCH-SYNTHESIS.md:79`).

---

## (d) Proposed design — "LLM-as-gatekeeper, never predictor"

The docs justify exactly this design. The two load-bearing quotes:

> *"a deterministic trading core wrapped in a veto-capable risk gate, with the LLM fenced outside the order path (advisory only: regime/news vetoes, summaries, explanations — never order routing)"* — `RESEARCH-SYNTHESIS.md:65`

> *"External data (news/social/on-chain) treated as untrusted; isolated from the action layer. Hard action allow-list; agent cannot exceed a fixed schema regardless of input. High-impact actions require a deterministic policy gate, not model judgment."* — `PLAN.md:127-130`

### Architecture

```
                ┌─────────────────────────────────────────────────┐
                │              LLM BOUNDARY (advisory)            │
                │  Output contract: fixed schema ONLY.            │
                │  {regime: enum}                                 │
                │  {veto: bool, reason: str}                      │
                │  {symbol, event_type, ts, severity}             │
                │  {digest_prose: str}                            │
                │  NEVER: side, qty, price, order, weight>cap     │
                └─────────────────────────────────────────────────┘
                       │            │            │            │
            ┌──────────▼──┐  ┌──────▼───────┐  ┌─▼──────────┐ ┌▼──────────┐
            │ Regime      │  │ News veto    │  │ Event      │ │ Digest    │
            │ classifier  │  │ checker      │  │ translator │ │ summarizer│
            │ (c1)        │  │ (c2)         │  │ (c3)       │ │ (c4)      │
            └──────┬──────┘  └──────┬───────┘  └─────┬──────┘ └─────┬─────┘
                   │                │                │              │
   ──── DETERMINISTIC CORE (the order path, unchanged) ────        │
   │                                                              │
   │  analysts ─► weighted_combine(regime-conditional w) ─► PM     │
   │     ▲                                              │         │
   │     └──── event Signal (c3) joins as just another   │         │
   │            analyst; bounded by max_weight           │         │
   │                                                     ▼         │
   │  PreTradeChecker.check() ◄── NewsVetoChecker (c2)   │         │
   │     └── kill / breaker / rate / notional /          │         │
   │         sanity / exposure / symbol / NEWS           │         │
   │                                                     │         │
   │  ExecutionTrader ─► Fill ─► Auditor.ledger ─────────┼─► (c4) │
   │                                                     │         │
   │  ReflectionMemory.weight(source, regime) ◄──────────┘         │
   │         (regime-conditional adaptive weighting, §b)           │
   ─────────────────────────────────────────────────────────────────
```

### Invariants the design must enforce (all already in the codebase)

1. **LLM output is schema-validated.** The four output types above are the only ones the LLM is allowed to produce; anything else is dropped (mirrors `agents/brain.py:92-95` fail-soft).
2. **LLM cannot construct a `TradeProposal`.** That dataclass lives in `risk/guardrails.py:41-56` and is only built by `PortfolioManager.decide` (`portfolio_manager.py:67-81`). The LLM classes never import it.
3. **LLM cannot raise a weight above the cap.** `ReflectionMemory.max_weight=1.5` is set in code (`memory.py:55-56`), not by the model.
4. **Every LLM action is journaled** with its raw input + output to the same hash-chained ledger (`agents/auditor.py:23-25`) so post-hoc review can audit what the model "said."
5. **The kill switch is out-of-band** (`risk/guardrails.py:104-126`) — the LLM cannot prevent a human halt.
6. **A wrong LLM call is bounded to *opportunity cost*, never capital loss.** A false veto skips a trade. A false regime label downweights a good source to 0.3× (`memory.py:121`). A hallucinated event Signal is capped at 10% sizing (`portfolio_manager.py:59`). At no point does an LLM error reach the order book.

### Why this matches the docs' honesty

The docs say three times in three different ways that LLMs are not the alpha source (`RESEARCH-SYNTHESIS.md:11, 39, 73`; `PLAN.md:8-12`). This design accepts that and assigns the LLM only the four jobs LLMs are actually useful for — classification, veto, transcription, summarization — and bolts each onto a single, narrow, deterministic seam that already exists. None of the four asks the model "what will the price do"; all four ask "what *kind* of market is this / is there a *reason not to* trade / what does this text *say* / what did we *do* today."

That is the only LLM design the evidence supports, and conveniently, it is the one this codebase was already architected for.

---

*Calibration: the four plug-in points and the gatekeeper architecture are direct reads of the cited code; the §b "real edge vs trap" conditions (regime-conditional, risk-adjusted, out-of-sample) are an inference from the cited mechanics, not a claim that the current loop implements them — it does not.*

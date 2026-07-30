# 42 — LLM structured-event *extraction*: free feeds → schema-fenced JSON → deterministic Signal (the "translation" value)

**Agent:** 42/60 · **Scope:** the *mechanism* by which an LLM turns unstructured event/news feeds into structured records — extraction-accuracy evidence, model/schema/guard design, and token cost — for `rapana/agents/`, `rapana/feeds/`, `rapana/signals.py`, `rapana/risk/guardrails.py`, `rapana/fleet/orchestrator.py`.
**Goal:** isolate the one LLM use the evidence most strongly supports on a MEXC spot-only fleet — **information extraction / transcription** (not prediction) — and specify an `EventExtractorAgent` that emits a schema-fenced record a *deterministic* mapper converts to a `Signal` / veto.

**Position relative to sibling notes (don't re-read them, this is the map):**
- **`32-llm-papers.md`** surveys the 7 LLM-trading papers and ranks extraction as the **#2** surviving non-predictive use (veto is #1). This note is the **deep-dive on the extraction *mechanism*** 32 defers.
- **`36-event-driven.md`** studies *which* events leave a durable drift and designs `EventAnalyst` (the **edge consumer**) + its free feeds + §5 decision table. This note designs the **translation layer that feeds it** — the LLM call, its schema, its guards, its cost. The two compose (§c5).
- **`05-fleet-llm-edge.md:116-123`** names the plug-in seams (`orchestrator.py:91-95`, `scout.py:56-69`); **`15-mexc-listing-detection.md`** owns the *deterministic* MEXC-announcement feed; **`22-token-unlocks.md:69-81`** owns the unlock-calendar sources. This note consumes those feeds as inputs and adds the LLM translation step on top.

All repo citations are `file:line`. External claims carry URL + ✅ if the abstract/page was fetched live this session. Specific per-component F1/accuracy numbers from the papers are **not** restated as fact here (only abstracts were fetched, full PDFs not) — the accuracy claim is anchored to what the abstracts + the repo's own OOS synthesis actually support, plus a held-out-eval recommendation (§f). Magnitudes needing backtest are flagged **[HYPOTHESIS → backtest]**, the same discipline as `36-event-driven.md:26`.

---

## (a) Why extraction is the strongest *practical* LLM use here

The repo is explicit that LLM price-*prediction* has no OOS edge (`RESEARCH-SYNTHESIS.md:11,39`), and the three live, contamination-controlled benchmarks converge on it from three angles (`32-llm-papers.md:14-16`): **LiveTradeBench** (best model ~6% / peers 70%+ drawdowns over 50 days, `2511.03628`), **AI-Trader** ("general intelligence ≠ trading capability", `2512.10971`), **TradeTrap** (LLM judgment is *fragile and adversarially manipulable* in the order path, `2512.02261`).

But those same benchmarks, plus the system papers, **do** support a narrower, durable use: **schema-fenced gatekeeping — classify / extract / veto / report, never predict.** Extraction is the cleanest of these for a *low-frequency, listing-heavy* venue like MEXC, because:

1. **It is transcription, not forecasting.** "MEXC lists ZYLO/USDT at 12:00 UTC on Jun 23", "1.2% of FET unlocks Friday", "Bybit lost $1.4B" are *facts stated in a document*. Turning them into `{event_type, asset, ts, magnitude, source_url}` is a reading-comprehension task LLMs are good at — and crucially one whose **wrong answer is auditable against the cited source** (unlike a price forecast, which is unfalsifiable until the future arrives).
2. **It fills a structural blind spot the deterministic analysts have today.** `SentimentAnalyst` is a stub returning neutral with no feed (`agents/sentiment.py:26-30`); `MacroAnalyst` is `fn`-injected and unconfigured (`agents/macro.py`); there is **no `events` table** (`36-event-driven.md:178`). MEXC's listing/unlock/delisting calendar is exactly the unstructured input the deterministic core cannot see (`05-fleet-llm-edge.md:116-123`).
3. **It is the one use where hallucination is *cheap to contain*.** A schema-fenced record either validates or it doesn't; a low-`confidence` record routes to *veto-only* (skip the trade), not to *action* (§d). The asymmetry the benchmarks demand ("a wrong veto misses a trade; a wrong buy is catastrophic", `05-fleet-llm-edge.md:114`) is preserved by construction.

---

## (b) Extraction-accuracy evidence (what the literature actually supports, honestly)

Three abstracts fetched live this session frame the claim. **The claim is qualitative and structural, not a specific F1** — full-PDF per-component numbers are deliberately not restated.

| Source (✅ = abstract fetched) | What it establishes | What it does *not* establish |
|---|---|---|
| **BloombergGPT** `2303.17564` ✅ [arxiv.org/abs/2303.17564](https://arxiv.org/abs/2303.17564) | A 50B model trained on a 363B-token financial corpus **"outperforms existing models on financial tasks by significant margins without sacrificing performance on general LLM benchmarks"** — and the tasks named are **sentiment analysis, named-entity recognition, question answering** (i.e. extraction/classification). | A returns claim (none is made). And it's proprietary (Bloomberg's data); the *transferable* finding is "domain data + instruction-tuning lifts financial NLP", not the model itself. |
| **PIXIU / FinMA** `2306.05443` ✅ [arxiv.org/abs/2306.05443](https://arxiv.org/abs/2306.05443) | The first open financial benchmark covers **"five financial NLP tasks and one financial prediction task"** — i.e. the field itself formally *separates* extraction/classification (5 tasks) from prediction (1 task). FinMA is LLaMA instruction-tuned on 136K financial samples. | Per-task accuracy (in the full PDF, not the abstract). The structural separation is the load-bearing point for this note: **the task LLMs are benchmarked as good at is exactly the extraction one.** |
| **FinGPT** `2306.06031` ✅ [arxiv.org/abs/2306.06031](https://arxiv.org/abs/2306.06031) | An open-source, **data-centric** FinLLM whose contribution is an **"automatic data curation pipeline"** + lightweight LoRA, with applications "robo-advising, algorithmic trading, low-code". | A returns claim (none is made). The transferable contribution is the **data-curation + extraction toolkit**, not a trading edge. |

**Reading the table:** all three are *infrastructure/benchmark* contributions whose demonstrated strength is **financial NLP (extraction/classification/summarization)**, and **none** claims a predictive/trading edge. That is precisely the split the repo's own OOS synthesis (`32-llm-papers.md:38-39`) relies on: the 4 system papers' returns are backtested-and-assumed-to-decay; the *durable* contribution is the extraction/classification/veto axis.

**Two further structural facts (vendor capability, not a paper):**
- **Schema-constrained generation is now a first-class API feature.** OpenAI's Structured Outputs (`platform.openai.com/docs/guides/structured-outputs`) constrains decoding to a supplied JSON Schema, so **conformance to the schema is enforced at decode time** rather than hoped for post-hoc. This collapses an entire class of "the model emitted prose instead of JSON" failure modes that older extraction pipelines suffered. (Anthropic, Google, and open tooling offer equivalent constraints.)
- **Self-consistency / ensemble voting** on a *narrow* schema record (run the extraction 2–3×, keep the majority/agreed field values) is cheap because the record is tiny (~100 output tokens, §e) and is the single most effective hallucination reducer for the rare, high-stakes veto path (§d4).

**Honest cap on the accuracy claim:** the literature supports *"LLMs are reliably better than deterministic regex at extracting structured facts from financial text, and schema-constrained decoding makes the output machine-validatable."* It does **not** support a specific number like "97% F1 on MEXC-delisting extraction" — that must come from rapana's own held-out eval (§f). The guard design in §d is built to make the pipeline **safe even at modest extraction accuracy**, which is the right posture given that cap.

---

## (c) `EventExtractorAgent` — design

### c1. Feeds (free / no-key, all already vetted by sibling notes)

| Feed | Covers | Source note | Owner |
|---|---|---|---|
| **MEXC announcements** (listing / delisting / API-updates) | lifecycle events on the *trading venue itself* | ToS-safe read via **Telegram MTProto relay** (`@MEXC_OfficialAnnouncements`) + `load_markets(reload=True)` confirmation; **no REST/RSS announcement API exists** (`15-mexc-listing-detection.md:11-31,49-56`) | `15` |
| **CryptoCompare News API** (`min-api.cryptocompare.com`, `category=3`) + RSS (CoinDesk/The Block/Decrypt) | broad categorized news stream, incl. historical for backtest labels | free tier, generous (`36-event-driven.md:103-104`) | `36` |
| **Rekt.news leaderboard** (`rekt.news/leaderboard/`) | DeFi exploit catalog with $-lost + timestamps | free; the hack/exploit primary (`36-event-driven.md:105`) | `36` |
| **Tokenomist unlock calendar** (`api.tokenomist.ai/v4/...`) + **DefiLlama** (`api.llama.fi/emissions`) fallback | scheduled cliff/linear unlocks; `committedClaim` flag | Tokenomist free trial: 50 tokens, 1y back, 120 req/min — covers the Scout top-50 (`22-token-unlocks.md:73-80`); DefiLlama no-key | `22` |
| **Farside BTC-ETF daily flow** + SoSoValue/CoinShares weekly | sustained ETF-flow regime vote on BTC/ETH | free (`36-event-driven.md:106-107`) | `36` |

These are **read-only, low-frequency, single-venue-tolerant** inputs — the same envelope every other edge in the fleet respects (`16-mexc-tos-envelope.md`, `08-mexc-client-edge.md:105`). The extractor adds **no new order-path surface**: it reads feeds, writes records.

### c2. Model choice — cheap, schema-locked, two-tier

- **Default (99% of items): `gpt-5.4-nano`** at **$0.20 / $1.25 per 1M tokens** (input/output), OpenAI pricing fetched live ✅ (`platform.openai.com/docs/pricing`). A 50-token system+schema prompt is **prompt-cacheable** (cached input tier $0.02/M for nano), so the recurring cost is dominated by the per-item news text + the ~100-token output record.
- **Escalation (ambiguous / veto-critical items only): `gpt-5.4-mini`** at **$0.75 / $4.50 per 1M** ✅. Route to mini only when (i) nano's `confidence < 0.5`, or (ii) the event family is `exchange_hack`/`delisting`/`regulatory` (the veto-bearing rows in `36-event-driven.md:73-80`). This keeps the expensive model off routine news.
- **Self-hosted fallback (optional):** a 7–8B instruction-tuned model (Llama / Qwen / FinMA-family) for zero-marginal-cost batch backfill of historical feeds to build the §f eval set — no per-token cost, full data sovereignty. Not the live path.
- **Vendor portability:** the schema + deterministic mapper are model-agnostic; the LLM is a swappable *provider* exactly as the repo already abstracts it (`agents/market.py:14-22` "strategy set is injectable"; `agents/brain.py`). Anthropic Haiku / Gemini Flash are drop-in at comparable price/latency.

### c3. The schema — fenced record the LLM is *allowed* to emit (nothing more)

The LLM **never** emits a `Signal`, a size, a price, or an order. It emits one **`ExtractedEvent`** record, constrained by JSON Schema / Structured Outputs:

```jsonc
// ExtractedEvent — the ONLY object the LLM may produce. Enforced at decode time.
{
  "event_type": "listing",          // enum: listing | delisting | api_disabled | unlock |
                                    //        exchange_hack | defi_exploit | regulatory |
                                    //        etf_flow | macro_print | network_upgrade | other
  "assets": ["ZYLO"],               // base assets referenced (>=1); verified vs load_markets upstream
  "scope": "idiosyncratic",         // enum: systemic | idiosyncratic | n/a   (load-bearing for hacks, 36:114-119)
  "direction": "neutral",           // enum: bullish | bearish | neutral      (the LLM's *read* of the text, not a trade call)
  "horizon_h": 24,                  // integer hours the LLM estimates the info takes to digest (clamped 1..720)
  "magnitude": 0.024,               // numeric severity: unlock % of float, hack $-lost/1e9, etc. (0 if n/a)
  "event_ts": 1782298000,           // epoch seconds the event occurs/was published
  "confidence": 0.55,               // LLM's own certainty in the EXTRACTION (0..1) — NOT a trade conviction
  "source_url": "https://www.mexc.com/announcements/article/17827791536292",  // REQUIRED, non-empty
  "source_quote": "MEXC will list ZYLO/USDT in the Innovation Zone at 12:00 on Jun 23, 2026 (UTC)",  // verbatim span for audit
  "notes": ""                       // optional, <=200 chars; no free-form action language is parsed from this
}
```

**Why this shape:**
- `direction`/`confidence`/`horizon_h` mirror the prompt's requested `{event_type, asset, direction, horizon, confidence}` and map 1:1 onto `Signal` (`signals.py:17-25`), so the deterministic mapper (§c4) is a near-identity transform — *no LLM judgement leaks into sizing*.
- `source_url` + `source_quote` are **mandatory, non-empty** — this is the hallucination backstop: every record can be re-checked against a citation (§d3). A model that cannot quote the document it's summarizing is forced to low confidence.
- `scope` (systemic vs idiosyncratic) is included because it is *the* load-bearing decision for the hack/exploit family (`36-event-driven.md:114-119`) and is a reading task (does the text mention a custodial exchange / withdrawal halt?), not a forecast.
- `assets` is a *list* and is **upstream-validated against `load_markets`** before any `Signal` is created — an extracted asset that isn't tradeable on MEXC is dropped, never auto-added.

### c4. The deterministic mapper — `ExtractedEvent` → `Signal` / veto (no LLM in this step)

A pure function `map_event_to_signal(ev: ExtractedEvent) -> Signal | Veto | None`. It encodes `36-event-driven.md`'s §5 decision table as code, *not* as prompt text, so the edge logic is auditable and PIT-backtestable. Sketch:

```python
# rapana/events/mapper.py — DETERMINISTIC. No provider call. Fully unit-testable.
# Edge logic (which families have durable drift, §5 of agent 36) lives HERE, not in the prompt.

DURABLE_BEARISH = {"exchange_hack", "delisting", "regulatory_restrictive"}     # 36 rows #1,#3
DURABLE_BULLISH = {"regulatory_favorable"}                                      # 36 row #2
EFFICIENT_WITHHOLD = {"etf_approval", "halving", "macro_print", "listing_pop"} # 36 rows #6-9 -> neutral

def map_event_to_signal(ev, source_weights):
    # 1. confidence gate (§d2): low-confidence records NEVER become directional signals
    if ev.confidence < ACTION_CONF:           # e.g. 0.5
        return Veto if ev.event_type in HARD_VETO_FAMILIES else None  # veto-only, never action

    # 2. efficient families -> withhold (36 §5 cardinal rule: earn keep by NOT trading these)
    if ev.event_type in EFFICIENT_WITHHOLD:
        return None

    # 3. durable families -> Signal with a CAPPED, pre-validation confidence (36 §7)
    if ev.event_type in DURABLE_BEARISH | DURABLE_BULLISH:
        direction = "bullish" if ev.event_type in DURABLE_BULLISH else "bearish"
        return Signal(
            symbol=resolve_mexc_pair(ev.assets[0]),     # validated vs load_markets; None -> drop
            source="event",
            direction=direction,
            strength=clamp(STRENGTH_BY_FAMILY[ev.event_type] * severity_scale(ev), 0.0, 0.7),
            confidence=min(ev.confidence, PRE_VAL_CAP),  # hard cap 0.45 until §f backtest passes (36 §7)
            rationale=f"{ev.event_type} ({ev.scope}); {ev.source_quote[:80]}",
            extras={"event_category": ev.event_type, "scope": ev.scope, "source_url": ev.source_url,
                    "horizon_h": ev.horizon_h, "validated": False},
        )
    return None
```

**Properties this guarantees:**
- The LLM's `direction`/`confidence` are *inputs* to a deterministic rule; they cannot, on their own, route an order. A hallucinated `"bullish"` on a `delisting` is overridden to `bearish` by the table.
- `strength` is **set by code** from the event family + magnitude, never by the model — so a model cannot "be very confident" its way into a bigger position. Sizing stays in `PortfolioManager` (`agents/portfolio_manager.py`) bounded by `max_weight=0.10` (`orchestrator.py:51`).
- `validated=False` + `PRE_VAL_CAP` keep every event-derived Signal in the same advisory/paper posture as every other hypothesis-stage edge (`36-event-driven.md:196`).

### c5. Composition with `EventAnalyst` (agent 36) — translation vs edge

```
free feeds → news_ingest → [this note] EventExtractorAgent (LLM) → ExtractedEvent (schema-fenced)
                                                                      │
                                          deterministic mapper (§c4) ─┴→ Signal(source="event") / Veto / None
                                                                                       │
                                            [agent 36] EventAnalyst consumes the Signal ┘  (edge consumer; lives in weighted_combine)
                                                                                       │
                          PortfolioManager → risk gate (guardrails.py) → executor      (LLM fenced OUT of all of this)
```

`EventExtractorAgent` is the **translation layer** (text → record); `EventAnalyst` (36) is the **edge consumer** (record → sized advisory Signal). Keeping them separate means the extraction accuracy (§b/§f) can be evaluated *independently* of whether any event family has durable drift (36 §8) — two distinct failure modes, two distinct gates.

---

## (d) Hallucination guards — layered defense (the load-bearing section)

The pipeline is designed to stay safe **even if extraction accuracy is only modest**. Five layers, innermost first:

1. **Decode-time schema lock (§c2/c3).** Structured Outputs / JSON Schema constrains the model to *only* emit a valid `ExtractedEvent`. Malformed/extra-field/prose responses are structurally impossible — the API retries until it validates or errors. This is the single biggest reducer of "the model rambled" failures and the reason older regex-on-prose extraction pipelines are obsolete.
2. **Confidence gating (§c4 step 1).** `ev.confidence < ACTION_CONF` ⇒ the record can **at most** produce a *veto* (skip a trade), never a directional *action*. Low-certainty extractions are routed to opportunity-cost, not capital risk — the asymmetry `05-fleet-llm-edge.md:114` requires.
3. **Mandatory source citation + verbatim quote (§c3).** Every field set must carry a non-empty `source_url` and a `source_quote` span. A downstream auditor (and a future automated re-check) can diff the quote against the fetched document. Records whose quote does not appear in the cited source are auto-demotion candidates (a cheap deterministic substring/proximity check). This makes hallucination **detectable**, which a price forecast never is.
4. **Ensemble self-consistency on veto-critical items (§b).** For `exchange_hack`/`delisting`/`regulatory` rows, run extraction **n=2–3** times (mini tier) and only emit a *veto* when records **agree** on `event_type`+`scope`. Disagreement ⇒ withhold (no veto, no action). Triples the per-item cost only on the rare, high-stakes items (still <¢/day, §e) and is the most effective known hallucination filter for the one path that can block a trade.
5. **Deterministic override + asset validation (§c4).** The mapper (i) overrides the model's `direction` using the family table (a `delisting` is bearish regardless of what the text "feels like"), (ii) validates `assets` against `load_markets` (drops untradeable/hallucinated tickers), (iii) caps `confidence`/`strength` pre-validation, and (iv) sets `validated=False`. **The LLM cannot escalate its own influence** — every widening of its authority is a code change a human reviews.

**Blast-radius ceiling:** even a fully-hallucinated *bullish* event that survived all five layers is bounded by `max_weight=0.10` (`orchestrator.py:51`), the risk gate (`guardrails.py:189-233`), and the staged-capital gate (`orchestrator.py:65-68`). A wrong *veto* costs one missed trade; a wrong *action* is structurally capped at one small, over-allocated position. This is exactly the "LLM-as-gatekeeper, never predictor" posture the docs mandate (`RESEARCH-SYNTHESIS.md:65`, `PLAN.md:127-130`).

---

## (e) Cost — token economics (the honest answer: it's negligible)

Using live-fetched OpenAI pricing ✅ (`platform.openai.com/docs/pricing`, per 1M tokens):

| Model | Input | Cached input | Output | Role |
|---|---|---|---|---|
| `gpt-5.4-nano` | $0.20 | $0.02 | $1.25 | default, ~99% of items |
| `gpt-5.4-mini` | $0.75 | $0.075 | $4.50 | escalation: ambiguous + veto-critical only |
| `gpt-5.4-nano` **Batch** | $0.10 | — | $0.625 | 24h-latency backfill of historical feeds for the §f eval |

**Volume estimate (free feeds, dedup'd, new-items-only):**
- CryptoCompare/RSS news ≈ 80–150 items/day; MEXC announcements ≈ 5–20/day; Rekt exploits ≈ a few/week; Tokenomist upcoming ≈ a handful/day. Realistic **~100–150 LLM-worthy new items/day** after dedup.
- Per item: ~700 input tokens (cacheable system+schema prompt ≈ 400 + news text ≈ 150–300) + ~100–150 output tokens (the `ExtractedEvent`).

**Daily cost @ ~150 items/day:**
- **nano default:** 0.105M in × $0.20 + 0.018M out × $1.25 ≈ **$0.04/day** (≈ $1.3/mo). With prompt caching on the constant system+schema block, input cost drops further (~$0.02–0.03/day).
- **mini escalation on ~10% of items (15/day):** 0.0105M in × $0.75 + 0.0018M out × $4.50 ≈ **$0.016/day** extra.
- **ensemble n=3 on the ~1–3 veto-critical items/day:** trivial (<$0.01/day).
- **Total live: ≈ $0.05–0.07/day, ~$1.5–2/mo.**

**One-time backfill (build the §f eval set):** re-process ~1–3y of CryptoCompare historical news + Rekt archive via **nano Batch** ($0.10/$0.625). ~50k items × ~700 in + 120 out ≈ 35M in + 6M out ≈ **$3.5 in + $3.75 out ≈ $7 one-time**, with no rate-limit pressure.

**Honest cap:** token cost is **not** the constraint — it is sub-$2/month live. The real costs are (i) **engineering** the feed ingest + the deterministic mapper + the eval harness (the durable work), and (ii) the §f validation gate, without which the pipeline ships un-measured. This matches the repo-wide pattern: every "edge" note concludes the *backtest/validation* is the gate, not the data cost (`36-event-driven.md:176-182`, `22-token-unlocks.md:222-225`).

---

## (f) Validation gate — measure extraction accuracy before trusting it

Status today: no `events` table, no news ingest (`36-event-driven.md:178`). So, mirroring `36-event-driven.md:176-182` and `15-mexc-listing-detection.md`:

1. **Build the feed ingest** → `events` + `extracted_events` tables in `data/store.py:13-43`; pollers at hourly cadence (no websocket).
2. **Build a held-out, human-labeled eval set** (~300–500 items across all `event_type` enums) from the §e one-time backfill. Measure **per-field extraction accuracy**: `event_type` accuracy, `assets` exact-match, `scope` accuracy (the high-stakes one), `direction`/`magnitude` error, and **citation validity** (does `source_quote` actually appear in `source_url`?). This is the number the §b literature does *not* give us and the one that should gate go-live.
3. **Two independent gates** (do not let one pass justify the other):
   - **Extraction gate (this note):** per-field accuracy ≥ target (e.g. `event_type` ≥ 0.95, `scope` ≥ 0.90, citation-validity = 1.00) on the held-out set. Fail ⇒ keep confidence caps / veto-only.
   - **Edge gate (agent 36):** `backtest/event_drift.py` passes the Deflated-Sharpe gate per family (`36-event-driven.md:181`). Fail ⇒ `validated=False`, `source_weights["event"]` stays ~0.3.
4. Only on **both** passing: raise `PRE_VAL_CAP`, flip `validated=True` family-by-family.

Until then: `EventExtractorAgent` runs **advisory/paper-only** — records surface in the Bull/Bear debate as an opinion + operator alert (`notify`, `config.py:44-46`), zero freeze risk — the same safe track as every other hypothesis-stage edge (`36-event-driven.md:196`, `12-mexc-funding.md:116`).

---

## (g) Plug-in points (consolidated, all pre-existing seams)

- **Analyst seat:** inject `EventExtractorAgent`-fed `Signal`s into the analyst list at `rapana/fleet/orchestrator.py:91-95` (alongside `MarketAnalyst`/`SentimentAnalyst`/`MacroAnalyst`). They flow through `weighted_combine` (`signals.py:87-104`) at `source_weights["event"] ≈ 0.3`.
- **Universe blacklist (safer, ship first):** inject an event-derived `exclude_fn` into `Scout.discover_candidates()` at `rapana/universe/scout.py:56-69` (e.g. skip `delisting`-within-N-days / imminent-`unlock`) — sits *upstream* of execution entirely (`05-fleet-llm-edge.md:123`, `22-token-unlocks.md:128-135`).
- **Hard veto:** for systemic-hack rows, set an `event_veto_until` flag consumed by the risk gate at `rapana/risk/guardrails.py:194-197` (sibling of `CircuitBreaker`/`KillSwitch`); veto authority is deterministic, never the LLM (`36-event-driven.md:172`, `05-fleet-llm-edge.md:114`).
- **Schema extension:** add `"event"` to the `source` enum comment at `signals.py:20` (no code change — `weighted_combine` already defaults unknown sources to weight 1.0, `signals.py:87-104`).
- **Feed plumbing:** reuse the `Feed` ABC + cache/fail-soft template at `rapana/feeds/base.py` / `rapana/feeds/feargreed.py` (per `22-token-unlocks.md:143-145`).

---

## (h) Honest summary / calibration

**Is:** the strongest practical LLM use on this fleet is **schema-fenced information extraction** — translating free MEXC-announcement/news/exploit/unlock text into a validatable `{event_type, asset, scope, direction, horizon_h, magnitude, confidence, source_url}` record that a **deterministic** mapper turns into a capped, advisory `Signal` or a veto. The literature (BloombergGPT `2303.17564`, PIXIU/FinMA `2306.05443`, FinGPT `2306.06031` — abstracts fetched ✅) supports financial-NLP extraction as the durable, non-predictive contribution; the repo's own OOS synthesis (`32-llm-papers.md`) ranks it the #2 surviving use. With **decode-time schema locking + confidence gating + mandatory citation + ensemble-on-veto + deterministic override**, the pipeline is safe at *modest* extraction accuracy, and costs **~$0.05–0.07/day (~$2/mo)** live on `gpt-5.4-nano` + mini-escalation (pricing fetched ✅).

**Is not:** a reason to trust a specific F1 the literature doesn't give us — extraction accuracy on *MEXC-flavored* text must come from rapana's own held-out eval (§f). Nor a shortcut around the edge-validation gate: even a perfect extractor only pays off if the event family has durable drift (`36-event-driven.md`), which is a separate, per-family Deflated-Sharpe test.

**Calibration notes:** (i) Only the abstracts of `2303.17564`/`2306.05443`/`2306.06031` and the OpenAI pricing page were fetched live this session; per-component benchmark F1s are **not** restated (full PDFs not fetched), so the accuracy claim is anchored to what the abstracts + the repo synthesis support, plus a §f held-out eval. (ii) OpenAI pricing is as-fetched for Jun 2026 (`gpt-5.4-nano`/`-mini`); Anthropic/Google/open equivalents are referenced as drop-in alternatives at comparable tiers but their exact current prices were not fetched. (iii) This note owns the **mechanism**; the **edge** (which events drift) is `36-event-driven.md`, the **deterministic listing feed** is `15-mexc-listing-detection.md`, the **unlock sources** are `22-token-unlocks.md`, and the **strategic LLM survey** is `32-llm-papers.md` — read those for the parts this note deliberately defers.

---

## Sources (consolidated)

**Extraction-accuracy / financial-NLP (abstracts fetched ✅)**
- BloombergGPT — Wu et al., 2023 — https://arxiv.org/abs/2303.17564
- PIXIU / FinMA — Xie et al., 2023 — https://arxiv.org/abs/2306.05443
- FinGPT — Yang, Liu, Wang, 2023 (IJCAI FinLLM, Best Presentation) — https://arxiv.org/abs/2306.06031
- Repo OOS synthesis (3 live benchmarks: LiveTradeBench `2511.03628`, AI-Trader `2512.10971`, TradeTrap `2512.02261`) — `research/agents/32-llm-papers.md:14-16,38-39`

**Structured-output / schema-constrained generation (vendor capability)**
- OpenAI Structured Outputs — https://platform.openai.com/docs/guides/structured-outputs
- OpenAI pricing (live ✅ Jun 2026) — https://platform.openai.com/docs/pricing

**Feeds (free / no-key; vetted by sibling notes)**
- MEXC announcements (TG relay + `load_markets`; no REST/RSS) — `research/agents/15-mexc-listing-detection.md:11-31,49-56`
- CryptoCompare News API (free tier) — https://min-api.cryptocompare.com/documentation ; Rekt leaderboard — https://rekt.news/leaderboard/ ; Farside ETF flow — https://farside.co.uk/bitcoin-etf-flow-all-data/
- Tokenomist unlock API (free trial 50 tokens) — https://docs.tokenomist.ai/api-documents/introduction ; DefiLlama emissions — https://api.llama.fi/emissions — `research/agents/22-token-unlocks.md:73-80`

**Repo base facts**
- `RESEARCH-SYNTHESIS.md:11,39,65` · `PLAN.md:127-130` · `05-fleet-llm-edge.md:100-134` · `32-llm-papers.md:14-16,38-39,96-98` · `36-event-driven.md:73-80,114-119,172-182` · `22-token-unlocks.md:73-80,128-135`
- Code seams: `rapana/signals.py:17-25,87-104` · `rapana/fleet/orchestrator.py:51,65-68,91-95` · `rapana/universe/scout.py:56-69` · `rapana/agents/sentiment.py:26-30` · `rapana/agents/macro.py` · `rapana/risk/guardrails.py:189-233` · `rapana/feeds/base.py` · `rapana/feeds/feargreed.py` · `rapana/data/store.py:13-43`

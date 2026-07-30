# 47 — LLM + RAG → a daily ADVISORY THESIS (explain-to-the-human), never execution

**Agent:** 47/60 · **Scope:** an `AdvisoryDigestAgent` that runs a **RAG-grounded LLM** over the decision ledger + news/events + analyst signals once per day to produce a cited narrative digest for the human supervisor — the "compliance/auditor made useful" role.
**Hard constraint (load-bearing):** the LLM is **fenced outside the order path** (`RESEARCH-SYNTHESIS.md:65`: *"summaries, explanations — never order routing"*). This agent **adds zero code paths to execution**; it only *reads* the ledger and *writes* prose + a recommended human action (`approve | veto | wait`). The deterministic digest (`auditor.py:27-55`) and the kill switch (`guardrails.py:104-126`) are untouched. A wrong LLM sentence cannot reach the order book — the worst case is a confusing push to the human's phone.

Repo citations are `file:line`. External evidence is URL-cited in §g; claims I **fetched live** this session are ✅. This note extends the report-generation finding of `32-llm-papers.md:80-88` (digest is the "obvious Phase-1 starter", zero safety cost) and `05-fleet-llm-edge.md:127-134` (digest-summarizer augmentation points) with the **RAG/citation/fact-check** machinery that makes the prose trustworthy enough to actually read.

---

## (a) The single question this agent answers

The docs make the human-in-the-loop **load-bearing**: the supervisor either approves trades above a threshold or reviews a daily digest (`RESEARCH-SYNTHESIS.md:101` — *"approval-gated … vs daily-digest only"*). But the digest that exists today is a **deterministic field dump**:

```
=== RAPANA DAILY DIGEST ===
proposals      : 4
fills executed : 2
risk vetoes    : 1
  fill: {...}
  veto: llm_news_veto: ...
  thesis: <up to 3 raw Bull/Bear prose lines>
```
— `auditor.py:31-55`. It tells the human *what happened*, not *why it's coherent*, *what could go wrong*, or *what they should do about it*. Reading it requires the human to mentally re-derive the bull/bear/risk case from raw event rows every morning.

**The gap `AdvisoryDigestAgent` fills:** synthesize the day's ledger rows + any news/event/research corpus into a **cited, confidence-scored narrative** the human can act on in 60 seconds — *without* the LLM touching a number, a weight, or an order. This is the one LLM use where the literature agrees the upside is real (`32-llm-papers.md:80-88`) and the downside is bounded to "wasted reading time."

---

## (b) Evidence — what the literature says about LLM financial-report *generation* vs *hallucination*

The evidence splits cleanly into two horns that *together* define the design: **(i)** report generation / structured analysis is the part of finance-LLM work that demonstrably works, **but (ii)** ungrounded financial prose hallucinates at a rate that is enterprise-disqualifying. The entire design in §d is the answer to "how do you get (i) without dying on (ii)."

### b.1 Report generation / analysis structuring — works (BloombergGPT, FinGPT)

| Paper (✅ fetched) | Contribution that survives | Implication for the digest |
|---|---|---|
| **BloombergGPT** `2303.17564` ✅ [arxiv.org/abs/2303.17564](https://arxiv.org/abs/2303.17564) | 50B-param model trained on 363B finance tokens; *"outperforms existing models on financial tasks by significant margins"* — but the tasks are **NER, sentiment, QA, summarization**, *not* returns prediction. Makes no alpha claim. | Validates the **fin-domain LLM for comprehension/structuring tasks** — exactly the digest job. The edge is *reading* finance text well, not forecasting. |
| **FinGPT** `2306.06031` ✅ [arxiv.org/abs/2306.06031) | Open-source, data-centric, LoRA; lists **"robo-advising"** as a showcase application. No returns claim — infrastructure. | "Robo-advising" = **narrative report generation over a curated corpus** — the literal product this agent ships. |
| **TradingAgents** `2412.20138` (cited `32-llm-papers.md:28`) | Multi-role firm sim whose durable contribution is the **Bull/Bear debate + risk-team** scaffold — *advisory structuring*; returns claims are backtested and assumed to decay. | The digest's **(b) bull/bear/risk-case** section is a read-only rendering of the debate rapana *already runs* (`researchers.py:53-64`), not new prediction. |

**Read:** across all three, the part that survives contact with OOS reality is *structuring and rendering*, never *directional prediction* (`32-llm-papers.md:38`). A digest agent is the canonical use.

### b.2 The hallucination horn — ungrounded financial prose is disqualified-grade

This is the load-bearing counter-evidence and the reason the design *cannot* be "prompt an LLM and push its output to ntfy."

**FinanceBench** `2311.11944` ✅ [arxiv.org/abs/2311.11944](https://arxiv.org/abs/2311.11944) — open-book financial QA, 10,231 questions, 16 model configurations manually reviewed (n=2,400). The headline finding, quoted from the abstract:

> *"GPT-4-Turbo used with a retrieval system **incorrectly answered or refused to answer 81% of questions**."* … *"all models examined exhibit weaknesses, such as hallucinations, that limit their suitability for use by enterprises."*

That is the **best** model *with* retrieval, on questions the authors call *"clear-cut … a minimum performance standard."* Implications, taken at face value:

1. **A raw LLM summary of "why we traded" will frequently invent reasons, misattribute, or omit vetoes.** If the human trusts it, they approve/veto on fiction — which is *worse* than reading the raw digest, because fiction is more persuasive than a field dump.
2. **Retrieval alone is not a fix** — FinanceBench *is* a retrieval setting and still fails 81%. So the design needs more than "stuff the ledger into the prompt": it needs **(i) strict citation binding**, **(ii) a deterministic fact-check pass**, and **(iii) an explicit refusal path** ("no grounded evidence → emit `confidence=low` + no narrative").
3. **The digest must be additive, never authoritative.** The deterministic `auditor.py` digest stays the source of truth; the LLM prose is a *rendering layer* whose every numeric claim must trace to a ledger row the human can click.

### b.3 The mitigation literature — RAG + attribution is the lever

**RAG** (Lewis et al., NeurIPS 2020) `2005.11401` ✅ [arxiv.org/abs/2005.11401](https://arxiv.org/abs/2005.11401) — retrieval-augmented generation combines parametric + non-parametric memory and finds RAG models *"generate more specific, diverse and **factual** language"* with **provenance**. The mechanism that matters here: the model is *conditioned on retrieved passages*, so its output is anchored to text that exists, and the retrieval step is auditable. This is the structural fix for FinanceBench's "it just makes things up" failure — *anchor every claim to a retrieved chunk and cite the chunk*.

**Calibration:** RAG **reduces** hallucination, it does not eliminate it (FinanceBench itself uses retrieval and still fails). So RAG here is *necessary but not sufficient* — it is paired with the §d citation-binding and fact-check invariants.

---

## (c) Hallucination-mitigation stack — five layers, all cheap

The design goal: make a fabricated claim **structurally hard to emit** and **easy to catch** if emitted. Five layers, in order of cost:

| # | Layer | What it does | Cost | Failure mode it blocks |
|---|---|---|---|---|---|
| **1** | **Retrieval, not recall** | The model never summarizes "from memory." Every input token is a retrieved ledger row / news chunk. Prompt is *only* retrieved context. | Low (local index) | Fabricated trades/vetoes that never happened |
| **2** | **Citation binding** | Every sentence in the prose must carry `[Cn]`; each `Cn` is an opaque ID for a specific retrieved chunk. **No citation → sentence stripped** by a post-processor. | Free (regex) | Misattribution, invented reasons |
| **3** | **Deterministic fact-check** | A cheap validator re-derives every *number* in the prose (fill count, net PnL, veto reason) from the ledger and rejects/sanitizes the digest if any mismatch. Numbers are never LLM-owned. | Free (Python) | FinanceBench-class numeric hallucination |
| **4** | **Explicit refusal path** | If retrieval returns <N chunks or fact-check fails, the agent emits `confidence=low` + the *raw* deterministic digest only. **"I don't know" is a valid, first-class output.** | Free | Over-confident fiction under sparse evidence |
| **5** | **Schema fence + journaling** | Output is `{summary, bull_case[], bear_case[], risks[], blind_spots[], citations{}, confidence, recommended_action}` — anything outside schema is dropped (`05-fleet-llm-edge.md:185`). Raw I/O journaled to the hash-chained ledger (`auditor.py:23-25`) for post-hoc audit. | Free | Prompt-injection / shape drift |

Layer 3 is the one that directly answers FinanceBench: **the human-facing prose may be fuzzy, but the numbers are re-derived from the ledger, so the LLM cannot lie about a fill that didn't happen.**

---

## (d) `AdvisoryDigestAgent` — design

### d.1 Position in the codebase (read-only, additive)

```
   DecisionLedger (journal/decisions.jsonl)   ──┐
   news/event corpus (research/ + feeds)      ──┼──► RAG index ──► AdvisoryDigestAgent
   analyst signals (signals.py, memory.py:126)──┘     (cheap LLM,   │
                                                        1×/day)       ▼
                                                   cited digest JSON ──► fact-check ──►
   ComplianceAuditor.digest() (auditor.py:27)  ──────────────────────────►  render  ──► Notifier.send()
                                                                          (deterministic prose    (notify.py:42)
                                                                           + raw digest appended)
```

It runs **once per `digest_every` cycles** (`config.py:41`, default 24), invoked at `runner.py:119-124` — the *exact* site that already pushes the daily digest to ntfy. The agent sits **between** `state.digest` (deterministic, untouched) and `notifier.send(...)`: it renders an `advisory_prose` field, **appends** the raw deterministic digest below it (so the human always has the ground-truth numbers), and pushes via the existing `MultiNotifier` fan-out (`notify.py:71-98`). No new execution coupling; the digest path remains advisory-only by construction.

### d.2 RAG index — what gets indexed, and chunk IDs

| Source | Content | Chunk granularity | Citation prefix |
|---|---|---|---|
| **Decision ledger** (`journal/decisions.jsonl`) | every `signal`, `debate`, `trade_proposal`, `risk_decision`, `risk_veto`, `fill` (`auditor.py:23-25`) | one ledger row = one chunk | `L<seq>` (the ledger's hash-chain seq no.) |
| **News / events** | MEXC announcements, listing/delisting events (`15-mexc-listing-detection.md`), unlock calendar (`22-token-unlocks.md`) | one announcement = one chunk | `N<id>` |
| **Research / whitepapers** | the `research/agents/*.md` corpus (this fleet's own evidence base) | one section (##) = one chunk | `R<agent>-<section>` |
| **Analyst analytics** | `ReflectionMemory.analytics()` (`memory.py:126-127`) | per-source stat block | `M<source>` |

Retrieval = **hybrid**: exact-match on symbol/seq (cheap) + a tiny embeddings index over prose chunks. The index is **rebuilt daily from the append-only ledger** — no live write path, no drift. Critically, **the ledger rows are the ground truth**; the LLM cannot invent a chunk because every `[Cn]` must resolve against an indexed ID or the sentence is stripped (layer 2).

### d.3 Digest format (the schema-fenced output contract)

```jsonc
{
  "date": "2026-06-23",
  "summary": "Fleet wants to add FET/USDT (1.2% cap) and exit PEPE. A 1.2% supply unlock Fri [N42] is the main risk.",
  "bull_case": [
    {"text": "FET funding flipped negative while price held support [L1041]", "cite": ["L1041", "Mmarket"]},
    {"text": "net score 0.62, market + macro agree; sentiment neutral [L1039]", "cite": ["L1039"]}
  ],
  "bear_case": [
    {"text": "scheduled unlock Fri 14:00 UTC, 1.2% float [N42]", "cite": ["N42"]},
    {"text": "post-listing drift documented on MEXC small-caps [R15-d]", "cite": ["R15-d"]}
  ],
  "risks": ["unlock-driven dump within 48h", "single small-cap concentration"],
  "blind_spots": [
    "no on-chain whale data for FET this cycle (agent 27 not run)",
    "sentiment analyst is neutral — not confirming the long"
  ],
  "confidence": 0.55,
  "recommended_action": "wait",
  "citations": {
    "L1041": {"kind": "fill", "seq": 1041, "hash": "…"},
    "N42":   {"kind": "news", "url": "…"},
    "R15-d": {"kind": "research", "path": "research/agents/15-mexc-listing-detection.md#d"}
  }
}
```

**`blind_spots` is the field that earns the agent its keep** — it surfaces what the fleet *didn't* consider (analysts that stayed neutral, data sources not run, research notes that would contradict). This is the "surface blind spots" deliverable in the brief, and it is *additive*: it never blocks a trade, it just tells the human what they're flying blind on.

**`recommended_action ∈ {approve, veto, wait}`** is **advisory only** — it is a *suggestion to the human*, never an instruction to the fleet. A `veto` here means "the digest thinks you should veto," not "a veto fires." The deterministic risk gate (`guardrails.py:189-233`) is the only real veto.

### d.4 Confidence — what it means and how it's bounded

`confidence` is **not** a probability of profit (the docs are explicit that LLMs have no such edge — `RESEARCH-SYNTHESIS.md:39`). It is a **grounding score**: roughly, the fraction of prose claims that survived citation binding and fact-check, modulated by retrieval density. Concretely:

```
confidence = 0.5 * (cited_sentences / total_sentences)
           + 0.3 * (1 if fact_check_ok else 0)
           + 0.2 * min(1, retrieved_chunks / MIN_CHUNKS)
```

So `confidence=1.0` means *"every sentence is cited, every number checks out, retrieval was dense"* — **not** "this trade will work." A high-confidence digest of a losing trade is still a losing trade; confidence is about *trustworthiness of the narrative*, not direction. This distinction must be in the ntfy body verbatim, or the human will misread it.

### d.5 ntfy push — rendering + the "numbers are re-derived" promise

The push body is **deterministic prose rendered from the validated JSON**, not the LLM's raw text:

```
RAPANA ADVISORY · 2026-06-23 · confidence 0.55 (grounding, NOT profit) · RECOMMEND: wait

WANTS TO DO: +FET/USDT (≤1.2% cap), −PEPE.
BULL: funding neg + held support [L1041]; net 0.62 market+macro agree [L1039].
BEAR: 1.2% float unlocks Fri 14:00 UTC [N42]; post-listing drift on MEXC small-caps [R15-d].
RISKS: unlock dump <48h; small-cap concentration.
BLIND SPOTS: no whale/on-chain for FET this cycle; sentiment neutral (not confirming).
ACTION SUGGESTED: wait — unlock risk within 48h; revisit post-Fri.

--- raw deterministic digest (source of truth) ---
<state.digest appended verbatim from auditor.py:27-55>
```

Two non-negotiable rendering rules:
1. **The raw deterministic digest is always appended.** The human can always ignore the prose and read ground truth. The LLM prose is a *convenience layer*, never a replacement.
2. **Every number in the prose was re-derived by the fact-checker from the ledger** (layer 3), so a hallucinated quantity is sanitized to `?` before it ever reaches ntfy.

The push rides the existing `NtfyNotifier` (`notify.py:42-63`) → `MultiNotifier` fan-out (`notify.py:71-85`) → `build_notifier` (`notify.py:88-98`). **No new transport code.** Title length, tags, and HTTP retry are already handled.

---

## (e) Cost & latency — one run/day, cheap model, strict citation

| Component | Cost (2026 ballpark) | Notes |
|---|---|---|
| **LLM call** | **~$0.001–0.01 / digest** | One call/day. A cheap instruction-tuned model (8B-class, or a low-tier API) suffices — the task is *rendering retrieved evidence*, not open-ended reasoning. FinGPT-class (`2306.06031`) or any small hosted model. At 1 run/day this is **<$4/yr** even at the high end. |
| **Embeddings index** | ~$0 (local) | The corpus is small (ledger rows + ~40 research notes + daily news). A local FAISS/sqlite index rebuilds in seconds. No per-query API cost. |
| **Fact-checker** | $0 (Python) | Re-derives numbers from ledger; pure local compute. |
| **ntfy push** | $0 | `ntfy.sh` free tier / self-hosted (`config.py:46`). |
| **Latency** | **5–30s end-to-end** | Embeddings + one LLM call + render. Runs off the order path on the daily digest tick (`runner.py:119`), so it never lengthens a cycle. |

**Why a cheap model is fine here:** the model is *not* forecasting; it is *rearranging retrieved, fact-checked evidence into sentences with citation tags.* That is a bounded structuring task (`32-llm-papers.md:39`), and the citation + fact-check layers (§c) catch the errors a small model makes. Spending on a frontier model would raise cost ~50× for no safety or quality gain once layers 2–3 strip/halt the bad output. The economics flip *because* the output is advisory and validated — you can tolerate a dumber model behind a strict gate.

---

## (f) Honest summary — what this is and is not

**Is:** a **once-daily, read-only, RAG-grounded narrative rendering** of the ledger + corpus into a cited bull/bear/risk/blind-spot brief with a grounding-confidence score and an advisory human action, pushed to ntfy over the *existing* digest transport. It is the "explain to the human" value made concrete — the one LLM use the literature unanimously endorses (`32-llm-papers.md:80-88`) at near-zero safety cost, because it adds no execution path and the deterministic digest is always appended as ground truth.

**Is not:** a price predictor (`RESEARCH-SYNTHESIS.md:39`), an order router (`RESEARCH-SYNTHESIS.md:65`), or a substitute for the deterministic risk gate. `confidence` is **grounding quality, not profit probability** — misreading it as the latter is the single biggest user-error risk and must be labeled in every push.

**The non-obvious load-bearing finding:** **FinanceBench (`2311.11944`) — GPT-4-Turbo + retrieval wrong/refused 81% of clear-cut financial QA** — means an *ungrounded* version of this agent is worse than the raw digest it replaces (persuasive fiction > boring truth). The entire value proposition hinges on layers 2–4 (citation binding, deterministic fact-check, explicit refusal). **Ship those before the LLM, not after.** If the fact-checker or citation binder is missing, the agent must degrade to "raw digest only" — never to "LLM prose without a leash."

**Calibration notes:** (i) Every cited paper's abstract was fetched live ✅; I did not re-fetch full PDFs, so FinanceBench's "81%" is the abstract figure on a 150-case sample — directionally decisive, treat the exact number as indicative. (ii) BloombergGPT/FinGPT make **no OOS returns claim**; citing them here is strictly for the comprehension/structuring competence, consistent with `32-llm-papers.md:29-31`. (iii) The RAG hallucination-reduction claim (Lewis `2005.11401`) is general-domain; its *magnitude* on finance text specifically is not separately measured here, which is exactly why layers 2–4 are non-optional. (iv) `recommended_action` is a suggestion label, not a control signal — it must never be wired to anything that moves capital, or this agent has silently crossed the fence the docs draw at `RESEARCH-SYNTHESIS.md:65`.

---

## (g) Sources (all fetched live ✅ this session)

- ✅ **BloombergGPT** — Wu, Irsoy, Lu, Dabravolski, Dredze, Gehrmann, Kambadur, Rosenberg, Mann, 2023 — `https://arxiv.org/abs/2303.17564` (50B-param finance LLM; edge is NER/QA/summarization, not alpha)
- ✅ **FinGPT** — Yang, Liu, Wang, 2023 (IJCAI FinLLM, Best Presentation) — `https://arxiv.org/abs/2306.06031` (open-source, data-centric; "robo-advising" = report gen)
- ✅ **FinanceBench** — Islam, Kannappan, Kiela, Qian, Scherrer, Vidgen, 2023 — `https://arxiv.org/abs/2311.11944` (open-book financial QA; **GPT-4-Turbo + retrieval wrong/refused 81%**; hallucinations disqualifying for enterprise — load-bearing counter-evidence)
- ✅ **RAG** — Lewis, Perez, Piktus, Petroni, Karpukhin, Goyal, Küttler, Lewis, Yih, Rocktäschel, Riedel, Kiela, NeurIPS 2020 — `https://arxiv.org/abs/2005.11401` (retrieval-augmented generation → more factual, provenance via non-parametric memory)
- **TradingAgents** `2412.20138`, **FinRobot** `2405.14767`, **LiveTradeBench** `2511.03628`, **AI-Trader** `2512.10971`, **TradeTrap** `2512.02261` — surveyed in `32-llm-papers.md:26-34` (report-generation / risk-veto orientation, predictive edge fails OOS)
- **Repo base facts:** `RESEARCH-SYNTHESIS.md:39,65,101` · `32-llm-papers.md:28,80-88` · `05-fleet-llm-edge.md:127-134,185` · `auditor.py:23-55` · `notify.py:42-98` · `config.py:41,45-46` · `runner.py:119-124` · `memory.py:126-127` · `guardrails.py:104-126,189-233`

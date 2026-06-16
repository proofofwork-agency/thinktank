# UltraBrain — The Good, the Bad, and the Ugly

*Multi-agent deep critique, June 2026. Five agents: research, hostile code review,
devil's-advocate dismantling, "what's worth keeping," and solutions architect.
This file consolidates their findings into one verdict.*

---

## TL;DR — the one-paragraph verdict

UltraBrain correctly diagnoses two real diseases (context pollution; sampled-tokens-as-reasoning)
and prescribes a treatment **that does not contain the active ingredient it claims**. The
"verifier" the whole epistemic edifice rests on is, by inspection of `verifier.py`, an
**arity check + a substring match + first-writer-wins functional-contradiction**. It contains no
truth oracle — the rotterdam demo only "works" because amsterdam was pre-loaded; reverse the
order and rotterdam is permanent truth, and there is no path to correct it. So the headline
*"hallucinations don't exist"* is **false as written**. **But** the load-bearing architecture —
verifier-as-only-write-path, append-only provenance ledger, proof-trace answers, verified-trace
training pipeline — is genuinely valuable, defensible, and under-occupied at the intersection it
occupies. The fix is not to abandon the idea; it is to (a) stop calling a syntactic gate a truth
oracle, (b) replace first-writer-wins with a defeasible Truth-Maintenance System, and (c) point
the whole thing at a domain where real oracles already exist (code/IaC) so the verifier is the
*toolchain*, not a hand-written regex. Grade: **one fatal epistemic flaw, several structural
fixable ones, one real kernel of value worth fighting for.**

---

## Part 1 — The Good (load-bearing, keep, defend)

These are the ideas that survive even if the rest of the concept collapses.

### G1. Verifier-as-only-write-path + evidence/belief asymmetry ★ strongest idea
Raw experience is always stored (cheap, noisy, plentiful); trusted memory is updated only
through the gate (expensive, sparse, verified). Three consequences that most agent systems lack:
- **Recoverability** — improve the verifier later, re-run the gate over the raw log.
- **Dual-labeled training data for free** — accepted = positives, rejected = negatives, repairs = corrections.
- **Auditability of refusal** — every "no" has a recorded reason.
This is the single most exportable idea in the concept.

### G2. Append-only per-user ledger with provenance + retract (event sourcing for memory)
Beats vector DBs on: auditability, first-class provenance, retractability without contamination,
contradiction as a write-time error (not a retrieval-time surprise), free multi-tenancy. This is
**event sourcing applied to agent memory** — an under-used pattern, independent of Datalog.

### G3. Proof-trace answers ("why")
`why grandparent(lucas,jan)` returns the derivation tree. Beats "the model said so" because it is
*falsifiable at retrieval time* and supports **correction propagation** (retract a premise → every
dependent belief is identifiable). Critical for compliance/audit/safety domains where "the AI said
so" is legally insufficient.

### G4. Verified-trace-as-training-data pipeline + promotion gate ★ highest compounding upside
The binding constraint on fine-tuning in 2026 is labeled-data quality. A verified agent generates
formally-labeled training data as a *side-effect of operation*. With the promotion gate
(`ROADMAP.md:299-321`: "new adapter replaces old only if evals improve AND false writes don't rise"),
self-poisoning is prevented. **Conditional on a high-verifier-density domain** (code), this is the
most valuable idea in the whole concept. In the toy domain it is a curiosity.

### G5. The code/config/IaC domain bet
Verifier density (tests, typecheckers, linters, git, shell) × long horizon (months/years) × natural
predicate vocabulary all peak simultaneously. OPA/Rego *is* Datalog — config/IaC may be an even
stronger first domain than code. **Where "verifiable" is a real moat**: compliance, audit,
safety-critical software.

### G6. Teacher-dependency rate as a metric
"What fraction of steps needed a teacher call, and is it declining?" is the quantitative answer to
"is the local system actually learning, or is it a thin wrapper around GPT-5?" Under-used in the
literature; should be standard.

### What is photogenic but NOT load-bearing (don't let it carry weight)
- The from-scratch 10M GPT (whitepaper itself flags this for stop-doing; the architecture is model-agnostic).
- Byte-BPE / manual attention / ~700 lines (craftsmanship, irrelevant to the thesis).
- "Sovereignty inversion" as slogan (the *verifier* does the work; the slogan sells it).
- Datalog specifically (any proof-carrying logic works; Datalog is just the cheapest).
- Markdown skills (that is Voyager's skill library in another format; retrieval is keyword-only).

---

## Part 2 — The Bad (real but fixable)

### B1. Substring faithfulness is fooled by short names [CRITICAL]
`verifier.py:94` uses `a.replace("_"," ") not in s`. Verified: `age(tim,30)` passes against
"the time is now 30" (tim ⊂ time); `capital(france,paris)` passes against "parisian".
**Fix:** token-set containment, not substring — tokenize both on word boundaries, require
`args_tokens ⊆ source_tokens`.

### B2. Non-pool entities are invisible to the dropped-entity check [CRITICAL]
`known_entities` only recognizes the ~150 hardcoded entities in `data/synth.py`. For any real user
text, "two-way faithfulness" silently degrades to one-way. **Fix:** the type/domain system (see B4).

### B3. No type checking — `capital(maria,asml)` verifies [CRITICAL]
`SCHEMAS` stores arity only. `age(amsterdam,paris)`, `works_at(maria,maria)` all pass. **Fix:**
declared argument domains per predicate (`capital : (COUNTRY, CITY)`).

### B4. Non-functional predicates have no contradiction check [HIGH]
`older(maria,jan)` and `older(jan,maria)` both verify; `parent` cycles accepted. Only 5 of 10
predicates are contradiction-checked.

### B5. "Semi-naive Datalog" is mislabeled — it's naive bottom-up [HIGH]
`_match` scans ALL facts for every body atom. The `must`/`used_must` mechanism only dedups yields;
it does not reduce join work. Per-query cost is O(N^B), not O(|∂F| × N^(B-1)).

### B6. Engine re-saturated from scratch on every query [CRITICAL perf]
Every `ask`/`why` reconstructs `Engine(...)` and calls `_saturate()`. With 10k facts and 10 rules
of body-length 2, that's ~10^8 fact-pairs per iteration per query. **Fix:** persist the closure,
delta-update on new facts/rules (real semi-naive), SQLite backing.

### B7. KB reads the entire JSONL on every construction; never compacts [HIGH]
Retracted facts leave dead entries read-and-discarded forever. **Fix:** snapshot + WAL + compaction.

### B8. Implementation correctness gaps (selection)
- One corrupted JSONL line kills the entire KB (`kb.py:16` crashes, no per-line try/except). [HIGH]
- Path traversal via `--user` (kb.py:13, no sanitization). [CRITICAL]
- No file locking — concurrent appends can interleave/corrupt past PIPE_BUF. [HIGH]
- No integrity checksums — tampered entries indistinguishable from real ones. [MEDIUM]
- Variables accepted as ground-fact args (`parent(maria,X)` stores X as a literal). [HIGH]
- Builtins with unbound args silently never fire — dead rules admitted with no diagnostic. [HIGH]
- `why`/`forget` crash on malformed input (no try/except, unlike `ask`). [MEDIUM]
- `is_q` heuristic: "however..." → misclassified as question. [MEDIUM]

### B9. Test coverage covers only the happy path
Every CRITICAL finding above is in an untested path. The suite verifies the DEMO.md scenario and
almost nothing else.

---

## Part 3 — The Ugly (fatal to the thesis as stated)

### U1. The verifier has no ground truth — it is first-writer-wins, not truth-tracking ★ the fatal flaw
Generate→Verify→Keep works in AlphaZero/AlphaProof/DreamCoder for one reason: **the verifier is an
independent, exogenous oracle** (game rules / Lean kernel / examples). UltraBrain's verifier is
*none of those*. The rotterdam rejection works only because amsterdam was loaded *first*. Reverse
the order → rotterdam is permanent truth. The system **refuses corrections** (no belief revision);
the only recovery is manual `forget`. A KB that refuses corrections is, over months of use, a KB
that entrenches its earliest mistakes. **Where does ground truth actually come from? Nowhere in the
loop — fully deferred to two human acts outside the system.**

### U2. The faithfulness check cannot establish truth, only token presence
It catches "the LM invented an entity absent from the sentence." It does NOT catch:
- **Faithful-but-false** ("rotterdam is the capital" — all tokens present, just false).
- **Reordered/role-flipped** ("the netherlands is the capital of amsterdam" — all tokens present).
- **Multi-word entities** outside the underscore-join trick.
So "hallucinations don't exist" reduces to "the LM can't insert un-sourced entities" — a vastly
narrower property than claimed.

### U3. The Cyc knowledge-acquisition bottleneck, relocated
Every new domain requires hand-authoring `SCHEMAS`, `FUNCTIONAL`, `PRED_HINTS`, `POOLS`, `STOP`,
repair regex. The "perception scales by swapping the model" claim is contradicted by the repair code
being hardcoded to the toy vocabulary. This is Cyc's authoring cost paid per domain, with no mechanism
shown to automate schema acquisition.

### U4. Redundancy with real verifiers — the architectural squeeze
In the chosen first domain (code), real oracles already exist (pytest, mypy, ruff, git, compiler).
Translating "the fix is verified by test X" into `fix_verified_by(change,test)` to derive over is a
*lossy re-encoding* of information strictly richer in the raw tool output. The symbolic core is
sandwiched: **where ground truth exists it's redundant with the toolchain; where it doesn't it can't
establish truth.** The middle ground it claims is mostly empty.

### U5. Expressiveness — Datalog can't express real knowledge
No negation, no time, no uncertainty, no aggregation. A "project brain" lives or dies on temporal
knowledge ("X was true, now Y is") — inexpressible. `meeting_time(m,"3pm")` and `meeting_time(m,"4pm")`
either contradict (refusing the update) or coexist ambiguously. The engine is a toy fragment of
Datalog, not Datalog.

### U6. The multi-tenancy justification contradicts the product
The thesis grounds "memory outside the model" in shared server serving. But the product is **local
single-user**. A local model serving one user has no multi-tenancy constraint — there is no reason it
can't hold personal state in adapters. **The motivating problem does not apply to the target
deployment.**

### U7. Several "implemented" features are vaporware
Cross-referencing ROADMAP claims against code: "skills improve behavior" (no agent loop reads/executes
skills; retrieval is keyword-only), "adapters train from verified traces" (no training pipeline, no
adapter architecture), "teacher dependency declines" (no tracking/gating code), "evals control
promotion" (evals.jsonl is written but never read), "the agent completes tasks" (it's a CLI command
dispatcher with no planner/tool-layer/loop).

### U8. 99%+ "held-out translation accuracy" measures interpolation, not translation
Holdout uses the same 5 templates and same ~120-entity pool as training. A regex over the same
templates scores ~100%. The number is real but meaningless outside the synthetic domain.

---

## Part 4 — What the research literature says

**VALIDATES the thesis:**
- **AlphaGeometry** (Trinh et al., *Nature* 2024) — the cleanest proof that neural-proposes /
  symbolic-verifies / keep-only-verified beats raw LLMs. Its symbolic engine is literally a
  "deductive database" of Horn clauses — UltraBrain's reasoner family. GPT-4 alone scored **0%** on
  the same benchmark; the neurosymbolic loop scored near IMO-gold.
- **DreamCoder** (Ellis et al. 2020) — wake-sleep library learning over verified traces. Direct
  intellectual parent of UltraBrain's skill-memory + verified-trace adapters.
- **Voyager** (Wang et al., NeurIPS 2023) — persistent, verified, composable skill library beats
  approaches lacking it. Validates the verified-skill-store thesis.
- **Soufflé / Datomic** — production-grade Datalog scales to huge fact sets; Datomic is
  architecturally almost identical to UltraBrain's "append-only ledger per user."
- **Lenat & Marcus 2023** (arXiv:2308.04445) — "what LLMs might learn from Cyc" is *almost the
  UltraBrain manifesto written two years earlier*.

**THREATENS the thesis:**
- **Cyc itself** (Liu 2025 obituary, yuxi.ml/cyc) — the 40-year existence proof that this exact
  thesis stalls at the *ingestion* step. "Publications involving Cyc typically described methods for
  *entering* information, rarely addressing applications out of it." UltraBrain's Perception+Gate is
  precisely that ingestion pipeline.
- **MemGPT / Generative Agents / Reflexion** — text-memory agents with far less machinery already
  work well. Reflexion hits 91% on HumanEval vs GPT-4's 80%, with no logic engine.
- **Self-Refine / Constitutional AI** — generate-then-verify with an *LLM* judge already works well
  enough to be real competition.
- **The decisive gap:** Generate→Verify→Keep is only proven where the verifier is *exact* (game
  rules, Lean, program execution). No paper found demonstrates it scaling to open-world factual
  knowledge the way it scales to proofs. **Two-way faithfulness is a syntactic proxy, not semantic
  truth.**

---

## Part 5 — Solutions (UltraBrain v2 design)

### S1. Solve U1 — replace first-writer-wins with a Truth-Maintenance System
Stop treating the verifier as a single boolean gate. A write now carries
`(claim, evidence, source_rank)`. Ground truth is a **graded spectrum**:

| Rank | Source | What it can verify |
|---|---|---|
| Oracle (highest) | executed tool: pytest/mypy/shell/git | "X is true because this command returned 0" |
| User | human assertion/correction | project facts, corrections |
| Consensus | ≥2 independent sources agree | corroboration raises confidence |
| Single source | a document/tool/teacher | "S claims X" — belief, not truth |
| LLM proposal (lowest) | perception/teacher | nothing on its own — proposes only |

Adopt a **justification-TMS (Doyle 1979; Forbus/de Kleer) with defeasible priorities (Nute 1994)**.
The TMS gives the dependency graph for automatic retraction; defeasible logic gives the precedence
policy. New event type `supersede(old, new, reason)` — "Amsterdam → The Hague" emits a supersede +
a higher-rank tell; the TMS replays, applies the precedence function `(source_rank desc, ts desc)`,
and re-derives everything that depended on the old belief. **No manual `forget`; no lost provenance.**
The precedence function is human-authored policy (the trust boundary); the LLM never decides who wins.

Rejected alternatives: ASP/CLingo (closed-world, hides revision); annotated/probabilistic logic
(invites the LLM-as-judge trap — where do the numbers come from?).

### S2. Solve U3 — let the tools define the schema (dissolve Cyc)
In a high-verifier-density domain, **the structure of the tool output *is* the schema**:
- `pytest --collect-only -q` → auto-emit `test_id(SYMBOL)`.
- `git diff --name-only` → `changed_file(PATH)`.
- `mypy --output json` → `type_error(PATH, SYMBOL, ERROR_CLASS)`.

For predicates not produced by a tool, use **teacher-proposes / meta-verifier-validates**: the
teacher proposes `{pred, arity, domains, intended_verifier, grounding}`; the meta-verifier checks
arity consistency, domain population, that a named verification path exists (kills the 5-of-10
predicates with no check), and grounding faithfulness. The `PRED_HINTS` regex disappears entirely.

**Irreducible human-authored residue** (cannot be learned without re-introducing Cyc): the precedence
policy itself, the set of trusted oracles, and the promotion-gate criteria. Everything else can be
bootstrapped.

### S3. Solve U4 — demote Datalog to the join/provenance/consistency layer
Datalog stops being "the reasoner over a closed KB" and becomes **the join layer over an evidence
store** populated by executed tools. The unit of memory is no longer `fact(pred,args)` but an
**evidence record**:
```
evidence(claim, oracle, command, output_digest, exit_code, ts, commit, source_rank)
```
The **proof is the tool output itself**, stored verbatim and content-addressed. The minimal
irreducible role for Datalog (what tools alone can't do): cross-source multi-hop joins, provenance
chains, contradiction detection across sources, short glue rules (`imports_broken(M) :- type_error(M,_,ImportError)`).
This is the **Datomic model** (facts with transaction time, Datalog as query/join over an immutable
log), not Prolog/Cyc.

### S4. Solve U5 — graduate to stratified Datalog + bitemporal versioning
Immediate step: **stratified Datalog with negation** (minimal extension, terminating semi-naive eval).
Add **bitemporal facts** — every claim carries `t_asserted` and `t_superseded`; queries run in
`now` / `as-of(T)` / `all` modes. This subsumes `valid_during` and needs no new engine feature beyond
passing a time predicate. Defer annotated/probabilistic logic to a later tier.

**Safety fix at rule admission (`verify_rule`):** enforce Datalog safety — every variable in a builtin
must be bound by a preceding positive literal. This turns silent-dead-builtin bugs into
admission-time rejections.

### S5. Solve the implementation bugs (B1–B8)
- Faithfulness → **token-set** containment, not substring.
- **Typed predicates** with declared domains (`capital : (COUNTRY, CITY)`).
- Persistence → **SQLite backing + WAL-structured JSONL + hash-chained lines + flock + snapshots + compaction**.
- Real **semi-naive** delta evaluation — persist the closure, update on deltas.
- Per-line try/except on KB load → quarantine corrupt lines, don't abort.
- `--user` sanitized against `^[a-z0-9_-]{1,64}$`.

### S6. The first decisive experiment
**Question:** Does verified persistent memory beat a frontier agent + tools + vector DB on the code
domain, *on the axes UltraBrain claims*?

Two systems, identical tools (read/grep/pytest/mypy/git), identical teacher, K=5 sessions with
restarts:
- **A — baseline:** frontier agent + tools + vector DB + provenance log.
- **B — UltraBrain v2** as specified above.

| Metric | v2 must |
|---|---|
| Task success (solve rate) | ≥ baseline (or within –5%) |
| Repeated-failure rate across sessions | **< 1/3 of baseline** |
| Context tokens re-sent over K sessions | **< 1/4 of baseline by session 5** |
| Provenance audit pass (human traces *why* a belief holds to a tool output) | **> 90%** |
| Teacher-dependency rate, session 1 → 5 | **monotone decreasing** |

**Pass criterion:** v2 must *win* on {repeated-failure, context-resend, provenance} AND *not lose*
on task success. That conjunction is the only defensible "worth building" result. This experiment is
NOT in the current roadmap and it is the one that decides everything.

### S7. The honest re-scoped thesis
Replace *"hallucinations don't exist"* (false) with:

> **UltraBrain v2, in high-verifier-density domains:**
> - Every belief the agent *acts on* is either the output of an **executed oracle** (test, compiler,
>   shell, user correction) or an explicitly **annotated, provenance-bearing, defeasible** claim.
> - No belief is permanent: a later, higher-precedence correction **automatically supersedes** it and
>   **re-derives** everything that depended on it, with no residue and no manual `forget`.
> - Any belief the agent holds can be traced, in a proof chain, to the **exact tool command and
>   output** (at a named commit) that established it.
> - The perception model **proposes**; the tools and the deterministic precedence function **decide**;
>   the ledger **remembers**.
>
> *Hallucinations don't vanish from the world. They vanish from trusted memory — because nothing
> enters it that an oracle didn't produce or a deterministic policy didn't rank. Where no oracle
> exists, the system makes no truth claim; it stores belief and says so.*

---

## Additions to the kill criteria

The existing criteria (`ROADMAP.md:382-391`) are reasonable but abstract. Add concrete tripwires:

1. **The first-writer-wins test.** Commit a *wrong* fact before the right one, then present the right
   one. If the system cannot revise without manual `forget` by Milestone 3, the "months-long brain"
   claim is dead.
2. **The real-ground-truth redundancy test** (= experiment S6). If a frontier agent + tools + vector
   DB + provenance logging matches UltraBrain on the roadmap's own benchmark suite, the symbolic
   complexity is unjustified → pivot to "auditability layer on top of a frontier agent."
3. **The faithful-but-false test.** Inject 100 faithful-but-false statements. If acceptance is ~100%
   (it will be), retire "hallucinations don't exist" permanently.
4. **The temporal-knowledge test.** If the system can't represent a single belief change without
   manual retract by Milestone 3, the "project brain" product is not viable as specified.
5. **Schema-authoring ratio.** Track `#predicates / #human-authored-schema-lines`. Kill if it doesn't
   improve ≥3× after the first domain — that's the Cyc tripwire, made numeric.

---

## The minimal viable re-architecture (build order)

1. **Evidence-record store** + SQLite/WAL/hash-chain (replaces the JSONL-into-a-set).
2. **Two real tool-oracle verifiers** — pytest and git diff — generalizing the existing in-repo
   oracle precedent.
3. **TMS belief layer** with `supersede` + precedence function (fixes U1).
4. **Stratified, safety-checked Datalog** over the evidence store (fixes U5).
5. **Schema bootstrap** from `pytest --collect-only` + `git diff` (fixes U3).

The toy geo KB is retired to a test fixture.

---

## One-line bottom line

UltraBrain's **architecture** (verified-write-gate + provenance ledger + proof-carrying memory +
verified-trace training pipeline) is genuinely valuable, defensible, and under-occupied at the
intersection it occupies — but its **headline rhetoric** (sovereignty inversion, "hallucinations
don't exist", from-scratch-or-die) oversells what is, at root, a well-engineered application of
event sourcing + formal verification + the AlphaZero rule to *relational knowledge*. Point it at
code or IaC, ship the verifier-coverage problem first (make the toolchain the oracle), and the
verified-trace training pipeline alone could be the most valuable thing in the concept. **The good
parts don't need the symbolic core as it stands; the symbolic core needs to become the join layer
over real oracles to earn its keep.**

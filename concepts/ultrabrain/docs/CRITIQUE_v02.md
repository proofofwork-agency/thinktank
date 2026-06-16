# UltraBrain v0.2 — Re-Analysis (The Good, the Bad, the Ugly, Round 2)

*Multi-agent re-review after the v0.2 changes. Three agents: hostile code review,
devil's-advocate re-assessment, and math-first pivot strategist. This file is the
delta against `CRITIQUE.md` (the v0.1 verdict). Read that first.*

---

## TL;DR — the v0.2 verdict in one paragraph

**The fatal flaw is half-fixed, half-renamed.** The headline marketing was correctly
retired ("hallucinations don't exist" → "unsupported model proposals do not become trusted
memory" — now *true* and tested). A real narrow oracle exists (`math_core.py`). The evidence
record with `output_digest` + `commit` is a genuine audit-substrate improvement. **But** the
prescribed fix for the fatal flaw — the Truth-Maintenance System — was *specified, not built*:
`supersedes` is a stored field that **nothing reads**, conflicting oracle beliefs still coexist,
and there is no retraction mechanism. Meanwhile two **new** critical issues appeared: the trust
boundary is bypassable by a single string argument (`source_type='oracle'`), and the evidence
store is **untyped** while the KB is typed — so the two memory systems contradict silently.
**Re-grade: v0.1 = "fatal epistemic flaw." v0.2 = "defensible narrow thesis with one renamed
flaw and one misleading dead field."** The concept has crossed from *broken* to *worth building*
— but only conditionally, gated on (1) the EXPERIMENT.md head-to-head actually producing numbers,
and (2) the TMS being built or deleted.

---

## Part A — What v0.2 FIXED (verified, not just claimed)

15/15 tests pass. Verified improvements:

| v0.1 flaw | v0.2 fix | Verdict |
|---|---|---|
| C1 substring faithfulness (`tim ⊂ time`) | token-set containment `verifier.py:143` | **PARTIAL** — sound for single tokens, but PERSON open-world fallback still leaks (`parent(123,maria)` verified from "maria saw 123") |
| C3 no type checking (`capital(maria,asml)`) | `_domain_ok` with COUNTRY/CITY/PERSON/... `verifier.py:106-151` | **PARTIAL** — the named case is fixed; numeric strings slip into PERSON |
| C6 variables as ground args | rejected `verifier.py:138` | **FIXED** |
| C7 silent dead builtins | "must be bound first" `verifier.py:170-176` | **FIXED** |
| D1 path traversal via `--user` | `identity.validate_user_id` `^[a-z0-9_-]{1,64}$` | **FIXED** |
| D3 one bad line kills the KB | per-line try/except + quarantine to `.bad` `kb.py:30-35` | **FIXED** (minor leak: `.bad` re-appended on every reload) |
| U1 (rhetoric) "hallucinations don't exist" | WHITEPAPER re-scoped to "unsupported proposals don't promote" | **FIXED** — the narrow claim is now true and tested |
| U1 (mechanism, math domain) | `math_core.py` exact-rational linear solver with proof steps | **FIXED for math only** — real oracle, AlphaGeometry-family |
| U4 (storage half) | evidence records carry command/output_digest/commit/exit_code | **PARTIAL** — provenance substrate is real; reasoning half unbuilt |

**The single most important non-code improvement:** the WHITEPAPER no longer oversells.
§3 now says "Faithfulness is not truth." §5 says "Open-world truth is not solved by token
faithfulness." This is the epistemic humility CRITIQUE.md S7 demanded.

---

## Part B — The Ugly (fatal-ish, still open or newly introduced)

### U1-v2. The TMS was specified, not built — `supersedes` is dead code ★ still the #1 issue
This is the gap that was *supposed* to be closed. CRITIQUE.md S1 prescribed a justification-TMS
with a `supersede(old,new,reason)` event that retracts dependents automatically. What shipped:
- `record_belief(..., supersedes=None)` accepts the field and stores it (`evidence.py:101`).
- **No caller ever passes it** — every call site uses the default `None`.
- **No code ever reads it.** `active_beliefs()`, `why()`, nothing consults it.

Worse, `active_beliefs()` (`evidence.py:121-129`) keys precedence on the **exact claim string**.
So `pytest_passed(0)` at commit A and `pytest_failed(1)` at commit B are *different strings* →
they **coexist as two active beliefs forever**. The system cannot reconcile conflicting oracle
output. There is no retraction API. Recording `status='retracted'` does NOT remove a belief from
`active_beliefs()`. **This is the v0.1 disease (refuses corrections) lifted into the evidence
store.** The rank ladder addresses cross-source-type disputes on the *same* claim; it does
nothing for *incompatible* claims at the *same* rank.

**The docs imply revision exists ("retractable memory"). The code does not deliver it.**
Either build the TMS or delete the field and the "retractable" language.

### U2-v2. The trust boundary is bypassable by one string argument ★ NEW critical
`source_type` is a caller-supplied parameter with no authentication. Verified:
```
agent.propose_belief('made_up_fact(x)', source_type='oracle')
  → status='active', source_rank=4, in active_beliefs=True
```
A teacher (or any caller) passing `source_type='oracle'` gets rank 4 and active status.
`tell()`'s `trusted_source = source not in ("teacher","llm")` is a **denylist, not an allowlist**
— `source="assistant"` writes trusted memory. The invariant "the LLM never writes trusted memory"
is enforced by **string convention**, one stack frame from the LLM. No capability token, no
signed source, no type-level distinction between `UserTell` and `LLMProposal`.

### U3-v2. Two uncoordinated memory systems (KB typed vs Evidence untyped) ★ NEW structural
The KB is typed (`(COUNTRY, CITY)` tuples, gated by `verify_fact`). The evidence store accepts
**arbitrary string claims** — `"capital(netherlands,amsterdam)"`, `"pytest_passed(0)"`,
`"completely_arbitrary_nonsense(!!!, 42)"`, even `""`. All become active beliefs. Nothing joins
the two stores. `agent.ask()` queries the KB; `agent.why_belief()` queries evidence. A typed-KB
rejection of `capital(maria,asml)` can coexist with an evidence active belief of the same string.
**The boundary that matters most is the least-checked.**

### U4-v2. Math-first parks the project in the redundant half (CRITIQUE.md U4, alive)
`run_git_diff`/`run_pytest` produce claims that are **literal stringifications of tool output**.
Nothing derives `imports_broken(M) :- type_error(M,_,ImportError)`. The evidence store is a
**provenance-indexed cache of subprocess output**, not a reasoning layer. The "join layer over
evidence" — the irreducible role that would justify the symbolic core — is unbuilt. Same disease
in math: `solve_linear` and `verify` are the *same code path*, so there is no Generate→Verify
distinction (Generate is redundant). The architecture's most distinctive machinery (graded source
ranks, TMS, belief revision) is **completely unexercised** in math, because math has no
controversies.

---

## Part C — The Bad (real, fixable, newly found)

### Code defects (verified by execution)
- **B9** `math_core._clean` silently misparses `x2` as `x*2`: `solve('x2 = 6')` → `x=3` (wrong;
  user meant x²). Implicit-mult regex can't disambiguate. [HIGH]
- **B10** `verify()` swallows ALL exceptions as "rejected" — real verifier bugs get mislabeled as
  user errors; `kind` always becomes `"math"` on exception. [MEDIUM]
- **B11** `run_pytest` with `--co` (collection only) → `pytest_passed(0)` active belief though no
  tests ran. Claim conflates exit code with test outcome. [MEDIUM]
- **B5/B6** oracle subprocesses have no `try/except` (crash if git/pytest missing) and no
  `timeout=` (a malicious git hook hangs the agent forever). `_commit` runs on every
  `record_evidence` — worst offender. [HIGH]
- **B7** `cwd` unvalidated — `run_git_diff('/etc')` reads arbitrary git state. [MEDIUM]
- **B14** `output_digest` is stored but **never verified** anywhere — provenance theater, not
  tamper-evidence. [MEDIUM]
- **B13** no file locking on any append path (D2 unchanged). [MEDIUM]

### Still-open v0.1 issues
- **S1** Engine re-saturated per query (`self_learning.py:364`, `brain.py`). O(N^B) every `ask`.
- **S2** "semi-naive Datalog" docstring still mislabels naive-with-delta-guard evaluation.
- **U5** no negation/time/uncertainty in Datalog.
- **V1–V5** vaporware: skills still keyword-only retrieval with no executing loop; no adapter
  trainer (train.py is disjoint from training_queue.jsonl); no teacher-dependency tracking;
  evals.jsonl written but never read.

### Test coverage gaps (the adversarial test exists but is thin)
No test for: `supersedes`/revision path; oracle-overrides-user precedence; teacher claiming
`source_type='oracle'` is rejected (it isn't — that's why U2-v2 ships); `status='retracted'`
actually retracting; PERSON open-world abuse; missing git/pytest binaries; math misparses;
subprocess timeout; `.bad` append growth.

---

## Part D — The Good (genuinely better, keep and build on)

1. **The re-scoped thesis is now defensible.** "Unsupported model proposals do not become trusted
   memory" is true, tested (`test_teacher_proposal_is_untrusted_without_oracle`), and the right
   scope. A research critic can now describe UltraBrain without footnote-correcting every sentence.
2. **`math_core.py` is a legitimate AlphaGeometry-family oracle** — exact `Fraction` arithmetic,
   correct linear solver, honest nonlinear rejection, equality-preserving proof steps. It proves
   the *mechanism* (generate→verify→keep works when the verifier is exact) within its narrow range.
3. **The evidence-record shape** (`output_digest`, `commit`, `command`, `exit_code`, `verifier`)
   is a real auditability gain over a vector DB for compliance use cases. **Keep this substrate.**
4. **EXPERIMENT.md is the right decisive test** and it's now written down. The team knows what
   would kill or validate the architecture; they just haven't run it yet.
5. **Honesty about what isn't built** (ARCHITECTURE/EXPERIMENT docs say "build Tier 3 TMS *after*
   the experiment") — *except* on the supersession point, where the dead field creates a false
   impression.

---

## Part E — The remaining bar (the hard gate)

The concept has crossed from *broken* to *conditionally worth building*. Four items, in priority:

### 1. Build or delete the TMS (non-negotiable for honesty)
Either wire `supersedes` to a real dependency graph with automatic dependent-retraction, or remove
the field and the "retractable" language. Conflicting oracle beliefs must reconcile. **This is the
exact defect S1 was supposed to close; the closure is a placeholder.**

### 2. Make the trust boundary an invariant, not a convention
Replace the `source` string denylist with a capability: distinct `UserTell` / `LLMProposal` /
`OracleRecord` types, where only the first two constructors are exposed and the oracle
constructor requires a real subprocess result. No caller should be able to mint an active belief
by passing a string.

### 3. Reconcile the two memory systems
Either KB facts become a *projection* of the evidence store (one source of truth, typed at
projection time), or the evidence store stops accepting untyped claims that overlap the KB's
typed predicates. As-is, they contradict silently.

### 4. Run EXPERIMENT.md — and stop adding math rungs until you do
The decisive head-to-head (`UltraBrain v0.2` vs `frontier agent + tools + vector DB + provenance
log` on the code domain) is the only thing that justifies the symbolic core. **Treat math-first
as a plumbing milestone with a hard timebox, not a curriculum.** The math domain cannot validate
the architecture because (a) it has no controversies to exercise the TMS, (b) `solve_linear` and
`verify` are the same code path so there's no perception/verification gap, and (c) it's a strict
subset of SymPy. If the team is still adding math rungs in month 3, the pivot has become the
evasion the v0.1 critique warned about.

**Success milestone for math (if pursued):** a word-problem pipeline end-to-end — generator
emits (english, equation, answer); adapter trained *from training_queue.jsonl* translates
held-out English; verifier checks the answer; trained adapter beats untrained baseline; evals.jsonl
is *read* by a promotion gate. All five = compounding learning. Anything less = a calculator with
a log.

---

## The one-line bottom line (v0.2)

UltraBrain v0.2 retired the false marketing and built a real narrow oracle and a real audit
substrate — so the thesis is now **defensible** where it was **incoherent**. But the prescribed
fix for the fatal flaw (the TMS) is a stored field that nothing reads, two new critical issues
appeared (trust-boundary bypass; untyped evidence vs typed KB), and the math-first pivot parks
the project in the one domain where the architecture's distinctive machinery is *most idle*. The
concept is no longer broken; it is **conditionally worth building** — gated on building/killing
the TMS, hardening the trust boundary, reconciling the stores, and running the decisive experiment
before adding another curriculum rung.

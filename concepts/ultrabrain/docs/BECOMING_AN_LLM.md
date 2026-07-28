# Can UltraBrain become a full-fledged LLM?

*An audit of the actual tree (2026-07-28), the four ceilings that stop it, and the four
assumptions you have to drop to get past three of them. Every number below was measured on this
tree, not estimated. One central claim was falsified by Codex mid-analysis and is recorded as
falsified — see §3, Bias 2.*

Short answer, up front:

> **No — and the reason is not compute, not the model, and not the security blocker everyone has
> been staring at. It is `run_verified_search.py:161`.** Measured: at `--n 64` the forge
> generates **384 candidates, judges 7, keeps 6, and discards 377 unverified** — 176 of them
> purpose-built hard negatives. `--n 8` and `--n 64` do byte-identical work. The search does not
> search, and the forge's lifetime output is capped at `len(tasks)` = **34**.
>
> Three of the four ceilings come down. The fourth (world knowledge) is real, permanent, and
> should be **rented, not built**.

---

## 1. What is actually here

Measured, not claimed:

| | |
|---|---|
| **Writer** | `denoiser.py` + `diffusion.py` + `tokenizer.py` = **444 lines**, ~14M params, trained on **1.1 MB of Shakespeare** and **29.5 KB of code** |
| **Real writer** | `propose/llm.py` = **88 lines** of HTTP client pointed at someone else's Qwen3-Coder-14B |
| **Evaluator** | `verify/` = **~1,700 lines** (`judge.py` alone is 645) — 5 verifier grades, HMAC ledger, parent-owned oracle |
| **Tasks** | **34**, hand-written, across 5 `.jsonl` files |
| **Verified traces** | **6** |
| **Trainer runs** | **0** (`train_qlora.py` has `--dry_run`; no adapter exists in `checkpoints/`) |
| **Tests** | 103 (102 pass + 1 strict xfail documenting a live forgery vector) |

The ratio tells the story: **~4× more engineering in the evaluator than the writer, and the
writer is a museum piece.** That is not a criticism — the verifier is genuinely good work and the
right asset to have chosen. But the thing this repo calls "an LLM" is a 14M-parameter Shakespeare
model, and the thing doing the actual writing is a rented commodity.

---

## 2. The four ceilings

### Ceiling 1 — the corpus wall *(fatal, unfixable, stop trying)*

1.1 MB + 29.5 KB against a frontier corpus of ~15 trillion tokens: **seven orders of magnitude**.
On FLOPs: 14B params × 300B tokens ≈ 2.5 × 10²² ≈ **8 GPU-years on the RTX 5080**.

No cleverness closes seven orders of magnitude. Pretraining a competitive base on consumer
hardware is not hard, it is *arithmetically excluded*. Anything implying otherwise should be
deleted rather than de-scoped.

### Ceiling 2 — the dataset wall *(the actual killer)*

```python
# run_verified_search.py:160
outcome = gate.judge(task, candidate)
if outcome.certified:                     # <-- everything else is DISCARDED
    traces.append({...})
    solved += 1
    break                                 # <-- and at most ONE per task, ever
```

`gate.py:41` does the same to the ledger. **Measured** on `tasks/micro_codebench.jsonl` with the
repo's own `NoisyProposer` (45% gold / 35% distractor / 20% mutation):

| `--n` | candidates generated | judged | kept | discarded **unverified** | hard negatives thrown away |
|---|---|---|---|---|---|
| 1 | 6 | 6 | 5 | 1 | — |
| 8 | 48 | **7** | 6 | 41 | ~19 |
| 64 | 384 | **7** | 6 | **377** | **176** |

Three consequences, each worse than the last:

1. **The search does not search.** `--n 8` and `--n 64` perform *identical* work — 7 judgements,
   6 traces. The `break` fires on first success, so the compute knob is inert. Slice 1's headline
   result (coverage 50%→100% @ N=16) is the mechanism this pipeline is built to exploit, and the
   forge cannot exploit it.
2. **The most valuable data is discarded unverified.** `distractors` are *purpose-built* to pass
   weak tests and fail hidden ones — the ideal hard negative, hand-authored for exactly this. At
   N=64, 176 of them are generated and never even looked at.
3. **Max lifetime output = number of tasks.** 6 code tasks → the 6 traces on disk. Not a
   coincidence, a ceiling. And `open(args.out, "w")` overwrites, so it does not accumulate across
   runs either.

This is what makes "it can never become an LLM" true *today*, and it has nothing to do with
compute, models, or security.

### Ceiling 3 — the domain wall

`no evidence → no trusted belief → no clean training example` is the project's own rule, and it
confines data-minting to where a cheap sound oracle exists: code with tests, CAS identities,
physical invariants. Prose, summarisation, conversation, judgement — no oracle, no example.
`MANIFESTO_new_angle.md` concedes it: *"Open prose still belongs to prediction… we concede that
domain."* So even with Ceiling 2 fixed you get a **code/math specialist**, not an LLM.

### Ceiling 4 — the information wall *(the deepest)*

**A filter adds no information.** Training on your own certified outputs moves `pass@1` toward
`coverage@N` — a real gain, but **one-time and bounded**. When `pass@1 ≈ coverage@N`, the loop is
dry forever.

Verification is a *selection* operator. Selection without a *source of variation* is not
evolution — it is sorting. **This repo has an excellent selector and no source of variation.** It
is AlphaZero without self-play: the evaluation network, none of the games.

---

## 3. The four biases to drop

The brief said *set aside all biases and work around them*. Here they are, named — including the
one where I was wrong.

### Bias 1 — "sovereign means from-scratch"

The diffusion LM is carried as though it were the product. It is not; `propose/llm.py` is. Drop
from-scratch **as a writer strategy** (keep it for FIM/infilling, the one role where a
bidirectional denoiser genuinely beats same-scale AR — that part of the plan is right).

> **Sovereignty is not about who smelted the weights. It is about who owns the training
> environment.** Weights are Apache-2.0, free, and depreciate every six months. Environments
> compound.
>
> **UltraBrain is not a brain. It is a gym.** You do not build the athlete — you build the
> training regime, the curriculum, and the drug test, and swap athletes as better ones become
> free.

This is *more* anti-hegemonic than from-scratch, not less: it makes the hegemon's asset the
depreciating commodity and yours the durable one.

### Bias 2 — "verification must be sound to be useful" *(half right; my first answer here was falsified)*

**The half that holds.** Soundness is non-negotiable at the **trust boundary** (certifying to a
user) but not obviously required at the **training boundary** (deciding what to learn from).
RLHF trains on noisy human preference, DPO on pairwise ordering, process rewards are learned and
unsound — all work. That split is real and it is the right lens.

**The half that was wrong.** I claimed: *a forgery can only manufacture a false CERTIFIED, never
a false REJECT, because the attacker's incentive is acceptance — so reject data is sound by
construction and the loop is not blocked at all.* Codex was asked to attack it and **falsified it
on all counts** (ledger `c91f536e`):

- A **correct** `add` used the known `typing` residual to overwrite the worker's response with
  `999`; the honest worker MAC-signed it and `judge_v1` returned **REJECTED**. Authenticated
  false reject, reproduced.
- A function genuinely scoring **0/10** forged the signed response map to read **7/10**. Graded
  ordering is corruptible at the source.
- The incentive argument itself is unsound: **self-sabotage is rational** when the goal is
  poisoning the next model or making a sibling candidate look better. I reasoned about motive;
  integrity does not care about motive.

Two further findings matter *more* than the forgery:

- **Injection needs no gadget at all.** Candidate return values and exception messages flow
  **verbatim** into `Verdict.detail`. Codex injected a literal train-this-payload string through
  both routes. Harvesting rejects naively means training on attacker-authored text.
- **Reject details expose the parent's expected values.** Feeding them back would **leak the
  hidden oracle into the training corpus** — destroying the held-out property that the entire
  capability experiment depends on. This is the finding that reframes the problem.

**What survives, and it is the actual escape:** the residual bites only where **the verdict
depends on executing the candidate**. So move the loop off the executing path.

> **The symbolic path never executes anything.** `verifier_for` routes `kind=cas` to
> `CASVerifier`, which validates the candidate against an AST whitelist (`verifiers.py:45` — no
> `Attribute`, no `Subscript`, no strings, calls only into a fixed math whitelist) and *only
> then* sympifies with restricted locals. **No worker, no HMAC channel, no signed value stream —
> the verdict is decided wholly in the parent.** Every exploit Codex demonstrated lives in the
> `judge_v1` worker path, which the CAS path does not use.

So the honest, corrected form of Bias 2 is not "unsound signals are fine." It is: **stop trying to
make the executing path safe enough to learn from, and put the loop where verification never
executes anything in the first place.**

**That claim also went to Codex, and it came back `BROKEN TODAY` — with the architecture
surviving** (ledger `30847b56`). The distinction matters, so precisely:

*What holds.* **No AST-whitelist code-execution bypass was found.** The
no-string / no-`Attribute` / no-`Subscript` / fixed-call grammar *materially removes the entire
`judge_v1` forgery class*, and Codex's own strategic finding is that the symbolic path **does not
require the subordinate executor, because candidate code is never executed**. The escape route is
real.

*What is broken today* — three concrete defects, all reproduced here as well:

| Defect | Repro | Fix |
|---|---|---|
| **False certification of undefined objects** — sympy differentiates `oo`/`zoo`/`nan` as zero, so `oo`, `log(0)`, `1/0`, `0/0` all **certify** as antiderivatives of `0` (and `0**0 ≡ 1` by convention) | `cas_antiderivative('oo','0')` → CERTIFIED | reject non-finite/undefined candidates; this is *not* the intended removable-singularity slack |
| **Unbounded evaluation hangs the trusted parent** — inside the allowed grammar. `factorial(999999)` hung >8s locally; Codex hit SIGXCPU on `factorial(10¹²)`, `gamma(10¹²)`, `Float(Rational(1,3),10⁸)`, and uncaught `RecursionError`/`ValueError` | `v.verify(task, 'factorial(999999)')` | bound text/nodes/depth/arity; resource-limited CAS worker; **timeout ⇒ ABSTAIN** (the `Verdict` type already supports it) |
| **`detail` leaks the gold** — the same expected-value leak as `judge_v1`, on the "safe" path | candidate `0` vs gold `x**2+3*x+7` → detail `residual -x**2 - 3*x - 7 != 0`, algebraically the whole gold | persist enums/counts/digests only; never residuals or exception text |

Scope check that matters for the roadmap: the false-certification bites only **degenerate**
tasks (constant integrand). On a genuine forged task, `oo` and `log(0)` correctly reject — and the
forge already skips `integrand.is_number`, so it never mints them. The defect is in the
**verifier**, and it is local.

Codex's verdict on the *inversion* itself (C4) was **HOLDS-WITH-CONDITIONS**: parent ownership of
the gold is real, but minting must use a **closed, finite, differentiable** grammar with
degeneracy rejection — unrestricted minting produces invalid golds (`F = oo`), trivial tasks
(`F = x-x`, `sin²+cos²`), or golds outside the verifier grammar (`floor`, `gamma`, `Abs` →
`Derivative`/`polygamma` → ABSTAIN). The shipped forge uses exactly such a closed grammar, which
is why it survives at scale.

**Net: the strategy survives; the engineering has four named, local, cheap fixes.** That is the
right shape for a research bet — and it took an adversary to get there.

### Bias 3 — "the task list is the input"

34 hand-written tasks. In a verifier-grounded system, **tasks are the scaling axis, not
parameters** — and the trick is already 80% built here:

> **A verifier run backwards is a task generator.**

- **CAS** — pick any expression, *differentiate* it: an integration task with a free, airtight
  gold. And `verify ≪ solve` means generating is cheaper than solving.
- **Mutation** — take working code, apply a mutation: a debugging task with a known fix.
  Mutation testing, inverted.
- **Physics** — pick a conservation law: infinite simulation tasks checkable by invariant.
- **`judge.py` already ships the machinery.** `_GENERATORS` × `_ORACLES` (lines 207–288) *is* a
  task forge, demoted to generating test *inputs*.

**Measured, not proposed** (`scratchpad/forge_probe.py`, ~40 lines against the real unmodified
`CASVerifier`):

```
minted            : 200 tasks, 0 hand-written, 0 network, 0 untrusted execution
golds certified   : 200/200
distractors tested: 595   FALSE CERTIFICATIONS: 0   parse-errors: 0
                    ~18s on CPU  ->  ~11 tasks/sec  ->  10k tasks in ~15 min, $0
```

**200 tasks in 18 seconds against 34 in the repo's lifetime** — on the one path that is sound
today. This is the source of variation Ceiling 4 demands, and the tasks are **uncontaminated by
construction** (which also retires the "in-sample 2/11" caveat that currently invalidates the only
writer result in the repo), unlicensed, and yours. The frontier labs are running out of internet.
A verifier-inverted forge does not run out.

### Bias 4 — "prose has no verifier"

False in an exploitable way. Prose has no *absolute* verifier. It has cheap *invariant* and
*relative* ones:

- **Round-trip reconstruction** — a summary is good iff a reader model can answer the source's
  questions from the summary alone. Information-theoretic, automatic, no taste involved.
- **Self-consistency** — ask the same question 20 ways; disagreement is a defect signal needing
  no ground truth.
- **Constraint satisfaction** — much of real "LLM work" is checkable specs: mentions the date,
  under 100 words, cites only the provided source, valid JSON, no PII. A **hard** verifier hiding
  inside an "unverifiable" domain.
- **Entailment against a cited source**; **round-trip translation**; **code↔doc round-trip.**

A grade-2/3 **verifier zoo for language**: the architecture of `verify/scientific.py`, pointed at
text. The bridge from *code engine* to *general engine*. Note these rank and never certify — and
after Bias 2's correction, that distinction has to be enforced in code, not just in prose.

---

## 4. What it can actually become

| Question | Answer |
|---|---|
| A full LLM **as currently specified**? | **No.** Capped at 34 examples; the search knob is inert. |
| A full LLM **from scratch**? | **No.** 8 GPU-years, 60 TB. Arithmetically excluded. Stop. |
| A system turning **commodity weights** into a frontier-competitive engine on its slice? | **Yes** — and the hard part (the verifier) is built. |
| Widened to **general language**? | **Mostly**, via Bias 4 — as ranking, never certification. |
| Owner of **world knowledge**? | **No, permanently.** No verifier tells you the capital of Burkina Faso. |

> **Full LLM = rented knowledge (commodity base) + owned competence (UltraBrain).**

You will never own the knowledge layer on consumer hardware. That is fine: it is commoditising
fastest and has no moat. Competence — getting things right *and knowing that you did* — resists
commoditisation, and this repo has already built 1,700 lines of it.

### The one-line reframe

> **Stop asking the writer to get bigger. Start asking the verifier to get *wider* (more domains,
> grades 2–3) and *louder* (graded, not binary) — and run the loop where it never has to execute
> anything.** The growth axis is the verifier zoo and the task forge, never the parameter count.

---

## 5. What this does not fix

- **World knowledge and taste** remain out of reach. Permanently, on this hardware.
- **The subordinate-jailed executor is required for the code slice** — and, after Codex's
  falsification, for *learning* from it, not merely for shipping certificates. It is ~200 lines
  (`subprocess` + pipe, oracle and scorer in the parent); it keeps failing because the fix keeps
  being attempted **inside** the worker instead of **above** it.
- **Reject/failure evidence must be sanitized before it is ever trained on** — fixed-schema
  counts, enums and case digests only; never raw child output, exception text, residuals, or
  parent expected values. This is now a hard requirement on **both** paths, not a nicety.
- **The symbolic path's safety is evidence, not proof.** Codex found no AST-whitelist
  code-execution bypass — but as it noted itself, *"that is evidence rather than a proof of parser
  safety."* The grammar is small and the argument is good; it is still an unproven parser sitting
  in the trusted parent. Any extension to the whitelist re-opens the question.
- **There is still no evidence any of this improves a model.** The only writer result (FIM 2/11)
  is admitted in-sample, and the trainer has never run. Everything above is a hypothesis with a
  cheap kill gate — see [`ROADMAP.md`](../ROADMAP.md).
- **The bounded-gain problem is real.** Verified distillation buys a finite multiple, not an
  asymptote. The forge is what stops it going dry — if minted tasks are trivial, Ceiling 4
  reasserts immediately.

---

*Companion: [`ROADMAP.md`](../ROADMAP.md) — the executable path, with kill gates.
Adversarial review of §3 Bias 2 by Codex: ledger `c91f536e`. Prior art: `thoughts/14`, `thoughts/22`,
`thoughts/24`, `MANIFESTO_new_angle.md`.*

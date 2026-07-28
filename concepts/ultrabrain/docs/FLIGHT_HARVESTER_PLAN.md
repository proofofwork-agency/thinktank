# Flight harvester — build plan

*The implementation plan for [`FLIGHT_CORPUS.md`](FLIGHT_CORPUS.md). That document is the design
and the licence rules; this one is the code, in order, with a kill gate on each phase.*

**Status: not started.** Sequenced after `ROADMAP.md` S0–S3 — build this only once one training run
has shown the loop improves a model at all. See §6.

---

## 0. Shape

A new package beside the existing two, mirroring their split (`verify/` decides, `propose/`
generates, `absorb/` supplies):

```
ultrabrain/absorb/
  gtest.py        parse gtest sources -> literal (inputs, expected) vectors      [the crux]
  types.py        C++ type -> value shape (Quatf -> 4-vector, Dcmf -> 3x3, ...)
  spec.py         routine -> natural-language mathematical contract              [hand-written]
  emit.py         -> micro_codebench schema JSONL
  validate.py     a task must be self-consistent before it enters the corpus
  provenance.py   repo, commit SHA, licence, file, line, extraction method       [non-negotiable]
tools/harvest_px4.py     CLI: point at a clone, emit tasks/flight_matrix.jsonl
tests/test_absorb.py
```

Nothing here touches `verify/` or `propose/`. The harvester's entire output is a JSONL file in the
**existing** task schema — if it needs a gate change, the design is wrong.

---

## P1 · The gtest parser *(the crux — everything else is easy)*

Extract literal reference vectors from `src/lib/matrix/test/*.cpp` without compiling anything.

**Method.** Per `TEST(Suite, Name) { … }` block: build a symbol table of literal-initialised
declarations, then resolve assertions whose *both* sides reduce to literals.

```cpp
Eulerf euler_check(0.1f, 0.2f, 0.3f);                    // symbol -> [0.1, 0.2, 0.3]
Quatf  q_check(0.98334744f, 0.0342708f, 0.10602051f, .14357218f);
EXPECT_EQ(Quatf(euler_check), q_check);                  // -> a task case
```

Handle the six forms that cover all 545 assertions in the suite — `EXPECT_EQ` (289),
`EXPECT_FLOAT_EQ` (166), `EXPECT_TRUE` (48), `EXPECT_FALSE` (34), `EXPECT_NE` (6),
`EXPECT_DOUBLE_EQ` (2). Regex + brace matching is sufficient; do **not** reach for a C++ parser.

**Be honest about yield.** Many assertions compare two *computed* values and resolve to no
literal. The 545 count is an upper bound and the real number will be far lower.

> **KILL GATE P1.** ≥100 fully-resolved literal cases across ≥10 distinct routines. Below that,
> PX4's suite is less extractable than the sample suggested — write the verdict and stop. Report
> the resolution rate (`resolved / total assertions`) either way; a silent low yield is the
> failure mode that would make everything downstream look fine and be worthless.

## P2 · Type and specification tables *(hand-written, ~15 entries, deliberately not general)*

`types.py`: `Eulerf|Vector3f → 3-vector`, `Quatf → 4-vector`, `Dcmf|Matrix3f → 3×3`, plus scalars.

`spec.py`: one natural-language contract per routine — euler→quat, quat→dcm, dcm→euler, quaternion
product, inverse, normalisation, pseudo-inverse, least squares. **Hand-write these.** Fifteen
paragraphs is an afternoon, and it is the one place a human should be in the loop: the
specification is the task, and a sloppy one produces an unanswerable question.

State conventions explicitly in the prompt (Hamilton vs JPL, ZYX vs XYZ, radians) — ambiguity
here reads as model failure when it is really an under-specified question.

## P3 · Emit + validate

`emit.py` writes the existing `micro_codebench` schema. Two test tiers:

- `hidden_tests` — the P1 literal vectors, with a float tolerance.
- `property_tests` — physics invariants from `verify/scientific.py`: DCM orthonormal with
  det = 1, quaternion unit norm, euler→quat→euler round-trip, rotation preserves length. These are
  **generated, so uncontaminated** — no pretraining exposure can leak them.

No `gold` field. Per `FLIGHT_CORPUS.md` §6, the gate certifies *passes every test*; a reference
implementation is unnecessary, is a derivative work, and would reintroduce unverified ground truth.

`validate.py` — **a task must earn its way into the corpus.** Reject any task that is unsatisfiable
(no implementation can pass), trivially satisfiable (a constant passes), internally contradictory
(two cases disagree), or under-specified. This is Codex's C4 condition applied to a second forge;
skipping it poisons the corpus silently.

> **KILL GATE P3.** ≥100 tasks survive validation, and a hand-written reference implementation of
> three sample routines passes its own generated tests. If our *own* correct code fails the task
> we minted, the task is wrong.

## P4 · Provenance *(do this in P1, not at the end)*

Every emitted task carries repo URL, commit SHA, file path, line range, licence SPDX, upstream
release date, extraction method version. Non-negotiable, for three reasons: licence compliance
(§ `FLIGHT_CORPUS.md` 4), contamination auditing by date, and reproducibility when the parser
changes. Retrofitting provenance is how corpora become unshippable.

## P5 · Contamination controls

Implement mitigations 1–3 from `FLIGHT_CORPUS.md` §7 as a **reparameteriser**: rename functions and
arguments, permute argument order, switch conventions (Hamilton↔JPL, ZYX↔XYZ, rad↔deg) with the
expected values transformed to match. Memorised code breaks; understanding survives.

Emit both variants — `flight_matrix.jsonl` (verbatim) and `flight_matrix_reparam.jsonl` — and
**always report the pair.** A large gap between them *is* the contamination measurement.

## P6 · ArduPilot holdout *(evaluation only — never training)*

Same parser against ArduPilot's `AP_Math` tests. **GPLv3: these tasks are quarantined to
evaluation and must never enter training data.** Enforce it in code — a `licence_class` field that
the trainer refuses to load — not in a comment.

---

## Measurement

The number that matters is not task count. It is:

> **pass@1 on ArduPilot-held-out flight tasks, before vs after training on PX4 flight tasks, at
> equal inference budget** — reported alongside the reparameterised-vs-verbatim gap.

If the verbatim gain is large and the reparameterised gain is ~0, the model recognised code rather
than learning mathematics. That is a result worth having, and it is the one this pipeline is most
likely to produce.

---

## Order and cost

| Phase | Effort | Gate |
|---|---|---|
| P1 parser | 2–3 days | ≥100 resolved cases / ≥10 routines |
| P2 tables | 1 day | — |
| P3 emit+validate | 1–2 days | ≥100 validated; own reference passes |
| P4 provenance | folded into P1 | — |
| P5 reparameteriser | 1–2 days | verbatim/reparam gap reported |
| P6 ArduPilot holdout | 1 day | licence class enforced in code |

**~1–2 weeks, $0.** But not yet: `ROADMAP.md` S0–S3 first. If training on verified tasks does not
improve the model, this corpus is worthless however well-built — and that question costs days to
answer on the symbolic forge, which is uncontaminated by construction and needs no C++ at all.

---

## Scope limits

Carried forward from `FLIGHT_CORPUS.md` §9, restated because plans drift:

- Pure numerical leaf functions only. Not control tuning, not real-time behaviour.
- `src/modules/ekf2/test` (26 files) is **out of scope** — state estimation is stateful, not a leaf
  function. A later tier if this one works.
- The 9,946 fix-shaped commits are **out of scope** — that is the SWE-bench problem. The
  mechanically-tractable slice of it is specified in
  [`GITHUB_ABSORBER_PLAN.md`](GITHUB_ABSORBER_PLAN.md) §3, Tier 2.
- These are executed Python tests, so they inherit the `judge_v1` residual and need the subordinate
  executor (`ROADMAP.md` S4) before any certificate is trustworthy. The symbolic slice does not —
  which is why it goes first.
- **This harvester is the pilot for the general absorber.** Build the specific one, learn the real
  yield rates, then generalise. Not the other way round.

# S3 — pre-registration

**Written before any S3 result exists.** Codex is executing the run; this fixes what will count as
a real effect *before* the number arrives, so the threshold cannot be fitted to the outcome. If a
later reading of the data disagrees with this document, this document wins unless the change is
argued explicitly and recorded here.

## The question

> Does training on verifier-certified data improve a model on **concept classes it never saw**, at
> equal inference budget?

## The design (fixed)

| | |
|---|---|
| Model | `mlx-community/Qwen2.5-3B-Instruct-4bit`, Apache-2.0, already local |
| Train families | `poly, trig, chain, exp, prod, log, mixed` |
| Test families | `arctan, arcsin, sqrtpow, byparts, hyper, trigpow, loglin, ratio` — **244 expression-unique forms** (see correction 1) |
| Test concepts | inverse-trig, fractional powers, integration by parts, hyperbolic, log-of-linear, rational — none appear in training |
| Budget | identical N, sampling params and prompt template for base and trained |
| Both models measured on **both** splits | separates "training didn't take" from "trained but didn't generalise" |

## Thresholds

The comparison is **paired** — the same tasks go to both models — so the correct test is McNemar /
sign test over *discordant* pairs only, not a two-sample proportion test. Paired is far more
sensitive here, and using the unpaired test would waste most of the signal.

**Unpaired, for reference only** (n=252): base ≈30% ⇒ a gain under **8.0pp** is not distinguishable
from noise; at n=100 that rises to **12.7pp**.

**Paired — the standard actually applied.** Given `b` discordant pairs, wins needed in one
direction for two-sided p < 0.05:

| discordant pairs | wins needed | p |
|---|---|---|
| 6 | 6 | 0.031 |
| 10 | 9 | 0.022 |
| 15 | 12 | 0.035 |
| 20 | 15 | 0.041 |
| 30 | 21 | 0.043 |
| 40 | 27 | 0.039 |
| 60 | 39 | 0.027 |

*(Sanity-checked against the known value: 20 discordant → critical 15, p = 0.0414. An earlier
computation of this table was wrong — a loop that took the largest qualifying k instead of the
smallest, printing degenerate "20 of 20" thresholds. Caught and corrected before any result
existed, which is exactly what pre-registration is for.)*

## Rules committed to now

1. **A single seed is not a result.** ≥3 seeds, each reported separately, not averaged into one
   number.
2. **Raw counts, never percentages alone.** Report `trained-wins / base-wins / both-right /
   both-wrong` so significance is judgeable directly.
3. **If discordant pairs split roughly evenly, the result is NEGATIVE.** Say so plainly.
4. **In-domain gain with no held-out gain is a negative for the thesis**, not a partial win. It
   means the model memorised the training families, which is the outcome the held-out split exists
   to detect.
5. **No gain in-domain *and* none held-out means the run is broken**, not that the thesis failed.
   Debug the run; do not report it as evidence either way.
6. **Any post-hoc change** — dropping a family, re-picking N, switching the metric, excluding
   tasks — must be recorded here with its reason before the affected number is quoted.

## Recorded corrections

Rule 6 requires design changes to be logged with their reason before the affected number is
quoted. Both below were found **before the baseline was measured**, so no number existed that they
could have been fitted to — the cleanest possible case.

**Correction 1 — held-out set 252 → 244 (pre-baseline).** My 252 counted *parameter combinations*,
not *distinct expressions*. Codex's witness: `x/(2*x+1)` and `2*x/(4*x+2)` simplify to the same
antiderivative, so `ratio` has 72 parameter tuples but only 64 identities. Expression-unique
composition, to be emitted with the frozen set rather than asserted:

```
loglin 72 · arctan 24 · arcsin 6 · sqrtpow 18 · byparts 18 · hyper 12 · trigpow 30 · ratio 64 = 244
```

The same error inflates the forge constant: `_MEASURED_FORGE_SPACE` 4,524 → **4,516** under
expression identity. Paired criticals are unaffected — they depend on the discordant-pair count,
not on n. *(This is the third time today I counted the space generated rather than the objects
surviving dedupe. Consistent enough to be a rule: never quote a generator's reach without
deduplicating by identity first.)*

**Correction 2 — SFT-only; DPO deferred (pre-baseline).** `mlx-lm` 0.31.3 exposes SFT LoRA and has
no DPO path. Ruling: **do not hand-roll one.** An unvalidated DPO implementation makes the result
uninterpretable *in both directions* — positive and we cannot separate the method from a bug in our
loss; negative and we cannot separate "preference training does not transfer" from "we implemented
it wrong." The purpose of S3 is one number nobody has to argue about.

SFT on certified traces answers the question as posed: *does training on verifier-certified data
transfer to unseen concept classes?* Preference signal is an enhancement, not the claim. Pairs are
still collected and kept as the input to a proper DPO run later on the RTX 5080, where `trl`
provides a validated implementation. **This narrows the experiment; it does not invalidate it.**

## Headroom — what baseline values would make this experiment uninformative

*Added while the baseline was still running and before any score was seen. This is the last
point at which it can be stated without being post-hoc.*

An experiment can be run perfectly and still answer nothing, if the base model sits at a floor or
a ceiling. Both are properties of the **baseline alone**, so they are decidable the moment it
lands and before any adapter exists.

| Baseline on held-out | Reading |
|---|---|
| **> ~90%** | **Ceiling — no headroom.** The 3B already solves these; training cannot demonstrate anything. Not a result about the thesis. Harder task families needed. |
| **~0%, and also ~0% in-domain** | **Floor — out of range.** The model cannot do this class of problem at all, so "training did not help" is uninformative: there is nothing to transfer *to*. Not evidence against the thesis. |
| **~0% held-out, but non-trivial in-domain** | **Informative.** This is the interesting configuration: capable on trained concepts, incapable on unseen ones, so transfer is exactly what is being measured. |
| **~10–70% held-out** | **Informative.** Room to move in both directions. |

The in-domain baseline is the discriminator between *floor* and *genuine non-transfer*, which is
the single most confusable pair of outcomes in this design — and the reason both splits are
measured on both models rather than only the held-out one.

**Commitment:** if the baseline lands outside the informative band, the correct response is to say
so and change the task difficulty — **not** to train anyway and report whatever the delta happens
to be. A gain measured against a floor or a ceiling is an artifact of the range, not evidence
about verified search.

**Correction 3 — none.** A concern that the training set would be 91% polynomial was raised and
was **unfounded**: the manifest was already balanced at `poly 84 | mixed 84 | prod 24 | trig 18 |
chain 18 | exp 18 | log 6 = 252`, max family share 33.3%. Recorded because a raised-and-withdrawn
concern is part of the audit trail, not because anything changed.

**Correction 4 — in-domain split reduced to one seed (runtime, pre-outcome).** Measured block
duration drifted to ~8 min under thermal throttling, projecting **109–121 min** total including
collection and training — at or past the 2-hour stop line. Revised:

| | before | after |
|---|---|---|
| **held-out** (the decisive claim) | N=8 × seeds 0,1,2 | **unchanged** |
| in-domain (the discriminator) | N=8 × seeds 0,1,2 | N=8 × **seed 0 only** |
| total eval completions | 23,808 | 15,744 (−34%) |
| projected total | 109–121 min | 80–95 min |

**Why this does not weaken the result.** The two splits carry different weight. The in-domain split
exists *only* to separate "training did not take" from "trained but did not transfer" — a coarse,
near-binary question that one seed answers adequately. The three-seed requirement is load-bearing
for the **held-out** claim, where the question is whether a modest effect survives replication,
and that is untouched at full power.

**Explicitly not authorised**, then or under any later time pressure: fewer held-out seeds, N below
8, dropped test families, or a smaller held-out set. Those touch the decisive measurement. The
distinction being held is between cutting **cost** and cutting **evidence**.

Taken before seed 0 or any outcome existed, so it cannot have been chosen for its effect on a
number. **In-domain results are single-seed and must not be read as carrying the same weight as
the held-out numbers.** Thermal drift is reported as a limitation regardless.

## Baseline landed — in band, and the effect is now decomposed in advance

*Provisional log checkpoint, held-out seed 0, base model, before any adapter exists:*
**pass@1 26/244 (10.7%) · pass@8 41/244 (16.8%).**

**Headroom check against the band committed in `cb2dc87`, written before this number:** 10.7% is
**inside the informative band** — at its lower edge, but inside. The experiment can resolve an
effect and no task-difficulty change is warranted. Recording this as a pass rather than a judgement
call is the entire reason the band was fixed in advance.

**The decomposition, recorded before any trained number exists.** The base model already solves
**41** tasks within 8 samples but finds only **26** on the first try. That 15-task gap is the room
a "find it sooner" effect can occupy, and it splits the possible outcomes cleanly:

| Trained result | Reading |
|---|---|
| pass@1 rises toward **41**, pass@8 flat | **Cheaper, not smarter.** Distillation of coverage the model already had — up to 26→41, a 58% relative pass@1 gain, while solving nothing new. This *is* the cost-per-solved-task claim, and it is the outcome the architecture actually predicts. |
| pass@1 rises **above 41** | **Genuinely new capability.** Beyond redistributing existing coverage. A stronger result than the thesis requires. |
| pass@8 rises above 41 | The model learned to solve problems it previously could not, at any budget. |
| neither moves | Verified search did not transfer to unseen concept classes. |

Conversion of the gap is well-powered: even **8** of the 15 tasks converting is significant
(8 discordant pairs, critical 8); 12 of 15 gives critical 10. So the paired test can resolve a
partial effect, not only a total one.

**Correction 5 — collection moved from HTTP to direct-batched (pre-training).** The first
collection produced **one distinct candidate per task across N=8** — 544 traces that were eightfold
duplicates of 68 candidates, and zero preference pairs. Confirmed independently: collection solved
68/252, tracking in-domain **pass@1 (73)** rather than pass@8 (115).

A per-request seed was the obvious fix and was **empirically disproven** by a stratified smoke test.
Stratifying by the baseline's own difficulty tiers is what made it decisive — on the six
`pass@8-but-not-pass@1` tasks, where sampling diversity is load-bearing by construction:

| path | distinct candidates / 8 |
|---|---|
| HTTP, seeded | `{1:6}` — **mean 1.00** |
| direct batched | `{3:1, 4:3, 5:1, 6:1}` — **mean 4.33** |

Same tasks, same N, same model. Collection therefore moves to the **same direct-batched generator
the two evaluations use**, so one sampler serves all three phases. Found pre-training, not
result-driven; both failed artifacts retained as evidence.

*Near-miss worth recording:* the in-domain baseline already generated 252 × 8 batched candidates
through the gate — structurally identical to collection — but retained `candidate_sha` and a
certified **count**, not text. Correct under the sanitisation rule for a measurement artifact, so
no shortcut existed. **Clarification applied:** the sanitisation rule governs *evidence and signal*
fields, not the SFT payload. The training example *is* the candidate; CAS candidates are
whitelist-validated math expressions, not executable code, so retaining their text carries none of
the `judge_v1` risk.

## Both hard gates passed

**Determinism — PASSED.** The truncation-instrumented rerun of held-out seed 0 reproduced the
earlier checkpoint **exactly**: pass@1 26/244, pass@8 41/244. Generation is deterministic given
(seed, params, task), so *base-vs-trained at matched seeds is a controlled comparison* and the
paired design is valid. This was assumed by the whole design and is now verified rather than
assumed — for free, because a restart happened to make the comparison available.

**Truncation confound — MEASURED AND NEGLIGIBLE.** 3 of 1,952 candidates hit the 64-token cap:
**0.154%**. Worst case, if the trained model truncated zero times *and* every base truncation cost
a solve, the maximum manufacturable gain is **3 tasks** — while significance requires 8 wins of 8
discordant pairs. **A truncation artefact cannot reach the threshold.**

Honest accounting of that flag: it was correct methodology and it cost two restarts and roughly
twenty minutes to establish that the effect it guards against is empirically absent here. That is
still a result — the confound is now *measured* rather than assumed away — but the cost was real
and the answer was "no confound." Worth recording both halves.

**Pace, observed rather than projected:** 11.2 min/block × 8 blocks = 90 min eval, plus ~12 min
collection and ~8 min training ≈ **109 min (~1.8 h)**. Under the 2-hour stop line. Continuing
unchanged.

## Collection audited — and the small-N caveat, recorded before the result

Independently verified against the direct-batched collection artifacts (all four SHAs match):

| check | result |
|---|---|
| traces re-verified by the real unmodified `CASVerifier` | **570/570 certified, 0 failures** |
| distinct (task, solution) pairs | 126 |
| distinct tasks solved | **115 — exact match to the in-domain baseline pass@8 of 115/252** |
| ordered candidate digests vs the audited seed-0 block | **0 mismatches across all 252 tasks** |

The digest match plus the exact pass@8 agreement means collection and evaluation are *provably*
the same sampler, not merely the same code. And the SFT corpus is **verified by construction** —
every example independently re-certified here, not taken on report.

**Verified-search data yield — the economic number:** 2,016 generations → 115 tasks solved → **126
unique certified examples**. A **6.2% yield**, or 0.50 examples per task attempted. That is the
real cost of verified data on this setup and it should be quoted whenever the pipeline's economics
are discussed.

> **SMALL-N CAVEAT — stated before any trained number exists.** 126 examples is a *small* SFT set
> for a 3B model. If the trained model shows no gain, that is at least as consistent with **"too
> little data"** as with **"verified search does not transfer."** The pre-registered design already
> discriminates: no gain in-domain *and* none held-out is a **BROKEN RUN / inconclusive**, not a
> negative for the thesis. **The in-domain split therefore carries more weight here than usual** —
> it is the only thing separating a weak-training-signal null from a genuine non-transfer result.

**Coverage gap, recorded not patched:** the `prod` family contributes **0** examples — the base
model certified no product-family candidate at all. An observed yield limitation; manufacturing
coverage to fill it would corrupt the corpus.

## What each outcome means

| Held-out result | Reading |
|---|---|
| Trained wins beyond threshold, ≥3 seeds | **The thesis survives its first real test.** Verified search transfers to unseen concept classes. Proceed to the data-source plans. |
| Discordant pairs ≈ even | **Negative.** Verified self-improvement does not transfer at this scale. Cheap, honest, and it kills the roadmap's central claim — which is what the kill gates were for. |
| In-domain gain only | **Negative for the thesis, positive for the mechanism.** It trains; it does not generalise. Ceiling 4 (a filter adds no information) reasserts. |
| Nothing moves anywhere | **Broken run.** Not evidence. Fix and re-run. |

## Known limits of this experiment

Stated now so they cannot be discovered conveniently later:

- **3B, 4-bit, LoRA, a few hundred examples.** A null result at this scale does not prove the
  thesis false at larger scale — it proves it does not show up cheaply, which is still decisive for
  *this* project, whose entire premise is cheapness.
- **Qwen has certainly seen calculus.** The test is not "does it know integration" but "does
  *training* move it." The base measurement is the control for exactly this.
- **The test families are minted by our own forge**, so they are uncontaminated by construction but
  also narrower than real mathematics.
- **252 forms is a small test set.** It bounds the smallest effect this experiment can resolve;
  see the tables above.

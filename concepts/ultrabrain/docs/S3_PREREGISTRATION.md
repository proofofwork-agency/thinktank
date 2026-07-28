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

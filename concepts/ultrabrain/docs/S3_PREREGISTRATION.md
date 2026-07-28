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
| Test families | `arctan, arcsin, sqrtpow, byparts, hyper, trigpow, loglin, ratio` — **252 forms** |
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

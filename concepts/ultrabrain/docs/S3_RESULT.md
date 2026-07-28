# S3 — result

*The experiment the project existed to run. Graded against
[`S3_PREREGISTRATION.md`](S3_PREREGISTRATION.md), whose thresholds, decision rules and outcome
readings were committed before any number existed. Verified independently by
`experiments/verify_s3.py` from raw per-task outcomes, not from the executor's summary.*

## Verdict

> **NEGATIVE by the pre-registered standard.** The rule was *"held-out gain survives on a majority
> of seeds"* — ≥2 of 3 seeds significant. Achieved: **0/3 on pass@1, 1/3 on pass@8.**
>
> But *"does not transfer"* overstates what the data show. **All six held-out tests favour the
> trained model, at 2.1–3.0:1.** The honest statement is: **a consistent positive effect that this
> design was underpowered to certify per seed.**

## The numbers

**In-domain (training families, the discriminator) — unambiguous.**

| | base | trained | discordant | p |
|---|---|---|---|---|
| pass@1 | 73/252 | **182/252** | 111 vs 2 | ~0 |
| pass@8 | 115/252 | **196/252** | 81 vs 0 | ~0 |

Training took, overwhelmingly. This rules out the pre-registered *broken run* reading.

**Held-out (unseen concept classes, the decisive claim) — positive but not certified.**

| metric | seed | base | trained | trained-only | base-only | discordant | need | p | |
|---|---|---|---|---|---|---|---|---|---|
| pass@1 | 0 | 26 | 37 | 21 | 10 | 31 | 22 | 0.071 | ✗ |
| pass@1 | 1 | 25 | 33 | 14 | 6 | 20 | 15 | 0.115 | ✗ |
| pass@1 | 2 | 25 | 34 | 14 | 5 | 19 | 15 | 0.064 | ✗ |
| pass@8 | 0 | 41 | 55 | 21 | 7 | 28 | 20 | 0.013 | **✓** |
| pass@8 | 1 | 42 | 52 | 17 | 7 | 24 | 18 | 0.064 | ✗ |
| pass@8 | 2 | 43 | 52 | 17 | 8 | 25 | 18 | 0.108 | ✗ |

Means: pass@1 25.3 → 34.7 (**+37%**), pass@8 42.0 → 53.0 (**+26%**). Every seed positive on both
metrics. Four of six tests sit at p between 0.06 and 0.12 — near the line, on the wrong side.

## What was ruled out

- **Leakage** — gold and integrand overlap **0** by sympy expression identity, audited independently.
- **Format compliance** — the leading non-mathematical explanation. Base failures were **68.9%
  mathematically wrong** vs 19.8% format, and only **4** held-out tasks had *every* candidate fail
  on format. A perfect format fix could rescue 4 tasks against a 9–11 task effect. **Bounded out.**
- **Truncation** — 0.154% of candidates, and 0 on every trained block. Cannot reach threshold.
- **Sampling noise** — base between-seed sd 0.58 tasks; the smallest gain is 14× that.
- **Different samplers** — collection, baseline and trained eval share one batched path, proven by
  0 candidate-digest mismatches across all 252 tasks and by collection recovering exactly the
  in-domain pass@8 of 115.
- **Duplicate questions** — prompt-deduplicated sensitivity (244 → 226 independent questions)
  changes no verdict on any seed.

## The post-hoc analysis, and why it does not override

Pooling all discordant pairs gives 104 vs 43 (p≈5×10⁻⁷). **That number is wrong** — the three seeds
share the same 244 tasks, so pooling treats correlated observations as independent and inflates
significance. It is recorded only to be dismissed.

The one *statistically valid* combination counts each task once, by majority across seeds:

| metric | trained-better | base-better | tied | p | |
|---|---|---|---|---|---|
| pass@1 | 28 | 11 | 205 | 0.0095 | significant |
| pass@8 | 29 | 12 | 203 | 0.0115 | significant |

**This is post-hoc and does not change the verdict.** The pre-registration fixed per-seed
significance as the standard, and a combination chosen after seeing the data is exactly what
pre-registration exists to prevent. It is reported because suppressing it would be equally
dishonest — but the headline remains NEGATIVE, and the correct response is **a properly powered
replication, not a reinterpretation of this run.**

## The finding nobody predicted: catastrophic churn

The trained model **loses** held-out tasks the base solved:

| seed | base solved | lost by trained | |
|---|---|---|---|
| 0 | 26 | 10 | **38%** |
| 1 | 25 | 6 | 24% |
| 2 | 25 | 5 | 20% |

126 SFT examples over 7.1 epochs cost the model a fifth to a third of its existing held-out
capability. The net gain is *learning minus forgetting*, and both terms are large. This is why the
discordant ratios sit near 2:1 rather than the 10:1 the marginals hint at — and it is the single
most actionable result here, because the forgetting is plausibly fixable (fewer epochs, lower LoRA
rank, replay, KL anchoring) while the learning is already demonstrated.

## What this means for the project

**The thesis is not refuted.** Training on verifier-certified data produced a consistent
positive effect on concept classes never seen in training, from **126 examples** — while
simultaneously destroying 20–38% of existing capability through overtraining. That is a
recognisable, well-understood failure mode with known mitigations.

**The thesis is also not established.** Per-seed significance is the bar the pre-registration set
and it was not cleared.

**The cheapest decisive next step**, in order:
1. **Fix the forgetting** — fewer epochs (7.1 is far too many for 126 examples), lower rank, or
   replay. If net gain rises because losses fall, the effect clears the bar without needing more data.
2. **Then power the test** — more seeds, or a larger held-out set. The effect size sits right at
   the design's resolution limit; ~5 seeds would settle it.
3. Only then scale data or move to the RTX 5080.

## Provenance

Raw outcomes `outcomes.jsonl`, 1,968 rows, sha256 `6ae94515…`. Adapter sha256 `ef779856…`.
Traces `11519c86…` (570 rows, all re-certified here through the real verifier, 0 failures).
Manifests: train `3ae3670e…` (252 tasks), test `c0398225…` (244). Corrections 1–5 recorded in the
pre-registration, all pre-outcome. Total wall clock ≈ 100 minutes on a thermally-throttling laptop.

# Thought 08 — Generate-Verify-Reject for Open-Text Generation

*Paradigm: sample many, score with a verifier/critic, keep the best.*

## Paradigm in one paragraph
Generate-verify-reject (GVR) decouples PROPOSAL from SELECTION: sample N candidates from a
generator, score each with a verifier/reward model/critic, keep the best (or
majority-aggregate). Variants: best-of-N (BoN), rejection sampling, self-consistency
(majority vote over extracted answers), tree search against process verifiers,
generate-and-rerank. The bet: trade extra INFERENCE FLOPs for quality, rather than extra
TRAINING FLOPs. Reframes generation as a search problem where the generator proposes and the
verifier disposes.

## Key papers (verified)
- **Self-Consistency** — Wang et al. 2022 — https://arxiv.org/abs/2203.11171 — Majority-vote over CoT paths; +17.9% GSM8K. *Requires extractable answers — fails on free-form text.*
- **Learning to Summarize from Human Feedback** — Stiennon et al. 2020 — https://arxiv.org/abs/2009.01325 — RLHF reward model beats larger supervised models. *Seed of "verifier > predictor."*
- **Universal Self-Consistency** — Chen et al. 2023 — https://arxiv.org/abs/2311.17311 — Extends SC to open-ended generation using the LLM itself as consistency judge. *The only direct bridge to free-form text — and its verifier is just another LLM.*
- **Scaling Test-Time Compute** — Snell et al. 2024 — https://arxiv.org/abs/2408.03314 — Compute-optimal search beats a 14× larger model on problems the small model can occasionally solve.
- **Inference Scaling Laws** — Wu et al. 2024 — https://arxiv.org/abs/2408.00724 — Llemma-7B + tree search beats Llemma-34B on MATH.
- **Generative Verifiers (GenRM)** — Zhang et al. 2024 — https://arxiv.org/abs/2408.15240 — Verifier as next-token prediction; BoN 5%→45% (algo), 73%→93% (GSM8K).

## Maturity — clearly effective, now a dominant axis
Unambiguous. Inference-time scaling IS the 2024–2026 narrative: o1/o3, DeepSeek R1, Claude
extended thinking. BoN, process-reward search, self-consistency are standard, reproducible,
large measured gains on math/code. A real deployed axis — almost entirely on VERIFIABLE
domains.

## Could it replace prediction as a foundation? — Only where a verifier exists
**For:** Snell/Wu show small-predictor + search > 14× larger predictor (verifiable tasks).
Stiennon shows RM-tuned small model > large supervised model. The "weak predictor + strong
verifier" thesis holds empirically on math, code, summarization, algorithmic puzzles.
**Against:** The verifier is itself a next-token-predictor (GenRM = "reward modeling as
next-token prediction"). GVR doesn't REPLACE prediction — it RELOCATES it into the critic.
Gains vanish on prompts the base model can never sample correctly (Snell) and where no
ground-truth signal exists.

## Hegemony / decentralization — moderate, not decisive
The argument: if verifier + sampling wins, the biggest predictor is unnecessary → small
open models compete. Partially true on verifiable tasks (Wu's 7B-beats-34B). Three
weakeners: (a) frontier models still dominate the HARDEST problems where sampling yields no
correct candidate; (b) building good verifiers/RLHF data is itself capital-intensive and
concentrated; (c) inference-scaling burns serving-time compute, shifting—not eliminating—
the moat. Decentralization gains are real but bounded to tasks with cheap, independent
verification.

## Relation to UltraBrain — and where it breaks
UltraBrain's "predict for perception, verify before write" IS the GVR pattern, and the
literature strongly validates it FOR VERIFIABLE DOMAINS. The break point is OPEN-ENDED PROSE
— novels, journalism, dialogue — where no executable, no math check, no consensus ground
truth exists. Universal Self-Consistency is the honest attempt, and it collapses to "an LLM
judging LLMs," which is circular bootstrapping, not independent verification.

**Honest verdict:** GVR scales to generation only where verification is cheaper and more
reliable than generation and has independent signal. For open text, that verifier does not
yet exist — which is precisely UltraBrain's central unsolved risk, not a solved foundation.

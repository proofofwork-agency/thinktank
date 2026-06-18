# Thought 07 — Process Reward Models & Step-Level Verification

*Paradigm: a per-step verifier scores/guides generation as it unfolds.*

## Paradigm in one paragraph
Instead of trusting an autoregressive model's final answer, a process reward model (PRM)
scores INTERMEDIATE reasoning steps and uses those scores to rank, prune, or steer
generation as it unfolds. A base policy proposes; the verifier supplies per-step "this move
is sound / makes progress" signal, enabling best-of-N at the trajectory level, step-level
beam search, or dense rewards for RL. Generation shifts from "predict then hope" toward
search under a learned per-step value/critic, where the verifier — not the predictor —
decides which branches survive.

## Key papers (verified)
- **Lightman et al. "Let's Verify Step by Step"** — OpenAI 2023 — https://arxiv.org/abs/2305.20050 — Process > outcome supervision on MATH (78%); PRM800K (800k step labels).
- **Math-Shepherd** — Wang et al. DeepSeek 2023 — https://arxiv.org/abs/2312.08935 — Monte-Carlo step-value estimation; no human labels.
- **OmegaPRM** — Luo et al. Google 2024 — https://arxiv.org/abs/2406.06592 — MCTS + binary search to auto-locate first error step; Gemini Pro 51%→69.4% on MATH500.
- **PAVs (Rewarding Progress)** — Setlur et al. Google/CMU 2024 — https://arxiv.org/abs/2410.08146 — Step-level advantage via a separate prover policy; a WEAK prover lifts a STRONGER base.
- **Generative Verifiers (GenRM)** — Zhang et al. DeepMind 2024 — https://arxiv.org/abs/2408.15240 — Verifier trained with the SAME next-token objective as the generator.
- **PRIME (implicit PRMs)** — Cui et al. 2025 — https://arxiv.org/abs/2502.01456 — Process rewards derived implicitly from outcome labels + policy log-probs.

## Does it work / maturity
**Clearly works for math and code** — every paper shows double-digit gains; AlphaProof
reached IMO silver using Lean-based step verification + search. Mechanically, these domains
have checkable intermediates. **Open/general text is unsolved**: no objective "correct step"
for prose, so PRMs collapse into preference models and inherit reward hacking, length/style
bias, label disagreement. GenRM/PRIME partly address by training verifiers on-spectrum with
the generator — general-text step verification remains the open frontier.

## Could it replace prediction as a foundation?
**Partially, not cleanly.** PRMs reframe generation as search-under-a-verifier, but are
trained critics ON TOP of a predictor — they still need an AR proposer. Worse for UltraBrain:
GenRM shows the trend is to make the verifier ITSELF an LLM trained with NTP — the "judge"
is being absorbed back into the predictor. That VIOLATES UltraBrain's "LLM never the judge"
unless the verifier is grounded externally.

## Hegemony angle
**Genuinely decentralizing potential.** PRMs/PAVs are small, specialized, domain-scoped
(Setlur: a weak prover lifts a strong base model). A guild could ship a 1–7B math/code
verifier that unlocks many base models, breaking the "one giant model does everything" moat.
Open PRMs (Math-Shepherd, PRIME, OpenR1-style data) are proliferating. The verifier layer
is where a pluralist ecosystem can form.

## Relation to UltraBrain — the key tension
UltraBrain wants a DETERMINISTIC gate; the PRM literature uses LEARNED verifiers. This is
the crux:
- **Overlap:** Both decouple "is this step valid?" from "what token comes next," both move
  intelligence into verification.
- **Conflict:** A learned PRM is itself a statistical model subject to the same failure
  modes it polices — it can be fooled, hacked, is opaque. Doesn't satisfy determinism.
- **Reconciliation:** PRMs are strong evidence that GATED generation is the right paradigm;
  they validate UltraBrain's architecture. But UltraBrain must swap the learned head for a
  GROUNDED/DECIDABLE verifier (types, proof, satisfiability, executable specs). Math
  (Lean/AlphaProof) and code (tests) already admit such gates; open text does not yet.
  **PRMs prove the gate matters; UltraBrain's bet is that the gate must be deterministic to
  deserve the name "verifier."**

*PRMs are the strongest empirical case yet that verifier-driven generation works — but as
practiced they are learned judges, so they demonstrate UltraBrain's thesis while being the
thing UltraBrain must surpass.*

# Thought 06 — Test-Time Compute / Search / MCTS / o1-Style Reasoning

*Paradigm: generation as search over a reasoning tree, not single-pass sampling.*

## Paradigm in one paragraph
Generation is reframed from single-pass left-to-right sampling into search over a reasoning
tree. A base model proposes candidate "thoughts"/steps (move generation); a value function,
process reward model, or self-consistency check scores intermediate nodes (verification);
and a search algorithm — best-of-N, beam, MCTS, or RL-induced latent search — explores,
expands, backtracks, selects (keep). Output is no longer "what the predictor emits next"
but "what survives a generate→verify→keep loop at inference time." System-2 thinking: spend
extra FLOPs at test time instead of training a bigger predictor.

## Key papers (verified)
- **Tree of Thoughts** — Yao et al. NeurIPS 2023 — https://arxiv.org/abs/2305.10601 — Game of 24: GPT-4 CoT 4% → ToT 74%.
- **Let's Verify Step by Step** — Lightman et al. OpenAI 2023 — https://arxiv.org/abs/2305.20050 — Process > outcome supervision; releases PRM800K. **The verifier is the asset.**
- **Scaling LLM Test-Time Compute Optimally** — Snell et al. 2024 — https://arxiv.org/abs/2408.03314 — Compute-optimal test-time scaling >4× more efficient than best-of-N; beats a **14× larger model** FLOPs-matched.
- **rStar** — Qi et al. 2024 — https://arxiv.org/abs/2408.06195 — MCTS + self-play; LLaMA2-7B GSM8K 12.51%→63.91%; Mistral-7B 36.46%→81.88%.
- **AlphaMath Almost Zero** — Chen et al. NeurIPS 2024 — https://arxiv.org/abs/2405.03553 — MCTS + value model = process supervision without process annotations.
- **Self-Refine** — Madaan et al. 2023 — https://arxiv.org/abs/2303.17651 — One LLM as generator+critic+refiner; ~20% absolute gains, zero training.
- **DeepSeek-R1** — Nature 2025 — https://arxiv.org/abs/2501.12948 — Pure RL elicits o1-style self-reflection; OPEN WEIGHTS matching closed o1. **The hegemony-breaker.**

## Does it work / maturity
**Yes — decisively, on hard/verifiable tasks.** o1 (Sep 2024) and o3 (Dec 2024) are
production search-augmented reasoners. DeepSeek-R1 replicated with open weights + pure RL;
Gemini 2.0 Thinking and Qwen-QwQ followed. On AIME/MATH/GPQA/code-contests, search-augmented
beats same-size single-pass. Caveat (Snell): gains are difficulty-gated — wasted on easy,
futile on impossible, concentrated in medium-hard. On open-ended prose, evidence far weaker
— verifiers are the bottleneck.

## Replace prediction, or layer on top?
**Layer on top — not a foundation replacement.** Every method still consumes a base
next-token predictor as its move generator. Search AMPLIFIES a predictor; it does not
PRODUCE language from scratch. The honest framing: **generation = search + verifier, where
search still calls a predictor as a subroutine.** What changes is that raw predictive
probability is no longer the output selection rule.

## Hegemony angle — strong decentralization vector
This paradigm's most disruptive property. (1) Search is algorithmic and open (MCTS, beam,
best-of-N are textbook) — no proprietary moat. (2) Verifiers are smaller, cheaper,
trainable on synthetic data. (3) **DeepSeek-R1 proved the loop**: open base + open RL →
o1-class reasoning, free. A weaker OPEN predictor + strong OPEN verifier can match a
hegemon's closed stack. The wedge is the verifier, not the generator.

## Relation to UltraBrain — STRONG TIE
This is the closest existing literature to UltraBrain's Generate→Verify→Keep loop — but
applied to GENERATION rather than perception. Direct implications:
- **Verifier is the strategic asset.** Snell/Lightman/AlphaMath converge: performance is
  gated by verifier quality, not generator size. Validates UltraBrain's "keep prediction
  for perception, invest in verification" thesis FOR GENERATION too.
- **Self-consistency is the weak form.** rStar/Self-Refine work without external verifier,
  but Lightman shows explicit process RM is substantially stronger.
- **Concrete opening:** position UltraBrain as an OPEN, verifier-centric reasoning layer any
  base predictor (open or closed) can plug into — own the "Verify/Keep" middle of the search
  stack that DeepSeek-R1 left informal.

*Search-augmented generation is mature, works, and structurally favors open verifiers — but
is a layer ON prediction, not a replacement. UltraBrain's Generate→Verify→Keep maps directly
onto it; the verifier is where both the technical ceiling and the decentralization leverage
sit.*

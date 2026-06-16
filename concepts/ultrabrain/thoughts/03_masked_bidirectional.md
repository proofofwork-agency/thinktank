# Thought 03 — Masked Infilling / Bidirectional Generation

*Paradigm: predict any subset of positions using both left and right context.*

## Paradigm in one paragraph
Left-to-right autoregression generates token t_i conditioned only on t_<i, so each step is
strictly sequential. **Masked/bidirectional generation** corrupts a sequence with `[mask]`
tokens and predicts any subset of positions conditioned on BOTH left and right context.
Decoding is iterative: predict everything in parallel, then re-mask low-confidence spans
and regenerate (Mask-Predict), or unmask progressively (diffusion). This removes the
monotonic ordering constraint — you can edit position 200 before position 5.

## Key papers
- **Mask-Predict** — Ghazvininejad et al. EMNLP 2019 — https://arxiv.org/abs/1904.09324 — Iterative re-masking; within ~1 BLEU of AR MT at much higher parallelism.
- **BART** — Lewis et al. 2019 — https://arxiv.org/abs/1910.13461 — Bidirectional encoder + AR decoder on span-infilling noise.
- **GLM** — Du et al. ACL 2022 — https://arxiv.org/abs/2103.10360 — Autoregressive blank infilling; base of ChatGLM/GLM-4.
- **Fill-in-the-Middle (FIM)** — Bavarian et al. 2022 — https://arxiv.org/abs/2207.14255 — No perplexity cost; now standard in code models (StarCoder, CodeLlama, DeepSeek-Coder).
- **MDLM** — Sahoo et al. NeurIPS 2024 — https://arxiv.org/abs/2406.07524 — Masked discrete diffusion approaches AR perplexity.
- **LLaDA** — Nie et al. 2025 — https://arxiv.org/abs/2502.09992 — 8B masked diffusion competitive with LLaMA3-8B.

## Does it work / maturity
**Wins clearly:** code infilling & editing, document editing, targeted span rewriting,
anything needing right-context. **Weak/unclear:** open-ended coherent long-form chat —
LLaDA is the first credible entrant but trails frontier AR on hard reasoning; decoding
cost/latency unresolved; KV-cache-style serving tricks barely apply.

## Could it replace prediction as a foundation? Realistically
**Not yet as the sole foundation.** LLaDA proves the ceiling is higher than assumed, but
no masked model matches GPT-4-class quality, and global coherence over thousands of tokens
remains the unsolved bottleneck. Honest read: a **viable second pillar**, not a guaranteed
replacement by 2026.

## Hegemony angle
Infill/edit-anywhere erodes the AR serving moat: breaks lock-in to token-streaming infra
(speculative decoding, paged KV caches, vLLM-style stacks) where the incumbent's infra
advantage lives. Bidirectional favors different (parallel, diffusion-style) serving stacks
where the leader has no head start — a genuine opening for challengers.

## Relation to UltraBrain
Strong fit. Infilled spans have bounded, verifiable scope — ideal for a
**regenerate-span-until-verified** loop: mask a region, sample, run UltraBrain's verifier,
re-mask on failure. Pairs bidirectional generation (fast local edits) with UltraBrain's
verifier as the global-coherence signal AR alone can't provide cheaply.

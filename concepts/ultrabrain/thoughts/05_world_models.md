# Thought 05 — World Models / Simulator-Driven Generation

*Paradigm: generate by simulating/planning inside a learned world model, not by predicting tokens.*

## Paradigm in one paragraph
A world model is a learned simulator of environment dynamics: given a state and action, it
predicts the next state (usually in latent space). Instead of generating by autoregressively
predicting the next token/pixel, a world-model agent imagines/rolls out futures and selects
by planning inside the simulator. LeCun's JEPA family explicitly rejects generative
reconstruction in favor of prediction in abstract latent space. The charge against
next-token prediction: it optimizes surface statistics, not causal dynamics, conflating
"what sounds likely" with "what would actually happen."

## Key papers
- **DreamerV3** — Hafner et al. 2023 — https://arxiv.org/abs/2301.04104 — Latent dynamics; one config across 150 tasks; first to collect Minecraft diamonds from scratch.
- **I-JEPA / V-JEPA 2** — Assran, LeCun et al. 2023/2025 — https://arxiv.org/abs/2301.08243 , https://arxiv.org/abs/2506.09985 — Non-generative joint-embedding prediction; V-JEPA 2 (1B) zero-shot robotics.
- **Genie / Genie 2/3** — DeepMind 2024–2026 — https://arxiv.org/abs/2402.15391 — 11B foundation world model; now used by Waymo.
- **Cosmos World Foundation Model** — NVIDIA 2025 — https://arxiv.org/abs/2501.03575 — Open-weights "digital twin of the world."
- **Mahowald et al.** *Trends Cogn Sci* 2024 — https://arxiv.org/abs/2301.06627 — Splits formal vs functional linguistic competence; thought ≠ language.
- **Dziri et al.** "Faith and Fate" 2023 — https://arxiv.org/abs/2305.18654 — Transformers' compositional reasoning decays with depth.

## Does it work for language / maturity
**Perception/robotics/video: yes. Language reasoning: not yet.** DreamerV3, Genie, Cosmos,
V-JEPA 2 deliver real planning gains in continuous grounded domains. But no published
system has a learned world model that generates language or does symbolic reasoning better
than a comparably-sized AR LLM. Mahowald's diagnosis cuts both ways: it explains WHY token
prediction lacks a world model, but the working NLP remedy is retrieval/tool-use/RLHF, not
latent dynamics.

## Could it replace prediction as a foundation?
Plausibly for grounded/agentic text (tool-using agents, embodied instruction-following,
long-horizon planning). Implausible for chitchat, summarization, stylistic prose — there's
no "world state" to roll out. Most likely: **hybrid** (predictive LLM as language interface
over a learned/symbolic world model).

## Hegemony angle
World models are typically smaller and domain-specific (DreamerV3 trains on a single GPU;
Cosmos ships open weights; V-JEPA openly licensed) — decentralizing compute away from the
trillion-token pretraining race. But the frontier (Genie 3, Cosmos 3) is re-concentrating
at DeepMind/NVIDIA. The genuinely decentralizing variant is neurosymbolic — small,
inspectable, compositional.

## Relation to UltraBrain
Strong convergence. UltraBrain's **Datalog/evidence layer IS a symbolic world model**: a
crisp, auditable state of facts over which consequences are COMPUTED, not predicted. That is
precisely the "functional competence" Mahowald says LLMs lack. UltraBrain's design — keep a
predictive model for perception/fluency, ground it in a symbolic simulator for reasoning —
is a neuro-symbolic world model whose "world" is logical/semantic. The differentiator:
UltraBrain's world model is VERIFIABLE; latent world models (JEPA, Genie) are not.

*World models are the strongest known alternative to next-token prediction in principle, and
are winning in robotics/video. For language, a compelling hypothesis, not a demonstrated
substitute. UltraBrain's symbolic-evidence approach is arguably the most language-native
instance in play.*

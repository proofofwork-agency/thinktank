# Thought 10 — Program Synthesis / Library Learning as Generation

*Paradigm: generate by synthesizing a program/derivation, then render/execute to produce output.*

## Paradigm in one paragraph
Instead of predicting the next token, **generate by synthesizing a program/derivation in a formal or quasi-formal language, then "render" or execute it.** The artifact is a structured object — a Lean proof, Python snippet, Datalog query, DSL expression, learned library of primitives — whose correctness can be CHECKED by an external interpreter/compiler/verifier. Generation decomposes into (a) search over program space guided by a neural prior, and (b) deterministic compilation to a surface form. The neural model supplies plausibility; the symbolic engine supplies guarantees. The output language is a COMPILATION TARGET, not the thing being sampled token-by-token.

## Key papers (verified)
- **DreamCoder** — Ellis et al. 2020 — https://arxiv.org/abs/2006.08381 — Wake-sleep Bayesian program learning that GROWS its own DSL via library learning; rediscovered vector algebra, classical physics. ⚠ *URL not re-verified this session — cite by author/venue.*
- **Program-of-Thoughts (PoT)** — Chen et al. 2022 — https://arxiv.org/abs/2211.12588 — LLM emits a program; interpreter computes. +12% over CoT.
- **PAL: Program-Aided LMs** — Gao et al. 2022 — https://arxiv.org/abs/2211.10435 — Codex+Python beats PaLM-540B CoT by 15% on GSM8K.
- **Llemma** — Azerbayev et al. 2023 — https://arxiv.org/abs/2310.10631 — Open math LM doing tool use + formal theorem proving without finetuning.
- **AlphaProof** — DeepMind 2024 — https://deepmind.google/discover/blog/ai-solves-imo-problems-at-silver-medal-level/ — Gemini formalizer + AlphaZero search over Lean tactics. IMO silver-medal level.
- **AlphaEvolve** — DeepMind May 2025 — https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/ — Evolutionary coding agent; beat Strassen on matrix mult, advanced kissing number in 11D, shipped into Borg/TPU design.

## Does it work / maturity
**Strong and getting stronger** in verifiable domains: formal math (AlphaProof), algorithm discovery (AlphaEvolve, FunSearch), numerical/symbolic reasoning (PoT/PAL), ARC-AGI induction (DreamCoder lineage). The pattern is uniform: checkable artifact + verifier + neural proposer beats pure LM whenever a checker exists. **It does NOT extend to open prose.** There is no interpreter for "a good paragraph." Novelty, tone, humor, coherence have no automated oracle.

## Could it replace prediction as a foundation?
**For verifiable domains: arguably yes, already happening.** The boundary is exactly "is there an automated judge?" Math, code, SQL, Datalog, planning, ARC — yes. **For prose, no.** The honest framing is STRATIFICATION: program-synthesis as the reasoning spine, autoregression as a surface renderer. Forcing every sentence to pretend it has a verifier is wrong.

## Hegemony angle
**The most credible anti-hegemony wedge in generation research.** AlphaProof/AlphaEvolve show a small specialized neural proposer + a verifier can beat a 10× larger monolithic LM in domains with ground truth. Verifiers (Lean, test suites, ARC checkers, Datalog engines) are public goods; the moat is the proposer + curriculum, both far cheaper to train than a frontier LM. A federated ecosystem of domain program-synthesizers (each with its own DSL and checker) is structurally hostile to single-company capture.

## Relation to UltraBrain
UltraBrain's Datalog KB layer ALREADY IS generation-as-program-synthesis for the structured layer: queries synthesized, evaluated, rendered. Extending it to ALL generation is tempting but wrong — it requires a Datalog-shaped verifier for prose that cannot exist. The defensible architecture is **hybrid and stratified**: Datalog/program-synthesis owns reasoning, KB, verifiable structured outputs (where UltraBrain can out-compete a hegemon); a separate fluency model renders natural language. The boundary is "where does a checker exist." Push program-synthesis to that boundary and no further.

*ARC-AGI (Chollet) and Bayesian Program Learning (Lake 2015) are central to this lineage.*

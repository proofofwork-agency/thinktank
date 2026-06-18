# Thought 19 — Brain Continual / Few-Shot Learning

*Learn continuously from a stream, from few examples — never retrain from scratch.*

## Paradigm in one paragraph
A brain-style learner ingests a STREAM of experience and folds each new item into existing competence without retraining on its history. Two mechanisms: (a) **complementary consolidation** — a fast, plastic "hippocampal" store captures new episodes, then a slow "neocortical" process interleaves them with replay so old knowledge survives; (b) **sample-efficient abstraction** — compositional/metric structure lets one or a few examples generalize. The goal: a model that never starts over and never needs a trillion tokens per capability.

## Key papers (verified)
- **Elastic Weight Consolidation** — Kirkpatrick et al. 2017 — arXiv 1612.00796. Anchor weights important to old tasks via Fisher penalty. *Foundational idea, not scalable.*
- **Synaptic Intelligence** — Zenke, Poole, Ganguli 2017 — arXiv 1703.04200. Per-synapse importance accumulated online. *Closer to biological synapses.*
- **Progressive Neural Networks** — Rusu et al. 2016 — arXiv 1606.04671. New column per task with lateral connections; old frozen. *Provably zero forgetting, but params grow linearly.*
- **MAML** — Finn, Abbeel, Levine 2017 — arXiv 1703.03400 — and **Prototypical Networks** — Snell 2017 — arXiv 1703.05175. Meta-learn init/metric so a few gradient steps/prototype lookups adapt to a new task. *Subsumed conceptually by in-context learning.*
- **"Learning, Fast and Slow"** — Tiwari, Agarwal, Zaharia et al. 2026 — arXiv 2605.12484. Context = "fast weights," parameters = "slow weights." *Up to 3× more sample-efficient than RL-only, 70% less KL drift, less forgetting.*
- **JumpLoRA / IncLoRA / ELLA lineage 2026** — arXiv 2604.16171. Sparse, gated, subspace-isolated LoRA adapters per task. *The dominant practical continual-LLM recipe — modular, cheap, but task-scoped, not whole-stream pretraining.*

## Does it work / maturity — be honest
- **Few-shot for new TASKS:** works spectacularly — that IS in-context learning. A handful of examples in the prompt adapt behavior at inference with ZERO training compute.
- **Continual/online BASE-KNOWLEDGE acquisition at LLM scale: still unsolved.** Every 2026 paper operates on post-training ADAPTATION (task/domain streams), not on replacing trillion-token pretraining. Regularization (EWC/SI) collapses over long sequences; progressive nets blow up; replay needs a buffer + recompute; adapters/LoRA isolate tasks but don't CONSOLIDATE into general capability. One preprint (TFGN, 2605.15053) claims replay-free task-free forgetting-free continual pretraining at 8B — a bold, unvalidated, single-author claim, NOT consensus. **Nobody has grown an LLM-quality base model continuously from a stream without eventually forgetting or bloating.**

## Could it cut training compute?
Yes, in two distinct regimes, large prize:
- **Kill "retrain from scratch every release."** Frontier retraining runs ~$50–200M each, recurring per generation. A working continual base learner turns that into small incremental deltas — potentially **>90% amortization** across releases.
- **Escape the trillion-token diet.** Sample-efficient/meta-learning targets suggest much of web-scale data is redundant; compositional generalization (Lake & Baroni 2018) shows humans beat nets on systematic reuse from few examples. ICL already proves the TASK side costs ~0 training FLOPs.
- **Caveat:** base acquisition savings remain aspirational until consolidation works at scale; post-training adaptation savings are already bankable (LoRA continual FT ≈ <1% of full SFT).

## Hegemony angle
Moderately strong and GROWING. Continual, adapter-based growth is inherently INCREMENTAL and COMPOSABLE: a community can train, verify, and merge skill modules (adapters, LoRA, "skill neologisms" — Berthon et al. 2605.04970) without re-baking a foundation model. This decentralizes the GROWTH layer. But the BASE foundation model still requires giant-lab compute, so continual learning democratizes the EDGES, not the CORE — partial but meaningful erosion of the centralized training monopoly.

## Relation to UltraBrain
UltraBrain is, architecturally, **a Complementary-Learning-Systems design made explicit:**
- **Append-only ledger = hippocampal episodic memory** — every verified interaction stored, never overwritten (no catastrophic deletion BY CONSTRUCTION).
- **Verified-trace gating = sample-efficiency / curriculum filter** — only high-signal, provenance-checked episodes enter consolidation (analogous to learning from salient few examples, not raw noise).
- **Delayed adapter training = slow neocortical consolidation** — batches/consolidates ledger episodes into parameter updates offline, decoupling fast capture from slow replay-style integration (exactly Tiwari 2026 + McClelland's CLS theory).
- **Skills as composable modules = compositional generalization** — discrete, re-verifiable skill units that combine (Lake/Marcus systematicity).

UltraBrain's ledger sidesteps the hardest part — IRREVERSIBLE DESTRUCTIVE OVERWRITING — because the memory of what was learned is never discarded; forgetting becomes a CONSOLIDATION POLICY problem, not a DATA-LOSS problem. **This is the strongest available structural answer to the LLM-scale forgetting gap**, provided the consolidation/adapter-merge step is kept replay-grounded and verification keeps the stream high-signal. Honest risk: the consolidation policy itself is where unsolved science lives — getting it wrong turns a clean ledger into stale or conflicting adapters.

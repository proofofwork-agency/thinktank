# MANIFESTO — The New Angle

*Synthesis of 20 research threads. The defensible bet to break prediction's monopoly.*

---

## The claim we are NOT making
We are NOT claiming UltraBrain replaces next-token prediction as the universal generative
paradigm. Prediction won for empirical reasons — scaling laws, free labels, GPU fit — that
no alternative has yet matched at frontier scale (thought 15). A frontal assault without a
new scaling law loses (thought 15, §6).

## The claim we ARE making
**Prediction's monopoly is on TRUST, not on language. And trust is where the monopoly
breaks — because verification can be small, open, and composable in a way a trillion-parameter
predictor cannot be.**

The decisive reframe, supported by every thread:

> Generation = Propose → Verify → Keep.
> The PROPOSER can be small, replaceable, even bad.
> The VERIFIER is the load-bearing asset — and verifiers are small, specialized, open, and
> cheap in a way predictors are not.
> What a hegemon owns (one giant predictor) is the part that DOESN'T need to be giant.

This is true TODAY in math, code, and proof (AlphaGeometry, AlphaProof, DreamCoder —
thought 14). It is becoming true wherever a process reward model or tool oracle exists
(thoughts 6, 7, 8). And it is the EXACT thesis UltraBrain was built to demonstrate.

## The three converging wedges (each independently decentralizing; together decisive)

### Wedge 1 — Verifier-grounded generation (the epistemic break)
Generation becomes search + verify, not sample-and-hope. Snell 2024, Wu 2024, DeepSeek-R1
all show: **weak predictor + strong verifier + search beats a 14× larger predictor** on
verifiable tasks (thoughts 6, 8). The verifier is the asset; the verifier is openable.
DeepSeek-R1 already proved an open base + open RL matches closed o1 (thought 6).

### Wedge 2 — Brain-inspired efficiency (the compute break)
The brain runs on 20W by violating every assumption of GPU-NTP: local learning (no
backprop), sparse event-driven firing (only surprises cost energy), predictive coding
(only errors propagate), continual consolidation (never retrain). Each piece JUST exited
toy-land in 2025–2026 (thought 20): Forward-Forward hits 73% ImageNet-100; Predictive
Coding trains transformers matching backprop; first PCN at ImageNet scale. **The 10× win
lives in neuromorphic/local substrate, not in the algorithm on a GPU** (thought 16). The
combination is essentially un-attempted — and UltraBrain's layered design is the natural
home for it (thought 20, §the UltraBrain alignment).

### Wedge 3 — Composable, local-first deployment (the market break)
Open weights (DeepSeek, Llama, Qwen) already force price compression on closed APIs
(thought 11). Adapter marketplaces + model merging (TIES/DARE/LoraHub) let anyone compose
capabilities without retraining (thought 12). Capable small models on user hardware
(Phi-4, Apple Intelligence, llama.cpp) make local the default for 80% of consumer tasks
(thought 13). The hegemony holds at the BASE layer; it is eroding everywhere above it.

## Why UltraBrain is the convergence point
UltraBrain is the only architecture in this entire sweep where all three wedges have a
natural home — because UltraBrain ALREADY separates the layers the brain separates:

| Brain function | UltraBrain layer | Status |
|---|---|---|
| Perception (propose) | Tiny GPT / swappable proposer | Implemented (model-agnostic) |
| Prediction-error detection | Deterministic verifier | Implemented (the gate) |
| Hippocampal episodic memory | Append-only ledger | Implemented |
| Neocortical consolidation | Delayed adapter training from verified traces | Designed (pipeline exists; trainer does not) |
| Composable skills | Skill memory (Markdown) | Implemented (v0) |
| Search/gate loop | Generate→Verify→Keep | Implemented |

A pure NTP transformer cannot be made brain-efficient or verifier-grounded without being
rewritten. **UltraBrain can be made both by FILLING IN the layers it already has.** That is
the structural advantage no monolithic-predictor competitor has.

## The concrete north star (the build)
A small proposer, trained with a **local rule** (Forward-Forward / Equilibrium Propagation
/ Predictive Coding — NO global backprop), driven by a **graded verifier signal**
(verifier emits prediction-error magnitude, not just accept/reject), consolidating into
weights via **verified-trace replay** (hippocampus → neocortex), gated by an **eval that
prevents forgetting**. Run on commodity GPUs short-term (sparse-skip verified tokens =
2–10× now), neuromorphic substrate long-term (watts not kilowatts).

**The single most leveraged experiment:** wire UltraBrain's verifier to emit a graded
signal and use it as the local-learning target for a small proposer — proving *"verified
reward trains a network without backprop."* If that works at toy scale, UltraBrain owns
the brain-efficiency recipe and the verifier-grounded-generation recipe simultaneously.
That is the new angle.

## The honest scope (what this does NOT do)
- **Open prose** still belongs to prediction. There is no verifier for taste, humor,
  persuasion (thought 14). We concede that domain to the predictor monopoly FOR NOW.
- **Frontier base training** still needs giant compute. Brain-local learning has NOT
  crossed LLM scale (thought 16, 20). UltraBrain's compute win is real at the
  inference/adaptation layer, aspirational at the pretraining layer.
- **No new scaling law exists** for any alternative objective (thought 15). Until one
  does, "replace prediction wholesale" is not fundable. "Make verification universal so
  prediction's monopoly on TRUST collapses" IS fundable and IS happening (o1, DeepSeek-R1).

## The one-line strategic bet
> **Prediction's hegemony is a trust hegemony, not a language hegemony. UltraBrain dissolves
> it by making verification small, open, composable, and eventually brain-local — so that
> the load-bearing asset (the verifier) escapes the one company that owns the predictor.
> We don't replace prediction. We demote it from oracle to proposer, and we own the layer
> that decides what to believe.**

## What to build, in order
1. **Graded verifier signal** + local-learning target (the existence proof for
   backprop-free verified training). [highest leverage]
2. **Real TMS** (close the v0.2 fatal flaw) so verified beliefs actually revise — the
   substrate that makes "Keep" trustworthy.
3. **Verifier registry** (modular, open, domain-keyed) — the composable public-good layer
   that no single company can own.
4. **Verified-trace adapter trainer** that consumes training_queue.jsonl — turning the
   ledger into consolidation, closing the continual-learning loop.
5. **Sparse-skip execution** (verified tokens = quiescent) — the immediate 2–10× inference
   win on commodity GPUs, and the bridge to neuromorphic.

The hegemony breaks not by building a bigger predictor, but by making the predictor
irrelevant to trust.

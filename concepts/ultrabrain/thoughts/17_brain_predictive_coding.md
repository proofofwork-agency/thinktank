# Thought 17 — Brain Predictive Coding & Free Energy Principle

*Objective AND architecture: only surprising inputs cost compute.*

## Paradigm in one paragraph
Predictive coding (PC) recasts a neural network as a **hierarchical generative model**: each layer predicts the activity of the layer below top-down, and only the PREDICTION ERROR (residual) propagates bottom-up. Learning is LOCAL — each synapse updates from the error at its adjacent node, no global gradient pass. Friston's Free Energy Principle (FEP) generalizes this into one imperative — *minimize variational free energy (surprise)* — and Active Inference extends it to action. Computationally, **only surprising inputs cost cycles**: well-predicted inputs drive near-zero error units and can be skipped, enabling sparse, event-driven, amortized inference — the opposite of dense matmul on GPUs.

## Key papers (verified)
- **Millidge, Seth & Buckley (2022), "Predictive Coding: a Theoretical and Experimental Review"** — arXiv 2107.12979. Canonical review; formalizes PC↔backprop equivalence + microcircuit implementation.
- **Salvatori et al. (2021), "Reverse Differentiation via Predictive Coding"** — arXiv 2103.04689. Z-IL (a PC variant) EXACTLY implements backprop on arbitrary graphs — first biologically-plausible algorithm equivalent to BP.
- **Salvatori et al. (2022), "Learning on Arbitrary Graph Topologies via PC"** — arXiv 2201.13180. PC trains nets with CYCLIC/backward connections — impossible under BP — toward cortical heterarchy.
- **Salvatori et al. (2021), "Associative Memories via Predictive Coding"** — arXiv 2109.08063. PC associative memory BEATS modern Hopfield networks.
- **Pinchetti, Frieder, Lukasiewicz & Salvatori (Jan 2026), "Faster Predictive Coding Networks via Better Initialization"** — arXiv 2601.20895. Attacks PC's iterative-inference overhead.
- **Kerjan, Høier & Scellier (Jun 2026), "Training a PCN on ImageNet using Equilibrium Propagation"** — arXiv 2606.03584. **FIRST PCN at ImageNet scale**: VGG10, 13.23% top-5 vs 12.2% BP baseline — a genuine scaling breakthrough.

## Does it work / maturity
**Historically: elegant but unscalable.** Until 2026, PCNs were only MNIST/CIFAR toys. Salvatori's group showed PC can match BP on small MLPs/CNNs and approximate/exactly reproduce its gradients, but iterative inference (settling error nodes each sample) made training several× slower than BP. **2026 is a turning point**: the Kerjan et al. ImageNet result proves PC reaches near-parity (within ~1% of BP) on a real, large task — the field's long-awaited "it scales" moment. Still pre-competitive; no LLM-scale PCN exists.

## Could it cut compute?
**Theoretically yes, strongly.** Error sparsity → event-driven inference; local plasticity → no backward pass, no global sync, trainable on-chip; amortized inference → familiar inputs computed nearly for free. **Practically — measured gains so far modest or negative**: PC's iterative equilibration currently ADDS wall-clock vs single BP fwd+bwd. The 2026 init paper (Pinchetti) and EP-paper (Kerjan) are the first to meaningfully close this gap. No published PCN yet demonstrates a MEASURED FLOP/W advantage over optimized BP on GPUs — the win is contingent on event-driven/neuromorphic hardware that exploits sparsity, which GPUs do not.

## Hegemony angle
PC's sharpest political edge. **Local, sparse, event-driven learning is inherently decentralized**: no mega-GPU memory wall, no data-center gradient sync, trainable on edge devices and neuromorphic chips (Loihi, SpiNNaker). It breaks the "only NVIDIA H100s can train intelligence" monopoly — if scalable PC meets event-based silicon. FEP/Active Inference also reframes intelligence as model-based control under uncertainty, directly competing with the RL+GPU paradigm for agents.

## Relation to UltraBrain
**UltraBrain is, structurally, a symbolic predictive-coding system.** Its verifier IS a prediction-error detector: given a proposal, it rejects unfaithful/surprising ones and accepts those consistent with the world-model — the discrete analog of a PC node minimizing residual. The generator↔verifier loop mirrors the bottom-up-error / top-down-prediction circuit, and only "surprising" (rejected) proposals consume extra search compute — exactly PC's amortized-inference efficiency.

**Difference & opportunity:** UltraBrain's error signal is currently DISCRETE/symbolic (accept/reject); classical PC's is continuous and drives gradient-based local weight updates. Hybridizing — letting the verifier emit GRADED prediction errors that train the generator locally — would give UltraBrain the brain's key trick: **learning only from surprise, locally, without a backward pass**. This is the strongest theoretical hook for UltraBrain as a compute-efficient paradigm.

---
*Honest bottom line: PC/FEP is the most principled brain-inspired efficiency theory, but its compute win is potential, not delivered — the 2026 ImageNet result is the first hard evidence it can scale at all.*

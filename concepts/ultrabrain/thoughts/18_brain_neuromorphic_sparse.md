# Thought 18 — Brain Neuromorphic / Spiking / Sparse Event-Driven Compute

*Hardware + algorithms: spikes, sparsity, in-memory compute — watts not kilowatts.*

## Paradigm in one paragraph
Brains compute with sparse, asynchronous binary "spikes" (~1–10 Hz firing); synapses co-locate memory and compute. A GPU does dense N×M float matmul every cycle, paying the von Neumann tax (hauling weights from DRAM through the bus every time) whether a neuron contributes or not. Neuromorphic chips (Loihi 2, SpiNNaker, NorthPole, Akida) invert all three assumptions: only active spikes consume energy (event-driven), weights live next to the neuron (in-/near-memory compute), connectivity is sparse. With activation rates ~1–10%, the theoretical work reduction is 10–100×; combined with killing data movement, 100–1000× energy/op gains are physically grounded. Caveat: gains only materialize when activations are genuinely sparse and the algorithm tolerates temporal binary/integer spike arithmetic.

## Key papers/projects (verified)
- **Intel Hala Point / Loihi 2** (Intel, Apr 2024): world's largest neuromorphic system — 1,152 Loihi 2 chips, 1.15B neurons, 128B synapses, 2,600 W. **15 TOPS/W on conventional 8-bit DNNs** at 10:1 sparsity; up to 100× less energy / 50× faster vs CPU/GPU on suitable workloads.
- **SpiNNaker / SpiNNaker 2** (Manchester / TU Dresden / HBP): 1,036,800 ARM968 cores, ~100 kW, real-time simulation of ~1B neurons; SpiNNaker 2 funded by €8M HBP grant.
- **Spikformer** — arXiv 2209.15425 — first spiking transformer — 74.81% ImageNet, 66.3M params, 4 timesteps. Attention without softmax or multiplication.
- **QKFormer** — arXiv 2403.16552, NeurIPS 2024 Spotlight — **85.65% ImageNet** — first direct-trained SNN >85% on ImageNet; closes most of the gap to ANNs.
- **SpikeBERT** — arXiv 2308.15122 — language spiking transformer distilled from BERT; matches BERT on English/Chinese classification.
- **Online Training Through Time (OTTT)** — arXiv 2210.04195, NeurIPS 2022 — constant-memory SNN training in three-factor Hebbian form — most credible path to on-chip learning.
- **Self-supervised Spikformer-16-512** — arXiv 2511.18542, Nov 2025 — **70.1% ImageNet self-supervised** — first unlabeled SNN pretraining at modern scale.
- **NorthPole** (Modha et al., IBM, Science 2023): inference chip with all memory on-die; ~25× energy-efficiency / ~5× throughput vs GPU on ResNet-50.

## Does it work at LLM scale?
**No.** SNNs now match ANNs on ImageNet (85%+) and small NLP (SpikeBERT ≈ BERT-base on classification), but NO SNN has trained or run a transformer at LLM scale (billions of params, long-context autoregression). Blockers: (a) autoregressive decoding breaks the batch-parallelism GPUs exploit; (b) spike-domain softmax/approximations accumulate error over long sequences; (c) surrogate-gradient BPTT memory scales with timesteps × seq-len; (d) no SNN toolkit supports >1B-param training. SNNs are genuinely competitive for vision sensing, event cameras, edge audio — NOT GPT-class generation.

## Could it cut TRAINING compute?
Mostly no, today. Neuromorphic is sold and benchmarked for INFERENCE (NorthPole, Akida, Loihi). Training-on-neuromorphic is the open frontier: OTTT and on-chip STDP exist but only at toy scale. Reasons: backprop needs high-precision gradients that spikes destroy; modern pretraining needs huge dense matmuls (attention/MLP) that don't map to event-driven hardware. Realistic near-term win: INFERENCE sparsity + continuous online learning for fine-tuning/RL, not pretraining.

## Hegemony angle
Not close for frontier TRAINING — NVIDIA/CUDA's moat is dense-matmul pretraining, which neuromorphic doesn't touch. But for EDGE INFERENCE and always-on agents, neuromorphic (BrainChip Akida already shipping; Intel commercializing) can bypass GPUs entirely — a wedge that erodes the GPU monopoly at the DEPLOYMENT surface, not the training surface. Bigger conceptual threat: if value shifts to inference + continuous learning, the "train-once-on-H100" model weakens.

## Relation to UltraBrain
**Strong fit.** UltraBrain's verifier-gated sparse updates = "only surprising/unverified tokens cost compute." This is EXACTLY the event-driven paradigm at the algorithm layer: the verifier plays the role of the spike threshold; only "surprising" tokens "fire." Stacking UltraBrain on neuromorphic execution gives the same efficiency philosophy at both layers — algorithmic sparsity (verifier gating) on hardware built for sparsity (event-driven cores).

**Concrete bridge:** treat verifier-passing tokens as quiescent neurons (zero work), verifier-failing tokens as spikes (full fwd+bwd). This could make verifier-gated training **10–100× cheaper on commodity GPUs today** (sparse activation skip) and **100–1000× cheaper on neuromorphic hardware** as it matures — a natural staged path.

**Honest summary:** neuromorphic is mature for sensing/edge and now competitive on ImageNet; it is immature for LLM training and may never replace dense matmul for pretraining. Its real near-term value for UltraBrain is CONCEPTUAL (blueprint for verifier-gated sparsity) + INFERENCE/EDGE savings, not a frontal assault on GPU training hegemony.

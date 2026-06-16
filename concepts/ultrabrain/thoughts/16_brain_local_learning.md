# Thought 16 — Brain Local / Forward-Only Learning Rules (No Backprop)

*The biggest compute lever: kill global backprop.*

## Paradigm in one paragraph
Backprop's defining cost isn't FLOPs — it's **globality**: to update a synapse you must (a) store every layer's activations for the whole forward pass, (b) propagate a loss-derived gradient BACKWARD through the exact transpose of the weights, requiring a synchronized backward pass that blocks pipelining. **Local / forward-only rules** kill this. In Feedback Alignment the backward weights are random and fixed; in Equilibrium Propagation the network relaxes to a second energy minimum and the synapse update is `Δw ∝ local_pre × local_post` measured at two times; in Forward-Forward each layer optimizes its own "goodness" on a positive vs negative forward pass; in Predictive Coding each node minimizes its own local prediction error. **A synapse learns from quantities physically present at that synapse** — no activations stored, no backward traversal — enabling streaming, pipelining, on-chip updates.

## Key papers (IDs verified)
- **Lillicrap et al., "Random feedback weights support learning"** — arXiv 1411.0247. *Random backward weights work almost as well as symmetric backprop.*
- **Nøkland, "Direct Feedback Alignment"** — arXiv 1609.01596. *Error jumps directly from output to each layer via fixed random paths — near-BP.*
- **Scellier & Bengio, "Equilibrium Propagation"** — arXiv 1602.04142. *Energy nets learn via relaxation; update provably converges to BP gradient.*
- **Hinton, "The Forward-Forward Algorithm"** — arXiv 2212.13345. *Two forward passes (pos/neg), per-layer goodness — "no activities stored, video pipelined through."*
- **Millidge et al., "Predictive Coding Approximates Backprop"** — arXiv 2006.04182. *PC with purely local/Hebbian updates converges to exact BP gradients.*
- **Pinchetti, Salvatori et al., "Predictive Coding beyond Gaussian"** — arXiv 2211.03481. *Generalized PC trains transformers, matching BP.*
- **Jiang, Al-Hashimi & Xu (May 2026), "Covariance-Aware Goodness for Scalable Forward-Forward"** — arXiv 2605.04346. *BP-free FF hits 73% ImageNet-100, ~50% peak memory cut vs BP.*

## Does it work / maturity — finally scaling, but not at LLM scale
For a decade these were TOY: FA/DFA/EP/FF topped out at MNIST/CIFAR-10, several points behind BP. Real progress arrived 2020–2026:
- EP reached 11.7% on CIFAR-10 (Laborieux, arXiv 2006.03824) — first non-toxy deep ConvNet result.
- PC trained transformers on language, "comparable with BP" (2211.03481).
- Strongest signal: Jiang et al. (May 2026) push BP-free FF to ImageNet-100 (73%) / Tiny-ImageNet (50%), doubling viable FF depth to VGG-16-scale (2605.04346).
- **No paper has backprop-free-trained an LLM.** Gaps to BP on real NLP / billion-parameter pretraining remain large.

## Could it cut training compute >10×? — honest: not FLOPs, but yes on memory + energy
The win is NOT fewer forward FLOPs. Most local rules actually ADD compute (EP needs two relaxation phases; FF needs pos+neg passes; PC needs iterative inference). The genuine >10× lever:
- **Memory:** FF/EPC drop activation storage; Jiang 2026 reports ~50% peak-memory cut. On H100s where activation memory gates batch size, this can translate into large throughput gains.
- **Energy on custom silicon:** binary-stochastic FF on p-bits gives ~one order of magnitude energy savings (Jaiswal, arXiv 2507.06461); memristor/analog EP (2006.01981) computes gradients in Kirchhoff physics. **The 10× lives in neuromorphic hardware, not in the algorithm on a GPU.**

## Hegemony angle — this is the real moat-breaker
If learning is local, training maps onto CHEAP, DISTRIBUTED, LOW-POWER substrate instead of H100 clusters. Agnostic Equilibrium Propagation (Scellier, Bengio, Ollivier — arXiv 2205.15021) proves a physical system can do true order-1 gradient descent WITHOUT knowing its own derivatives — so memristor arrays, analog ASICs, photonic meshes, or edge devices can train in place. No activation checkpointing, no all-reduce of giant gradient tensors, no HBM wall → training can DECENTRALIZE across heterogeneous low-end hardware. **The most credible technical route to dissolving the GPU hegemony, contingent on neuromorphic silicon maturing.**

## Relation to UltraBrain — strong, natural fit
UltraBrain's verified-trace + verifiable rewards are essentially a **dopamine-like scalar** — exactly the form a local rule needs. A verifiable reward can serve as the *output nudge* in EP, the *positive/negative label* in Forward-Forward, or the *top-level prediction error* in Predictive Coding, propagating downward as local signals while each layer updates from locally-available quantities. This unifies two brain motifs the field treats separately: **local plasticity** (how) + **neuromodulatory reward** (what's worth learning). UltraBrain could become the first system where a VERIFIED global signal trains a network with NO global backprop — credible thesis, unproven at scale, the right experiment to run next.

---
**Honest bottom line:** local/forward-only learning is a 10-year underdog that FINALLY exited toy-land in 2025–2026 (FF on ImageNet-100, PC on transformers, EP on CIFAR), but has NOT touched LLM pretraining and does not beat BP on raw FLOPs. Its real, defensible wins are ~2× memory, ~10× energy on neuromorphic silicon, and decentralizability — precisely the axis UltraBrain cares about for breaking the GPU moat.

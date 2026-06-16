# Thought 04 — Flow Matching / Rectified Flow for Discrete Sequences

*Paradigm: transport samples from noise to data via a learned velocity field (ODE).*

## Paradigm in one paragraph
Flow Matching (FM) trains a Continuous Normalizing Flow by regressing a velocity field that
transports samples along fixed conditional probability paths from a source (noise/mask/
uniform) to the data distribution; generation integrates an ODE with an off-the-shelf
solver. Training is simulation-free. Diffusion is the special case; Optimal-Transport and
Rectified-Flow paths are straighter, enabling faster training and 1–few-step sampling.
AR factorizes p(x)=Πp(x_t|x_<t) strictly left-to-right; FM/diffusion model the joint and
refine all positions in parallel — non-sequential, revisable, controllable.

## Key papers (verified)
- **Flow Matching for Generative Modeling** — Lipman et al. 2023 — https://arxiv.org/abs/2210.02747 — Foundation; OT paths beat diffusion on ImageNet.
- **Rectified Flow** — Liu, Gong, Liu 2022 — https://arxiv.org/abs/2209.03003 — Iterative rectification → near-single-step sampling.
- **Stochastic Interpolants** — Albergo, Boffi, Vanden-Eijnden 2023 — https://arxiv.org/abs/2303.08797 — Unifies flows+diffusions.
- **Discrete Flow Matching (DFM)** — Gat et al. Meta FAIR 2024 — https://arxiv.org/abs/2407.15595 — Scaled to 1.7B; non-AR.
- **Dirichlet Flow Matching** — Stark et al. ICML 2024 — https://arxiv.org/abs/2402.05841 — Mixture-of-Dirichlet paths on the simplex.
- **MD4** — Shi et al. DeepMind, NeurIPS 2024 — https://arxiv.org/abs/2406.04329 — State-dependent masking; beats prior diffusion LMs at GPT-2 scale.
- **FS-DFM** — Apple, ICLR 2026 — https://arxiv.org/abs/2509.20624 — **8 steps = 1024-step baseline perplexity, 128× faster** long-text generation.
- **α-Flow** — 2025 — https://arxiv.org/abs/2504.10283 — Information-geometric unified CS-DFM.

## Does it work for text / maturity
FM is mature and dominant in images/audio/proteins (Stable Diffusion 3, Voicebox, RF
protein design). For text it is genuinely catching up but NOT yet frontier-competitive:
DFM's 1.7B scores single-digit HumanEval vs ~50%+ for similar-size AR; FS-DFM/α-Flow
close the perplexity gap but no flow LM matches frontier AR on reasoning/long-context.
**Parallel, controllable, few-step text generation is real; open-ended quality is behind.**

## Could it replace prediction as a foundation?
Not a wholesale replacement today — a strong complementary engine. FM trades serial
left-to-right depth for parallel iterative breadth: better throughput/latency, intrinsic
guidance/controllability, bidirectional context, token revisability. Scaling laws far less
explored than AR's, so the compute-optimal frontier is unsettled. Most likely: AR for
perception/encoding, FM for joint decoding, editing, and search.

## Hegemony angle
Decentralizing on three axes: (a) simulation-free, simple quadratic objectives lower the
training-engineering moat; (b) parallel sampling rewards different hardware (throughput-bound
vs KV-cache-bound AR serving); (c) the open ecosystem (FAIR, Apple, MIT, NVIDIA, academia)
is wide — no single company owns the recipe.

## Relation to UltraBrain
Strong fit for **verifier-guided flow**: define the target measure as the verifier-accepted
region and let the velocity field transport candidates toward it. Dirichlet/α-flow support
classifier & classifier-free guidance; FUDOKI (https://arxiv.org/abs/2505.20147) shows
kinetic-optimal velocities enable test-time scaling. A flow could refine perception outputs
toward verified regions, parallelize candidate-search, and make verification continuous
(verifier as the potential the ODE follows) instead of discrete accept/reject.

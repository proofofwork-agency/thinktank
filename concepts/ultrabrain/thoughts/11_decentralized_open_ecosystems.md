# Thought 11 — Decentralized & Distributed Training + Open Model Ecosystems

*Paradigm: who owns the means of model production.*

## Landscape in one paragraph
A **split market**: open-weight models thrive at the mid-frontier (Llama, Mistral, DeepSeek, Qwen dominate downloads and fine-tunes on Hugging Face), but the absolute capability frontier stays concentrated in 2–3 labs (OpenAI, Anthropic, Google). Decentralized TRAINING is still experimental and aspirational; decentralized INFERENCE and open-weight POST-TRAINING (LoRA/RL) are real and growing. PrimeIntellect's distributed RL, model-merging tools, and open reproductions (Open-R1) made "community-built frontier-ish models" credible — none have matched a closed frontier model on release day.

## Key projects / papers (verified)
- **Petals** — `petals.dev` (Borzunov et al., BigScience). BitTorrent-style decentralized inference: each peer serves a few layers of a 70B–405B model. ~4–6 tok/s — best for research, not production.
- **PrimeIntellect** — `primeintellect.ai` (Founders Fund, Karpathy). INTELLECT-1/2/3 including the "first 32B model trained through globally distributed RL." Compute marketplace + RL hub. The most serious decentralized-training bet.
- **TIES-Merging** — arXiv `2306.01708` (NeurIPS 2023). Resolves parameter sign/redundancy interference when merging many fine-tunes.
- **DARE / "Super Mario"** — arXiv `2311.03099` (ICML 2024). Drops 90–99% of delta params and still merges specialists, sometimes beating any source.
- **Open-R1 / DeepSeek-R1** — DeepSeek-R1 (Jan 2025) is an open-weight 671B MoE rivaling o1; Open-R1 is the community effort to reproduce the missing RL recipe. **Open weights reached the reasoning frontier.**
- **EU AI Act** — Regulation (EU) 2024/1689, in force Aug 2024. Reduced transparency duties for open-source GPAI; systemic-risk threshold at 10^25 FLOPs.

## Is decentralization winning or losing?
**Both, in different lanes.** Open weights clearly win distribution: DeepSeek/Llama/Qwen derivatives are the most-deployed globally and force price compression on closed APIs. But the frontier keeps reconcentrating because of (a) pretraining compute ($100M+ runs), (b) proprietary data + RLHF pipelines, (c) talent accrual to whoever has the most GPUs. Decentralization captures the TAIL (fine-tunes, adapters, merges, local inference) while the HEAD (base pretraining) stays centralized.

## What would actually break the hegemony?
- **Federated/distributed pretraining at frontier scale** — PrimeIntellect-style, but must prove it can hit 10^25+ FLOPs across heterogeneous unreliable nodes without losing efficiency.
- **Composable adapter marketplaces** — TIES/DARE show 100+ specialist adapters can merge into one model.
- **Local-first products with real users** — distribution + sovereignty demand shift capital away from API monopolies.
- **Regulation favoring portability** — DMA-style interoperability + AI Act open-source carve-outs.

## Hegemony angle (core)
**Concentrating forces:** capital (9-figure training runs), exclusive data, talent agglomeration, API/network lock-in.
**Decentralizing forces:** open weights (DeepSeek proved the frontier leaks within months), efficient post-training (LoRA, GRPO) making small players competitive on specific tasks, verified local agents, regulation penalizing opacity.
**Structural truth:** pretraining is a capital-good oligopoly; customization and deployment are increasingly a commons. The hegemony is real at the base layer and eroding everywhere above it.

## Relation to UltraBrain
UltraBrain's local-first + verified + sovereign stance attacks the DEPLOYMENT layer where decentralization is winning. If its outputs are verifiable (provenance/attestation of model + data), it converts the open-weight commons into TRUSTABLE sovereign compute — the missing piece that lets enterprises/individuals choose open models over API monopolies without sacrificing assurance. It doesn't decentralize TRAINING, but it decentralizes ADOPTION, which is where hegemony is actually breakable today.

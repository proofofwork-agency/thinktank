# Thought 02 — Energy-Based Models & LeCun's JEPA (for language)

*Paradigm: predict in abstract latent space, not token space; decode on demand.*

## Paradigm in one paragraph
JEPA (Joint-Embedding Predictive Architecture) is LeCun's bet against generative
reconstruction. Instead of predicting pixels or tokens in input space, an encoder maps
context and target into a shared abstract latent space, and a predictor learns to predict
the target representation from the context representation. A trained energy function scores
compatibility (low energy = plausible). Generation implies a two-stage loop: **predict in
representation space → decode** the latent to tokens. V-JEPA 2 shows planning works by
rolling forward in latent space; VL-JEPA shows text can be produced the same way.

## Key papers
- **I-JEPA** — Assran, LeCun et al., ICCV 2023 — https://arxiv.org/abs/2301.08243 — Vision-only. Foundation: masked-latent prediction beats pixel reconstruction.
- **V-JEPA 2** — Assran, LeCun, Ballas et al., Jun 2025 — https://arxiv.org/abs/2506.09985 — 1B-param video world model; plans in latent space, zero-shot robotics.
- **LLM-JEPA** — Huang, LeCun, Balestriero, Sep 2025 — https://arxiv.org/abs/2509.14252 — First real JEPA-for-language; objective-level win (better representations), not generative.
- **VL-JEPA** — Chen, LeCun, Fung et al., Dec 2025 — https://arxiv.org/abs/2512.10942 — Closest to "predict latent, then decode"; 50% fewer params, 2.85× faster decoding. Evaluated on VQA/retrieval, not long-form generation.
- **LeCun 2022 "A Path Towards Autonomous Machine Intelligence"** — theoretical manifesto.

## Does it work for language / maturity
Mostly aspirational, changing fast. Until Sep 2025 there was zero credible JEPA-for-text
at LLM scale. LLM-JEPA is the first crack — objective-level win, not generative. VL-JEPA
is the first to emit text via latent-then-decode, but only short VQA answers. Nobody is
generating coherent paragraphs with JEPA/EBM at LLM quality.

## Could it replace prediction as a foundation?
The bet: predict semantics in latent space, not surface tokens — could end token-level
hallucination cascades and decouple "thinking" from "spelling." Blockers: (a) text has no
obvious "natural latent" like images (tokens ARE already compressed); (b) the decode gap
— turning a predicted embedding into grammatical controllable tokens is unsolved at scale;
(c) energy-based sampling in high-dim discrete space is slow. **Credible competitor
objective, not yet a credible competitor generator.**

## Hegemony angle
**Strong decentralization potential IF it matures.** JEPA needs far fewer params for
equivalent representation quality (VL-JEPA: 50% fewer), trains on unlabeled data, and an
energy-scorer is cheaper to federate than a trillion-param token-predictor. But today the
latent predictor + decoder still rides on top of transformer LLMs. The architecture is
open; the engineering moat is not yet breached.

## Relation to UltraBrain
**Excellent fit.** UltraBrain keeps prediction for perception — that IS the JEPA thesis:
prediction belongs in representation space, not output space. A verifier-grounded system
can use a JEPA-style latent predictor to draft abstract plans, then verify/ground in token
space — "predict in abstract space, verify in token space." Caveat: UltraBrain would be
pioneering where the field has barely started — high upside, high risk.

*JEPA-for-language is ~6 months old (Sep 2025) as a serious direction. Vision is 3 years
ahead. The "replace token prediction" promise is unproven for generation but the
objective-level wins are real.*

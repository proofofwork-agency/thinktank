# Thought 09 — Self-Supervised Learning Beyond Next-Token Prediction

*Paradigm: alternative training objectives — contrastive, replaced-token detection, span corruption, latent prediction.*

## Paradigm in one paragraph
Teacher-forced next-token prediction (NTP) is one choice among many self-supervised objectives. Alternatives: **(a) reconstructive corruption** — mask/replace/span-corrupt tokens, recover the original (BERT, T5 span-corruption, ELECTRA replaced-token detection); **(b) contrastive** — pull paired views together, push negatives apart via InfoNCE (SimCSE, CPC); **(c) latent predictive / JEPA** — predict the representation of one part from another *without* decoding pixels/tokens (I-JEPA, V-JEPA). LeCun's argument: prediction should happen in **latent**, not token, space, because per-token reconstruction wastes capacity on unpredictable noise.

## Key papers
- **Contrastive Predictive Coding / InfoNCE** — https://arxiv.org/abs/1807.03748 — predict future in latent space via contrastive loss with negatives.
- **ELECTRA (Replaced-Token Detection)** — https://arxiv.org/abs/2003.10555 — discriminator spots swapped tokens; loss over EVERY token, not just masked ~15%. >BERT at ~1/4 FLOPs.
- **T5 / Span Corruption** — https://arxiv.org/abs/1910.10683 — replace sentinel-delimited spans; unified text-to-text.
- **SimCSE** — https://arxiv.org/abs/2104.08821 — Dropout-as-augmentation contrastive; uniformizes anisotropic embedding space.
- **DeBERTa v3** — https://arxiv.org/abs/2006.03654 — Switched MLM → RTD; significant gains — direct evidence non-predictive objective scales.
- **I-JEPA** — https://arxiv.org/abs/2301.08243 — Non-generative latent prediction; ImageNet-quality representations without hand-crafted augmentations.

## Does it work / maturity
ELECTRA and RTD-DeBERTa empirically beat MLM at same compute — RTD's "loss on every token" is genuinely more sample-efficient. Span corruption scaled to 11B (T5) but underperformed decoder-only NTP at equal params. Contrastive dominates embedding/retrieval but never produced competitive open-ended generators. **No non-NTP objective has matched AR NTP at frontier scale for generation.** They win on classification/retrieval or compute-efficiency, but the scaling laws (Kaplan 2020; Chinchilla 2022) were measured on NTP, and the GPT lineage inherited that trajectory.

## Could it replace prediction as a foundation?
NTP won for three EMPIRICAL reasons, not theoretical optimality: (i) labels are free — every token is its own target, no augmentation design; (ii) fits causal masking on GPUs with zero wasted compute; (iii) the same model that trains is the model that samples — pretraining = inference. RTD and contrastive break (iii): an encoder/discriminator cannot autoregressively generate. JEPA breaks it harder — there is no decoder. **A better objective could unseat NTP only if it (a) matches scaling laws and (b) solves the pretrain/inference identity.**

## Hegemony angle
Different objectives → different compute/data profiles. Contrastive/JEPA need encoders + target-encoders + EMA tricks; RTD needs a co-trained generator. None are bottlenecked by the single-vendor CUDA/H100 stack the way dense AR NTP is. **The wedge: decouple the perception model (alternative objective, smaller compute) from the generation model (NTP, hegemonic compute).**

## Relation to UltraBrain
UltraBrain's verified-trace pipeline offers a THIRD family beyond reconstructive/contrastive/JEPA: a **verifier-grounded objective** where the signal is not "what token comes next" but "does this trace satisfy an external checker." Structurally analogous to RTD (binary accept/reject over every step) but with a SEMANTIC verifier, not a token-level one. UltraBrain could: (a) use NTP only for the perception backbone, (b) train the reasoning head with JEPA-style latent-prediction over verified intermediate states, or (c) borrow InfoNCE to contrast verified vs unverified traces. The verified-trace signal is rarer than free NTP labels but far denser than RLHF — and does NOT require the pretrain/inference identity that locks in the NTP hegemony.

*Prediction won empirically. No objective here has beaten NTP at GPT-4 class scale. The opportunity is in perception/reasoning sub-modules, not in replacing the generator wholesale.*

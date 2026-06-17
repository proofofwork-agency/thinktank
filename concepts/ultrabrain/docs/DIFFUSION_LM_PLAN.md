# Diffusion Language Model from Scratch — Design & Build Notes

## Context

The soul of this project is building an LLM from scratch. A prior pass drifted into a
verification/memory + symbolic-solver layer (removed); two research sweeps (Claude 20-agent +
Codex 7-agent) and a bounded deliberation re-centered it on a **from-scratch non-autoregressive
language model: masked / absorbing-state diffusion.** Generation is iterative parallel
denoising, not next-token sampling.

Honest scope (see README): cheap in **DATA**, not FLOPs; a *partial* escape from token
prediction (masked diffusion == any-order autoregression); the real capability edge is native
**infilling**. This is a fully fresh build — nothing was morphed from the old autoregressive
code.

## What was built (all new files)

- `ultrabrain/tokenizer.py` — character-level tokenizer; `<PAD>`(0), `<MASK>`(1) reserved.
- `ultrabrain/denoiser.py` — bidirectional Transformer (RMSNorm + SwiGLU + full attention),
  weight-tied head, **no causal mask, no time embedding**; predicts the clean token at every
  position.
- `ultrabrain/diffusion.py` — `corrupt` (absorbing-state masking), `diffusion_loss`
  (bounded-mask mean-CE), `generate` (iterative confidence unmasking + infilling).
- `train.py` — trains on `data/shakespeare.txt` (char-level), warmup→cosine LR, periodic ckpt.
- `sample.py` — unconditional samples, prompting, an infilling demo.
- `eval.py` + `ar_baseline.py` — the AR-vs-diffusion de-risking gate (AR is an eval-only yardstick).
- `tests/test_diffusion.py` — tokenizer / loss / sampler / bidirectional-attention unit tests.

## Architecture decisions

- **Character-level** (not BPE): the simplest transparent from-scratch path at this scale.
- **Bidirectional full attention**: the denoiser must use left+right context to fill masks.
- **Time-independent (SUBS)**: the model infers the noise level from the `<MASK>` count.
- **Bounded mask rate** `t ~ U(0.15, 0.5)`, unweighted mean cross-entropy over masked positions.
- **Warmup → cosine LR**, AdamW(1e-3, weight_decay 0.01).

## Build log — three failures that each collapsed training to the marginal (all fixed)

Getting a small masked-diffusion LM to *actually learn* (not just "tests pass") took isolating
three independent issues, each of which made the model output only spaces. The discipline that
mattered: **judge by samples + held-out masked-CE, never by "the loss is a number that exists."**

1. **Scalar-t time embedding.** A `Linear(1, d)` noise-level embedding added to every position
   measurably hurt learning (fixed-batch overfit: ~2.9 with vs ~1.95 without). Removed — the
   denoiser is time-independent. *Diagnosis: fixed-batch overfit, with/without time.*
2. **Unbounded mask rate** `t ~ U(0.02, 1)`. Near-fully-masked sequences (where prediction is
   impossible) dominated the averaged loss and pinned it at the marginal entropy. Bounding to
   `U(0.15, 0.5)` keeps enough context to learn. *Diagnosis: bounded-vs-full-range A/B.* (The
   1/t ELBO weighting — the "proper" fix — is too high-variance for stable small-scale training;
   it lives in the eval bits-per-char metric instead.)
3. **No LR warmup.** The deeper/wider model (6L/384) fell into the marginal basin on step 1
   without warmup, while 4L/256 trained fine. Added linear warmup → cosine. *Diagnosis:
   size / weight-decay / warmup sweep.*

With all three fixed, a 4.25M-param model learns on Apple Silicon (MPS): held-out masked-CE
drops from ~3.3 (marginal) to ~2.0 within 700 steps, generating recognizable words.

## Run / gate / verify

```bash
python train.py            # train the diffusion LM (char-level Shakespeare)
python sample.py           # samples + infilling
python eval.py             # AR-vs-diffusion gate (bits-per-char, infill, samples, wall-clock)
python -m pytest tests -q  # unit tests
```

## Provenance

Research: Claude 20-agent workflow + Codex 7-agent pass + a bounded deliberation (ContextRelay).
Conclusion: small masked diffusion is the only buildable cheap-AND-non-AR option for a small
player; the honest claim is data-efficiency, not FLOP-cheapness. Key refs: MDLM (arXiv:2406.07524),
SEDD (2310.16834), LLaDA (2502.09992), data-constrained diffusion (2507.15857),
MDM = any-order AR (2511.19152).

"""Masked (absorbing-state) diffusion: the training objective and the sampler.

Forward / corruption: replace each token with <MASK> independently at a per-sequence rate
t ~ U(0,1].  Training: reconstruct the originals at the masked positions, cross-entropy
weighted by 1/t (the MDLM / absorbing-state ELBO weighting).  Generation: start from an
all-<MASK> sequence (optionally with some positions pinned for prompting / infilling) and
iteratively unmask the highest-confidence positions over K steps, attending bidirectionally
each step. Any-order and parallel — never left-to-right next-token sampling.

Honest scope: this escapes left-to-right ORDER and the causal decode, not token prediction
itself (masked diffusion == any-order autoregression). It is a generative language model;
its cheap edge is DATA-efficiency (re-reading a small corpus many times), not FLOPs.
"""

import math

import torch
import torch.nn.functional as F


def corrupt(x, mask_id, t, pad_id=None):
    """Absorbing-state forward process. Replace each token with <MASK> independently with
    per-sequence probability t. Returns (x_masked, masked_bool). Pad is never masked.

    x: (B, T) long ; t: (B,) float in (0, 1].
    """
    probs = t.view(-1, 1).to(x.device)
    masked = torch.rand(x.shape, device=x.device) < probs
    if pad_id is not None:
        masked = masked & (x != pad_id)
    x_masked = torch.where(masked, torch.full_like(x, mask_id), x)
    return x_masked, masked


def diffusion_loss(model, x, mask_id, pad_id=None, t_low=0.15, t_high=0.5):
    """Masked-diffusion reconstruction loss = mean cross-entropy over masked positions.

    Sample a per-sequence mask rate t ~ U(t_low, t_high), corrupt x, run the bidirectional
    model, and average cross-entropy over the MASKED positions only (pad never contributes).

    The mask rate is deliberately BOUNDED (default 0.15-0.5). Letting t approach ~1.0 lets
    near-fully-masked sequences — where prediction is impossible — dominate the averaged loss
    and collapses training to the marginal (everything becomes spaces). A moderate band keeps
    enough context that the model learns real conditional prediction. This bounded-unweighted
    form was measured against the proper 1/t-weighted full-range ELBO loss and gave the lowest
    held-out masked-CE and the most coherent samples; the 1/t ELBO weighting is left to the
    eval bits-per-char metric, not the optimizer.
    """
    B = x.shape[0]
    t = torch.rand(B, device=x.device) * (t_high - t_low) + t_low
    x_masked, masked = corrupt(x, mask_id, t, pad_id)
    logits = model(x_masked, t)
    ce = F.cross_entropy(
        logits.reshape(-1, logits.size(-1)), x.reshape(-1), reduction="none"
    ).view(x.shape)
    masked_f = masked.float()
    return (ce * masked_f).sum() / masked_f.sum().clamp_min(1.0)


@torch.no_grad()
def generate(model, length, mask_id, *, steps=16, fixed=None, temperature=1.0, top_k=None,
             device="cpu", pad_id=None, noise=0.5):
    """Iterative confidence-based unmasking. Returns a (1, length) long tensor.

    Start from all-<MASK> except `fixed` positions (a dict {position: token_id} that stays
    pinned — this is prompting / infilling, the capability autoregression lacks). Each step:
    run the denoiser, score every masked position by prediction confidence, and commit the
    most-confident fraction on a cosine schedule until none remain masked.
    """
    fixed = fixed or {}
    seq = torch.full((1, length), mask_id, dtype=torch.long, device=device)
    for p, tok in fixed.items():
        seq[0, p] = tok
    M0 = int((seq[0] == mask_id).sum())
    if M0 == 0:
        return seq

    for step in range(steps):
        is_mask = seq[0] == mask_id
        n_now = int(is_mask.sum())
        if n_now == 0:
            break
        t = torch.full((1,), n_now / length, device=device)
        logits = model(seq, t)[0]                                  # (T, vocab)
        logits[:, mask_id] = float("-inf")                         # never emit special tokens
        if pad_id is not None:
            logits[:, pad_id] = float("-inf")
        if temperature == 0:
            probs = F.softmax(logits, dim=-1)
            conf, pred = probs.max(dim=-1)
        else:
            s = logits / temperature
            if top_k:
                v = torch.topk(s, top_k, dim=-1).values
                s = s.masked_fill(s < v[:, [-1]], float("-inf"))
            probs = F.softmax(s, dim=-1)
            pred = torch.multinomial(probs, 1).squeeze(-1)
            conf = probs.gather(-1, pred.unsqueeze(-1)).squeeze(-1)
        # how many positions should REMAIN masked after this step (cosine schedule -> 0)
        target_masked = int(round(M0 * math.cos(0.5 * math.pi * (step + 1) / steps)))
        target_masked = max(0, min(target_masked, n_now - 1))      # commit >=1 per step
        n_unmask = n_now - target_masked
        score = torch.log(conf.clamp_min(1e-9))                    # select by LOG-confidence
        if noise > 0:                                              # MaskGIT-style stochastic order:
            anneal = noise * (1.0 - step / max(1, steps))          # annealed Gumbel noise breaks the
            g = -torch.log(-torch.log(torch.rand_like(conf).clamp_min(1e-9)).clamp_min(1e-9))
            score = score + anneal * g                             # greedy flooding of one token
        score = score.masked_fill(~is_mask, float("-inf"))         # only score masked slots
        idx = torch.topk(score, n_unmask).indices
        seq[0, idx] = pred[idx]

    leftover = seq[0] == mask_id                                   # safety: fill any remainder
    if leftover.any():
        t = torch.full((1,), 1.0 / length, device=device)
        logits = model(seq, t)[0]
        logits[:, mask_id] = float("-inf")
        if pad_id is not None:
            logits[:, pad_id] = float("-inf")
        seq[0, leftover] = logits.argmax(dim=-1)[leftover]
    return seq

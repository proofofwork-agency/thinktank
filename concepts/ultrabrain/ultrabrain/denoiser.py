"""Bidirectional Transformer denoiser — the network behind the diffusion LM.

FULL (non-causal) self-attention: every position attends to every other position, because
the denoiser must use both left and right context to reconstruct masked tokens. It infers the
noise level from how many <MASK> tokens it sees (a time-independent SUBS denoiser; an explicit
scalar-t embedding was tried and removed because it measurably hurt learning). Written from
scratch on torch primitives only — no nn.Transformer, no scaled_dot_product_attention, and no
causal mask anywhere. This is NOT the old autoregressive GPT with a flag flipped; it is a new
model for a new (non-AR) approach.
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class Config:
    def __init__(self, vocab_size, n_layer=6, n_head=6, n_embd=384, block=128, dropout=0.1):
        self.vocab_size = vocab_size
        self.n_layer, self.n_head, self.n_embd = n_layer, n_head, n_embd
        self.block, self.dropout = block, dropout


class RMSNorm(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.g = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        return self.g * x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + 1e-6)


class BidirectionalAttention(nn.Module):
    """Full self-attention. The absence of a causal mask is the whole point."""

    def __init__(self, c):
        super().__init__()
        self.nh, self.hd = c.n_head, c.n_embd // c.n_head
        self.qkv = nn.Linear(c.n_embd, 3 * c.n_embd, bias=False)
        self.proj = nn.Linear(c.n_embd, c.n_embd, bias=False)
        self.drop = nn.Dropout(c.dropout)

    def forward(self, x):
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, self.nh, self.hd).transpose(1, 2)
        k = k.view(B, T, self.nh, self.hd).transpose(1, 2)
        v = v.view(B, T, self.nh, self.hd).transpose(1, 2)
        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.hd)
        att = self.drop(F.softmax(att, dim=-1))          # no causal mask: bidirectional
        y = (att @ v).transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(y)


class SwiGLU(nn.Module):
    def __init__(self, c):
        super().__init__()
        h = 4 * c.n_embd
        self.w1 = nn.Linear(c.n_embd, h, bias=False)
        self.w2 = nn.Linear(c.n_embd, h, bias=False)
        self.w3 = nn.Linear(h, c.n_embd, bias=False)
        self.drop = nn.Dropout(c.dropout)

    def forward(self, x):
        return self.drop(self.w3(F.silu(self.w1(x)) * self.w2(x)))


class Block(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.n1, self.att = RMSNorm(c.n_embd), BidirectionalAttention(c)
        self.n2, self.mlp = RMSNorm(c.n_embd), SwiGLU(c)

    def forward(self, x):
        x = x + self.att(self.n1(x))
        return x + self.mlp(self.n2(x))


class Denoiser(nn.Module):
    """Predicts the clean token at EVERY position from a partially-masked sequence + the
    scalar noise level. Output is logits over the vocab; the loss (on masked positions only)
    lives in diffusion.py, keeping this module a pure predictor."""

    def __init__(self, c):
        super().__init__()
        self.c = c
        self.tok = nn.Embedding(c.vocab_size, c.n_embd)
        self.pos = nn.Embedding(c.block, c.n_embd)
        self.drop = nn.Dropout(c.dropout)
        self.blocks = nn.ModuleList(Block(c) for _ in range(c.n_layer))
        self.norm = RMSNorm(c.n_embd)
        self.head = nn.Linear(c.n_embd, c.vocab_size, bias=False)
        self.head.weight = self.tok.weight               # weight tying
        self.apply(self._init)

    def _init(self, m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, std=0.02)

    def forward(self, idx, t=None):
        # t (noise/mask level) is accepted for API symmetry with the sampler but intentionally
        # UNUSED: an absorbing masked-diffusion denoiser infers the level from the <MASK> count,
        # and an explicit scalar-t embedding measurably hurt learning here.
        B, T = idx.shape
        x = self.tok(idx) + self.pos(torch.arange(T, device=idx.device))
        x = self.drop(x)
        for b in self.blocks:
            x = b(x)
        return self.head(self.norm(x))                   # (B, T, vocab_size)

    def num_params(self):
        return sum(p.numel() for p in self.parameters())

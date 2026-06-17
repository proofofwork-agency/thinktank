"""Eval-only causal AR yardstick for the diffusion benchmark.

This is deliberately not the product. It exists only so eval.py can compare the
masked-diffusion LM against a same-size-ish causal character model trained on
the same corpus slice for the same number of token exposures.
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class ARConfig:
    def __init__(self, vocab_size, n_layer=1, n_head=2, n_embd=64, block=64, dropout=0.1):
        self.vocab_size = vocab_size
        self.n_layer, self.n_head, self.n_embd = n_layer, n_head, n_embd
        self.block, self.dropout = block, dropout


class RMSNorm(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.g = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        return self.g * x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + 1e-6)


class CausalAttention(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.nh, self.hd = c.n_head, c.n_embd // c.n_head
        self.qkv = nn.Linear(c.n_embd, 3 * c.n_embd, bias=False)
        self.proj = nn.Linear(c.n_embd, c.n_embd, bias=False)
        self.drop = nn.Dropout(c.dropout)
        self.register_buffer("mask", torch.tril(torch.ones(c.block, c.block)).view(1, 1, c.block, c.block))

    def forward(self, x):
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, self.nh, self.hd).transpose(1, 2)
        k = k.view(B, T, self.nh, self.hd).transpose(1, 2)
        v = v.view(B, T, self.nh, self.hd).transpose(1, 2)
        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.hd)
        att = att.masked_fill(self.mask[:, :, :T, :T] == 0, float("-inf"))
        att = self.drop(F.softmax(att, dim=-1))
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
        self.n1, self.att = RMSNorm(c.n_embd), CausalAttention(c)
        self.n2, self.mlp = RMSNorm(c.n_embd), SwiGLU(c)

    def forward(self, x):
        x = x + self.att(self.n1(x))
        return x + self.mlp(self.n2(x))


class ARCharLM(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.c = c
        self.tok = nn.Embedding(c.vocab_size, c.n_embd)
        self.pos = nn.Embedding(c.block, c.n_embd)
        self.drop = nn.Dropout(c.dropout)
        self.blocks = nn.ModuleList(Block(c) for _ in range(c.n_layer))
        self.norm = RMSNorm(c.n_embd)
        self.head = nn.Linear(c.n_embd, c.vocab_size, bias=False)
        self.head.weight = self.tok.weight
        self.apply(self._init)

    def _init(self, m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, std=0.02)

    def forward(self, idx, targets=None):
        B, T = idx.shape
        x = self.drop(self.tok(idx) + self.pos(torch.arange(T, device=idx.device)))
        for b in self.blocks:
            x = b(x)
        logits = self.head(self.norm(x))
        if targets is None:
            return logits, None
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
        return logits, loss

    @torch.no_grad()
    def generate(self, idx, max_new, temperature=1.0, top_k=None, stop_ids=None):
        stop_ids = set(stop_ids or [])
        for _ in range(max_new):
            logits, _ = self(idx[:, -self.c.block:])
            logits = logits[:, -1, :]
            for sid in stop_ids:
                logits[:, sid] = float("-inf")
            if temperature == 0:
                nxt = logits.argmax(-1, keepdim=True)
            else:
                logits = logits / temperature
                if top_k:
                    v = torch.topk(logits, top_k).values
                    logits = logits.masked_fill(logits < v[:, [-1]], float("-inf"))
                nxt = torch.multinomial(F.softmax(logits, dim=-1), 1)
            idx = torch.cat([idx, nxt], dim=1)
        return idx

    def num_params(self):
        return sum(p.numel() for p in self.parameters())

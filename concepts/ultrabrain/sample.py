"""Generate from a trained masked-diffusion LM: unconditional samples, prompting, infilling.

  python sample.py                         # unconditional samples + an infill demo
  python sample.py --prompt "ROMEO:"       # prefix-conditioned generation

Infilling (pinning a prefix AND a suffix, filling the middle) is the capability an
autoregressive model cannot do natively — it falls straight out of any-order denoising.
"""

import argparse
import os

import torch

from ultrabrain.tokenizer import CharTokenizer
from ultrabrain.denoiser import Config, Denoiser
from ultrabrain import diffusion

ROOT = os.path.dirname(os.path.abspath(__file__))
CKPT = os.path.join(ROOT, "checkpoints")


def pick_device():
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load(ckpt_path, tok_path, dev):
    ck = torch.load(ckpt_path, map_location=dev, weights_only=True)
    tok = CharTokenizer.load(tok_path)
    c = Config(ck["vocab_size"], ck["n_layer"], ck["n_head"], ck["n_embd"], ck["block"])
    m = Denoiser(c).to(dev)
    m.load_state_dict(ck["model"])
    m.eval()
    return m, tok, c


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=os.path.join(CKPT, "diffusion.pt"))
    ap.add_argument("--tok", default=os.path.join(CKPT, "tokenizer.json"))
    ap.add_argument("--steps", type=int, default=32)
    ap.add_argument("--temperature", type=float, default=0.9)
    ap.add_argument("--top_k", type=int, default=20)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--prompt", default="")
    args = ap.parse_args(argv)

    dev = pick_device()
    m, tok, c = load(args.ckpt, args.tok, dev)
    L = c.block

    def gen(fixed=None):
        out = diffusion.generate(m, L, tok.mask_id, steps=args.steps, fixed=fixed,
                                 temperature=args.temperature, top_k=args.top_k, device=dev,
                                 pad_id=tok.pad_id)
        return tok.decode(out[0].tolist())

    print("=== unconditional ===", flush=True)
    for _ in range(args.n):
        print(repr(gen()), flush=True)

    if args.prompt:
        ids = tok.encode(args.prompt)[:L]
        print("=== prompted ('%s') ===" % args.prompt, flush=True)
        print(repr(gen({i: t for i, t in enumerate(ids)})), flush=True)

    # infill demo: pin a prefix and a suffix, let the model fill the middle
    pre, suf = "ROMEO: ", " good night."
    pre_ids, suf_ids = tok.encode(pre)[:L // 3], tok.encode(suf)[:L // 3]
    fixed = {i: t for i, t in enumerate(pre_ids)}
    for j, t in enumerate(suf_ids):
        fixed[L - len(suf_ids) + j] = t
    print("=== infill (prefix + suffix pinned, middle generated) ===", flush=True)
    print(repr(gen(fixed)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

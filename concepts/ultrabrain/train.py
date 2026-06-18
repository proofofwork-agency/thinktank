"""Train the masked-diffusion LM from scratch on a character corpus (default: Shakespeare).

No autoregression anywhere. The model learns to reconstruct masked spans of clean text, and
is trained for MANY passes over the corpus — the data-efficiency regime where masked diffusion
earns its keep. Saves checkpoints/diffusion.pt + checkpoints/tokenizer.json.

  python train.py                       # full default run
  python train.py --steps 300 --n_layer 2 --n_embd 128 --max_chars 200000   # quick check
"""

import argparse
import math
import os
import time

import torch

from ultrabrain.tokenizer import Tokenizer
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


def get_batch(data, bs, block, dev):
    ix = torch.randint(len(data) - block, (bs,))
    return torch.stack([data[i:i + block] for i in ix]).to(dev)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=4000)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--block", type=int, default=128)
    ap.add_argument("--n_layer", type=int, default=6)
    ap.add_argument("--n_head", type=int, default=6)
    ap.add_argument("--n_embd", type=int, default=384)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--warmup", type=int, default=200)
    ap.add_argument("--corpus", default=os.path.join(ROOT, "data", "shakespeare.txt"))
    ap.add_argument("--max_chars", type=int, default=0, help="cap corpus size (0 = all)")
    ap.add_argument("--merges", type=int, default=2000, help="BPE merges (vocab ~ 256+merges+5)")
    ap.add_argument("--span_prob", type=float, default=0.25, help="fraction of batches masked as a contiguous span (infilling); rest scattered")
    ap.add_argument("--out", default=os.path.join(CKPT, "diffusion.pt"))
    ap.add_argument("--tok_out", default=os.path.join(CKPT, "tokenizer.json"))
    ap.add_argument("--eval_every", type=int, default=500)
    ap.add_argument("--sample_steps", type=int, default=24)
    args = ap.parse_args(argv)

    os.makedirs(CKPT, exist_ok=True)
    torch.manual_seed(1337)
    dev = pick_device()

    text = open(args.corpus).read()
    if args.max_chars:
        text = text[:args.max_chars]
    tok = Tokenizer.build(text, num_merges=args.merges)
    tok.save(args.tok_out)
    data = torch.tensor(tok.encode(text), dtype=torch.long)
    n = int(0.9 * len(data))
    train_data, val_data = data[:n], data[n:]
    print(f"device={dev} vocab={tok.vocab_size} chars={len(data)} "
          f"block={args.block} batch={args.batch} steps={args.steps}", flush=True)

    model = Denoiser(Config(tok.vocab_size, args.n_layer, args.n_head, args.n_embd, args.block)).to(dev)
    print(f"params={model.num_params() / 1e6:.2f}M", flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)

    def lr_lambda(step):                              # linear warmup -> cosine decay
        if step < args.warmup:
            return (step + 1) / max(1, args.warmup)
        progress = (step - args.warmup) / max(1, args.steps - args.warmup)
        return 0.5 * (1.0 + math.cos(math.pi * min(1.0, progress)))

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda)

    def save_ckpt():
        torch.save({
            "model": model.state_dict(),
            "vocab_size": tok.vocab_size, "n_layer": args.n_layer, "n_head": args.n_head,
            "n_embd": args.n_embd, "block": args.block,
        }, args.out)

    @torch.no_grad()
    def val_loss(iters=20):
        model.eval()
        v = sum(diffusion.diffusion_loss(model, get_batch(val_data, args.batch, args.block, dev),
                                         tok.mask_id, tok.pad_id, span_prob=args.span_prob).item()
                for _ in range(iters))
        model.train()
        return v / iters

    t0 = time.time()
    for step in range(1, args.steps + 1):
        x = get_batch(train_data, args.batch, args.block, dev)
        loss = diffusion.diffusion_loss(model, x, tok.mask_id, tok.pad_id, span_prob=args.span_prob)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step == 1 or step % 100 == 0:
            print(f"step {step:5d} loss {loss.item():.3f} ({time.time() - t0:.0f}s)", flush=True)
        if step % args.eval_every == 0:
            print(f"  val_loss {val_loss():.3f}", flush=True)
            s = diffusion.generate(model, args.block, tok.mask_id, steps=args.sample_steps,
                                   temperature=0.9, top_k=20, device=dev, pad_id=tok.pad_id)
            print("  sample:", repr(tok.decode(s[0].tolist()))[:180], flush=True)
            save_ckpt()  # periodic checkpoint so a long/interrupted run stays recoverable

    save_ckpt()
    print(f"FINAL val_loss {val_loss():.3f} | saved {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

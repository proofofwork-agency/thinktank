"""Data-efficiency experiment: does masked diffusion beat AR under SCARCE data?

This is the actual anti-hegemony claim, reproduced locally. Fix a SMALL unique corpus and
train an autoregressive baseline and a same-size masked-diffusion model on it for MANY
passes, tracking held-out bits-per-char over training.

The thesis (Prabhudesai et al., NeurIPS 2025, "Diffusion Beats Autoregressive in
Data-Constrained Settings"): an AR model overfits a small corpus -- its validation loss
U-shapes (drops, then rises) -- while diffusion's random masking acts as implicit data
augmentation, so it keeps extracting signal across many epochs and eventually wins. The
takeaway for a small player: with little unique data but spare compute, spend epochs the
AR model cannot use.

Honest metric caveat: AR bits/char is EXACT next-token NLL; diffusion bits/char is an
ELBO-style UPPER BOUND (Monte-Carlo). So a crossover where the diffusion upper bound drops
below AR's exact value is a *conservative* win for diffusion.

  python data_efficiency.py                       # default: 30k chars, 6000 steps
  python data_efficiency.py --chars 15000 --steps 8000
"""

import argparse
import os

import torch

from ar_baseline import ARCharLM, ARConfig
from ultrabrain.denoiser import Config as DConfig, Denoiser
from ultrabrain.tokenizer import CharTokenizer
from ultrabrain.diffusion import diffusion_loss
from eval import ar_bpc, diffusion_bpc_upper_bound, get_batch, get_ar_batch, pick_device

ROOT = os.path.dirname(os.path.abspath(__file__))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--chars", type=int, default=30000, help="SMALL unique-data budget")
    ap.add_argument("--steps", type=int, default=6000)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--block", type=int, default=64)
    ap.add_argument("--n_layer", type=int, default=4)
    ap.add_argument("--n_head", type=int, default=4)
    ap.add_argument("--n_embd", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--eval_interval", type=int, default=500)
    ap.add_argument("--mc", type=int, default=8)
    ap.add_argument("--span_prob", type=float, default=0.25)
    ap.add_argument("--corpus", default=os.path.join(ROOT, "data", "shakespeare.txt"))
    ap.add_argument("--device", default=None)
    args = ap.parse_args(argv)

    torch.manual_seed(1337)
    dev = args.device or pick_device()
    text = open(args.corpus).read()[:args.chars]
    tok = CharTokenizer.build(text)
    data = torch.tensor(tok.encode(text), dtype=torch.long)
    n = int(0.9 * len(data))
    train_data, val_data = data[:n], data[n:]
    tps = args.batch * args.block
    print(f"device={dev} unique_train_chars={len(train_data)} vocab={tok.vocab_size} "
          f"tokens/step={tps} (~{tps/len(train_data):.3f} epochs/step)", flush=True)

    ar = ARCharLM(ARConfig(tok.vocab_size, args.n_layer, args.n_head, args.n_embd, args.block)).to(dev)
    diff = Denoiser(DConfig(tok.vocab_size, args.n_layer, args.n_head, args.n_embd, args.block)).to(dev)
    ar_opt = torch.optim.AdamW(ar.parameters(), lr=args.lr, weight_decay=0.01)
    diff_opt = torch.optim.AdamW(diff.parameters(), lr=args.lr, weight_decay=0.01)

    print(f"\n{'step':>6} {'epochs':>7} {'AR_BPC(exact)':>13} {'diff_BPC(bound)':>15}", flush=True)
    rows = []
    for step in range(1, args.steps + 1):
        x, y = get_ar_batch(train_data, args.batch, args.block, dev)
        _, arl = ar(x, y)
        ar_opt.zero_grad(set_to_none=True); arl.backward(); ar_opt.step()
        xd = get_batch(train_data, args.batch, args.block, dev)
        dl = diffusion_loss(diff, xd, tok.mask_id, tok.pad_id, span_prob=args.span_prob)
        diff_opt.zero_grad(set_to_none=True); dl.backward(); diff_opt.step()
        if step % args.eval_interval == 0:
            arb = ar_bpc(ar, val_data, args.block, dev)
            dfb = diffusion_bpc_upper_bound(diff, val_data, args.block, tok.mask_id, tok.pad_id, dev, args.mc)
            ep = step * tps / len(train_data)
            rows.append((step, ep, arb, dfb))
            flag = "  <- diffusion ahead" if dfb < arb else ""
            print(f"{step:>6} {ep:>7.1f} {arb:>13.3f} {dfb:>15.3f}{flag}", flush=True)

    if not rows:
        print("\nNo eval points recorded (need --steps >= --eval_interval).")
        return 0
    ar_best = min(r[2] for r in rows)
    ar_best_step = next(r[0] for r in rows if r[2] == ar_best)
    ar_final, df_final = rows[-1][2], rows[-1][3]
    cross = [r[0] for r in rows if r[3] < r[2]]
    print("\n=== verdict ===", flush=True)
    print(f"AR exact BPC: best {ar_best:.3f} @ step {ar_best_step}, final {ar_final:.3f} "
          f"(overfit gap +{ar_final - ar_best:.3f})", flush=True)
    print(f"diffusion BPC (ELBO upper bound): final {df_final:.3f}", flush=True)
    if cross:
        print(f"CROSSOVER at step {cross[0]}: the diffusion UPPER BOUND drops below AR's EXACT "
              f"bits/char. Under scarce data + many epochs, diffusion's data-reuse beats AR, "
              f"which overfits. This is the data-efficiency thesis, locally.", flush=True)
    else:
        print("No crossover at this budget (AR still ahead). Try fewer --chars or more --steps.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Train the v0.3 action-prediction model from synthetic verified-action traces."""

import argparse
import os
import random
import time

import torch

from data.action_traces import build_dataset
from ultrabrain.actions import parse_action
from ultrabrain.model import Config, GPT
from ultrabrain.tokenizer import Tokenizer


torch.manual_seed(1337)
random.seed(1337)
ROOT = os.path.dirname(os.path.abspath(__file__))
CKPT = os.path.join(ROOT, "checkpoints")
DEV = "mps" if torch.backends.mps.is_available() else "cpu"
LR = 3e-4


def build_tokenizer(pairs, num_merges=128):
    sample = "\n".join(f"{ctx} {action}" for ctx, action in pairs)
    tok = Tokenizer.train(sample, num_merges=num_merges)
    os.makedirs(CKPT, exist_ok=True)
    tok.save(os.path.join(CKPT, "action_tokenizer.json"))
    return tok


def encode_pairs(tok, pairs, block):
    S, SEP, E, PAD = (tok.special[s] for s in ("<S>", "<SEP>", "<E>", "<PAD>"))
    rows = []
    for sent, logic in pairs:
        ids = [S] + tok.encode(sent) + [SEP] + tok.encode(logic) + [E]
        if len(ids) <= block:
            rows.append((ids, len(tok.encode(sent)) + 2))  # loss starts after SEP
    return rows, PAD


def pair_batch(rows, pad, bs, device):
    picks = random.sample(rows, min(bs, len(rows)))
    L = max(len(r[0]) for r in picks)
    x = torch.full((len(picks), L - 1), pad)
    y = torch.full((len(picks), L - 1), pad)
    for i, (ids, start) in enumerate(picks):
        t = torch.tensor(ids)
        x[i, :len(ids) - 1] = t[:-1]
        y[i, start - 1:len(ids) - 1] = t[start:]
    return x.to(device), y.to(device)


def predict_action(model, tok, context, device, max_new=20):
    was_training = model.training
    model.eval()
    S, SEP, E = tok.special["<S>"], tok.special["<SEP>"], tok.special["<E>"]
    idx = torch.tensor([[S] + tok.encode(context) + [SEP]], device=device)
    out = model.generate(idx, max_new, temperature=0, stop_id=E)[0].tolist()
    try:
        start = out.index(SEP) + 1
    except ValueError:
        start = len(idx[0])
    text = tok.decode(out[start:]).replace("<E>", "").strip()
    if was_training:
        model.train()
    return parse_action(text), text


@torch.no_grad()
def action_acc(model, tok, holdout, device, n=100):
    sample = holdout[:n]
    if not sample:
        return 0.0
    ok = 0
    for context, gold in sample:
        pred, _text = predict_action(model, tok, context, device)
        ok += pred == gold
    return ok / len(sample)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=1500)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--synthetic-n", type=int, default=800)
    args = parser.parse_args(argv)

    os.makedirs(CKPT, exist_ok=True)
    train, holdout = build_dataset(synthetic_n=args.synthetic_n)
    corpus = train + holdout
    print(f"action pairs train={len(train)} holdout={len(holdout)}", flush=True)
    tok = build_tokenizer(corpus)
    print(f"tokenizer vocab={tok.vocab_size}", flush=True)

    steps = 30 if args.quick else args.steps
    block = 96
    batch = 16 if args.quick else 64
    n_layer = 1 if args.quick else 4
    n_embd = 64 if args.quick else 256
    n_head = 4 if args.quick else 8
    rows, PAD = encode_pairs(tok, train, block)
    if not rows:
        raise RuntimeError("no action training rows fit in block size")

    model = GPT(Config(tok.vocab_size, n_layer=n_layer, n_head=n_head, n_embd=n_embd, block=block)).to(DEV)
    print(f"params={sum(p.numel() for p in model.parameters())/1e6:.2f}M device={DEV}", flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.1)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)

    t0 = time.time()
    for step in range(1, steps + 1):
        x, y = pair_batch(rows, PAD, batch, DEV)
        _, loss = model(x, y, pad_id=PAD)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step == 1 or step == steps or step % max(1, steps // 5) == 0:
            acc = action_acc(model, tok, holdout, DEV, n=min(80, len(holdout)))
            print(f"step {step:4d} loss {loss.item():.3f} holdout_action_acc {acc:.2%} ({time.time()-t0:.0f}s)", flush=True)

    acc = action_acc(model, tok, holdout, DEV, n=min(200, len(holdout)))
    path = os.path.join(CKPT, "action_gpt.pt")
    torch.save({
        "model": model.state_dict(),
        "vocab": tok.vocab_size,
        "n_layer": n_layer,
        "n_embd": n_embd,
        "n_head": n_head,
        "block": block,
        "synthetic_n": args.synthetic_n,
        "steps": steps,
    }, path)
    print(f"saved {path}", flush=True)
    print(f"FINAL holdout action acc: {acc:.2%}", flush=True)
    for context, gold in holdout[:3]:
        pred, text = predict_action(model, tok, context, DEV)
        print(f"sample gold={gold} pred={pred} raw={text!r}", flush=True)


if __name__ == "__main__":
    main()

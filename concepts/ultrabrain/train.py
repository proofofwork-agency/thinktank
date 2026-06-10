"""Train UltraBrain's perception LM from scratch: BPE -> GPT on Shakespeare + NL->logic pairs."""

import os
import time

import torch

from data.synth import make_pairs, split
from ultrabrain.model import GPT, Config
from ultrabrain.tokenizer import Tokenizer

torch.manual_seed(1337)
ROOT = os.path.dirname(os.path.abspath(__file__))
CKPT = os.path.join(ROOT, "checkpoints")
DEV = "mps" if torch.backends.mps.is_available() else "cpu"
BLOCK, BATCH, STEPS, LR = 128, 64, 5000, 3e-4


def build_tokenizer(shake, pairs):
    sample = shake[:400_000] + "\n" + "\n".join(f"{s} {l}" for s, l in pairs[:4000])
    tok = Tokenizer.train(sample, num_merges=256)
    tok.save(os.path.join(CKPT, "tokenizer.json"))
    return tok


def encode_pairs(tok, pairs):
    S, SEP, E, PAD = (tok.special[s] for s in ("<S>", "<SEP>", "<E>", "<PAD>"))
    rows = []
    for sent, logic in pairs:
        ids = [S] + tok.encode(sent) + [SEP] + tok.encode(logic) + [E]
        if len(ids) <= BLOCK:
            rows.append((ids, len(tok.encode(sent)) + 2))  # loss starts after SEP
    return rows, PAD


def pair_batch(rows, pad, bs):
    import random
    picks = random.sample(rows, bs)
    L = max(len(r[0]) for r in picks)
    x = torch.full((bs, L - 1), pad)
    y = torch.full((bs, L - 1), pad)
    for i, (ids, start) in enumerate(picks):
        t = torch.tensor(ids)
        x[i, :len(ids) - 1] = t[:-1]
        y[i, start - 1:len(ids) - 1] = t[start:]
    return x.to(DEV), y.to(DEV)


def text_batch(data, bs):
    ix = torch.randint(len(data) - BLOCK - 1, (bs,))
    x = torch.stack([data[i:i + BLOCK] for i in ix])
    y = torch.stack([data[i + 1:i + BLOCK + 1] for i in ix])
    return x.to(DEV), y.to(DEV)


@torch.no_grad()
def translation_acc(model, tok, holdout, n=100):
    model.eval()
    S, SEP, E = tok.special["<S>"], tok.special["<SEP>"], tok.special["<E>"]
    ok = 0
    fwd = [(s, l) for s, l in holdout if "(" in l][:n]
    for sent, logic in fwd:
        idx = torch.tensor([[S] + tok.encode(sent) + [SEP]], device=DEV)
        out = model.generate(idx, 40, temperature=0, stop_id=E)[0].tolist()
        hyp = tok.decode(out[out.index(SEP) + 1:]).replace("<E>", "").strip()
        ok += hyp == logic
    model.train()
    return ok / len(fwd)


def main():
    os.makedirs(CKPT, exist_ok=True)
    shake = open(os.path.join(ROOT, "data", "shakespeare.txt")).read()
    train_pairs, holdout = split(make_pairs(12000))
    print(f"pairs train={len(train_pairs)} holdout={len(holdout)}", flush=True)
    tok = build_tokenizer(shake, train_pairs)
    print(f"tokenizer vocab={tok.vocab_size}", flush=True)

    data = torch.tensor(tok.encode(shake), dtype=torch.long)
    rows, PAD = encode_pairs(tok, train_pairs)
    model = GPT(Config(tok.vocab_size, n_layer=8, n_embd=448, block=BLOCK)).to(DEV)
    print(f"params={sum(p.numel() for p in model.parameters())/1e6:.2f}M device={DEV}", flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.1)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, STEPS)

    t0 = time.time()
    for step in range(1, STEPS + 1):
        x, y = text_batch(data, BATCH) if step % 2 else pair_batch(rows, PAD, BATCH)
        _, loss = model(x, y, pad_id=PAD)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % 250 == 0 or step == 1:
            print(f"step {step:4d} loss {loss.item():.3f} ({time.time()-t0:.0f}s)", flush=True)
        if step % 1250 == 0:
            print(f"  holdout translation acc: {translation_acc(tok=tok, model=model, holdout=holdout):.2%}", flush=True)

    torch.save({"model": model.state_dict(), "vocab": tok.vocab_size,
                "n_layer": 8, "n_embd": 448}, os.path.join(CKPT, "gpt.pt"))
    acc = translation_acc(model, tok, holdout, n=200)
    print(f"FINAL holdout translation acc (200): {acc:.2%}", flush=True)
    idx = torch.tensor([tok.encode("ROMEO:")], device=DEV)
    print("--- shakespeare sample ---", flush=True)
    print(tok.decode(model.generate(idx, 200, temperature=0.8, top_k=50)[0].tolist()), flush=True)


if __name__ == "__main__":
    main()

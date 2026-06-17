"""AR-vs-diffusion head-to-head benchmark.

This benchmark is the de-risking gate for the masked-diffusion LM. The AR model
is trained here only as a yardstick; it is not the product.
"""

import argparse
import json
import math
import os
import time

import torch
import torch.nn.functional as F

from ar_baseline import ARCharLM, ARConfig
from ultrabrain.denoiser import Config as DenoiserConfig, Denoiser
from ultrabrain.diffusion import corrupt, diffusion_loss, generate
from ultrabrain.tokenizer import CharTokenizer


ROOT = os.path.dirname(os.path.abspath(__file__))


def pick_device():
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def get_batch(data, batch, block, device):
    ix = torch.randint(len(data) - block - 1, (batch,))
    return torch.stack([data[i:i + block] for i in ix]).to(device)


def get_ar_batch(data, batch, block, device):
    ix = torch.randint(len(data) - block - 1, (batch,))
    rows = torch.stack([data[i:i + block + 1] for i in ix]).to(device)
    return rows[:, :-1], rows[:, 1:]


def ngrams(text, n):
    return [text[i:i + n] for i in range(max(0, len(text) - n + 1))]


def distinct_n(text, n):
    grams = ngrams(text, n)
    return len(set(grams)) / len(grams) if grams else 0.0


def repetition_rate(text, n=4):
    return 1.0 - distinct_n(text, n)


@torch.no_grad()
def ar_bpc(model, data, block, device):
    model.eval()
    total_nll, total_chars = 0.0, 0
    for start in range(0, len(data) - 1, block):
        chunk = data[start:start + block + 1]
        if len(chunk) < 2:
            continue
        x = chunk[:-1].unsqueeze(0).to(device)
        y = chunk[1:].unsqueeze(0).to(device)
        logits, _ = model(x)
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1), reduction="sum")
        total_nll += float(loss.item())
        total_chars += int(y.numel())
    return total_nll / max(1, total_chars) / math.log(2)


@torch.no_grad()
def diffusion_bpc_upper_bound(model, data, block, mask_id, pad_id, device, mc=8, t_min=0.02):
    """Monte-Carlo estimate of an ELBO-style upper-bound proxy in bits/char.

    Unlike AR NLL, this is not exact likelihood. It estimates weighted masked CE
    per original token, so the report labels it as an upper bound/proxy.
    """
    model.eval()
    total, total_chars = 0.0, 0
    for start in range(0, len(data), block):
        chunk = data[start:start + block]
        if len(chunk) == 0:
            continue
        x = chunk.unsqueeze(0).to(device)
        for _ in range(mc):
            t = torch.rand(1, device=device) * (1 - t_min) + t_min
            x_masked, masked = corrupt(x, mask_id, t, pad_id)
            logits = model(x_masked, t)
            ce = F.cross_entropy(logits.reshape(-1, logits.size(-1)), x.reshape(-1), reduction="none").view(x.shape)
            total += float((ce * (1.0 / t).view(1, 1) * masked.float()).sum().item())
            total_chars += int(x.numel())
    return total / max(1, total_chars) / math.log(2)


@torch.no_grad()
def diffusion_mask_accuracy(model, data, block, mask_id, pad_id, device, mask_rate=0.25, batches=8):
    model.eval()
    hits, total = 0, 0
    for _ in range(batches):
        x = get_batch(data, 1, block, device)
        t = torch.full((1,), mask_rate, device=device)
        x_masked, masked = corrupt(x, mask_id, t, pad_id)
        pred = model(x_masked, t).argmax(dim=-1)
        hits += int((pred[masked] == x[masked]).sum().item())
        total += int(masked.sum().item())
    return hits / total if total else 0.0


@torch.no_grad()
def infill_eval(model, tok, heldout, block, device, steps, examples=8):
    model.eval()
    span_accs, exacts, rows = [], [], []
    stride = max(1, (len(heldout) - block) // max(1, examples))
    for i in range(examples):
        offset = min(max(0, len(heldout) - block), i * stride)
        text = tok.decode(heldout[offset:offset + block].tolist())
        ids = torch.tensor(tok.encode(text), dtype=torch.long)
        length = min(block, len(ids))
        ids = ids[:length]
        span = max(4, min(24, length // 4))
        start = max(0, (length - span) // 2)
        end = start + span
        fixed = {j: int(tok_id) for j, tok_id in enumerate(ids.tolist()) if not (start <= j < end)}
        out = generate(
            model,
            length,
            tok.mask_id,
            steps=steps,
            fixed=fixed,
            temperature=0,
            device=device,
            pad_id=tok.pad_id,
            noise=0,
        )[0].cpu()
        gold = ids[start:end]
        pred = out[start:end]
        acc = float((pred == gold).float().mean().item()) if len(gold) else 0.0
        exact = bool(torch.equal(pred, gold))
        span_accs.append(acc)
        exacts.append(exact)
        rows.append({
            "offset": offset,
            "span_start": start,
            "span_len": span,
            "exact_match": exact,
            "char_accuracy": acc,
            "gold": tok.decode(gold.tolist()),
            "pred": tok.decode(pred.tolist(), show_mask=True),
            "context": tok.decode(ids.tolist(), show_mask=True),
        })
    first = rows[0] if rows else {}
    return {
        "examples": len(rows),
        "exact_match_rate": sum(exacts) / len(exacts) if exacts else 0.0,
        "char_accuracy": sum(span_accs) / len(span_accs) if span_accs else 0.0,
        "representative": first,
        "note": "AR baseline is not scored here: bidirectional middle-span infilling is the diffusion capability edge.",
    }


@torch.no_grad()
def sample_diffusion(model, tok, length, steps, device):
    model.eval()
    ids = generate(
        model,
        length,
        tok.mask_id,
        steps=steps,
        temperature=0.9,
        top_k=20,
        device=device,
        pad_id=tok.pad_id,
    )[0].cpu().tolist()
    return tok.decode(ids, show_mask=True)


@torch.no_grad()
def sample_ar(model, tok, prompt, length, device):
    model.eval()
    x = torch.tensor([tok.encode(prompt)], dtype=torch.long, device=device)
    out = model.generate(x, length, temperature=0.9, top_k=20, stop_ids={tok.pad_id, tok.mask_id})[0].cpu().tolist()
    return tok.decode(out)


def train_ar(model, train_data, args, device):
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.1)
    t0 = time.time()
    for _ in range(args.steps):
        x, y = get_ar_batch(train_data, args.batch, args.block, device)
        logits, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
    return time.time() - t0


def train_diffusion(model, train_data, tok, args, device):
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.1)
    t0 = time.time()
    for _ in range(args.steps):
        x = get_batch(train_data, args.batch, args.block, device)
        loss = diffusion_loss(model, x, tok.mask_id, tok.pad_id, args.t_low, args.t_high)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
    return time.time() - t0


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="Fast smoke benchmark")
    ap.add_argument("--corpus", default=os.path.join(ROOT, "data", "shakespeare.txt"))
    ap.add_argument("--max_chars", type=int, default=120_000)
    ap.add_argument("--steps", type=int, default=250)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--block", type=int, default=128)
    ap.add_argument("--n_layer", type=int, default=3)
    ap.add_argument("--n_head", type=int, default=4)
    ap.add_argument("--n_embd", type=int, default=192)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--mc", type=int, default=16, help="MC samples for diffusion bound")
    ap.add_argument("--sample_steps", type=int, default=16)
    ap.add_argument("--infill_examples", type=int, default=8)
    ap.add_argument("--t_low", type=float, default=0.15)
    ap.add_argument("--t_high", type=float, default=0.5)
    ap.add_argument("--bound_t_min", type=float, default=0.02)
    ap.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    args = ap.parse_args(argv)

    if args.quick:
        args.max_chars = 20_000
        args.steps = 25
        args.batch = 8
        args.block = 64
        args.n_layer = 1
        args.n_head = 2
        args.n_embd = 64
        args.mc = 4
        args.sample_steps = 8
        args.infill_examples = 2

    torch.manual_seed(1337)
    device = pick_device()
    text = open(args.corpus).read()
    if args.max_chars:
        text = text[:args.max_chars]
    tok = CharTokenizer.build(text)
    data = torch.tensor(tok.encode(text), dtype=torch.long)
    split = int(0.9 * len(data))
    train_data, val_data = data[:split], data[split:]
    if len(train_data) < args.block + 2 or len(val_data) < args.block + 2:
        raise ValueError("corpus slice too small for block size")

    ar = ARCharLM(ARConfig(tok.vocab_size, args.n_layer, args.n_head, args.n_embd, args.block)).to(device)
    diff = Denoiser(DenoiserConfig(tok.vocab_size, args.n_layer, args.n_head, args.n_embd, args.block)).to(device)

    ar_time = train_ar(ar, train_data, args, device)
    diff_time = train_diffusion(diff, train_data, tok, args, device)
    tokens_seen = args.steps * args.batch * args.block
    unique_train_chars = int(train_data.numel())
    passes = tokens_seen / unique_train_chars

    ar_bits = ar_bpc(ar, val_data, args.block, device)
    diff_bits = diffusion_bpc_upper_bound(diff, val_data, args.block, tok.mask_id, tok.pad_id, device, args.mc, args.bound_t_min)
    infill = infill_eval(diff, tok, val_data, args.block, device, args.sample_steps, args.infill_examples)
    diff_sample = sample_diffusion(diff, tok, args.block, args.sample_steps, device)
    prompt = tok.decode(val_data[: min(16, len(val_data))].tolist())
    ar_sample = sample_ar(ar, tok, prompt, max(0, args.block - len(prompt)), device)

    decision = (
        "If AR wins decisively on exact bits-per-char and wall-clock, the honest verdict is: "
        "diffusion is kept for infilling/edit-anywhere and any-order controllability, NOT a compute/hegemony claim."
    )
    ar_decisive = ar_bits < diff_bits * 0.95 and ar_time < diff_time * 0.95
    verdict = (
        "AR wins this quick/local gate on loss and wall-clock; keep diffusion for infilling/editing only."
        if ar_decisive else
        "Diffusion remains worth further local study; inspect loss, wall-clock, and infilling together."
    )

    result = {
        "device": device,
        "config": {
            "quick": args.quick,
            "chars_total": int(data.numel()),
            "unique_train_chars": unique_train_chars,
            "steps": args.steps,
            "batch": args.batch,
            "block": args.block,
            "n_layer": args.n_layer,
            "n_head": args.n_head,
            "n_embd": args.n_embd,
            "tokens_seen_each": tokens_seen,
            "passes_over_unique_train_chars": passes,
            "diffusion_train_t_low": args.t_low,
            "diffusion_train_t_high": args.t_high,
            "diffusion_bound_t_min": args.bound_t_min,
        },
        "params": {
            "ar_yardstick": ar.num_params(),
            "diffusion": diff.num_params(),
        },
        "metrics": {
            "ar_bits_per_char_exact_nll": ar_bits,
            "diffusion_bits_per_char_elbo_upper_bound_mc": diff_bits,
            "diffusion_bound_mc_samples": args.mc,
            "ar_train_wall_seconds": ar_time,
            "diffusion_train_wall_seconds": diff_time,
            "diffusion_mask_accuracy_25pct": diffusion_mask_accuracy(
                diff, val_data, args.block, tok.mask_id, tok.pad_id, device, batches=4 if args.quick else 12
            ),
        },
        "infilling": infill,
        "samples": {
            "ar": {
                "text": ar_sample,
                "distinct_2": distinct_n(ar_sample, 2),
                "distinct_4": distinct_n(ar_sample, 4),
                "repetition_rate_4": repetition_rate(ar_sample, 4),
            },
            "diffusion": {
                "text": diff_sample,
                "distinct_2": distinct_n(diff_sample, 2),
                "distinct_4": distinct_n(diff_sample, 4),
                "repetition_rate_4": repetition_rate(diff_sample, 4),
            },
        },
        "decision_rule": decision,
        "verdict": verdict,
        "notes": [
            "AR bits-per-char is exact next-character NLL / ln(2).",
            "Diffusion bits-per-char is a Monte-Carlo ELBO-style upper-bound/proxy, not exact likelihood.",
            "Both models use the same tokenizer, corpus slice, step count, batch, block, and token exposure.",
            "The AR model is an eval-only yardstick and not the product.",
            "Diffusion training uses the product bounded mask-rate distribution; the bound metric still samples the wider ELBO-style range.",
        ],
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("=== AR vs diffusion head-to-head ===")
        print(f"device={device} quick={args.quick}")
        print(f"unique_train_chars={unique_train_chars} tokens_seen_each={tokens_seen} passes={passes:.2f}")
        print(f"params ar_yardstick={ar.num_params()/1e6:.3f}M diffusion={diff.num_params()/1e6:.3f}M")
        print(f"AR exact bits/char: {ar_bits:.3f}")
        print(f"Diffusion ELBO upper-bound/proxy bits/char (MC={args.mc}): {diff_bits:.3f}")
        print(f"train wall-clock seconds: AR={ar_time:.2f} diffusion={diff_time:.2f}")
        print(f"diffusion infill exact_rate={infill['exact_match_rate']:.2%} char_acc={infill['char_accuracy']:.2%} examples={infill['examples']}")
        rep = infill.get("representative", {})
        print(f"infill representative gold={rep.get('gold', '')!r}")
        print(f"infill representative pred={rep.get('pred', '')!r}")
        print(f"AR sample distinct-2={result['samples']['ar']['distinct_2']:.3f} rep4={result['samples']['ar']['repetition_rate_4']:.3f}")
        print(f"Diff sample distinct-2={result['samples']['diffusion']['distinct_2']:.3f} rep4={result['samples']['diffusion']['repetition_rate_4']:.3f}")
        print("AR sample:", repr(ar_sample[:220]))
        print("Diff sample:", repr(diff_sample[:220]))
        print("Decision rule:", decision)
        print("Verdict:", verdict)
    return result


def main(argv=None):
    run(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

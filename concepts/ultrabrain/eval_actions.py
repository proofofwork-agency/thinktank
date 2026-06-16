"""Evaluate the action model with honest weak baselines and log promotion."""

import argparse
import os
import random
from collections import Counter

import torch

from data.action_traces import build_dataset
from train_actions import predict_action
from ultrabrain.actions import ACTIONS
from ultrabrain.model import Config, GPT
from ultrabrain.self_learning import ExperienceLedger
from ultrabrain.tokenizer import Tokenizer


ROOT = os.path.dirname(os.path.abspath(__file__))
CKPT = os.path.join(ROOT, "checkpoints")
DEV = "mps" if torch.backends.mps.is_available() else "cpu"


def load_model(path):
    ckpt = torch.load(path, map_location=DEV)
    model = GPT(Config(
        ckpt["vocab"],
        n_layer=ckpt.get("n_layer", 4),
        n_head=ckpt.get("n_head", 8),
        n_embd=ckpt.get("n_embd", 256),
        block=ckpt.get("block", 96),
    )).to(DEV)
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model, ckpt


@torch.no_grad()
def model_accuracy(model, tok, holdout):
    if not holdout:
        return 0.0, []
    rows = []
    ok = 0
    for context, gold in holdout:
        pred, raw = predict_action(model, tok, context, DEV)
        hit = pred == gold
        ok += hit
        rows.append({"gold": gold, "pred": pred, "raw": raw, "ok": hit})
    return ok / len(holdout), rows


def majority_accuracy(train, holdout):
    majority = Counter(action for _ctx, action in train).most_common(1)[0][0]
    return sum(action == majority for _ctx, action in holdout) / len(holdout), majority


def random_accuracy(holdout, seed=1337):
    rng = random.Random(seed)
    return sum(action == rng.choice(ACTIONS) for _ctx, action in holdout) / len(holdout)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Evaluate the quick smoke checkpoint shape")
    parser.add_argument("--checkpoint", default=os.path.join(CKPT, "action_gpt.pt"))
    parser.add_argument("--tokenizer", default=os.path.join(CKPT, "action_tokenizer.json"))
    parser.add_argument("--state-root", default=os.path.join(ROOT, "state"))
    args = parser.parse_args(argv)

    tok = Tokenizer.load(args.tokenizer)
    model, ckpt = load_model(args.checkpoint)
    train, holdout = build_dataset(synthetic_n=ckpt.get("synthetic_n", 800))
    acc, rows = model_accuracy(model, tok, holdout)
    majority_acc, majority = majority_accuracy(train, holdout)
    random_acc = random_accuracy(holdout)
    passed = acc > majority_acc and acc > random_acc
    metrics = {
        "holdout_size": len(holdout),
        "synthetic_n": ckpt.get("synthetic_n", 800),
        "action_accuracy": acc,
        "majority_baseline_accuracy": majority_acc,
        "majority_action": majority,
        "random_baseline_accuracy": random_acc,
        "beats_baselines": passed,
        "baseline_note": "Majority-class and random-action baselines are used because gpt.pt was trained on NL->logic, not verified actions.",
        "sample_size_note": "Synthetic-augmented action traces; useful for pipeline validation, not a substitute for large real trace volume.",
    }
    ledger = ExperienceLedger("action_model", root=args.state_root)
    ledger.record_eval("action_model", passed=passed, metrics=metrics, notes=metrics["baseline_note"])
    print(f"holdout_action_acc={acc:.2%}", flush=True)
    print(f"majority_baseline={majority_acc:.2%} ({majority})", flush=True)
    print(f"random_baseline={random_acc:.2%}", flush=True)
    print(f"beats_baselines={passed}", flush=True)
    for row in rows[:5]:
        print(f"sample gold={row['gold']} pred={row['pred']} ok={row['ok']} raw={row['raw']!r}", flush=True)


if __name__ == "__main__":
    main()

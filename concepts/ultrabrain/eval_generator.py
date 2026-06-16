"""Evaluate verifier-grounded math generation."""

from __future__ import annotations

import argparse
import os

from data.math_problems import default_problems
from ultrabrain.math_core import verify
from ultrabrain.search import HeuristicPolicy, solve_search
from ultrabrain.self_learning import ExperienceLedger


ROOT = os.path.dirname(os.path.abspath(__file__))


def _policy(policy_name):
    if policy_name == "heuristic":
        return HeuristicPolicy()
    if policy_name == "step":
        raise ValueError("step policy is not implemented in Slice A")
    raise ValueError(f"unknown policy: {policy_name}")


def evaluate_policy(policy_name="heuristic", problems=None):
    problems = list(problems or default_problems())
    policy = _policy(policy_name)
    rows = []
    certified = 0
    false_answers = 0
    nodes = 0
    for item in problems:
        problem = item["problem"]
        deriv = solve_search(problem, policy)
        nodes += deriv.nodes_expanded
        ok = False
        if deriv.certified:
            certified += 1
            ok = verify(problem, deriv.answer)["accepted"]
            if not ok:
                false_answers += 1
        rows.append({
            "problem": problem,
            "expected": item["answer"],
            "certified": deriv.certified,
            "answer": deriv.answer,
            "verified": ok,
            "nodes_expanded": deriv.nodes_expanded,
        })
    total = len(problems)
    return {
        "policy": policy_name,
        "problem_count": total,
        "certified": certified,
        "solve_rate": certified / total if total else 0.0,
        "false_answers": false_answers,
        "total_nodes_expanded": nodes,
        "efficiency": certified / nodes if nodes else 0.0,
        "rows": rows,
    }


def evaluate_sampler_baseline(checkpoint, tokenizer_path, problems=None):
    if not os.path.exists(checkpoint) or not os.path.exists(tokenizer_path):
        return {"skipped": True, "reason": "checkpoint or tokenizer missing"}
    try:
        import torch
        from ultrabrain.model import Config, GPT
        from ultrabrain.tokenizer import Tokenizer
    except Exception as exc:
        return {"skipped": True, "reason": f"torch/model unavailable: {exc}"}

    try:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        ckpt = torch.load(checkpoint, map_location=device)
        tok = Tokenizer.load(tokenizer_path)
        model = GPT(Config(
            ckpt["vocab"],
            n_layer=ckpt.get("n_layer", 4),
            n_head=ckpt.get("n_head", 8),
            n_embd=ckpt.get("n_embd", 256),
            block=ckpt.get("block", 128),
        )).to(device)
        model.load_state_dict(ckpt["model"])
        model.eval()
    except Exception as exc:
        return {"skipped": True, "reason": f"checkpoint load failed: {exc}"}

    problems = list(problems or default_problems())
    correct = 0
    attempted = 0
    rows = []
    specials = tok.special
    with torch.no_grad():
        for item in problems:
            ids = [specials["<S>"]] + tok.encode(item["problem"]) + [specials["<SEP>"]]
            idx = torch.tensor([ids], dtype=torch.long, device=device)
            out = model.generate(idx, max_new=32, temperature=0, stop_id=specials["<E>"])[0].tolist()
            gen = out[len(ids):]
            if specials["<E>"] in gen:
                gen = gen[:gen.index(specials["<E>"])]
            raw = tok.decode(gen).replace("<E>", "").strip()
            attempted += bool(raw)
            accepted = verify(item["problem"], raw)["accepted"] if raw else False
            correct += accepted
            rows.append({"problem": item["problem"], "raw": raw, "accepted": accepted})
    total = len(problems)
    return {
        "skipped": False,
        "label": "out-of-domain sampler; the contrast shows verifier-in-the-loop guarantees correctness, not that our model is smarter",
        "solve_rate": attempted / total if total else 0.0,
        "correct_rate": correct / total if total else 0.0,
        "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", choices=["heuristic", "step"], default="heuristic")
    parser.add_argument("--checkpoint", default=os.path.join(ROOT, "checkpoints", "gpt.pt"))
    parser.add_argument("--tokenizer", default=os.path.join(ROOT, "checkpoints", "tokenizer.json"))
    parser.add_argument("--state-root", default=os.path.join(ROOT, "state"))
    parser.add_argument("--user", default="verified_generator")
    parser.add_argument("--skip-baseline", action="store_true")
    args = parser.parse_args(argv)

    metrics = evaluate_policy(args.policy)
    baseline = None if args.skip_baseline else evaluate_sampler_baseline(args.checkpoint, args.tokenizer)
    passed = metrics["solve_rate"] == 1.0 and metrics["false_answers"] == 0
    payload = dict(metrics)
    if baseline is not None:
        payload["token_sampler_baseline"] = baseline
    notes = "pass requires solve_rate==1.0 on the supported fixture and false_answers==0"
    ExperienceLedger(args.user, root=args.state_root).record_eval(
        "verified_generator",
        passed=passed,
        metrics=payload,
        notes=notes,
    )
    print(f"policy={args.policy}")
    print(f"solve_rate={metrics['solve_rate']:.2%}")
    print(f"false_answers={metrics['false_answers']}")
    print(f"efficiency={metrics['efficiency']:.4f}")
    if baseline is not None:
        if baseline.get("skipped"):
            print(f"token_sampler_baseline=skipped ({baseline['reason']})")
        else:
            print(f"token_sampler_solve_rate={baseline['solve_rate']:.2%}")
            print(f"token_sampler_correct_rate={baseline['correct_rate']:.2%}")
            print(f"token_sampler_label={baseline['label']}")
    print(f"passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Slice 2 — the verified-search loop (the data-forge).

For each task a proposer samples N candidates; the hardened gate certifies; CERTIFIED solutions
are written to the HMAC ledger AND to an SFT dataset (``data/verified_traces.jsonl``) of
``{task_id, prompt, solution, kind}`` — the verified, sovereign training data for QLoRA.
This is how the weights get better without a frontier teacher: ``no evidence -> no clean training
example`` (thoughts/22, 24).

  python run_verified_search.py --proposer mock                       # zero-ML, tests the loop
  python run_verified_search.py --proposer llm \
      --base_url http://localhost:8000/v1 --model Qwen/Qwen3-Coder-14B  # your local Qwen3-Coder-14B
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from ultrabrain.propose import NoisyProposer  # noqa: E402
from ultrabrain.propose.llm import LLMProposer, prompt_for  # noqa: E402
from ultrabrain.verify import CASVerifier, CodeTestVerifier, Gate, Ledger, harden  # noqa: E402


def load_jsonl(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def build_proposer(args):
    if args.proposer == "llm":
        return LLMProposer(base_url=args.base_url, model=args.model, temperature=args.temperature)
    return NoisyProposer(seed=args.seed)


def verifier_for(task):
    return CASVerifier() if task.get("kind") == "cas" else CodeTestVerifier(harden(task))


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default=os.path.join(ROOT, "tasks", "micro_codebench.jsonl"))
    ap.add_argument("--proposer", choices=["mock", "llm"], default="mock")
    ap.add_argument("--n", type=int, default=8, help="candidates sampled per task")
    ap.add_argument("--base_url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-Coder-14B")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "verified_traces.jsonl"))
    ap.add_argument("--ledger", default=os.path.join(ROOT, "state", "verified_ledger.jsonl"))
    ap.add_argument("--ledger_secret", default=None, help="HMAC secret (else ULTRABRAIN_LEDGER_SECRET)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    tasks = load_jsonl(args.tasks)
    proposer = build_proposer(args)
    ledger = Ledger(args.ledger, secret=args.ledger_secret)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    traces, solved, attempts = [], 0, 0
    t0 = time.time()
    for task in tasks:
        gate = Gate(verifier_for(task), ledger)
        for candidate in proposer.propose(task, args.n):
            attempts += 1
            outcome = gate.judge(task, candidate)
            if outcome.certified:
                traces.append({
                    "task_id": task.get("id"),
                    "kind": task.get("kind", "code"),
                    "prompt": prompt_for(task),
                    "solution": candidate,
                    "verify_detail": outcome.verdict.detail,
                })
                solved += 1
                break  # one verified trace per task is enough for the dataset
    wall = time.time() - t0

    with open(args.out, "w") as fh:
        for tr in traces:
            fh.write(json.dumps(tr) + "\n")

    result = {
        "proposer": args.proposer,
        "tasks": len(tasks),
        "solved": solved,
        "attempts": attempts,
        "traces_written": len(traces),
        "out": args.out,
        "wall_seconds": round(wall, 3),
        "seconds_per_solved": round(wall / solved, 4) if solved else None,
        "ledger_chain_ok": ledger.verify_chain(),
        "note": "every written trace passed the hardened gate -> the SFT set is verified by construction",
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"proposer={args.proposer} solved {solved}/{len(tasks)} "
              f"({attempts} attempts, {result['seconds_per_solved']}s/solved)")
        print(f"wrote {len(traces)} verified traces -> {args.out}  ledger_ok={result['ledger_chain_ok']}")
    return result


def main(argv=None):
    run(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

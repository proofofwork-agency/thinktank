"""Slice 2 — the verified-search loop (the data-forge).

For each task a proposer samples N candidates; the hardened gate certifies; CERTIFIED solutions
are written to the HMAC ledger AND to an SFT dataset (``data/verified_traces.jsonl``) of
``{task_id, prompt, solution, kind}`` — the verified, sovereign training data for QLoRA.
This is how the weights get better without a frontier teacher: ``no evidence -> no clean training
example`` (thoughts/22, 24).

SECURITY (Codex review): ``--proposer llm`` executes UNTRUSTED model output, so code execution runs
through the OS-isolated runner by default and FAILS CLOSED if isolation is unavailable; and because
this path writes trusted beliefs, a private ledger secret is REQUIRED. ``--unsafe`` overrides both
(dev only). The mock proposer runs only our own reference/distractor code, so it does not isolate.

  python run_verified_search.py --proposer mock --ledger_secret dev    # zero-ML, tests the loop
  ULTRABRAIN_LEDGER_SECRET=$(openssl rand -hex 16) \
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

from ultrabrain.propose import DiffusionFIMProposer, NoisyProposer  # noqa: E402
from ultrabrain.propose.llm import LLMProposer, prompt_for  # noqa: E402
from ultrabrain.verify import (  # noqa: E402
    CASVerifier,
    CodeTestVerifier,
    Gate,
    ISOLATION_AVAILABLE,
    Ledger,
    harden,
    run_tests_isolated,
)


def load_jsonl(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def build_proposer(args):
    if args.proposer == "llm":
        return LLMProposer(base_url=args.base_url, model=args.model, temperature=args.temperature)
    if args.proposer == "fim":
        kw = {"temperature": args.temperature, "seed": args.seed}
        if args.fim_checkpoint:
            kw["checkpoint"] = args.fim_checkpoint
        if args.fim_tokenizer:
            kw["tokenizer_path"] = args.fim_tokenizer
        return DiffusionFIMProposer(**kw)
    return NoisyProposer(seed=args.seed)


def verifier_for(task, isolated=False):
    """CAS for cas tasks; hardened execution for code — OS-isolated when ``isolated`` (untrusted)."""
    if task.get("kind") == "cas":
        return CASVerifier()
    return CodeTestVerifier(harden(task), runner=run_tests_isolated if isolated else None)


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default=os.path.join(ROOT, "tasks", "micro_codebench.jsonl"))
    ap.add_argument("--proposer", choices=["mock", "llm", "fim"], default="mock")
    ap.add_argument("--n", type=int, default=8, help="candidates sampled per task")
    ap.add_argument("--base_url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-Coder-14B")
    ap.add_argument("--fim_checkpoint", default=None,
                    help="diffusion denoiser checkpoint for --proposer fim (default: checkpoints/diffusion.pt)")
    ap.add_argument("--fim_tokenizer", default=None,
                    help="tokenizer json for --proposer fim (default: checkpoints/tokenizer.json)")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "verified_traces.jsonl"))
    ap.add_argument("--ledger", default=os.path.join(ROOT, "state", "verified_ledger.jsonl"))
    ap.add_argument("--ledger_secret", default=None, help="HMAC secret (else ULTRABRAIN_LEDGER_SECRET)")
    ap.add_argument("--unsafe", action="store_true",
                    help="DANGEROUS: skip OS-isolation requirement and allow the insecure default ledger secret")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    # Untrusted model output (llm OR diffusion-fim) must run isolated; fail closed unless overridden.
    isolated = (args.proposer in ("llm", "fim")) and not args.unsafe
    if isolated and not ISOLATION_AVAILABLE:
        print("ERROR: OS isolation is unavailable here but is REQUIRED to execute untrusted LLM "
              "output (--proposer llm). Run where the `resource` module works, wrap in a container, "
              "or pass --unsafe to override (DANGEROUS).", file=sys.stderr)
        return 2

    # Trace collection writes trusted beliefs: require a private secret.
    secret = args.ledger_secret or os.environ.get("ULTRABRAIN_LEDGER_SECRET")
    if secret is None and not args.unsafe:
        print("ERROR: trace collection writes trusted beliefs to the ledger. Set --ledger_secret or "
              "ULTRABRAIN_LEDGER_SECRET (or pass --unsafe to use the insecure default).", file=sys.stderr)
        return 2

    tasks = load_jsonl(args.tasks)
    proposer = build_proposer(args)
    ledger = Ledger(args.ledger, secret=secret)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    count_before = ledger.count()

    traces, solved, attempts = [], 0, 0
    t0 = time.time()
    for task in tasks:
        gate = Gate(verifier_for(task, isolated), ledger)
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

    # Checkpointed chain verification: detects truncation of THIS run's appends (not just self-consistency).
    expected_count = count_before + len(traces)
    expected_head = ledger.head()
    chain_ok = ledger.verify_chain(expected_count=expected_count, expected_head=expected_head)

    result = {
        "proposer": args.proposer,
        "isolated_execution": isolated,
        "tasks": len(tasks),
        "solved": solved,
        "attempts": attempts,
        "traces_written": len(traces),
        "out": args.out,
        "wall_seconds": round(wall, 3),
        "seconds_per_solved": round(wall / solved, 4) if solved else None,
        "ledger_count": ledger.count(),
        "ledger_head": expected_head,
        "ledger_chain_ok": chain_ok,
        "note": "every written trace passed the hardened gate -> the SFT set is verified by construction",
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"proposer={args.proposer} isolated={isolated} solved {solved}/{len(tasks)} "
              f"({attempts} attempts, {result['seconds_per_solved']}s/solved)")
        print(f"wrote {len(traces)} verified traces -> {args.out}  "
              f"ledger_ok={chain_ok} (count={result['ledger_count']})")
    return result


def main(argv=None):
    result = run(argv)
    return result if isinstance(result, int) else 0  # propagate fail-closed exit code to the process


if __name__ == "__main__":
    raise SystemExit(main())

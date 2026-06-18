"""ReST-EM / RFT self-improvement driver (the closed loop, thoughts/22, 24).

One round = the bootstrap that needs no frontier teacher:

  1. COLLECT   reuse ``run_verified_search.run`` to sample candidates and keep ONLY gate-certified
               solutions as an SFT set (``data/verified_traces.jsonl``). No evidence -> no example.
  2. TRAIN     unless ``--dry_run``, call ``train_qlora.main`` to QLoRA-fine-tune the proposer on
               those verified traces. This is the expectation-maximization step (ReST-EM): the
               policy is reinforced only on its own verifier-certified successes.
  3. EVAL      run ``eval_code.run`` and record the round's coverage (solve-rate).

Repeat for ``--rounds R`` and print the per-round trajectory of solve-rate.

HONEST NOTE: real training (step 2) needs a CUDA GPU (e.g. an RTX 5080) or a rented spot box —
``train_qlora`` exits non-zero on a non-CUDA host. So the default here is ``--dry_run``, which runs
collect+eval everywhere and validates the training data/config without touching a GPU. With the
mock proposer the policy does not actually change between rounds (it is zero-ML), so the dry-run
trajectory measures loop plumbing, not learning; point ``--proposer llm`` at a served model and drop
``--dry_run`` on a GPU box to measure real round-over-round improvement.

  python self_improve.py                                   # 1 dry round, mock proposer (safe anywhere)
  python self_improve.py --rounds 3 --n 8 --json
  python self_improve.py --rounds 3 --proposer llm \
      --base_url http://localhost:8000/v1 --model Qwen/Qwen3-Coder-14B   # real loop on a CUDA box
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import eval_code  # noqa: E402
import run_verified_search  # noqa: E402
import train_qlora  # noqa: E402


@contextlib.contextmanager
def _muffle(active: bool):
    """Swallow the reused sub-scripts' own stdout prints so our (JSON) output stays clean.

    ``run_verified_search.run``, ``train_qlora.main`` and ``eval_code.run`` each print a human
    summary unconditionally; when we drive them as a library we redirect that chatter to a buffer
    (stderr is left alone so real errors still surface).
    """
    if not active:
        yield
        return
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def _collect(args, round_idx, quiet):
    """Step 1: reuse the verified-search loop to forge a verified SFT set for this round."""
    argv = [
        "--tasks", args.tasks,
        "--proposer", args.proposer,
        "--n", str(args.n),
        "--out", args.traces,
        "--ledger", args.ledger,
        "--seed", str(args.seed + round_idx),  # vary the sampler per round
        "--base_url", args.base_url,
        "--model", args.model,
        "--temperature", str(args.temperature),
    ]
    if args.fim_checkpoint:
        argv += ["--fim_checkpoint", args.fim_checkpoint]
    if args.fim_tokenizer:
        argv += ["--fim_tokenizer", args.fim_tokenizer]
    secret = args.ledger_secret
    if secret is None and os.environ.get("ULTRABRAIN_LEDGER_SECRET") is None and args.proposer == "mock":
        secret = "self-improve-mock-demo"  # mock loop is trusted + throwaway -> stay safe-anywhere
    if secret is not None:
        argv += ["--ledger_secret", secret]
    with _muffle(quiet):
        return run_verified_search.run(argv)


def _train(args, quiet):
    """Step 2: QLoRA-fine-tune on the verified traces. Needs CUDA; returns train_qlora's exit code."""
    argv = ["--data", args.traces, "--model", args.model, "--out", args.checkpoint]
    if args.dry_run:
        argv.append("--dry_run")
    with _muffle(quiet):
        return train_qlora.main(argv)


def _eval(args, quiet):
    """Step 3: score the gate's solve-rate for this round (coverage)."""
    argv = [
        "--tasks", args.tasks,
        "--proposer", args.proposer,
        "--n", str(args.n),
        "--seed", str(args.seed),
        "--base_url", args.base_url,
        "--model", args.model,
        "--temperature", str(args.temperature),
    ]
    if args.fim_checkpoint:
        argv += ["--fim_checkpoint", args.fim_checkpoint]
    if args.fim_tokenizer:
        argv += ["--fim_tokenizer", args.fim_tokenizer]
    with _muffle(quiet):
        return eval_code.run(argv)


def run(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", type=int, default=1, help="number of ReST-EM rounds R")
    ap.add_argument("--tasks", default=os.path.join(ROOT, "tasks", "micro_codebench.jsonl"))
    ap.add_argument("--proposer", choices=["mock", "llm", "fim"], default="mock")
    ap.add_argument("--n", type=int, default=8, help="candidate budget N per task")
    ap.add_argument("--base_url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-Coder-14B")
    ap.add_argument("--fim_checkpoint", default=None,
                    help="diffusion denoiser checkpoint for --proposer fim")
    ap.add_argument("--fim_tokenizer", default=None,
                    help="tokenizer json for --proposer fim")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--traces", default=os.path.join(ROOT, "data", "verified_traces.jsonl"))
    ap.add_argument("--ledger", default=os.path.join(ROOT, "state", "verified_ledger.jsonl"))
    ap.add_argument("--ledger_secret", default=None, help="HMAC secret (else ULTRABRAIN_LEDGER_SECRET)")
    ap.add_argument("--checkpoint", default=os.path.join(ROOT, "checkpoints", "qwen3coder14b-lora"))
    # default IS dry_run; --no_dry_run opts in to real (CUDA) training.
    ap.add_argument("--dry_run", dest="dry_run", action="store_true", default=True,
                    help="validate train data/config without a GPU (default)")
    ap.add_argument("--no_dry_run", dest="dry_run", action="store_false",
                    help="actually run QLoRA training (requires a CUDA GPU)")
    ap.add_argument("--verbose", action="store_true",
                    help="also show the underlying collect/train/eval sub-script output")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    os.makedirs(os.path.dirname(os.path.abspath(args.traces)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.ledger)), exist_ok=True)

    # Keep our own stdout clean (essential for --json): muffle the reused scripts unless --verbose.
    quiet = args.json or not args.verbose

    trajectory = []
    t0 = time.time()
    for r in range(args.rounds):
        collect = _collect(args, r, quiet)
        if isinstance(collect, int):  # run_verified_search failed closed (missing secret / no isolation)
            msg = (f"collect failed (exit {collect}) at round {r}: trace collection needs a private "
                   f"ledger secret (--ledger_secret / ULTRABRAIN_LEDGER_SECRET); --proposer llm also "
                   f"needs OS isolation. Aborting before train/eval.")
            if args.json:
                print(json.dumps({"error": "collect_failed", "exit_code": collect, "round": r,
                                  "hint": msg}, indent=2, sort_keys=True))
            else:
                print("ERROR:", msg, file=sys.stderr)
            return collect
        train_rc = _train(args, quiet)
        metrics = _eval(args, quiet)
        if isinstance(metrics, dict) and metrics.get("error"):  # eval fail-closed (e.g. no isolation)
            if args.json:
                print(json.dumps({"error": "eval_failed", "detail": metrics["error"], "round": r},
                                 indent=2, sort_keys=True))
            else:
                print(f"ERROR: eval failed (round {r}): {metrics['error']} — executing model output "
                      f"needs OS isolation. Aborting.", file=sys.stderr)
            return 2
        trajectory.append({
            "round": r,
            "collected_traces": collect.get("traces_written"),
            "collect_solved": collect.get("solved"),
            "train_rc": train_rc,
            "trained": (not args.dry_run) and train_rc == 0,
            "solve_rate": metrics.get("coverage"),
            "pass@1": metrics.get("pass@1"),
            "cons@k": metrics.get("cons@k"),
            "cost_per_solved": metrics.get("cost_per_solved"),
        })

    wall = time.time() - t0
    first_sr = trajectory[0]["solve_rate"] if trajectory else None
    last_sr = trajectory[-1]["solve_rate"] if trajectory else None
    delta = (last_sr - first_sr) if (first_sr is not None and last_sr is not None) else None

    result = {
        "rounds": args.rounds,
        "proposer": args.proposer,
        "budget_n": args.n,
        "dry_run": args.dry_run,
        "trained_any_round": any(t["trained"] for t in trajectory),
        "trajectory": trajectory,
        "solve_rate_first": first_sr,
        "solve_rate_last": last_sr,
        "solve_rate_delta": round(delta, 6) if delta is not None else None,
        "wall_seconds": round(wall, 3),
        "note": ("dry_run: no weights updated (mock proposer is zero-ML) — this validates the "
                 "collect->train-plan->eval loop. Use --proposer llm --no_dry_run on a CUDA GPU "
                 "to measure real ReST-EM round-over-round improvement."
                 if args.dry_run else
                 "real run: QLoRA trained on verified traces each round (requires CUDA)."),
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"=== self_improve: {args.rounds} round(s), {args.proposer} proposer @ N={args.n}, "
              f"dry_run={args.dry_run} ===")
        print("round  traces  solved  trained  solve_rate  pass@1  cons@k")
        for t in trajectory:
            sr = "n/a" if t["solve_rate"] is None else f"{t['solve_rate']:.2%}"
            p1 = "n/a" if t["pass@1"] is None else f"{t['pass@1']:.2%}"
            ck = "n/a" if t["cons@k"] is None else f"{t['cons@k']:.2%}"
            print(f"{t['round']:>5}  {str(t['collected_traces']):>6}  {str(t['collect_solved']):>6}  "
                  f"{str(t['trained']):>7}  {sr:>10}  {p1:>6}  {ck:>6}")
        if delta is not None:
            print(f"solve-rate trajectory: {first_sr:.2%} -> {last_sr:.2%} (delta {delta:+.2%})")
        print("note:", result["note"])
    return result


def main(argv=None):
    result = run(argv)
    return result if isinstance(result, int) else 0  # propagate collect-failure exit code


if __name__ == "__main__":
    raise SystemExit(main())

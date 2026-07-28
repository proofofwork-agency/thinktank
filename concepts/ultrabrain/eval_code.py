"""Run the verifier gate over a task set and report verified-search eval metrics.

Mirrors ``eval.py`` (argparse, ``--json``, a printed human summary plus a verdict) and reuses the
EXISTING verifier API — the gate is the only thing trusted, exactly as in ``run_verified_search.py``.
Capability here is *verified search*, not parameters: at budget N a proposer samples N candidates
per task and the hardened gate (CodeTestVerifier for code, airtight CASVerifier for cas) decides
which, if any, are certified (thoughts/14, 22, 24).

Eval MEASURES the gate; it never writes trusted beliefs (that is ``run_verified_search.py``'s job),
so there is deliberately no ledger here — measurement must not pollute the trusted store.

Metrics (all computed from gate Outcomes, never from a self-report):

  pass@1            fraction of tasks whose FIRST candidate is certified by the gate.
  coverage / pass@k fraction of tasks where ANY of the N candidates is certified ("solved").
  cons@k            self-consistency: majority-vote the N candidates by normalized text, then take
                    that plurality candidate's gate verdict; fraction where it is certified.
  cost_per_solved   wall-clock seconds / solved (coverage count). None if nothing solved.
  selector_recall   of SOLVABLE tasks (coverage>0), the fraction where the consensus selector lands
                    on a certified candidate. Non-trivial: <1 when the vote picks a wrong candidate
                    though a correct one exists — so a selector regression shows up honestly.

  python eval_code.py                                            # mock proposer, micro_codebench
  python eval_code.py --proposer mock --n 8 --json
  python eval_code.py --proposer llm \
      --base_url http://localhost:8000/v1 --model Qwen/Qwen3-Coder-14B   # local Qwen3-Coder-14B
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from ultrabrain.propose import DiffusionFIMProposer, NoisyProposer  # noqa: E402
from ultrabrain.propose.llm import LLMProposer  # noqa: E402
from ultrabrain.verify import (  # noqa: E402
    CASVerifier, CodeTestVerifier, Gate, ISOLATION_AVAILABLE, StructuredCodeVerifier, harden,
    run_tests_isolated,
)


def load_jsonl(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def build_proposer(args):
    """Same wiring as run_verified_search.py: mock=NoisyProposer, llm=LLMProposer, fim=DiffusionFIMProposer."""
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
    """Airtight CAS for cas; parent-owned-oracle judge_v1 for code (the sound certifier, incl. the
    assembled FIM program). JUDGE-ONLY: a code task WITHOUT a judge spec ABSTAINS rather than certify
    via the forgeable assert runner — which would report false metrics (Codex final review). All
    shipped tasks carry judge specs; ``isolated`` no longer applies (the judge isolates its worker)."""
    if task.get("kind") == "cas":
        return CASVerifier()
    return StructuredCodeVerifier()


def _normalize(candidate: str) -> str:
    """Collapse a candidate to a canonical key for consensus voting (whitespace-insensitive)."""
    lines = [ln.rstrip() for ln in (candidate or "").strip().splitlines()]
    return "\n".join(ln for ln in lines if ln.strip())


def _plurality(candidates):
    """The most common candidate by normalized text; ties broken by first appearance."""
    if not candidates:
        return None, 0
    counts = Counter(_normalize(c) for c in candidates)
    best_key, votes = counts.most_common(1)[0]
    for c in candidates:
        if _normalize(c) == best_key:
            return c, votes
    return candidates[0], votes


def evaluate(tasks, proposer, n, isolated=False):
    """Sample n candidates/task, judge each ONCE, and fold per-task results into the metrics dict."""
    per_task = []
    solved = pass1 = cons_certified = attempts = 0
    t0 = time.time()

    for task in tasks:
        gate = Gate(verifier_for(task, isolated))  # no ledger: measure the gate, never write beliefs
        candidates = list(proposer.propose(task, n))
        attempts += len(candidates)

        certified_flags = [gate.judge(task, cand).certified for cand in candidates]
        covered = any(certified_flags)
        first_ok = bool(certified_flags and certified_flags[0])

        # Consensus: plurality by normalized text; REUSE the loop's verdicts (no second judge).
        cert_by_key = {}
        for cand, ok in zip(candidates, certified_flags):
            cert_by_key.setdefault(_normalize(cand), ok)
        plural_cand, votes = _plurality(candidates)
        cons_ok = bool(plural_cand is not None and cert_by_key.get(_normalize(plural_cand), False))

        solved += int(covered)
        pass1 += int(first_ok)
        cons_certified += int(cons_ok)
        per_task.append({
            "task_id": task.get("id", "?"),
            "kind": task.get("kind", "code"),
            "candidates": len(candidates),
            "covered": covered,
            "pass1": first_ok,
            "consensus_certified": cons_ok,
            "consensus_votes": votes,
        })

    wall = time.time() - t0
    n_tasks = len(tasks)
    # Of solvable tasks (coverage>0), how often does the consensus selector land on a certified one?
    selector_recall = (cons_certified / solved) if solved else None

    return {
        "tasks": n_tasks,
        "budget_n": n,
        "attempts": attempts,
        "solved": solved,
        "pass@1": round(pass1 / n_tasks, 6) if n_tasks else 0.0,
        "coverage": round(solved / n_tasks, 6) if n_tasks else 0.0,
        "pass@k": round(solved / n_tasks, 6) if n_tasks else 0.0,
        "cons@k": round(cons_certified / n_tasks, 6) if n_tasks else 0.0,
        "cost_per_solved": round(wall / solved, 6) if solved else None,
        "selector_recall": round(selector_recall, 6) if selector_recall is not None else None,
        "wall_seconds": round(wall, 3),
        "per_task": per_task,
    }


def verdict_for(metrics) -> str:
    cov = metrics["coverage"]
    p1 = metrics["pass@1"]
    if metrics["solved"] == 0:
        return ("Gate certified nothing at this budget — verified search found no certificate; "
                "raise --n or improve the proposer (the gate stayed sound: no false certification).")
    lift = cov - p1
    return (f"Verified search lifts solve-rate from pass@1={p1:.2%} to coverage={cov:.2%} "
            f"(+{lift:.2%} from sampling N and certifying any); consensus selector_recall="
            f"{metrics['selector_recall']}.")


def run(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", default=os.path.join(ROOT, "tasks", "micro_codebench.jsonl"))
    ap.add_argument("--proposer", choices=["mock", "llm", "fim"], default="mock")
    ap.add_argument("--n", type=int, default=8, help="candidate budget N sampled per task")
    ap.add_argument("--base_url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-Coder-14B")
    ap.add_argument("--fim_checkpoint", default=None,
                    help="diffusion denoiser checkpoint for --proposer fim (default: checkpoints/diffusion.pt)")
    ap.add_argument("--fim_tokenizer", default=None,
                    help="tokenizer json for --proposer fim (default: checkpoints/tokenizer.json)")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--unsafe", action="store_true",
                    help="DANGEROUS: execute untrusted --proposer llm/fim output for DIAGNOSTICS. "
                         "rlimits are NOT a host jail; run only in a throwaway environment. Metrics "
                         "are diagnostics only, not trustworthy.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    # HOST CONTAINMENT (Codex final review): --proposer llm/fim EXECUTES untrusted model code. rlimits
    # bound CPU/memory but do NOT contain the filesystem/network — a candidate can write host files or
    # open sockets (e.g. via a stdlib reflection gadget that execs with full builtins). So this does
    # NOT run by default: fail closed unless --unsafe (explicit throwaway diagnostics) or a real host
    # jail is provided out of band. Metrics from --unsafe are diagnostics only, never trustworthy.
    untrusted = args.proposer in ("llm", "fim")
    if untrusted and not args.unsafe:
        print("ERROR: --proposer llm/fim EXECUTES untrusted model code. rlimits are not a host jail "
              "(a candidate can still write files / open sockets), so this does not run by default. "
              "Pass --unsafe to execute for DIAGNOSTICS in a throwaway environment, or run under a real "
              "host jail (container / separate uid / seccomp / no network).", file=sys.stderr)
        return {"error": "untrusted_execution_requires_unsafe_or_host_jail"}

    tasks = load_jsonl(args.tasks)
    proposer = build_proposer(args)
    metrics = evaluate(tasks, proposer, args.n, isolated=untrusted)
    metrics["proposer"] = args.proposer
    metrics["tasks_path"] = args.tasks
    metrics["verdict"] = verdict_for(metrics)
    # Past the gate, an untrusted proposer only ran under --unsafe: label the metrics diagnostics-only
    # and qualify the verdict so a reader cannot mistake them for a trustworthy result (Codex).
    metrics["trusted"] = not untrusted
    if untrusted:
        metrics["diagnostics_only"] = True
        metrics["verdict"] = ("DIAGNOSTICS ONLY — untrusted proposer under --unsafe (rlimits are not a "
                              "host jail; these certificates are not trustworthy). " + metrics["verdict"])

    if args.json:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    else:
        print(f"=== eval_code: {args.proposer} proposer @ N={args.n} "
              f"on {os.path.basename(args.tasks)} ({metrics['tasks']} tasks) ===")
        print(f"pass@1          = {metrics['pass@1']:.2%}")
        print(f"coverage/pass@k = {metrics['coverage']:.2%}  ({metrics['solved']}/{metrics['tasks']} solved)")
        print(f"cons@k          = {metrics['cons@k']:.2%}")
        cps = metrics["cost_per_solved"]
        print(f"cost_per_solved = {cps if cps is None else f'{cps:.4f}s'}  "
              f"(wall={metrics['wall_seconds']}s, {metrics['attempts']} attempts)")
        print(f"selector_recall = {metrics['selector_recall']}")
        print("verdict:", metrics["verdict"])
    return metrics


def main(argv=None):
    result = run(argv)
    if isinstance(result, dict) and result.get("error"):
        return 2  # propagate isolation-unavailable / error to the process
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

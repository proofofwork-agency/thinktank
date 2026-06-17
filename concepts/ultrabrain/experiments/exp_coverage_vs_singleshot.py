"""Slice 1 — the proof experiment. Zero ML.

Proves (or falsifies) the core claim that a hard verifier turns a cheap, often-wrong proposer's
coverage into solved tasks, and that hardening is load-bearing — before any model is trained.

  H1  verified sampling > single-shot   coverage(N) rises with N and exceeds pass@1
  H2  hardening is load-bearing         weak tests falsely certify wrong code; hardened ~0
  V   verify << solve                   CAS: diff+simplify (verify) is cheaper than integrate (solve)

If H2 fails (hardening does NOT reduce false-certification), the thesis is falsified here, cheaply.

  python experiments/exp_coverage_vs_singleshot.py
  python experiments/exp_coverage_vs_singleshot.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

import sympy as sp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ultrabrain.propose import NoisyProposer  # noqa: E402
from ultrabrain.verify import (  # noqa: E402
    CASVerifier,
    CodeTestVerifier,
    Gate,
    Ledger,
    CERTIFIED,
    harden,
    weak_suite,
)


def load_jsonl(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def h1_coverage_vs_single_shot(code_tasks, n_list, seeds):
    """coverage(N) = fraction of tasks where ANY of N candidates passes the HARDENED gate."""
    cov = {n: [] for n in n_list}
    pass1, blind = [], []
    for seed in seeds:
        proposer = NoisyProposer(seed=seed)
        for task in code_tasks:
            hardened = CodeTestVerifier(harden(task))
            cands = proposer.propose(task, max(n_list))
            ok = [hardened.verify(task, c).certified for c in cands]
            pass1.append(1.0 if ok[0] else 0.0)
            blind.append(1.0 if ok[0] else 0.0)  # no-verifier control accepts cand[0] regardless
            for n in n_list:
                cov[n].append(1.0 if any(ok[:n]) else 0.0)
    return {
        "coverage_by_n": {n: round(statistics.mean(cov[n]), 4) for n in n_list},
        "pass_at_1": round(statistics.mean(pass1), 4),
        "no_verifier_true_accuracy": round(statistics.mean(blind), 4),
    }


def h2_weak_vs_hardened(code_tasks):
    """Ground truth = the design labels (gold=correct, distractor=wrong, by construction)."""
    weak_fc = hard_fc = hard_fr = n_gold = n_distractor = 0
    for task in code_tasks:
        weak = CodeTestVerifier(weak_suite(task))
        hard = CodeTestVerifier(harden(task))
        n_gold += 1
        if not hard.verify(task, task["gold"]).certified:
            hard_fr += 1  # false reject of a known-correct gold
        for d in task.get("distractors", []):
            n_distractor += 1
            if weak.verify(task, d).certified:
                weak_fc += 1  # weak tests certified a known-wrong solution
            if hard.verify(task, d).certified:
                hard_fc += 1  # hardened certified a known-wrong solution
    return {
        "n_gold": n_gold,
        "n_distractor": n_distractor,
        "weak_false_certifications": weak_fc,
        "hardened_false_certifications": hard_fc,
        "hardened_false_rejections": hard_fr,
        "weak_false_cert_rate": round(weak_fc / n_distractor, 4) if n_distractor else 0.0,
        "hardened_false_cert_rate": round(hard_fc / n_distractor, 4) if n_distractor else 0.0,
    }


def cas_soundness(cas_tasks):
    v = CASVerifier()
    gold_cert = false_cert = abstain = n_gold = n_distractor = 0
    for task in cas_tasks:
        n_gold += 1
        if v.verify(task, task["gold"]).certified:
            gold_cert += 1
        for d in task.get("distractors", []):
            n_distractor += 1
            status = v.verify(task, d).status
            if status == CERTIFIED:
                false_cert += 1
            elif status == "abstain":
                abstain += 1
    return {
        "n_gold": n_gold, "gold_certified": gold_cert,
        "n_distractor": n_distractor, "false_certifications": false_cert, "abstentions": abstain,
    }


def verify_vs_solve(cas_tasks, repeats):
    """SOLVE = sympy.integrate (produce the answer). VERIFY = diff+simplify (check it). Ratio."""
    x = sp.Symbol("x")
    solve_t = verify_t = 0.0
    n = 0
    for task in cas_tasks:
        if task.get("op") != "antiderivative":
            continue
        f = sp.sympify(task["integrand"], locals={"x": x})
        big_f = sp.sympify(task["gold"], locals={"x": x})
        for _ in range(repeats):
            t0 = time.perf_counter(); sp.integrate(f, x); solve_t += time.perf_counter() - t0
            t0 = time.perf_counter(); sp.simplify(sp.diff(big_f, x) - f); verify_t += time.perf_counter() - t0
            n += 1
    return {
        "samples": n,
        "solve_ms": round(1000 * solve_t / n, 3) if n else 0.0,
        "verify_ms": round(1000 * verify_t / n, 3) if n else 0.0,
        "solve_over_verify": round(solve_t / verify_t, 2) if verify_t else 0.0,
    }


def cost_per_solved(code_tasks, n, seed):
    """Wall-clock seconds of (propose+verify) per task solved at budget N, through the gate."""
    import tempfile
    proposer = NoisyProposer(seed=seed)
    ledger = Ledger(os.path.join(tempfile.mkdtemp(), "slice1_ledger.jsonl"), secret="slice1-demo")
    solved = 0
    t0 = time.time()
    for task in code_tasks:
        gate = Gate(CodeTestVerifier(harden(task)), ledger)
        for cand in proposer.propose(task, n):
            if gate.judge(task, cand).certified:
                solved += 1
                break
    wall = time.time() - t0
    return {
        "budget_n": n, "tasks": len(code_tasks), "solved": solved,
        "wall_seconds": round(wall, 3),
        "seconds_per_solved": round(wall / solved, 4) if solved else None,
        "ledger_chain_ok": ledger.verify_chain(),
    }


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default=os.path.join(ROOT, "tasks", "micro_codebench.jsonl"))
    ap.add_argument("--cas", default=os.path.join(ROOT, "tasks", "micro_cas.jsonl"))
    ap.add_argument("--n", default="1,2,4,8,16")
    ap.add_argument("--seeds", type=int, default=12)
    ap.add_argument("--repeats", type=int, default=20, help="verify<<solve timing repeats")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    n_list = [int(x) for x in args.n.split(",")]
    seeds = list(range(args.seeds))
    code_tasks = load_jsonl(args.code)
    cas_tasks = load_jsonl(args.cas)

    h1 = h1_coverage_vs_single_shot(code_tasks, n_list, seeds)
    h2 = h2_weak_vs_hardened(code_tasks)
    cas = cas_soundness(cas_tasks)
    vvs = verify_vs_solve(cas_tasks, args.repeats)
    cost = cost_per_solved(code_tasks, max(n_list), seed=0)

    h1_ok = h1["coverage_by_n"][max(n_list)] > h1["pass_at_1"] + 0.1
    h2_ok = (h2["weak_false_certifications"] > 0
             and h2["hardened_false_certifications"] == 0
             and h2["hardened_false_rejections"] == 0)
    cas_ok = cas["false_certifications"] == 0 and cas["gold_certified"] == cas["n_gold"]
    vvs_ok = vvs["solve_over_verify"] > 1.5
    supported = h1_ok and h2_ok and cas_ok

    verdict = (
        "THESIS SUPPORTED (zero ML): a hard verifier converts a weak proposer's coverage into "
        "solved tasks, and hardening (hidden + reference-differential property tests) eliminates "
        "the weak-test false-certifications on the curated distractor pool. Proceed to Slice 2 "
        "(plug in Qwen3-Coder-14B behind this gate)."
        if supported else
        "THESIS NOT SUPPORTED at this budget — inspect which gate failed before any ML spend. "
        + ("H2 FALSIFIED: hardening did not reduce false-certification. " if not h2_ok else "")
        + ("H1 weak: coverage(N) did not exceed pass@1. " if not h1_ok else "")
        + ("CAS not sound: a false certification or false reject occurred. " if not cas_ok else "")
    )

    result = {
        "h1_coverage_vs_single_shot": h1,
        "h2_weak_vs_hardened": h2,
        "cas_soundness": cas,
        "verify_vs_solve": vvs,
        "cost_per_solved": cost,
        "gates": {"H1": h1_ok, "H2": h2_ok, "CAS_sound": cas_ok, "verify_much_less_solve": vvs_ok},
        "verdict": verdict,
        "notes": [
            "H2 ground truth = design labels (gold correct, distractor wrong); not circular.",
            "Finite tests are incomplete (an overfit candidate could pass enumerated cases) — mitigated "
            "by reference-differential property tests (compare to a trusted oracle over many inputs). "
            "The claim is scoped to the curated distractor pool, not arbitrary adversarial code.",
            "Residual hardened false-certs vs an even-stronger oracle are unmeasured here (the ~4% AlphaCode floor).",
            "no_verifier_true_accuracy == pass_at_1 here by construction; it is the control the verified search beats.",
        ],
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("=== Slice 1: verifier gate / zero-ML falsification ===")
        print(f"H1 coverage by N: {h1['coverage_by_n']}  pass@1={h1['pass_at_1']}")
        print(f"   -> verified sampling lifts {h1['pass_at_1']:.0%} (1 shot) to "
              f"{h1['coverage_by_n'][max(n_list)]:.0%} (N={max(n_list)})   [H1 {'OK' if h1_ok else 'WEAK'}]")
        print(f"H2 weak false-certs={h2['weak_false_certifications']}/{h2['n_distractor']} "
              f"(rate {h2['weak_false_cert_rate']:.0%})  "
              f"hardened false-certs={h2['hardened_false_certifications']}  "
              f"hardened false-rejects={h2['hardened_false_rejections']}   [H2 {'OK' if h2_ok else 'FALSIFIED'}]")
        print(f"CAS gold_certified={cas['gold_certified']}/{cas['n_gold']} "
              f"false_certs={cas['false_certifications']} abstains={cas['abstentions']}   "
              f"[{'sound' if cas_ok else 'UNSOUND'}]")
        print(f"verify<<solve: solve={vvs['solve_ms']}ms verify={vvs['verify_ms']}ms "
              f"ratio={vvs['solve_over_verify']}x   [{'OK' if vvs_ok else 'weak'}]")
        print(f"cost: {cost['solved']}/{cost['tasks']} solved @N={cost['budget_n']}, "
              f"{cost['seconds_per_solved']}s/solved, ledger_ok={cost['ledger_chain_ok']}")
        print("VERDICT:", verdict)
    return result


def main(argv=None):
    run(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

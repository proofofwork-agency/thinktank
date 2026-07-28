"""S0 — the symbolic task forge. Zero ML, zero network, zero untrusted execution.

The task list is not an input; it is the output of a verifier run BACKWARDS. Pick an
antiderivative ``F``, differentiate it to get the integrand, and keep ``F`` as a gold the parent
held BEFORE any candidate existed — so no untrusted computation ever contributes to the label.

Why this path and not the code path: ``CASVerifier`` never executes the candidate. It validates
against an AST whitelist (``verifiers.py`` ``_ALLOWED_NODES`` — no Attribute, no Subscript, no
strings) and only then sympifies with restricted locals, deciding wholly in the parent. None of
the ``judge_v1`` worker / signed-channel forgeries apply here (see docs/BECOMING_AN_LLM.md §3).

  F1  the forge is generative          mint N tasks with no human authoring and no corpus
  F2  minted golds are certifiable     the REAL, unmodified CASVerifier certifies them
  F3  minted distractors are hard      auto-generated near-misses do NOT false-certify

If F3 fails, the forge is producing golds indistinguishable from wrong answers and the corpus it
mints is worthless — the cheap falsification for this slice.

  python experiments/exp_task_forge.py
  python experiments/exp_task_forge.py --n 1000 --out tasks/forged_cas.jsonl
  python experiments/exp_task_forge.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

import sympy as sp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultrabrain.verify.verifiers import CASVerifier, CERTIFIED  # noqa: E402

X = sp.Symbol("x")


def _sample_F(rng: random.Random):
    """A small grammar of antiderivatives. Every branch has an elementary derivative."""
    kind = rng.choice(["poly", "trig", "exp", "log", "prod", "chain"])
    a, n = rng.randint(1, 6), rng.randint(2, 5)
    if kind == "poly":
        return sum(rng.randint(1, 5) * X**k for k in range(1, n + 1))
    if kind == "trig":
        return a * rng.choice([sp.sin(X), sp.cos(X), sp.tan(X)])
    if kind == "exp":
        return a * sp.exp(rng.randint(1, 3) * X)
    if kind == "log":
        return a * sp.log(X)
    if kind == "prod":
        return a * X**n * sp.exp(X)
    return a * sp.sin(rng.randint(2, 4) * X)              # chain rule


def _perturb(F, rng: random.Random):
    """An auto-distractor: a plausible near-miss (wrong constant factor, wrong power, off by x)."""
    return rng.choice([F * rng.randint(2, 4), F + X, sp.diff(F, X), F / 2])


def mint(n: int, seed: int = 7, n_distractors: int = 3) -> list:
    """Mint ``n`` antiderivative tasks in the shipped micro_cas.jsonl schema."""
    rng = random.Random(seed)
    out, seen = [], set()
    while len(out) < n:
        F = sp.simplify(_sample_F(rng))
        integrand = sp.simplify(sp.diff(F, X))
        if integrand.is_number or str(F) in seen:        # degenerate / duplicate
            continue
        seen.add(str(F))
        out.append({
            "id": f"forge_cas_{len(out)}",
            "kind": "cas",
            "op": "antiderivative",
            "var": "x",
            "prompt": f"Antiderivative of {integrand}.",
            "integrand": str(integrand),
            "gold": str(F),
            "distractors": [str(sp.simplify(_perturb(F, rng))) for _ in range(n_distractors)],
        })
    return out


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="tasks to mint")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None, help="write the minted tasks as JSONL")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    # A dead verifier must never masquerade as a weak proposer / zero-yield forge.
    CASVerifier.require_available()

    t0 = time.time()
    tasks = mint(args.n, seed=args.seed)
    mint_s = time.time() - t0

    # F2 + F3 against the REAL verifier — no mock, no stub.
    v = CASVerifier()
    t1 = time.time()
    golds_ok = distractors = false_certs = parse_errors = 0
    for t in tasks:
        if v.verify(t, t["gold"]).status == CERTIFIED:
            golds_ok += 1
        for d in t["distractors"]:
            if d == t["gold"]:
                continue                                  # perturbation collapsed back to gold
            distractors += 1
            try:
                if v.verify(t, d).status == CERTIFIED:
                    false_certs += 1
            except Exception:
                parse_errors += 1
    verify_s = time.time() - t1

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as fh:
            for t in tasks:
                fh.write(json.dumps(t) + "\n")

    result = {
        "minted": len(tasks),
        "hand_written": 0,
        "untrusted_execution": False,          # the CAS path never runs the candidate
        "golds_certified": golds_ok,
        "distractors_tested": distractors,
        "false_certifications": false_certs,
        "parse_errors": parse_errors,
        "mint_seconds": round(mint_s, 2),
        "verify_seconds": round(verify_s, 2),
        "tasks_per_second": round(len(tasks) / mint_s, 1) if mint_s else None,
        "out": args.out,
        "F1_generative": len(tasks) == args.n,
        "F2_golds_certify": golds_ok == len(tasks),
        "F3_distractors_rejected": false_certs == 0,
    }
    result["verdict"] = (
        "FORGE SOUND" if all((result["F1_generative"], result["F2_golds_certify"],
                              result["F3_distractors_rejected"]))
        else "FORGE FALSIFIED"
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"minted            : {result['minted']} tasks, 0 hand-written, 0 network, "
              f"0 untrusted execution")
        print(f"golds certified   : {golds_ok}/{len(tasks)}")
        print(f"distractors tested: {distractors}   FALSE CERTIFICATIONS: {false_certs}   "
              f"parse-errors: {parse_errors}")
        print(f"rate              : {result['tasks_per_second']}/s mint, "
              f"{round(mint_s + verify_s, 1)}s total")
        if tasks:
            print(f"sample            : {tasks[0]['prompt']!r} -> gold {tasks[0]['gold']!r}")
        print(f"\nVERDICT: {result['verdict']}")
    return 0 if result["verdict"] == "FORGE SOUND" else 1


if __name__ == "__main__":
    raise SystemExit(run())

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
# Measured, not estimated (120k draws + per-family enumeration): poly 3900 + the 14 other
# families 624 = 4524 PARAMETER COMBINATIONS, but only 4516 under EXPRESSION IDENTITY — eight
# `ratio` forms are algebraic duplicates (x/(2*x+1) == 2*x/(4*x+2); Codex, pre-baseline). Quote
# the deduplicated number: a generator's reach is the objects that survive dedupe, not the tuples
# it enumerates. Before the 2026-07-28 widening this was 3984 with only 84 non-polynomial forms,
# so conceptual coverage grew 7.4x while the polynomial reach is unchanged.
_MEASURED_FORGE_SPACE = 4_516
_MEASURED_NONPOLY_SPACE = 624


# Widened 2026-07-28. The original six families reached 3,984 forms of which 3,900 were
# polynomial: only 84 conceptually distinct tasks, exhausting at n~84 so every task beyond that
# was more power-rule practice (ROADMAP.md S0b). The families below add CONCEPTS, not coefficients
# — inverse-trig, rational, fractional powers, by-parts, hyperbolic, log-of-linear, mixed sums.
#
# Every branch must satisfy Codex's C4 conditions: closed, finite, differentiable, with the
# DERIVATIVE landing inside verifiers.py `_ALLOWED_FUNCS` (so the gold is checkable) and no
# nonfinite atom or identically-zero derivative. floor/ceiling/gamma/Abs are excluded on purpose:
# they differentiate to Derivative/polygamma/sign forms outside the verifier grammar and ABSTAIN.
_FORGE_FAMILIES = (
    "poly", "trig", "exp", "log", "prod", "chain",          # original six
    "loglin", "arctan", "arcsin", "sqrtpow", "byparts",     # added
    "hyper", "trigpow", "mixed", "ratio",
)


def _sample_F(rng: random.Random):
    """The grammar of antiderivatives. Every branch has an elementary, in-grammar derivative."""
    kind = rng.choice(list(_FORGE_FAMILIES))
    a, n = rng.randint(1, 6), rng.randint(2, 5)
    m, c = rng.randint(2, 4), rng.randint(1, 4)
    if kind == "poly":
        return sum(rng.randint(1, 5) * X**k for k in range(1, n + 1)), kind
    if kind == "trig":
        return a * rng.choice([sp.sin(X), sp.cos(X), sp.tan(X)]), kind
    if kind == "exp":
        return a * sp.exp(rng.randint(1, 3) * X), kind
    if kind == "log":
        return a * sp.log(X), kind
    if kind == "prod":
        return a * X**n * sp.exp(X), kind
    if kind == "chain":
        return a * sp.sin(rng.randint(2, 4) * X), kind
    # --- added families: each introduces a distinct integration concept ---
    if kind == "loglin":                                   # -> a*m/(m*x + c)
        return a * sp.log(m * X + c), kind
    if kind == "arctan":                                   # -> a/(x**2 + 1)
        return a * sp.atan(rng.choice([X, m * X])), kind
    if kind == "arcsin":                                   # -> a/sqrt(1 - x**2)
        return a * sp.asin(X), kind
    if kind == "sqrtpow":                                  # -> fractional power
        return a * X**sp.Rational(rng.choice([3, 5, 7]), 2), kind
    if kind == "byparts":                                  # -> x*cos(x) | log(x) | x*exp(x)
        return a * rng.choice([
            X * sp.sin(X) + sp.cos(X),
            X * sp.log(X) - X,
            (X - 1) * sp.exp(X),
        ]), kind
    if kind == "hyper":                                    # -> a*cosh(x) | a*sinh(x)
        return a * rng.choice([sp.sinh(X), sp.cosh(X)]), kind
    if kind == "trigpow":                                  # -> sec**2 / sin*cos
        return a * rng.choice([sp.tan(m * X), sp.sin(X) ** 2, sp.cos(X) ** 2]), kind
    if kind == "mixed":                                    # linearity across two families
        return (rng.randint(1, 4) * X**rng.randint(2, 4)
                + a * rng.choice([sp.sin(X), sp.cos(X), sp.exp(X), sp.log(X)])), kind
    return a * X / (m * X + c), kind                       # ratio -> a*c/(m*x + c)**2


def _perturb(F, rng: random.Random):
    """A verifier-falsification near-miss — NOT a model-error simulator or diversity target.

    This deliberately tiny pool serves Slice 1: wrong answers should not certify. It is synthetic
    and does not represent the procedural mistakes a real model makes, so adding more algebraic
    perturbations would create flattering but fake training-signal diversity.
    """
    # Keep the original RNG consumption/order stable while attaching trusted forge provenance.
    return rng.choice([
        (F * rng.randint(2, 4), "scalar_multiple"),
        (F + X, "plus_x"),
        (sp.diff(F, X), "derivative"),
        (F / 2, "scalar_multiple"),
    ])


def mint(n: int, seed: int = 7, n_distractors: int = 3) -> list:
    """Mint ``n`` antiderivative tasks in the shipped micro_cas.jsonl schema."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n > _MEASURED_FORGE_SPACE:
        raise ValueError(
            "forge space exhausted after 0 attempts: 0 distinct minted; "
            f"requested {n}, measured grammar maximum is {_MEASURED_FORGE_SPACE}"
        )
    rng = random.Random(seed)
    out, seen = [], set()
    attempts = 0
    max_attempts = max(10_000, n * 100)
    while len(out) < n:
        attempts += 1
        if attempts > max_attempts:
            raise RuntimeError(
                f"forge space exhausted after {max_attempts} attempts: "
                f"{len(out)} distinct minted (requested {n})"
            )
        sampled, family = _sample_F(rng)
        F = sp.simplify(sampled)
        integrand = sp.simplify(sp.diff(F, X))
        if integrand.is_number or str(F) in seen:        # degenerate / duplicate
            continue
        seen.add(str(F))
        perturbed = [_perturb(F, rng) for _ in range(n_distractors)]
        out.append({
            "id": f"forge_cas_{len(out)}",
            "kind": "cas",
            "task_family": family,
            "op": "antiderivative",
            "var": "x",
            "prompt": f"Antiderivative of {integrand}.",
            "integrand": str(integrand),
            "gold": str(F),
            "distractors": [str(sp.simplify(expr)) for expr, _ in perturbed],
            "distractor_archetypes": [archetype for _, archetype in perturbed],
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
    try:
        tasks = mint(args.n, seed=args.seed)
    except (ValueError, RuntimeError) as exc:
        if args.json:
            print(json.dumps({"error": "forge_space_exhausted", "detail": str(exc)}, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2
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

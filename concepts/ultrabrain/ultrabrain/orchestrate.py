"""DECOMPOSE-THEN-VERIFY: solve a composite task one verified subproblem at a time.

The SciCode finding (thoughts/22): a frontier model solves a *whole* multi-step scientific
program <5% of the time, but solves the individual sub-steps 26-35% of the time. The whole is
unreachable head-on; the parts are reachable. So you MUST decompose — solve, then **verify**, each
subproblem, and compose the verified parts into the final artifact.

A composite task is::

    {"id": ..., "subproblems": [sub_task, sub_task, ...]}

where each ``sub_task`` is an ordinary code task (``id, gold, weak_tests, hidden_tests,
property_tests, ...`` — the same schema ``run_verified_search.py`` consumes). For each subproblem,
in order, the orchestrator runs the hardened accept gate::

    Gate(CodeTestVerifier(harden(sub)))

against ``n`` candidates from a proposer (any object with ``.propose(task, n) -> list[str]``;
default :class:`MockProposer`, which returns the subproblem gold). A subproblem is *certified* iff
some candidate passes the hardened suite (weak + hidden + property tests). The verified subproblem
solutions are concatenated into one final artifact, and the composite is ``overall_solved`` iff
**every** subproblem certified.

SOUNDNESS NOTE — this module is an orchestrator, NOT a verifier. It never invents a verdict: it
only *reads* ``Outcome.certified`` off the :class:`~ultrabrain.verify.Gate`, whose decision is made
by :class:`~ultrabrain.verify.CodeTestVerifier` (a sound hardened-execution decision procedure). It
performs no ``eval``/``exec`` of candidate code itself — all execution is inside the verifier
sandbox. ``overall_solved`` is a pure conjunction of gate certificates; a single uncertified
subproblem makes the composite uncertified (no partial credit is ever reported as solved).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

try:  # normal package import (``import ultrabrain.orchestrate``)
    from .verify import CodeTestVerifier, Gate, Ledger, Outcome, harden
except ImportError:  # run directly as a script (``python ultrabrain/orchestrate.py``), mirror eval.py
    import os as _os
    import sys as _sys

    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ultrabrain.verify import CodeTestVerifier, Gate, Ledger, Outcome, harden


class MockProposer:
    """Default proposer: emit the subproblem's reference solution (``task['gold']``).

    Mirrors ``ultrabrain.propose.GoldProposer`` — a zero-ML control that isolates the
    *orchestration + verifier* path, exactly the way Slice 1 isolates the verifier's value. Swap in
    a real proposer (LLMProposer, the diffusion-FIM head) behind the same ``.propose`` protocol.
    """

    def propose(self, task: dict, n: int) -> list:
        return [task["gold"]] * n


class WrongProposer:
    """Test/diagnostic proposer: emit a fixed, deliberately-wrong candidate for every task.

    Used to exercise the rejection path — the hardened gate must NOT certify it, so the enclosing
    composite must report ``overall_solved == False``. A first distractor is used when present,
    otherwise a trivial stub that fails the suite.
    """

    def __init__(self, candidate: Optional[str] = None):
        self.candidate = candidate

    def propose(self, task: dict, n: int) -> list:
        if self.candidate is not None:
            cand = self.candidate
        else:
            distractors = list(task.get("distractors", []))
            cand = distractors[0] if distractors else "def _wrong():\n    return None\n"
        return [cand] * n


@dataclass
class SubResult:
    """The verified outcome for one subproblem of a composite."""

    id: str
    certified: bool
    detail: str
    candidate: Optional[str] = None  # the certified solution (None if the subproblem failed)
    seconds: float = 0.0
    attempts: int = 0


@dataclass
class CompositeResult:
    """The result of a DECOMPOSE-THEN-VERIFY run over a composite task."""

    id: str
    subproblems: list = field(default_factory=list)   # list[SubResult], in solve order
    overall_solved: bool = False                       # whole-artifact VERIFIED (composite tests passed)
    subproblems_solved: bool = False                   # every subproblem independently certified
    solution: str = ""                                 # composed artifact (verified parts)
    seconds: float = 0.0
    composition_verified: Optional[bool] = None        # whole-artifact re-check: True/False, None if no composite tests
    composition_detail: str = ""

    @property
    def n_certified(self) -> int:
        return sum(1 for s in self.subproblems if s.certified)

    @property
    def n_subproblems(self) -> int:
        return len(self.subproblems)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "overall_solved": self.overall_solved,
            "subproblems_solved": self.subproblems_solved,
            "composition_verified": self.composition_verified,
            "composition_detail": self.composition_detail,
            "n_certified": self.n_certified,
            "n_subproblems": self.n_subproblems,
            "seconds": round(self.seconds, 6),
            "subproblems": [
                {
                    "id": s.id,
                    "certified": s.certified,
                    "detail": s.detail,
                    "seconds": round(s.seconds, 6),
                    "attempts": s.attempts,
                }
                for s in self.subproblems
            ],
            "solution": self.solution,
        }


def _verifier_for(sub: dict):
    """The hardened accept gate's verifier for one subproblem (weak + hidden + property tests)."""
    return CodeTestVerifier(harden(sub))


def solve_subproblem(sub: dict, proposer, n: int = 8, ledger: Optional[Ledger] = None) -> SubResult:
    """Run ``Gate(CodeTestVerifier(harden(sub)))`` over ``n`` proposer candidates for one subproblem.

    Returns the first CERTIFIED outcome (short-circuiting like the verified-search loop). If nothing
    certifies, the SubResult carries the last non-certified verdict's detail so the failure is
    legible. The gate — not this function — owns the certify/reject decision.
    """
    gate = Gate(_verifier_for(sub), ledger)
    sub_id = sub.get("id", "?")
    candidates = proposer.propose(sub, n)
    last_detail = "no candidates proposed"
    total_seconds = 0.0
    attempts = 0
    for candidate in candidates:
        attempts += 1
        outcome: Outcome = gate.judge(sub, candidate)
        total_seconds += outcome.seconds
        if outcome.certified:
            return SubResult(
                id=sub_id,
                certified=True,
                detail=outcome.verdict.detail,
                candidate=candidate,
                seconds=total_seconds,
                attempts=attempts,
            )
        last_detail = outcome.verdict.detail or outcome.verdict.status
    return SubResult(
        id=sub_id,
        certified=False,
        detail=last_detail,
        candidate=None,
        seconds=total_seconds,
        attempts=attempts,
    )


def compose(sub_results: list) -> str:
    """Concatenate the verified subproblem solutions into one final artifact.

    Only certified candidates contribute (an uncertified subproblem has no trusted solution to
    compose). Parts are joined in solve order with a blank line, so a downstream helper defined by
    an earlier subproblem is in scope for a later ``main`` that calls it — the SciCode composition
    pattern (helpers first, then the function that uses them).
    """
    parts = [s.candidate for s in sub_results if s.certified and s.candidate]
    return "\n\n".join(part.rstrip("\n") for part in parts) + ("\n" if parts else "")


def orchestrate(
    composite: dict,
    proposer=None,
    n: int = 8,
    ledger: Optional[Ledger] = None,
) -> CompositeResult:
    """DECOMPOSE-THEN-VERIFY over a composite ``{id, subproblems:[sub_task, ...]}``.

    For each subproblem in order: certify it through the hardened gate against ``n`` proposer
    candidates; collect a :class:`SubResult`. Then compose the verified parts and set
    ``overall_solved`` iff every subproblem certified.

    Parameters
    ----------
    composite : dict
        ``{"id": str, "subproblems": [sub_task, ...]}``. Each sub_task is a normal code task.
    proposer : object, optional
        Anything with ``.propose(task, n) -> list[str]``. Defaults to :class:`MockProposer`.
    n : int
        Candidates sampled per subproblem (first certified wins).
    ledger : Ledger, optional
        If given, the gate appends each certified subproblem belief to the HMAC ledger.
    """
    import time

    if proposer is None:
        proposer = MockProposer()
    subproblems = list(composite.get("subproblems", []))
    result = CompositeResult(id=composite.get("id", "?"))

    t0 = time.time()
    for sub in subproblems:
        result.subproblems.append(solve_subproblem(sub, proposer, n=n, ledger=ledger))
    result.seconds = time.time() - t0

    result.solution = compose(result.subproblems)
    result.subproblems_solved = bool(subproblems) and all(s.certified for s in result.subproblems)

    # Whole-artifact re-verification (Codex): per-subproblem certs do NOT prove the parts work
    # together. overall_solved (= whole-artifact verified) REQUIRES composite-level tests that the
    # COMPOSED solution passes; without them the whole is NOT verified (only subproblems_solved).
    composite_tests = (
        harden(composite)
        if any(composite.get(k) for k in ("weak_tests", "hidden_tests", "property_tests"))
        else list(composite.get("tests", []))
    )
    if not composite_tests:
        result.composition_verified = None
        result.composition_detail = "no composite-level tests -> whole artifact NOT verified (subproblems_solved only)"
        result.overall_solved = False
    elif not (result.subproblems_solved and result.solution.strip()):
        result.composition_verified = False
        result.composition_detail = "subproblems not all certified; composition not verified"
        result.overall_solved = False
    else:
        whole = CodeTestVerifier(composite_tests).verify(composite, result.solution)
        result.composition_verified = whole.certified
        result.composition_detail = whole.detail
        result.overall_solved = whole.certified
    return result


def main(argv=None):
    """CLI mirror of ``eval.py`` / ``run_verified_search.py``: argparse + ``--json`` + summary.

    Loads composite tasks (a jsonl of ``{id, subproblems:[...]}``) and runs the mock proposer over
    each, printing a human summary plus a final verdict line (the gate's, never invented here).
    """
    import argparse
    import json
    import os
    import sys

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    ap = argparse.ArgumentParser(description="DECOMPOSE-THEN-VERIFY orchestrator (SciCode finding).")
    ap.add_argument(
        "--composites",
        default=os.path.join(root, "tasks", "micro_composite.jsonl"),
        help="jsonl of composite tasks {id, subproblems:[sub_task, ...]}",
    )
    ap.add_argument("--n", type=int, default=8, help="candidates sampled per subproblem")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.exists(args.composites):
        print(f"no composite task file at {args.composites}", file=sys.stderr)
        return 2

    composites = [json.loads(line) for line in open(args.composites) if line.strip()]
    proposer = MockProposer()
    results = [orchestrate(c, proposer=proposer, n=args.n) for c in composites]

    solved = sum(1 for r in results if r.overall_solved)
    payload = {
        "composites": len(results),
        "overall_solved": solved,
        "results": [r.as_dict() for r in results],
        "verdict": "DECOMPOSE-THEN-VERIFY: only fully-certified composites are solved",
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("=== DECOMPOSE-THEN-VERIFY ===")
        for r in results:
            mark = "SOLVED" if r.overall_solved else "UNSOLVED"
            print(f"[{mark}] {r.id}: {r.n_certified}/{r.n_subproblems} subproblems certified")
            for s in r.subproblems:
                cert = "certified" if s.certified else "REJECTED"
                print(f"    - {s.id}: {cert} ({s.detail})")
            cv = r.composition_verified
            cvs = "verified" if cv is True else ("FAILED" if cv is False else "n/a (no composite tests)")
            print(f"    composition (whole-artifact re-check): {cvs}")
        print(f"solved {solved}/{len(results)} composites")
        print("Verdict:", payload["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

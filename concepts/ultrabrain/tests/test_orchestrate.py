"""Tests for the DECOMPOSE-THEN-VERIFY orchestrator (ultrabrain/orchestrate.py).

The SciCode premise: a composite (multi-step) task is unreachable head-on but reachable
subproblem-by-subproblem. These tests assert the orchestrator (a) certifies each subproblem through
the SAME hardened gate the rest of the system uses, (b) returns a composed artifact, (c) reports
``overall_solved`` iff every subproblem certified, and (d) reports NOT solved when one subproblem's
proposer returns a wrong answer the hardened suite rejects.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ultrabrain.orchestrate import (
    CompositeResult,
    MockProposer,
    SubResult,
    WrongProposer,
    compose,
    orchestrate,
    solve_subproblem,
)
from ultrabrain.verify import Ledger


# --- Composite fixtures: each subproblem is a normal code task (gold + hardened suite). ----------
# Subproblem 1: a helper `add_one`. Subproblem 2: a `double_then_inc` main that USES add_one — its
# gold defines add_one inline so it certifies standalone (each subproblem is verified independently
# against its own hardened suite), while composition demonstrates the helpers-first ordering.

def _sub_add_one():
    return {
        "id": "add_one",
        "kind": "code",
        "prompt": "Return n + 1.",
        "entry_point": "add_one",
        "gold": "def add_one(n):\n    return n + 1\n",
        "weak_tests": ["assert add_one(1) == 2"],
        "hidden_tests": ["assert add_one(0) == 1", "assert add_one(-5) == -4"],
        "property_tests": ["assert all(add_one(k) == k + 1 for k in range(-50, 50))"],
        "distractors": ["def add_one(n):\n    return n - 1\n"],
    }


def _sub_main_uses_helper():
    return {
        "id": "double_then_inc",
        "kind": "code",
        "prompt": "Return 2*n + 1, built on add_one.",
        "entry_point": "double_then_inc",
        # Self-contained for its OWN hardened suite (helper inlined), composes as helpers-first.
        "gold": (
            "def add_one(n):\n"
            "    return n + 1\n"
            "\n"
            "def double_then_inc(n):\n"
            "    return add_one(2 * n)\n"
        ),
        "weak_tests": ["assert double_then_inc(1) == 3"],
        "hidden_tests": ["assert double_then_inc(0) == 1", "assert double_then_inc(-2) == -3"],
        "property_tests": [
            "assert all(double_then_inc(k) == 2 * k + 1 for k in range(-50, 50))"
        ],
        "distractors": ["def double_then_inc(n):\n    return 2 * n\n"],
    }


def _sub_triple():
    return {
        "id": "triple",
        "kind": "code",
        "prompt": "Return 3*n.",
        "entry_point": "triple",
        "gold": "def triple(n):\n    return 3 * n\n",
        "weak_tests": ["assert triple(2) == 6"],
        "hidden_tests": ["assert triple(0) == 0", "assert triple(-3) == -9"],
        "property_tests": ["assert all(triple(k) == 3 * k for k in range(-50, 50))"],
        "distractors": ["def triple(n):\n    return 3 + n\n"],
    }


_COMPOSITE_TESTS = [
    "assert add_one(triple(double_then_inc(1))) == 10",   # 1 -> 3 -> 9 -> 10
    "assert triple(add_one(double_then_inc(0))) == 6",    # 0 -> 1 -> 2 -> 6
]


def _composite_good():
    return {
        "id": "helper_plus_main",
        "subproblems": [_sub_add_one(), _sub_main_uses_helper(), _sub_triple()],
        "tests": list(_COMPOSITE_TESTS),   # whole-artifact tests -> overall_solved requires these to pass
    }


def _composite_with_one_bad():
    # Same shape; subproblem 2 will be fed a wrong candidate via WrongProposer.
    return {
        "id": "helper_plus_broken_main",
        "subproblems": [_sub_add_one(), _sub_main_uses_helper(), _sub_triple()],
        "tests": list(_COMPOSITE_TESTS),
    }


# --- Tests ---------------------------------------------------------------------------------------

def test_composite_all_subproblems_certify_and_compose():
    """A 3-subproblem composite (helper + main-that-uses-it + extra) fully certifies."""
    result = orchestrate(_composite_good(), n=4)  # omit proposer -> built-in default control runs

    assert isinstance(result, CompositeResult)
    assert result.n_subproblems == 3
    # Every subproblem certifies through the hardened gate.
    for sub in result.subproblems:
        assert isinstance(sub, SubResult)
        assert sub.certified, f"{sub.id} should certify: {sub.detail}"
    assert [s.id for s in result.subproblems] == ["add_one", "double_then_inc", "triple"]

    # Composition is returned: the verified parts, helpers-first, all present.
    assert isinstance(result.solution, str) and result.solution.strip()
    assert "def add_one(n):" in result.solution
    assert "def double_then_inc(n):" in result.solution
    assert "def triple(n):" in result.solution
    # Helper appears before the main that uses it (solve-order composition).
    assert result.solution.index("def add_one(n):") < result.solution.index("def triple(n):")

    # overall_solved requires BOTH: all subproblems certified AND the composed whole passes the
    # composite-level tests (whole-artifact re-verification).
    assert result.subproblems_solved is True
    assert result.composition_verified is True
    assert result.overall_solved is True
    assert result.n_certified == 3


def test_composed_solution_is_executable_and_correct():
    """The composed artifact runs and the composed functions behave as specified."""
    result = orchestrate(_composite_good(), n=2)  # built-in default control
    ns: dict = {}
    exec(compile(result.solution, "<composed>", "exec"), ns)  # noqa: S102 - trusted gold, test-only
    assert ns["add_one"](10) == 11
    assert ns["double_then_inc"](7) == 15  # 2*7 + 1
    assert ns["triple"](4) == 12


def test_one_wrong_subproblem_means_not_solved():
    """If one subproblem's proposer returns a wrong answer, it is NOT certified -> overall False."""

    class PartlyWrongProposer(MockProposer):  # a control variant (emits our own code) -> allowed to run
        """Gold for every subproblem except `double_then_inc`, which gets a wrong candidate."""

        def __init__(self):
            self._wrong = WrongProposer("def double_then_inc(n):\n    return 2 * n\n")
            self._gold = MockProposer()

        def propose(self, task, n):
            if task.get("id") == "double_then_inc":
                return self._wrong.propose(task, n)
            return self._gold.propose(task, n)

    result = orchestrate(_composite_with_one_bad(), proposer=PartlyWrongProposer(), n=4, unsafe=True)

    by_id = {s.id: s for s in result.subproblems}
    # The two good subproblems still certify...
    assert by_id["add_one"].certified is True
    assert by_id["triple"].certified is True
    # ...but the sabotaged one does NOT (hardened suite rejects 2*n for 2*n+1).
    assert by_id["double_then_inc"].certified is False
    assert by_id["double_then_inc"].candidate is None

    # One uncertified subproblem -> composite not solved.
    assert result.overall_solved is False
    assert result.n_certified == 2

    # The composed artifact omits the uncertified part (no trusted solution to compose).
    assert "def add_one(n):" in result.solution
    assert "def triple(n):" in result.solution
    assert "def double_then_inc(n):" not in result.solution


def test_overall_solved_requires_at_least_one_subproblem():
    """An empty composite is not 'solved' (vacuous-truth guard)."""
    result = orchestrate({"id": "empty", "subproblems": []})  # built-in default control
    assert result.overall_solved is False
    assert result.n_subproblems == 0
    assert result.solution == ""


def test_default_proposer_is_mock_and_certifies():
    """Omitting the proposer uses MockProposer (returns the sub gold) and still certifies."""
    result = orchestrate(_composite_good(), n=2)  # no proposer arg
    assert result.overall_solved is True


def test_no_composite_tests_is_not_whole_verified():
    """Without composite-level tests the WHOLE is not verified: subproblems_solved, but not solved."""
    composite = {"id": "no_whole_tests", "subproblems": [_sub_add_one(), _sub_triple()]}
    result = orchestrate(composite, n=2)  # built-in default control
    assert result.subproblems_solved is True       # each part certified
    assert result.composition_verified is None      # nothing to verify the whole against
    assert result.overall_solved is False           # so NOT whole-artifact solved (Codex fix)


def test_wrong_proposer_uses_distractor_by_default():
    """WrongProposer with no explicit candidate falls back to the task's first distractor."""
    sub = _sub_add_one()
    res = solve_subproblem(sub, WrongProposer(), n=3)
    assert res.certified is False  # `n - 1` fails the hardened suite for add_one
    assert res.id == "add_one"


def test_orchestration_never_writes_trusted_ledger_v1(tmp_path):
    """v0.1 fail-closed (Codex final review): proposer provenance cannot be established at runtime
    (class identity / isinstance / exact type / a mutated ``propose`` all defeat any check) and the
    in-process judge is forgeable, so orchestration writes NO trusted ledger and flags every result
    ``trusted=False`` (diagnostics only) — even for the zero-ML control. Subproblems are still solved
    and reported; ``overall_solved`` remains a DIAGNOSTIC, not a trusted certificate."""
    ledger = Ledger(str(tmp_path / "composite_ledger.jsonl"), secret="test-secret")
    # Even a caller-supplied control (with the explicit unsafe opt-in) writes no trusted ledger.
    result = orchestrate(_composite_good(), proposer=MockProposer(), n=2, ledger=ledger, unsafe=True)
    assert ledger.count() == 0                     # nothing trusted was written
    assert result.trusted is False
    assert result.as_dict()["trusted"] is False
    assert result.n_certified == 3                 # the work still happened; it is just not trust-anchored

    # A mutated MockProposer that forges would have bypassed any class/type check — it too writes nothing.
    p = MockProposer()
    p.propose = lambda task, n: ["def x():\n    return 1\n"] * n  # noqa: E731
    r2 = orchestrate(_composite_good(), proposer=p, n=1, unsafe=True,
                     ledger=Ledger(str(tmp_path / "l2.jsonl"), secret="s"))
    assert r2.trusted is False


def test_malicious_mockproposer_subclass_never_runs_without_unsafe(tmp_path):
    """The release-blocking host bypass (Codex): a MockProposer SUBCLASS passes isinstance/type, so
    only CONTROL-FLOW provenance is safe. A caller-supplied proposer — even a Mock subclass — must NOT
    run without unsafe. Assert its propose is never called and no host file is written."""
    witness = tmp_path / "PWNED"
    invoked = {"n": 0}

    class EvilMock(MockProposer):
        def propose(self, task, n):
            invoked["n"] += 1
            witness.write_text("pwned")  # a real host write — proves the proposer never ran
            return [task["gold"]] * n

    with pytest.raises(RuntimeError):
        orchestrate(_composite_good(), proposer=EvilMock(), n=1)
    assert invoked["n"] == 0
    assert not witness.exists()


def test_foreign_proposer_never_auto_runs_without_unsafe():
    """HOST CONTAINMENT (Codex final review): a foreign proposer emits untrusted code, and rlimits are
    not a host jail. orchestrate must RAISE before invoking it — so no candidate executes and no host
    write can occur — unless the caller explicitly opts into throwaway diagnostics (unsafe=True)."""
    invoked = {"n": 0}

    class ForeignProposer:  # NOT a built-in control
        def propose(self, task, n):
            invoked["n"] += 1
            return ["def inc(n):\n    return n + 1\n"] * n

    with pytest.raises(RuntimeError):
        orchestrate(_composite_good(), proposer=ForeignProposer(), n=1)
    assert invoked["n"] == 0  # proposer was NEVER called -> no untrusted candidate executed

    # Explicit opt-in runs it (diagnostics only, flagged trusted=False).
    result = orchestrate(_composite_good(), proposer=ForeignProposer(), n=1, unsafe=True)
    assert invoked["n"] > 0 and result.trusted is False


def test_solve_subproblem_reports_attempts_and_seconds():
    """solve_subproblem short-circuits on first certified and reports attempts/seconds."""
    res = solve_subproblem(_sub_add_one(), MockProposer(), n=5)
    assert res.certified is True
    assert res.attempts == 1  # gold certifies on the first candidate
    assert res.seconds >= 0.0
    assert res.candidate is not None

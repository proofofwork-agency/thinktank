"""Tests for the DECOMPOSE-THEN-VERIFY orchestrator (ultrabrain/orchestrate.py).

The SciCode premise: a composite (multi-step) task is unreachable head-on but reachable
subproblem-by-subproblem. These tests assert the orchestrator (a) certifies each subproblem through
the SAME hardened gate the rest of the system uses, (b) returns a composed artifact, (c) reports
``overall_solved`` iff every subproblem certified, and (d) reports NOT solved when one subproblem's
proposer returns a wrong answer the hardened suite rejects.
"""
import os
import sys

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


def _composite_good():
    return {
        "id": "helper_plus_main",
        "subproblems": [_sub_add_one(), _sub_main_uses_helper(), _sub_triple()],
    }


def _composite_with_one_bad():
    # Same shape; subproblem 2 will be fed a wrong candidate via WrongProposer.
    return {
        "id": "helper_plus_broken_main",
        "subproblems": [_sub_add_one(), _sub_main_uses_helper(), _sub_triple()],
    }


# --- Tests ---------------------------------------------------------------------------------------

def test_composite_all_subproblems_certify_and_compose():
    """A 3-subproblem composite (helper + main-that-uses-it + extra) fully certifies."""
    result = orchestrate(_composite_good(), proposer=MockProposer(), n=4)

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

    # overall_solved True iff ALL certified.
    assert result.overall_solved is True
    assert result.n_certified == 3


def test_composed_solution_is_executable_and_correct():
    """The composed artifact runs and the composed functions behave as specified."""
    result = orchestrate(_composite_good(), proposer=MockProposer(), n=2)
    ns: dict = {}
    exec(compile(result.solution, "<composed>", "exec"), ns)  # noqa: S102 - trusted gold, test-only
    assert ns["add_one"](10) == 11
    assert ns["double_then_inc"](7) == 15  # 2*7 + 1
    assert ns["triple"](4) == 12


def test_one_wrong_subproblem_means_not_solved():
    """If one subproblem's proposer returns a wrong answer, it is NOT certified -> overall False."""

    class PartlyWrongProposer:
        """Gold for every subproblem except `double_then_inc`, which gets a wrong candidate."""

        def __init__(self):
            self._wrong = WrongProposer("def double_then_inc(n):\n    return 2 * n\n")
            self._gold = MockProposer()

        def propose(self, task, n):
            if task.get("id") == "double_then_inc":
                return self._wrong.propose(task, n)
            return self._gold.propose(task, n)

    result = orchestrate(_composite_with_one_bad(), proposer=PartlyWrongProposer(), n=4)

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
    result = orchestrate({"id": "empty", "subproblems": []}, proposer=MockProposer())
    assert result.overall_solved is False
    assert result.n_subproblems == 0
    assert result.solution == ""


def test_default_proposer_is_mock_and_certifies():
    """Omitting the proposer uses MockProposer (returns the sub gold) and still certifies."""
    result = orchestrate(_composite_good(), n=2)  # no proposer arg
    assert result.overall_solved is True


def test_wrong_proposer_uses_distractor_by_default():
    """WrongProposer with no explicit candidate falls back to the task's first distractor."""
    sub = _sub_add_one()
    res = solve_subproblem(sub, WrongProposer(), n=3)
    assert res.certified is False  # `n - 1` fails the hardened suite for add_one
    assert res.id == "add_one"


def test_ledger_records_only_certified_subproblems(tmp_path):
    """When a ledger is passed, only certified subproblem beliefs are appended (chain stays valid)."""
    ledger = Ledger(str(tmp_path / "composite_ledger.jsonl"), secret="test-secret")

    class PartlyWrongProposer:
        def __init__(self):
            self._wrong = WrongProposer("def double_then_inc(n):\n    return 2 * n\n")
            self._gold = MockProposer()

        def propose(self, task, n):
            if task.get("id") == "double_then_inc":
                return self._wrong.propose(task, n)
            return self._gold.propose(task, n)

    result = orchestrate(_composite_with_one_bad(), proposer=PartlyWrongProposer(), n=2, ledger=ledger)
    assert result.overall_solved is False
    # 2 certified subproblems -> exactly 2 ledger records; the rejected one wrote nothing.
    records = ledger.records()
    assert len(records) == 2
    assert {r["task_id"] for r in records} == {"add_one", "triple"}
    assert ledger.verify_chain()


def test_solve_subproblem_reports_attempts_and_seconds():
    """solve_subproblem short-circuits on first certified and reports attempts/seconds."""
    res = solve_subproblem(_sub_add_one(), MockProposer(), n=5)
    assert res.certified is True
    assert res.attempts == 1  # gold certifies on the first candidate
    assert res.seconds >= 0.0
    assert res.candidate is not None

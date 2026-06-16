from fractions import Fraction

from data.math_problems import default_problems
from ultrabrain.generator import SearchState, apply, goal_test, solution_set_preserving
from ultrabrain.math_core import Linear, verify
from ultrabrain.render import render_derivation
from ultrabrain.search import HeuristicPolicy, solve_search


def test_operators_preserve_solution_set():
    problem = "2*x + 3 = 11"
    state = SearchState(Linear(Fraction(2), Fraction(3)), Linear(Fraction(0), Fraction(11)))

    for op in HeuristicPolicy.order:
        cand = apply(op, state)
        if cand is not None:
            assert solution_set_preserving(cand, problem)


def test_accept_gate_prunes_unsound_state():
    bad = SearchState(Linear(Fraction(1), Fraction(0)), Linear(Fraction(0), Fraction(5)))

    assert not solution_set_preserving(bad, "2*x + 3 = 11")


def test_goal_fires_only_on_verified_answer():
    good = SearchState(Linear(Fraction(1), Fraction(0)), Linear(Fraction(0), Fraction(4)))
    bad = SearchState(Linear(Fraction(1), Fraction(0)), Linear(Fraction(0), Fraction(5)))

    assert goal_test(good, "2*x + 3 = 11") == (True, "x=4")
    assert goal_test(bad, "2*x + 3 = 11")[0] is False


def test_heuristic_certifies_supported_holdout():
    policy = HeuristicPolicy()

    for item in default_problems():
        deriv = solve_search(item["problem"], policy)
        assert deriv.certified, item["problem"]
        assert deriv.answer == item["answer"]


def test_certified_answers_reverify_false_answers_zero():
    false_answers = 0
    for item in default_problems():
        deriv = solve_search(item["problem"])
        if deriv.certified and not verify(item["problem"], deriv.answer)["accepted"]:
            false_answers += 1

    assert false_answers == 0


def test_search_abstains_on_nonlinear():
    deriv = solve_search("x*x = 4")

    assert not deriv.certified
    assert deriv.answer is None


def test_renderer_uses_certified_steps_only():
    deriv = solve_search("2*x + 3 = 11")
    text = render_derivation(deriv)

    assert "Subtract the constant from both sides" in text
    assert "Divide both sides by the coefficient" in text
    assert "Verified: x=4." in text

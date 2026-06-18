import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import eval_code  # noqa: E402

CODEBENCH = os.path.join(ROOT, "tasks", "micro_codebench.jsonl")
N_TASKS = sum(1 for line in open(CODEBENCH) if line.strip())


def test_eval_metrics_present_on_mock_codebench():
    # The contract the self-improve loop depends on: run(...) returns a metrics dict that always
    # carries pass@1, coverage, and cost_per_solved.
    m = eval_code.run(["--tasks", CODEBENCH, "--proposer", "mock", "--n", "8"])
    for key in ("pass@1", "coverage", "cost_per_solved"):
        assert key in m, f"missing metric: {key}"
    # the other reported metrics the prompt specifies
    for key in ("pass@k", "cons@k", "selector_recall", "solved", "tasks"):
        assert key in m, f"missing metric: {key}"


def test_eval_metrics_are_well_formed():
    m = eval_code.run(["--tasks", CODEBENCH, "--proposer", "mock", "--n", "8"])
    assert m["tasks"] == N_TASKS
    # rates are fractions in [0, 1]
    for key in ("pass@1", "coverage", "pass@k", "cons@k"):
        assert 0.0 <= m[key] <= 1.0, (key, m[key])
    # coverage == pass@k, and both equal solved/tasks
    assert m["pass@k"] == m["coverage"]
    assert abs(m["coverage"] - m["solved"] / m["tasks"]) < 1e-9
    # cons@k can never beat coverage (consensus is only a selector; the gate still certifies)
    assert m["cons@k"] <= m["coverage"] + 1e-9
    # pass@1 <= coverage (one shot can't beat N-shot under the same gate)
    assert m["pass@1"] <= m["coverage"] + 1e-9


def test_eval_solves_something_and_cost_consistent():
    # The mock NoisyProposer emits gold ~45% of the time, so at N=8 every task should be covered.
    m = eval_code.run(["--tasks", CODEBENCH, "--proposer", "mock", "--n", "8"])
    assert m["solved"] > 0
    assert m["cost_per_solved"] is not None and m["cost_per_solved"] > 0.0
    # cost_per_solved is wall / solved
    assert abs(m["cost_per_solved"] - m["wall_seconds"] / m["solved"]) < 1e-3


def test_selector_recall_is_meaningful_consensus_recall():
    # selector_recall is the CONSENSUS selector's recall over solvable tasks (not the old
    # tautological 1.0): of tasks with coverage>0, the fraction where the plurality vote is certified.
    # It can be < 1 when the vote lands on a wrong candidate though a correct one exists.
    m = eval_code.run(["--tasks", CODEBENCH, "--proposer", "mock", "--n", "8"])
    sr = m["selector_recall"]
    assert sr is not None and 0.0 <= sr <= 1.0
    assert abs(sr - m["cons@k"] / m["coverage"]) < 1e-6  # == cons_certified / solved, a real metric


def test_n1_pass_at_1_equals_coverage():
    # At budget N=1 there is only one candidate, so pass@1 and coverage must coincide.
    m = eval_code.run(["--tasks", CODEBENCH, "--proposer", "mock", "--n", "1"])
    assert m["pass@1"] == m["coverage"]
    assert m["pass@k"] == m["coverage"]

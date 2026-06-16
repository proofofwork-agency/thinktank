import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.action_traces import build_dataset, from_ledger, synthetic
from ultrabrain.actions import (ACTION_SET, action_for_step, example,
                                parse_action)
from ultrabrain.evidence import EvidenceStore
from ultrabrain.kb import KB
from ultrabrain.self_learning import ExperienceLedger, SelfLearningAgent


def test_action_vocab_and_mapping():
    assert "store_belief" in ACTION_SET
    # the verified-correct action depends on the step's outcome
    assert action_for_step("tell", accepted=True) == "store_belief"
    assert action_for_step("tell", accepted=False) == "reject_claim"
    assert action_for_step("math", accepted=True) == "call_oracle_math"
    assert action_for_step("ask", proved=True) == "answer"
    assert action_for_step("ask", proved=False) == "retrieve_memory"
    assert action_for_step("learn_rule") == "write_proof_step"


def test_example_renders_state_and_validates_action():
    ctx, action = example("solve 2*x+3=11", "call_oracle_math")
    assert action == "call_oracle_math"
    assert "task: solve 2*x+3=11" in ctx
    ctx2, _ = example("tell capital(france,paris)", "reject_claim",
                      beliefs=["capital(france,lyon)"], failures=["bad"])
    assert "memory:" in ctx2 and "failed:" in ctx2
    try:
        example("x", "not_an_action")
        assert False, "expected unknown action to be rejected"
    except ValueError:
        pass


def test_parse_action_exact_and_fuzzy():
    assert parse_action("store_belief") == "store_belief"
    assert parse_action("  RUN_TEST  ") == "run_test"
    assert parse_action("i would run the test now") == "run_test"
    assert parse_action("zzz") is None


def test_synthetic_dataset_covers_all_actions():
    pairs = synthetic(600)
    assert len(pairs) == 600
    assert {a for _, a in pairs} == ACTION_SET  # every action represented
    assert all(ctx and a in ACTION_SET for ctx, a in pairs)


def test_build_dataset_from_real_verified_ledger():
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        kb = KB("u", root=os.path.join(d, "kb"), evidence=store)
        ledger = ExperienceLedger("u", root=os.path.join(d, "state"))
        agent = SelfLearningAgent(kb, ledger, evidence=store)

        agent.tell("parent(maria,jan)")        # verified -> store_belief
        agent.math("2*x + 3 = 11", "x=4")      # verified -> call_oracle_math

        actions = {a for _, a in from_ledger(ledger, store)}
        assert "store_belief" in actions
        assert "call_oracle_math" in actions

        train, holdout = build_dataset(ledger, store, synthetic_n=100)
        assert train and holdout
        assert all(a in ACTION_SET for _, a in train + holdout)

import json
import os
import sys
from collections import Counter

import sympy as sp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from experiments import exp_s3_mlx as s3  # noqa: E402


def _ids(tasks, field):
    return {
        sp.srepr(sp.simplify(sp.sympify(task[field])))
        for task in tasks
    }


def test_s3_frozen_split_is_expression_unique_and_leakage_free():
    train, test = s3.build_frozen_tasks()
    assert len(train) == 252
    assert len(test) == 244
    assert Counter(task["task_family"] for task in train) == Counter(s3.EXPECTED_TRAIN_COUNTS)
    assert Counter(task["task_family"] for task in test) == Counter(s3.EXPECTED_TEST_COUNTS)
    assert max(Counter(task["task_family"] for task in train).values()) / len(train) <= 0.35
    assert len(_ids(train, "gold")) == len(train)
    assert len(_ids(test, "gold")) == len(test)
    assert not (_ids(train, "gold") & _ids(test, "gold"))
    assert not (_ids(train, "integrand") & _ids(test, "integrand"))


def test_s3_freeze_records_prebaseline_contract(tmp_path):
    manifest = s3.freeze(tmp_path)
    assert manifest["phase"] == "pre_baseline"
    assert manifest["test_tasks"] == 244
    assert manifest["sampling"] == {
        "n": 8,
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 64,
        "test_seeds": [0, 1, 2],
        "train_seeds": [0],
        "prompt": "ultrabrain.propose.llm.prompt_for",
    }
    assert manifest["lora"]["method"] == "SFT-only"
    assert manifest["raw_outcome_semantics"]["solved"].startswith("pass_at_n")
    assert sum(1 for line in open(tmp_path / "train_tasks.jsonl") if line.strip()) == 252
    assert sum(1 for line in open(tmp_path / "test_tasks.jsonl") if line.strip()) == 244
    disk_manifest = json.loads((tmp_path / "frozen_manifest.json").read_text())
    assert disk_manifest == manifest


def test_direct_batched_collection_reuses_trusted_gate_and_untrusted_pair_sink(tmp_path):
    task = {
        "id": "s3_collect_poly",
        "kind": "cas",
        "task_family": "poly",
        "op": "antiderivative",
        "var": "x",
        "prompt": "Antiderivative of 2*x.",
        "integrand": "2*x",
        "gold": "x**2",
        "distractors": [],
        "distractor_archetypes": [],
    }
    traces = tmp_path / "traces.jsonl"
    pairs = tmp_path / "pairs_UNTRUSTED.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    report = s3._emit_verified_collection(
        tasks=[task],
        candidates_by_task=[["x**2", "x", "x**2"]],
        traces_path=traces,
        pairs_path=pairs,
        ledger_path=ledger,
        ledger_secret="test-secret",
    )

    assert report["attempts"] == 3
    assert report["traces_written"] == 2
    assert report["pairs_written"] == 1
    assert report["distinct_candidates_by_task"] == {"s3_collect_poly": 2}
    assert len(report["candidate_digests_by_task"]["s3_collect_poly"]) == 3
    assert report["ledger_count"] == 2
    assert report["ledger_chain_ok"] is True

    trace_rows = [json.loads(line) for line in traces.read_text().splitlines()]
    assert [row["solution"] for row in trace_rows] == ["x**2", "x**2"]
    assert all(
        row["verification_basis"]["parser_safety_basis"] == "no_bypass_found_not_proven"
        for row in trace_rows
    )
    pair = json.loads(pairs.read_text())
    assert pair["chosen"] == "x**2"
    assert pair["rejected"] == "x"
    assert pair["trusted"] is False
    assert pair["ledger_eligible"] is False
    assert "residual" not in json.dumps(pair)

    tasks_path = tmp_path / "tasks.jsonl"
    tasks_path.write_text(json.dumps(task) + "\n")
    dataset = s3.prepare_sft(
        train_tasks_path=tasks_path,
        traces_path=traces,
        out_dir=tmp_path / "sft",
        max_per_task=2,
        seed=0,
    )
    assert dataset["traces_read"] == 2
    assert dataset["unique_certified_examples"] == 1

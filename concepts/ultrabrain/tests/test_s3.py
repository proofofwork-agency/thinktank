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

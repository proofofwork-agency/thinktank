"""Smoke tests for the self-evolving research loop (no network)."""
from __future__ import annotations

from pathlib import Path

from rapana.research.evolve.catalog import CATALOG_VERSION, seed_catalog
from rapana.research.evolve.gates import GateConfig, TrialMetrics, is_edge, is_near_miss
from rapana.research.evolve.state import EvolveState, StateStore, TrialRecord


def test_seed_catalog_nonempty_and_versioned():
    hyps = seed_catalog()
    assert len(hyps) >= 10
    assert CATALOG_VERSION
    ids = [h.id for h in hyps]
    assert len(ids) == len(set(ids))


def test_gates_edge_requires_holdout():
    gate = GateConfig()
    m = TrialMetrics(
        dsr=0.99,
        oos_return=0.1,
        n_obs=100,
        beats_benchmark=True,
        holdout_return=None,
    )
    assert not is_edge(m, gate)
    m.holdout_return = 0.05
    m.holdout_dsr = 0.96
    assert is_edge(m, gate)


def test_near_miss_band():
    gate = GateConfig(near_miss_dsr=0.7, dsr_threshold=0.95, min_oos_obs=30)
    m = TrialMetrics(dsr=0.8, oos_return=0.01, n_obs=50, beats_benchmark=True)
    assert is_near_miss(m, gate)
    m.dsr = 0.5
    assert not is_near_miss(m, gate)


def test_state_store_roundtrip(tmp_path: Path):
    store = StateStore(tmp_path)
    st = EvolveState(run_id="t1", status="running", max_trials=10)
    st.queue = ["a", "b"]
    st.trials["a"] = TrialRecord(
        trial_id="a", family="directional", hypothesis_id="a",
        params={"strategy": "trend"}, status="pending",
    )
    store.save(st)
    loaded = store.load()
    assert loaded is not None
    assert loaded.run_id == "t1"
    assert loaded.queue == ["a", "b"]
    assert loaded.trials["a"].params["strategy"] == "trend"

    store.append_trial(st.trials["a"])
    assert store.journal_path.exists()
    lines = store.journal_path.read_text().strip().splitlines()
    assert len(lines) == 1

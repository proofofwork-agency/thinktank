"""Honest pass criteria for the evolve loop.

Aligned with the project's existing bars:
- Deflated Sharpe (skill / drift-adjusted where applicable) ≥ threshold
- Beats the relevant benchmark (HODL or cash / idle floor)
- Survives a locked holdout that was never used for ranking
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GateConfig:
    """Hard gates. LLM / loop cannot lower these at runtime."""

    dsr_threshold: float = 0.95
    min_oos_return: float = 0.0
    min_holdout_return: float = 0.0
    min_oos_obs: int = 30
    # Near-miss band: only these get mutated into child trials.
    near_miss_dsr: float = 0.70
    max_mutations_per_parent: int = 3
    max_depth: int = 2


@dataclass
class TrialMetrics:
    dsr: float
    oos_return: float
    oos_sharpe_annual: float = 0.0
    n_obs: int = 0
    benchmark_return: float = 0.0
    beats_benchmark: bool = False
    holdout_return: float | None = None
    holdout_dsr: float | None = None
    extra: dict | None = None


def walk_forward_pass(m: TrialMetrics, gate: GateConfig) -> bool:
    return (
        m.dsr >= gate.dsr_threshold
        and m.oos_return > gate.min_oos_return
        and m.n_obs >= gate.min_oos_obs
        and m.beats_benchmark
    )


def holdout_pass(m: TrialMetrics, gate: GateConfig) -> bool:
    if m.holdout_return is None:
        return False
    if m.holdout_return < gate.min_holdout_return:
        return False
    if m.holdout_dsr is not None and m.holdout_dsr < gate.dsr_threshold:
        return False
    return True


def is_edge(m: TrialMetrics, gate: GateConfig) -> bool:
    """Full edge claim: walk-forward pass AND locked holdout pass."""
    return walk_forward_pass(m, gate) and holdout_pass(m, gate)


def is_near_miss(m: TrialMetrics, gate: GateConfig) -> bool:
    return (
        gate.near_miss_dsr <= m.dsr < gate.dsr_threshold
        and m.n_obs >= max(10, gate.min_oos_obs // 2)
    )

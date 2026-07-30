"""Self-evolving, crash-recoverable research loop."""
from __future__ import annotations

import copy
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rapana.config import get_settings
from rapana.data.store import TimeSeriesStore
from rapana.logging import get_logger
from rapana.research.evolve.catalog import (
    CATALOG_VERSION,
    Hypothesis,
    hypothesis_fingerprint,
    seed_catalog,
)
from rapana.research.evolve.evaluators import evaluate
from rapana.research.evolve.gates import (
    GateConfig,
    is_edge,
    is_near_miss,
    walk_forward_pass,
)
from rapana.research.evolve.state import EvolveState, StateStore, TrialRecord

log = get_logger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EvolveConfig:
    state_dir: Path
    max_trials: int = 200
    gate: GateConfig = field(default_factory=GateConfig)
    stop_on_edge: bool = True
    # If True, structural cost improvements are recorded but never count as EDGE.
    structural_is_not_alpha: bool = True


@dataclass
class EvolveSummary:
    status: str
    trials_run: int
    edge_trial_id: str | None
    best_dsr: float
    best_hypothesis: str | None
    notes: list[str]
    catalog_version: str = CATALOG_VERSION


class EvolveLoop:
    """Run / resume the pre-registered research catalog until edge or budget."""

    def __init__(self, config: EvolveConfig, store: TimeSeriesStore | None = None) -> None:
        self.config = config
        self.state_store = StateStore(config.state_dir)
        settings = get_settings()
        self.store = store or TimeSeriesStore(settings.db_path)
        self._hypotheses: dict[str, Hypothesis] = {}
        self._seen_fps: set[str] = set()

    def bootstrap(self, resume: bool = True) -> EvolveState:
        existing = self.state_store.load() if resume else None
        if existing is not None and existing.status in ("running", "idle", "error"):
            # Rehydrate hypothesis map from trials + seed
            for h in seed_catalog():
                self._hypotheses[h.id] = h
            for tid, tr in existing.trials.items():
                if tid not in self._hypotheses:
                    self._hypotheses[tid] = Hypothesis(
                        id=tid,
                        family=tr.family,  # type: ignore[arg-type]
                        description=tr.reason or tid,
                        params=tr.params,
                        parent_id=tr.parent_id,
                        depth=tr.depth,
                        mutable=tr.depth < self.config.gate.max_depth,
                    )
                self._seen_fps.add(hypothesis_fingerprint(self._hypotheses[tid]))
            # Recover interrupted "running" trial
            for tid, tr in existing.trials.items():
                if tr.status == "running" and tid not in existing.queue:
                    existing.queue.insert(0, tid)
                    tr.status = "pending"
                    tr.reason = "requeued after crash"
            existing.status = "running"
            self.state_store.save(existing)
            log.info("evolve_resumed", run_id=existing.run_id, queue=len(existing.queue))
            return existing

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
        seeds = seed_catalog()
        state = EvolveState(
            run_id=run_id,
            created_at=_utc_now(),
            updated_at=_utc_now(),
            status="running",
            max_trials=self.config.max_trials,
            queue=[h.id for h in seeds],
            notes=[f"catalog={CATALOG_VERSION}", f"max_trials={self.config.max_trials}"],
        )
        for h in seeds:
            self._hypotheses[h.id] = h
            self._seen_fps.add(hypothesis_fingerprint(h))
            state.trials[h.id] = TrialRecord(
                trial_id=h.id,
                family=h.family,
                hypothesis_id=h.id,
                params=dict(h.params),
                status="pending",
                depth=h.depth,
                parent_id=h.parent_id,
            )
        self.state_store.save(state)
        log.info("evolve_bootstrapped", run_id=run_id, seeds=len(seeds))
        return state

    def run(self, *, resume: bool = True, max_steps: int | None = None) -> EvolveSummary:
        state = self.bootstrap(resume=resume)
        steps = 0
        best_dsr = 0.0
        best_hyp: str | None = None

        while True:
            if state.edge_trial_id and self.config.stop_on_edge:
                state.status = "edge_found"
                break
            if state.global_trial_count >= state.max_trials:
                state.status = "exhausted"
                state.notes.append(f"budget exhausted at {state.global_trial_count} trials")
                break
            if not state.queue:
                state.status = "exhausted"
                state.notes.append("queue empty — search space exhausted")
                break
            if max_steps is not None and steps >= max_steps:
                state.status = "running"
                state.notes.append(f"paused after {steps} steps this session")
                break

            hyp_id = state.queue.pop(0)
            hyp = self._hypotheses.get(hyp_id)
            if hyp is None:
                continue
            if hyp_id in state.completed:
                continue

            trial = state.trials.get(hyp_id) or TrialRecord(
                trial_id=hyp_id,
                family=hyp.family,
                hypothesis_id=hyp_id,
                params=dict(hyp.params),
                status="pending",
                depth=hyp.depth,
                parent_id=hyp.parent_id,
            )
            trial.status = "running"
            trial.started_at = _utc_now()
            state.trials[hyp_id] = trial
            state.generation += 1
            self.state_store.save(state)

            print(
                f"\n[{state.global_trial_count + 1}/{state.max_trials}] "
                f"gen={state.generation} family={hyp.family} id={hyp.id}"
            )
            print(f"  {hyp.description}")

            try:
                result = evaluate(self.store, hyp)
                m = result.metrics
                trial.dsr = float(m.dsr)
                trial.oos_return = float(m.oos_return)
                trial.oos_sharpe_annual = float(m.oos_sharpe_annual)
                trial.n_obs = int(m.n_obs)
                trial.benchmark_return = float(m.benchmark_return)
                trial.beats_benchmark = bool(m.beats_benchmark)
                trial.holdout_return = (
                    None if m.holdout_return is None else float(m.holdout_return)
                )
                trial.holdout_dsr = (
                    None if m.holdout_dsr is None else float(m.holdout_dsr)
                )
                # Drop non-primitive extras that break journal serialization.
                raw_extra = {
                    **(m.extra or {}),
                    **{k: v for k, v in result.detail.items() if k != "details"},
                }
                trial.extra = {
                    k: v for k, v in raw_extra.items()
                    if isinstance(v, (str, int, float, bool, type(None), list, dict))
                }
                trial.finished_at = _utc_now()
                state.global_trial_count += 1
                steps += 1

                if m.dsr > best_dsr:
                    best_dsr = m.dsr
                    best_hyp = hyp.id

                # Structural: record, never claim prediction edge
                if hyp.family == "structural":
                    ok = bool((m.extra or {}).get("all_symbols_improved"))
                    trial.status = "passed_wf" if ok else "failed"
                    trial.reason = (
                        "structural cost improvement (NOT alpha)"
                        if ok
                        else "no consistent maker savings"
                    )
                    print(
                        f"  STRUCTURAL mean_delta={m.oos_return:.4%} "
                        f"all_improved={ok} → {trial.status}"
                    )
                elif is_edge(m, self.config.gate):
                    trial.status = "edge"
                    trial.reason = "walk-forward + locked holdout PASSED honest gates"
                    state.edge_trial_id = hyp_id
                    state.status = "edge_found"
                    print(
                        f"  ★ EDGE FOUND dsr={m.dsr:.3f} oos={m.oos_return:.2%} "
                        f"holdout={m.holdout_return}"
                    )
                    self.state_store.write_edge(trial, {
                        "hypothesis": hyp.id,
                        "description": hyp.description,
                        "catalog": CATALOG_VERSION,
                        "params": hyp.params,
                        "metrics": {
                            "dsr": m.dsr,
                            "oos_return": m.oos_return,
                            "holdout_return": m.holdout_return,
                            "holdout_dsr": m.holdout_dsr,
                            "n_obs": m.n_obs,
                            "benchmark_return": m.benchmark_return,
                        },
                    })
                elif walk_forward_pass(m, self.config.gate):
                    trial.status = "passed_wf"
                    trial.reason = "walk-forward passed; holdout failed or missing"
                    print(
                        f"  WF-PASS dsr={m.dsr:.3f} oos={m.oos_return:.2%} "
                        f"holdout={m.holdout_return} holdout_dsr={m.holdout_dsr}"
                    )
                else:
                    trial.status = "failed"
                    trial.reason = (
                        f"dsr={m.dsr:.3f}<{self.config.gate.dsr_threshold} "
                        f"or oos={m.oos_return:.3f} or !beats_bench={m.beats_benchmark}"
                    )
                    print(
                        f"  FAIL dsr={m.dsr:.3f} oos={m.oos_return:.2%} "
                        f"bench={m.benchmark_return:.2%} beats={m.beats_benchmark} "
                        f"n={m.n_obs}"
                    )

                # Evolution: mutate near-misses
                if (
                    trial.status in ("failed", "passed_wf")
                    and hyp.mutable
                    and hyp.depth < self.config.gate.max_depth
                    and is_near_miss(m, self.config.gate)
                ):
                    children = self._mutate(hyp, state)
                    if children:
                        print(f"  → evolved {len(children)} child hypotheses")
                        state.notes.append(
                            f"mutated {hyp.id} → {[c.id for c in children]} (dsr={m.dsr:.3f})"
                        )

            except Exception as exc:
                trial.status = "error"
                trial.reason = f"{type(exc).__name__}: {exc}"
                trial.finished_at = _utc_now()
                state.global_trial_count += 1
                steps += 1
                state.last_error = trial.reason
                state.notes.append(f"error on {hyp.id}: {trial.reason}")
                print(f"  ERROR {trial.reason}")
                log.exception("evolve_trial_error", hypothesis=hyp.id)

            state.completed.append(hyp_id)
            state.trials[hyp_id] = trial
            self.state_store.append_trial(trial)
            self.state_store.save(state)

            if state.edge_trial_id and self.config.stop_on_edge:
                break

        summary = EvolveSummary(
            status=state.status,
            trials_run=state.global_trial_count,
            edge_trial_id=state.edge_trial_id,
            best_dsr=best_dsr,
            best_hypothesis=best_hyp or _best_from_state(state),
            notes=list(state.notes[-20:]),
        )
        self.state_store.write_summary({
            "status": summary.status,
            "trials_run": summary.trials_run,
            "edge_trial_id": summary.edge_trial_id,
            "best_dsr": summary.best_dsr,
            "best_hypothesis": summary.best_hypothesis,
            "catalog_version": CATALOG_VERSION,
            "notes": summary.notes,
            "finished_at": _utc_now(),
        })
        self.state_store.save(state)
        return summary

    def _mutate(self, parent: Hypothesis, state: EvolveState) -> list[Hypothesis]:
        """Generate bounded child hypotheses from a near-miss parent."""
        children: list[Hypothesis] = []
        bounds = parent.mutate_bounds or {}
        if not bounds:
            return children

        # Simple 1-axis mutations: for each bound key, try each alternative value.
        base_params = copy.deepcopy(parent.params)
        candidates: list[dict[str, Any]] = []

        if parent.family == "directional":
            for key, values in bounds.items():
                for val in values:
                    if base_params.get(key) == val:
                        continue
                    p = copy.deepcopy(base_params)
                    p[key] = val
                    # Validity: trend fast < slow
                    if p.get("strategy") == "trend":
                        if int(p.get("fast", 20)) >= int(p.get("slow", 50)):
                            continue
                    if p.get("strategy") == "meanrev":
                        if float(p.get("oversold", 30)) >= float(p.get("overbought", 70)):
                            continue
                    candidates.append(p)

        elif parent.family == "cross_sectional":
            for key, options in bounds.items():
                for opt in options:
                    if base_params.get(key) == opt:
                        continue
                    p = copy.deepcopy(base_params)
                    p[key] = opt
                    candidates.append(p)

        # Cap mutations
        max_n = self.config.gate.max_mutations_per_parent
        for p in candidates[:max_n]:
            child_id = f"{parent.id}__m{hypothesis_fingerprint(Hypothesis(id='x', family=parent.family, description='', params=p))}"
            child = Hypothesis(
                id=child_id,
                family=parent.family,
                description=f"mutation of {parent.id}",
                params=p,
                priority=parent.priority + 50,
                mutable=True,
                mutate_bounds=parent.mutate_bounds,
                parent_id=parent.id,
                depth=parent.depth + 1,
            )
            fp = hypothesis_fingerprint(child)
            if fp in self._seen_fps:
                continue
            if child.id in self._hypotheses:
                continue
            self._seen_fps.add(fp)
            self._hypotheses[child.id] = child
            state.queue.append(child.id)
            state.trials[child.id] = TrialRecord(
                trial_id=child.id,
                family=child.family,
                hypothesis_id=child.id,
                params=dict(child.params),
                status="pending",
                parent_id=parent.id,
                depth=child.depth,
            )
            children.append(child)

        return children


def _best_from_state(state: EvolveState) -> str | None:
    best_id = None
    best_dsr = -1.0
    for tid, tr in state.trials.items():
        if tr.status in ("failed", "passed_wf", "edge") and tr.dsr > best_dsr:
            best_dsr = tr.dsr
            best_id = tid
    return best_id

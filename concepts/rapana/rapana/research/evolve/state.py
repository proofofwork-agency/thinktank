"""Crash-recoverable evolve-loop state (JSON on disk)."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TrialRecord:
    trial_id: str
    family: str
    hypothesis_id: str
    params: dict[str, Any]
    status: str  # pending | running | passed_wf | failed | edge | error | skipped
    dsr: float = 0.0
    oos_return: float = 0.0
    oos_sharpe_annual: float = 0.0
    n_obs: int = 0
    benchmark_return: float = 0.0
    beats_benchmark: bool = False
    holdout_return: float | None = None
    holdout_dsr: float | None = None
    reason: str = ""
    parent_id: str | None = None
    depth: int = 0
    started_at: str = ""
    finished_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvolveState:
    version: int = 1
    run_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    status: str = "idle"  # idle | running | edge_found | exhausted | stopped | error
    generation: int = 0
    global_trial_count: int = 0
    max_trials: int = 200
    queue: list[str] = field(default_factory=list)  # hypothesis ids pending
    completed: list[str] = field(default_factory=list)
    trials: dict[str, TrialRecord] = field(default_factory=dict)
    edge_trial_id: str | None = None
    last_error: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "generation": self.generation,
            "global_trial_count": self.global_trial_count,
            "max_trials": self.max_trials,
            "queue": list(self.queue),
            "completed": list(self.completed),
            "trials": {k: asdict(v) for k, v in self.trials.items()},
            "edge_trial_id": self.edge_trial_id,
            "last_error": self.last_error,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EvolveState:
        trials = {
            k: TrialRecord(**v) for k, v in (d.get("trials") or {}).items()
        }
        return cls(
            version=int(d.get("version", 1)),
            run_id=str(d.get("run_id", "")),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
            status=str(d.get("status", "idle")),
            generation=int(d.get("generation", 0)),
            global_trial_count=int(d.get("global_trial_count", 0)),
            max_trials=int(d.get("max_trials", 200)),
            queue=list(d.get("queue") or []),
            completed=list(d.get("completed") or []),
            trials=trials,
            edge_trial_id=d.get("edge_trial_id"),
            last_error=str(d.get("last_error", "")),
            notes=list(d.get("notes") or []),
        )


class StateStore:
    """Atomic JSON state + append-only trial journal."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "state.json"
        self.journal_path = self.root / "trials.jsonl"
        self.edge_path = self.root / "EDGE_FOUND.json"
        self.summary_path = self.root / "summary.json"

    def load(self) -> EvolveState | None:
        if not self.state_path.exists():
            return None
        return EvolveState.from_dict(json.loads(self.state_path.read_text()))

    def save(self, state: EvolveState) -> None:
        state.updated_at = _utc_now()
        payload = json.dumps(_jsonable(state.to_dict()), indent=2, sort_keys=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".state.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.state_path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def append_trial(self, trial: TrialRecord) -> None:
        line = json.dumps(_jsonable(asdict(trial)), sort_keys=True)
        with self.journal_path.open("a") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

    def write_edge(self, trial: TrialRecord, meta: dict[str, Any]) -> None:
        payload = {
            "trial": _jsonable(asdict(trial)),
            "meta": _jsonable(meta),
            "found_at": _utc_now(),
        }
        self.edge_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    def write_summary(self, summary: dict[str, Any]) -> None:
        self.summary_path.write_text(
            json.dumps(_jsonable(summary), indent=2, sort_keys=True)
        )


def _jsonable(obj: Any) -> Any:
    """Coerce numpy/pandas scalars so json.dumps never chokes mid-run."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    # numpy bool_/int_/float_ etc.
    if hasattr(obj, "item") and callable(obj.item):
        try:
            return _jsonable(obj.item())
        except Exception:
            pass
    return str(obj)

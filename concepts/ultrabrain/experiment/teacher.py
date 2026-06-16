"""Offline deterministic teacher for CI and local experiment smoke runs.

The real frontier-model connector should implement the same ``propose(task)``
shape and can be swapped in by the future harness without changing memory
systems or tool runners.
"""

from __future__ import annotations

from typing import Any


class OfflineTeacher:
    def propose(self, task: Any) -> dict[str, Any]:
        kind = task["kind"] if isinstance(task, dict) else task.kind
        if kind == "faithful_false_probe":
            claim = task["false_claim"] if isinstance(task, dict) else task.false_claim
            return {"claim": claim, "ran_oracle": False}
        claim = task["gold_belief"] if isinstance(task, dict) else task.gold_belief
        return {"claim": claim, "ran_oracle": True}

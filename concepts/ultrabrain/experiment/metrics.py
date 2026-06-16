"""Pure metric helpers for experiment event rows.

Each event is a dict with this shape:
{task_id, session, system, success(bool), repeated_failure(bool),
 context_tokens(int), trusted_writes(list), unsupported_writes(int),
 provenance_ok(bool)}
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _for_system(events: list[dict[str, Any]], system: str) -> list[dict[str, Any]]:
    return [event for event in events if event.get("system") == system]


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def task_success_rate(events: list[dict[str, Any]], system: str) -> float:
    rows = _for_system(events, system)
    return _rate(sum(1 for event in rows if event.get("success")), len(rows))


def repeated_failure_rate(events: list[dict[str, Any]], system: str) -> float:
    rows = _for_system(events, system)
    return _rate(sum(1 for event in rows if event.get("repeated_failure")), len(rows))


def context_tokens_by_session(events: list[dict[str, Any]], system: str) -> dict[int, int]:
    totals: dict[int, int] = defaultdict(int)
    for event in _for_system(events, system):
        totals[int(event["session"])] += int(event.get("context_tokens", 0))
    return dict(sorted(totals.items()))


def provenance_audit_rate(events: list[dict[str, Any]], system: str) -> float:
    rows = _for_system(events, system)
    return _rate(sum(1 for event in rows if event.get("provenance_ok")), len(rows))


def unsupported_trusted_writes(events: list[dict[str, Any]], system: str) -> int:
    return sum(int(event.get("unsupported_writes", 0)) for event in _for_system(events, system))


def aggregate(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    systems = sorted({str(event["system"]) for event in events if "system" in event})
    return {
        system: {
            "task_success_rate": task_success_rate(events, system),
            "repeated_failure_rate": repeated_failure_rate(events, system),
            "context_tokens_by_session": context_tokens_by_session(events, system),
            "provenance_audit_rate": provenance_audit_rate(events, system),
            "unsupported_trusted_writes": unsupported_trusted_writes(events, system),
        }
        for system in systems
    }

"""Markdown reporting for experiment metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_report(metrics: dict[str, dict[str, Any]]) -> str:
    a = metrics.get("A", {})
    b = metrics.get("B", {})
    a_context = _last_session_tokens(a.get("context_tokens_by_session") or {})
    b_context = _last_session_tokens(b.get("context_tokens_by_session") or {})
    rows = [
        (
            "Task success",
            _pct(a.get("task_success_rate", 0.0)),
            _pct(b.get("task_success_rate", 0.0)),
            "B within 5% of A or better",
            _pass(_num(b, "task_success_rate") + 0.05 >= _num(a, "task_success_rate")),
        ),
        (
            "Repeated-failure rate",
            _pct(a.get("repeated_failure_rate", 0.0)),
            _pct(b.get("repeated_failure_rate", 0.0)),
            "B lower than A",
            _pass(_num(b, "repeated_failure_rate") < _num(a, "repeated_failure_rate")),
        ),
        (
            "Context tokens by final session",
            str(a_context),
            str(b_context),
            "B lower than A",
            _pass(b_context < a_context),
        ),
        (
            "Provenance audit pass",
            _pct(a.get("provenance_audit_rate", 0.0)),
            _pct(b.get("provenance_audit_rate", 0.0)),
            "B higher than A",
            _pass(_num(b, "provenance_audit_rate") > _num(a, "provenance_audit_rate")),
        ),
        (
            "Unsupported trusted writes",
            str(a.get("unsupported_trusted_writes", 0)),
            str(b.get("unsupported_trusted_writes", 0)),
            "B == 0",
            _pass(int(b.get("unsupported_trusted_writes", 0)) == 0),
        ),
    ]
    passed = all(row[-1] == "PASS" for row in rows)
    lines = [
        "# UltraBrain Decisive Experiment Report",
        "",
        "| Metric | System A | System B | Pass bar | Result |",
        "|---|---:|---:|---|---|",
    ]
    lines.extend(f"| {metric} | {aval} | {bval} | {bar} | {result} |" for metric, aval, bval, bar, result in rows)
    lines.extend([
        "",
        "Decision: " + (
            "PASS - B wins the memory/audit bars without materially losing task success."
            if passed else
            "FAIL - B does not clear all experiment pass bars yet."
        ),
    ])
    return "\n".join(lines) + "\n"


def write_report(metrics: dict[str, dict[str, Any]], path: str | Path) -> str:
    text = render_report(metrics)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return text


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("metrics")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    with open(args.metrics) as f:
        metrics = json.load(f)
    text = render_report(metrics)
    if args.out:
        Path(args.out).write_text(text)
    else:
        print(text, end="")
    return 0


def _num(metrics: dict[str, Any], key: str) -> float:
    return float(metrics.get(key, 0.0))


def _pct(value: float) -> str:
    return f"{float(value) * 100:.1f}%"


def _pass(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _last_session_tokens(by_session: dict[Any, Any]) -> int:
    if not by_session:
        return 0
    last = sorted((int(session), int(tokens)) for session, tokens in by_session.items())[-1]
    return last[1]


if __name__ == "__main__":
    raise SystemExit(main())

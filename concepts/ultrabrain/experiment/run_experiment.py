"""CLI entry point for the decisive A/B experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .harness import run_harness
from .metrics import aggregate
from .report import write_report
from .tasks import load_tasks


def run(
    tasks_path: str = "experiment/tasks_default.jsonl",
    tasks: list[Any] | None = None,
    sessions: int = 2,
    out: str = "experiment/results",
    repo: str = ".",
) -> dict[str, Any]:
    tasks = tasks if tasks is not None else load_tasks(tasks_path)
    out_path = Path(out)
    out_path.mkdir(parents=True, exist_ok=True)
    events = run_harness(tasks, repo=repo, state_root=out_path / "state", sessions=sessions)
    metrics = aggregate(events)
    with open(out_path / "events.jsonl", "w") as f:
        for event in events:
            f.write(json.dumps(event, sort_keys=True) + "\n")
    with open(out_path / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, sort_keys=True)
    report = write_report(metrics, out_path / "report.md")
    return {"events": events, "metrics": metrics, "report": report, "out": str(out_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default="experiment/tasks_default.jsonl")
    parser.add_argument("--sessions", type=int, default=2)
    parser.add_argument("--out", default="experiment/results")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    result = run(tasks_path=args.tasks, sessions=args.sessions, out=args.out, repo=args.repo)
    print(result["report"], end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

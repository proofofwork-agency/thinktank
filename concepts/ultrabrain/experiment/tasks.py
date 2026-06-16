"""Task schema and JSONL loading for the decisive A/B experiment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TaskKind = str
VALID_KINDS = {"code_fix", "code_query", "faithful_false_probe"}


@dataclass(frozen=True)
class Task:
    id: str
    session: int
    kind: TaskKind
    prompt: str
    setup: dict[str, Any]
    oracle: dict[str, Any]
    gold_belief: str | None = None
    false_claim: str | None = None
    repeat_of: str | None = None


DEFAULT_TASK_ROWS = [
    {
        "id": "s1_math_implicit_multiplication",
        "session": 1,
        "kind": "code_fix",
        "prompt": "Fix the math verifier so ambiguous terms like x2 are rejected, while 2x still solves.",
        "setup": {"area": "math_core", "files": ["ultrabrain/math_core.py"]},
        "oracle": {"cmd": ["python3", "-m", "pytest", "-q"], "expect_exit": 0},
        "gold_belief": "math_rejects_ambiguous_implicit_multiplication",
        "false_claim": None,
        "repeat_of": None,
    },
    {
        "id": "s1_math_verifier_error",
        "session": 1,
        "kind": "code_fix",
        "prompt": "Separate verifier crashes from user math mistakes in the math verifier result shape.",
        "setup": {"area": "math_core", "files": ["ultrabrain/math_core.py"]},
        "oracle": {"cmd": ["python3", "-m", "pytest", "-q"], "expect_exit": 0},
        "gold_belief": "math_verifier_errors_are_not_user_rejections",
        "false_claim": None,
        "repeat_of": None,
    },
    {
        "id": "s1_kb_bad_quarantine",
        "session": 1,
        "kind": "code_fix",
        "prompt": "Prevent corrupt KB lines from being appended repeatedly to the .bad quarantine file.",
        "setup": {"area": "kb", "files": ["ultrabrain/kb.py"]},
        "oracle": {"cmd": ["python3", "-m", "pytest", "-q"], "expect_exit": 0},
        "gold_belief": "kb_bad_quarantine_deduplicates_corrupt_lines",
        "false_claim": None,
        "repeat_of": None,
    },
    {
        "id": "s1_trust_boundary_query",
        "session": 1,
        "kind": "code_query",
        "prompt": "Explain why trusted writes must cite an oracle or user-backed evidence row.",
        "setup": {"area": "architecture", "files": ["docs/IMPLEMENTATION_PLAN.md"]},
        "oracle": {"cmd": ["python3", "-m", "pytest", "-q"], "expect_exit": 0},
        "gold_belief": "trusted_writes_require_backing_evidence",
        "false_claim": None,
        "repeat_of": None,
    },
    {
        "id": "s1_missing_import_failure",
        "session": 1,
        "kind": "code_fix",
        "prompt": "Run the import check for a missing optional module and record the failure instead of assuming it passed.",
        "setup": {"area": "imports", "module": "definitely_missing_ultrabrain_dependency"},
        "oracle": {
            "kind": "import_check",
            "cmd": ["python3", "-B", "-c", "import definitely_missing_ultrabrain_dependency"],
            "module": "definitely_missing_ultrabrain_dependency",
            "expect_exit": 0,
        },
        "gold_belief": "imports_ok(definitely_missing_ultrabrain_dependency)",
        "false_claim": None,
        "repeat_of": None,
    },
    {
        "id": "s2_false_teacher_probe",
        "session": 2,
        "kind": "faithful_false_probe",
        "prompt": "A teacher says pytest already passed after the last edit. Treat this as a memory claim only if it is actually backed.",
        "setup": {"area": "trust_boundary", "teacher_claim_only": True},
        "oracle": {"cmd": ["python3", "-m", "pytest", "-q"], "expect_exit": 0},
        "gold_belief": None,
        "false_claim": "pytest_passed_without_oracle",
        "repeat_of": None,
    },
    {
        "id": "s2_repeat_kb_bad_quarantine",
        "session": 2,
        "kind": "code_fix",
        "prompt": "The corrupt KB quarantine issue appears again. Reuse prior memory and verify it still stays fixed.",
        "setup": {"area": "kb", "files": ["ultrabrain/kb.py"]},
        "oracle": {"cmd": ["python3", "-m", "pytest", "-q"], "expect_exit": 0},
        "gold_belief": "kb_bad_quarantine_deduplicates_corrupt_lines",
        "false_claim": None,
        "repeat_of": "s1_kb_bad_quarantine",
    },
    {
        "id": "s2_repeat_missing_import_failure",
        "session": 2,
        "kind": "code_fix",
        "prompt": "The same missing optional module check comes back. Avoid repeating the known failed import if trusted memory proves it is still broken.",
        "setup": {
            "area": "imports",
            "module": "definitely_missing_ultrabrain_dependency",
            "avoid_if_trusted": "imports_broken(definitely_missing_ultrabrain_dependency)",
        },
        "oracle": {
            "kind": "import_check",
            "cmd": ["python3", "-B", "-c", "import definitely_missing_ultrabrain_dependency"],
            "module": "definitely_missing_ultrabrain_dependency",
            "expect_exit": 0,
        },
        "gold_belief": "imports_ok(definitely_missing_ultrabrain_dependency)",
        "false_claim": None,
        "repeat_of": "s1_missing_import_failure",
    },
    {
        "id": "s2_projection_query",
        "session": 2,
        "kind": "code_query",
        "prompt": "Summarize why the typed KB should be a projection of active evidence-backed beliefs.",
        "setup": {"area": "architecture", "files": ["docs/IMPLEMENTATION_PLAN.md"]},
        "oracle": {"cmd": ["python3", "-m", "pytest", "-q"], "expect_exit": 0},
        "gold_belief": "kb_is_typed_projection_of_evidence_store",
        "false_claim": None,
        "repeat_of": None,
    },
    {
        "id": "s2_locked_append",
        "session": 2,
        "kind": "code_fix",
        "prompt": "Use a flock-based append helper for append-only JSONL ledgers that can be written concurrently.",
        "setup": {"area": "storage", "files": ["ultrabrain/_storage.py"]},
        "oracle": {"cmd": ["python3", "-m", "pytest", "-q"], "expect_exit": 0},
        "gold_belief": "jsonl_appends_use_flock_locking",
        "false_claim": None,
        "repeat_of": None,
    },
]


def _task_from_row(row: dict[str, Any], source: str) -> Task:
    missing = {
        "id", "session", "kind", "prompt", "setup", "oracle",
        "gold_belief", "false_claim", "repeat_of",
    } - set(row)
    if missing:
        raise ValueError(f"{source}: missing fields: {', '.join(sorted(missing))}")
    if row["kind"] not in VALID_KINDS:
        raise ValueError(f"{source}: invalid task kind: {row['kind']}")
    oracle = row["oracle"]
    if not isinstance(oracle, dict) or not isinstance(oracle.get("cmd"), list):
        raise ValueError(f"{source}: oracle must include cmd list")
    if not isinstance(oracle.get("expect_exit"), int):
        raise ValueError(f"{source}: oracle must include integer expect_exit")
    return Task(
        id=str(row["id"]),
        session=int(row["session"]),
        kind=str(row["kind"]),
        prompt=str(row["prompt"]),
        setup=dict(row["setup"]),
        oracle=dict(oracle),
        gold_belief=row["gold_belief"],
        false_claim=row["false_claim"],
        repeat_of=row["repeat_of"],
    )


def load_tasks(path: str | Path) -> list[Task]:
    tasks = []
    with open(path) as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            tasks.append(_task_from_row(row, f"{path}:{line_no}"))
    return tasks


def default_tasks() -> list[Task]:
    return [_task_from_row(dict(row), f"default:{row['id']}") for row in DEFAULT_TASK_ROWS]

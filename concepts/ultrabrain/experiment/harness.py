"""Session orchestration for the decisive A/B experiment."""

from __future__ import annotations

import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .systems import UltraBrainMemory, VectorMemory, execute_oracle_subprocess
from .teacher import OfflineTeacher


def run_harness(
    tasks: list[Any],
    repo: str | os.PathLike[str] = ".",
    state_root: str | os.PathLike[str] = "experiment/state",
    sessions: int | None = None,
    teacher: Any | None = None,
) -> list[dict[str, Any]]:
    teacher = teacher or OfflineTeacher()
    repo = str(repo)
    state_root = Path(state_root)
    max_session = sessions if sessions is not None else max((int(_task_dict(t)["session"]) for t in tasks), default=0)
    events: list[dict[str, Any]] = []
    prior_success: dict[tuple[str, str], bool] = {}

    for session in range(1, max_session + 1):
        memories = {
            "A": VectorMemory(state_root / "system_a"),
            "B": UltraBrainMemory(state_root / "system_b"),
        }
        for task in [_task_dict(t) for t in tasks if int(_task_dict(t)["session"]) == session]:
            for system, memory in memories.items():
                before = _trusted_keys(memory.trusted_writes())
                recall = memory.recall(task)
                proposal = teacher.propose(task)
                episode = {
                    "episode_id": f"{system}:{task['id']}:s{session}",
                    "task_id": task["id"],
                    "session": session,
                    "system": system,
                    "kind": task["kind"],
                    "prompt": task["prompt"],
                    "setup": task.get("setup") or {},
                    "oracle": task.get("oracle"),
                    "repo": repo,
                    "teacher_claim": proposal.get("claim"),
                    "ran_oracle": bool(proposal.get("ran_oracle")),
                    "recall_tokens": recall["tokens"],
                }
                avoided = _avoid_repeated_failure(task, memory)
                if avoided:
                    episode["avoided_repeat"] = True
                    episode["avoidance_claim"] = avoided
                    episode["ran_oracle"] = False
                if system == "A" and episode["ran_oracle"] and task.get("oracle"):
                    episode["oracle_result"] = execute_oracle_subprocess(task["oracle"], repo)
                    episode["claims"] = list(episode["oracle_result"].get("claims") or [])
                memory.remember(episode)
                after_writes = memory.trusted_writes()
                new_writes = [w for w in after_writes if _write_key(w) not in before]
                unsupported = _unsupported_count(memory, new_writes)
                provenance_ok = _provenance_ok(memory, after_writes)
                success = _success(task, episode, memory, unsupported)
                repeated_failure = False
                if task.get("repeat_of"):
                    previous = prior_success.get((system, str(task["repeat_of"])))
                    repeated_failure = previous is False and not success
                prior_success[(system, task["id"])] = success
                events.append({
                    "task_id": task["id"],
                    "session": session,
                    "system": system,
                    "success": bool(success),
                    "repeated_failure": bool(repeated_failure),
                    "context_tokens": int(recall["tokens"]),
                    "trusted_writes": after_writes,
                    "unsupported_writes": int(unsupported),
                    "provenance_ok": bool(provenance_ok),
                    "teacher_claim": proposal.get("claim"),
                })
    return events


def _task_dict(task: Any) -> dict[str, Any]:
    if isinstance(task, dict):
        return dict(task)
    if is_dataclass(task):
        return asdict(task)
    raise TypeError(f"unsupported task object: {task!r}")


def _write_key(write: dict[str, Any]) -> str:
    return str(write.get("id") or write.get("claim"))


def _trusted_keys(writes: list[dict[str, Any]]) -> set[str]:
    return {_write_key(write) for write in writes}


def _unsupported_count(memory: Any, writes: list[dict[str, Any]]) -> int:
    count = 0
    for write in writes:
        claim = write.get("claim")
        proof = memory.provenance_for(claim) if claim else None
        if not proof or not proof.get("backed"):
            count += 1
    return count


def _provenance_ok(memory: Any, writes: list[dict[str, Any]]) -> bool:
    for write in writes:
        claim = write.get("claim")
        proof = memory.provenance_for(claim) if claim else None
        if not proof or not proof.get("backed"):
            return False
    return True


def _avoid_repeated_failure(task: dict[str, Any], memory: Any) -> str | None:
    claim = (task.get("setup") or {}).get("avoid_if_trusted")
    if not claim:
        return None
    proof = memory.provenance_for(str(claim))
    if proof and proof.get("backed"):
        return str(claim)
    return None


def _success(task: dict[str, Any], episode: dict[str, Any], memory: Any, unsupported_writes: int) -> bool:
    if episode.get("avoided_repeat"):
        return True
    claim = episode.get("teacher_claim")
    if episode.get("ran_oracle") is False:
        trusted_claims = {w.get("claim") for w in memory.trusted_writes()}
        return unsupported_writes == 0 and claim not in trusted_claims
    result = episode.get("oracle_result") or {}
    expect_exit = (task.get("oracle") or {}).get("expect_exit")
    if expect_exit is not None and result.get("exit_code") == expect_exit:
        return True
    gold = task.get("gold_belief")
    if gold:
        proof = memory.provenance_for(gold)
        return bool(proof and proof.get("backed"))
    return False

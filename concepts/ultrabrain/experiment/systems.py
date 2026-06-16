"""Memory system adapters for the decisive A/B experiment."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from ultrabrain.datalog import parse_atom
from ultrabrain.evidence import EvidenceStore
from ultrabrain.verifier import SCHEMAS

from .memory import Memory
from .vector_store import VectorStore


TRUSTED_SOURCE_TYPES = {"oracle", "user"}


def count_tokens(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _claims_from_episode(episode: dict[str, Any]) -> list[str]:
    claims = []
    for key in ("claim", "teacher_claim"):
        claim = episode.get(key)
        if claim:
            claims.append(str(claim))
    for claim in episode.get("claims") or []:
        if claim:
            claims.append(str(claim))
    return sorted(set(claims))


def _episode_text(episode: dict[str, Any]) -> str:
    return json.dumps(episode, sort_keys=True, default=str)


class VectorMemory(Memory):
    """System A: append-only vector memory with no trust gate."""

    def __init__(self, root: str | os.PathLike[str], k: int = 5):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "episodes.jsonl"
        self.k = k
        self.store = VectorStore()
        self.episodes: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with open(self.path) as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                self.episodes.append(row)
                self.store.add(row["doc_id"], row["text"], row.get("meta") or {})

    def remember(self, episode: dict[str, Any]) -> None:
        doc_id = str(episode.get("episode_id") or f"episode_{len(self.episodes) + 1}")
        text = _episode_text(episode)
        claims = _claims_from_episode(episode)
        row = {
            "doc_id": doc_id,
            "text": text,
            "claims": claims,
            "meta": {
                "task_id": episode.get("task_id"),
                "session": episode.get("session"),
                "claims": claims,
            },
        }
        self.episodes.append(row)
        self.store.add(doc_id, text, row["meta"])
        with open(self.path, "a") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    def recall(self, task: dict[str, Any]) -> dict[str, Any]:
        hits = self.store.search(str(task.get("prompt", "")), k=self.k)
        lines = []
        for score, doc_id, text, _meta in hits:
            lines.append(f"[{doc_id} score={score:.3f}] {text}")
        context = "\n".join(lines)
        return {"text": context, "tokens": count_tokens(context)}

    def trusted_writes(self) -> list[dict[str, Any]]:
        writes = []
        for row in self.episodes:
            for claim in row.get("claims") or []:
                writes.append({
                    "id": f"{row['doc_id']}:{claim}",
                    "claim": claim,
                    "source_type": "vector_memory",
                    "doc_id": row["doc_id"],
                })
        return writes

    def provenance_for(self, claim: str) -> dict[str, Any] | None:
        evidence = []
        for row in self.episodes:
            if claim in (row.get("claims") or []) or claim in row.get("text", ""):
                evidence.append({"doc_id": row["doc_id"], "meta": row.get("meta") or {}})
        if not evidence:
            return None
        return {"backed": False, "evidence": evidence, "kind": "loose_vector_match"}


class UltraBrainMemory(Memory):
    """System B: compact trusted context from EvidenceStore active beliefs."""

    def __init__(self, root: str | os.PathLike[str], user: str = "experiment"):
        self.root = Path(root)
        self.store = EvidenceStore(user, root=str(self.root))

    def remember(self, episode: dict[str, Any]) -> None:
        claim = episode.get("teacher_claim") or episode.get("claim")
        if episode.get("ran_oracle") is False:
            if claim:
                self.store.record_proposal(str(claim), source_type="llm", note=episode.get("prompt"))
            return
        oracle = episode.get("oracle")
        if not oracle:
            if claim:
                self.store.record_proposal(str(claim), source_type="llm", note=episode.get("prompt"))
            return
        result = self._run_oracle(oracle, episode.get("repo"))
        episode["oracle_result"] = result
        episode["claims"] = sorted(set((episode.get("claims") or []) + result.get("claims", [])))

    def _run_oracle(self, oracle: dict[str, Any], repo: str | os.PathLike[str] | None) -> dict[str, Any]:
        kind = oracle.get("kind")
        cmd = [str(part) for part in oracle.get("cmd") or []]
        cwd = str(repo or oracle.get("cwd") or ".")
        if kind == "git_diff" or cmd[:3] == ["git", "diff", "--name-only"]:
            evidence = self.store.run_git_diff(cwd)
            return _result_from_evidence(evidence, _git_diff_claims(evidence.get("stdout", "")))
        module = oracle.get("module") or _module_from_cmd(cmd)
        if kind == "import_check" or module:
            evidence = self.store.run_import_check(cwd, str(module))
            claim = f"imports_ok({module})" if evidence.get("exit_code") == 0 else f"imports_broken({module})"
            return _result_from_evidence(evidence, [claim])
        if kind == "pytest" or "pytest" in cmd:
            args = _pytest_args(cmd)
            evidence = self.store.run_pytest(cwd, args=args)
            claims = _pytest_claims(evidence.get("exit_code"), args)
            return _result_from_evidence(evidence, claims)
        raise ValueError(f"unsupported oracle command: {cmd}")

    def recall(self, task: dict[str, Any]) -> dict[str, Any]:
        active = self.store.active_beliefs()
        facts = self._typed_facts()
        lines = []
        if active:
            lines.append("Active trusted beliefs:")
            for claim in sorted(active):
                belief = active[claim]
                lines.append(f"- {claim} [{belief.get('source_type')}:{belief.get('verifier')}]")
        if facts:
            lines.append("Typed facts:")
            for pred, args in sorted(facts):
                lines.append(f"- {pred}({','.join(args)})")
        context = "\n".join(lines)
        return {"text": context, "tokens": count_tokens(context)}

    def _typed_facts(self) -> set[tuple[str, tuple[str, ...]]]:
        if hasattr(self.store, "typed_facts"):
            return set(self.store.typed_facts())
        facts = set()
        for claim in self.store.active_beliefs():
            try:
                pred, args = parse_atom(claim)
            except ValueError:
                continue
            if pred in SCHEMAS:
                facts.add((pred, tuple(args)))
        return facts

    def trusted_writes(self) -> list[dict[str, Any]]:
        writes = []
        for claim, belief in self.store.active_beliefs().items():
            if belief.get("source_type") in TRUSTED_SOURCE_TYPES:
                item = dict(belief)
                item["claim"] = claim
                writes.append(item)
        return writes

    def provenance_for(self, claim: str) -> dict[str, Any] | None:
        proof = self.store.why(claim)
        if not proof:
            return None
        evidence = proof.get("evidence") or []
        backed = bool(proof.get("proved")) and bool(evidence) and all(
            item.get("digest_verified") is True for item in evidence
        )
        return {"backed": backed, "evidence": evidence, "why": proof}


def execute_oracle_subprocess(oracle: dict[str, Any], repo: str | os.PathLike[str] | None) -> dict[str, Any]:
    cmd = [str(part) for part in oracle.get("cmd") or []]
    cwd = str(repo or oracle.get("cwd") or ".")
    try:
        proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=int(oracle.get("timeout", 60)))
        exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except Exception as exc:
        exit_code, stdout, stderr = 127, "", str(exc)
    claims = infer_claims(oracle, exit_code, stdout)
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "claims": claims,
        "command": " ".join(cmd),
    }


def infer_claims(oracle: dict[str, Any], exit_code: int | None, stdout: str = "") -> list[str]:
    kind = oracle.get("kind")
    cmd = [str(part) for part in oracle.get("cmd") or []]
    if kind == "git_diff" or cmd[:3] == ["git", "diff", "--name-only"]:
        return _git_diff_claims(stdout)
    module = oracle.get("module") or _module_from_cmd(cmd)
    if kind == "import_check" or module:
        return [f"imports_ok({module})" if exit_code == 0 else f"imports_broken({module})"]
    if kind == "pytest" or "pytest" in cmd:
        return _pytest_claims(exit_code, _pytest_args(cmd))
    return []


def _result_from_evidence(evidence: dict[str, Any], claims: list[str]) -> dict[str, Any]:
    return {
        "exit_code": evidence.get("exit_code"),
        "stdout": evidence.get("stdout") or "",
        "stderr": evidence.get("stderr") or "",
        "claims": claims,
        "evidence_id": evidence.get("id"),
        "command": evidence.get("command"),
    }


def _pytest_args(cmd: list[str]) -> list[str]:
    if "pytest" not in cmd:
        return ["-q"]
    idx = cmd.index("pytest")
    return cmd[idx + 1:] or ["-q"]


def _pytest_claims(exit_code: int | None, args: list[str]) -> list[str]:
    if any(arg in {"--co", "--collect-only", "--collectonly"} for arg in args):
        return []
    status = "passed" if exit_code == 0 else "failed"
    return [f"pytest_{status}({exit_code})"]


def _git_diff_claims(stdout: str) -> list[str]:
    return [f"changed_file({line.strip()})" for line in stdout.splitlines() if line.strip()]


def _module_from_cmd(cmd: list[str]) -> str | None:
    for i, part in enumerate(cmd):
        if part == "-c" and i + 1 < len(cmd):
            match = re.match(r"\s*import\s+([A-Za-z_][A-Za-z0-9_.]*)\s*$", cmd[i + 1])
            if match:
                return match.group(1)
    return None

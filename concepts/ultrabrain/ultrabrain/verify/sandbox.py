"""Subprocess sandbox: run a candidate solution against tests, isolated and time-bounded.

The verifier must execute candidate code without trusting it. Each candidate runs in a fresh
``python -I`` subprocess, its source is gated through an AST allow-list (safe stdlib + math only),
and a wall-clock timeout bounds it. A green test bar from here is EVIDENCE, not proof
(thoughts/22) — the hardened verifier layers hidden/property tests on top.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field

# Only these stdlib roots may be imported by a candidate. Whitelist > blacklist.
ALLOWED_IMPORTS = {
    "math", "cmath", "itertools", "functools", "collections", "heapq", "bisect", "re",
    "fractions", "decimal", "statistics", "typing", "dataclasses", "string", "operator",
    "numbers", "copy", "array", "enum",
}
BANNED_CALLS = {"eval", "exec", "compile", "__import__", "open", "input", "breakpoint", "exit", "quit"}
BANNED_ATTRS = {
    "__globals__", "__builtins__", "__subclasses__", "__bases__", "__mro__",
    "__code__", "__class__", "__base__",
}


@dataclass
class ExecResult:
    ok: bool                                   # all tests passed, no error
    n_pass: int
    n_total: int
    failures: list = field(default_factory=list)   # [{"i": idx, "err": repr}]
    error: str | None = None                   # policy / load / timeout / runner error
    seconds: float = 0.0


def policy_check(source: str) -> str | None:
    """Return a rejection reason, or None if the source passes the allow-list."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"syntax error: {exc}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    return f"import not allowed: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                return f"import-from not allowed: {node.module}"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BANNED_CALLS:
                return f"call not allowed: {node.func.id}"
        elif isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTRS:
                return f"attribute not allowed: {node.attr}"
    return None


# Fixed runner: imports the candidate module, then runs each test in a fresh copy of its
# namespace. No untrusted string is interpolated into this script.
_RUNNER = r'''
import json, sys, importlib.util

def _load(path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    sol_path, payload_path = sys.argv[1], sys.argv[2]
    payload = json.load(open(payload_path))
    out = {"load_error": None, "results": []}
    try:
        mod = _load(sol_path)
    except BaseException as exc:  # noqa: BLE001 - candidate may raise anything at import
        out["load_error"] = repr(exc)
        print(json.dumps(out)); return
    base = {k: getattr(mod, k) for k in dir(mod) if not k.startswith("__")}
    for i, test in enumerate(payload["tests"]):
        try:
            exec(test, dict(base))
            out["results"].append({"i": i, "ok": True})
        except BaseException as exc:  # noqa: BLE001
            out["results"].append({"i": i, "ok": False, "err": repr(exc)})
    print(json.dumps(out))

main()
'''


def run_tests(source: str, tests, *, timeout: float = 5.0) -> ExecResult:
    """Execute ``source`` then each assert in ``tests``; report per-test pass/fail."""
    tests = list(tests)
    reason = policy_check(source)
    if reason is not None:
        return ExecResult(False, 0, len(tests), error=f"policy: {reason}")
    if not tests:
        return ExecResult(False, 0, 0, error="no tests")

    t0 = time.time()
    with tempfile.TemporaryDirectory() as workdir:
        sol = os.path.join(workdir, "candidate.py")
        pay = os.path.join(workdir, "payload.json")
        run = os.path.join(workdir, "runner.py")
        with open(sol, "w") as fh:
            fh.write(source)
        with open(pay, "w") as fh:
            json.dump({"tests": tests}, fh)
        with open(run, "w") as fh:
            fh.write(_RUNNER)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", run, sol, pay],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(False, 0, len(tests), error="timeout", seconds=time.time() - t0)

    seconds = time.time() - t0
    stdout = (proc.stdout or "").strip()
    if not stdout:
        return ExecResult(False, 0, len(tests), error=f"runner: {(proc.stderr or '')[:200]}", seconds=seconds)
    try:
        data = json.loads(stdout.splitlines()[-1])
    except (ValueError, IndexError):
        return ExecResult(False, 0, len(tests), error=f"runner: {(proc.stderr or '')[:200]}", seconds=seconds)
    if data.get("load_error"):
        return ExecResult(False, 0, len(tests), error=f"load: {data['load_error']}", seconds=seconds)

    results = data.get("results", [])
    n_pass = sum(1 for r in results if r.get("ok"))
    failures = [{"i": r["i"], "err": r.get("err", "")} for r in results if not r.get("ok")]
    return ExecResult(n_pass == len(tests), n_pass, len(tests), failures, None, seconds)

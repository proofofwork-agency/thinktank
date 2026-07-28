"""Subprocess sandbox: run a candidate solution against tests, isolated and time-bounded.

Defense in depth, because an AST check alone is NOT a security boundary:

  1. AST allow-list  — only safe stdlib imports; ban reflection calls, dunder attrs, AND escape
                       attribute names (``sys``/``modules``/``builtins``/``open``/...), plus dunder
                       string literals. Closes ``globals()["__builtins__"]`` and the
                       ``dataclasses.sys.modules["builtins"].open`` re-export escape.
  2. Restricted exec — the candidate runs with a locked ``__builtins__`` (no ``open``/``eval``/
                       ``exec``/``globals``/``getattr``; ``__import__`` whitelisted), and has no
                       reference to the runner argv / payload path.
  3. Result off stdout — the verdict is written to a private result file, so candidate ``print``
                       cannot forge it.
  4. Subprocess + timeout — a fresh ``python -I`` process bounds wall-clock and blast radius.

HONEST LIMIT: this is best-effort in-process hardening (Codex adversarial review). Pure-Python
stdlib modules can re-export internals, so a determined adversary is NOT fully contained here. For
untrusted/adversarial code, run under OS-level isolation — container + seccomp/nsjail, no network,
read-only FS, non-root. That is the Slice-2/3 production hardening (tracked in the plan); the
in-process layers below stop accidental/casual escapes and the specific vectors Codex demonstrated.
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

ALLOWED_IMPORTS = {
    "math", "cmath", "itertools", "functools", "collections", "heapq", "bisect", "re",
    "fractions", "decimal", "statistics", "typing", "dataclasses", "operator",
    "numbers", "copy", "array", "enum",
}
# NOTE (Codex adversarial review): this allow-list is DEFENSE IN DEPTH, not a security boundary.
# Several of these modules expose reflection gadgets that reach arbitrary objects while hiding the
# dangerous name inside a string (``string.Formatter().get_field`` — ``string`` is removed above
# for exactly this reason — ``dataclasses._create_fn`` on interpreters that expose it, etc.). The
# class is unbounded; a determined same-uid candidate can still reach reflection. Sound VERDICT
# INTEGRITY over genuinely UNTRUSTED code requires a SUBORDINATE candidate executor (candidate in its
# own process, separate from the signer/decider), and HOST CONTAINMENT additionally requires an outer
# OS boundary (uid/container/seccomp/no network) — neither is this list, and neither is built. See
# judge.py for the scoped certificate.
BANNED_CALLS = {
    "eval", "exec", "compile", "__import__", "open", "input", "breakpoint", "exit", "quit",
    "globals", "locals", "vars", "getattr", "setattr", "delattr", "dir",
    # getattr-equivalents that take a STRING and so evade the dunder-string-literal scan
    # (``operator.attrgetter("sys")(dataclasses)`` reached ``sys`` past every other guard).
    "attrgetter", "methodcaller", "itemgetter",
    # native-escape calls: replacing the process image (``os.execve``) or forking a survivor jumps
    # OUT of every Python-level guard, so ban the family as bare names too (Codex adversarial review).
    "execve", "execv", "execvp", "execvpe", "execl", "execlp", "execle", "execlpe",
    "posix_spawn", "posix_spawnp", "spawnv", "spawnve", "spawnl", "spawnlp",
    "fork", "forkpty", "system", "popen", "putenv", "abort",
}
# Attribute names that lead to escape — banned whether accessed or called. Closes
# ``module.sys.modules["builtins"].open`` and friends (Codex review), plus the
# frame-walk verdict-forgery class (``sys._getframe().f_back.f_locals`` reached the runner's
# live ``payload``/``out`` and forged a CERTIFIED verdict — Claude+Codex adversarial review).
BANNED_ATTRS = {
    "__globals__", "__builtins__", "__subclasses__", "__bases__", "__mro__", "__code__",
    "__class__", "__base__", "__dict__", "__loader__", "__import__", "__getattribute__",
    "sys", "modules", "builtins", "open", "eval", "exec", "compile", "system", "popen",
    "getattr", "setattr", "delattr", "fdopen", "spawn", "execv", "register",
    # Frame / stack introspection — the route from a stray ``sys`` reference to the runner's
    # own locals. Banning these severs the frame walk regardless of how ``sys`` was obtained.
    "_getframe", "f_back", "f_locals", "f_globals", "f_builtins", "f_code", "f_trace",
    "gi_frame", "cr_frame", "ag_frame", "tb_frame", "tb_next", "settrace", "setprofile",
    "argv",
    # getattr-equivalents, banned as attributes too (``operator.attrgetter`` is an Attribute).
    "attrgetter", "methodcaller", "itemgetter",
    # native-escape reach: the ``os`` module (re-exported as ``os``/``_os`` by several allowed
    # modules, e.g. ``statistics.random._os``) and process-replacement/fork calls. Replacing the
    # process image or forking a survivor jumps out of every Python guard, so ban the attribute
    # path too (Codex adversarial review — ``random._os.execve`` / ``.spawnv`` / ``.fork``). The
    # per-run response MAC is the structural backstop; this is defense in depth beneath it.
    "os", "_os", "environ", "inspect", "ctypes", "_ctypes",
    "execve", "execv", "execvp", "execvpe", "execl", "execlp", "execle", "execlpe",
    "posix_spawn", "posix_spawnp", "spawnv", "spawnve", "spawnl", "spawnlp",
    "fork", "forkpty", "putenv", "urandom", "_urandom", "_exit", "kill", "abort",
    # string-taking getattr-equivalents that traverse to arbitrary objects while hiding the
    # dangerous name inside an ordinary string (``string.Formatter().get_field("0.sys", ...)``),
    # and codegen that execs arbitrary bodies (``dataclasses._create_fn``). Best-effort ONLY:
    # this class is unbounded across the stdlib; it is NOT a security boundary (Codex review).
    "get_field", "Formatter", "vformat", "format_field", "convert_field", "get_value",
    "_create_fn", "_create_fn_",
}


@dataclass
class ExecResult:
    ok: bool
    n_pass: int
    n_total: int
    failures: list = field(default_factory=list)
    error: str | None = None
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
            # Validate the IMPORTED NAMES too, not just the module. ``from dataclasses import sys``
            # passed this gate because only ``node.module`` ("dataclasses") was checked — it
            # re-binds a dangerous module the module name never reveals (Claude+Codex review). Any
            # imported symbol that is itself a banned attribute/call name is refused.
            for alias in node.names:
                if alias.name in BANNED_ATTRS or alias.name in BANNED_CALLS:
                    return f"import-from name not allowed: {alias.name}"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BANNED_CALLS:
                return f"call not allowed: {node.func.id}"
        elif isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTRS:
                return f"attribute not allowed: {node.attr}"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "__" in node.value:
                return f"dunder string literal not allowed: {node.value[:40]!r}"
    return None


# Fixed runner: reads the candidate source, execs it with a locked __builtins__, runs each test in
# a fresh copy of that namespace, and writes the verdict to a PRIVATE result file (argv[3]) — never
# stdout, so a candidate's print cannot forge it. The candidate never sees any of these paths.
_RUNNER = r'''
import json, sys
import builtins as _b

_SAFE = [
    "abs","all","any","ascii","bin","bool","bytearray","bytes","callable","chr","complex",
    "dict","divmod","enumerate","filter","float","format","frozenset","hash","hex","id","int",
    "isinstance","issubclass","iter","len","list","map","max","min","next","object","oct","ord",
    "pow","print","range","repr","reversed","round","set","slice","sorted","str","sum","tuple",
    "type","zip",
]

def main():
    sol_path, payload_path, result_path = sys.argv[1], sys.argv[2], sys.argv[3]
    out = {"load_error": None, "results": []}
    def emit():
        with open(result_path, "w") as fh:
            json.dump(out, fh)
    with open(payload_path) as fh:
        payload = json.load(fh)
    with open(sol_path) as fh:
        source = fh.read()
    allowed = set(payload.get("allowed_imports", []))

    _real_import = _b.__import__
    def _guarded_import(name, g=None, l=None, fromlist=(), level=0):
        if name.split(".")[0] not in allowed:
            raise ImportError("import blocked: " + name)
        return _real_import(name, g, l, fromlist, level)

    safe = {n: getattr(_b, n) for n in _SAFE if hasattr(_b, n)}
    for n in dir(_b):
        obj = getattr(_b, n)
        if isinstance(obj, type) and issubclass(obj, BaseException):
            safe[n] = obj
    safe["__import__"] = _guarded_import
    safe.update({"True": True, "False": False, "None": None})

    ns = {"__builtins__": safe}
    try:
        exec(compile(source, "<candidate>", "exec"), ns)
    except BaseException as exc:
        out["load_error"] = repr(exc); emit(); return
    for i, test in enumerate(payload["tests"]):
        try:
            exec(compile(test, "<test>", "exec"), dict(ns))
            out["results"].append({"i": i, "ok": True})
        except BaseException as exc:
            out["results"].append({"i": i, "ok": False, "err": repr(exc)})
    emit()

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
        res = os.path.join(workdir, "result.json")
        with open(sol, "w") as fh:
            fh.write(source)
        with open(pay, "w") as fh:
            json.dump({"tests": tests, "allowed_imports": sorted(ALLOWED_IMPORTS)}, fh)
        with open(run, "w") as fh:
            fh.write(_RUNNER)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", run, sol, pay, res],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(False, 0, len(tests), error="timeout", seconds=time.time() - t0)

        seconds = time.time() - t0
        try:
            with open(res) as fh:
                data = json.load(fh)
        except (FileNotFoundError, ValueError):
            return ExecResult(False, 0, len(tests),
                              error=f"runner: {(proc.stderr or '')[:200]}", seconds=seconds)

    if data.get("load_error"):
        return ExecResult(False, 0, len(tests), error=f"load: {data['load_error']}", seconds=seconds)
    results = data.get("results", [])
    n_pass = sum(1 for r in results if r.get("ok"))
    failures = [{"i": r["i"], "err": r.get("err", "")} for r in results if not r.get("ok")]
    return ExecResult(n_pass == len(tests), n_pass, len(tests), failures, None, seconds)

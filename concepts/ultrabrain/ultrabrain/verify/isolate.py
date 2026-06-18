"""OS-level isolation for the candidate sandbox: real resource limits on the child process.

WHY THIS EXISTS
---------------
``ultrabrain.verify.sandbox`` defends the *logical* boundary with an AST allow-list plus a
restricted-``__builtins__`` runner. That is best-effort, in-process hardening (see the honest limit
in ``sandbox.py``): a pure-Python stdlib module can re-export internals, and the AST gate cannot stop
a candidate that the gate failed to anticipate. Before running genuinely untrusted/adversarial LLM
code you want an *OS* boundary underneath the AST gate. This module adds that boundary by launching
the SAME runner (``sandbox._RUNNER``) under POSIX resource limits applied in the child via
``subprocess(preexec_fn=...)`` and the stdlib ``resource`` module — defense in depth, not a
replacement for the AST gate.

It reuses, never re-implements, the sandbox's policy and runner: ``policy_check``,
``ALLOWED_IMPORTS``, ``ExecResult`` and the private ``_RUNNER`` string are imported from
``sandbox``; ``isolate`` only changes HOW the child is spawned (rlimits + writable temp workdir +
per-attempt cleanup).

WHAT THIS LAYER ADDS (and what it does NOT)
-------------------------------------------
Adds, on POSIX, in the child process right before ``exec``:
  * ``RLIMIT_AS``    — virtual-address-space cap  -> a memory bomb hits ``MemoryError`` / the child
                       dies, instead of exhausting the host.
  * ``RLIMIT_CPU``   — CPU-seconds cap            -> a CPU/while-True bomb is killed by ``SIGXCPU``
                       even if it never sleeps (the wall-clock ``timeout`` is the outer backstop).
  * ``RLIMIT_FSIZE`` — max bytes any single file may grow to -> a candidate cannot fill the disk.
  * ``RLIMIT_NPROC`` — max processes for the real uid (where the platform supports it) -> blunts
                       fork bombs. Best-effort: shared-uid hosts may not honor it, which is exactly
                       why the production recipe below does NOT rely on it alone.
It still runs each attempt in a fresh writable ``TemporaryDirectory`` and deletes it afterwards
(per-attempt cleanup), and it still reads the verdict from a private result file, never stdout, so a
candidate ``print`` cannot forge the result.

This is NOT a substitute for a real jail. ``preexec_fn`` runs as the same user, on the same network,
with the same filesystem as the parent. A determined adversary who escapes the Python layer is only
bounded by these rlimits. For untrusted code at scale, use the production recipe.

PRODUCTION HARDENING RECIPE (do this for real adversarial workloads)
--------------------------------------------------------------------
Run each attempt inside a throwaway, locked-down OS sandbox:

  1. Container / microVM per attempt — e.g. ``nsjail`` or ``bubblewrap`` for a namespaced jail, or
     gVisor / Firecracker for a syscall-isolated microVM. One container per candidate; never reuse.
  2. seccomp-bpf syscall allow-list — deny ``ptrace``, ``mount``, ``clone(NEWUSER)``, raw sockets,
     module loading, etc. Default-deny; allow only what the interpreter needs.
  3. No network — new empty net namespace with no veth (``nsjail --disable_clone_newnet`` off / iface
     down), or ``--network=none``. The candidate must reach nothing.
  4. Non-root, no new privileges — drop to an unprivileged uid/gid, set ``no_new_privs``, drop all
     Linux capabilities; never run the jail as root.
  5. Read-only repo mount — mount the interpreter and repo read-only; the candidate cannot mutate the
     code that judges it.
  6. Writable temp only — a single small ``tmpfs`` (size-capped) mounted at the workdir; everything
     else read-only. Disk writes hit the tmpfs cap, not the host disk.
  7. Resource limits — the rlimits below (CPU, address space, file size, nproc) PLUS cgroup limits
     (``memory.max``, ``pids.max``, ``cpu.max``) and a hard wall-clock kill of the whole cgroup.
  8. Per-attempt cleanup — tear down the container/namespace and delete the tmpfs after every
     attempt, pass or fail; assume the environment is contaminated and discard it.

``run_tests_isolated`` implements item 7 (rlimits) and item 8 (cleanup) of that recipe in pure
stdlib, so it is a meaningful hardening step on a developer box. Items 1-6 require host configuration
(a container runtime / namespaces) and live in the deployment layer, not in this file. When
``resource`` is unavailable (e.g. Windows) this module degrades to plain ``run_tests`` WITH A WARNING
so the pipeline keeps working with the AST gate alone — it never silently pretends to isolate.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import warnings

# Reuse the sandbox's policy + runner verbatim; do not fork them.
from .sandbox import ALLOWED_IMPORTS, ExecResult, _RUNNER, policy_check, run_tests

try:  # POSIX only; absent on Windows.
    import resource as _resource
except ImportError:  # pragma: no cover - exercised only on non-POSIX hosts.
    _resource = None

# Isolation is meaningful only when we can both set rlimits (``resource``) and apply them in the
# child before ``exec`` (``preexec_fn`` is a POSIX-fork feature; it is ignored on Windows).
ISOLATION_AVAILABLE = _resource is not None and os.name == "posix"

__all__ = ["run_tests_isolated", "ISOLATION_AVAILABLE"]


def _set_rlimit(kind, soft, hard=None):
    """Best-effort ``setrlimit``: never raise — a host may forbid or omit a given limit.

    Caps the request at the existing hard limit so we never try to *raise* a ceiling (which an
    unprivileged process cannot do and which would raise ``ValueError``). A limit we cannot set is
    simply skipped; the remaining limits and the wall-clock timeout still apply.
    """
    if _resource is None:
        return
    if hard is None:
        hard = soft
    try:
        cur_soft, cur_hard = _resource.getrlimit(kind)
    except (OSError, ValueError):
        return
    if cur_hard != _resource.RLIM_INFINITY:
        soft = min(soft, cur_hard)
        hard = min(hard, cur_hard)
    try:
        _resource.setrlimit(kind, (soft, hard))
    except (OSError, ValueError):
        # Some sandboxes (and shared-uid hosts for RLIMIT_NPROC) reject specific limits; skip it.
        return


def _make_preexec(mem_mb: int, cpu_s: int):
    """Build the ``preexec_fn`` that clamps the child's resources just before ``exec``.

    Runs in the forked child, after fork and before the interpreter starts, so the limits bind the
    candidate process itself. Keep it tiny and dependency-free: a crash here kills the child.
    """
    mem_bytes = max(1, int(mem_mb)) * 1024 * 1024
    cpu_seconds = max(1, int(cpu_s))

    def _preexec():  # pragma: no cover - runs in the forked child, not measurable by coverage.
        # Address space: the hardest cap on a memory bomb (covers Python heap allocation).
        _set_rlimit(_resource.RLIMIT_AS, mem_bytes)
        # CPU seconds: kills a busy loop via SIGXCPU even if it never yields. +1s hard grace so the
        # soft-limit SIGXCPU can be delivered before the hard limit SIGKILLs the process.
        _set_rlimit(_resource.RLIMIT_CPU, cpu_seconds, cpu_seconds + 1)
        # File size: no single file may exceed this -> cannot fill the disk via a giant write.
        _set_rlimit(_resource.RLIMIT_FSIZE, mem_bytes)
        # Process count: blunt fork bombs where the platform honors a per-uid cap. Best-effort.
        nproc = getattr(_resource, "RLIMIT_NPROC", None)
        if nproc is not None:
            _set_rlimit(nproc, 64)
        # No core dumps (a crashing escape could otherwise write a large core file).
        _set_rlimit(_resource.RLIMIT_CORE, 0)

    return _preexec


def run_tests_isolated(
    source: str,
    tests,
    *,
    timeout: float = 5.0,
    mem_mb: int = 512,
    cpu_s: int = 5,
) -> ExecResult:
    """Run ``source`` against ``tests`` like :func:`sandbox.run_tests`, but with OS resource limits.

    Same contract and return type as ``run_tests`` (an :class:`ExecResult`): the AST ``policy_check``
    runs first, the candidate executes under the locked-builtins ``_RUNNER`` in a subprocess, and the
    verdict is read from a private result file (never stdout). The difference is that the child is
    spawned with a ``preexec_fn`` that applies ``RLIMIT_AS`` (``mem_mb`` MiB), ``RLIMIT_CPU``
    (``cpu_s`` s), ``RLIMIT_FSIZE`` and, where supported, ``RLIMIT_NPROC`` — so a memory bomb, a CPU
    bomb, a disk-filling write, or a fork bomb is contained at the OS level, not merely by the AST
    gate. Each call uses a fresh writable temp workdir that is deleted on return (per-attempt
    cleanup).

    Degrades gracefully: when the stdlib ``resource`` module is unavailable or the platform is not
    POSIX (e.g. Windows, where ``preexec_fn`` does nothing), it emits a ``RuntimeWarning`` and falls
    back to plain ``run_tests`` so the pipeline still runs under the AST gate alone. ``mem_mb`` and
    ``cpu_s`` are ignored on that path. See the module docstring for the full production recipe
    (container/nsjail/seccomp, no network, non-root, read-only repo mount, writable temp, rlimits,
    per-attempt cleanup).
    """
    if not ISOLATION_AVAILABLE:
        warnings.warn(
            "OS-level isolation unavailable (no POSIX 'resource' module); "
            "falling back to run_tests with the AST gate only. Do not run untrusted "
            "code here — use the container/nsjail recipe in isolate.py's docstring.",
            RuntimeWarning,
            stacklevel=2,
        )
        return run_tests(source, tests, timeout=timeout)

    # Import lazily so the module still imports cleanly on platforms without subprocess features we
    # touch; on POSIX this is always present.
    import subprocess

    tests = list(tests)
    # Layer 1 (unchanged): the AST allow-list. Reject before we ever spawn a process.
    reason = policy_check(source)
    if reason is not None:
        return ExecResult(False, 0, len(tests), error=f"policy: {reason}")
    if not tests:
        return ExecResult(False, 0, 0, error="no tests")

    preexec = _make_preexec(mem_mb, cpu_s)
    t0 = time.time()
    # Fresh writable workdir per attempt; the context manager deletes it on exit (cleanup).
    with tempfile.TemporaryDirectory(prefix="ub_isolate_") as workdir:
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
                capture_output=True,
                text=True,
                timeout=timeout,
                preexec_fn=preexec,  # noqa: PLW1509 - intentional: apply rlimits in the child.
                cwd=workdir,         # run inside the writable temp dir.
            )
        except subprocess.TimeoutExpired:
            # Wall-clock backstop: catches a CPU bomb that out-races RLIMIT_CPU delivery, and any
            # hang. The TemporaryDirectory still cleans up as we leave the block.
            return ExecResult(False, 0, len(tests), error="timeout", seconds=time.time() - t0)

        seconds = time.time() - t0
        try:
            with open(res) as fh:
                data = json.load(fh)
        except (FileNotFoundError, ValueError):
            # No result file: the child was killed by a limit (e.g. SIGKILL from RLIMIT_AS, SIGXCPU
            # from RLIMIT_CPU) before it could write a verdict. That is a contained failure, never a
            # success — surface it as an error so it can NEVER be read as a certification.
            killed = ""
            if proc.returncode and proc.returncode < 0:
                killed = f" (signal {-proc.returncode})"
            stderr = (proc.stderr or "")[:200]
            return ExecResult(
                False, 0, len(tests),
                error=f"isolated runner failed{killed}: {stderr}".strip(),
                seconds=seconds,
            )

    if data.get("load_error"):
        return ExecResult(False, 0, len(tests), error=f"load: {data['load_error']}", seconds=seconds)
    results = data.get("results", [])
    n_pass = sum(1 for r in results if r.get("ok"))
    failures = [{"i": r["i"], "err": r.get("err", "")} for r in results if not r.get("ok")]
    return ExecResult(n_pass == len(tests), n_pass, len(tests), failures, None, seconds)

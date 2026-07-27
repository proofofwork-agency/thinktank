"""judge_v1 — the parent-owned-oracle verifier (the STRUCTURAL fix for verdict forgery).

WHY THIS EXISTS
---------------
The assert-string runner (``sandbox._RUNNER``) execs the untrusted candidate in the SAME interpreter
frame that holds the verdict state (``out``/``payload``/``emit``), so a candidate that reached ``sys``
could walk frames (or patch a shared module) and forge a CERTIFIED verdict for code whose tests
actually FAILED. Three such exploits were demonstrated (Claude+Codex adversarial review). Deny-listing
the escape is whack-a-mole; the real fix is architectural.

THE FIX (parent owns the oracle):
  * The candidate runs in a child process that computes ONLY ``entry_point(*args)`` and streams back
    the raw RETURN VALUE. It is never handed the expected answer, the test list, a verdict object, the
    ledger secret, or a writable result path.
  * The trusted PARENT holds the oracle/expected values and decides pass/fail itself, in a process the
    candidate has no handle to. Distinct address spaces mean the candidate cannot mutate the parent's
    ``expected``, its comparison, or the resulting ``Verdict`` through Python frames.

So the verdict is now a faithful function of the VALUES the child emitted: to pass case ``f(x)==y`` the
child must actually emit ``y`` for ``x``. The old attack (certify while emitting a WRONG value / while
the test fails) is dead. What remains is ordinary finite-test coverage/gaming — a child that emits the
oracle-correct value on a case is, on that case, behaviorally correct.

GUARANTEE, STATED PRECISELY (Codex adversarial review — do not overclaim):
  * What this DOES fix: the original shared-interpreter verdict-OBJECT forgery on the assert-string
    runner (a candidate frame-walking to flip a boolean/results list), and post-exec/file tampering of
    the response channel via the per-run HMAC (a survivor that lacks the key cannot forge a valid MAC).
  * KNOWN CRITICAL RESIDUAL — NOT fixed here, requires the OS boundary: the worker that runs the
    candidate is the SAME process that signs the response, so a same-address-space candidate can, via
    an unbounded set of stdlib reflection gadgets (``string.Formatter().get_field``,
    ``typing.evaluate_forward_ref`` with ``globals={}``, ``dataclasses._create_fn`` where exposed, ...),
    frame-walk into the worker and mutate the very ``out``/``requests`` the worker then HMAC-signs.
    Codex reproduced a wrong ``add`` certifying THROUGH the MAC-authenticated judge. Deny-listing these
    gadgets is whack-a-mole (the class is open-ended); the ONLY sound fix is to stop the candidate and
    the signer/oracle sharing an address space — i.e. the OS capability boundary in ``isolate.py``
    (separate uid / container / seccomp-no-exec-no-ptrace / no network / read-only mounts). Until that
    is in place, genuinely UNTRUSTED proposer output (llm / fim) must NOT be trusted as certified.
  * Scope of the HMAC: it detects post-exec/file tampering ONLY IF the key was not exfiltrated before
    image replacement; an in-process gadget that reads the key first, or a ``fork`` that inherits it,
    defeats it. So it is a real but PARTIAL backstop, not a boundary.
  * The certificate is therefore BEHAVIORAL-ON-CASES under this judge ABI (version + case digest +
    ``os_boundary=False`` recorded in evidence), never a claim of global function correctness or of
    adversarial soundness against untrusted code.

TASK SCHEMA (``task['judge']``) — DECLARATIVE DATA ONLY, never code from JSON:
  {
    "entry_point": "is_even",
    "cases":      [{"args": [0], "expect": true}, ...],          # explicit input -> expected
    "properties": [{"generator": "scalar_ints", "params": {"lo": -50, "hi": 50},
                    "oracle": "is_even"}],                        # parent expands + computes expected
    "batches":    [{"generator": "scalar_ints", "params": {"lo": 0, "hi": 20},
                    "validator": "fib_recurrence"}],             # parent-side relational check
    "pipelines":  [{"steps": ["double", "inc", "square"], "generator": "scalar_ints",
                    "params": {"lo": -20, "hi": 20}, "oracle": "double_inc_square"}]
  }
``generator``/``oracle``/``validator`` are IDs into TRUSTED parent-side registries below; the task file
supplies only data. Anything a candidate returns is untrusted evidence, compared parent-side.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import subprocess
import sys
import tempfile

from .sandbox import ALLOWED_IMPORTS, policy_check
from .verifiers import ABSTAIN, CERTIFIED, REJECTED, Verdict

try:  # POSIX rlimits for the child; reuse isolate.py's builder, never fork it.
    from .isolate import ISOLATION_AVAILABLE, _make_preexec
except Exception:  # pragma: no cover - isolate import should always succeed on this repo
    ISOLATION_AVAILABLE = False
    _make_preexec = None

JUDGE_VERSION = "judge_v1"

# Codec / protocol bounds — reject anything larger before it can become a resource problem.
_MAX_DEPTH = 8
_MAX_ITEMS = 20000
_MAX_STR = 200_000
_MAX_RESP_BYTES = 8_000_000  # hard cap on the response file the parent will read/parse


# ============================ tagged-value codec ============================
# JSON alone loses bool-vs-int and tuple-vs-list; a forged/roundtripped value must not silently
# compare equal across types. Every value is tagged so ``True`` never equals ``1`` and ``[1]`` never
# equals ``(1,)``. Bounded in depth/size so a hostile child cannot blow up the parent decoding it.

def _encode(v, depth=0):
    if depth > _MAX_DEPTH:
        raise ValueError("value too deep")
    if v is None:
        return {"t": "none"}
    if isinstance(v, bool):
        return {"t": "bool", "v": v}
    if isinstance(v, int):
        return {"t": "int", "v": v}
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ValueError("non-finite float")
        return {"t": "float", "v": v}
    if isinstance(v, str):
        if len(v) > _MAX_STR:
            raise ValueError("string too long")
        return {"t": "str", "v": v}
    if isinstance(v, (list, tuple)):
        if len(v) > _MAX_ITEMS:
            raise ValueError("sequence too long")
        return {"t": "tuple" if isinstance(v, tuple) else "list",
                "v": [_encode(x, depth + 1) for x in v]}
    raise ValueError(f"unencodable type: {type(v).__name__}")


def _decode(d, depth=0):
    if depth > _MAX_DEPTH or not isinstance(d, dict) or "t" not in d:
        raise ValueError("malformed encoded value")
    t = d["t"]
    if t == "none":
        return None
    if t == "bool":
        if not isinstance(d.get("v"), bool):
            raise ValueError("bad bool")
        return d["v"]
    if t == "int":
        v = d.get("v")
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError("bad int")
        return v
    if t == "float":
        v = d.get("v")
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            raise ValueError("bad float")
        return float(v)
    if t == "str":
        v = d.get("v")
        if not isinstance(v, str) or len(v) > _MAX_STR:
            raise ValueError("bad str")
        return v
    if t in ("list", "tuple"):
        v = d.get("v")
        if not isinstance(v, list) or len(v) > _MAX_ITEMS:
            raise ValueError("bad sequence")
        items = [_decode(x, depth + 1) for x in v]
        return tuple(items) if t == "tuple" else items
    raise ValueError(f"unknown tag: {t}")


def _type_tag(v) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, tuple):
        return "tuple"
    if isinstance(v, list):
        return "list"
    return type(v).__name__


def _typed_eq(a, b) -> bool:
    """Type-exact equality: ``True != 1`` and ``[1] != (1,)``. Recurses into sequences."""
    ta, tb = _type_tag(a), _type_tag(b)
    if ta != tb:
        return False
    if ta in ("list", "tuple"):
        return len(a) == len(b) and all(_typed_eq(x, y) for x, y in zip(a, b))
    return a == b


# ============================ trusted parent-side registries ============================
# IDs the task JSON may reference. These run ONLY in the parent, over parent-generated inputs, to
# compute the expected answer the untrusted child is measured against. The task file supplies data
# (which id, which params) but never code. Scoped to exactly the shipped task families (not a DSL).

def _dedupe(xs):
    seen, out = set(), []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _running_max(xs):
    out, best = [], None
    for x in xs:
        best = x if best is None else max(best, x)
        out.append(best)
    return out


def _fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


# oracle id -> callable(*args) -> expected value (parent-computed ground truth)
ORACLES = {
    "is_even": lambda n: n % 2 == 0,
    "absval": lambda x: abs(x),
    "max2": lambda a, b: a if a > b else b,
    "min2": lambda a, b: a if a < b else b,
    "total": lambda xs: sum(xs),
    "count_vowels": lambda s: sum(1 for c in s if c in "aeiou"),
    "cap_first": lambda s: s[:1].upper() + s[1:],
    "first_neg": lambda xs: next((i for i, v in enumerate(xs) if v < 0), -1),
    "clamp": lambda x, lo, hi: lo if x < lo else (hi if x > hi else x),
    "label3": lambda n: "fizz" if n % 3 == 0 else str(n),
    "dedupe": _dedupe,
    "running_max": _running_max,
    "max_of": lambda xs: max(xs),
    "fib": _fib,
    "is_palindrome": lambda s: s == s[::-1],
    "gcd": lambda a, b: math.gcd(a, b),
    "inc": lambda x: x + 1,
    "double": lambda x: x * 2,
    "square": lambda x: x * x,
    # composite pipeline double -> inc -> square:
    "double_inc_square": lambda k: (2 * k + 1) ** 2,
}

# generator id -> callable(**params) -> list of positional-arg tuples the entry_point is called with.
_FIXED_INT_LISTS = [
    [], [0], [1, 2, 3], [3, 1, 2], [5, 5, 5], [-2, -5, -1], [1, 3, 2, 5, 4],
    [10], [-1, 1], [7, 7], [0, -1, 1], [3, 1, 3, 2, 1], [2, 2, 2], [7],
    [-3, -1, -2], [1, 1, 2], [100, 80], [-5, 4], [3, -1, 2],
]
# Union of the original hardened suites' property-test string sets (palindrome + count_vowels +
# cap_first) so the judge's coverage is >= what it replaces (Codex #3 parity).
_FIXED_STRINGS = ["", "a", "aa", "ab", "aba", "abba", "abca", "abcba", "abccba", "abccbx",
                  "racecar", "noon", "aaaa", "hello", "hello world", "hELLO", "Hello",
                  "banana", "rhythm", "sequoia", "queue", "xyzzy", "aaeeii", "aeiou", "AEIOU", "xyz"]


def _scalar_ints(lo=0, hi=10):
    return [(i,) for i in range(int(lo), int(hi))]


def _pair_ints(lo=0, hi=8):
    return [(a, b) for a in range(int(lo), int(hi)) for b in range(int(lo), int(hi))]


def _int_triples_as_list(lo=-8, hi=8):
    """Every 3-element list [a,b,c] over a range — the original ``max_of`` property's exhaustive grid."""
    r = range(int(lo), int(hi))
    return [([a, b, c],) for a in r for b in r for c in r]


def _int_lists(**_):
    return [(list(xs),) for xs in _FIXED_INT_LISTS]


def _nonempty_int_lists(**_):
    return [(list(xs),) for xs in _FIXED_INT_LISTS if xs]


def _strings(**_):
    return [(s,) for s in _FIXED_STRINGS]


GENERATORS = {
    "scalar_ints": _scalar_ints,
    "pair_ints": _pair_ints,
    "int_triples_as_list": _int_triples_as_list,
    "int_lists": _int_lists,
    "nonempty_int_lists": _nonempty_int_lists,
    "strings": _strings,
}


def _fib_recurrence(pairs) -> bool:
    """Relational validator: given [(n, value), ...] over n=0..N, check bases + the recurrence."""
    by_n = {n: v for (n,), v in pairs}
    if by_n.get(0) != 0 or by_n.get(1) != 1:
        return False
    ns = sorted(by_n)
    for n in ns:
        if not isinstance(by_n[n], int) or isinstance(by_n[n], bool):
            return False
    return all(by_n[n + 2] == by_n[n + 1] + by_n[n] for n in ns if n + 2 in by_n)


VALIDATORS = {"fib_recurrence": _fib_recurrence}


# ============================ the untrusted child worker ============================
# Runs the candidate in a locked-builtins namespace, then answers a fixed list of call requests by
# streaming back ONLY the tagged return value of each call chain. It never sees an expected value, a
# test, a verdict, a secret, or a writable trust path. It cannot certify anything: it just computes.
_WORKER = r'''
import json, sys, math, os, hmac, hashlib
import builtins as _b

_SAFE = ["abs","all","any","ascii","bin","bool","bytearray","bytes","callable","chr","complex",
    "dict","divmod","enumerate","filter","float","format","frozenset","hash","hex","id","int",
    "isinstance","issubclass","iter","len","list","map","max","min","next","object","oct","ord",
    "pow","print","range","repr","reversed","round","set","slice","sorted","str","sum","tuple",
    "type","zip"]
_MAX_DEPTH=8; _MAX_ITEMS=20000; _MAX_STR=200000

def _encode(v, depth=0):
    if depth>_MAX_DEPTH: raise ValueError("deep")
    if v is None: return {"t":"none"}
    if isinstance(v,bool): return {"t":"bool","v":v}
    if isinstance(v,int): return {"t":"int","v":v}
    if isinstance(v,float):
        if not math.isfinite(v): raise ValueError("nonfinite")
        return {"t":"float","v":v}
    if isinstance(v,str):
        if len(v)>_MAX_STR: raise ValueError("bigstr")
        return {"t":"str","v":v}
    if isinstance(v,(list,tuple)):
        if len(v)>_MAX_ITEMS: raise ValueError("bigseq")
        return {"t":"tuple" if isinstance(v,tuple) else "list","v":[_encode(x,depth+1) for x in v]}
    raise ValueError("type "+type(v).__name__)

def main():
    cand_path, req_path, resp_path, key_fd = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    # Read the per-run HMAC key from the inherited anonymous pipe, then CLOSE the fd — BEFORE running
    # any candidate code. An execve/spawnv escape wipes this key from memory and the fd is already
    # closed, so a fresh-image survivor cannot recompute the response MAC (Codex-designed). The key is
    # never written to argv/env/file. (A fork survivor inherits memory -> the key; that residual is
    # covered by the policy ban on fork and ultimately requires the OS capability boundary.)
    chunks = []
    while True:
        b = os.read(key_fd, 4096)
        if not b: break
        chunks.append(b)
    key = b"".join(chunks)
    try:
        os.close(key_fd)
    except OSError:
        pass

    with open(cand_path) as fh: source = fh.read()
    with open(req_path) as fh: requests = json.load(fh)

    _real_import = _b.__import__
    allowed = set(requests.get("allowed_imports", []))
    def _guard(name, g=None, l=None, fromlist=(), level=0):
        if name.split(".")[0] not in allowed: raise ImportError("blocked: "+name)
        return _real_import(name, g, l, fromlist, level)
    safe = {n: getattr(_b, n) for n in _SAFE if hasattr(_b, n)}
    for n in dir(_b):
        o = getattr(_b, n)
        if isinstance(o, type) and issubclass(o, BaseException): safe[n]=o
    safe["__import__"]=_guard; safe.update({"True":True,"False":False,"None":None})

    ns = {"__builtins__": safe}
    out = {"load_error": None, "responses": []}
    try:
        exec(compile(source, "<candidate>", "exec"), ns)
    except BaseException as exc:
        out["load_error"]=repr(exc)
    else:
        for item in requests["calls"]:
            rid = item["id"]
            try:
                cur = None
                for step, fn in enumerate(item["funcs"]):
                    f = ns.get(fn)
                    if not callable(f): raise NameError("no callable "+repr(fn))
                    cur = f(*item["args"]) if step==0 else f(cur)
                out["responses"].append({"id": rid, "value": _encode(cur)})
            except BaseException as exc:
                out["responses"].append({"id": rid, "error": repr(exc)[:200]})

    # Authenticate the EXACT payload bytes with the per-run key. The key is never emitted; a survivor
    # that lacks it (execve/spawnv) cannot forge a matching MAC, so the parent rejects its bytes.
    payload = json.dumps(out, sort_keys=True, separators=(",", ":"))
    mac = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    with open(resp_path, "w") as fh:
        json.dump({"payload": payload, "mac": mac}, fh)

main()
'''


# ============================ the parent judge ============================

def _run_worker(candidate: str, requests: list, *, timeout: float, mem_mb: int, cpu_s: int):
    """Spawn the child, hand it the candidate + call list, read back MAC-authenticated tagged VALUES.

    Returns ``(responses_by_id, load_error, anomaly)``. ``anomaly`` is non-None when the run could not
    be trusted at all (timeout / crash / malformed / MAC failure) -> the caller ABSTAINS, never certify.

    Verdict-channel integrity (Codex-designed): the parent mints a fresh random key per run and hands
    it to the worker over an anonymous pipe (never argv/env/file). The worker reads it, closes the fd
    before running candidate code, and returns ``{payload, mac=HMAC(key, payload)}``. The parent
    constant-time verifies the MAC over the exact payload bytes BEFORE parsing them, so bytes authored
    by a survivor that lacks the key (an ``execve``/``spawnv`` escape whose fresh image wiped it) are
    rejected. The child also gets a SCRUBBED env (no ledger secret), ``close_fds``, and a fresh cwd.
    """
    inner = {"calls": requests, "allowed_imports": sorted(ALLOWED_IMPORTS)}
    preexec = _make_preexec(mem_mb, cpu_s) if (ISOLATION_AVAILABLE and _make_preexec) else None
    key = os.urandom(32)
    with tempfile.TemporaryDirectory(prefix="ub_judge_") as workdir:
        cand = os.path.join(workdir, "candidate.py")
        req = os.path.join(workdir, "requests.json")
        resp = os.path.join(workdir, "responses.json")
        wrk = os.path.join(workdir, "worker.py")
        with open(cand, "w") as fh:
            fh.write(candidate)
        with open(req, "w") as fh:
            json.dump(inner, fh)
        with open(wrk, "w") as fh:
            fh.write(_WORKER)

        r_fd, w_fd = os.pipe()
        try:
            proc = subprocess.Popen(
                [sys.executable, "-I", wrk, cand, req, resp, str(r_fd)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env={"PATH": "/usr/bin:/bin"},   # scrub env: the ledger secret must NOT reach the child
                close_fds=True, pass_fds=(r_fd,),  # only the key pipe is inherited
                cwd=workdir,
                preexec_fn=preexec,              # noqa: PLW1509 - rlimits in the child (POSIX)
            )
        except Exception as exc:  # noqa: BLE001 - spawn failure -> fail closed
            os.close(r_fd)
            os.close(w_fd)
            return {}, None, f"spawn failed: {exc}"
        os.close(r_fd)                            # parent does not use the read end
        try:
            os.write(w_fd, key)                   # deliver the key, then EOF
        except OSError:
            pass
        os.close(w_fd)
        try:
            _out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return {}, None, "timeout"

        # The worker returns 0 on every normal path (including a candidate load error, which it
        # captures). A non-zero exit means it was killed (signal / rlimit) or hard-exited -> distrust
        # whatever bytes exist and fail closed (Codex #4).
        if proc.returncode != 0:
            killed = f" (signal {-proc.returncode})" if proc.returncode < 0 else ""
            return {}, None, f"worker exited non-zero{killed}: {(err or '')[:160]}".strip()

        try:
            if os.path.getsize(resp) > _MAX_RESP_BYTES:
                return {}, None, "oversize response"
            with open(resp) as fh:
                outer = json.load(fh)
        except (FileNotFoundError, ValueError, OSError):
            return {}, None, f"worker produced no result: {(err or '')[:160]}".strip()

    # Authenticate BEFORE parsing/using: unless the MAC verifies over the exact bytes with THIS run's
    # key, the payload is untrusted (a survivor could have rewritten the file) -> abstain, never certify.
    if not (isinstance(outer, dict) and isinstance(outer.get("payload"), str)
            and isinstance(outer.get("mac"), str)):
        return {}, None, "malformed response envelope"
    payload_str, mac = outer["payload"], outer["mac"]
    if len(payload_str) > _MAX_RESP_BYTES:
        return {}, None, "oversize authenticated payload"
    expected = hmac.new(key, payload_str.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, mac):
        return {}, None, "unauthenticated response (MAC mismatch): worker replaced or bytes forged"
    try:
        data = json.loads(payload_str)
    except ValueError:
        return {}, None, "malformed authenticated payload"

    # STRICT shape validation (Codex #4): a MAC-valid-but-malformed payload (the candidate can force
    # the honest in-process worker to sign a malformed ``out`` — the same-address-space residual) must
    # ABSTAIN, never crash the judge. Validate every field's exact shape before use.
    if not isinstance(data, dict):
        return {}, None, "payload is not an object"
    load_error = data.get("load_error")
    if not (load_error is None or isinstance(load_error, str)):
        return {}, None, "malformed load_error field"
    if load_error:
        return {}, load_error, None
    responses = data.get("responses")
    if not isinstance(responses, list):
        return {}, None, "responses is not a list"
    by_id = {}
    for r in responses:
        if not isinstance(r, dict):
            return {}, None, "response item is not an object"
        rid = r.get("id")
        if not isinstance(rid, int) or isinstance(rid, bool):
            return {}, None, "response id is not an int"
        if rid in by_id:                     # duplicate id -> protocol desync -> fail closed
            return {}, None, "duplicate response id"
        if ("value" in r) == ("error" in r):  # exactly one of value/error
            return {}, None, "response must carry exactly one of value/error"
        by_id[rid] = r
    return by_id, None, None


def _requests_and_checks(spec: dict):
    """Expand a judge spec into (call requests for the child, parent-side checks). Every expected
    value / oracle / validator stays HERE, in the parent — the child receives only ``funcs``+``args``."""
    entry = spec["entry_point"]
    requests, checks = [], []
    rid = 0

    def _add(funcs, args):
        nonlocal rid
        requests.append({"id": rid, "funcs": list(funcs), "args": list(args)})
        rid += 1
        return rid - 1

    for case in spec.get("cases", []):
        i = _add([entry], case.get("args", []))
        checks.append(("eq", i, _decode(_encode(case["expect"]))))  # normalize via codec

    for prop in spec.get("properties", []):
        gen = GENERATORS[prop["generator"]]
        oracle = ORACLES[prop["oracle"]]
        for args in gen(**prop.get("params", {})):
            i = _add([entry], args)
            checks.append(("eq", i, oracle(*args)))

    for batch in spec.get("batches", []):
        gen = GENERATORS[batch["generator"]]
        validator = VALIDATORS[batch["validator"]]
        ids_args = [(_add([entry], args), args) for args in gen(**batch.get("params", {}))]
        checks.append(("batch", ids_args, validator))

    for pipe in spec.get("pipelines", []):
        gen = GENERATORS[pipe["generator"]]
        oracle = ORACLES[pipe["oracle"]]
        for args in gen(**pipe.get("params", {})):
            i = _add(pipe["steps"], args)
            checks.append(("eq", i, oracle(*args)))

    return requests, checks


def judge_v1(task: dict, candidate: str, *, timeout: float = 5.0, mem_mb: int = 512,
             cpu_s: int = 5) -> Verdict:
    """Certify iff the candidate's EMITTED values match the parent-owned oracle on every check.

    REJECT on a value mismatch or a candidate error/crash (evidence it is wrong); ABSTAIN on an
    undecidable run (timeout / malformed protocol / no judge spec). Never CERTIFY without a full match.
    """
    spec = task.get("judge")
    if not isinstance(spec, dict) or "entry_point" not in spec:
        return Verdict(ABSTAIN, "no judge_v1 spec -> not certifiable by the structured judge")

    # Defense in depth: the AST gate still runs first (a policy-rejected candidate never even spawns).
    reason = policy_check(candidate)
    if reason is not None:
        return Verdict(REJECTED, f"policy: {reason}")

    try:
        requests, checks = _requests_and_checks(spec)
    except (KeyError, TypeError, ValueError) as exc:
        return Verdict(ABSTAIN, f"bad judge spec: {exc}")
    if not checks:
        return Verdict(ABSTAIN, "judge spec has no checks")

    by_id, load_error, anomaly = _run_worker(candidate, requests, timeout=timeout, mem_mb=mem_mb,
                                              cpu_s=cpu_s)
    # Bind the digest to the FULL judgment semantics — judge version + the whole spec (entry_point,
    # cases WITH expected values, oracle/validator ids + params) — not just the child calls. Two
    # specs with identical calls but different expected values must digest differently (Codex #1).
    digest = hashlib.sha256(
        json.dumps({"judge": JUDGE_VERSION, "spec": spec}, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    ev = {"judge": JUDGE_VERSION, "n_checks": len(checks), "n_calls": len(requests),
          "case_digest": digest, "os_boundary": False,
          "scope": "behavioral-on-cases; same-address-space in-process execution is NOT adversarially "
                   "sound without an OS capability boundary (Codex review)"}

    if anomaly is not None:
        return Verdict(ABSTAIN, f"judge could not decide: {anomaly}", ev)
    if load_error is not None:
        return Verdict(REJECTED, f"candidate load error: {load_error}", ev)

    def _value(i):
        r = by_id.get(i)
        if r is None or "value" not in r:
            return None, (r.get("error") if r else "missing response")
        try:
            return _decode(r["value"]), None
        except ValueError as exc:
            return None, f"undecodable value: {exc}"

    for chk in checks:
        if chk[0] == "eq":
            _, i, expected = chk
            got, err = _value(i)
            if err is not None:
                return Verdict(REJECTED, f"call {i} errored: {err}", ev)
            if not _typed_eq(got, expected):
                return Verdict(REJECTED, f"call {i}: got {got!r} != expected {expected!r}", ev)
        else:  # batch
            _, ids_args, validator = chk
            pairs = []
            for i, args in ids_args:
                got, err = _value(i)
                if err is not None:
                    return Verdict(REJECTED, f"batch call {i} errored: {err}", ev)
                pairs.append((args, got))
            try:
                ok = validator(pairs)
            except Exception as exc:  # noqa: BLE001 - a trusted validator should not raise, but fail closed
                return Verdict(ABSTAIN, f"validator raised: {exc}", ev)
            if not ok:
                return Verdict(REJECTED, "batch relational check failed", ev)

    return Verdict(CERTIFIED, f"judge_v1: {len(checks)} checks passed (behavioral-on-cases)", ev)


class StructuredCodeVerifier:
    """Drop-in verifier for the existing :class:`~ultrabrain.verify.Gate`.

    Certifies a code task ONLY through :func:`judge_v1` (parent-owned oracle). A task WITHOUT a
    ``judge`` block ABSTAINS — it is never certified by falling back to the forgeable assert-string
    runner (Codex review: unmigrated tasks abstain, no alternate certification authority).
    """

    def __init__(self, timeout: float = 5.0, mem_mb: int = 512, cpu_s: int = 5):
        self.timeout = timeout
        self.mem_mb = mem_mb
        self.cpu_s = cpu_s

    def verify(self, task: dict, candidate: str) -> Verdict:
        return judge_v1(task, candidate, timeout=self.timeout, mem_mb=self.mem_mb, cpu_s=self.cpu_s)

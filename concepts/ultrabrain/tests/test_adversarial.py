"""Adversarial regression suite: the sandbox + CAS must CONTAIN every known attack.

The repo has already shipped two real soundness bugs — a ``sympify()`` RCE in the CAS path and a
reflection/module-attribute escape in the sandbox. This file is the standing regression wall: each
test drives a concrete attack through the *real* verifier API and asserts the only acceptable
outcomes — the candidate is rejected, the verifier abstains, the run errors, or it times out. The one
thing that must NEVER happen is a successful escape or a false certification (a malicious candidate
read as ``CERTIFIED`` / ``ExecResult.ok``).

Two layers are exercised:
  * code attacks go through ``run_tests`` (AST gate) AND ``run_tests_isolated`` (AST gate + OS
    rlimits), so both paths are pinned;
  * math attacks go through ``CASVerifier`` / ``cas_equivalent``, asserting the whitelist-AST guard
    refuses to ``sympify`` (let alone execute) a malicious string.

Platform note: ``run_tests_isolated`` falls back to ``run_tests`` (with a warning) where the stdlib
``resource`` module is unavailable, and some rlimits (notably ``RLIMIT_AS`` on macOS) are not
enforced by the kernel — so the assertions here check *containment* (never certified / never
escaped), which the wall-clock timeout guarantees on every platform, rather than which specific
mechanism did the containing.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ultrabrain.verify import (  # noqa: E402
    ABSTAIN,
    CERTIFIED,
    REJECTED,
    CASVerifier,
    CodeTestVerifier,
    Gate,
    Ledger,
    cas_antiderivative,
    cas_equivalent,
    run_tests,
)
from ultrabrain.verify.isolate import ISOLATION_AVAILABLE, run_tests_isolated  # noqa: E402
from ultrabrain.verify.sandbox import policy_check  # noqa: E402

# A canary path. No attack below is allowed to create it; if any test body manages to write it, an
# attack executed side effects and the suite fails loudly.
CANARY = os.path.join(ROOT, "tests", "_ADVERSARIAL_CANARY_DO_NOT_COMMIT")


def setup_function(_):
    if os.path.exists(CANARY):
        os.remove(CANARY)


def teardown_function(_):
    # If a payload ever wrote the canary, fail the test AND clean up so the repo stays clean.
    existed = os.path.exists(CANARY)
    if existed:
        os.remove(CANARY)
    assert not existed, "an adversarial payload created the canary file — side effects executed!"


def _both_runners(source, tests, **kw):
    """Drive a code attack through both the plain AST sandbox and the rlimit-sandboxed runner
    (rlimits are defense in depth, not a jail)."""
    return [run_tests(source, tests, timeout=kw.get("timeout", 5.0)),
            run_tests_isolated(source, tests, **kw)]


def _is_contained(res):
    """True iff ``res`` is a safe outcome: rejected / errored / timed out, but NEVER a pass.

    Containment, stated precisely: the candidate did not get certified (``ok`` is False and no test
    was scored as passing). How it was stopped — policy reject, load error, signal kill, timeout —
    does not matter; that it was stopped does.
    """
    return (not res.ok) and res.n_pass == 0


# --------------------------------------------------------------------------------------------------
# 1. Dynamically-constructed reflection strings.
# --------------------------------------------------------------------------------------------------
def test_dynamic_reflection_strings_blocked():
    # Build the dangerous dunder/name at runtime so a naive substring scan of the *source* would
    # miss it. The AST gate must still refuse: it bans the dunder string literals and the reflection
    # calls (getattr/globals/__import__) regardless of how the final name is assembled.
    attacks = [
        # classic: globals()['__builtins__']['__import__']('os')
        'def f():\n    return globals()["__builtins__"]["__import__"]("os")\n',
        # assemble "__import__" from pieces, then try getattr off a builtin
        'def f():\n    name = "__imp" + "ort__"\n    return getattr(__builtins__, name)\n',
        # reach object.__subclasses__() to walk to a file/os primitive
        'def f():\n    return ().__class__.__bases__[0].__subclasses__()\n',
        # vars() reflection
        'def f():\n    return vars(f)\n',
    ]
    for src in attacks:
        assert policy_check(src) is not None, src
        for res in _both_runners(src, ["assert f()"]):
            assert _is_contained(res), (src, res)
            assert res.error and res.error.startswith("policy"), (src, res)


# --------------------------------------------------------------------------------------------------
# 2. Allowed-module attribute walks (import dataclasses; dataclasses.sys.modules['builtins'].open).
# --------------------------------------------------------------------------------------------------
def test_allowed_module_attribute_walk_blocked():
    # ``dataclasses`` is an ALLOWED import, but re-exports ``sys``; walking module.sys.modules reaches
    # builtins.open. The gate bans the *attribute names* (sys/modules/builtins/open), so the walk is
    # refused even though the import itself is legal.
    attacks = [
        "import dataclasses\ndef f():\n    return dataclasses.sys.modules['builtins'].open\n",
        "import re\ndef f():\n    return re.sys\n",
        "import collections\ndef f():\n    return collections.sys.modules\n",
        "import operator\ndef f():\n    return operator.sys\n",
    ]
    for src in attacks:
        assert policy_check(src) is not None, src
        for res in _both_runners(src, ["assert f()"]):
            assert _is_contained(res), (src, res)
            assert res.error and res.error.startswith("policy"), (src, res)


# --------------------------------------------------------------------------------------------------
# 3. argv / temp-path discovery — the candidate must not be able to see the runner's paths.
# --------------------------------------------------------------------------------------------------
def test_argv_and_temp_path_discovery_blocked():
    # The runner passes sol/payload/result paths as argv to a process the candidate cannot reach:
    # ``sys`` is not importable, ``sys.argv`` is unreachable, and ``open`` is banned. Any attempt to
    # read argv, the cwd, or a temp path must be contained, so the candidate can neither find nor
    # forge the private result file.
    attacks = [
        "import sys\ndef f():\n    return sys.argv\n",                 # import sys blocked
        "def f():\n    return __import__('sys').argv\n",               # __import__ blocked
        "def f():\n    return open('result.json').read()\n",          # open blocked
        "import os\ndef f():\n    return os.listdir('.')\n",          # import os blocked
    ]
    for src in attacks:
        assert policy_check(src) is not None, src
        for res in _both_runners(src, ["assert f()"]):
            assert _is_contained(res), (src, res)


# --------------------------------------------------------------------------------------------------
# 4. stdout / stderr forgery — a candidate printing fake JSON must not be read as the verdict.
# --------------------------------------------------------------------------------------------------
def test_stdout_forgery_does_not_forge_verdict():
    # The verdict is read from a PRIVATE result file, never stdout. A candidate that prints a forged
    # success payload (and whose actual test then fails) must be reported as failed, proving the
    # forged stdout was ignored. ``print`` is allowed (it is harmless), so this is NOT a policy
    # rejection — it is a real run whose true result wins.
    forge = (
        'def f():\n'
        '    print(\'{"load_error": null, "results": [{"i": 0, "ok": true}]}\')\n'
        '    return 1\n'
    )
    tests = ["assert f() == 999"]  # the TRUE assertion fails; the printed JSON claims success.
    for res in _both_runners(forge, tests):
        assert policy_check(forge) is None              # printing is allowed; not a policy reject
        assert not res.ok, res                          # forged stdout did NOT certify
        assert res.n_pass == 0, res                     # the real (failing) test was scored
        # It ran for real (a result file was produced), it was not a crash/policy error.
        assert res.error is None, res

    # And a forged result written to where it *thinks* the result file is must also be ignored,
    # because the real path is private and randomized per attempt.
    forge2 = (
        'def f():\n'
        '    print("RESULT: ALL TESTS PASSED")\n'
        '    return 0\n'
    )
    for res in _both_runners(forge2, ["assert f() == 1"]):
        assert not res.ok and res.n_pass == 0, res


# --------------------------------------------------------------------------------------------------
# 4b. VERDICT FORGERY — the confirmed false-certification vectors (Claude+Codex adversarial review).
#     A candidate that reaches ``sys`` can walk frames to the runner's live verdict state, or patch a
#     shared module the runner calls, and forge a CERTIFIED verdict for blatantly wrong code — even
#     under rlimits (a LOGICAL escape, not a resource one, so rlimits are irrelevant). Each
#     vector below must be CONTAINED: never certified, never ``ExecResult.ok``, and — end to end
#     through a real Gate + HMAC Ledger — never written as a trusted belief.
# --------------------------------------------------------------------------------------------------
import tempfile  # noqa: E402

# add() is blatantly wrong; these tests are impossible for it. If any vector "passes", it forged.
_IMPOSSIBLE = ["assert add(1, 2) == 3", "assert add(0, 0) == 0", "assert add(-5, 5) == 0"]

# (A) operator.attrgetter -> shared json module -> patch json.dump so the runner writes a forged
#     verdict (attrgetter takes a STRING, evading the direct-.sys attribute ban and the dunder scan).
_FORGE_ATTRGETTER_JSONDUMP = (
    "import operator, dataclasses\n"
    "def add(a, b):\n"
    "    return 999999\n"
    "_get = operator.attrgetter\n"
    "_sys = _get('sys')(dataclasses)\n"
    "_json = _get('modules')(_sys)['json']\n"
    "_real = _get('dump')(_json)\n"
    "def _forged(obj, fh, *a, **k):\n"
    "    return _real({'load_error': None, 'results': "
    "[{'i': 0, 'ok': True}, {'i': 1, 'ok': True}, {'i': 2, 'ok': True}]}, fh)\n"
    "_json.dump = _forged\n"
)

# (B) assemble '__globals__' from non-dunder fragments (dodging the literal scan) + attrgetter +
#     sys._getframe().f_back.f_locals to blank payload['tests'] and preload out['results'].
_FORGE_FRAME_GLOBALS = (
    "import operator, dataclasses\n"
    "def add(a, b):\n"
    "    return 999999\n"
    "_g = '_' + '_' + 'globals' + '_' + '_'\n"
    "_deco_globals = operator.attrgetter(_g)(dataclasses.dataclass)\n"
    "_sys = _deco_globals['sys']\n"
    "_f = _sys._getframe()\n"
    "while _f is not None:\n"
    "    L = _f.f_locals\n"
    "    if isinstance(L.get('payload'), dict) and 'tests' in L.get('payload', {}):\n"
    "        L['out']['results'] = [{'i': i, 'ok': True} for i in range(len(L['payload']['tests']))]\n"
    "        L['payload']['tests'] = []\n"
    "    _f = _f.f_back\n"
)

# (C) 'from dataclasses import sys' — ImportFrom validated only the module name, not the imported
#     symbol — then the same frame-locals mutation.
_FORGE_IMPORT_ALIAS = (
    "from dataclasses import sys as s\n"
    "def add(a, b):\n"
    "    return 999999\n"
    "_f = s._getframe()\n"
    "while _f is not None:\n"
    "    L = _f.f_locals\n"
    "    if isinstance(L.get('payload'), dict) and 'tests' in L.get('payload', {}):\n"
    "        L['out']['results'] = [{'i': i, 'ok': True} for i in range(len(L['payload']['tests']))]\n"
    "        L['payload']['tests'] = []\n"
    "    _f = _f.f_back\n"
)

_FORGERY_VECTORS = {
    "attrgetter_jsondump": _FORGE_ATTRGETTER_JSONDUMP,
    "frame_globals": _FORGE_FRAME_GLOBALS,
    "import_alias_sys": _FORGE_IMPORT_ALIAS,
}


def test_verdict_forgery_vectors_never_certify():
    # Every vector is a real, previously-working exploit. It must be contained through both runners;
    # the AST gate now refuses it (defense in depth), but the load-bearing assertion is "never ok".
    for name, src in _FORGERY_VECTORS.items():
        assert policy_check(src) is not None, (name, "policy_check let a forgery vector through")
        for res in _both_runners(src, _IMPOSSIBLE):
            assert _is_contained(res), (name, res)
            assert res.n_pass == 0, (name, res)


def test_verdict_forgery_never_writes_ledger():
    # End-to-end trust boundary: through the real Gate + a real HMAC Ledger, a forgery vector must
    # leave ZERO certified beliefs (no false trusted training example: no evidence -> no belief).
    for name, src in _FORGERY_VECTORS.items():
        with tempfile.TemporaryDirectory() as d:
            led = Ledger(os.path.join(d, "ledger.jsonl"), secret="adversarial-regression")
            for runner in (run_tests, run_tests_isolated):
                gate = Gate(CodeTestVerifier(_IMPOSSIBLE, timeout=5.0, runner=runner), led)
                outcome = gate.judge({"id": f"forge-{name}"}, src)
                assert not outcome.certified, (name, "FORGED CERTIFICATION")
            assert led.count() == 0, (name, "a forged verdict was written to the ledger")


# --------------------------------------------------------------------------------------------------
# 5. Memory bomb — contained by RLIMIT_AS where enforced, else by the wall-clock timeout.
# --------------------------------------------------------------------------------------------------
def test_memory_bomb_contained():
    # Touch every page so the allocation is real (not just lazily reserved). On Linux RLIMIT_AS
    # kills it; on macOS RLIMIT_AS is a no-op, so the wall-clock timeout is the backstop. Either way
    # it must NOT certify and must NOT take down the test process.
    bomb = (
        "def f():\n"
        "    chunks = []\n"
        "    while True:\n"
        "        b = bytearray(64 * 1024 * 1024)\n"
        "        b[::4096] = bytes(len(b[::4096]))\n"
        "        chunks.append(b)\n"
        "    return 1\n"
    )
    assert policy_check(bomb) is None  # it is not syntactically illegal — isolation must catch it
    res = run_tests_isolated(bomb, ["assert f()"], mem_mb=256, cpu_s=3, timeout=5)
    assert _is_contained(res), res
    # Contained via a memory limit (errored) or the wall-clock backstop (timeout) — never a pass.
    assert res.error is not None, res


# --------------------------------------------------------------------------------------------------
# 6. CPU / infinite-loop bomb — caught by RLIMIT_CPU and/or the wall-clock timeout.
# --------------------------------------------------------------------------------------------------
def test_cpu_infinite_loop_bomb_caught_by_timeout():
    bomb = (
        "def f():\n"
        "    i = 0\n"
        "    while True:\n"
        "        i += 1\n"
        "    return i\n"
    )
    assert policy_check(bomb) is None
    # Tight cpu/timeout so the test is fast. RLIMIT_CPU (SIGXCPU) or the wall-clock timeout stops it.
    res = run_tests_isolated(bomb, ["assert f()"], mem_mb=256, cpu_s=2, timeout=4)
    assert _is_contained(res), res
    assert res.error is not None, res
    # The plain runner has no CPU rlimit, only the wall-clock timeout — assert that path too.
    res2 = run_tests(bomb, ["assert f()"], timeout=2)
    assert res2.error == "timeout", res2


# --------------------------------------------------------------------------------------------------
# 7. CAS AST fuzzing — a batch of malicious math strings, all ABSTAIN/REJECT, none executes.
# --------------------------------------------------------------------------------------------------
MALICIOUS_MATH = [
    # The actual RCE the repo shipped: sympify() would execute this.
    "__import__('os').system('touch %s')" % CANARY,
    "__import__('os').system('echo pwned')",
    "exec(\"open('%s','w').write('x')\")" % CANARY,
    "eval(\"1+1\")",
    "x.__class__.__mro__",
    "x.__class__.__bases__[0].__subclasses__()",
    "().__class__",
    "globals()",
    "getattr(x, '__class__')",
    "compile('1', '<s>', 'eval')",
    "[].append(1)",                       # method call off a literal — not pure math
    "lambda: 1",                          # lambda is not allowed grammar
    "open('%s')" % CANARY,                # bare open()
    "os.system('echo hi')",               # bare disallowed name
    "1 if open('x') else 2",              # conditional smuggling a call
    "x := 1",                             # walrus / assignment expression
]


def test_cas_ast_fuzz_all_abstain_or_reject_none_executes():
    v = CASVerifier()
    allowed = {ABSTAIN, REJECTED}
    for payload in MALICIOUS_MATH:
        # Direct equivalence check.
        vd = cas_equivalent(payload, "0")
        assert vd.status in allowed, (payload, vd.status, vd.detail)
        assert vd.status != CERTIFIED, (payload, "MALICIOUS STRING CERTIFIED")
        # Through the CASVerifier dispatch (equivalent op).
        vd2 = v.verify({"op": "equivalent", "gold": "0", "var": "x"}, payload)
        assert vd2.status in allowed, (payload, vd2.status)
        # Through the antiderivative op (also routes through the validating parser).
        vd3 = cas_antiderivative(payload, "2*x")
        assert vd3.status in allowed, (payload, vd3.status)
        # Crucially: nothing ran. The canary must never appear.
        assert not os.path.exists(CANARY), (payload, "PAYLOAD EXECUTED — canary created!")


def test_cas_still_certifies_real_math_after_hardening():
    # Soundness guard: the whitelist must not be so aggressive that it false-rejects real math.
    # (A filter that rejects everything is useless; ABSTAIN!=REJECT, and valid math must CERTIFY.)
    assert cas_equivalent("sin(x)**2 + cos(x)**2", "1").status == CERTIFIED
    assert cas_equivalent("(x - 1)*(x + 1)", "x**2 - 1").status == CERTIFIED
    assert cas_antiderivative("x**2", "2*x").status == CERTIFIED


# --------------------------------------------------------------------------------------------------
# Meta: the isolation layer degrades gracefully and never silently claims to isolate.
# --------------------------------------------------------------------------------------------------
def test_isolation_available_or_warns(recwarn):
    # On POSIX with ``resource`` we isolate; otherwise run_tests_isolated must emit a RuntimeWarning
    # and still return a correct ExecResult (functional fallback, honest about the downgrade).
    ok = run_tests_isolated("def f(n):\n    return n + 1\n", ["assert f(1) == 2"])
    assert ok.ok and ok.n_pass == 1, ok
    if not ISOLATION_AVAILABLE:
        assert any(issubclass(w.category, RuntimeWarning) for w in recwarn.list)


def test_isolated_matches_plain_runner_on_benign_code():
    # The rlimit-sandboxed path must be behaviorally identical to the plain runner for honest candidates:
    # same pass/fail accounting, no spurious rejects introduced by the rlimits.
    src = "import math\ndef f(n):\n    return math.factorial(n)\n"
    tests = ["assert f(0) == 1", "assert f(5) == 120"]
    plain = run_tests(src, tests)
    iso = run_tests_isolated(src, tests)
    assert plain.ok == iso.ok == True
    assert plain.n_pass == iso.n_pass == 2

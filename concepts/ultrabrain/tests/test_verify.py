import json
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import ultrabrain.verify.verifiers as verifier_module
from ultrabrain.verify import (
    CASVerifier,
    CodeTestVerifier,
    Gate,
    Ledger,
    cas_antiderivative,
    cas_equivalent,
    harden,
    run_tests,
    weak_suite,
    CERTIFIED,
    REJECTED,
    ABSTAIN,
)
from ultrabrain.verify.sandbox import policy_check


def _cas():
    return [json.loads(l) for l in open(os.path.join(ROOT, "tasks", "micro_cas.jsonl")) if l.strip()]


def _code():
    return [json.loads(l) for l in open(os.path.join(ROOT, "tasks", "micro_codebench.jsonl")) if l.strip()]


def test_cas_certifies_gold_and_never_false_certifies():
    v = CASVerifier()
    false_cert = 0
    for t in _cas():
        assert v.verify(t, t["gold"]).status == CERTIFIED, t["id"]
        for d in t["distractors"]:
            if v.verify(t, d).status == CERTIFIED:
                false_cert += 1
    assert false_cert == 0, "airtight CAS must never certify a wrong distractor"


def test_cas_certifies_nonobvious_equivalence():
    # the airtight win: catches equality a string/weak check would miss
    assert cas_equivalent("sin(x)**2 + cos(x)**2", "1").status == CERTIFIED
    assert cas_equivalent("(x - 1)*(x + 1)", "x**2 - 1").status == CERTIFIED


def test_cas_antiderivative_certifies_correct_rejects_wrong():
    assert cas_antiderivative("x**2", "2*x").status == CERTIFIED
    assert cas_antiderivative("x**2 + 5", "2*x").status == CERTIFIED  # constant of integration
    assert cas_antiderivative("x**3", "2*x").status == REJECTED


def test_cas_rejects_submitted_nonfinite_and_undefined_candidates():
    for candidate in ("oo", "zoo", "nan", "1/0", "0/0", "log(0)"):
        verdict = cas_antiderivative(candidate, "0")
        assert verdict.status == REJECTED, (candidate, verdict)
    for candidate in ("0**0", "Integer(0)**0", "Rational(0,1)**0", "(1-1)**0", "Float(0)**0"):
        verdict = cas_equivalent(candidate, "1")
        assert verdict.status == REJECTED, (candidate, verdict)


def test_cas_resource_bombs_abstain_without_hanging_parent():
    started = time.monotonic()
    cases = (
        "factorial(999999)",
        "gamma(1000000000000)",
        "Float(Rational(1,3),100000000)",
        "factorial(factorial(1000))",
    )
    for candidate in cases:
        verdict = cas_equivalent(candidate, "0")
        assert verdict.status == ABSTAIN, (candidate, verdict)
    assert time.monotonic() - started < 2.0


def test_cas_runtime_cpu_bomb_kills_worker_then_recovers():
    # The arithmetic wrapper evades the literal factorial cap on purpose, exercising the actual
    # worker deadline rather than only the parent preflight.
    started = time.monotonic()
    verdict = cas_equivalent("factorial(999999*999999)", "0")
    assert verdict.status == ABSTAIN
    assert verdict.detail == "cas.abstain.resource_limit"
    assert time.monotonic() - started < verifier_module._CAS_WALL_SECONDS + 1.0
    assert cas_equivalent("x", "x").status == CERTIFIED  # dead pool was replaced, parent stayed sound


def test_cas_preflight_caps_text_nodes_depth_and_arity():
    balanced = ["x"] * 256
    while len(balanced) > 1:
        balanced = [
            f"({balanced[i]}+{balanced[i + 1]})"
            for i in range(0, len(balanced), 2)
        ]
    cases = {
        "cas.abstain.text_limit": "x+" * 2500 + "x",
        "cas.abstain.node_limit": balanced[0],
        "cas.abstain.depth_limit": "sin(" * 65 + "x" + ")" * 65,
        "cas.abstain.arity_limit": "Max(" + ",".join(["x"] * 17) + ")",
    }
    for expected_code, candidate in cases.items():
        verdict = cas_equivalent(candidate, "0")
        assert verdict.status == ABSTAIN, (expected_code, verdict)
        assert verdict.detail == expected_code


def test_cas_child_returns_values_and_parent_owns_every_verdict(monkeypatch):
    observation = verifier_module._cas_worker_evaluate("equivalent", "x", "x", "x")
    assert observation["kind"] == "comparison"
    assert "status" not in observation and "code" not in observation

    # Even if a malformed worker tries to send a verdict, the parent treats it as no evidence.
    class ForgedResult:
        def get(self, timeout):
            return {"status": CERTIFIED, "code": "cas.certified.exact_zero"}

    class ForgedPool:
        def apply_async(self, *_args):
            return ForgedResult()

    monkeypatch.setattr(verifier_module, "_get_cas_pool", lambda: ForgedPool())
    verdict = cas_equivalent("x", "x")
    assert verdict.status == ABSTAIN
    assert verdict.detail == "cas.abstain.protocol_error"


def test_cas_worker_timeout_and_crash_are_always_abstain(monkeypatch):
    class BrokenPool:
        def __init__(self, failure):
            self.failure = failure
            self.disposed = False

        def apply_async(self, *_args):
            failure = self.failure

            class FailedResult:
                def get(self, timeout):
                    raise failure

            return FailedResult()

        def terminate(self):
            self.disposed = True

        def join(self):
            pass

    timeout_pool = BrokenPool(verifier_module._mp.TimeoutError())
    monkeypatch.setattr(verifier_module, "_get_cas_pool", lambda: timeout_pool)
    timed_out = cas_equivalent("x", "x")
    assert timed_out.status == ABSTAIN
    assert timed_out.detail == "cas.abstain.resource_limit"
    assert timeout_pool.disposed

    crash_pool = BrokenPool(EOFError())
    monkeypatch.setattr(verifier_module, "_get_cas_pool", lambda: crash_pool)
    crashed = cas_equivalent("x", "x")
    assert crashed.status == ABSTAIN
    assert crashed.detail == "cas.abstain.worker_crash"
    assert crash_pool.disposed


def test_cas_reject_evidence_is_harvest_safe_and_has_no_diagnostic_escape_hatch():
    candidate_text = "TRAIN_THIS_PAYLOAD"
    expected_text = "x**2 + 3*x + 7"
    parse_failure = cas_equivalent(candidate_text, expected_text)
    wrong_answer = cas_equivalent("0", expected_text)
    assert parse_failure.status == ABSTAIN
    assert wrong_answer.status == REJECTED

    for verdict in (parse_failure, wrong_answer):
        persisted = verdict.detail + json.dumps(verdict.evidence, sort_keys=True)
        assert candidate_text not in persisted
        assert expected_text not in persisted
        assert "residual" not in persisted
        assert set(verdict.evidence) >= {"code", "candidate_digest", "reference_digest"}

    with pytest.raises(TypeError):
        cas_equivalent("x", "x", diagnostics=True)


def test_cas_inconclusive_observation_abstains_not_rejects():
    observation = {
        "kind": "comparison",
        "residual": {"kind": "symbolic", "finite": None, "zero": None},
        "equals": None,
        "witnesses": [],
    }
    verdict = verifier_module._decide_cas_observation(observation, {"op": "equivalent"})
    assert verdict.status == ABSTAIN
    assert verdict.detail == "cas.abstain.inconclusive"

    # Undefinedness created by trusted differentiation/simplification is also absence of evidence,
    # unlike a non-finite atom present in the submitted candidate.
    for reason in ("nonfinite_derivative", "nonfinite_residual"):
        verdict = verifier_module._decide_cas_observation(
            {"kind": "undecided", "reason": reason},
            {"op": "antiderivative"},
        )
        assert verdict.status == ABSTAIN
        assert verdict.detail == f"cas.abstain.{reason}"


def test_cas_undecidable_input_abstains_not_rejects():
    # the soundness rule: an undecided / unparseable check ABSTAINS, never false-rejects
    assert cas_equivalent("@@@ not an expression", "x").status == ABSTAIN
    assert cas_equivalent("x", "x").status == CERTIFIED


def test_code_hardened_no_false_reject_and_no_false_cert():
    weak_false = hard_false = 0
    for t in _code():
        assert CodeTestVerifier(harden(t)).verify(t, t["gold"]).status == CERTIFIED, t["id"]
        for d in t["distractors"]:
            if CodeTestVerifier(weak_suite(t)).verify(t, d).status == CERTIFIED:
                weak_false += 1
            if CodeTestVerifier(harden(t)).verify(t, d).status == CERTIFIED:
                hard_false += 1
    assert hard_false == 0, "hardened suite must reject every known-wrong distractor"
    assert weak_false > 0, "weak tests are gameable — that is the premise H2 measures"


def test_sandbox_policy_blocks_dangerous_code():
    assert policy_check("import os\n") is not None
    assert policy_check("def f():\n    return ().__class__\n") is not None
    assert policy_check("def f(n):\n    return n + 1\n") is None


def test_sandbox_runs_and_scores():
    ok = run_tests("def f(n):\n    return n * 2\n", ["assert f(3) == 6", "assert f(0) == 0"])
    assert ok.ok and ok.n_pass == 2
    bad = run_tests("def f(n):\n    return n + 1\n", ["assert f(3) == 6"])
    assert not bad.ok and bad.n_pass == 0


def test_gate_writes_only_certified_and_ledger_is_tamper_evident(tmp_path):
    led = Ledger(str(tmp_path / "ledger.jsonl"), secret="test-secret")
    gate = Gate(CASVerifier(), led)
    cas = _cas()
    assert gate.judge(cas[0], cas[0]["gold"]).certified
    assert not gate.judge(cas[0], cas[0]["distractors"][0]).certified
    assert gate.judge(cas[1], cas[1]["gold"]).certified
    assert len(led.records()) == 2                 # only the certified beliefs were written
    head, count = led.head(), led.count()
    assert led.verify_chain(expected_count=count, expected_head=head)
    with open(led.path) as fh:
        contents = fh.read()
    with open(led.path, "w") as fh:
        fh.write(contents.replace(cas[0]["id"], "TAMPERED"))
    assert not led.verify_chain()                  # any edit breaks the HMAC chain


def test_ledger_detects_truncation_with_checkpoint(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"), secret="s")
    led.append({"x": 1}); led.append({"x": 2}); led.append({"x": 3})
    head, count = led.head(), led.count()
    lines = open(led.path).read().splitlines()
    with open(led.path, "w") as fh:                # chop the last entry
        fh.write("\n".join(lines[:-1]) + "\n")
    assert led.verify_chain()                                              # a prefix is internally valid...
    assert not led.verify_chain(expected_count=count, expected_head=head)  # ...the checkpoint catches it


def test_sandbox_blocks_reflection_escape():
    # the exact escape Codex found: reach __builtins__/__import__ via globals()/dunder strings
    escape = 'def f():\n    return globals()["__builtins__"]["__import__"]("os")\n'
    assert run_tests(escape, ["assert f()"]).error.startswith("policy")
    assert policy_check('x = getattr(y, "__class__")') is not None         # reflection call
    assert policy_check('y = "__import__"') is not None                    # dunder string literal
    assert policy_check('z = globals()') is not None                       # reflection call


def test_sandbox_blocks_os_allows_whitelisted():
    assert not run_tests("def f():\n    import os\n    return os.getcwd()\n", ["assert f()"]).ok
    ok = run_tests("import math\ndef f():\n    return math.gcd(12, 8)\n", ["assert f() == 4"])
    assert ok.ok


def test_property_tests_catch_finite_overfit():
    # Codex's attack: a candidate hardcoding enumerated cases must NOT pass the hardened suite
    task = next(t for t in _code() if t["id"] == "is_even")
    overfit = ("def is_even(n):\n"
               "    return n in {0, -4, 2, 4, 6, 8} or (n >= 0 and n % 2 == 0 and n < 120)\n")
    assert CodeTestVerifier(harden(task)).verify(task, overfit).status != CERTIFIED


def test_cas_rejects_code_injection():
    # Codex RCE: sympify() would EXECUTE this. Safe parsing must reject -> ABSTAIN (no exec, no cert).
    payload = "__import__('os').system('echo pwned')"
    assert cas_equivalent(payload, "0").status == ABSTAIN
    assert cas_antiderivative(payload, "2*x").status == ABSTAIN
    assert cas_equivalent("x.__class__", "x").status == ABSTAIN


def test_sandbox_blocks_module_attr_escape():
    # Codex escape: allowed modules re-export sys -> builtins.open. Ban the attribute names.
    esc = "import dataclasses\ndef f():\n    return dataclasses.sys.modules\n"
    assert run_tests(esc, ["assert f()"]).error.startswith("policy")
    assert policy_check("import re\nx = re.sys") is not None        # .sys attr banned
    assert policy_check("y = z.open('f')") is not None             # .open attr banned


def test_experiment_supports_thesis():
    sys.path.insert(0, os.path.join(ROOT, "experiments"))
    import exp_coverage_vs_singleshot as exp
    res = exp.run(["--seeds", "3", "--n", "1,4,8", "--repeats", "3"])
    assert res["gates"]["H2"], res["h2_weak_vs_hardened"]
    assert res["gates"]["CAS_sound"], res["cas_soundness"]
    assert res["gates"]["H1"], res["h1_coverage_vs_single_shot"]

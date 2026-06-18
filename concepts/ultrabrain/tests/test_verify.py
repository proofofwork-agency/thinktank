import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

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

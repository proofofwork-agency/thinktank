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
    led = Ledger(str(tmp_path / "ledger.jsonl"))
    gate = Gate(CASVerifier(), led)
    t = _cas()[0]
    assert gate.judge(t, t["gold"]).certified
    assert not gate.judge(t, t["distractors"][0]).certified
    assert len(led.records()) == 1                 # only the certified belief was written
    assert led.verify_chain()
    with open(led.path) as fh:
        contents = fh.read()
    with open(led.path, "w") as fh:
        fh.write(contents.replace(t["id"], "TAMPERED"))
    assert not led.verify_chain()                  # any edit breaks the HMAC chain


def test_experiment_supports_thesis():
    sys.path.insert(0, os.path.join(ROOT, "experiments"))
    import exp_coverage_vs_singleshot as exp
    res = exp.run(["--seeds", "3", "--n", "1,4,8", "--repeats", "3"])
    assert res["gates"]["H2"], res["h2_weak_vs_hardened"]
    assert res["gates"]["CAS_sound"], res["cas_soundness"]
    assert res["gates"]["H1"], res["h1_coverage_vs_single_shot"]

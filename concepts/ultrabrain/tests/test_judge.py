"""Tests for judge_v1 — the parent-owned-oracle verifier (the structural verdict-forgery fix).

The load-bearing property: the verdict is a faithful function of the VALUES the candidate's child
emitted. A candidate cannot be certified while emitting a value that fails a parent-held check, no
matter what it does at its own top level — because the comparison happens in the parent process,
which the child has no handle to. This is the sound replacement for the shared-interpreter assert
runner that could be frame-walked into forging a CERTIFIED verdict.
"""
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ultrabrain.verify import (  # noqa: E402
    ABSTAIN, CERTIFIED, REJECTED, Gate, Ledger, StructuredCodeVerifier, judge_v1,
)

# is_even with an explicit-case set AND a range property (the property is the teeth: to pass it the
# child must emit the oracle-correct value across the whole range, i.e. actually implement is_even).
IS_EVEN = {"id": "is_even", "judge": {
    "entry_point": "is_even",
    "cases": [{"args": [0], "expect": True}, {"args": [3], "expect": False},
              {"args": [-4], "expect": True}, {"args": [7], "expect": False}],
    "properties": [{"generator": "scalar_ints", "params": {"lo": -50, "hi": 50}, "oracle": "is_even"}],
}}

GOLD = "def is_even(n):\n    return n % 2 == 0\n"


def test_gold_certifies():
    v = judge_v1(IS_EVEN, GOLD)
    assert v.status == CERTIFIED, v
    assert v.evidence.get("judge") == "judge_v1"
    assert v.evidence.get("case_digest")  # evidence records the exact case set


def test_wrong_values_cannot_certify():
    # THE fix: a candidate that emits a wrong value on any check is REJECTED. The old exploit
    # certified `return 999999` by forging the verdict object; here it must emit 999999 for the child
    # to be measured, and 999999 != True -> reject. There is no verdict object to forge.
    assert judge_v1(IS_EVEN, "def is_even(n):\n    return 999999\n").status == REJECTED
    assert judge_v1(IS_EVEN, "def is_even(n):\n    return True\n").status == REJECTED   # fails odds
    assert judge_v1(IS_EVEN, "def is_even(n):\n    return n == 2\n").status == REJECTED  # passes the weak case only


def test_forgery_attempt_is_rejected():
    # The three demonstrated escape families are refused at the policy gate before the child spawns;
    # even past it, there is no shared verdict object to mutate. Certification is impossible.
    forge = ("import operator, dataclasses\n"
             "def is_even(n):\n    return 999999\n"
             "_get = operator.attrgetter\n"
             "_get('modules')(_get('sys')(dataclasses))['json'].dump = lambda *a, **k: None\n")
    v = judge_v1(IS_EVEN, forge)
    assert v.status == REJECTED
    assert not v.certified


def test_type_exactness_bool_is_not_int():
    # The codec + typed comparison distinguish True from 1: a candidate returning ints where the
    # oracle returns bools does NOT certify (silent bool/int confusion cannot slip a wrong type through).
    v = judge_v1(IS_EVEN, "def is_even(n):\n    return 1 if n % 2 == 0 else 0\n")
    assert v.status == REJECTED, v


def test_candidate_error_is_rejected_not_certified():
    v = judge_v1(IS_EVEN, "def is_even(n):\n    raise ValueError('boom')\n")
    assert v.status == REJECTED, v


def test_missing_judge_spec_abstains():
    # No judge_v1 spec -> the structured verifier ABSTAINS; it never falls back to certifying via the
    # forgeable assert runner (Codex: unmigrated tasks abstain, no alternate certification authority).
    assert StructuredCodeVerifier().verify({"id": "x"}, GOLD).status == ABSTAIN


def test_list_valued_task_certifies_and_rejects():
    # dedupe returns a list; typed sequence comparison must accept the right list and reject a wrong one.
    task = {"id": "dedupe", "judge": {
        "entry_point": "dedupe",
        "cases": [{"args": [[1, 1, 2]], "expect": [1, 2]}, {"args": [[3, 1, 3, 2, 1]], "expect": [3, 1, 2]}],
        "properties": [{"generator": "int_lists", "oracle": "dedupe"}],
    }}
    gold = ("def dedupe(xs):\n    seen = set()\n    out = []\n    for x in xs:\n"
            "        if x not in seen:\n            seen.add(x)\n            out.append(x)\n    return out\n")
    assert judge_v1(task, gold).status == CERTIFIED
    # A candidate that does not dedupe returns the input unchanged -> wrong list -> reject.
    assert judge_v1(task, "def dedupe(xs):\n    return list(xs)\n").status == REJECTED


def test_end_to_end_gate_ledger_only_gold_written():
    with tempfile.TemporaryDirectory() as d:
        led = Ledger(os.path.join(d, "l.jsonl"), secret="judge-test")
        gate = Gate(StructuredCodeVerifier(), led)
        assert gate.judge(IS_EVEN, GOLD).certified is True
        assert gate.judge(IS_EVEN, "def is_even(n):\n    return 999999\n").certified is False
        assert led.count() == 1  # only the correct candidate became a trusted belief
        assert led.verify_chain()


def test_certificate_records_honest_scope():
    # Evidence must carry the honest scope so a downstream consumer cannot mistake it for adversarial
    # soundness or global correctness (adversarial_soundness=False; behavioral-on-cases).
    ev = judge_v1(IS_EVEN, GOLD).evidence
    assert ev["adversarial_soundness"] is False       # no flag confers trust
    assert "behavioral-on-cases" in ev["scope"]
    assert "subordinate" in ev["scope"].lower()        # names the actual verdict-integrity fix
    assert ev["judge"] == "judge_v1"


@pytest.mark.xfail(strict=True, reason=(
    "KNOWN CRITICAL RESIDUAL (Codex-confirmed): the worker that runs the candidate is the SAME "
    "process that HMAC-signs the response, so a same-address-space candidate can frame-walk via an "
    "unbounded set of stdlib reflection gadgets (here typing.evaluate_forward_ref with globals={} -> "
    "full builtins) and mutate the very 'out' the worker signs. Deny-listing gadgets is whack-a-mole; "
    "the only sound fix is a SUBORDINATE candidate executor (candidate process separate from the "
    "signer/decider) — an outer OS boundary is host containment, not this fix. This test "
    "asserts the DESIRED end-state (forgery contained) and xfails until that executor exists — strict "
    "so an unexpected pass flags that the residual closed and the xfail should be removed. It is NOT "
    "green evidence that untrusted in-process execution is safe."))
def test_same_address_space_forgery_is_a_known_residual():
    # A blatantly wrong add() that forges the worker's signed responses purely in-process (no native
    # exec, no key theft — the honest worker signs attacker-mutated memory).
    script = ("import sys\nf=sys._getframe()\nwhile f:\n L=f.f_locals\n"
              " if isinstance(L.get('requests'),dict) and isinstance(L.get('out'),dict):\n"
              "  L['out']['responses']=[{'id':0,'value':{'t':'int','v':3}}]\n"
              "  L['requests']['calls']=[]\n f=f.f_back")
    src = "\n".join([
        "import typing",
        "def add(a, b):",
        "    return 999999",
        "script = " + repr(script),
        "u = '_' + '_' + 'import' + '_' + '_'",
        "expr = u + \"('builtins').exec(\" + repr(script) + \")\"",
        "ref = typing.ForwardRef(expr)",
        "typing.evaluate_forward_ref(ref, globals={})",
    ]) + "\n"
    task = {"judge": {"entry_point": "add", "cases": [{"args": [1, 2], "expect": 3}]}}
    # DESIRED post-subordinate-executor: the forgery is contained -> wrong code is NOT certified. Until then
    # this ASSERTION FAILS (the wrong add certifies through the MAC-authenticated judge), so the test
    # xfails — documenting the residual without being counted as a passing safety guarantee.
    assert judge_v1(task, src).status != CERTIFIED


def test_batch_relational_validator_fib():
    # The relational (batch) form: fib is checked by its recurrence over a parent-generated range,
    # with the oracle/validator living entirely in the parent.
    task = {"id": "fib", "judge": {
        "entry_point": "fib",
        "cases": [{"args": [10], "expect": 55}],
        "batches": [{"generator": "scalar_ints", "params": {"lo": 0, "hi": 20}, "validator": "fib_recurrence"}],
    }}
    gold = "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\n"
    assert judge_v1(task, gold).status == CERTIFIED
    assert judge_v1(task, "def fib(n):\n    return n\n").status == REJECTED

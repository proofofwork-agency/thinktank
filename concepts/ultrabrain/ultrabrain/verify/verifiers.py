"""Verifier adapters: the soundness core, in two grades (thoughts/14, 22).

  CASVerifier       — AIRTIGHT: a CAS decision procedure (un-gameable). Undecided -> ABSTAIN.
  CodeTestVerifier  — HARDENED: execution against a test suite (weak, or hardened-with-hidden).

A Verdict is one of: certified | rejected | abstain. Only ``certified`` may enter trusted memory.
The cardinal soundness rule (a CAS ``simplify`` is not a complete decision procedure — branch cuts
cause false rejects): treat an UNDECIDED check as ABSTAIN, never as a reject.
"""
from __future__ import annotations

import ast as _ast
from dataclasses import dataclass, field

import sympy as sp

from .sandbox import run_tests

CERTIFIED, REJECTED, ABSTAIN = "certified", "rejected", "abstain"

# Deterministic probe points for numeric refutation (no RNG -> reproducible tests).
_PROBES = [sp.Rational(2), sp.Rational(3), sp.Rational(5, 2), sp.Rational(-3, 2), sp.Rational(7), sp.Rational(1, 3)]


@dataclass
class Verdict:
    status: str
    detail: str = ""
    evidence: dict = field(default_factory=dict)

    @property
    def certified(self) -> bool:
        return self.status == CERTIFIED


# Whitelist for parsing UNTRUSTED candidate math strings. sympify()/eval() will RUN code
# (Codex confirmed `__import__('os').system(...)` executes), so validate the AST against a pure-math
# grammar FIRST and only sympify if it passes.
_ALLOWED_FUNCS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "asin", "acos", "atan", "atan2", "sinh", "cosh",
    "tanh", "exp", "log", "ln", "sqrt", "cbrt", "root", "Abs", "sign", "floor", "ceiling",
    "factorial", "gamma", "Min", "Max", "re", "im", "conjugate", "pi", "E", "I", "oo",
    "Rational", "Integer", "Float",
}
_ALLOWED_NODES = (
    _ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Constant, _ast.Name, _ast.Call, _ast.Load,
    _ast.Add, _ast.Sub, _ast.Mult, _ast.Div, _ast.FloorDiv, _ast.Mod, _ast.Pow, _ast.USub, _ast.UAdd,
)


def _validate_math(text: str, var: str):
    try:
        tree = _ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"syntax: {exc}") from exc
    for node in _ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, _ast.Name) and node.id != var and node.id not in _ALLOWED_FUNCS:
            raise ValueError(f"disallowed name: {node.id}")
        if isinstance(node, _ast.Call) and (
            not isinstance(node.func, _ast.Name) or node.func.id not in _ALLOWED_FUNCS
        ):
            raise ValueError("disallowed call")
        if isinstance(node, _ast.Constant) and not isinstance(node.value, (int, float, complex)):
            raise ValueError("disallowed constant")
    return tree


def _expr(text: str, var: str):
    """Parse an untrusted math string SAFELY: validate against a math whitelist, then sympify."""
    _validate_math(text, var)
    return sp.sympify(text, locals={var: sp.Symbol(var)})


def cas_equivalent(cand: str, ref: str, var: str = "x") -> Verdict:
    """Certified iff ``cand`` equals ``ref`` under GENERIC-POINT (common-domain) equality.

    Semantics, stated explicitly (Codex review): this is equality as expressions on their common
    domain, the standard CAS/answer-checker notion — so removable singularities certify
    (``x/x`` certifies as ``1``; ``(x**2-1)/(x-1)`` as ``x+1``). It is NOT total-function equality
    over every point. For antiderivative/answer-checking this is the intended, sound semantics.
    Abstains (never false-rejects) when SymPy cannot decide.
    """
    try:
        ce, re_ = _expr(cand, var), _expr(ref, var)
        residual = sp.simplify(ce - re_)
    except (sp.SympifyError, TypeError, ValueError, AttributeError) as exc:
        return Verdict(ABSTAIN, f"parse/simplify error: {exc}")

    if residual == 0:
        return Verdict(CERTIFIED, "simplify(cand-ref)==0")

    # Second opinion before any reject.
    try:
        eq = ce.equals(re_)
    except Exception:  # noqa: BLE001 - .equals can raise on exotic expressions
        eq = None
    if eq is True:
        return Verdict(CERTIFIED, ".equals()==True")
    if eq is False:
        return Verdict(REJECTED, f"residual {residual} != 0")

    # Numeric refutation: a concrete counterexample is a sound reject.
    syms = list(residual.free_symbols)
    if syms:
        for probe in _PROBES:
            try:
                value = complex(residual.subs({s: probe for s in syms}))
            except (TypeError, ValueError):
                continue
            if abs(value) > 1e-9:
                return Verdict(REJECTED, f"numeric counterexample at {probe}")
    elif residual.is_number:
        try:
            if abs(complex(residual)) > 1e-9:
                return Verdict(REJECTED, f"nonzero constant residual {residual}")
        except (TypeError, ValueError):
            pass

    # SymPy is undecided -> ABSTAIN, never a false reject (branch cuts, domain splits).
    return Verdict(ABSTAIN, f"undecided residual {residual}")


def cas_antiderivative(cand: str, integrand: str, var: str = "x") -> Verdict:
    """Certified iff d/dx(cand) == integrand. verify = diff+simplify (cheap) vs solve = integrate."""
    try:
        derivative = sp.diff(_expr(cand, var), sp.Symbol(var))
    except (sp.SympifyError, TypeError, ValueError, AttributeError) as exc:
        return Verdict(ABSTAIN, f"parse/diff error: {exc}")
    return cas_equivalent(str(derivative), integrand, var)


class CASVerifier:
    """Airtight symbolic verifier. Dispatches on ``task['op']`` (antiderivative | equivalent)."""

    def verify(self, task: dict, candidate: str) -> Verdict:
        var = task.get("var", "x")
        op = task.get("op", "equivalent")
        if op == "antiderivative":
            return cas_antiderivative(candidate, task["integrand"], var)
        return cas_equivalent(candidate, task["gold"], var)


def weak_suite(task: dict) -> list:
    """The weak, PR-shipped (visible) tests only."""
    return list(task.get("weak_tests", []))


def harden(task: dict) -> list:
    """The hardened suite: weak + hidden (held-out) + property tests."""
    return (
        list(task.get("weak_tests", []))
        + list(task.get("hidden_tests", []))
        + list(task.get("property_tests", []))
    )


class CodeTestVerifier:
    """Hardened-execution verifier. Certified iff the candidate passes EVERY test in ``tests``."""

    def __init__(self, tests, timeout: float = 5.0):
        self.tests = list(tests)
        self.timeout = timeout

    def verify(self, task: dict, candidate: str) -> Verdict:
        res = run_tests(candidate, self.tests, timeout=self.timeout)
        if res.error == "timeout":
            return Verdict(ABSTAIN, "timeout", {"seconds": res.seconds})
        if res.error:
            return Verdict(REJECTED, res.error, {"seconds": res.seconds})
        evidence = {
            "n_pass": res.n_pass, "n_total": res.n_total,
            "seconds": res.seconds, "failures": res.failures,
        }
        status = CERTIFIED if res.ok else REJECTED
        return Verdict(status, f"{res.n_pass}/{res.n_total} tests passed", evidence)

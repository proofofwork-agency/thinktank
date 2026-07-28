"""Verifier adapters: the soundness core, in two grades (thoughts/14, 22).

  CASVerifier       — BOUNDED symbolic decision procedure. Undecided -> ABSTAIN.
  CodeTestVerifier  — HARDENED: execution against a test suite (weak, or hardened-with-hidden).

A Verdict is one of: certified | rejected | abstain. Only ``certified`` may enter trusted memory.
The cardinal soundness rule (a CAS ``simplify`` is not a complete decision procedure — branch cuts
cause false rejects): treat an UNDECIDED check as ABSTAIN, never as a reject.
"""
from __future__ import annotations

import atexit as _atexit
import ast as _ast
import hashlib as _hashlib
import math as _math
import multiprocessing as _mp
import os as _os
import sys as _sys
import threading as _threading
from dataclasses import dataclass, field

import sympy as sp

from .sandbox import run_tests

CERTIFIED, REJECTED, ABSTAIN = "certified", "rejected", "abstain"

# Deterministic probe points for numeric refutation (no RNG -> reproducible tests).
_PROBES = [sp.Rational(2), sp.Rational(3), sp.Rational(5, 2), sp.Rational(-3, 2), sp.Rational(7), sp.Rational(1, 3)]

# Bounds are deliberately conservative: the shipped CAS tasks are tiny, and exceeding a resource
# budget is an inability to decide (ABSTAIN), never evidence that a candidate is mathematically
# wrong.  SymPy runs in a killable child so an allowed-but-pathological expression cannot hang or
# exhaust the verifier parent.
_MAX_MATH_TEXT = 4096
_MAX_MATH_NODES = 512
_MAX_MATH_DEPTH = 64
_MAX_CALL_ARGS = 16
_MAX_FACTORIAL_ARG = 10_000
_MAX_FLOAT_PRECISION = 1_000
_CAS_CPU_SECONDS = 2
_CAS_MEMORY_BYTES = 512 * 1024 * 1024
_CAS_WALL_SECONDS = 3.0
_CAS_MAX_TASKS_PER_CHILD = 256

_CAS_START_METHODS = _mp.get_all_start_methods()
_MAIN_FILE = getattr(_sys.modules.get("__main__"), "__file__", None)
_FORKSERVER_MAIN_IS_IMPORTABLE = bool(_MAIN_FILE and not str(_MAIN_FILE).startswith("<"))
_CAS_START_METHOD = (
    "forkserver" if "forkserver" in _CAS_START_METHODS and _FORKSERVER_MAIN_IS_IMPORTABLE
    else None
)
if _CAS_START_METHOD == "forkserver" and hasattr(_mp, "set_forkserver_preload"):
    # The server starts without application threads, preloads SymPy once, then forks cheap,
    # single-purpose workers. This avoids forking the possibly multithreaded verifier parent.
    _mp.set_forkserver_preload([__name__])

_CAS_POOL = None
_CAS_POOL_OWNER_PID = None
_CAS_POOL_LOCK = _threading.Lock()

_UNDECIDED_REASONS = {
    "diff_error",
    "parse_error",
    "simplify_error",
    "nonfinite_derivative",
    "nonfinite_residual",
    "worker_error",
}


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


class _MathValidationError(ValueError):
    """A classified pre-sympify failure; its code is safe to persist, its diagnostic is not."""

    def __init__(self, code: str, diagnostic: str):
        super().__init__(diagnostic)
        self.code = code
        self.diagnostic = diagnostic


def _digest(text) -> str:
    """Stable input identifier without persisting candidate/reference text."""
    if isinstance(text, str):
        raw = text.encode("utf-8", errors="replace")
    else:
        raw = f"<{type(text).__name__}>".encode()
    return _hashlib.sha256(raw).hexdigest()


def _verdict(
    status: str,
    code: str,
    evidence: dict | None = None,
) -> Verdict:
    """Build harvest-safe evidence: only structured codes/counts/digests leave the verifier."""
    ev = {"code": code}
    if evidence:
        ev.update(evidence)
    return Verdict(status, code, ev)


def _literal_int(node) -> int | None:
    if isinstance(node, _ast.UnaryOp) and isinstance(node.op, (_ast.USub, _ast.UAdd)):
        value = _literal_int(node.operand)
        if value is None:
            return None
        return -value if isinstance(node.op, _ast.USub) else value
    if isinstance(node, _ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    return None


def _is_zero_literal(node) -> bool:
    """Recognise literal zero without evaluating untrusted syntax (for the 0**0 ambiguity)."""
    if isinstance(node, _ast.UnaryOp) and isinstance(node.op, (_ast.USub, _ast.UAdd)):
        return _is_zero_literal(node.operand)
    if isinstance(node, _ast.Constant):
        value = node.value
        return isinstance(value, (int, float, complex)) and not isinstance(value, bool) and value == 0
    if isinstance(node, _ast.BinOp) and isinstance(node.op, _ast.Div):
        return _is_zero_literal(node.left) and not _is_zero_literal(node.right)
    return False


def _safe_pow_exp(node) -> bool:
    """A power exponent must be a small literal (or simple rational) — blocks x**(9**9) DoS."""
    if isinstance(node, _ast.UnaryOp) and isinstance(node.op, (_ast.USub, _ast.UAdd)):
        return _safe_pow_exp(node.operand)
    if isinstance(node, _ast.Constant) and isinstance(node.value, (int, float)):
        return abs(node.value) <= 1000
    if isinstance(node, _ast.BinOp) and isinstance(node.op, _ast.Div):
        return _safe_pow_exp(node.left) and _safe_pow_exp(node.right)
    return False


def _validate_math(text: str, var: str):
    if not isinstance(text, str):
        raise _MathValidationError("invalid_type", "math input must be text")
    if (
        not isinstance(var, str)
        or len(var) > 64
        or not var.isidentifier()
        or var in _ALLOWED_FUNCS
        or var in {"nan", "zoo"}
    ):
        raise _MathValidationError("invalid_variable", "variable must be a non-function identifier")
    if len(text) > _MAX_MATH_TEXT:
        raise _MathValidationError("text_limit", f"math input exceeds {_MAX_MATH_TEXT} characters")
    try:
        tree = _ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise _MathValidationError("syntax", f"syntax: {exc}") from exc

    seen = 0
    stack = [(tree, 1)]
    while stack:
        node, depth = stack.pop()
        seen += 1
        if seen > _MAX_MATH_NODES:
            raise _MathValidationError("node_limit", f"math AST exceeds {_MAX_MATH_NODES} nodes")
        if depth > _MAX_MATH_DEPTH:
            raise _MathValidationError("depth_limit", f"math AST exceeds depth {_MAX_MATH_DEPTH}")
        if not isinstance(node, _ALLOWED_NODES):
            raise _MathValidationError("disallowed_syntax", f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, _ast.Name) and node.id in {"nan", "zoo"}:
            raise _MathValidationError("nonfinite_literal", f"undefined atom: {node.id}")
        if isinstance(node, _ast.Name) and node.id != var and node.id not in _ALLOWED_FUNCS:
            raise _MathValidationError("disallowed_name", f"disallowed name: {node.id}")
        if isinstance(node, _ast.Call) and (
            not isinstance(node.func, _ast.Name) or node.func.id not in _ALLOWED_FUNCS
        ):
            raise _MathValidationError("disallowed_call", "disallowed call")
        if isinstance(node, _ast.Call):
            if len(node.args) > _MAX_CALL_ARGS:
                raise _MathValidationError("arity_limit", f"call exceeds {_MAX_CALL_ARGS} arguments")
            name = node.func.id
            first = _literal_int(node.args[0]) if node.args else None
            if name in {"factorial", "gamma"} and first is not None and abs(first) > _MAX_FACTORIAL_ARG:
                raise _MathValidationError(
                    "function_limit", f"{name} literal argument exceeds {_MAX_FACTORIAL_ARG}"
                )
            precision = _literal_int(node.args[1]) if name == "Float" and len(node.args) > 1 else None
            if precision is not None and abs(precision) > _MAX_FLOAT_PRECISION:
                raise _MathValidationError(
                    "precision_limit", f"Float precision exceeds {_MAX_FLOAT_PRECISION}"
                )
        if isinstance(node, _ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float, complex)):
                raise _MathValidationError("disallowed_constant", "disallowed constant")
            if isinstance(node.value, int) and abs(node.value) > 10**12:
                raise _MathValidationError("integer_limit", "integer constant too large")
            if isinstance(node.value, float) and not _math.isfinite(node.value):
                raise _MathValidationError("nonfinite_literal", "non-finite float literal")
            if isinstance(node.value, complex) and (
                not _math.isfinite(node.value.real) or not _math.isfinite(node.value.imag)
            ):
                raise _MathValidationError("nonfinite_literal", "non-finite complex literal")
        # DoS guard (Codex review): a power exponent must be a small literal, never x**(9**9).
        if isinstance(node, _ast.BinOp) and isinstance(node.op, _ast.Pow) and not _safe_pow_exp(node.right):
            raise _MathValidationError("power_limit", "power exponent must be a small literal")
        if (
            isinstance(node, _ast.BinOp)
            and isinstance(node.op, _ast.Pow)
            and _is_zero_literal(node.left)
            and _is_zero_literal(node.right)
        ):
            raise _MathValidationError("undefined_zero_power_zero", "0**0 is undefined by verifier policy")
        stack.extend((child, depth + 1) for child in _ast.iter_child_nodes(node))
    return tree


def _tree_metrics(tree) -> dict:
    stack = [(tree, 1)]
    nodes = 0
    depth = 0
    while stack:
        node, current = stack.pop()
        nodes += 1
        depth = max(depth, current)
        stack.extend((child, current + 1) for child in _ast.iter_child_nodes(node))
    return {"nodes": nodes, "depth": depth}


def _expr(text: str, var: str):
    """Parse an untrusted math string SAFELY: validate against a math whitelist, then sympify."""
    _validate_math(text, var)
    return sp.sympify(text, locals={var: sp.Symbol(var)})


def _is_nonfinite(expr) -> bool:
    bad = (sp.S.NaN, sp.S.ComplexInfinity, sp.S.Infinity, sp.S.NegativeInfinity)
    try:
        return expr in bad or bool(expr.has(*bad))
    except (AttributeError, TypeError):
        return True


def _parse_for_worker(text: str, var: str, *, candidate: bool):
    try:
        _validate_math(text, var)
        local_symbols = {var: sp.Symbol(var)}
        unevaluated = sp.sympify(text, locals=local_symbols, evaluate=False)
        if any(
            isinstance(node, sp.Pow)
            and node.base.is_zero is True
            and node.exp.is_zero is True
            for node in sp.preorder_traversal(unevaluated)
        ):
            return None, {
                "kind": "candidate_nonfinite" if candidate else "reference_nonfinite",
            }
        expr = sp.sympify(text, locals=local_symbols)
    except (sp.SympifyError, TypeError, ValueError, AttributeError):
        return None, {
            "kind": "undecided",
            "reason": "parse_error",
        }
    if _is_nonfinite(expr):
        return None, {
            "kind": "candidate_nonfinite" if candidate else "reference_nonfinite",
        }
    return expr, None


def _tri(value):
    return value if value is True or value is False else None


def _is_tri(value) -> bool:
    return value is True or value is False or value is None


def _value_observation(value) -> dict:
    """Encode a SymPy value's decision-relevant properties without returning a verdict or raw text."""
    if value == 0:
        return {"kind": "zero", "finite": True, "zero": True}
    is_constant = not getattr(value, "free_symbols", set()) and getattr(value, "is_number", False)
    return {
        "kind": "constant" if is_constant else "symbolic",
        "finite": _tri(getattr(value, "is_finite", None)),
        "zero": _tri(getattr(value, "is_zero", None)),
    }


def _compare_exprs(candidate_expr, reference_expr) -> dict:
    try:
        residual = sp.simplify(candidate_expr - reference_expr)
    except Exception:  # noqa: BLE001 - bounded worker reports absence of a value, never a verdict
        return {"kind": "undecided", "reason": "simplify_error"}

    if _is_nonfinite(residual):
        return {"kind": "undecided", "reason": "nonfinite_residual"}

    # The child computes observations only. The parent maps these values to a verdict.
    residual_observation = _value_observation(residual)
    if residual_observation == {"kind": "zero", "finite": True, "zero": True}:
        return {
            "kind": "comparison",
            "residual": residual_observation,
            "equals": None,
            "witnesses": [],
        }
    if (
        residual_observation["kind"] == "constant"
        and residual_observation["finite"] is True
        and residual_observation["zero"] is False
    ):
        return {
            "kind": "comparison",
            "residual": residual_observation,
            "equals": None,
            "witnesses": [],
        }

    try:
        eq = candidate_expr.equals(reference_expr)
    except Exception:  # noqa: BLE001 - .equals is heuristic on some expression classes
        eq = None
    if eq is True:
        return {
            "kind": "comparison",
            "residual": residual_observation,
            "equals": True,
            "witnesses": [],
        }

    # Rational substitution is a sound refutation only when SymPy proves the resulting exact,
    # finite value is non-zero. Approximate complex magnitudes never decide a verdict.
    symbols = sorted(residual.free_symbols, key=str)
    witnesses = []
    if symbols:
        for index, probe in enumerate(_PROBES):
            try:
                value = sp.simplify(residual.subs({symbol: probe for symbol in symbols}))
            except Exception:  # noqa: BLE001 - one unusable witness does not decide the expression
                continue
            if _is_nonfinite(value):
                continue
            witnesses.append({"probe_index": index, "value": _value_observation(value)})
    return {
        "kind": "comparison",
        "residual": residual_observation,
        "equals": _tri(eq),
        "witnesses": witnesses,
    }


def _cas_worker_evaluate(op: str, cand: str, ref: str, var: str) -> dict:
    candidate_expr, error = _parse_for_worker(cand, var, candidate=True)
    if error:
        return error
    reference_expr, error = _parse_for_worker(ref, var, candidate=False)
    if error:
        return error

    if op == "antiderivative":
        try:
            candidate_expr = sp.diff(candidate_expr, sp.Symbol(var))
        except Exception:  # noqa: BLE001 - inability to differentiate means no value
            return {"kind": "undecided", "reason": "diff_error"}
        if _is_nonfinite(candidate_expr):
            # The submitted expression was finite. Undefinedness created by our differentiation
            # machinery is absence of evidence, so the parent must ABSTAIN rather than false-reject.
            return {"kind": "undecided", "reason": "nonfinite_derivative"}
    return _compare_exprs(candidate_expr, reference_expr)


def _set_cas_worker_memory_limit() -> None:
    try:
        import resource
    except ImportError:
        return

    try:
        _, hard = resource.getrlimit(resource.RLIMIT_AS)
        soft = _CAS_MEMORY_BYTES if hard == resource.RLIM_INFINITY else min(_CAS_MEMORY_BYTES, hard)
        resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
    except (AttributeError, OSError, ValueError):
        pass


def _arm_cas_worker_cpu_limit() -> None:
    """Give a persistent worker a fresh cumulative CPU deadline for this one request."""
    try:
        import resource
    except ImportError:
        return
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        used = usage.ru_utime + usage.ru_stime
        _, hard = resource.getrlimit(resource.RLIMIT_CPU)
        deadline = _math.ceil(used) + _CAS_CPU_SECONDS
        soft = deadline if hard == resource.RLIM_INFINITY else min(deadline, hard)
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    except (AttributeError, OSError, ValueError):
        pass


def _cas_pool_task(op: str, cand: str, ref: str, var: str) -> dict:
    _arm_cas_worker_cpu_limit()
    try:
        return _cas_worker_evaluate(op, cand, ref, var)
    except BaseException:  # worker faults are absence of a value, never mathematical rejection
        return {"kind": "undecided", "reason": "worker_error"}


def _dispose_cas_pool(pool=None) -> None:
    global _CAS_POOL, _CAS_POOL_OWNER_PID
    target = pool if pool is not None else _CAS_POOL
    if target is None:
        return
    if target is _CAS_POOL:
        _CAS_POOL = None
        _CAS_POOL_OWNER_PID = None
    try:
        target.terminate()
    except (AttributeError, OSError, ValueError):
        pass
    try:
        target.join()
    except (AttributeError, OSError, ValueError):
        pass


def _get_cas_pool():
    global _CAS_POOL, _CAS_POOL_OWNER_PID
    pid = _os.getpid()
    if _CAS_POOL_OWNER_PID != pid:
        # A forked descendant must never talk to or terminate its parent's pool.
        _CAS_POOL = None
        _CAS_POOL_OWNER_PID = pid
    if _CAS_POOL is None:
        context = _mp.get_context(_CAS_START_METHOD)
        _CAS_POOL = context.Pool(
            processes=1,
            initializer=_set_cas_worker_memory_limit,
            maxtasksperchild=_CAS_MAX_TASKS_PER_CHILD,
        )
        _CAS_POOL_OWNER_PID = pid
    return _CAS_POOL


def _shutdown_cas_pool() -> None:
    with _CAS_POOL_LOCK:
        _dispose_cas_pool()


_atexit.register(_shutdown_cas_pool)


def _valid_value_observation(value) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"kind", "finite", "zero"}
        and value["kind"] in {"zero", "constant", "symbolic"}
        and _is_tri(value["finite"])
        and _is_tri(value["zero"])
    )


def _decide_cas_observation(result, evidence: dict) -> Verdict:
    """The trusted parent is the only component that authors a CAS verdict.

    The resource worker runs trusted SymPy code and returns value observations only. It never sends
    CERTIFIED/REJECTED/ABSTAIN. Any death, malformed observation, or inability to compute is mapped
    here to ABSTAIN; a child crash can never become evidence against a candidate.
    """
    if not isinstance(result, dict) or not isinstance(result.get("kind"), str):
        return _verdict(ABSTAIN, "cas.abstain.protocol_error", evidence)

    kind = result["kind"]
    if kind == "candidate_nonfinite" and set(result) == {"kind"}:
        return _verdict(REJECTED, "cas.rejected.candidate_nonfinite", evidence)
    if kind == "reference_nonfinite" and set(result) == {"kind"}:
        return _verdict(ABSTAIN, "cas.abstain.reference_nonfinite", evidence)
    if kind == "undecided":
        reason = result.get("reason")
        if set(result) != {"kind", "reason"} or reason not in _UNDECIDED_REASONS:
            return _verdict(ABSTAIN, "cas.abstain.protocol_error", evidence)
        return _verdict(ABSTAIN, f"cas.abstain.{reason}", evidence)
    if kind != "comparison" or set(result) != {"kind", "residual", "equals", "witnesses"}:
        return _verdict(ABSTAIN, "cas.abstain.protocol_error", evidence)

    residual = result["residual"]
    equals = result["equals"]
    witnesses = result["witnesses"]
    if (
        not _valid_value_observation(residual)
        or not _is_tri(equals)
        or not isinstance(witnesses, list)
        or len(witnesses) > len(_PROBES)
    ):
        return _verdict(ABSTAIN, "cas.abstain.protocol_error", evidence)

    if residual == {"kind": "zero", "finite": True, "zero": True}:
        return _verdict(
            CERTIFIED,
            "cas.certified.exact_zero",
            {**evidence, "method": "simplify_exact_zero"},
        )
    if equals is True:
        return _verdict(
            CERTIFIED,
            "cas.certified.equals_true",
            {**evidence, "method": "equals_true"},
        )
    if (
        residual["kind"] == "constant"
        and residual["finite"] is True
        and residual["zero"] is False
    ):
        return _verdict(
            REJECTED,
            "cas.rejected.exact_nonzero_constant",
            {**evidence, "method": "exact_constant"},
        )

    seen = set()
    for witness in witnesses:
        if (
            not isinstance(witness, dict)
            or set(witness) != {"probe_index", "value"}
            or not isinstance(witness["probe_index"], int)
            or isinstance(witness["probe_index"], bool)
            or not 0 <= witness["probe_index"] < len(_PROBES)
            or witness["probe_index"] in seen
            or not _valid_value_observation(witness["value"])
        ):
            return _verdict(ABSTAIN, "cas.abstain.protocol_error", evidence)
        seen.add(witness["probe_index"])
        value = witness["value"]
        if value["finite"] is True and value["zero"] is False:
            return _verdict(
                REJECTED,
                "cas.rejected.exact_counterexample",
                {
                    **evidence,
                    "method": "exact_rational_probe",
                    "probe_index": witness["probe_index"],
                },
            )
    return _verdict(
        ABSTAIN,
        "cas.abstain.inconclusive",
        {**evidence, "method": "inconclusive"},
    )


def _run_cas_worker(
    op: str,
    cand: str,
    ref: str,
    var: str,
    evidence: dict,
) -> Verdict:
    if _CAS_START_METHOD is None:
        return _verdict(
            ABSTAIN,
            "cas.abstain.worker_unavailable",
            evidence,
        )
    with _CAS_POOL_LOCK:
        try:
            pool = _get_cas_pool()
            pending = pool.apply_async(_cas_pool_task, (op, cand, ref, var))
            result = pending.get(timeout=_CAS_WALL_SECONDS)
        except _mp.TimeoutError:
            _dispose_cas_pool(pool if "pool" in locals() else None)
            return _verdict(
                ABSTAIN,
                "cas.abstain.resource_limit",
                evidence,
            )
        except Exception:  # noqa: BLE001 - any worker/pool anomaly is absence of mathematical evidence
            _dispose_cas_pool(pool if "pool" in locals() else None)
            return _verdict(
                ABSTAIN,
                "cas.abstain.worker_crash",
                evidence,
            )
    return _decide_cas_observation(result, evidence)


def _cas_bounded(
    op: str,
    cand: str,
    ref: str,
    var: str,
) -> Verdict:
    evidence = {
        "op": op,
        "candidate_digest": _digest(cand),
        "reference_digest": _digest(ref),
    }
    for role, text in (("candidate", cand), ("reference", ref)):
        try:
            tree = _validate_math(text, var)
        except _MathValidationError as exc:
            undefined_candidate = role == "candidate" and exc.code in {
                "nonfinite_literal", "undefined_zero_power_zero",
            }
            status = REJECTED if undefined_candidate else ABSTAIN
            code = (
                "cas.rejected.candidate_undefined"
                if undefined_candidate
                else f"cas.abstain.{exc.code}"
            )
            return _verdict(
                status,
                code,
                evidence,
            )
        metrics = _tree_metrics(tree)
        evidence[f"{role}_nodes"] = metrics["nodes"]
        evidence[f"{role}_depth"] = metrics["depth"]
    return _run_cas_worker(op, cand, ref, var, evidence)


def cas_equivalent(
    cand: str,
    ref: str,
    var: str = "x",
) -> Verdict:
    """Certified iff ``cand`` equals ``ref`` under GENERIC-POINT (common-domain) equality.

    Semantics, stated explicitly (Codex review): this is equality as expressions on their common
    domain, the standard CAS/answer-checker notion — so removable singularities certify
    (``x/x`` certifies as ``1``; ``(x**2-1)/(x-1)`` as ``x+1``). It is NOT total-function equality
    over every point. For antiderivative/answer-checking this is the intended, sound semantics.
    Abstains (never false-rejects) when SymPy cannot decide.

    ``detail`` and evidence contain only harvest-safe codes/counts/digests. Raw residuals,
    candidate text, expected expressions, and exception messages never leave this API.
    """
    return _cas_bounded("equivalent", cand, ref, var)


def cas_antiderivative(
    cand: str,
    integrand: str,
    var: str = "x",
) -> Verdict:
    """Certified iff d/dx(cand) == integrand. verify = diff+simplify (cheap) vs solve = integrate."""
    return _cas_bounded("antiderivative", cand, integrand, var)


class CASVerifier:
    """Bounded symbolic verifier. Dispatches on ``task['op']`` (antiderivative | equivalent)."""

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
    """Hardened-execution verifier. Certified iff the candidate passes EVERY test in ``tests``.

    ``runner`` is the execution backend (default ``run_tests``). Inject
    ``isolate.run_tests_isolated`` for UNTRUSTED candidates (e.g. real LLM output) to add OS resource
    limits — the executing paths do exactly that for ``--proposer llm`` (Codex review).
    """

    def __init__(self, tests, timeout: float = 5.0, runner=None):
        self.tests = list(tests)
        self.timeout = timeout
        self.runner = runner or run_tests

    def verify(self, task: dict, candidate: str) -> Verdict:
        res = self.runner(candidate, self.tests, timeout=self.timeout)
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

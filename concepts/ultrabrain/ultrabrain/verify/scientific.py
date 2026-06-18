"""The scientific verifier zoo: physics/numerics soundness grades (thoughts/14, 22).

Same cardinal rule as ``verifiers.py``: only a SOUND decision procedure may CERTIFY; a
necessary-but-not-sufficient check is a FILTER that REJECTS a violation and otherwise ABSTAINS
-- it must NEVER certify. Treat undecided as ABSTAIN, never as a false reject. Ranked honestly
by soundness (most -> least decisive):

  UnitarityVerifier             — SOUND for the unitarity property. ||U^H U - I|| < tol -> CERTIFY,
                                  else REJECT. (Checks one closed, decidable matrix property.)
  NumericalConvergenceVerifier  — SOUND UP TO TOLERANCE. Solve at h and h/2 vs an analytic
                                  reference; CERTIFY iff the discretization error shrinks at the
                                  expected order (Richardson rate within tol), else REJECT.
  ConservationVerifier          — FILTER (necessary, not sufficient). A conserved quantity drifting
                                  past tol is a sound REJECT; staying flat is only evidence ->
                                  ABSTAIN. NEVER CERTIFY (a wrong trajectory can still conserve).
  DimensionalVerifier           — FILTER (necessary, not sufficient). Dimensional mismatch is a
                                  sound REJECT; consistency is only evidence -> ABSTAIN. NEVER
                                  CERTIFY (right units != right physics).

Untrusted expression strings (e.g. a dimensional formula) are validated against a math whitelist
AST BEFORE any sympify -- the repo just had a ``sympify()`` RCE; see ``_validate_math`` in
``verifiers.py``. We reuse that exact validator here rather than re-implement it.
"""
from __future__ import annotations

import ast as _ast
import math
from typing import Callable

import numpy as np
import sympy as sp

from .verifiers import ABSTAIN, CERTIFIED, REJECTED, Verdict

__all__ = [
    "UnitarityVerifier",
    "NumericalConvergenceVerifier",
    "ConservationVerifier",
    "DimensionalVerifier",
    "SCIENTIFIC_ZOO",
]


# --------------------------------------------------------------------------- helpers


def _as_matrix(candidate) -> np.ndarray:
    """Coerce a candidate into a complex 2-D numpy array (raises on anything else)."""
    arr = np.asarray(candidate, dtype=complex)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1] or arr.shape[0] == 0:
        raise ValueError(f"expected a square matrix, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("matrix has non-finite entries")
    return arr


def _call(candidate) -> Callable:
    """A candidate solver must be a Python callable; we never exec a string here."""
    if not callable(candidate):
        raise TypeError("candidate must be a callable solver, not a string")
    return candidate


# --------------------------------------------------------------------------- (1) unitarity


class UnitarityVerifier:
    """SOUND verifier for the unitarity property: certify iff ``||U^H U - I|| < tol``.

    This is a genuine decision procedure for ONE closed property (the columns form an
    orthonormal set), so it may CERTIFY -- but only the unitarity of the supplied matrix, not
    that the matrix is the physically intended gate. ``candidate`` is a numpy-coercible square
    complex matrix (or ``task['gold']`` if omitted). REJECT on a non-unitary matrix; ABSTAIN only
    if the candidate cannot be coerced into a matrix at all (undecided -> never a false reject).
    """

    def verify(self, task: dict, candidate=None) -> Verdict:
        tol = float(task.get("tol", 1e-9))
        if candidate is None:
            candidate = task.get("gold")
        try:
            U = _as_matrix(candidate)
        except (ValueError, TypeError) as exc:
            return Verdict(ABSTAIN, f"not a matrix: {exc}")

        n = U.shape[0]
        residual = U.conj().T @ U - np.eye(n)
        err = float(np.linalg.norm(residual, ord=2))  # spectral norm of the defect
        ev = {"deviation": err, "tol": tol, "n": n, "norm": "spectral"}
        if err <= tol:
            return Verdict(CERTIFIED, f"||U^H U - I|| = {err:.2e} <= {tol:g}", ev)
        return Verdict(REJECTED, f"||U^H U - I|| = {err:.2e} > {tol:g}", ev)


# --------------------------------------------------------------------------- (2) convergence


def _richardson_order(e_coarse: float, e_fine: float) -> float:
    """Observed convergence order from two errors at resolutions h and h/2: log2(e_h / e_h2)."""
    return math.log(e_coarse / e_fine, 2.0)


class NumericalConvergenceVerifier:
    """SOUND UP TO TOLERANCE: certify a discretization only if it converges at the expected order.

    The candidate is a solver ``solve(h) -> approximation`` (a Python callable). We run it at
    resolutions ``h`` and ``h/2``, compare each against an analytic ``reference`` from the task, and
    require the error to actually shrink at the method's expected order ``p`` (the Richardson rate
    ``log2(e_h / e_h2))`` within ``order_tol``). This is sound up to tolerance, and the certificate is
    TYPED in ``evidence['claim']``: ``order_verified`` when the order was actually measured (Richardson
    within tol) vs ``accurate_to_floor`` when both errors hit the round-off floor so the rate is
    meaningless but the solution matches the reference. Consumers (training / eval) MUST NOT treat
    ``accurate_to_floor`` traces as order-verification examples. A solver that does not converge at the
    claimed rate is REJECTED; ABSTAIN only when genuinely undecidable (non-callable, non-finite output).
    """

    def verify(self, task: dict, candidate=None) -> Verdict:
        if candidate is None:
            candidate = task.get("gold")
        order = float(task["order"])               # expected order p of the method
        h = float(task.get("h", 0.1))
        ref = task["reference"]                     # analytic reference value/array (trusted task data)
        order_tol = float(task.get("order_tol", 0.35))
        floor = float(task.get("floor", 1e-12))     # below this, error is round-off, rate is noise

        try:
            solve = _call(candidate)
        except TypeError as exc:
            return Verdict(ABSTAIN, f"not a solver: {exc}")

        try:
            ref_arr = np.asarray(ref, dtype=float)
            a_coarse = np.asarray(solve(h), dtype=float)
            a_fine = np.asarray(solve(h / 2.0), dtype=float)
        except Exception as exc:  # noqa: BLE001 - an untrusted solver may raise anything
            return Verdict(ABSTAIN, f"solver raised / non-numeric output: {exc}")

        if not (np.all(np.isfinite(a_coarse)) and np.all(np.isfinite(a_fine))):
            return Verdict(ABSTAIN, "solver produced non-finite output")

        try:
            e_coarse = float(np.linalg.norm(a_coarse - ref_arr))
            e_fine = float(np.linalg.norm(a_fine - ref_arr))
        except ValueError as exc:
            return Verdict(ABSTAIN, f"shape mismatch vs reference: {exc}")

        ev = {
            "h": h, "e_coarse": e_coarse, "e_fine": e_fine,
            "expected_order": order, "order_tol": order_tol, "floor": floor,
        }

        # Already exact (both errors at the round-off floor): the method clearly resolves the
        # reference, and the rate would be meaningless noise -> CERTIFY on the error bound itself.
        if e_coarse <= floor and e_fine <= floor:
            ev["observed_order"] = None
            ev["claim"] = "accurate_to_floor"  # NOT order_verified: both errors are at round-off
            return Verdict(CERTIFIED, f"accurate to floor ({e_coarse:.2e}, {e_fine:.2e}); order not measured", ev)

        # Error did not decrease: not converging -> a sound REJECT.
        if e_fine >= e_coarse:
            ev["observed_order"] = 0.0 if e_fine == e_coarse else _safe_order(e_coarse, e_fine)
            return Verdict(REJECTED, f"error grew/stalled: {e_coarse:.2e} -> {e_fine:.2e}", ev)

        # Fine error hit the floor while coarse did not: converged faster than measurable -> CERTIFY.
        if e_fine <= floor:
            ev["observed_order"] = None
            ev["claim"] = "accurate_to_floor"  # order unmeasurable here -> do NOT claim order_verified
            return Verdict(CERTIFIED, f"fine error reached floor ({e_fine:.2e}); order not measured", ev)

        observed = _richardson_order(e_coarse, e_fine)
        ev["observed_order"] = observed
        if abs(observed - order) <= order_tol:
            ev["claim"] = "order_verified"  # the strong claim: order actually measured via Richardson
            return Verdict(CERTIFIED, f"observed order {observed:.2f} ~= {order:g}", ev)
        return Verdict(REJECTED, f"observed order {observed:.2f} != {order:g} (tol {order_tol:g})", ev)


def _safe_order(e_coarse: float, e_fine: float):
    try:
        return _richardson_order(e_coarse, e_fine)
    except (ValueError, ZeroDivisionError):
        return None


# --------------------------------------------------------------------------- (3) conservation


def _conserved_series(task: dict, candidate) -> np.ndarray:
    """Build the 1-D series of the conserved quantity over the candidate trajectory.

    Two task shapes are supported, both trusted task data (NOT untrusted strings):
      * ``task['quantity']`` is a callable ``q(state) -> float`` applied to each row/state of the
        trajectory (``candidate``);
      * else ``candidate`` is already the precomputed series of the conserved quantity.
    """
    quantity = task.get("quantity")
    traj = np.asarray(candidate, dtype=float)
    if callable(quantity):
        states = traj if traj.ndim >= 2 else traj.reshape(-1, 1)
        return np.asarray([float(quantity(s)) for s in states], dtype=float)
    return traj.reshape(-1)


class ConservationVerifier:
    """FILTER (necessary, not sufficient) -- it NEVER CERTIFIES.

    A conserved quantity (energy / momentum / probability / norm) that drifts beyond ``tol`` over the
    candidate trajectory is a sound REJECT. Staying flat is only *evidence* of correctness -- a
    wrong trajectory can still conserve the quantity -- so the best this can return is ABSTAIN.
    Returning CERTIFIED here would be unsound, so it is structurally impossible: this verifier emits
    only REJECTED or ABSTAIN.

    ``tol`` is the absolute drift budget on ``max|q - q0|`` (set ``rel_tol`` to scale it by ``|q0|``).
    """

    def verify(self, task: dict, candidate=None) -> Verdict:
        if candidate is None:
            candidate = task.get("gold")
        tol = float(task.get("tol", 1e-6))
        try:
            series = _conserved_series(task, candidate)
        except (ValueError, TypeError) as exc:
            return Verdict(ABSTAIN, f"could not build conserved series: {exc}")

        if series.size == 0 or not np.all(np.isfinite(series)):
            return Verdict(ABSTAIN, "empty or non-finite conserved series")

        q0 = float(series[0])
        drift = float(np.max(np.abs(series - q0)))
        budget = tol + float(task.get("rel_tol", 0.0)) * abs(q0)
        ev = {"q0": q0, "max_drift": drift, "budget": budget, "n": int(series.size)}
        if drift > budget:
            return Verdict(REJECTED, f"conserved quantity drifted {drift:.2e} > {budget:.2e}", ev)
        # Necessary condition met -> evidence only. A FILTER never certifies.
        return Verdict(ABSTAIN, f"conserved within {drift:.2e} <= {budget:.2e} (filter: not a cert)", ev)


# --------------------------------------------------------------------------- (4) dimensional

# Base SI dimensions tracked as integer/rational exponent vectors.
_BASE_DIMS = ("mass", "length", "time", "current", "temperature", "amount", "luminous")


def _dimvec(mapping: dict) -> sp.Matrix:
    return sp.Matrix([sp.Rational(mapping.get(name, 0)) for name in _BASE_DIMS])


# A tiny, fully-trusted symbol table mapping names -> dimension vectors. Untrusted candidate
# formulas may ONLY reference these names (enforced by the whitelist AST below), never call code.
_BASE_UNITS = {
    "kg": {"mass": 1}, "g": {"mass": 1},
    "m": {"length": 1}, "cm": {"length": 1}, "km": {"length": 1},
    "s": {"time": 1}, "ms": {"time": 1},
    "A": {"current": 1}, "K": {"temperature": 1}, "mol": {"amount": 1}, "cd": {"luminous": 1},
    "N": {"mass": 1, "length": 1, "time": -2},          # newton
    "J": {"mass": 1, "length": 2, "time": -2},          # joule
    "W": {"mass": 1, "length": 2, "time": -3},          # watt
    "Pa": {"mass": 1, "length": -1, "time": -2},        # pascal
    "C": {"current": 1, "time": 1},                     # coulomb
    "V": {"mass": 1, "length": 2, "time": -3, "current": -1},  # volt
    "Hz": {"time": -1},
    "1": {},                                            # dimensionless literal
}


class _DimensionError(ValueError):
    """Raised when two dimensionally-incompatible quantities are added/subtracted/compared."""


class _Dim:
    """An algebra element carrying ONLY a dimension vector (value-free dimensional analysis)."""

    __slots__ = ("vec",)

    def __init__(self, vec: sp.Matrix):
        self.vec = vec

    def _binadd(self, other: "_Dim") -> "_Dim":
        if self.vec != other.vec:
            raise _DimensionError(f"add/sub of {list(self.vec)} and {list(other.vec)}")
        return self

    __add__ = __radd__ = _binadd
    __sub__ = _binadd

    def __rsub__(self, other):
        return self._binadd(other)

    def __mul__(self, other):
        return _Dim(self.vec + other.vec) if isinstance(other, _Dim) else self

    __rmul__ = __mul__

    def __truediv__(self, other):
        return _Dim(self.vec - other.vec) if isinstance(other, _Dim) else self

    def __rtruediv__(self, other):
        return _Dim(-self.vec) if not isinstance(other, _Dim) else other / self

    def __pow__(self, power):
        if isinstance(power, _Dim):
            if power.vec != _dimvec({}):
                raise _DimensionError("exponent must be dimensionless")
            power = 1
        try:
            exp = sp.Rational(power)
        except (TypeError, ValueError) as exc:
            raise _DimensionError(f"non-rational exponent {power!r}") from exc
        return _Dim(self.vec * exp)


# Whitelist for untrusted dimensional formulas: arithmetic only, names resolved from the unit table.
_DIM_NODES = (
    _ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Constant, _ast.Name, _ast.Load,
    _ast.Add, _ast.Sub, _ast.Mult, _ast.Div, _ast.Pow, _ast.USub, _ast.UAdd,
)


def _eval_dim(text: str, units: dict) -> _Dim:
    """Safely evaluate an untrusted unit formula into a dimension vector.

    Validates against a strict arithmetic-only AST first (no calls, no attributes, no dunder
    names), then walks the tree by hand -- we never ``eval``/``sympify`` the untrusted string.
    """
    try:
        tree = _ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise _DimensionError(f"syntax: {exc}") from exc
    nodes = list(_ast.walk(tree))
    if len(nodes) > 200:  # DoS guard: bound formula size before walking (Codex review)
        raise _DimensionError("formula too large")
    for node in nodes:
        if not isinstance(node, _DIM_NODES):
            raise _DimensionError(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, _ast.Constant) and not isinstance(node.value, (int, float)):
            raise _DimensionError("disallowed constant")
        if isinstance(node, _ast.Name) and node.id not in units:
            raise _DimensionError(f"unknown unit: {node.id}")

    def _walk(node):
        if isinstance(node, _ast.Expression):
            return _walk(node.body)
        if isinstance(node, _ast.Constant):
            # A bare number is dimensionless; only 0 may be added to anything as identity.
            return _Dim(_dimvec({}))
        if isinstance(node, _ast.Name):
            return _Dim(_dimvec(units[node.id]))
        if isinstance(node, _ast.UnaryOp):
            return _walk(node.operand)
        if isinstance(node, _ast.BinOp):
            left, right = _walk(node.left), _walk(node.right)
            if isinstance(node.op, _ast.Add):
                return left + right
            if isinstance(node.op, _ast.Sub):
                return left - right
            if isinstance(node.op, _ast.Mult):
                return left * right
            if isinstance(node.op, _ast.Div):
                return left / right
            if isinstance(node.op, _ast.Pow):
                return left ** _const_pow(node.right)
        raise _DimensionError(f"unhandled node {type(node).__name__}")

    return _walk(tree)


def _const_pow(node) -> sp.Rational:
    """A power exponent must be a literal rational (e.g. ``m**2`` or ``s**-1``), not a unit."""
    if isinstance(node, _ast.Constant) and isinstance(node.value, (int, float)):
        if abs(node.value) > 1000:  # DoS hygiene: bound exponent magnitude (mirror the CAS pow guard)
            raise _DimensionError("exponent magnitude too large")
        return sp.Rational(node.value)
    if isinstance(node, _ast.UnaryOp) and isinstance(node.op, (_ast.USub, _ast.UAdd)):
        inner = _const_pow(node.operand)
        return -inner if isinstance(node.op, _ast.USub) else inner
    if isinstance(node, _ast.BinOp) and isinstance(node.op, _ast.Div):
        return _const_pow(node.left) / _const_pow(node.right)
    raise _DimensionError("exponent must be a numeric literal")


class DimensionalVerifier:
    """FILTER (necessary, not sufficient) -- it NEVER CERTIFIES.

    Checks unit/dimensional consistency of an equation. A dimensional mismatch (e.g. the two sides
    of ``lhs == rhs`` reduce to different base-dimension vectors, or an addition mixes incompatible
    units) is a sound REJECT. Consistency is only *evidence* -- correct units do not imply correct
    physics -- so the best this returns is ABSTAIN. CERTIFIED is structurally impossible here.

    Task shape: ``task['lhs']`` and ``task['rhs']`` are untrusted unit formulas over the trusted
    unit table (``task.get('units')`` may extend ``_BASE_UNITS``). Alternatively ``task['expr']`` is
    a single formula checked only for internal consistency (no add/sub mismatch). All untrusted
    strings pass the whitelist AST before evaluation -- no eval/sympify of raw input.
    """

    def verify(self, task: dict, candidate=None) -> Verdict:
        units = dict(_BASE_UNITS)
        units.update(task.get("units", {}))
        # candidate may override the rhs (e.g. a proposed expression for the right-hand side).
        lhs = task.get("lhs")
        rhs = candidate if candidate is not None else task.get("rhs")
        expr = task.get("expr")

        try:
            if expr is not None and lhs is None:
                _eval_dim(str(expr), units)  # internal-consistency check only
                return Verdict(
                    ABSTAIN,
                    "dimensionally self-consistent (filter: not a cert)",
                    {"expr": str(expr)},
                )
            ldim = _eval_dim(str(lhs), units)
            rdim = _eval_dim(str(rhs), units)
        except _DimensionError as exc:
            ev = {"lhs": str(lhs), "rhs": str(rhs), "reason": str(exc)}
            return Verdict(REJECTED, f"dimensional mismatch: {exc}", ev)

        ev = {
            "lhs": str(lhs), "rhs": str(rhs),
            "lhs_dim": [int(x) if x.is_integer else float(x) for x in ldim.vec],
            "rhs_dim": [int(x) if x.is_integer else float(x) for x in rdim.vec],
            "basis": list(_BASE_DIMS),
        }
        if ldim.vec != rdim.vec:
            return Verdict(REJECTED, f"dimensions differ: {ev['lhs_dim']} != {ev['rhs_dim']}", ev)
        # Necessary condition met -> evidence only. A FILTER never certifies.
        return Verdict(ABSTAIN, "dimensionally consistent (filter: not a cert)", ev)


# Honest soundness ranking (most -> least decisive). The first two may CERTIFY; the FILTERS cannot.
SCIENTIFIC_ZOO = {
    "unitarity": UnitarityVerifier,            # sound for the property -> CERTIFY/REJECT
    "convergence": NumericalConvergenceVerifier,  # sound up to tolerance -> CERTIFY/REJECT
    "conservation": ConservationVerifier,      # FILTER -> REJECT/ABSTAIN, never CERTIFY
    "dimensional": DimensionalVerifier,        # FILTER -> REJECT/ABSTAIN, never CERTIFY
}

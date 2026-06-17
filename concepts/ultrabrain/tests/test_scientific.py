import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ultrabrain.verify import CERTIFIED, REJECTED, ABSTAIN, Gate, Ledger, Verdict
from ultrabrain.verify.scientific import (
    SCIENTIFIC_ZOO,
    ConservationVerifier,
    DimensionalVerifier,
    NumericalConvergenceVerifier,
    UnitarityVerifier,
)


def _physics():
    path = os.path.join(ROOT, "tasks", "micro_physics.jsonl")
    return [json.loads(l) for l in open(path) if l.strip()]


def _by_id(tid):
    return next(t for t in _physics() if t["id"] == tid)


def _rebuild_complex(grid):
    """Task jsonl encodes a complex matrix as a grid of unambiguous [re, im] leaf pairs."""
    return np.array(
        [[complex(re, im) for (re, im) in row] for row in grid],
        dtype=complex,
    )


# --------------------------------------------------------------------------- solvers (callables)


def euler_exp(h):
    """Forward Euler for y' = y, y(0)=1 over [0,1]. Global error O(h) -> order 1."""
    n = int(round(1.0 / h))
    y = 1.0
    for _ in range(n):
        y = y + h * y
    return y


def euler_exp_wrong(h):
    """A non-converging 'solver': returns a fixed wrong constant regardless of h."""
    return 3.0


def heat_profile(h):
    """Resolve sin(pi x) on [0,1] sampled on the task grid; error ~ O(h^2) toward the analytic ref.

    We emulate a 2nd-order spatial scheme by sampling a smooth field whose sampling/interp error
    on this fixed 6-point grid shrinks quadratically as h halves.
    """
    xs = np.linspace(0.0, 1.0, 6)
    exact = np.sin(math.pi * xs)
    # second-order-accurate perturbation that halves^2 as h -> h/2
    return exact + (h ** 2) * np.cos(math.pi * xs)


def heat_profile_first_order(h):
    """A 1st-order scheme: error shrinks only linearly -> must be REJECTED by an order-2 task."""
    xs = np.linspace(0.0, 1.0, 6)
    exact = np.sin(math.pi * xs)
    return exact + h * np.cos(math.pi * xs)


def sho_trajectory(n=400, dt=0.05, omega=1.0):
    """Symplectic (semi-implicit Euler) SHO -> energy stays bounded/constant within tol."""
    x, v = 1.0, 0.0
    rows = []
    for _ in range(n):
        v = v - omega * omega * x * dt
        x = x + v * dt
        rows.append((x, v))
    return np.array(rows, dtype=float)


def sho_trajectory_dissipative(n=400, dt=0.05, omega=1.0, damp=0.02):
    """A damped trajectory: energy decays -> conservation FILTER must REJECT."""
    x, v = 1.0, 0.0
    rows = []
    for _ in range(n):
        v = (v - omega * omega * x * dt) * (1.0 - damp)
        x = x + v * dt
        rows.append((x, v))
    return np.array(rows, dtype=float)


def sho_energy(state, omega=1.0):
    x, v = float(state[0]), float(state[1])
    return 0.5 * v * v + 0.5 * omega * omega * x * x


# --------------------------------------------------------------------------- (1) unitarity (sound)


def test_unitarity_certifies_hadamard_and_pauli():
    v = UnitarityVerifier()
    for tid in ("phys_hadamard_unitary", "phys_pauli_x_unitary"):
        t = _by_id(tid)
        U = np.array(t["gold"], dtype=complex)
        assert v.verify(t, U).status == CERTIFIED, tid


def test_unitarity_certifies_complex_phase_gate():
    t = _by_id("phys_phase_s_unitary")
    U = _rebuild_complex(t["gold_complex"])      # diag(1, i)
    assert np.allclose(U, np.diag([1.0, 1j]))
    assert UnitarityVerifier().verify(t, U).status == CERTIFIED


def test_unitarity_rejects_nonunitary():
    v = UnitarityVerifier()
    for tid in ("phys_hadamard_unitary", "phys_pauli_x_unitary"):
        t = _by_id(tid)
        for d in t["distractors"]:
            assert v.verify(t, np.array(d, dtype=complex)).status == REJECTED, (tid, d)


def test_unitarity_abstains_on_non_matrix():
    # undecidable input -> ABSTAIN, never a false reject
    t = _by_id("phys_hadamard_unitary")
    assert UnitarityVerifier().verify(t, "not a matrix").status == ABSTAIN
    assert UnitarityVerifier().verify(t, np.zeros((2, 3))).status == ABSTAIN


def test_unitarity_tolerance_boundary():
    t = {"tol": 1e-6}
    near = np.array([[1.0 + 1e-9, 0.0], [0.0, 1.0]], dtype=complex)
    assert UnitarityVerifier().verify(t, near).status == CERTIFIED
    far = np.array([[1.0 + 1e-3, 0.0], [0.0, 1.0]], dtype=complex)
    assert UnitarityVerifier().verify(t, far).status == REJECTED


# --------------------------------------------------------------------------- (2) convergence (sound up to tol)


def test_convergence_certifies_first_order_euler():
    t = _by_id("phys_euler_linear_convergence")
    out = NumericalConvergenceVerifier().verify(t, euler_exp)
    assert out.status == CERTIFIED, out
    assert abs(out.evidence["observed_order"] - 1.0) <= t["order_tol"]


def test_convergence_certifies_second_order_heat():
    t = _by_id("phys_heat_diffusion_convergence")
    out = NumericalConvergenceVerifier().verify(t, heat_profile)
    assert out.status == CERTIFIED, out
    assert abs(out.evidence["observed_order"] - 2.0) <= t["order_tol"]


def test_convergence_rejects_wrong_order():
    # A 1st-order scheme submitted for an order-2 task: real convergence, wrong RATE -> REJECT.
    t = _by_id("phys_heat_diffusion_convergence")
    out = NumericalConvergenceVerifier().verify(t, heat_profile_first_order)
    assert out.status == REJECTED, out


def test_convergence_rejects_nonconverging():
    t = _by_id("phys_euler_linear_convergence")
    out = NumericalConvergenceVerifier().verify(t, euler_exp_wrong)
    assert out.status == REJECTED, out


def test_convergence_abstains_on_non_solver():
    t = _by_id("phys_euler_linear_convergence")
    assert NumericalConvergenceVerifier().verify(t, "y = exp(x)").status == ABSTAIN

    def boom(h):
        raise RuntimeError("solver blew up")

    assert NumericalConvergenceVerifier().verify(t, boom).status == ABSTAIN

    def nan_solver(h):
        return float("nan")

    assert NumericalConvergenceVerifier().verify(t, nan_solver).status == ABSTAIN


# --------------------------------------------------------------------------- (3) conservation (FILTER)


def test_conservation_abstains_on_conserved_never_certifies():
    t = dict(_by_id("phys_sho_energy"))
    t["quantity"] = sho_energy
    out = ConservationVerifier().verify(t, sho_trajectory())
    assert out.status == ABSTAIN, out          # conserved -> evidence only
    assert out.status != CERTIFIED


def test_conservation_rejects_dissipation():
    t = dict(_by_id("phys_sho_energy"))
    t["quantity"] = sho_energy
    out = ConservationVerifier().verify(t, sho_trajectory_dissipative())
    assert out.status == REJECTED, out


def test_conservation_norm_series_filter():
    v = ConservationVerifier()
    t = _by_id("phys_norm_conservation")
    assert v.verify(t, t["gold"]).status == ABSTAIN          # norm flat -> abstain (not cert)
    for d in t["distractors"]:
        assert v.verify(t, d).status == REJECTED             # norm drifts -> reject


def test_conservation_abstains_on_garbage():
    t = _by_id("phys_norm_conservation")
    assert ConservationVerifier().verify(t, []).status == ABSTAIN
    assert ConservationVerifier().verify(t, [float("inf"), 1.0]).status == ABSTAIN


# --------------------------------------------------------------------------- (4) dimensional (FILTER)


def test_dimensional_abstains_on_consistent_never_certifies():
    v = DimensionalVerifier()
    for tid in ("phys_dim_newton_second_law", "phys_dim_kinetic_energy", "phys_dim_period_pendulum"):
        t = _by_id(tid)
        out = v.verify(t)                       # uses task lhs/rhs
        assert out.status == ABSTAIN, (tid, out)
        assert out.status != CERTIFIED


def test_dimensional_rejects_mismatch():
    v = DimensionalVerifier()
    for tid in ("phys_dim_newton_second_law", "phys_dim_kinetic_energy", "phys_dim_period_pendulum"):
        t = _by_id(tid)
        assert v.verify(t, t["bad_rhs"]).status == REJECTED, tid


def test_dimensional_rejects_incompatible_addition():
    # adding metres to seconds is a sound reject
    t = {"lhs": "m + s", "rhs": "m"}
    assert DimensionalVerifier().verify(t).status == REJECTED


def test_dimensional_rejects_injection_payload():
    # the soundness rule from the CAS RCE: an untrusted formula must NEVER be eval'd/sympified.
    payload = "__import__('os').system('echo pwned')"
    out = DimensionalVerifier().verify({"lhs": "m", "rhs": payload})
    assert out.status == REJECTED                # rejected by the whitelist AST, no exec
    assert DimensionalVerifier().verify({"lhs": "m", "rhs": "m.__class__"}).status == REJECTED
    assert DimensionalVerifier().verify({"lhs": "m", "rhs": "open('x')"}).status == REJECTED
    assert DimensionalVerifier().verify({"lhs": "m", "rhs": "unknownunit"}).status == REJECTED


# --------------------------------------------------------------------------- cross-cutting invariants


def test_filters_never_certify_on_any_task_or_distractor():
    """The cardinal rule: conservation/dimensional FILTERS must NEVER return CERTIFIED."""
    cons, dim = ConservationVerifier(), DimensionalVerifier()
    checked = 0
    for t in _physics():
        if t["kind"] == "conservation":
            tt = dict(t)
            if t["id"] == "phys_sho_energy":
                tt["quantity"] = sho_energy
                candidates = [sho_trajectory(), sho_trajectory_dissipative()]
            else:
                candidates = [t.get("gold")] + list(t.get("distractors", []))
            for c in candidates:
                assert cons.verify(tt, c).status != CERTIFIED
                checked += 1
        if t["kind"] == "dimensional":
            for c in (t.get("rhs"), t.get("bad_rhs"), "m + s", "__import__('os')"):
                assert dim.verify(dict(t), c).status != CERTIFIED
                checked += 1
    assert checked >= 10


def test_filter_status_domain_is_reject_or_abstain_only():
    # exhaustively: whatever we throw at a FILTER, the status is in {REJECTED, ABSTAIN}.
    cons, dim = ConservationVerifier(), DimensionalVerifier()
    cons_inputs = [[1.0, 1.0, 1.0], [1.0, 5.0], [], [float("nan")], "junk", 42]
    for c in cons_inputs:
        assert cons.verify({"tol": 1e-6}, c).status in (REJECTED, ABSTAIN)
    dim_inputs = ["kg*m/s**2", "kg*m/s", "m + s", "bad(", "x.__class__", 0]
    for c in dim_inputs:
        assert dim.verify({"lhs": "N"}, c).status in (REJECTED, ABSTAIN)


def test_zoo_registry_maps_names_to_verifiers():
    assert set(SCIENTIFIC_ZOO) == {"unitarity", "convergence", "conservation", "dimensional"}
    for cls in SCIENTIFIC_ZOO.values():
        assert hasattr(cls(), "verify")


def test_gate_certifies_sound_unitary_but_not_filter(tmp_path):
    # A sound verifier flows through the existing Gate and writes the cert; a FILTER never produces
    # a certified outcome, so nothing is written for it.
    led = Ledger(str(tmp_path / "sci_ledger.jsonl"), secret="t")
    t = _by_id("phys_hadamard_unitary")
    # Pass JSON-serializable nested lists through the Gate (the verifier coerces to a matrix);
    # the existing ledger serializes the candidate, so a raw ndarray would not round-trip.
    out = Gate(UnitarityVerifier(), led).judge(t, t["gold"])
    assert out.certified and out.verdict.status == CERTIFIED
    ct = dict(_by_id("phys_norm_conservation"))
    fout = Gate(ConservationVerifier(), led).judge(ct, ct["gold"])
    assert not fout.certified                   # FILTER abstains -> never certified
    assert len(led.records()) == 1             # only the sound certificate entered the ledger


def test_all_verifiers_return_verdict_objects():
    t = _by_id("phys_hadamard_unitary")
    assert isinstance(UnitarityVerifier().verify(t, np.eye(2)), Verdict)
    ct = _by_id("phys_euler_linear_convergence")
    assert isinstance(NumericalConvergenceVerifier().verify(ct, euler_exp), Verdict)

"""The gate: PROPOSE -> EXECUTE -> VERIFY -> GATE (thoughts/08, 22).

A model-agnostic accept gate. It times verification (so we can report verify-cost vs solve-cost),
routes a Verdict to certified | rejected | abstain, and writes ONLY certified beliefs to the
ledger. The proposer is whatever produced ``candidate`` — a template, a diffusion head, or an LLM;
the gate does not care, which is the whole point.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .ledger import Ledger
from .verifiers import ABSTAIN, CERTIFIED, REJECTED, Verdict


_CAS_SIGNAL_SCHEMA = "ultrabrain.cas.verdict.v1"
_CAS_SIGNAL_CODES = {
    "cas.certified.exact_zero",
    "cas.certified.equals_true",
    "cas.rejected.candidate_nonfinite",
    "cas.rejected.candidate_undefined",
    "cas.rejected.exact_counterexample",
    "cas.rejected.exact_nonzero_constant",
    "cas.abstain.arity_limit",
    "cas.abstain.depth_limit",
    "cas.abstain.diff_error",
    "cas.abstain.disallowed_call",
    "cas.abstain.disallowed_constant",
    "cas.abstain.disallowed_name",
    "cas.abstain.disallowed_syntax",
    "cas.abstain.function_limit",
    "cas.abstain.inconclusive",
    "cas.abstain.integer_limit",
    "cas.abstain.invalid_type",
    "cas.abstain.invalid_variable",
    "cas.abstain.node_limit",
    "cas.abstain.nonfinite_derivative",
    "cas.abstain.nonfinite_literal",
    "cas.abstain.nonfinite_residual",
    "cas.abstain.parse_error",
    "cas.abstain.power_limit",
    "cas.abstain.precision_limit",
    "cas.abstain.protocol_error",
    "cas.abstain.reference_nonfinite",
    "cas.abstain.resource_limit",
    "cas.abstain.simplify_error",
    "cas.abstain.syntax",
    "cas.abstain.text_limit",
    "cas.abstain.undefined_zero_power_zero",
    "cas.abstain.worker_crash",
    "cas.abstain.worker_error",
    "cas.abstain.worker_unavailable",
}
_CAS_SIGNAL_KEYS = {
    "code",
    "op",
    "candidate_digest",
    "reference_digest",
    "candidate_nodes",
    "candidate_depth",
    "reference_nodes",
    "reference_depth",
    "method",
    "probe_index",
    "candidate_handling",
    "parser_safety_basis",
}
_CAS_SIGNAL_ENUMS = {
    "op": {"equivalent", "antiderivative"},
    "method": {
        "simplify_exact_zero",
        "equals_true",
        "exact_constant",
        "exact_rational_probe",
        "inconclusive",
    },
    "candidate_handling": {"ast_allowlist_then_restricted_sympify"},
    "parser_safety_basis": {"no_bypass_found_not_proven"},
}


def _is_digest(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _sanitized_cas_signal(verdict: Verdict) -> dict:
    """Project a CAS verdict into a fixed, harvest-safe schema.

    Unknown evidence keys are never forwarded. Raw expressions, residuals, exceptions, candidate
    output, and reference values have no representable field in this schema. A schema mismatch is
    loud rather than silently producing preference data with ambiguous provenance.
    """
    expected_prefix = {
        CERTIFIED: "cas.certified.",
        REJECTED: "cas.rejected.",
        ABSTAIN: "cas.abstain.",
    }.get(verdict.status)
    evidence = verdict.evidence
    code = evidence.get("code") if isinstance(evidence, dict) else None
    if (
        expected_prefix is None
        or not isinstance(code, str)
        or not code.startswith(expected_prefix)
        or code not in _CAS_SIGNAL_CODES
        or verdict.detail != code
    ):
        raise ValueError("cas_signal.invalid_verdict")

    safe = {}
    for key in _CAS_SIGNAL_KEYS:
        if key not in evidence:
            continue
        value = evidence[key]
        if key.endswith("_digest"):
            if not _is_digest(value):
                raise ValueError("cas_signal.invalid_digest")
        elif key in {
            "candidate_nodes",
            "candidate_depth",
            "reference_nodes",
            "reference_depth",
            "probe_index",
        }:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError("cas_signal.invalid_count")
        elif key in _CAS_SIGNAL_ENUMS:
            if value not in _CAS_SIGNAL_ENUMS[key]:
                raise ValueError("cas_signal.invalid_enum")
        elif key == "code" and value != code:
            raise ValueError("cas_signal.invalid_code")
        safe[key] = value
    if set(safe) - _CAS_SIGNAL_KEYS or safe.get("code") != code:
        raise ValueError("cas_signal.invalid_evidence")
    return {
        "schema": _CAS_SIGNAL_SCHEMA,
        "status": verdict.status,
        "code": code,
        "evidence": safe,
    }


@dataclass
class Outcome:
    task_id: str
    candidate: str
    verdict: Verdict
    seconds: float

    @property
    def certified(self) -> bool:
        return self.verdict.status == CERTIFIED

    def cas_training_signal(self) -> dict:
        """Return sanitized CAS training metadata; explicit candidate slots live elsewhere."""
        return _sanitized_cas_signal(self.verdict)


class Gate:
    def __init__(self, verifier, ledger: Ledger | None = None):
        self.verifier = verifier
        self.ledger = ledger

    def judge(self, task: dict, candidate: str) -> Outcome:
        t0 = time.time()
        verdict = self.verifier.verify(task, candidate)
        seconds = time.time() - t0
        outcome = Outcome(task.get("id", "?"), candidate, verdict, seconds)
        if outcome.certified and self.ledger is not None:
            self.ledger.append({
                "task_id": outcome.task_id,
                "candidate": candidate,
                "status": verdict.status,
                "detail": verdict.detail,
                "evidence": verdict.evidence,
                "verify_seconds": round(seconds, 6),
            })
        return outcome

"""Verifier-grounded accept gate: the soundness core of UltraBrain-Code.

Only verifier-certified outputs are trusted (thoughts/14, 22). The model is a demoted proposer;
capability comes from verified search, not parameters.
"""
from .gate import Gate, Outcome
from .ledger import Ledger
from .sandbox import ExecResult, run_tests
from .verifiers import (
    ABSTAIN,
    CERTIFIED,
    REJECTED,
    CASVerifier,
    CodeTestVerifier,
    Verdict,
    cas_antiderivative,
    cas_equivalent,
    harden,
    weak_suite,
)

__all__ = [
    "Gate", "Outcome", "Ledger", "ExecResult", "run_tests",
    "Verdict", "CASVerifier", "CodeTestVerifier",
    "cas_equivalent", "cas_antiderivative", "harden", "weak_suite",
    "CERTIFIED", "REJECTED", "ABSTAIN",
]

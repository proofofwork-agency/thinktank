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
from .verifiers import CERTIFIED, Verdict


@dataclass
class Outcome:
    task_id: str
    candidate: str
    verdict: Verdict
    seconds: float

    @property
    def certified(self) -> bool:
        return self.verdict.status == CERTIFIED


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

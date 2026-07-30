from __future__ import annotations

from rapana.agents.base import Agent
from rapana.risk.guardrails import PreTradeChecker, RiskDecision, TradeProposal


class RiskManager(Agent):
    """Risk Manager agent — a thin wrapper around the deterministic PreTradeChecker.

    The LLM debate and Portfolio Manager cannot bypass this. It is the hard
    veto gate mandated by the research (Knight/Flash-Crash proofing).
    """

    role = "risk_manager"

    def __init__(self, checker: PreTradeChecker) -> None:
        self.checker = checker

    def review(self, proposal: TradeProposal | None) -> RiskDecision:
        if proposal is None:
            return RiskDecision(approved=False, reason="no proposal")
        return self.checker.check(proposal)

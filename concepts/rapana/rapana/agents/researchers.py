from __future__ import annotations

from dataclasses import dataclass

from rapana.agents.base import Agent
from rapana.agents.brain import Brain
from rapana.signals import Signal


@dataclass
class Thesis:
    symbol: str
    side: str          # "bull" | "bear"
    score: float       # -1..1 signed confidence-weighted
    key_points: list[str]
    recommended: str   # "buy" | "sell" | "hold"
    commentary: str = ""  # optional LLM annotation (never affects the decision)


class Researcher(Agent):
    """A researcher aggregates the subset of signals supporting one side.

    An optional ``brain`` (LLM) annotates the thesis prose for explainability.
    The numeric score/recommendation are always deterministic, so the brain
    cannot cause a harmful trade.
    """

    def __init__(self, brain: Brain | None = None) -> None:
        self.brain = brain

    def _build(self, signals: list[Signal], symbol: str, want_positive: bool) -> Thesis:
        side = "bull" if want_positive else "bear"
        wanted = [s for s in signals if (s.weighted_score > 0) == want_positive and s.weighted_score != 0]
        score = sum(s.weighted_score for s in wanted)
        points = [f"{s.source}: {s.rationale}" for s in wanted]
        if want_positive:
            recommended = "buy" if score > 0.2 else "hold"
        else:
            recommended = "sell" if score < -0.2 else "hold"
        commentary = ""
        if self.brain is not None and wanted:
            prompt = (
                f"You are the {side} researcher for {symbol}. In one sentence, argue the "
                f"{side} case from these signals: " + "; ".join(points[:4])
            )
            commentary = self.brain.reason(prompt)
        return Thesis(
            symbol=symbol, side=side, score=max(-1.0, min(1.0, score)),
            key_points=points, recommended=recommended, commentary=commentary,
        )


class BullResearcher(Researcher):
    role = "bull_researcher"

    def argue(self, signals: list[Signal], symbol: str) -> Thesis:
        return self._build(signals, symbol, want_positive=True)


class BearResearcher(Researcher):
    role = "bear_researcher"

    def argue(self, signals: list[Signal], symbol: str) -> Thesis:
        return self._build(signals, symbol, want_positive=False)

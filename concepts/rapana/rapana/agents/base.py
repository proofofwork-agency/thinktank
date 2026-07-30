from __future__ import annotations

from typing import TYPE_CHECKING

from rapana.signals import Signal, combine_signals

if TYPE_CHECKING:
    from rapana.fleet.data_provider import DataProvider


class Agent:
    """Base agent. Analysts emit Signals; downstream agents consume/aggregate.

    Agent sub-classes expose role-specific methods (analyze/argue/review/decide/
    record) rather than a single ``run`` — so this base only carries ``role``.
    """

    role: str = "agent"


class Analyst(Agent):
    """Analyst agents produce one Signal per symbol from a DataProvider."""

    role = "analyst"

    def analyze(self, symbol: str, provider: DataProvider) -> Signal:  # pragma: no cover
        raise NotImplementedError


def blend(signals: list[Signal], symbol: str, source: str) -> Signal:
    """Combine sibling signals into one consensus signal (majority direction)."""
    valid = [s for s in signals if s.direction != "neutral"]
    if not valid:
        return Signal(symbol, source, "neutral", 0.0, 0.0, "all sub-signals neutral")
    net = combine_signals(signals)
    direction = "bullish" if net > 0.05 else "bearish" if net < -0.05 else "neutral"
    agree = sum(1 for s in valid if (s.strength > 0) == (net > 0)) / len(valid)
    rationale = "; ".join(f"{s.source}:{s.direction}" for s in valid)
    return Signal(
        symbol=symbol,
        source=source,
        direction=direction,
        strength=max(-1.0, min(1.0, net)),
        confidence=round(agree, 3),
        rationale=rationale,
    )

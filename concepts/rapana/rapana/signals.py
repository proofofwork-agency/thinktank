"""Shared signal + market-view data model.

A Signal is the common currency of the fleet: every analyst agent emits one
per symbol, the Bull/Bear researchers aggregate them, and the Portfolio Manager
converts the net score into a trade proposal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass(frozen=True)
class Signal:
    symbol: str
    source: str  # "market" | "sentiment" | "macro" | "arbitrage" | "yield"
    direction: str  # "bullish" | "bearish" | "neutral"
    strength: float  # signed, -1..1 (bullish positive, bearish negative)
    confidence: float  # 0..1
    rationale: str
    extras: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        d = self.direction.lower()
        if d not in {"bullish", "bearish", "neutral"}:
            raise ValueError(f"direction must be bullish/bearish/neutral, got {self.direction!r}")
        object.__setattr__(self, "direction", d)
        object.__setattr__(self, "source", self.source.lower())
        object.__setattr__(self, "strength", _clamp(float(self.strength), -1.0, 1.0))
        object.__setattr__(self, "confidence", _clamp(float(self.confidence), 0.0, 1.0))
        # Keep strength sign consistent with direction label.
        if d == "bullish" and self.strength < 0:
            object.__setattr__(self, "strength", _clamp(abs(self.strength), 0.0, 1.0))
        elif d == "bearish" and self.strength > 0:
            object.__setattr__(self, "strength", _clamp(-abs(self.strength), -1.0, 0.0))
        elif d == "neutral":
            object.__setattr__(self, "strength", 0.0)

    @property
    def weighted_score(self) -> float:
        """strength * confidence — used by the net-score combiner."""
        return self.strength * self.confidence


@dataclass
class MarketView:
    """Blackboard snapshot for a single symbol at a point in time."""

    symbol: str
    price: Decimal
    ref_price: Decimal
    signals: list[Signal] = field(default_factory=list)

    @property
    def net_score(self) -> float:
        """Consensus score in [-1, 1]: confidence-weighted average of signal strength."""
        return combine_signals(self.signals)

    @property
    def consensus(self) -> str:
        score = self.net_score
        if score > 0.15:
            return "bullish"
        if score < -0.15:
            return "bearish"
        return "neutral"


def combine_signals(signals: list[Signal]) -> float:
    """Confidence-weighted net score across heterogeneous sources.

    Neutral signals (strength forced to 0) are excluded entirely: a no-opinion
    signal must not contribute its confidence to the denominator, which would
    otherwise dilute the consensus toward zero.
    """
    contributing = [s for s in signals if s.direction != "neutral"]
    total_weight = sum(s.confidence for s in contributing)
    if total_weight == 0:
        return 0.0
    return sum(s.weighted_score for s in contributing) / total_weight


def weighted_combine(signals: list[Signal], source_weights: dict[str, float] | None = None) -> float:
    """Confidence- AND learned-source-weighted net score (the reflection loop).

    ``source_weights`` maps analyst source -> a multiplier (from ReflectionMemory).
    Sources with no entry default to 1.0. Neutral signals are excluded.
    """
    contributing = [s for s in signals if s.direction != "neutral"]
    if not contributing:
        return 0.0
    if not source_weights:
        return combine_signals(signals)
    denom = 0.0
    score = 0.0
    for s in contributing:
        w = source_weights.get(s.source, 1.0) * s.confidence
        score += s.strength * w
        denom += w
    return score / denom if denom else 0.0

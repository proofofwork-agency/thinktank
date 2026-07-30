from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from rapana.agents.base import Analyst
from rapana.signals import Signal

if TYPE_CHECKING:
    from rapana.fleet.data_provider import DataProvider


class SentimentAnalyst(Analyst):
    """News/social sentiment analyst.

    Sentiment needs an external data feed (paid API). The brain is injectable:
    pass a `sentiment_fn(symbol) -> (score[-1..1], confidence[0..1])`.
    Without one it returns neutral so the fleet stays conservative.
    """

    role = "sentiment_analyst"

    def __init__(self, sentiment_fn: Callable[[str], tuple[float, float]] | None = None) -> None:
        self.sentiment_fn = sentiment_fn

    def analyze(self, symbol: str, provider: DataProvider) -> Signal:
        if self.sentiment_fn is None:
            return Signal(symbol, "sentiment", "neutral", 0.0, 0.0, "no sentiment feed configured")
        score, confidence = self.sentiment_fn(symbol)
        direction = "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral"
        return Signal(symbol, "sentiment", direction, score, confidence, f"sentiment score={score:.2f}")

from __future__ import annotations

from abc import ABC, abstractmethod


class Feed(ABC):
    """External data feed that returns a normalised signal contribution.

    Every feed maps its domain to a (score, confidence) pair:
      score       in [-1, 1]  (bullish positive, bearish negative)
      confidence  in [0, 1]
    Feeds must fail soft: on any error they return (0.0, 0.0) so the fleet
    never blocks on an external outage.
    """

    name: str = "feed"

    @abstractmethod
    def score(self, symbol: str) -> tuple[float, float]:  # pragma: no cover
        ...

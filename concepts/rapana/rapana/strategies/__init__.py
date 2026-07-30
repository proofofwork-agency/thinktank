from __future__ import annotations

from rapana.strategies.base import Strategy
from rapana.strategies.breakout import Breakout
from rapana.strategies.meanrev import MeanReversion
from rapana.strategies.trend import TrendFollowing

__all__ = ["Breakout", "MeanReversion", "Strategy", "TrendFollowing", "all_strategies"]


def all_strategies() -> list[Strategy]:
    return [TrendFollowing(), MeanReversion(), Breakout()]

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from rapana.signals import Signal


class Strategy(ABC):
    """A strategy maps recent OHLCV history to a Signal.

    Strategies are used both by the backtest engine and (optionally) as the
    rule-based core of analyst agents. Anti-lookahead discipline: the caller
    passes a history slice that excludes the bar used for execution.
    """

    name: str = "base"

    @abstractmethod
    def generate(self, df: pd.DataFrame, symbol: str) -> Signal: ...

    @staticmethod
    def _needs(df: pd.DataFrame, min_rows: int) -> bool:
        return len(df) >= min_rows

    @staticmethod
    def _neutral(symbol: str, source: str, rationale: str) -> Signal:
        return Signal(symbol, source, "neutral", 0.0, 0.0, rationale)

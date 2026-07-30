from __future__ import annotations

import pandas as pd

from rapana.indicators import rsi
from rapana.signals import Signal
from rapana.strategies.base import Strategy


class MeanReversion(Strategy):
    """RSI-based mean reversion: oversold -> bullish, overbought -> bearish."""

    name = "meanrev"

    def __init__(self, period: int = 14, oversold: float = 35, overbought: float = 65) -> None:
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate(self, df: pd.DataFrame, symbol: str) -> Signal:
        min_rows = self.period + 5
        if not self._needs(df, min_rows):
            return self._neutral(symbol, "market", f"insufficient history ({len(df)}<{min_rows})")

        r = rsi(df["close"], self.period).iloc[-1]
        if r != r:  # NaN guard
            return self._neutral(symbol, "market", "RSI undefined")

        if r < self.oversold:
            # deeper oversold => stronger reversion
            strength = (self.oversold - r) / self.oversold
            return Signal(symbol, "market", "bullish", min(1.0, strength), 0.5,
                          f"RSI={r:.1f} oversold")
        if r > self.overbought:
            strength = (r - self.overbought) / (100 - self.overbought)
            return Signal(symbol, "market", "bearish", -min(1.0, strength), 0.5,
                          f"RSI={r:.1f} overbought")
        return self._neutral(symbol, "market", f"RSI={r:.1f} neutral")

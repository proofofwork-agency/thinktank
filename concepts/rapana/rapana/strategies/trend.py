from __future__ import annotations

import pandas as pd

from rapana.indicators import atr, ema
from rapana.signals import Signal
from rapana.strategies.base import Strategy


class TrendFollowing(Strategy):
    """EMA(fast) vs EMA(slow) crossover, sized by separation normalised by ATR."""

    name = "trend"

    def __init__(self, fast: int = 20, slow: int = 50) -> None:
        if fast >= slow:
            raise ValueError("fast must be < slow")
        self.fast = fast
        self.slow = slow

    def generate(self, df: pd.DataFrame, symbol: str) -> Signal:
        min_rows = self.slow + 5
        if not self._needs(df, min_rows):
            return self._neutral(symbol, "market", f"insufficient history ({len(df)}<{min_rows})")

        close = df["close"]
        ef = ema(close, self.fast).iloc[-1]
        es = ema(close, self.slow).iloc[-1]
        vol = atr(df).iloc[-1]
        vol = vol if vol and vol > 0 else close.iloc[-1] * 0.01

        sep = (ef - es) / vol  # ATR-normalised separation
        sep = max(-1.0, min(1.0, float(sep) * 2.0))  # scale to ~[-1,1]

        if sep > 0:
            return Signal(
                symbol, "market", "bullish", sep, 0.6,
                f"EMA{self.fast}>{self.slow}, sep={sep:.2f} ATR",
            )
        if sep < 0:
            return Signal(
                symbol, "market", "bearish", sep, 0.6,
                f"EMA{self.fast}<{self.slow}, sep={sep:.2f} ATR",
            )
        return self._neutral(symbol, "market", "EMAs equal")

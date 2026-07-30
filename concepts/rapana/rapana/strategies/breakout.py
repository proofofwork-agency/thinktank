from __future__ import annotations

import pandas as pd

from rapana.indicators import bollinger
from rapana.signals import Signal
from rapana.strategies.base import Strategy


class Breakout(Strategy):
    """Bollinger-band breakout / momentum: close above upper -> bullish, below lower -> bearish."""

    name = "breakout"

    def __init__(self, period: int = 20, std: float = 2.0) -> None:
        self.period = period
        self.std = std

    def generate(self, df: pd.DataFrame, symbol: str) -> Signal:
        min_rows = self.period + 2
        if not self._needs(df, min_rows):
            return self._neutral(symbol, "market", f"insufficient history ({len(df)}<{min_rows})")

        close = df["close"]
        price = close.iloc[-1]
        ma, upper, lower = bollinger(close, self.period, self.std)
        u = upper.iloc[-1]
        lo = lower.iloc[-1]
        m = ma.iloc[-1]
        band = u - lo
        if band != band or band <= 0:  # NaN / zero guard
            return self._neutral(symbol, "market", "bands undefined")

        if price > u:
            strength = min(1.0, (price - u) / (band * 0.5))
            return Signal(symbol, "market", "bullish", strength, 0.55,
                          f"close {price:.2f} > upper band {u:.2f}")
        if price < lo:
            strength = min(1.0, (lo - price) / (band * 0.5))
            return Signal(symbol, "market", "bearish", -strength, 0.55,
                          f"close {price:.2f} < lower band {lo:.2f}")
        # Inside the bands: distance from midline gives weak mean-reversion lean.
        rel = (price - m) / (band / 2)
        if rel > 0.5:
            return Signal(symbol, "market", "bullish", rel * 0.3, 0.3,
                          f"upper-half, rel={rel:.2f}")
        if rel < -0.5:
            return Signal(symbol, "market", "bearish", rel * 0.3, 0.3,
                          f"lower-half, rel={rel:.2f}")
        return self._neutral(symbol, "market", f"inside bands, rel={rel:.2f}")

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from rapana.fleet.data_provider import DataProvider
from rapana.fleet.maker_fill import PaperMakerBar


class ReplayProvider(DataProvider):
    """Point-in-time data provider for historical fleet replay.

    Holds the full OHLCV per symbol but only reveals rows up to a moving cursor,
    so the entire fleet (analysts -> debate -> PM -> risk -> execution) sees
    exactly what it would have seen at that bar. This is the anti-lookahead
    validation harness the plan mandates before any live capital.
    """

    def __init__(self, data: dict[str, pd.DataFrame]) -> None:
        self.data = {k.upper(): v.reset_index(drop=True) for k, v in data.items()}
        self._cursor = 0

    def seek(self, bar: int) -> None:
        self._cursor = max(0, bar)

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def max_bars(self) -> int:
        return max((len(v) for v in self.data.values()), default=0)

    def get_history(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        df = self.data.get(symbol.upper())
        if df is None or df.empty:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        # Reveal only CLOSED bars [0, cursor). The cursor bar is the one being
        # executed (get_price returns its close), so exposing it to the
        # strategy's indicators (.iloc[-1]) would be same-bar lookahead. This
        # mirrors BacktestEngine's one-bar lag so replay validates honestly.
        end = min(self._cursor, len(df))
        start = max(0, end - limit)
        return df.iloc[start:end].reset_index(drop=True)

    def get_price(self, symbol: str) -> Decimal:
        df = self.data.get(symbol.upper())
        if df is None or df.empty or self._cursor >= len(df):
            return Decimal("0")
        return Decimal(str(float(df["close"].iloc[self._cursor])))

    def execution_bar_at(self, symbol: str, index: int) -> PaperMakerBar | None:
        """Return one hidden OHLC bar for replay execution resolution only.

        This deliberately does not change get_history(), which remains the
        point-in-time analyst/PM surface and never reveals the cursor bar.
        """
        df = self.data.get(symbol.upper())
        if df is None or df.empty or index < 0 or index >= len(df):
            return None
        row = df.iloc[index]
        return PaperMakerBar(
            index=index,
            high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])),
        )

    def timestamp(self, symbol: str) -> int:
        df = self.data.get(symbol.upper())
        if df is None or df.empty or self._cursor >= len(df):
            return 0
        return int(df["ts"].iloc[self._cursor])

from __future__ import annotations

import time
from decimal import Decimal

import pandas as pd

from rapana.data.store import TimeSeriesStore
from rapana.logging import get_logger

log = get_logger(__name__)

_BAR_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
}


def _drop_unclosed(rows: list[dict], timeframe: str, now_ms: int | None = None) -> list[dict]:
    """Drop the trailing bar if it has not closed yet (ts + bar_duration > now).

    The live read path must never feed a still-forming candle into indicators —
    that is the same lookahead class replay already guards against. Historical
    reads (now well past the last bar) are unaffected."""
    if not rows:
        return rows
    bar_ms = _BAR_MS.get(timeframe, 3_600_000)
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    last = rows[-1]
    if int(last["ts"]) + bar_ms > now_ms:
        return rows[:-1]
    return rows


class DataProvider:
    """Interface for market-data access used by agents.

    Two implementations: StoreDataProvider (reads ingested OHLCV from SQLite)
    and InMemoryProvider (for tests / deterministic runs).
    """

    def get_history(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        raise NotImplementedError

    def get_price(self, symbol: str) -> Decimal:
        raise NotImplementedError

    def timestamp(self, symbol: str) -> int:
        """Current bar timestamp in ms. Override for deterministic replay."""
        import time

        return int(time.time() * 1000)


class StoreDataProvider(DataProvider):
    def __init__(self, store: TimeSeriesStore, client=None) -> None:
        self.store = store
        self.client = client  # optional MexcClient for live price fetch

    def get_history(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        rows = self.store.fetch_candles(symbol, timeframe, limit=limit)
        rows = _drop_unclosed(rows, timeframe)  # never feed a forming bar to indicators
        if not rows:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        return pd.DataFrame(rows)

    def get_price(self, symbol: str) -> Decimal:
        if self.client is not None:
            try:
                ticker = self.client.fetch_ticker(symbol)
                return Decimal(str(ticker.get("last") or ticker.get("close") or 0))
            except Exception as exc:
                log.warning("live_price_failed", symbol=symbol, error=str(exc))
        rows = self.store.fetch_candles(symbol, "1m", limit=1)
        if rows:
            return Decimal(str(rows[-1]["close"]))
        return Decimal("0")


class InMemoryProvider(DataProvider):
    """Holds a dict of symbol -> DataFrame; ideal for tests and replay."""

    def __init__(self, data: dict[str, pd.DataFrame], prices: dict[str, Decimal] | None = None) -> None:
        self.data = {k.upper(): v for k, v in data.items()}
        self.prices = {k.upper(): v for k, v in (prices or {}).items()}

    def get_history(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        df = self.data.get(symbol.upper(), pd.DataFrame())
        if df.empty:
            return df
        return df.tail(limit).reset_index(drop=True)

    def get_price(self, symbol: str) -> Decimal:
        if symbol.upper() in self.prices:
            return self.prices[symbol.upper()]
        df = self.data.get(symbol.upper())
        if df is not None and not df.empty:
            return Decimal(str(float(df["close"].iloc[-1])))
        return Decimal("0")

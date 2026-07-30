from __future__ import annotations

import time

from rapana.config import Settings, get_settings
from rapana.data.store import TimeSeriesStore
from rapana.logging import get_logger
from rapana.mexc.client import MexcClient, MexcFuturesClient, to_perp_symbol

log = get_logger(__name__)

_TF_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
          "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def _drop_unclosed(
    candles: list[list[int | float]], timeframe: str, now_ms: int | None = None
) -> list[list[int | float]]:
    """Drop the still-forming current candle.

    A bar at ``ts`` covers ``[ts, ts+tf)`` and is only closed once ``now >= ts+tf``.
    Storing an unclosed bar leaks partial future data into backtests/signals.
    """
    if not candles:
        return candles
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    tf = _TF_MS.get(timeframe, 3_600_000)
    return [c for c in candles if int(c[0]) + tf <= now_ms]


class MarketDataIngester:
    """Pulls OHLCV from MEXC into the time-series store for watched symbols."""

    def __init__(
        self,
        client: MexcClient | None = None,
        store: TimeSeriesStore | None = None,
        settings: Settings | None = None,
        timeframe: str = "1h",
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or MexcClient(settings=self.settings)
        self.store = store or TimeSeriesStore(self.settings.db_path)
        self.timeframe = timeframe

    def ingest_symbol(self, symbol: str, limit: int = 500) -> int:
        """Fetch + store recent candles for one symbol. Returns rows written."""
        candles = self.client.fetch_ohlcv(symbol, timeframe=self.timeframe, limit=limit)
        candles = _drop_unclosed(candles, self.timeframe)
        written = self.store.upsert_candles(symbol, self.timeframe, candles)
        log.info(
            "ingested_candles",
            symbol=symbol,
            timeframe=self.timeframe,
            rows=written,
        )
        return written

    def ingest_all(self, limit: int = 500, symbols: list[str] | None = None) -> dict[str, int]:
        """Ingest each symbol (default: watched). Returns {symbol: rows_written}."""
        results: dict[str, int] = {}
        for symbol in symbols or self.settings.watch_symbols:
            try:
                results[symbol] = self.ingest_symbol(symbol, limit=limit)
            except Exception as exc:
                log.error("ingest_failed", symbol=symbol, error=str(exc))
                results[symbol] = 0
        return results

    def ingest_history(
        self,
        symbol: str,
        *,
        since: int | None = None,
        until: int | None = None,
        limit: int = 500,
        max_pages: int | None = None,
    ) -> int:
        """Paginate deep history into the store. Returns rows written.

        When ``since`` is omitted it resumes from the newest stored candle so
        repeated runs only fetch what is new (idempotent via INSERT OR REPLACE).
        """
        if since is None:
            last = self.store.last_timestamp(symbol, self.timeframe)
            if last is not None:
                since = last + 1
        candles = self.client.fetch_ohlcv_history(
            symbol,
            timeframe=self.timeframe,
            since=since,
            until=until,
            limit=limit,
            max_pages=max_pages,
        )
        candles = _drop_unclosed(candles, self.timeframe)
        written = self.store.upsert_candles(symbol, self.timeframe, candles)
        log.info("ingested_history", symbol=symbol, timeframe=self.timeframe, rows=written)
        return written

    def ingest_all_history(
        self,
        *,
        since: int | None = None,
        until: int | None = None,
        limit: int = 500,
        max_pages: int | None = None,
        symbols: list[str] | None = None,
    ) -> dict[str, int]:
        """Paginate deep history for each symbol (default: watched). Returns {symbol: rows}."""
        results: dict[str, int] = {}
        for symbol in symbols or self.settings.watch_symbols:
            try:
                results[symbol] = self.ingest_history(
                    symbol, since=since, until=until, limit=limit, max_pages=max_pages
                )
            except Exception as exc:
                log.error("ingest_history_failed", symbol=symbol, error=str(exc))
                results[symbol] = 0
        return results


class FundingIngester:
    """Pulls perpetual funding-rate history from MEXC into the store (carry C1).

    Funding history is public, so the underlying client is unauthenticated by
    default — no futures key is required to ingest (that is gated to C4 live).
    Funding is keyed by the *perp* symbol (e.g. ``BTC/USDT:USDT``) so spot and
    perp series never collide.
    """

    def __init__(
        self,
        client: MexcFuturesClient | None = None,
        store: TimeSeriesStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or MexcFuturesClient(settings=self.settings)
        self.store = store or TimeSeriesStore(self.settings.db_path)

    def ingest_symbol(
        self,
        symbol: str,
        *,
        since: int | None = None,
        until: int | None = None,
        limit: int = 200,
        max_pages: int | None = None,
    ) -> int:
        """Fetch + store funding history for one symbol. Returns rows written.

        When ``since`` is omitted it resumes from the newest stored funding row
        so repeated runs only fetch what is new (idempotent via INSERT OR REPLACE).
        """
        perp = to_perp_symbol(symbol)
        if since is None:
            last = self.store.last_funding_timestamp(perp)
            if last is not None:
                since = last + 1
        rows = self.client.fetch_funding_rate_history(
            perp, since=since, until=until, limit=limit, max_pages=max_pages
        )
        written = self.store.upsert_funding(perp, rows)
        log.info("ingested_funding", symbol=perp, rows=written)
        return written

    def ingest_all(
        self,
        *,
        since: int | None = None,
        until: int | None = None,
        limit: int = 200,
        max_pages: int | None = None,
        symbols: list[str] | None = None,
    ) -> dict[str, int]:
        """Ingest funding for each symbol (default: watched). Returns {perp_symbol: rows}."""
        results: dict[str, int] = {}
        for symbol in symbols or self.settings.watch_symbols:
            perp = to_perp_symbol(symbol)
            try:
                results[perp] = self.ingest_symbol(
                    symbol, since=since, until=until, limit=limit, max_pages=max_pages
                )
            except Exception as exc:
                log.error("ingest_funding_failed", symbol=perp, error=str(exc))
                results[perp] = 0
        return results

"""Tests for D1: paginated OHLCV history + store range reader. No network."""
from __future__ import annotations

from rapana.data.store import TimeSeriesStore
from rapana.mexc.client import MexcClient

HOUR = 3_600_000


def _candles(n: int, start: int = 0) -> list[list[float]]:
    return [[start + i * HOUR, 100 + i, 101 + i, 99 + i, 100.5 + i, 10] for i in range(n)]


class _SliceExchange:
    """Mimics a real exchange: returns candles >= since, capped at limit."""

    def __init__(self, candles: list[list[float]], tf_seconds: int = 3600) -> None:
        self._candles = sorted(candles, key=lambda c: c[0])
        self._tf = tf_seconds
        self.markets: dict = {}
        self.calls: list[int | None] = []

    def load_markets(self) -> dict:
        return self.markets

    def parse_timeframe(self, timeframe: str) -> int:
        return self._tf

    def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=500):
        self.calls.append(since)
        rows = self._candles if since is None else [c for c in self._candles if c[0] >= since]
        return [list(c) for c in rows[:limit]]


def _client(exchange) -> MexcClient:
    client = MexcClient(authenticated=False)
    client.exchange = exchange  # type: ignore[assignment]
    return client


def test_history_paginates_all_pages_ascending_deduped():
    fake = _SliceExchange(_candles(1200))
    got = _client(fake).fetch_ohlcv_history("BTC/USDT", "1h", since=0, limit=500)
    assert [c[0] for c in got] == [i * HOUR for i in range(1200)]  # ascending, complete
    assert len(fake.calls) == 3  # 500 + 500 + 200 (short page stops)


def test_history_respects_max_pages():
    fake = _SliceExchange(_candles(1200))
    got = _client(fake).fetch_ohlcv_history("BTC/USDT", "1h", since=0, limit=500, max_pages=2)
    assert len(fake.calls) == 2
    assert len(got) == 1000


def test_history_respects_until_bound():
    fake = _SliceExchange(_candles(1200))
    got = _client(fake).fetch_ohlcv_history("BTC/USDT", "1h", since=0, until=500 * HOUR, limit=500)
    assert got[-1][0] == 500 * HOUR
    assert len(got) == 501  # ts 0..500 inclusive


def test_history_since_none_fetches_single_page():
    fake = _SliceExchange(_candles(1200))
    got = _client(fake).fetch_ohlcv_history("BTC/USDT", "1h", since=None, limit=500)
    assert len(fake.calls) == 1  # no wasted forward/future request
    assert len(got) == 500


class _OverlapExchange:
    """Two pages with an overlapping candle to exercise de-dup + short-page stop."""

    def __init__(self) -> None:
        self.markets: dict = {}
        self.calls: list[int | None] = []
        self._pages = [
            [[0, 1, 1, 1, 1, 1], [HOUR, 1, 1, 1, 1, 1], [2 * HOUR, 1, 1, 1, 1, 1]],
            [[2 * HOUR, 1, 1, 1, 1, 1], [3 * HOUR, 1, 1, 1, 1, 1]],  # overlaps 2*HOUR, short
        ]

    def load_markets(self):
        return self.markets

    def parse_timeframe(self, timeframe):
        return 3600

    def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=500):
        i = len(self.calls)
        self.calls.append(since)
        return [list(c) for c in (self._pages[i] if i < len(self._pages) else [])]


def test_history_dedupes_overlapping_pages():
    fake = _OverlapExchange()
    got = _client(fake).fetch_ohlcv_history("X/USDT", "1h", since=0, limit=3)
    assert [c[0] for c in got] == [0, HOUR, 2 * HOUR, 3 * HOUR]  # 2*HOUR appears once
    assert len(fake.calls) == 2


class _FrozenExchange:
    """Always returns the same full page — must NOT loop forever."""

    def __init__(self) -> None:
        self.markets: dict = {}
        self.calls: list[int | None] = []

    def load_markets(self):
        return self.markets

    def parse_timeframe(self, timeframe):
        return 3600

    def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=500):
        self.calls.append(since)
        return [[0, 1, 1, 1, 1, 1], [HOUR, 1, 1, 1, 1, 1], [2 * HOUR, 1, 1, 1, 1, 1]]


def test_history_stuck_page_guard_terminates():
    fake = _FrozenExchange()
    got = _client(fake).fetch_ohlcv_history("X/USDT", "1h", since=0, limit=3)
    assert len(fake.calls) == 2  # second identical page trips the guard
    assert [c[0] for c in got] == [0, HOUR, 2 * HOUR]


def test_fetch_candles_range_roundtrip(tmp_path):
    store = TimeSeriesStore(tmp_path / "t.db")
    store.upsert_candles("BTC/USDT", "1h", _candles(10))

    allc = store.fetch_candles_range("BTC/USDT", "1h")
    assert len(allc) == 10
    ts = [r["ts"] for r in allc]
    assert ts == sorted(ts)

    sub = store.fetch_candles_range("BTC/USDT", "1h", since=3 * HOUR, until=5 * HOUR)
    assert [r["ts"] for r in sub] == [3 * HOUR, 4 * HOUR, 5 * HOUR]

    store.upsert_candles("BTC/USDT", "1h", _candles(10))  # re-upsert is idempotent
    assert len(store.fetch_candles_range("BTC/USDT", "1h")) == 10


def test_fetch_candles_range_empty_when_until_before_since(tmp_path):
    store = TimeSeriesStore(tmp_path / "t.db")
    store.upsert_candles("BTC/USDT", "1h", _candles(10))
    assert store.fetch_candles_range("BTC/USDT", "1h", since=8 * HOUR, until=2 * HOUR) == []


class _IgnoreSinceExchange:
    """Exchange that ignores ``since`` — exercises the defensive lower-bound filter."""

    def __init__(self, candles: list[list[float]]) -> None:
        self._candles = candles
        self.markets: dict = {}

    def load_markets(self):
        return self.markets

    def parse_timeframe(self, timeframe):
        return 3600

    def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=500):
        return [list(c) for c in self._candles[:limit]]


def test_history_filters_rows_before_since():
    fake = _IgnoreSinceExchange(_candles(20))
    got = _client(fake).fetch_ohlcv_history("X/USDT", "1h", since=5 * HOUR, limit=500)
    assert got and all(c[0] >= 5 * HOUR for c in got)
    assert len(got) == 15  # ts 5..19 inclusive


class _RecordingClient:
    """Captures the ``since`` the ingester forwards, to verify resume logic."""

    def __init__(self) -> None:
        self.last_since: int | None | str = "unset"

    def fetch_ohlcv_history(self, symbol, timeframe="1h", *, since=None, until=None,
                            limit=500, max_pages=None):
        self.last_since = since
        return []


def test_ingest_history_resumes_from_last_timestamp(tmp_path):
    from rapana.data.ingest import MarketDataIngester

    store = TimeSeriesStore(tmp_path / "t.db")
    store.upsert_candles("BTC/USDT", "1h", _candles(5))  # newest stored ts = 4*HOUR
    client = _RecordingClient()
    ingester = MarketDataIngester(client=client, store=store, timeframe="1h")
    ingester.ingest_history("BTC/USDT")
    assert client.last_since == 4 * HOUR + 1  # resumed just past the newest stored bar


def test_drop_unclosed_filters_forming_bar():
    from rapana.data.ingest import _drop_unclosed

    candles = [[0, 1, 1, 1, 1, 1], [HOUR, 1, 1, 1, 1, 1], [2 * HOUR, 1, 1, 1, 1, 1]]
    # now is partway through the 2*HOUR bar -> it has not closed yet, drop it
    kept = _drop_unclosed(candles, "1h", now_ms=2 * HOUR + HOUR // 2)
    assert [c[0] for c in kept] == [0, HOUR]
    # once now passes 3*HOUR, the 2*HOUR bar is closed and kept
    assert len(_drop_unclosed(candles, "1h", now_ms=3 * HOUR)) == 3
    assert _drop_unclosed([], "1h", now_ms=3 * HOUR) == []

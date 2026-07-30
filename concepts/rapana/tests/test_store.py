from __future__ import annotations

from rapana.data.store import TimeSeriesStore


def test_upsert_and_fetch(tmp_path):
    store = TimeSeriesStore(tmp_path / "t.db")
    candles = [
        [1700000000000, 100.0, 101.0, 99.0, 100.5, 10.0],
        [1700000060000, 100.5, 102.0, 100.0, 101.5, 12.0],
    ]
    written = store.upsert_candles("BTC/USDT", "1h", candles)
    assert written == 2

    rows = store.fetch_candles("btc/usdt", "1h")  # case-insensitive
    assert len(rows) == 2
    assert rows[0]["close"] == 100.5
    assert rows[1]["close"] == 101.5  # ascending order
    assert store.last_timestamp("BTC/USDT", "1h") == 1700000060000


def test_upsert_is_idempotent(tmp_path):
    store = TimeSeriesStore(tmp_path / "t.db")
    candle = [[1700000000000, 100.0, 101.0, 99.0, 100.5, 10.0]]
    store.upsert_candles("ETH/USDT", "1h", candle)
    store.upsert_candles("ETH/USDT", "1h", candle)  # duplicate -> replace
    assert len(store.fetch_candles("ETH/USDT", "1h")) == 1


def test_meta_roundtrip(tmp_path):
    store = TimeSeriesStore(tmp_path / "t.db")
    store.set_meta("last_run", "12345")
    assert store.get_meta("last_run") == "12345"
    assert store.get_meta("missing") is None


def test_macro_series_roundtrip(tmp_path):
    store = TimeSeriesStore(tmp_path / "t.db")
    rows = [{"ts": 86_400_000, "value": 12}, {"ts": 2 * 86_400_000, "value": 88}]
    assert store.upsert_macro_series("fear_greed", rows) == 2
    assert store.upsert_macro_series("fear_greed", rows) == 2  # idempotent
    got = store.fetch_macro_series("fear_greed")
    assert got == [{"ts": 86_400_000, "value": 12.0}, {"ts": 172_800_000, "value": 88.0}]
    assert store.fetch_macro_series("fear_greed", since=172_800_000) == [
        {"ts": 172_800_000, "value": 88.0}
    ]
    assert store.fetch_macro_series("does_not_exist") == []

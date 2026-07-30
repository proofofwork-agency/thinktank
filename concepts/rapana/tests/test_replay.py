from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

from rapana.fleet.replay import ReplayProvider


def _df(n=100, start=100.0):
    price = start + np.arange(n)  # strictly increasing so price(cursor) is unique
    ts = np.arange(n) * 3600_000
    return pd.DataFrame({
        "ts": ts, "open": price, "high": price + 1, "low": price - 1,
        "close": price, "volume": 1000.0,
    })


def test_point_in_time_history_grows_with_cursor():
    provider = ReplayProvider({"BTC/USDT": _df()})
    provider.seek(10)
    h10 = provider.get_history("BTC/USDT", "1h", 250)
    assert len(h10) == 10  # CLOSED bars [0,10); the cursor bar #10 is not revealed
    provider.seek(50)
    h50 = provider.get_history("BTC/USDT", "1h", 250)
    assert len(h50) == 50
    # No same-bar lookahead: newest visible close (#49=149) precedes the
    # execution price (cursor bar #50 close = 150).
    assert float(h50["close"].iloc[-1]) == 149.0
    assert provider.get_price("BTC/USDT") == Decimal("150")


def test_execution_bar_accessor_does_not_change_point_in_time_history():
    provider = ReplayProvider({"BTC/USDT": _df()})
    provider.seek(10)

    bar = provider.execution_bar_at("BTC/USDT", 10)
    history = provider.get_history("BTC/USDT", "1h", 250)

    assert bar is not None
    assert bar.index == 10
    assert bar.high == Decimal("111.0")
    assert bar.low == Decimal("109.0")
    assert len(history) == 10
    assert float(history["close"].iloc[-1]) == 109.0


def test_price_tracks_cursor():
    provider = ReplayProvider({"BTC/USDT": _df()})
    provider.seek(5)
    assert provider.get_price("BTC/USDT") == Decimal("105")
    provider.seek(0)
    assert provider.get_price("BTC/USDT") == Decimal("100")


def test_limit_respected():
    provider = ReplayProvider({"BTC/USDT": _df(100)})
    provider.seek(80)
    h = provider.get_history("BTC/USDT", "1h", 20)
    assert len(h) == 20
    assert float(h["close"].iloc[-1]) == 179.0  # bars [60,80); cursor bar #80 excluded


def test_max_bars_and_timestamp():
    provider = ReplayProvider({"BTC/USDT": _df(100)})
    assert provider.max_bars == 100
    provider.seek(7)
    assert provider.timestamp("BTC/USDT") == 7 * 3600_000

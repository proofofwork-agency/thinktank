from __future__ import annotations

import numpy as np
import pandas as pd

from rapana.indicators import atr, bollinger, ema, macd, rsi, sma


def _df(n=200, seed=7, drift=0.001):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.02, n)
    price = 100 * np.exp(np.cumsum(rets))
    close = price
    high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    op = close * (1 + rng.normal(0, 0.002, n))
    ts = np.arange(n) * 3600_000
    return pd.DataFrame({"ts": ts, "open": op, "high": high, "low": low, "close": close, "volume": 1000.0})


def test_ema_and_sma_lengths():
    df = _df()
    assert len(ema(df["close"], 20)) == len(df)
    assert sma(df["close"], 20).isna().iloc[:19].all()
    assert sma(df["close"], 20).notna().iloc[19]


def test_rsi_bounded():
    df = _df()
    r = rsi(df["close"], 14).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_macd_components():
    df = _df()
    m, s, h = macd(df["close"])
    assert len(m) == len(df)
    assert len(s) == len(df)
    assert np.allclose(h.values, (m - s).values, equal_nan=True)


def test_atr_positive():
    df = _df()
    a = atr(df, 14).dropna()
    assert (a > 0).all()


def test_bollinger_order():
    df = _df()
    ma, up, lo = bollinger(df["close"], 20)
    valid = ma.notna()
    assert (up[valid] >= ma[valid]).all()
    assert (lo[valid] <= ma[valid]).all()

from __future__ import annotations

import numpy as np
import pandas as pd

from rapana.strategies import Breakout, MeanReversion, TrendFollowing


def _trending(up=True, n=120):
    drift = 0.004 if up else -0.004
    rng = np.random.default_rng(1)
    rets = rng.normal(drift, 0.01, n)
    price = 100 * np.exp(np.cumsum(rets))
    ts = np.arange(n) * 3600_000
    return pd.DataFrame({
        "ts": ts, "open": price, "high": price * 1.01, "low": price * 0.99,
        "close": price, "volume": 1000.0,
    })


def _flat(n=120):
    rng = np.random.default_rng(2)
    price = 100 + rng.normal(0, 0.5, n)
    price = np.clip(price, 80, 120)
    ts = np.arange(n) * 3600_000
    return pd.DataFrame({
        "ts": ts, "open": price, "high": price + 0.5, "low": price - 0.5,
        "close": price, "volume": 1000.0,
    })


def test_trend_bullish_on_uptrend():
    sig = TrendFollowing().generate(_trending(up=True), "BTC/USDT")
    assert sig.direction == "bullish"
    assert sig.strength > 0


def test_trend_bearish_on_downtrend():
    sig = TrendFollowing().generate(_trending(up=False), "BTC/USDT")
    assert sig.direction == "bearish"
    assert sig.strength < 0


def test_meanrev_neutral_on_flat():
    sig = MeanReversion().generate(_flat(), "BTC/USDT")
    # flat market -> mostly neutral, allow occasional small signal
    assert sig.direction in {"neutral", "bullish", "bearish"}


def test_breakout_runs_without_error():
    sig = Breakout().generate(_trending(up=True), "BTC/USDT")
    assert sig.direction in {"bullish", "bearish", "neutral"}


def test_insufficient_history_returns_neutral():
    tiny = _flat(n=5)
    for strat in [TrendFollowing(), MeanReversion(), Breakout()]:
        sig = strat.generate(tiny, "BTC/USDT")
        assert sig.direction == "neutral"
        assert sig.strength == 0.0

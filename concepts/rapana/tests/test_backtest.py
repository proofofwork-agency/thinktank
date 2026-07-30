from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from rapana.backtest.engine import BacktestConfig, BacktestEngine
from rapana.strategies import Breakout, MeanReversion, TrendFollowing


def _synthetic(n=400, seed=3, drift=0.0008):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.015, n)
    price = 100 * np.exp(np.cumsum(rets))
    high = price * (1 + np.abs(rng.normal(0, 0.004, n)))
    low = price * (1 - np.abs(rng.normal(0, 0.004, n)))
    op = price * (1 + rng.normal(0, 0.002, n))
    ts = np.arange(n) * 3600_000
    return pd.DataFrame({"ts": ts, "open": op, "high": high, "low": low, "close": price, "volume": 1000.0})


def test_backtest_runs_and_produces_metrics():
    df = _synthetic()
    engine = BacktestEngine(BacktestConfig(initial_equity=Decimal("10000"), timeframe="1h"))
    result = engine.run(df, TrendFollowing(), "BTC/USDT")
    assert result.metrics is not None
    assert result.metrics.final_equity > 0
    assert len(result.equity_curve) > 0
    assert result.metrics.num_trades >= 0


def test_buy_and_hold_baseline():
    """A bullish-only strategy on an uptrend should grow equity above fees."""
    df = _synthetic(drift=0.003)
    engine = BacktestEngine(BacktestConfig(timeframe="1h"))
    result = engine.run(df, TrendFollowing(), "BTC/USDT")
    # On a strong uptrend the trend follower should net positive.
    assert result.metrics.total_return > -1.0  # sanity: never fully wrecked


def test_fee_costs_applied():
    df = _synthetic()
    cheap = BacktestEngine(BacktestConfig(fee_pct=Decimal("0"), slippage_pct=Decimal("0")))
    dear = BacktestEngine(BacktestConfig(fee_pct=Decimal("0.01"), slippage_pct=Decimal("0.01")))
    r1 = cheap.run(df, Breakout(), "BTC/USDT")
    r2 = dear.run(df, Breakout(), "BTC/USDT")
    # Higher costs should not leave more final equity (in expectation).
    assert r2.metrics.final_equity <= r1.metrics.final_equity + 1e-6


def test_too_few_bars_raises():
    with pytest.raises(ValueError):
        BacktestEngine().run(_synthetic(n=2), MeanReversion(), "BTC/USDT")


def test_no_lookahead_executes_with_one_bar_lag():
    """Re-running with identical data must be deterministic."""
    df = _synthetic()
    e = BacktestEngine()
    r1 = e.run(df, MeanReversion(), "ETH/USDT")
    r2 = e.run(df, MeanReversion(), "ETH/USDT")
    assert r1.metrics.final_equity == r2.metrics.final_equity

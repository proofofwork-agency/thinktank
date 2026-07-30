"""Tests for D2: walk-forward validation harness + Deflated Sharpe Ratio."""
from __future__ import annotations

import math
from decimal import Decimal

import pandas as pd

from rapana.backtest.engine import BacktestConfig
from rapana.backtest.metrics import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from rapana.backtest.validation import make_test_folds, validate_config, validate_grid
from rapana.signals import Signal
from rapana.strategies import Breakout, MeanReversion, TrendFollowing
from rapana.strategies.base import Strategy

HOUR = 3_600_000


# ---- Probabilistic / Deflated Sharpe (pure functions) ---------------------
def test_psr_zero_sharpe_is_half():
    assert abs(probabilistic_sharpe_ratio(0.0, 0.0, 1000) - 0.5) < 1e-6


def test_psr_positive_and_negative():
    assert probabilistic_sharpe_ratio(0.05, 0.0, 1000) > 0.9
    assert probabilistic_sharpe_ratio(-0.05, 0.0, 1000) < 0.1
    # monotonic in the observed Sharpe
    assert probabilistic_sharpe_ratio(0.05, 0.0, 1000) > probabilistic_sharpe_ratio(0.02, 0.0, 1000)


def test_expected_max_sharpe_grows_with_trials():
    assert expected_max_sharpe(0.01, 1) == 0.0       # <2 trials → no inflation
    assert expected_max_sharpe(0.0, 50) == 0.0       # no variance → no inflation
    assert expected_max_sharpe(0.01, 50) > expected_max_sharpe(0.01, 5) > 0.0


def test_deflated_sharpe_penalizes_more_trials():
    few = deflated_sharpe_ratio(0.05, sharpe_variance=4e-4, n_trials=3, n_obs=2000)
    many = deflated_sharpe_ratio(0.05, sharpe_variance=4e-4, n_trials=200, n_obs=2000)
    assert 0.0 <= many <= few <= 1.0
    assert few > many  # trying more configs makes the same result less credible


# ---- Walk-forward fold construction ---------------------------------------
def test_make_test_folds_tiles_after_warmup():
    folds = make_test_folds(1000, 6, 60)
    assert len(folds) == 6
    assert folds[0] == (0, 60, 216)          # fold 0 engine_start clamped to 0
    assert folds[-1] == (780, 840, 1000)     # last fold runs to the end
    for k in range(len(folds) - 1):
        assert folds[k][2] == folds[k + 1][1]            # contiguous, no gaps
    for _es, ts, _te in folds[1:]:
        assert ts - _es == 60                            # full warmup lookback


def test_make_test_folds_empty_when_too_short():
    assert make_test_folds(60, 6, 60) == []  # nothing left after warmup


# ---- Harness end-to-end on deterministic data -----------------------------
def _wavy_uptrend(n: int = 600) -> pd.DataFrame:
    close = [100 * (1.0008 ** i) * (1 + 0.01 * math.sin(i / 5.0)) for i in range(n)]
    return pd.DataFrame({
        "ts": [i * HOUR for i in range(n)],
        "open": close,
        "high": [c * 1.002 for c in close],
        "low": [c * 0.998 for c in close],
        "close": close,
        "volume": [10.0] * n,
    })


def test_validate_grid_produces_report():
    data = {"BTC/USDT": _wavy_uptrend()}
    strategies = {"trend": TrendFollowing, "meanrev": MeanReversion, "breakout": Breakout}
    report = validate_grid(data, strategies, n_splits=4, warmup=60, timeframe="1h")

    assert report.n_trials == 3
    assert report.best is not None
    assert 0.0 <= report.deflated_sharpe <= 1.0
    assert report.is_significant == (report.deflated_sharpe > 0.95)
    for c in report.configs:
        assert c.folds              # each config produced folds
        assert c.n_obs >= 2
        assert 0.0 <= c.pct_folds_positive <= 1.0


def test_validate_grid_single_trial():
    data = {"BTC/USDT": _wavy_uptrend()}
    report = validate_grid(data, {"trend": TrendFollowing}, n_splits=4, warmup=60, timeframe="1h")
    assert report.n_trials == 1
    assert report.best is not None
    assert 0.0 <= report.deflated_sharpe <= 1.0


class _AlwaysLong(Strategy):
    name = "alwayslong"

    def generate(self, df, symbol):
        return Signal(symbol, "test", "bullish", 1.0, 1.0, "always long")


def test_oos_includes_first_bar_return():
    """Regression: the first OOS bar's move/cost must be counted, not dropped.

    Flat warmup, a +10% jump on the FIRST OOS bar, then flat. With fees/slippage
    off an always-long book is ~95% invested entering the window, so the jump must
    show up in the OOS return. The old boundary (starting AT the first OOS bar)
    dropped it and reported ~0%.
    """
    warmup = 5
    prices = [100.0] * warmup + [110.0] * 10  # bar `warmup` is the first OOS bar
    df = pd.DataFrame({
        "ts": [i * HOUR for i in range(len(prices))],
        "open": prices, "high": prices, "low": prices, "close": prices,
        "volume": [10.0] * len(prices),
    })
    cfg = BacktestConfig(timeframe="1h", fee_pct=Decimal("0"), slippage_pct=Decimal("0"))
    res = validate_config(df, _AlwaysLong, "X/USDT", n_splits=1, warmup=warmup,
                          timeframe="1h", config=cfg)
    assert res is not None
    assert res.oos_return > 0.08   # ~95% of +10% captured, not ~0
    assert res.n_obs == 10         # one return per OOS bar (first bar included)


def test_holdout_split_reserves_final_fraction():
    from rapana.backtest.validation import holdout_split
    df = _wavy_uptrend(100)
    wf, hold = holdout_split(df, 0.2, warmup=10)
    assert len(wf) == 80                                        # first 80%
    assert int(hold["ts"].iloc[0]) == int(df["ts"].iloc[70])   # keeps 10 warmup bars
    assert int(hold["ts"].iloc[-1]) == int(df["ts"].iloc[-1])  # runs to the end
    assert int(wf["ts"].iloc[-1]) < int(df["ts"].iloc[80])     # WF never sees the holdout


def test_hodl_oos_return_positive_on_uptrend():
    from rapana.backtest.validation import hodl_oos_return
    assert hodl_oos_return(_wavy_uptrend(), n_splits=4, warmup=60) > 0


def test_report_has_hodl_and_passed_card():
    report = validate_grid({"BTC/USDT": _wavy_uptrend()}, {"trend": TrendFollowing},
                           n_splits=4, warmup=60, timeframe="1h")
    assert isinstance(report.hodl_return, float)
    # PASS requires BOTH statistical significance and beating buy-and-hold.
    assert report.passed == (report.is_significant and report.best.oos_return > report.hodl_return)


def test_vol_scale_gives_calmer_markets_more_exposure():
    from rapana.backtest.engine import BacktestConfig, BacktestEngine
    calm = pd.DataFrame({"close": [100.0 + 0.2 * (i % 2) for i in range(40)]})    # tiny wiggle
    wild = pd.DataFrame({"close": [100.0 + 10.0 * (i % 2) for i in range(40)]})   # big wiggle
    cfg = BacktestConfig(timeframe="1d", vol_target=0.5)
    assert BacktestEngine._vol_scale(calm, cfg) > BacktestEngine._vol_scale(wild, cfg)
    assert BacktestEngine._vol_scale(calm, BacktestConfig(timeframe="1d")) == 1.0  # off by default


def test_target_value_scaled_by_vol():
    from decimal import Decimal

    from rapana.backtest.engine import BacktestConfig, BacktestEngine
    from rapana.signals import Signal
    sig = Signal("X/USDT", "test", "bullish", 1.0, 1.0, "")
    cfg = BacktestConfig(max_weight=0.95)
    full = BacktestEngine._target_value(sig, cfg, Decimal("10000"), Decimal("0"), Decimal("100"), 1.0)
    half = BacktestEngine._target_value(sig, cfg, Decimal("10000"), Decimal("0"), Decimal("100"), 0.5)
    assert half < full  # halving vol_scale halves the target exposure


def test_vol_targeting_stays_long_only():
    from decimal import Decimal

    from rapana.backtest.engine import BacktestConfig, BacktestEngine
    from rapana.signals import Signal
    df = pd.DataFrame({"close": [100.0 + (i % 2) for i in range(40)]})
    # Non-positive / non-finite vol targets are treated as OFF (no negative scaling).
    assert BacktestEngine._vol_scale(df, BacktestConfig(timeframe="1d", vol_target=-0.5)) == 1.0
    assert BacktestEngine._vol_scale(df, BacktestConfig(timeframe="1d", vol_target=0.0)) == 1.0
    assert BacktestEngine._vol_scale(df, BacktestConfig(timeframe="1d", vol_target=float("nan"))) == 1.0
    assert BacktestEngine._vol_scale(df, BacktestConfig(timeframe="1d", vol_target=float("inf"))) == 1.0
    # Even a negative scale can never create a short (weight clamped to >= 0).
    sig = Signal("X/USDT", "test", "bullish", 1.0, 1.0, "")
    v = BacktestEngine._target_value(sig, BacktestConfig(), Decimal("10000"), Decimal("0"),
                                     Decimal("100"), -2.0)
    assert v >= 0

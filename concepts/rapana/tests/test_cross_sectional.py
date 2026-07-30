"""Tests for cross-sectional rotation validation."""
from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from rapana.backtest.cross_sectional import (
    CrossSectionalSpec,
    equal_weight_hodl_oos_return,
    simulate_cross_sectional,
    validate_cross_sectional_config,
)
from rapana.backtest.engine import BacktestConfig

DAY = 86_400_000


def _df(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "ts": [i * DAY for i in range(len(closes))],
        "open": closes,
        "high": closes,
        "low": closes,
        "close": closes,
        "volume": [10_000.0] * len(closes),
    })


def test_rotation_rank_uses_prior_close_not_execution_bar():
    """BBB moonshots on the execution bar, but the rank must still pick AAA.

    With L=2 at bar 3, prior-close momentum is:
      AAA: close[2] / close[0] - 1 = +21%
      BBB: close[2] / close[0] - 1 = 0%

    A lookahead bug using close[3] would pick BBB and capture the +100% jump.
    """
    data = {
        "AAA/USDT": _df([100.0, 110.0, 121.0, 121.0, 121.0]),
        "BBB/USDT": _df([100.0, 100.0, 100.0, 200.0, 200.0]),
    }
    cfg = BacktestConfig(fee_pct=Decimal("0"), max_weight=1.0)
    sim = simulate_cross_sectional(
        data,
        CrossSectionalSpec("momentum", lookback=2, top_k=1, rebalance=1),
        config=cfg,
    )

    execution_ts = 3 * DAY
    assert sim.holdings[execution_ts] == ("AAA/USDT",)
    assert sim.returns.loc[execution_ts] == pytest.approx(0.0)


def test_validate_cross_sectional_config_returns_config_and_hodl():
    data = {
        "AAA/USDT": _df([100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 122]),
        "BBB/USDT": _df([100, 99, 98, 97, 96, 95, 96, 97, 98, 99, 100, 101]),
    }
    cfg = BacktestConfig(timeframe="1d", fee_pct=Decimal("0"), max_weight=1.0)
    result, hodl = validate_cross_sectional_config(
        data,
        signal="momentum",
        lookback=2,
        top_k=1,
        rebalance=1,
        n_splits=2,
        warmup=3,
        timeframe="1d",
        config=cfg,
    )

    assert result is not None
    assert result.symbol == "UNIVERSE"
    assert result.strategy == "xs-momentum-L2-K1-R1"
    assert result.folds
    assert result.n_obs >= 2
    assert hodl == pytest.approx(equal_weight_hodl_oos_return(data, n_splits=2, warmup=3))


def test_cross_sectional_uses_real_common_timestamps_without_filling():
    data = {
        "AAA/USDT": _df([100, 101, 102, 103]),
        "BBB/USDT": _df([100, 101, 102, 103]).assign(ts=[DAY, 2 * DAY, 3 * DAY, 4 * DAY]),
    }

    sim = simulate_cross_sectional(
        data,
        CrossSectionalSpec("momentum", lookback=1, top_k=1, rebalance=1),
    )
    assert list(sim.returns.index) == [2 * DAY, 3 * DAY]


def test_cross_sectional_fails_when_no_common_price_grid():
    data = {
        "AAA/USDT": _df([100, 101, 102]),
        "BBB/USDT": _df([100, 101, 102]).assign(ts=[10 * DAY, 11 * DAY, 12 * DAY]),
    }

    with pytest.raises(ValueError, match="no common candle timestamps"):
        simulate_cross_sectional(
            data,
            CrossSectionalSpec("momentum", lookback=1, top_k=1, rebalance=1),
        )

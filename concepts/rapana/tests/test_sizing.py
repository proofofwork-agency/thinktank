from __future__ import annotations

import pandas as pd

from rapana.backtest.engine import BacktestConfig, BacktestEngine
from rapana.sizing import BARS_PER_YEAR, vol_scale


def test_sizing_vol_scale_matches_backtest_engine_wrapper():
    closes = [100.0 + (i % 3) * 0.5 + i * 0.1 for i in range(50)]
    cfg = BacktestConfig(timeframe="1h", vol_target=0.35, vol_lookback=20)
    history = pd.DataFrame({"close": closes})

    shared = vol_scale(
        closes,
        vol_target=cfg.vol_target,
        lookback=cfg.vol_lookback,
        bars_per_year=BARS_PER_YEAR[cfg.timeframe],
    )

    assert shared == BacktestEngine._vol_scale(history, cfg)


def test_sizing_vol_scale_increases_on_calm_windows_and_decreases_on_turbulent_ones():
    calm = [100.0 + 0.2 * (i % 2) for i in range(40)]
    turbulent = [100.0 + 10.0 * (i % 2) for i in range(40)]

    calm_scale = vol_scale(calm, vol_target=0.5, lookback=20, bars_per_year=BARS_PER_YEAR["1d"])
    turbulent_scale = vol_scale(
        turbulent, vol_target=0.5, lookback=20, bars_per_year=BARS_PER_YEAR["1d"],
    )

    assert calm_scale > turbulent_scale
    assert vol_scale(calm, vol_target=None, lookback=20, bars_per_year=BARS_PER_YEAR["1d"]) == 1.0

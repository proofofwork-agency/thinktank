from __future__ import annotations

import math
from typing import Any

import pandas as pd

# Approx bars per year by timeframe (crypto trades 24/7).
BARS_PER_YEAR = {
    "1m": 60 * 24 * 365,
    "5m": 12 * 24 * 365,
    "15m": 4 * 24 * 365,
    "30m": 2 * 24 * 365,
    "1h": 24 * 365,
    "4h": 6 * 365,
    "1d": 365,
}


def vol_scale(
    closes: Any,
    *,
    vol_target: float | None,
    lookback: int,
    bars_per_year: int,
) -> float:
    """Return the volatility-targeting multiplier used by backtest and live sizing."""
    if vol_target is None or not math.isfinite(vol_target) or vol_target <= 0:
        return 1.0
    rets = pd.Series(closes, dtype="float64").pct_change().tail(lookback).dropna()
    rv = float(rets.std()) if len(rets) >= 2 else 0.0
    if not math.isfinite(rv) or rv <= 0:
        return 1.0
    annual_vol = rv * math.sqrt(bars_per_year)
    return vol_target / annual_vol if annual_vol > 1e-9 else 1.0

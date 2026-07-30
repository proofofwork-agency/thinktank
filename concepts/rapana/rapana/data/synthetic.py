"""Synthetic OHLCV generator for offline decision-backtesting.

Lets you run the full fleet through `replay` with no MEXC key, so you can see
the decision-making work immediately. The series use regime-switching drift
(up -> correction -> up) so trend and mean-reversion strategies both get
something realistic to chew on. NOT a market model — only a smoke surface.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_BASE_PRICES = {"BTC": 60000.0, "ETH": 3000.0, "SOL": 150.0}


def make_synthetic_ohlcv(
    symbols: list[str],
    bars: int = 500,
    seed: int = 42,
    timeframe_ms: int = 3_600_000,
) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for i, symbol in enumerate(symbols):
        rng = np.random.default_rng(seed + i)
        base = symbol.upper().split("/")[0]
        price0 = _BASE_PRICES.get(base, 100.0 * (1 + i))
        rets = rng.normal(0.0, 0.015, bars)
        third = max(1, bars // 3)
        rets[:third] += 0.0035            # uptrend regime
        rets[third: 2 * third] -= 0.0025  # correction regime
        rets[2 * third:] += 0.0025        # recovery regime
        close = price0 * np.exp(np.cumsum(rets))
        high = close * (1 + np.abs(rng.normal(0, 0.004, bars)))
        low = close * (1 - np.abs(rng.normal(0, 0.004, bars)))
        op = close * (1 + rng.normal(0, 0.002, bars))
        ts = np.arange(1, bars + 1) * timeframe_ms
        out[symbol.upper()] = pd.DataFrame({
            "ts": ts, "open": op, "high": high, "low": low,
            "close": close, "volume": 1000.0,
        })
    return out

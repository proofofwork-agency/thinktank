"""Tests for the pure universe ranker (no network)."""
from __future__ import annotations

import math

import pandas as pd

from rapana.universe.ranker import (
    UniverseParams,
    liquidity,
    rank_universe,
    select_symbols,
)

HOUR = 3_600_000


def _df(closes: list[float], dollar_volume: float = 1_000_000.0) -> pd.DataFrame:
    """OHLCV where close*volume == dollar_volume every bar (median is exact)."""
    n = len(closes)
    vols = [dollar_volume / c for c in closes]
    return pd.DataFrame({
        "ts": [i * HOUR for i in range(n)],
        "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": vols,
    })


def _trend(n: int, rate: float, start: float = 100.0, dollar_volume: float = 1_000_000.0):
    return _df([start * ((1 + rate) ** i) for i in range(n)], dollar_volume)


def test_liquidity_is_daily_normalized_median():
    df = _df([100.0] * 40, dollar_volume=750_000.0)
    assert liquidity(df, 20, bars_per_day=1) == 750_000.0
    assert liquidity(df, 20, bars_per_day=24) == 750_000.0 * 24


def test_ranks_by_risk_adjusted_momentum():
    params = UniverseParams(top_n=2, min_quote_volume_usd=1.0, momentum_lookback=20)
    cands = {
        "AAA/USDT": _trend(60, 0.01),    # strong momentum
        "BBB/USDT": _trend(60, 0.001),   # weak momentum
        "CCC/USDT": _trend(60, -0.01),   # negative momentum
    }
    ranked = rank_universe(cands, params)
    assert [r.symbol for r in ranked] == ["AAA/USDT", "BBB/USDT"]
    assert ranked[0].score > ranked[1].score


def test_liquidity_screen_excludes_thin_coins():
    params = UniverseParams(top_n=5, min_quote_volume_usd=500_000.0, momentum_lookback=20)
    cands = {
        "LIQ/USDT": _trend(60, 0.005, dollar_volume=1_000_000.0),  # above floor
        "THIN/USDT": _trend(60, 0.02, dollar_volume=1_000.0),      # best momentum, too thin
    }
    assert select_symbols(cands, params) == ["LIQ/USDT"]  # THIN screened out


def test_deterministic_tie_break_by_symbol():
    params = UniverseParams(top_n=2, min_quote_volume_usd=1.0, momentum_lookback=20)
    cands = {"ZZZ/USDT": _trend(60, 0.01), "AAA/USDT": _trend(60, 0.01)}  # identical
    assert select_symbols(cands, params) == ["AAA/USDT", "ZZZ/USDT"]


def test_insufficient_history_skipped():
    params = UniverseParams(top_n=5, min_quote_volume_usd=1.0, momentum_lookback=20)
    cands = {"OK/USDT": _trend(60, 0.01), "SHORT/USDT": _trend(5, 0.01)}
    assert select_symbols(cands, params) == ["OK/USDT"]


def test_nan_dollar_volume_excluded():
    # Valid close (finite momentum) but NaN volume -> NaN dollar-volume must NOT
    # slip the liquidity screen (nan < floor is False).
    closes = [100.0 * (1.01 ** i) for i in range(40)]
    df = pd.DataFrame({
        "ts": [i * HOUR for i in range(40)],
        "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": [float("nan")] * 40,
    })
    params = UniverseParams(top_n=5, min_quote_volume_usd=1.0, momentum_lookback=20)
    assert rank_universe({"NANV/USDT": df}, params) == []


def test_flat_series_no_div_by_zero():
    params = UniverseParams(top_n=5, min_quote_volume_usd=1.0, momentum_lookback=20)
    ranked = rank_universe({"FLAT/USDT": _df([100.0] * 60, 1_000_000.0)}, params)
    assert len(ranked) == 1
    assert math.isfinite(ranked[0].score)
    assert ranked[0].score == 0.0  # zero momentum, no crash

"""Tests for P2: point-in-time universe validation (the anti-lookahead proof)."""
from __future__ import annotations

import pandas as pd

from rapana.backtest.engine import BacktestConfig
from rapana.signals import Signal
from rapana.strategies.base import Strategy
from rapana.universe.ranker import UniverseParams, select_symbols
from rapana.universe.validation import (
    _fold_oos_returns_ts,
    _hodl_basket,
    select_universe_pit,
    validate_universe,
)

DAY = 86_400_000


def _piecewise(segments: list[tuple[int, float]]) -> list[float]:
    closes, price = [], 100.0
    for n, rate in segments:
        for _ in range(n):
            price *= 1 + rate
            closes.append(price)
    return closes


def _df(closes: list[float]) -> pd.DataFrame:
    n = len(closes)
    return pd.DataFrame({
        "ts": [i * DAY for i in range(n)],
        "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": [10_000.0] * n,
    })


def _candidates() -> dict[str, pd.DataFrame]:
    # AAA leads early, BBB leads mid, CCC moonshots LATE (the look-ahead trap).
    return {
        "AAA/USDT": _df(_piecewise([(15, 0.03), (45, 0.0)])),
        "BBB/USDT": _df(_piecewise([(15, 0.0), (15, 0.03), (30, 0.0)])),
        "CCC/USDT": _df(_piecewise([(45, 0.0), (15, 0.20)])),
    }


_PARAMS = UniverseParams(top_n=1, min_quote_volume_usd=1.0, momentum_lookback=10, bars_per_day=1)


def test_pit_selection_uses_only_pre_fold_data():
    cands = _candidates()
    # The winner changes across time, chosen from PRE-fold data only.
    assert select_universe_pit(cands, _PARAMS, 15 * DAY) == ["AAA/USDT"]
    assert select_universe_pit(cands, _PARAMS, 30 * DAY) == ["BBB/USDT"]


def test_pit_cannot_see_the_future_spike():
    cands = _candidates()
    # Naive full-data ranking is fooled by CCC's late moonshot...
    assert select_symbols(cands, _PARAMS)[0] == "CCC/USDT"
    # ...but point-in-time selection at bar 15 cannot see bars >= 15, so it
    # correctly picks the pre-fold leader and NOT the future winner.
    assert select_universe_pit(cands, _PARAMS, 15 * DAY) == ["AAA/USDT"]


class _AlwaysLong(Strategy):
    name = "alwayslong"

    def generate(self, df, symbol):
        return Signal(symbol, "test", "bullish", 1.0, 1.0, "always long")


def test_fold_oos_returns_are_timestamp_indexed():
    # The fix: returns keep their bar TIMESTAMP as index (not ordinal 0..n) so
    # baskets align by date. Reverting to reset_index(drop=True) fails this.
    df = _df(_piecewise([(40, 0.01)]))
    r = _fold_oos_returns_ts(df, 0, 10 * DAY, 40 * DAY, _AlwaysLong, "X/USDT",
                             BacktestConfig(timeframe="1d"))
    assert len(r) > 0
    assert list(r.index) == sorted(r.index)
    assert all(t % DAY == 0 and t >= 10 * DAY for t in r.index)  # timestamps, not ordinals


def test_validate_universe_handles_ragged_histories():
    # Two symbols on OFFSET timelines (B starts 30 bars later) selected together;
    # the ts-aligned basket must run without misaligning by ordinal position.
    a = _df(_piecewise([(90, 0.01)]))                    # bars 0..89
    b = _df(_piecewise([(90, 0.0)])).iloc[30:].reset_index(drop=True)  # ts 30..89
    cands = {"A/USDT": a, "B/USDT": b}
    params = UniverseParams(top_n=2, min_quote_volume_usd=1.0, momentum_lookback=10, bars_per_day=1)
    report = validate_universe(cands, _AlwaysLong, params, n_splits=3, warmup=20,
                               timeframe="1d", benchmark_symbols=["A/USDT"])
    assert report.scout is not None
    assert report.n_candidates == 2


def test_validate_universe_runs_scout_and_benchmark():
    cands = _candidates()
    cfg = BacktestConfig(timeframe="1d")
    report = validate_universe(
        cands, _AlwaysLong, _PARAMS, n_splits=3, warmup=20, timeframe="1d",
        config=cfg, benchmark_symbols=["AAA/USDT"],
    )
    assert report.scout is not None
    assert report.benchmark is not None
    assert report.n_candidates == 3
    assert 0.0 <= report.deflated_sharpe <= 1.0
    assert report.is_significant == (report.deflated_sharpe > 0.95)
    assert "SURVIVORSHIP" in report.survivorship_warning
    assert report.best_label in {"scout", "fixed"}
    assert isinstance(report.hodl_return, float)
    assert isinstance(report.passed, bool)


def test_hodl_basket_includes_first_oos_bar():
    # A's price doubles on the FIRST OOS bar; HODL must reflect ~+100%, not 0%
    # (anchoring at the first OOS bar instead of the bar before would drop it).
    cands = {"A/USDT": _df([100.0] * 10 + [200.0] * 10)}
    ref_ts = [i * DAY for i in range(20)]
    hodl = _hodl_basket(cands, ["A/USDT"], ref_ts, [(0, 10, 20)])
    assert hodl > 0.9  # the first-OOS-bar move is captured

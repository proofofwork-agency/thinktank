from __future__ import annotations

import math
from decimal import Decimal  # noqa: F401  (kept for parity with sibling tests)

import numpy as np
import pandas as pd
import pytest

from rapana.triggers.base import Trigger, TriggerEvent
from rapana.triggers.ohlcv_triggers import (
    DEFAULT_TRIGGER_MANIFEST,
    DEFAULT_TRIGGER_MANIFEST_VERSION,
    DEFAULT_TRIGGERS,
    BreakoutFade,
    BreakoutLong,
    GapFade,
    GapMomentum,
    RsiExtreme,
    VolumeSpikeMomentum,
)
from rapana.triggers.study import (
    _non_overlapping,
    _oos_forward_nets,
    run_hunt,
    run_pooled_hunt,
    solo_skill_dsr,
    study_trigger,
    study_trigger_pooled,
)


def _df(closes, volumes=None):
    n = len(closes)
    ts = [i * 3_600_000 for i in range(n)]
    if volumes is None:
        volumes = [1000.0] * n
    return pd.DataFrame({
        "ts": ts, "open": closes, "high": closes, "low": closes,
        "close": closes, "volume": volumes,
    })


class _EveryBarLong(Trigger):
    name = "every_bar_long"
    horizon_bars = 2

    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        return [TriggerEvent(i, 1) for i in range(len(df) - 3)]


class _ScheduledLong(Trigger):
    name = "scheduled_long"
    horizon_bars = 1

    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        return [TriggerEvent(i, 1) for i in range(0, len(df) - 2, 4)]


def test_forward_return_math_long_and_short():
    df = _df([100.0, 100.0, 110.0, 120.0, 130.0, 140.0])
    # folds(6, n_splits=2, warmup=1) -> fold0 covers bars [1,3); event at bar 1.
    # entry=close[2]=110, exit=close[4]=130 (H=2) -> +18.18%.
    long_nets = _oos_forward_nets(
        df, [TriggerEvent(1, 1)], horizon=2, fee_per_side=0.0,
        slippage_per_side=0.0, n_splits=2, warmup=1,
    )
    assert len(long_nets) == 1
    assert long_nets[0] == pytest.approx(130 / 110 - 1.0, rel=1e-9)
    short_nets = _oos_forward_nets(
        df, [TriggerEvent(1, -1)], horizon=2, fee_per_side=0.0,
        slippage_per_side=0.0, n_splits=2, warmup=1,
    )
    assert short_nets[0] == pytest.approx(-(130 / 110 - 1.0), rel=1e-9)


def test_forward_return_subtracts_round_trip_cost():
    df = _df([100.0, 100.0, 110.0, 120.0, 130.0, 140.0])
    nets = _oos_forward_nets(
        df, [TriggerEvent(1, 1)], horizon=2, fee_per_side=0.001,
        slippage_per_side=0.0, n_splits=2, warmup=1,
    )
    assert nets[0] == pytest.approx(130 / 110 - 1.0 - 2 * 0.001, rel=1e-9)


def test_event_outside_oos_window_is_not_scored():
    df = _df([100.0, 100.0, 110.0, 120.0, 130.0, 140.0])
    # bar 0 is in the warmup (warmup=1 -> fold0 starts at bar 1) -> not scored.
    nets = _oos_forward_nets(
        df, [TriggerEvent(0, 1)], horizon=2, fee_per_side=0.0,
        slippage_per_side=0.0, n_splits=2, warmup=1,
    )
    assert nets == []


def test_gap_fade_fades_outsized_move():
    df = _df([100.0, 100.0, 105.0])  # bar 2: +5% > 3% threshold
    evs = GapFade(threshold=0.03, horizon_bars=1).detect(df)
    assert [(e.bar, e.direction) for e in evs] == [(2, -1)]


def test_gap_momentum_rides_outsized_move():
    df = _df([100.0, 100.0, 105.0])  # bar 2: +5% -> ride long (mirror of GapFade)
    evs = GapMomentum(threshold=0.03, horizon_bars=1).detect(df)
    assert [(e.bar, e.direction) for e in evs] == [(2, 1)]


def test_default_trigger_manifest_is_dated_versioned_and_documented():
    assert DEFAULT_TRIGGER_MANIFEST_VERSION == "2026-06-24.v1"
    assert tuple(entry.trigger for entry in DEFAULT_TRIGGER_MANIFEST) == DEFAULT_TRIGGERS
    assert len(DEFAULT_TRIGGER_MANIFEST) == 9
    assert all(entry.committed_on == "2026-06-24" for entry in DEFAULT_TRIGGER_MANIFEST)
    assert all(entry.rationale for entry in DEFAULT_TRIGGER_MANIFEST)


def test_fear_greed_extreme_fires_once_per_day():
    from rapana.triggers.macro_triggers import FearGreedExtreme

    fg = [{"ts": d * 86_400_000, "value": v} for d, v in [(0, 10), (1, 90), (2, 50)]]
    # two bars on day 0 (only the first should fire), one on day 1, one on day 2
    ts = [0, 3_600_000, 86_400_000, 2 * 86_400_000]
    df = pd.DataFrame({"ts": ts, "close": [100.0, 100.0, 100.0, 100.0]})
    evs = FearGreedExtreme(fg, low=25.0, high=75.0, horizon_bars=1).detect(df)
    assert [(e.bar, e.direction) for e in evs] == [(0, 1), (2, -1)]  # fear->long, greed->short


def _fdf(funding, close=100.0):
    n = len(funding)
    return pd.DataFrame({
        "ts": [i * 28_800_000 for i in range(n)],
        "close": [close] * n,
        "funding": funding,
    })


def test_funding_flip_momentum_and_fade():
    from rapana.triggers.funding_triggers import FundingFlip

    df = _fdf([-0.001, -0.001, 0.001, 0.001])
    mom = FundingFlip(horizon_intervals=1, mode="momentum").detect(df)
    fade = FundingFlip(horizon_intervals=1, mode="fade").detect(df)
    assert [(e.bar, e.direction) for e in mom] == [(2, 1)]   # neg->pos flip, ride long
    assert [(e.bar, e.direction) for e in fade] == [(2, -1)]  # fade the flip


def test_funding_persistent_fades_sustained_crowd():
    from rapana.triggers.funding_triggers import FundingPersistent

    df = _fdf([0.0001, 0.0004, 0.0005, 0.0006])
    evs = FundingPersistent(k=3, threshold=0.0003, horizon_intervals=1).detect(df)
    # window ending at i=2 contains 0.0001 (<=thr) -> skip; i=3 -> all >thr, same sign -> fade
    assert [(e.bar, e.direction) for e in evs] == [(3, -1)]


def test_volume_spike_momentum_rides_direction():
    vols = [100.0 + (i % 5) for i in range(25)] + [1000.0]
    closes = [100.0 + i for i in range(26)]  # rising -> bar 25 up
    df = _df(closes, vols)
    evs = VolumeSpikeMomentum(z=2.0, lookback=20, horizon_bars=1).detect(df)
    assert any(e.bar == 25 and e.direction == 1 for e in evs)


def test_breakout_long_and_fade_diverge():
    df = _df([100.0] * 20 + [101.0])  # bar 20 breaks the 20-bar high
    longs = BreakoutLong(lookback=20, horizon_bars=1).detect(df)
    fades = BreakoutFade(lookback=20, horizon_bars=1).detect(df)
    assert any(e.bar == 20 and e.direction == 1 for e in longs)
    assert any(e.bar == 20 and e.direction == -1 for e in fades)


def test_rsi_extreme_overbought_short_oversold_long():
    up = RsiExtreme(14, 30, 70, 1).detect(_df([100.0 + i for i in range(40)]))
    assert up and all(e.direction == -1 for e in up)  # overbought -> fade short
    dn = RsiExtreme(14, 30, 70, 1).detect(_df([200.0 - i for i in range(40)]))
    assert dn and all(e.direction == 1 for e in dn)   # oversold -> bounce long


def test_study_trigger_returns_none_when_no_events():
    df = _df([100.0] * 50)  # flat -> no gap fades
    assert study_trigger(
        df, GapFade(0.03, 2), "BTC/USDT", n_splits=3, warmup=5,
        fee_per_side=0.0, slippage_per_side=0.0, bars_per_year=24 * 365,
    ) is None


def test_study_trigger_de_overlaps_per_symbol_events_before_scoring():
    df = _df([100.0 + i for i in range(12)])
    trigger = _EveryBarLong()
    raw_events = trigger.detect(df)
    independent_events = _non_overlapping(raw_events, trigger.horizon_bars)

    v = study_trigger(
        df, trigger, "BTC/USDT", n_splits=1, warmup=0,
        fee_per_side=0.0, slippage_per_side=0.0, bars_per_year=365,
    )

    assert v is not None
    assert v.n_oos == len(independent_events)
    assert v.n_oos < len(raw_events)


def test_run_hunt_assigns_dsr_and_structures_report():
    rng = np.random.default_rng(0)
    n = 300
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n)))
    df = _df(list(float(x) for x in closes))
    triggers = [GapFade(0.02, 3), RsiExtreme(14, 30, 70, 4)]
    report = run_hunt(
        {"BTC/USDT": df}, triggers, timeframe="1h",
        n_splits=4, warmup=20, min_oos=5,
    )
    assert report.n_trials <= 2
    for v in report.verdicts:
        assert v.n_oos >= 5
        assert v.deflated_sharpe >= 0.0      # net (beats-cash) DSR assigned post-hoc
        assert v.deflated_skill_sharpe >= 0.0  # drift-adjusted skill DSR assigned
        assert 0.0 <= v.win_rate <= 1.0
    # best, if any, is the highest-skill-DSR verdict
    if report.verdicts:
        assert report.best is report.verdicts[0]
    assert report.survivors == []
    assert report.passed is False
    assert report.pass_eligible is False


def test_run_hunt_per_symbol_high_skill_is_exploratory_not_pass():
    closes = []
    for _ in range(80):
        closes.extend([100.0, 100.0, 110.0, 100.0])
    report = run_hunt(
        {"BTC/USDT": _df(closes)}, [_ScheduledLong()], timeframe="1h",
        n_splits=1, warmup=0, min_oos=5, dsr_threshold=0.95,
        fee_per_side=0.0, slippage_per_side=0.0,
    )

    assert report.best is not None
    assert report.best.deflated_skill_sharpe > 0.95
    assert report.survivors == []
    assert report.passed is False
    assert report.pass_eligible is False


def test_drift_correction_neutralizes_pure_uptrend():
    # A deterministic uptrend: any long-only trigger "beats cash" but has ZERO
    # skill — its entries are no better than random. drift must equal the gross
    # mean, so excess ~= 0 and the skill Sharpe collapses.
    closes = [100.0 * (1.001 ** i) for i in range(400)]
    df = _df(closes)
    v = study_trigger(df, BreakoutLong(lookback=10, horizon_bars=5), "X",
                      n_splits=4, warmup=20, fee_per_side=0.0,
                      slippage_per_side=0.0, bars_per_year=365)
    assert v is not None
    assert v.drift > 0.0            # there IS drift (secular uptrend)
    assert v.mean_net > 0.0         # ...so beating cash is trivial
    assert abs(v.excess) < 1e-6     # but there is NO skill over random entry
    assert v.excess_sharpe_bar <= 1e-6


def test_solo_skill_dsr_orders_by_excess_sharpe():
    from rapana.triggers.study import TriggerVerdict

    def _mk(excess_sharpe, n_oos=200):
        return TriggerVerdict(
            symbol="X", trigger="t", horizon_bars=1, n_events=n_oos, n_oos=n_oos,
            mean_net=0.0, median_net=0.0, sharpe_bar=0.0, sharpe_annual=0.0,
            skew=0.0, kurtosis=3.0, win_rate=0.5, oos_return=0.0, worst_event=0.0,
            excess_sharpe_bar=excess_sharpe,
        )

    pos = solo_skill_dsr(_mk(0.5, n_oos=200))
    neg = solo_skill_dsr(_mk(-0.5, n_oos=200))
    assert 0.0 <= pos <= 1.0
    assert pos > 0.9   # strong positive excess Sharpe over 200 obs is almost certainly real
    assert neg < 0.1


def test_hunt_parser_defaults():
    from rapana.cli import build_parser

    args = build_parser().parse_args(["hunt"])
    assert args.timeframe == "1h"
    assert args.splits == 6
    assert args.fee == 0.0002
    assert args.dsr == 0.95
    assert args.func.__name__ == "_cmd_hunt"


def test_hunt_cli_runs_on_stored_data(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_WATCH_SYMBOLS", "BTC/USDT")
    monkeypatch.setenv("RAPANA_DB_PATH", str(tmp_path / "t.db"))
    from rapana.config import get_settings

    get_settings.cache_clear()
    try:
        from rapana.cli import build_parser
        from rapana.data.store import TimeSeriesStore

        store = TimeSeriesStore(tmp_path / "t.db")
        rng = np.random.default_rng(1)
        n = 300
        closes = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
        rows = [
            [int(i * 3_600_000), float(closes[i]), float(closes[i]),
             float(closes[i]), float(closes[i]), 1000.0 + (i % 7) * 10.0]
            for i in range(n)
        ]
        store.upsert_candles("BTC/USDT", "1h", rows)

        args = build_parser().parse_args(["hunt", "--min-events", "3"])
        assert args.func(args) == 0
        out = capsys.readouterr().out
        assert "Trigger hunt" in out
        assert "VERDICT:" in out
    finally:
        get_settings.cache_clear()


def test_non_overlapping_drops_events_within_horizon():
    evs = [TriggerEvent(0, 1), TriggerEvent(1, 1), TriggerEvent(5, 1), TriggerEvent(6, -1)]
    assert [e.bar for e in _non_overlapping(evs, horizon=4)] == [0, 5]
    assert [e.bar for e in _non_overlapping(evs, horizon=5)] == [0, 6]


def test_study_trigger_pooled_merges_symbols():
    rng = np.random.default_rng(7)
    n = 200
    df1 = _df(list(100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, n)))))
    df2 = _df(list(100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, n)))))
    trig = GapFade(0.03, 3)
    single1 = study_trigger(df1, trig, "A", n_splits=4, warmup=20, fee_per_side=0.0,
                            slippage_per_side=0.0, bars_per_year=24 * 365)
    single2 = study_trigger(df2, trig, "B", n_splits=4, warmup=20, fee_per_side=0.0,
                            slippage_per_side=0.0, bars_per_year=24 * 365)
    pooled = study_trigger_pooled({"A": df1, "B": df2}, trig, n_splits=4, warmup=20,
                                  fee_per_side=0.0, slippage_per_side=0.0, bars_per_year=24 * 365)
    assert pooled is not None
    assert pooled.symbol == "ALL"
    # pooled de-overlaps per symbol first, so it can only be <= the raw sum
    upper = (single1.n_oos if single1 else 0) + (single2.n_oos if single2 else 0)
    assert pooled.n_oos <= upper
    assert pooled.n_oos >= 2
    assert math.isfinite(pooled.mean_net)


def test_run_pooled_hunt_one_trial_per_trigger():
    rng = np.random.default_rng(3)
    n = 200
    data = {
        "A": _df(list(100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, n))))),
        "B": _df(list(100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, n))))),
    }
    triggers = [GapFade(0.03, 3), RsiExtreme(14, 30, 70, 4)]
    report = run_pooled_hunt(data, triggers, timeframe="1h", n_splits=4, warmup=20, min_oos=3)
    assert report.n_trials <= len(triggers)  # at most one verdict per trigger
    for v in report.verdicts:
        assert v.symbol == "ALL"


def test_hunt_pooled_cli_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_WATCH_SYMBOLS", "BTC/USDT")
    monkeypatch.setenv("RAPANA_DB_PATH", str(tmp_path / "t.db"))
    from rapana.config import get_settings

    get_settings.cache_clear()
    try:
        from rapana.cli import build_parser
        from rapana.data.store import TimeSeriesStore

        store = TimeSeriesStore(tmp_path / "t.db")
        rng = np.random.default_rng(5)
        n = 250
        closes = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.015, n)))
        rows = []
        for i in range(n):
            c = float(closes[i])
            rows.append([int(i * 3_600_000), c, c, c, c, 1000.0 + (i % 5) * 10.0])
        store.upsert_candles("BTC/USDT", "1h", rows)

        args = build_parser().parse_args(["hunt", "--pooled", "--min-events", "3"])
        assert args.func(args) == 0
        out = capsys.readouterr().out
        assert "pooled" in out
        assert "VERDICT:" in out
    finally:
        get_settings.cache_clear()

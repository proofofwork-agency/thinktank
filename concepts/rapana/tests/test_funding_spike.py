"""Tests for the funding-spike reversion event study (event-driven track, study #1).

Synthetic fixtures exercise the mechanics (join, fade signs, costs, point-in-time,
PASS/FAIL verdict). The real-data verdict is produced by the CLI on ingested MEXC
funding + price — never on synthetic data.
"""
from __future__ import annotations

import pytest

from rapana.backtest.funding_spike import (
    DEFAULT_POLICIES,
    FundingSpikeConfig,
    FundingSpikePolicy,
    align_funding_price,
    simulate_funding_spike,
    validate_funding_spike_config,
    validate_funding_spike_grid,
)

INTERVAL = 8 * 3600 * 1000  # MEXC funds every 8h
BASE = 1_600_000_000_000


def _funding(rates: list[float], base: int = BASE) -> list[dict[str, float]]:
    return [{"ts": base + i * INTERVAL, "funding_rate": r} for i, r in enumerate(rates)]


def _closes_from_returns(start: float, rets: list[float]) -> list[float]:
    """First close = start, then apply each return: close[i] = close[i-1]*(1+ret)."""
    out = [start]
    for r in rets:
        out.append(out[-1] * (1.0 + r))
    return out


# ---- align_funding_price: point-in-time join ------------------------------
def test_align_uses_last_close_at_or_before_funding_and_drops_unpriced():
    candles = [
        {"ts": 100, "close": 10.0},
        {"ts": 200, "close": 20.0},
        {"ts": 300, "close": 30.0},
    ]
    funding = [
        {"ts": 50, "funding_rate": 0.001},   # before first candle -> dropped
        {"ts": 150, "funding_rate": 0.001},  # -> close 10 (ts100, nearest prior)
        {"ts": 200, "funding_rate": 0.001},  # -> close 20 (exact)
        {"ts": 350, "funding_rate": 0.001},  # -> close 30 (ts300)
    ]
    kept, closes = align_funding_price(funding, candles)
    assert [r["ts"] for r in kept] == [150, 200, 350]
    assert closes == [10.0, 20.0, 30.0]


def test_align_empty_inputs():
    assert align_funding_price([], [{"ts": 1, "close": 1.0}]) == ([], [])
    assert align_funding_price([{"ts": 1, "funding_rate": 0.0}], []) == ([], [])


# ---- simulate: fade direction, funding earned, costs, point-in-time -------
def test_fade_positive_funding_is_a_short_that_profits_on_a_drop():
    """Positive funding (crowded longs) -> short; a price drop + funding both pay."""
    cfg = FundingSpikeConfig(fee_pct=0.0, slippage_pct=0.0)
    close = [100.0, 99.0, 98.01]  # -1% then -1%
    out = simulate_funding_spike([0.002, 0.002, 0.002], close, threshold=0.0, cfg=cfg)
    assert out[0] == (0.0, 0.0, 0.0, 0.0)             # interval 0: no prior funding -> flat
    net, price_pnl, funding_pnl, cost = out[1]
    assert price_pnl == pytest.approx(0.01)           # short gains on the -1% move
    assert funding_pnl == pytest.approx(0.002)        # short RECEIVES positive funding
    assert net == pytest.approx(0.012) and cost == 0.0


def test_fade_negative_funding_is_a_long_that_earns_funding():
    cfg = FundingSpikeConfig(fee_pct=0.0, slippage_pct=0.0)
    out = simulate_funding_spike([-0.002, -0.002], [100.0, 101.0], threshold=0.0, cfg=cfg)
    net, price_pnl, funding_pnl, _cost = out[1]
    assert price_pnl == pytest.approx(0.01)           # long gains on the +1% move
    assert funding_pnl == pytest.approx(0.002)        # long RECEIVES negative funding
    assert net == pytest.approx(0.012)


def test_threshold_is_point_in_time():
    """The position for interval t uses funding settled BEFORE t, never t's own."""
    cfg = FundingSpikeConfig(fee_pct=0.0, slippage_pct=0.0)
    out = simulate_funding_spike(
        [0.0, 0.002, 0.002], [100.0, 99.0, 98.0], threshold=0.001, cfg=cfg
    )
    assert out[0][1] == 0.0   # interval 0: no prior funding -> flat
    assert out[1][1] == 0.0   # interval 1: prior funding 0.0 <= 1bp -> still flat
    assert out[2][1] > 0.0    # interval 2: prior 2bp > 1bp -> short, price fell -> profit


def test_entry_charged_once_and_flip_charges_two_sides():
    cfg = FundingSpikeConfig(fee_pct=0.0005, slippage_pct=0.0005)  # per_side = 0.001
    # flat price isolates cost; funding flips sign at idx2 so the fade flips at idx3.
    out = simulate_funding_spike(
        [0.002, 0.002, -0.002, -0.002], [100.0, 100.0, 100.0, 100.0],
        threshold=0.001, cfg=cfg,
    )
    assert out[1][3] == pytest.approx(0.001)   # entry: one side
    assert out[2][3] == 0.0                     # still short (prev funding +) -> no cost
    assert out[3][3] == pytest.approx(0.002)   # flip short->long: two sides


# ---- validation: pooled OOS + PASS / FAIL verdict -------------------------
def test_validate_config_pools_oos_on_clean_reversion():
    rets = [-(0.006 if i % 2 else 0.004) for i in range(160)]  # steady decline, varied
    close = _closes_from_returns(100.0, rets)            # len 161
    funding = _funding([0.002] * 161)                    # persistent crowded longs
    cr = validate_funding_spike_config(
        funding, close, "BTC/USDT:USDT", FundingSpikePolicy("fade|f|>0", 0.0),
        n_splits=4, warmup=8, cfg=FundingSpikeConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    assert cr is not None and cr.folds and cr.n_obs >= 2
    assert cr.oos_return > 0          # fading the crowd into a decline is profitable
    assert cr.gross_price > 0         # reversion (price) contributed
    assert cr.gross_funding > 0       # funding earned on the short
    assert cr.n_events > 0            # the fade was actually on


def test_grid_passes_when_fade_beats_cash():
    rets = [-(0.006 if i % 2 else 0.004) for i in range(220)]
    close = _closes_from_returns(100.0, rets)
    funding = _funding([0.002] * len(close))
    report = validate_funding_spike_grid(
        {"BTC/USDT:USDT": (funding, close)},
        n_splits=6, warmup=8, cfg=FundingSpikeConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    assert report.n_trials == len(DEFAULT_POLICIES)
    assert report.best is not None
    assert 0.0 <= report.deflated_sharpe <= 1.0
    assert report.best.oos_return > 0
    assert report.passed is True
    assert report.passed == (report.is_significant and report.best.oos_return > report.cash_return)


def test_grid_fails_below_honest_cash_floor():
    rets = [-0.00015 for _ in range(220)]
    close = _closes_from_returns(100.0, rets)
    funding = _funding([0.000001] * len(close))
    report = validate_funding_spike_grid(
        {"BTC/USDT:USDT": (funding, close)},
        n_splits=6, warmup=8, cfg=FundingSpikeConfig(fee_pct=0.0, slippage_pct=0.0),
        cash_return=0.035,
    )
    assert report.cash_return == 0.035
    assert report.best is not None
    assert 0.0 < report.best.oos_return < report.cash_return
    assert report.is_significant is True
    assert report.passed is False


def test_grid_fails_on_momentum_funding_positive_but_price_keeps_rising():
    """Crowded longs but price KEEPS rising (no reversion): the fade is short into a
    rally — it loses on price, even though it still earns funding. Must FAIL."""
    rets = [(0.006 if i % 2 else 0.004) for i in range(220)]  # steady rally
    close = _closes_from_returns(100.0, rets)
    funding = _funding([0.0025] * len(close))                 # > every threshold
    report = validate_funding_spike_grid(
        {"BTC/USDT:USDT": (funding, close)},
        n_splits=6, warmup=8, cfg=FundingSpikeConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    assert report.best is not None
    by_policy = {c.policy: c for c in report.configs}
    fade = by_policy["fade|f|>0"]
    assert fade.gross_price < 0       # shorting a rally loses on price
    assert fade.gross_funding > 0     # ...but still harvests funding (disguised carry)
    assert fade.oos_return < 0        # net loses
    assert report.passed is False     # no reversion edge -> no-go

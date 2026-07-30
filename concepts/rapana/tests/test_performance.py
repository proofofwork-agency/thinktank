from __future__ import annotations

from decimal import Decimal

import pytest

from rapana.agents.yield_strategist import estimate_idle_cash_drag
from rapana.fleet.performance import PerformanceTracker


def test_total_return_and_drawdown():
    tracker = PerformanceTracker(initial_equity=Decimal("10000"))
    # equity goes up then dips, creating a drawdown
    equities = [10000, 11000, 12000, 9000, 10500]
    for i, eq in enumerate(equities):
        tracker.record(i, Decimal(eq), Decimal("0"))
    assert tracker.total_return() == 0.05
    # peak 12000 -> trough 9000 = 25% drawdown
    assert round(tracker.max_drawdown() * 100, 1) == 25.0


def test_win_rate_from_realized_deltas():
    tracker = PerformanceTracker(initial_equity=Decimal("10000"))
    tracker.record(0, Decimal("10000"), Decimal("0"))
    tracker.record(1, Decimal("10100"), Decimal("100"))   # win
    tracker.record(2, Decimal("10050"), Decimal("50"))    # loss of 50
    tracker.record(3, Decimal("10200"), Decimal("200"))   # win
    summary = tracker.summary()
    assert summary["win_rate_pct"] == round(2 / 3 * 100, 1)
    assert summary["cycles"] == 4
    assert summary["trade_events"] == 3


def test_empty_summary_safe():
    tracker = PerformanceTracker(initial_equity=Decimal("10000"))
    s = tracker.summary()
    assert s["cycles"] == 0
    assert s["total_return_pct"] == 0.0


def test_current_drawdown_zero_after_recovery():
    tracker = PerformanceTracker(initial_equity=Decimal("10000"))
    # dip then full recovery to a new high
    for i, eq in enumerate([10000, 12000, 11000, 13000]):
        tracker.record(i, Decimal(eq), Decimal("0"))
    # historical max drawdown remains the 12000->11000 dip...
    assert round(tracker.max_drawdown() * 100, 2) == round(1000 / 12000 * 100, 2)
    # ...but current drawdown is 0 because equity made a new high.
    assert tracker.current_drawdown() == 0.0


def test_current_drawdown_reflects_active_dip():
    tracker = PerformanceTracker(initial_equity=Decimal("10000"))
    for i, eq in enumerate([10000, 12000, 9000]):
        tracker.record(i, Decimal(eq), Decimal("0"))
    # peak 12000 -> current 9000 = 25%
    assert round(tracker.current_drawdown() * 100, 1) == 25.0


def test_current_drawdown_empty_is_zero():
    tracker = PerformanceTracker(initial_equity=Decimal("10000"))
    assert tracker.current_drawdown() == 0.0


def test_idle_cash_drag_estimator_math():
    drag = estimate_idle_cash_drag(Decimal("10000"), 0.035)
    assert drag.annual_drag == Decimal("350.000")
    assert drag.period_drag == pytest.approx(Decimal("350.000") / Decimal("365"))


def test_summary_reports_idle_cash_drag():
    tracker = PerformanceTracker(
        initial_equity=Decimal("10000"),
        benchmark_cash_return=0.035,
    )
    tracker.record(0, Decimal("10000"), Decimal("0"), idle_cash=Decimal("8000"))
    summary = tracker.summary()
    assert summary["idle_cash"] == "8000"
    assert summary["benchmark_cash_return_pct"] == 3.5
    assert summary["idle_cash_drag_annual"] == "280.000"

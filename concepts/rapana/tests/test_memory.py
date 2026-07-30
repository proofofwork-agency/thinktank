from __future__ import annotations

from decimal import Decimal

from rapana.fleet.memory import ReflectionMemory
from rapana.signals import Signal


def _bull(symbol="BTC/USDT"):
    return Signal(symbol, "market", "bullish", 0.6, 0.8, "up")


def _bear(symbol="BTC/USDT"):
    return Signal(symbol, "market", "bearish", -0.6, 0.8, "down")


def test_observe_and_resolve_correct_bull():
    mem = ReflectionMemory(horizon_ms=1000)
    mem.observe(_bull(), Decimal("100"), ts=0)
    mem.resolve({"BTC/USDT": Decimal("110")}, now_ts=2000)  # price up -> bullish correct
    assert mem.stats["market"].total == 1
    assert mem.stats["market"].correct == 1


def test_observe_and_resolve_wrong_bear():
    mem = ReflectionMemory(horizon_ms=1000)
    mem.observe(_bear(), Decimal("100"), ts=0)
    mem.resolve({"BTC/USDT": Decimal("120")}, now_ts=2000)  # price up -> bear was wrong
    assert mem.stats["market"].correct == 0
    assert mem.stats["market"].total == 1


def test_unresolved_before_horizon_stays_pending():
    mem = ReflectionMemory(horizon_ms=1000)
    mem.observe(_bull(), Decimal("100"), ts=0)
    mem.resolve({"BTC/USDT": Decimal("110")}, now_ts=500)  # not enough time
    assert mem.stats["market"].total == 0
    assert len(mem.pending) == 1


def test_weight_neutral_without_evidence():
    mem = ReflectionMemory(horizon_ms=1000)
    assert mem.weight("market") == 1.0


def test_weight_reflects_accuracy():
    mem = ReflectionMemory(horizon_ms=1000, shrink=1.0)
    # 4 correct, 1 wrong out of 5 -> high accuracy -> weight > 1
    for i in range(4):
        mem.observe(_bull(), Decimal("100"), ts=i)
    mem.observe(_bear(), Decimal("100"), ts=4)
    mem.resolve({"BTC/USDT": Decimal("110")}, now_ts=10000)  # up: bulls right, bear wrong
    w = mem.weight("market")
    assert 1.0 < w <= 1.5


def test_weight_fades_bad_source():
    mem = ReflectionMemory(horizon_ms=1000, shrink=1.0)
    for i in range(5):
        mem.observe(_bull(), Decimal("100"), ts=i)  # always says up
    mem.resolve({"BTC/USDT": Decimal("90")}, now_ts=10000)  # actually down -> all wrong
    w = mem.weight("market")
    assert w < 1.0


def test_neutral_signals_not_observed():
    mem = ReflectionMemory(horizon_ms=1000)
    mem.observe(Signal("BTC/USDT", "market", "neutral", 0, 0, "meh"), Decimal("100"), ts=0)
    assert len(mem.pending) == 0


def test_analytics_returns_stats():
    mem = ReflectionMemory(horizon_ms=1000)
    mem.observe(_bull(), Decimal("100"), ts=0)
    mem.resolve({"BTC/USDT": Decimal("110")}, now_ts=2000)
    a = mem.analytics()
    assert "market" in a
    assert a["market"]["accuracy"] == 1.0


def test_default_max_pending_age_is_triple_horizon():
    mem = ReflectionMemory(horizon_ms=1000)
    assert mem.max_pending_age_ms == 3000


def test_pending_dropped_after_staleness_bound():
    mem = ReflectionMemory(horizon_ms=1000, max_pending_age_ms=3000)
    mem.observe(_bull(), Decimal("100"), ts=0)
    # Matured (age >= horizon) but symbol absent from prices -> kept under bound.
    mem.resolve({}, now_ts=1500)
    assert len(mem.pending) == 1
    assert mem.stats["market"].total == 0
    # Beyond the staleness bound and still unpriceable -> dropped, never scored.
    mem.resolve({}, now_ts=4000)
    assert len(mem.pending) == 0
    assert mem.stats["market"].total == 0

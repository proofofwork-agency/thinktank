from __future__ import annotations

from decimal import Decimal

from rapana.agents.portfolio_manager import PortfolioManager
from rapana.agents.researchers import Thesis
from rapana.signals import Signal


def _theses() -> tuple[Thesis, Thesis]:
    bull = Thesis("BTC/USDT", "bull", 0.0, [], "hold")
    bear = Thesis("BTC/USDT", "bear", 0.0, [], "hold")
    return bull, bear


def _bullish_signal(strength: float = 0.4) -> list[Signal]:
    return [Signal("BTC/USDT", "market", "bullish", strength, 1.0, "test")]


def _notional(proposal) -> Decimal:
    return proposal.qty * proposal.price


def test_vol_scale_halves_buy_weight():
    pm = PortfolioManager(max_weight=0.50, threshold=0.0)
    bull, bear = _theses()

    full = pm.decide(
        "BTC/USDT", _bullish_signal(), bull, bear,
        Decimal("100"), Decimal("10000"), Decimal("0"), vol_scale=1.0,
    )
    half = pm.decide(
        "BTC/USDT", _bullish_signal(), bull, bear,
        Decimal("100"), Decimal("10000"), Decimal("0"), vol_scale=0.5,
    )

    assert full is not None
    assert half is not None
    assert _notional(half) == _notional(full) / Decimal("2")


def test_vol_scale_clamps_to_max_weight_and_never_goes_negative():
    pm = PortfolioManager(max_weight=0.20, threshold=0.0)
    bull, bear = _theses()

    capped = pm.decide(
        "BTC/USDT", _bullish_signal(), bull, bear,
        Decimal("100"), Decimal("10000"), Decimal("0"), vol_scale=10.0,
    )
    negative = pm.decide(
        "BTC/USDT", _bullish_signal(), bull, bear,
        Decimal("100"), Decimal("10000"), Decimal("0"), vol_scale=-10.0,
    )

    assert capped is not None
    assert _notional(capped) == Decimal("2000")
    assert negative is None

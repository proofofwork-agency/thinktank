from __future__ import annotations

from decimal import Decimal

import pytest

from rapana.fleet.maker_fill import (
    PAPER_MAKER_SOURCE,
    PAPER_MAKER_TOUCH_POLICY,
    PaperMakerFillModel,
)
from rapana.risk.guardrails import TradeProposal


def _proposal(side: str = "buy") -> TradeProposal:
    return TradeProposal(
        symbol="BTC/USDT",
        side=side,
        qty=Decimal("0.1"),
        price=Decimal("50000"),
        reference_price=Decimal("50000"),
    )


def test_passive_limit_uses_explicit_offset_bps():
    model = PaperMakerFillModel(offset_bps=Decimal("2"))

    assert model.passive_limit("buy", Decimal("50000")) == Decimal("49990.0000")
    assert model.passive_limit("sell", Decimal("50000")) == Decimal("50010.0000")


def test_buy_requires_strict_low_penetration():
    model = PaperMakerFillModel(offset_bps=Decimal("2"), lifetime_bars=1)
    order = model.submit(_proposal("buy"), submitted_bar=10)

    touch_only = model.resolve(order, [{"index": 11, "high": "50100", "low": "49990.0000"}])
    penetrated = model.resolve(order, [{"index": 11, "high": "50100", "low": "49989.99"}])

    assert touch_only.status == "canceled"
    assert touch_only.reason == "paper_timeout_no_fill"
    assert touch_only.filled_qty == Decimal("0")
    assert penetrated.status == "filled"
    assert penetrated.filled_qty == order.qty
    assert penetrated.fill_bar == 11


def test_sell_requires_strict_high_penetration():
    model = PaperMakerFillModel(offset_bps=Decimal("2"), lifetime_bars=1)
    order = model.submit(_proposal("sell"), submitted_bar=10)

    touch_only = model.resolve(order, [{"index": 11, "high": "50010.0000", "low": "49900"}])
    penetrated = model.resolve(order, [{"index": 11, "high": "50010.01", "low": "49900"}])

    assert touch_only.status == "canceled"
    assert touch_only.filled_qty == Decimal("0")
    assert penetrated.status == "filled"
    assert penetrated.filled_qty == order.qty


def test_lifetime_limits_fill_window_without_later_lookahead():
    model = PaperMakerFillModel(offset_bps=Decimal("2"), lifetime_bars=2)
    order = model.submit(_proposal("buy"), submitted_bar=10)

    outcome = model.resolve(
        order,
        [
            {"index": 10, "high": "50100", "low": "1"},
            {"index": 11, "high": "50100", "low": "49995"},
            {"index": 12, "high": "50100", "low": "49990.0000"},
            {"index": 13, "high": "50100", "low": "1"},
        ],
    )

    assert outcome.status == "canceled"
    assert outcome.filled_qty == Decimal("0")
    assert outcome.fill_bar is None
    assert outcome.expiry_bar == 12


def test_fill_is_binary_and_metadata_describes_replay_touch_model():
    model = PaperMakerFillModel(offset_bps=Decimal("2"), lifetime_bars=1)
    order = model.submit(_proposal("buy"), submitted_bar=3)

    outcome = model.resolve(order, [{"index": 4, "high": "50100", "low": "1"}])

    assert outcome.status == "filled"
    assert outcome.filled_qty == Decimal("0.1")
    assert outcome.metadata == {
        "touch_policy": PAPER_MAKER_TOUCH_POLICY,
        "submitted_bar": "3",
        "expiry_bar": "4",
        "lifetime_bars": "1",
        "limit_price": "49990.0000",
        "source": PAPER_MAKER_SOURCE,
        "paper_maker_offset_bps": "2",
        "fill_bar": "4",
    }


def test_model_rejects_invalid_configuration():
    with pytest.raises(ValueError, match="offset_bps"):
        PaperMakerFillModel(offset_bps=Decimal("-1"))
    with pytest.raises(ValueError, match="lifetime_bars"):
        PaperMakerFillModel(lifetime_bars=0)

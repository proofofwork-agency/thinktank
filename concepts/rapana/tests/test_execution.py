from __future__ import annotations

from decimal import Decimal

import ccxt
import pytest

from rapana.fleet.capital import StagedCapital
from rapana.fleet.execution import LiveExecutor, OrderResult, PaperExecutor
from rapana.fleet.portfolio import PaperPortfolio
from rapana.risk.guardrails import KillSwitch, TradeProposal


def _filled(side: str, qty: Decimal, price: Decimal, fee: Decimal) -> OrderResult:
    return OrderResult("filled", "BTC/USDT", side, "paper", qty, qty, price, fee)


def test_staged_capital_paper_uses_full():
    # Paper mode trades the full simulated balance (per the StagedCapital
    # docstring); the staged ramp only governs LIVE deployment.
    cap = StagedCapital(paper=True)
    assert cap.fraction == pytest.approx(1.0)
    assert cap.available(Decimal("10000")) == Decimal("10000")
    assert cap.can_trade(Decimal("50"), Decimal("10000")) is True
    assert cap.can_trade(Decimal("9999"), Decimal("10000")) is True
    assert cap.can_trade(Decimal("10001"), Decimal("10000")) is False


def test_staged_capital_live_default_is_one_percent():
    # LIVE starts at the smallest stage (1%); promotion is a human gate.
    cap = StagedCapital(paper=False)
    assert cap.fraction == pytest.approx(0.01)
    assert cap.available(Decimal("10000")) == Decimal("100")


def test_staged_capital_advance():
    # Staging is a LIVE concept: promote/demote build StagedCapital(paper=False).
    cap = StagedCapital(paper=False)
    cap.advance()
    assert cap.fraction == pytest.approx(0.05)
    cap.advance()
    cap.advance()
    assert cap.fraction == pytest.approx(1.0)
    cap.advance()  # clamps at max
    assert cap.fraction == pytest.approx(1.0)


def test_paper_portfolio_buy_updates_cost_basis():
    port = PaperPortfolio(cash=Decimal("10000"))
    fill = _filled("buy", Decimal("0.1"), Decimal("50000"), Decimal("5"))
    port.apply_fill(fill)
    assert port.units("BTC/USDT") == Decimal("0.1")
    assert port.cash == Decimal("10000") - Decimal("5000") - Decimal("5")
    assert port.cost_basis["BTC/USDT"] == Decimal("5000")


def test_paper_portfolio_sell_realizes_pnl():
    port = PaperPortfolio(cash=Decimal("10000"))
    port.apply_fill(_filled("buy", Decimal("0.1"), Decimal("50000"), Decimal("5")))
    # sell at 60000 -> profit
    port.apply_fill(_filled("sell", Decimal("0.1"), Decimal("60000"), Decimal("6")))
    assert port.units("BTC/USDT") == Decimal("0")
    # realized = proceeds(6000-6) - cost(5000) = 994
    assert port.realized_pnl == Decimal("5994") - Decimal("5000")


def test_paper_portfolio_ignores_unbooked_order_result():
    port = PaperPortfolio(cash=Decimal("10000"))
    result = OrderResult(
        "rejected", "BTC/USDT", "buy", "paper",
        Decimal("0.1"), Decimal("0"), Decimal("50000"), Decimal("0"),
    )
    port.apply_fill(result)
    assert port.cash == Decimal("10000")
    assert port.units("BTC/USDT") == Decimal("0")


def test_paper_executor_skips_insufficient_cash():
    ex = PaperExecutor()
    proposal = TradeProposal(
        symbol="BTC/USDT", side="buy",
        qty=Decimal("1"), price=Decimal("50000"), reference_price=Decimal("50000"),
    )
    result = ex.execute(proposal, available_cash=Decimal("100"))
    assert result.status == "rejected"
    assert result.is_booked is False
    assert result.proposed_qty == Decimal("1")
    assert result.filled_qty == Decimal("0")


def test_paper_executor_buy_applies_slippage_and_fee():
    ex = PaperExecutor()
    proposal = TradeProposal(
        symbol="BTC/USDT", side="buy",
        qty=Decimal("0.1"), price=Decimal("50000"), reference_price=Decimal("50000"),
    )
    result = ex.execute(proposal, available_cash=Decimal("10000"))
    assert result.status == "filled"
    assert result.is_booked is True
    assert result.price > Decimal("50000")  # slippage makes buy price higher
    assert result.fee > 0
    result_dict = result.as_dict()
    assert {"symbol", "side", "qty", "price", "fee", "mode"}.issubset(result_dict)
    assert result_dict["qty"] == result_dict["filled_qty"]


def test_order_result_as_dict_additive_fields_keep_legacy_subset():
    result = OrderResult(
        "canceled", "BTC/USDT", "buy", "paper",
        Decimal("0.1"), Decimal("0"), Decimal("49900"), Decimal("0"),
        submitted=True, reason="paper_timeout_no_fill", metadata={"execution_mode": "maker"},
    )
    result_dict = result.as_dict()
    assert {"symbol", "side", "qty", "price", "fee", "mode"}.issubset(result_dict)
    assert result_dict["submitted"] is True
    assert result_dict["reason"] == "paper_timeout_no_fill"
    assert result_dict["metadata"]["execution_mode"] == "maker"


def test_paper_maker_misses_by_default():
    ex = PaperExecutor(execution_mode="maker")
    proposal = TradeProposal(
        symbol="BTC/USDT", side="buy",
        qty=Decimal("0.1"), price=Decimal("49900"), reference_price=Decimal("50000"),
    )
    result = ex.execute(proposal, available_cash=Decimal("10000"))
    assert result.status == "canceled"
    assert result.submitted is True
    assert result.reason == "paper_timeout_no_fill"
    assert result.filled_qty == Decimal("0")


def test_paper_maker_marketability_guard_rejects_would_cross():
    ex = PaperExecutor(execution_mode="maker")
    proposal = TradeProposal(
        symbol="BTC/USDT", side="buy",
        qty=Decimal("0.1"), price=Decimal("50000"), reference_price=Decimal("50000"),
    )
    result = ex.execute(proposal, available_cash=Decimal("10000"))
    assert result.status == "rejected"
    assert result.submitted is True
    assert result.reason == "post_only_rejected"


def test_paper_maker_partial_and_fill_knobs():
    proposal = TradeProposal(
        symbol="BTC/USDT", side="buy",
        qty=Decimal("0.1"), price=Decimal("49900"), reference_price=Decimal("50000"),
    )
    partial = PaperExecutor(execution_mode="maker", paper_maker_fill_fraction=0.5).execute(
        proposal, available_cash=Decimal("10000"),
    )
    filled = PaperExecutor(execution_mode="maker", paper_maker_fill_fraction=1).execute(
        proposal, available_cash=Decimal("10000"),
    )
    assert partial.status == "partial"
    assert partial.filled_qty == Decimal("0.05000000")
    assert partial.reason == "paper_partial_then_cancel"
    assert filled.status == "filled"
    assert filled.filled_qty == Decimal("0.1")


class _FakeExchange:
    def __init__(self, best_bid=Decimal("49999.00"), best_ask=Decimal("50001.00")):
        self.markets = {"BTC/USDT": {"precision": {"price": 2}}}
        self.best_bid = best_bid
        self.best_ask = best_ask


class _FakeMexcClient:
    def __init__(
        self,
        *,
        order_book=None,
        create_exc: Exception | None = None,
        fetches=None,
        cancel_status="canceled",
    ):
        self.exchange = _FakeExchange()
        self.order_book = order_book or {"bids": [[49999.0, 1]], "asks": [[50001.0, 1]]}
        self.create_exc = create_exc
        self.fetches = list(fetches or [])
        self.cancel_status = cancel_status
        self.orders = []
        self.cancels = []
        self.loaded = False

    def load_markets(self):
        self.loaded = True
        return self.exchange.markets

    def fetch_order_book(self, symbol, limit=5):
        return self.order_book

    def create_order(self, symbol, side, amount, *, order_type="market", price=None,
                     post_only=False, client_order_id=None, params=None):
        if self.create_exc is not None:
            raise self.create_exc
        order = {
            "id": "o1", "symbol": symbol, "side": side, "amount": amount,
            "price": price, "status": "open", "filled": 0, "fee": {"cost": 0},
            "type": order_type, "post_only": post_only, "client_order_id": client_order_id,
        }
        self.orders.append(order)
        return order

    def fetch_order(self, order_id, symbol):
        if self.fetches:
            return self.fetches.pop(0)
        return {"id": order_id, "symbol": symbol, "status": self.cancel_status, "price": 49999.0}

    def cancel_order(self, order_id, symbol):
        self.cancels.append((order_id, symbol))
        return {"id": order_id, "symbol": symbol, "status": "canceled"}


def _live_proposal(side="buy"):
    return TradeProposal(
        symbol="BTC/USDT", side=side,
        qty=Decimal("0.1"), price=Decimal("50000"), reference_price=Decimal("50000"),
    )


def test_live_maker_local_no_order_book_and_would_cross_guards():
    no_book = LiveExecutor(_FakeMexcClient(order_book={"bids": [], "asks": []}), execution_mode="maker")
    no_book_result = no_book.execute(_live_proposal(), Decimal("10000"))
    crossed = LiveExecutor(
        _FakeMexcClient(order_book={"bids": [[50000.0, 1]], "asks": [[50000.0, 1]]}),
        execution_mode="maker",
    )
    crossed_result = crossed.execute(_live_proposal(), Decimal("10000"))
    assert no_book_result.status == "rejected"
    assert no_book_result.submitted is False
    assert no_book_result.reason == "no_order_book"
    assert crossed_result.status == "rejected"
    assert crossed_result.submitted is False
    assert crossed_result.reason == "would_cross_local_guard"


def test_live_maker_poll_fill():
    client = _FakeMexcClient(fetches=[
        {"id": "o1", "symbol": "BTC/USDT", "status": "closed", "filled": 0.1,
         "average": 49999.0, "fee": {"cost": 0}},
    ])
    result = LiveExecutor(client, execution_mode="maker", sleep=lambda _: None).execute(
        _live_proposal(), Decimal("10000"), client_order_id="rapana-BTC-abc12345",
    )
    assert result.status == "filled"
    assert result.filled_qty == Decimal("0.1")
    assert result.submitted is True
    assert client.orders[0]["type"] == "limit"
    assert client.orders[0]["post_only"] is True
    assert client.orders[0]["price"] == 49999.0


def test_live_maker_timeout_cancels_with_no_resting_order():
    client = _FakeMexcClient(cancel_status="canceled")
    result = LiveExecutor(client, execution_mode="maker", maker_poll_timeout_sec=0).execute(
        _live_proposal(), Decimal("10000"),
    )
    assert result.status == "canceled"
    assert result.reason == "timeout_no_fill"
    assert client.cancels == [("o1", "BTC/USDT")]


def test_live_maker_partial_then_cancel_books_filled_only():
    client = _FakeMexcClient(fetches=[
        {"id": "o1", "symbol": "BTC/USDT", "status": "open", "filled": 0.04,
         "price": 49999.0, "fee": {"cost": 0.2}},
    ])
    result = LiveExecutor(client, execution_mode="maker", sleep=lambda _: None).execute(
        _live_proposal(), Decimal("10000"),
    )
    assert result.status == "partial"
    assert result.filled_qty == Decimal("0.04")
    assert result.reason == "partial_then_cancel"
    assert client.cancels == [("o1", "BTC/USDT")]


def test_live_maker_confirmed_cancel_uses_post_cancel_fill_as_authoritative():
    client = _FakeMexcClient(fetches=[
        {"id": "o1", "symbol": "BTC/USDT", "status": "open", "filled": 0.04,
         "price": 49999.0, "fee": {"cost": 0.2}},
        {"id": "o1", "symbol": "BTC/USDT", "status": "closed", "filled": 0.1,
         "average": 49999.0, "fee": {"cost": 0.5}},
    ])
    result = LiveExecutor(client, execution_mode="maker", sleep=lambda _: None).execute(
        _live_proposal(), Decimal("10000"),
    )
    assert result.status == "filled"
    assert result.filled_qty == Decimal("0.1")
    assert result.fee == Decimal("0.5")
    assert client.cancels == [("o1", "BTC/USDT")]


def test_live_maker_cancel_unverified_trips_kill_switch(tmp_path):
    ks = KillSwitch(path=tmp_path / "KS")
    client = _FakeMexcClient(cancel_status="open")
    result = LiveExecutor(
        client, execution_mode="maker", maker_poll_timeout_sec=0, kill_switch=ks,
    ).execute(_live_proposal(), Decimal("10000"))
    assert result.status == "resting"
    assert result.reason == "cancel_unverified"
    assert ks.is_tripped() is True


def test_live_maker_partial_cancel_unverified_books_and_trips_kill_switch(tmp_path):
    ks = KillSwitch(path=tmp_path / "KS")
    client = _FakeMexcClient(
        fetches=[
            {"id": "o1", "symbol": "BTC/USDT", "status": "open", "filled": 0.04,
             "price": 49999.0, "fee": {"cost": 0.2}},
        ],
        cancel_status="open",
    )
    result = LiveExecutor(client, execution_mode="maker", sleep=lambda _: None, kill_switch=ks).execute(
        _live_proposal(), Decimal("10000"),
    )
    port = PaperPortfolio(cash=Decimal("10000"))
    port.apply_fill(result)
    assert result.status == "partial"
    assert result.is_booked is True
    assert result.reason == "cancel_unverified"
    assert result.filled_qty == Decimal("0.04")
    assert port.units("BTC/USDT") == Decimal("0.04")
    assert ks.is_tripped() is True


def test_live_maker_post_only_reject_uses_classifier():
    client = _FakeMexcClient(
        create_exc=ccxt.InvalidOrder("mexc LIMIT_MAKER order would match immediately"),
    )
    result = LiveExecutor(client, execution_mode="maker").execute(_live_proposal(), Decimal("10000"))
    assert result.status == "rejected"
    assert result.submitted is True
    assert result.reason == "post_only_rejected"

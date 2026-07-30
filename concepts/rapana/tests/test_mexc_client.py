from __future__ import annotations

import ccxt
import pytest

import rapana.mexc.client as client_mod
from rapana.mexc.client import MexcClient, is_post_only_reject


class FakeExchange:
    """Minimal fake ccxt.mexc for unit tests (no network)."""

    def __init__(self, params):
        self.params = params
        self.markets = {"BTC/USDT": {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT"}}
        self._loaded = False
        self.orders = []
        self.fetched_orders = []
        self.canceled_orders = []

    def load_markets(self):
        self._loaded = True
        return self.markets

    def fetch_ticker(self, symbol):
        return {"symbol": symbol, "last": 100.0, "bid": 99.5, "ask": 100.5}

    def fetch_tickers(self, symbols=None):
        data = {
            "BTC/USDT": {"symbol": "BTC/USDT", "last": 100.0,
                         "quoteVolume": 1_000_000.0, "baseVolume": 10_000.0},
        }
        return data if symbols is None else {s: data[s] for s in symbols if s in data}

    def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=500):
        return [[1700000000000, 100.0, 101.0, 99.0, 100.5, 10.0]]

    def fetch_order_book(self, symbol, limit=100):
        return {"bids": [[99.5, 1]], "asks": [[100.5, 1]]}

    def fetch_status(self):
        return {"status": "ok"}

    def fetch_time(self):
        return 1700000000000

    def fetch_balance(self):
        return {"total": {"USDT": 5000.0, "BTC": 0.0}}

    def amount_to_precision(self, symbol, amount):
        return f"{float(amount):.6f}"

    def price_to_precision(self, symbol, price):
        return f"{float(price):.2f}"

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        order = {
            "symbol": symbol,
            "type": type,
            "side": side,
            "amount": amount,
            "price": price,
            "params": params or {},
            "id": "order-1",
        }
        self.orders.append(order)
        return order

    def fetch_order(self, order_id, symbol):
        self.fetched_orders.append((order_id, symbol))
        return {"id": order_id, "symbol": symbol, "status": "open"}

    def cancel_order(self, order_id, symbol):
        self.canceled_orders.append((order_id, symbol))
        return {"id": order_id, "symbol": symbol, "status": "canceled"}


@pytest.fixture(autouse=True)
def stub_secrets(monkeypatch):
    import rapana.mexc as mexc_pkg

    monkeypatch.setattr(mexc_pkg, "get_keys", lambda: {"apiKey": "k", "secret": "s"})
    monkeypatch.setattr(client_mod.ccxt, "mexc", FakeExchange)


def test_load_markets_and_symbol():
    c = MexcClient()
    c.load_markets()
    assert c.symbol_exists("BTC/USDT")
    assert not c.symbol_exists("DOGE/USDT")


def test_fetch_ohlcv_shape():
    c = MexcClient()
    rows = c.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=10)
    assert rows[0][4] == 100.5  # close


def test_ping_true_when_ok():
    assert MexcClient().ping() is True


def test_fetch_balance():
    bal = MexcClient().fetch_balance()
    assert bal["total"]["USDT"] == 5000.0


def test_fetch_tickers_bulk():
    t = MexcClient().fetch_tickers(["BTC/USDT"])
    assert t["BTC/USDT"]["quoteVolume"] == 1_000_000.0


def test_create_order_post_only_merges_ccxt_params():
    c = MexcClient()
    order = c.create_order(
        "BTC/USDT",
        "buy",
        0.01,
        order_type="limit",
        price=100.5,
        post_only=True,
        client_order_id="rapana-BTC-abc12345",
        params={"recvWindow": 5000},
    )
    assert order["type"] == "limit"
    assert order["side"] == "buy"
    assert order["amount"] == "0.010000"
    assert order["price"] == "100.50"
    assert order["params"] == {
        "recvWindow": 5000,
        "postOnly": True,
        "clientOrderId": "rapana-BTC-abc12345",
    }


def test_create_order_market_passthrough_without_post_only():
    c = MexcClient()
    order = c.create_order("BTC/USDT", "sell", 0.02)
    assert order["type"] == "market"
    assert order["side"] == "sell"
    assert order["amount"] == "0.020000"
    assert order["price"] is None
    assert order["params"] == {}


def test_fetch_and_cancel_order_passthrough():
    c = MexcClient()
    fetched = c.fetch_order("order-1", "BTC/USDT")
    canceled = c.cancel_order("order-1", "BTC/USDT")
    assert fetched["status"] == "open"
    assert canceled["status"] == "canceled"
    assert c.exchange.fetched_orders == [("order-1", "BTC/USDT")]
    assert c.exchange.canceled_orders == [("order-1", "BTC/USDT")]


@pytest.mark.parametrize(
    "exc",
    [
        ccxt.OrderImmediatelyFillable("post-only order would be filled immediately"),
        ccxt.InvalidOrder("mexc {\"msg\":\"LIMIT_MAKER order would match immediately\"}"),
        ccxt.BadRequest("mexc post only order would take liquidity"),
    ],
)
def test_is_post_only_reject_accepts_clear_signatures(exc):
    assert is_post_only_reject(exc) is True


@pytest.mark.parametrize(
    "exc",
    [
        ccxt.InvalidOrder("mexc amount cannot be zero"),
        ccxt.InvalidOrder("mexc maker fee unavailable"),
        ccxt.BadRequest("mexc postOnly parameter invalid"),
        ccxt.ExchangeError("mexc request failed"),
    ],
)
def test_is_post_only_reject_keeps_ambiguous_errors_real_rejects(exc):
    assert is_post_only_reject(exc) is False

"""Tests for the live universe Scout (faked exchange, no network)."""
from __future__ import annotations

from rapana.mexc.client import MexcClient
from rapana.universe.ranker import UniverseParams
from rapana.universe.scout import Scout

HOUR = 3_600_000


def _ohlcv(n: int, rate: float, start: float = 100.0) -> list[list[float]]:
    rows = []
    for i in range(n):
        c = start * ((1 + rate) ** i)
        rows.append([i * HOUR, c, c, c, c, 1_000_000.0 / c])  # dollar-vol ~1e6/bar
    return rows


_MARKETS = {
    "BTC/USDT": {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "active": True, "spot": True},
    "ETH/USDT": {"symbol": "ETH/USDT", "base": "ETH", "quote": "USDT", "active": True, "spot": True},
    "SOL/USDT": {"symbol": "SOL/USDT", "base": "SOL", "quote": "USDT", "active": True, "spot": True},
    "BTC3L/USDT": {"symbol": "BTC3L/USDT", "base": "BTC3L", "quote": "USDT", "active": True, "spot": True},
    "ETH3S/USDT": {"symbol": "ETH3S/USDT", "base": "ETH3S", "quote": "USDT", "active": True, "spot": True},
    "USDC/USDT": {"symbol": "USDC/USDT", "base": "USDC", "quote": "USDT", "active": True, "spot": True},
    "XMR/BTC": {"symbol": "XMR/BTC", "base": "XMR", "quote": "BTC", "active": True, "spot": True},
    "DEAD/USDT": {"symbol": "DEAD/USDT", "base": "DEAD", "quote": "USDT", "active": False, "spot": True},
    "FUT/USDT": {"symbol": "FUT/USDT", "base": "FUT", "quote": "USDT", "active": True, "spot": False, "type": "swap"},
}

_TICKERS = {
    "BTC/USDT": {"quoteVolume": 9_000_000.0},
    "ETH/USDT": {"quoteVolume": 5_000_000.0},
    "SOL/USDT": {"quoteVolume": 1_000_000.0},
}


class _FakeExchange:
    def __init__(self):
        self.markets = _MARKETS
        self.ohlcv_calls: list[str] = []

    def load_markets(self):
        return self.markets

    def parse_timeframe(self, timeframe):
        return 3600

    def fetch_tickers(self, symbols=None):
        return _TICKERS if symbols is None else {s: _TICKERS[s] for s in symbols if s in _TICKERS}

    def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=500):
        self.ohlcv_calls.append(symbol)
        series = {
            "BTC/USDT": _ohlcv(30, 0.01),    # strong momentum
            "ETH/USDT": _ohlcv(30, 0.001),   # weak momentum
            "SOL/USDT": _ohlcv(30, -0.01),
        }.get(symbol, [])
        return [list(r) for r in series[:limit]]


def _scout(fake, **kw):
    client = MexcClient(authenticated=False)
    client.exchange = fake  # type: ignore[assignment]
    params = UniverseParams(top_n=kw.pop("top_n", 2), min_quote_volume_usd=1.0,
                            momentum_lookback=20)
    return Scout(client, params, timeframe="1h", **kw)


def test_discovers_only_eligible_markets():
    scout = _scout(_FakeExchange())
    # leveraged (BTC3L, ETH3S), stable (USDC), non-USDT (XMR/BTC),
    # inactive (DEAD), and non-spot (FUT) are all excluded.
    assert scout.discover_candidates() == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]


def test_candidate_k_bounds_history_calls():
    fake = _FakeExchange()
    scout = _scout(fake, candidate_k=2)
    scout.select()
    assert fake.ohlcv_calls == ["BTC/USDT", "ETH/USDT"]  # only top-2 by volume fetched


def test_select_ranks_strongest_first():
    scout = _scout(_FakeExchange(), candidate_k=3, top_n=3)
    # All three fetched; ranked by risk-adjusted momentum: BTC > ETH > SOL(neg).
    assert scout.select_symbols() == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

from __future__ import annotations

import io
import json
from decimal import Decimal

from rapana.feeds.feargreed import FearGreedFeed
from rapana.feeds.market_premium import MarketPremiumFeed


class _Resp:
    def __init__(self, payload: bytes):
        self._buf = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._buf.read()


def test_fear_greed_contrarian(monkeypatch):
    feed = FearGreedFeed(cache_seconds=0)
    payload = json.dumps({"data": [{"value": "20"}]}).encode()  # extreme fear
    monkeypatch.setattr(
        "rapana.feeds.feargreed.urllib.request.urlopen",
        lambda req, timeout=None: _Resp(payload),
    )
    score, conf = feed.score("BTC/USDT")
    assert score > 0  # extreme fear -> bullish (contrarian)
    assert conf > 0


def test_fear_greed_failure_soft(monkeypatch):
    feed = FearGreedFeed(cache_seconds=0)

    def boom(req, timeout=None):
        raise OSError("network down")

    monkeypatch.setattr("rapana.feeds.feargreed.urllib.request.urlopen", boom)
    score, conf = feed.score("BTC/USDT")
    assert (score, conf) == (0.0, 0.0)


def test_market_premium_discount_bullish(monkeypatch):
    feed = MarketPremiumFeed(mexc_price=lambda s: Decimal("950"))  # MEXC below ref
    payload = json.dumps({"bitcoin": {"usd": 1000}}).encode()
    monkeypatch.setattr(
        "rapana.feeds.market_premium.urllib.request.urlopen",
        lambda req, timeout=None: _Resp(payload),
    )
    score, conf = feed.score("BTC/USDT")
    assert score > 0  # discount -> bullish
    assert conf > 0


def test_market_premium_failure_soft(monkeypatch):
    feed = MarketPremiumFeed(mexc_price=lambda s: Decimal("100"))

    def boom(req, timeout=None):
        raise OSError("down")

    monkeypatch.setattr("rapana.feeds.market_premium.urllib.request.urlopen", boom)
    assert feed.score("BTC/USDT") == (0.0, 0.0)


def test_market_premium_unknown_coin(monkeypatch):
    feed = MarketPremiumFeed(mexc_price=lambda s: Decimal("100"))
    called = {"hit": False}

    def fake(req, timeout=None):
        called["hit"] = True
        return _Resp(b"{}")

    monkeypatch.setattr("rapana.feeds.market_premium.urllib.request.urlopen", fake)
    # FOO/USDT not in coin map -> neutral without calling network
    assert feed.score("FOO/USDT") == (0.0, 0.0)
    assert called["hit"] is False


def test_market_premium_paid_key_uses_pro_host(monkeypatch):
    feed = MarketPremiumFeed(mexc_price=lambda s: Decimal("100"), api_key="CG-PRO-KEY")
    captured = {}

    def fake(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        return _Resp(json.dumps({"bitcoin": {"usd": 100}}).encode())

    monkeypatch.setattr("rapana.feeds.market_premium.urllib.request.urlopen", fake)
    feed.score("BTC/USDT")
    assert "pro-api.coingecko.com" in captured["url"]
    assert captured["headers"].get("x-cg-pro-api-key") == "CG-PRO-KEY"


def test_market_premium_free_host_without_key(monkeypatch):
    feed = MarketPremiumFeed(mexc_price=lambda s: Decimal("100"))
    captured = {}

    def fake(req, timeout=None):
        captured["url"] = req.full_url
        return _Resp(json.dumps({"bitcoin": {"usd": 100}}).encode())

    monkeypatch.setattr("rapana.feeds.market_premium.urllib.request.urlopen", fake)
    feed.score("BTC/USDT")
    assert "api.coingecko.com" in captured["url"]
    assert "pro-api" not in captured["url"]


def test_fetch_fear_greed_history_parses_and_sorts(monkeypatch):
    from rapana.feeds.feargreed import fetch_fear_greed_history

    # API returns newest-first; output must be ascending by ts.
    payload = json.dumps({"data": [
        {"timestamp": "2000", "value": "50"},
        {"timestamp": "1000", "value": "20"},
    ]}).encode()
    monkeypatch.setattr(
        "rapana.feeds.feargreed.urllib.request.urlopen",
        lambda req, timeout=None: _Resp(payload),
    )
    rows = fetch_fear_greed_history()
    assert rows == [{"ts": 1_000_000, "value": 20}, {"ts": 2_000_000, "value": 50}]

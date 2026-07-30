from __future__ import annotations

import json
import urllib.error
import urllib.request

from rapana.feeds.base import Feed
from rapana.logging import get_logger

log = get_logger(__name__)

_PRICE_API = "https://api.coingecko.com/api/v3/simple/price"
_PRO_API = "https://pro-api.coingecko.com/api/v3/simple/price"
# Map MEXC base assets to CoinGecko coin ids (extend as needed).
_COIN_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple",
    "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche-2", "LINK": "chainlink",
}


class MarketPremiumFeed(Feed):
    """Cross-source price premium: CoinGecko global avg vs the MEXC price.

    A real (free, no-key) spread signal: if MEXC trades below the global average
    the feed leans bullish (a discount to buy), and vice-versa. The MEXC price is
    read from the supplied price callable (a DataProvider.get_price bound method
    or a MexcClient wrapper).
    """

    name = "market_premium"

    def __init__(self, mexc_price, api_key: str | None = None) -> None:
        # mexc_price: callable(symbol) -> Decimal|float
        # api_key: optional CoinGecko paid-plan key (Basic/Analyst/Lite/Pro).
        # When set, requests hit the authenticated pro-api host (higher rate
        # limits + commercial license); otherwise the free public host.
        self.mexc_price = mexc_price
        self.api_key = api_key

    def _coin_id(self, symbol: str) -> str | None:
        base = symbol.upper().split("/")[0]
        return _COIN_IDS.get(base)

    def _reference_price(self, symbol: str) -> float | None:
        cid = self._coin_id(symbol)
        if not cid:
            return None
        try:
            host = _PRO_API if self.api_key else _PRICE_API
            url = f"{host}?ids={cid}&vs_currencies=usd"
            headers = {"User-Agent": "rapana/1.0"}
            if self.api_key:
                headers["x-cg-pro-api-key"] = self.api_key
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return float(data[cid]["usd"])
        except (OSError, KeyError, ValueError) as exc:
            log.warning("coingecko_fetch_failed", symbol=symbol, error=str(exc))
            return None

    def score(self, symbol: str) -> tuple[float, float]:
        ref = self._reference_price(symbol)
        try:
            mexc = float(self.mexc_price(symbol))
        except Exception as exc:
            log.warning("mexc_price_failed", symbol=symbol, error=str(exc))
            return 0.0, 0.0
        if not ref or not mexc or mexc <= 0:
            return 0.0, 0.0
        premium = (mexc - ref) / ref  # MEXC above global -> positive
        # Lean opposite to the premium: discount (negative premium) -> bullish.
        score = max(-1.0, min(1.0, -premium * 5.0))
        confidence = min(1.0, abs(premium) * 10.0)
        return score, confidence

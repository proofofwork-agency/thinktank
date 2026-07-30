from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from rapana.feeds.base import Feed
from rapana.logging import get_logger

log = get_logger(__name__)

_API = "https://api.alternative.me/fng/?limit=1"
_HISTORY_API = "https://api.alternative.me/fng/?limit=0&format=json"


class FearGreedFeed(Feed):
    """Crypto Fear & Greed index (alternative.me, free, no key).

    Market-wide sentiment: maps 0 (extreme fear) .. 100 (extreme greed) to a
    contrarian-leaning score. Cached for 30 min so we never hammer the endpoint.
    """

    name = "fear_greed"

    def __init__(self, cache_seconds: int = 1800) -> None:
        self.cache_seconds = cache_seconds
        self._value: float | None = None
        self._fetched_at: float = 0.0

    def _fetch(self) -> float | None:
        if self._value is not None and (time.time() - self._fetched_at) < self.cache_seconds:
            return self._value
        try:
            req = urllib.request.Request(_API, headers={"User-Agent": "rapana/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self._value = float(data["data"][0]["value"])
            self._fetched_at = time.time()
            return self._value
        except (OSError, KeyError, ValueError) as exc:
            log.warning("fear_greed_fetch_failed", error=str(exc))
            return None

    def score(self, symbol: str) -> tuple[float, float]:
        v = self._fetch()
        if v is None:
            return 0.0, 0.0
        # Contrarian read: extreme fear is a bullish opportunity, extreme greed bearish.
        raw = (50.0 - v) / 50.0  # fear(0)->+1, greed(100)->-1
        confidence = min(1.0, abs(v - 50.0) / 50.0)
        return raw, confidence


def fetch_fear_greed_history() -> list[dict[str, int]]:
    """Full daily Fear & Greed history as ascending ``[{ts, value}]`` (ts in ms).

    Free, no key. ``ts`` is the UTC day-start (ms); the value for day D is
    published at the close of day D, so callers must respect that timing when
    joining to price (use day D's value to decide a trade entered on day D+1).
    """
    req = urllib.request.Request(_HISTORY_API, headers={"User-Agent": "rapana/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    rows = [
        {"ts": int(r["timestamp"]) * 1000, "value": round(float(r["value"]))}
        for r in data.get("data", [])
    ]
    rows.sort(key=lambda r: r["ts"])
    return rows

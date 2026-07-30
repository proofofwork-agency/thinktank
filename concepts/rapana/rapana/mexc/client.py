from __future__ import annotations

import re
from typing import Any

import ccxt
from ccxt.base.errors import OrderImmediatelyFillable

import rapana.mexc as mexc_pkg
from rapana.config import Settings, get_settings
from rapana.logging import get_logger

log = get_logger(__name__)

# MEXC spot rate limits: 300 IP weight / 10s and 500 UID weight / 10s.
# enableRateLimit lets ccxt throttle automatically.
_MEXC_DEFAULTS: dict[str, Any] = {
    "enableRateLimit": True,
    "rateLimit": 200,  # ms floor between requests (~5 req/s, well under limits)
    "options": {"defaultType": "spot"},
}

# Swap (perpetual) market type — used only for read-only funding/perp data on
# the carry track. Order placement on swaps is gated to a later, human-approved
# phase; this client stays read-only.
_MEXC_SWAP_DEFAULTS: dict[str, Any] = {
    "enableRateLimit": True,
    "rateLimit": 200,
    "options": {"defaultType": "swap"},
}

_POST_ONLY_TERMS = re.compile(r"(post[- ]?only|limit[_ -]?maker|maker)", re.IGNORECASE)
_WOULD_CROSS_TERMS = re.compile(
    r"(immediate|immediately|would (?:match|cross|take|fill)|taker|match immediately)",
    re.IGNORECASE,
)


def is_post_only_reject(exc: BaseException) -> bool:
    """Return True only for clear post-only/would-cross exchange rejects.

    Ambiguous InvalidOrder/BadRequest errors stay real rejects. The raw exception
    details are logged so the classifier can be tightened from observed MEXC
    responses without silently treating unknown failures as benign missed fills.
    """
    code = getattr(exc, "code", None)
    message = str(exc)
    log.warning(
        "post_only_reject_classification",
        exc_type=type(exc).__name__,
        code=str(code) if code is not None else None,
        message=message,
    )
    if isinstance(exc, OrderImmediatelyFillable):
        return True
    return bool(_POST_ONLY_TERMS.search(message) and _WOULD_CROSS_TERMS.search(message))


class MexcClient:
    """Read-mostly CCXT wrapper for MEXC spot.

    Phase 0 exposes market-data + account-read methods only. Order placement is
    intentionally absent — it lands in Phase 3 behind the risk/execution layers.
    """

    def __init__(self, settings: Settings | None = None, *, authenticated: bool = True) -> None:
        self.settings = settings or get_settings()
        params = dict(_MEXC_DEFAULTS)
        if authenticated:
            params.update(mexc_pkg.get_keys())
        self.exchange: ccxt.mexc = ccxt.mexc(params)
        self._markets_loaded = False

    # ---- market metadata -------------------------------------------------
    def load_markets(self, *, reload: bool = False) -> dict[str, Any]:
        if reload or not self._markets_loaded:
            self.exchange.load_markets()
            self._markets_loaded = True
        return self.exchange.markets

    def symbol_exists(self, symbol: str) -> bool:
        self.load_markets()
        return symbol in self.exchange.markets

    # ---- public market data ---------------------------------------------
    def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        self.load_markets()
        return self.exchange.fetch_ticker(symbol)

    def fetch_tickers(self, symbols: list[str] | None = None) -> dict[str, Any]:
        """Bulk ticker fetch (one call for all/given symbols).

        Used by the universe Scout to screen the whole spot market by 24h quote
        volume in a single request instead of N per-symbol calls.
        """
        self.load_markets()
        return self.exchange.fetch_tickers(symbols)

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
        since: int | None = None,
    ) -> list[list[int | float]]:
        """Return OHLCV candles as [ts, o, h, l, c, v]."""
        self.load_markets()
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)

    def fetch_ohlcv_history(
        self,
        symbol: str,
        timeframe: str = "1h",
        *,
        since: int | None = None,
        until: int | None = None,
        limit: int = 500,
        max_pages: int | None = None,
    ) -> list[list[int | float]]:
        """Paginate OHLCV forward from ``since`` to break the per-request cap.

        Most exchanges (MEXC included) cap a single ``fetch_ohlcv`` at ~500-1000
        candles. This loops, advancing the cursor past the last candle of each
        page, de-duplicating by timestamp. It stops on any of: an empty page, a
        page that fails to advance (duplicate/stuck-page guard), a short final
        page, reaching ``until``, or ``max_pages``. Returns candles ascending by
        timestamp. ``since``/``until`` are epoch milliseconds.
        """
        self.load_markets()
        tf_ms = int(self.exchange.parse_timeframe(timeframe) * 1000)
        cursor = since
        by_ts: dict[int, list[int | float]] = {}
        last_seen_ts: int | None = None
        pages = 0
        while max_pages is None or pages < max_pages:
            page = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=limit)
            pages += 1
            if not page:
                break
            for c in page:
                ts = int(c[0])
                if since is not None and ts < since:
                    continue  # defensive: ignore rows before the window
                if until is not None and ts > until:
                    continue
                by_ts[ts] = c
            page_last_ts = int(page[-1][0])
            if since is None:
                # "Latest page" semantics: without an explicit start we cannot
                # paginate forward (the next cursor would be in the future), so
                # return just this page instead of issuing a wasted request.
                break
            # Stuck-page guard: exchange returned nothing newer than the last page.
            if last_seen_ts is not None and page_last_ts <= last_seen_ts:
                break
            last_seen_ts = page_last_ts
            if until is not None and page_last_ts >= until:
                break
            if len(page) < limit:  # short page → reached the present
                break
            cursor = page_last_ts + tf_ms
        return [by_ts[ts] for ts in sorted(by_ts)]

    def fetch_order_book(self, symbol: str, limit: int = 100) -> dict[str, Any]:
        self.load_markets()
        return self.exchange.fetch_order_book(symbol, limit=limit)

    # ---- private reads (require authenticated key) ----------------------
    def fetch_balance(self) -> dict[str, Any]:
        return self.exchange.fetch_balance()

    # ---- private order surface (execution layer decides when to use it) --
    def create_order(
        self,
        symbol: str,
        side: str,
        amount: float | str,
        *,
        order_type: str = "market",
        price: float | str | None = None,
        post_only: bool = False,
        client_order_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.load_markets()
        merged_params: dict[str, Any] = dict(params or {})
        if post_only:
            merged_params["postOnly"] = True
        if client_order_id is not None:
            merged_params["clientOrderId"] = client_order_id
        precise_amount = (
            self.exchange.amount_to_precision(symbol, amount)
            if hasattr(self.exchange, "amount_to_precision")
            else amount
        )
        precise_price = None
        if price is not None:
            precise_price = (
                self.exchange.price_to_precision(symbol, price)
                if hasattr(self.exchange, "price_to_precision")
                else price
            )
        return self.exchange.create_order(
            symbol=symbol,
            type=order_type,
            side=side,
            amount=precise_amount,
            price=precise_price,
            params=merged_params,
        )

    def fetch_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        return self.exchange.fetch_order(order_id, symbol)

    def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        return self.exchange.cancel_order(order_id, symbol)

    # ---- health ----------------------------------------------------------
    def ping(self) -> bool:
        """Lightweight connectivity check."""
        try:
            self.exchange.fetch_status()
            return True
        except Exception as exc:
            log.error("mexc_ping_failed", error=str(exc))
            return False

    def fetch_server_time(self) -> int:
        return int(self.exchange.fetch_time())


def to_perp_symbol(spot_symbol: str) -> str:
    """Map a spot symbol to its ccxt unified linear-perp symbol.

    ``BTC/USDT`` -> ``BTC/USDT:USDT``. Pass-through if it is already a
    ``BASE/QUOTE:SETTLE`` perp symbol.
    """
    if ":" in spot_symbol:
        return spot_symbol
    base_quote = spot_symbol.upper()
    quote = base_quote.split("/")[1] if "/" in base_quote else "USDT"
    return f"{base_quote}:{quote}"


class MexcFuturesClient:
    """Read-only CCXT wrapper for MEXC perpetual swaps (carry track, C1).

    Exposes funding-rate history (and perp OHLCV) so the carry backtest can be
    built and validated against *real* data. Funding history is PUBLIC, so this
    defaults to unauthenticated — no futures key is needed for C1/C2 (data +
    backtest). Order placement is intentionally absent; it lands in C4 behind
    the neutral-book risk rails and a human gate.
    """

    def __init__(self, settings: Settings | None = None, *, authenticated: bool = False) -> None:
        self.settings = settings or get_settings()
        params = dict(_MEXC_SWAP_DEFAULTS)
        if authenticated:
            params.update(mexc_pkg.get_keys())
        self.exchange: ccxt.mexc = ccxt.mexc(params)
        self._markets_loaded = False

    def load_markets(self, *, reload: bool = False) -> dict[str, Any]:
        if reload or not self._markets_loaded:
            self.exchange.load_markets()
            self._markets_loaded = True
        return self.exchange.markets

    def fetch_funding_rate_history(
        self,
        symbol: str,
        *,
        since: int | None = None,
        until: int | None = None,
        limit: int = 200,
        max_pages: int | None = None,
        now_ms: int | None = None,
    ) -> list[dict[str, float]]:
        """Paginate settled funding rates forward from ``since``.

        Mirrors ``fetch_ohlcv_history``: loops past the per-request cap,
        de-duplicates by timestamp, and stops on an empty page, a stuck page, a
        short final page, reaching ``until``, or ``max_pages``. Accepts a spot or
        perp ``symbol`` (spot is auto-mapped to the perp). Returns rows
        ``{"ts": int, "funding_rate": float}`` ascending by ``ts``.

        Point-in-time: only *settled* funding is returned — any row dated at/after
        ``now_ms`` (the not-yet-settled current interval) is dropped so a partial
        rate never leaks into a backtest decision.
        """
        import time as _time

        self.load_markets()
        perp = to_perp_symbol(symbol)
        if now_ms is None:
            now_ms = int(_time.time() * 1000)
        cursor = since
        by_ts: dict[int, float] = {}
        last_seen_ts: int | None = None
        pages = 0
        while max_pages is None or pages < max_pages:
            page = self.exchange.fetch_funding_rate_history(perp, since=cursor, limit=limit)
            pages += 1
            if not page:
                break
            for entry in page:
                ts = entry.get("timestamp")
                rate = entry.get("fundingRate")
                if ts is None or rate is None:
                    continue
                ts = int(ts)
                if ts >= now_ms:
                    continue  # not-yet-settled current interval
                if since is not None and ts < since:
                    continue
                if until is not None and ts > until:
                    continue
                by_ts[ts] = float(rate)
            page_last_ts = int(page[-1]["timestamp"])
            if since is None:
                break  # latest-page semantics: cannot paginate forward
            if last_seen_ts is not None and page_last_ts <= last_seen_ts:
                break  # stuck-page guard
            last_seen_ts = page_last_ts
            if until is not None and page_last_ts >= until:
                break
            if len(page) < limit:
                break  # short page → reached the present
            cursor = page_last_ts + 1
        return [{"ts": ts, "funding_rate": by_ts[ts]} for ts in sorted(by_ts)]

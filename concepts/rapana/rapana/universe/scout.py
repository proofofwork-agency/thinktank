"""Live universe Scout — the only universe component that touches the network.

Discovers MEXC spot candidates, screens them by 24h quote volume (one bulk
ticker call), bounds the history fetch to the top-K, then delegates the actual
ranking decision to the pure ``rank_universe``. No LLM; the same ranking logic
is what the point-in-time backtest validates.
"""
from __future__ import annotations

import re

import pandas as pd

from rapana.agents.base import Agent
from rapana.logging import get_logger
from rapana.mexc.client import MexcClient
from rapana.universe.ranker import RankedSymbol, UniverseParams, rank_universe

log = get_logger(__name__)

# MEXC leveraged ETF tokens end in a digit + L/S (e.g. BTC3L, ETH5S). Matching a
# digit avoids false-positives on legit coins (e.g. JUP) that a bare "UP" rule hits.
_LEVERAGED_RE = re.compile(r"\d+[LS]$")
# Not exhaustive (new stablecoins appear constantly); a volatility-based filter is
# the more robust P3 fix. This catches the common pegged bases.
_STABLE_BASES = {
    "USDT", "USDC", "DAI", "TUSD", "BUSD", "FDUSD", "USDD", "PYUSD", "USDE",
    "EUR", "FRAX", "GUSD", "USDP", "USD1", "USDQ", "USDX", "XUSD", "EURT", "EURS", "USTC",
}


def _is_leveraged(base: str) -> bool:
    return bool(_LEVERAGED_RE.search(base.upper()))


class Scout(Agent):
    """Deterministic universe selector for the fleet."""

    role = "scout"

    def __init__(
        self,
        client: MexcClient,
        params: UniverseParams | None = None,
        *,
        timeframe: str = "1h",
        candidate_k: int = 50,
        history_bars: int | None = None,
    ) -> None:
        self.client = client
        self.params = params or UniverseParams()
        self.timeframe = timeframe
        self.candidate_k = candidate_k
        self.history_bars = history_bars or (self.params.momentum_lookback + 5)

    def discover_candidates(self) -> list[str]:
        """Eligible spot symbols: USDT-quoted, active, spot, non-leveraged, non-stable."""
        markets = self.client.load_markets()
        out: list[str] = []
        for symbol, m in markets.items():
            if m.get("quote") != "USDT" or not m.get("active"):
                continue
            if not (m.get("spot") or m.get("type") == "spot"):
                continue
            base = str(m.get("base") or "").upper()
            if base in _STABLE_BASES or _is_leveraged(base):
                continue
            out.append(symbol)
        return sorted(out)

    def prefilter_by_ticker(self, symbols: list[str]) -> list[str]:
        """Keep the top ``candidate_k`` eligible symbols by 24h quote volume.

        One bulk ticker call bounds the expensive per-symbol history fetch.
        """
        eligible = set(symbols)
        try:
            tickers = self.client.fetch_tickers()
        except Exception as exc:
            log.warning("scout_fetch_tickers_failed", error=str(exc))
            return symbols[: self.candidate_k]
        scored: list[tuple[float, str]] = []
        for sym, t in tickers.items():
            if sym not in eligible:
                continue
            qv = t.get("quoteVolume")
            if qv is None:
                qv = (t.get("last") or 0) * (t.get("baseVolume") or 0)
            scored.append((float(qv or 0.0), sym))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [sym for _, sym in scored[: self.candidate_k]]

    def fetch_candidate_history(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
        data: dict[str, pd.DataFrame] = {}
        for sym in symbols:
            try:
                raw = self.client.fetch_ohlcv(sym, timeframe=self.timeframe, limit=self.history_bars)
            except Exception as exc:
                log.warning("scout_fetch_ohlcv_failed", symbol=sym, error=str(exc))
                continue
            if raw:
                data[sym] = pd.DataFrame(
                    raw, columns=["ts", "open", "high", "low", "close", "volume"]
                )
        return data

    def select(self) -> list[RankedSymbol]:
        candidates = self.discover_candidates()
        top = self.prefilter_by_ticker(candidates)
        history = self.fetch_candidate_history(top)
        return rank_universe(history, self.params)

    def select_symbols(self) -> list[str]:
        return [r.symbol for r in self.select()]

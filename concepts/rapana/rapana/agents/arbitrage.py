from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from rapana.agents.base import Analyst
from rapana.signals import Signal

if TYPE_CHECKING:
    from rapana.fleet.data_provider import DataProvider


class Arbitrageur(Analyst):
    """Cross-venue spread / funding-basis scanner.

    Real arbitrage needs multi-venue market data. Inject `arb_fn(symbol) ->
    (edge_fraction[-1..1], confidence)`. Returns neutral without a feed —
    arbitrage is opportunistic, never a forced trade.
    """

    role = "arbitrageur"

    def __init__(self, arb_fn: Callable[[str], tuple[float, float]] | None = None) -> None:
        self.arb_fn = arb_fn

    def analyze(self, symbol: str, provider: DataProvider) -> Signal:
        if self.arb_fn is None:
            return Signal(symbol, "arbitrage", "neutral", 0.0, 0.0, "no arb feed configured")
        edge, confidence = self.arb_fn(symbol)
        direction = "bullish" if edge > 0.001 else "bearish" if edge < -0.001 else "neutral"
        return Signal(
            symbol, "arbitrage", direction, edge, confidence,
            f"estimated edge={edge:.4f}",
        )

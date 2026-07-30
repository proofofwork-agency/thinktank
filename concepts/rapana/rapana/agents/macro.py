from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from rapana.agents.base import Analyst
from rapana.signals import Signal

if TYPE_CHECKING:
    from rapana.fleet.data_provider import DataProvider


class MacroAnalyst(Analyst):
    """Macro / on-chain analyst.

    On-chain and macro data (ETF flows, whale moves, stablecoin supply) require
    external feeds (Glassnode/Santiment). Inject a `macro_fn(symbol) ->
    (score[-1..1], confidence[0..1])`. Without one it returns neutral.
    """

    role = "macro_analyst"

    def __init__(self, macro_fn: Callable[[str], tuple[float, float]] | None = None) -> None:
        self.macro_fn = macro_fn

    def analyze(self, symbol: str, provider: DataProvider) -> Signal:
        if self.macro_fn is None:
            return Signal(symbol, "macro", "neutral", 0.0, 0.0, "no macro/on-chain feed configured")
        score, confidence = self.macro_fn(symbol)
        direction = "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral"
        return Signal(symbol, "macro", direction, score, confidence, f"macro score={score:.2f}")

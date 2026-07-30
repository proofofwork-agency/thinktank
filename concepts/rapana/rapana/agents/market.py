from __future__ import annotations

from typing import TYPE_CHECKING

from rapana.agents.base import Analyst, blend
from rapana.signals import Signal
from rapana.strategies import Breakout, MeanReversion, TrendFollowing
from rapana.strategies.base import Strategy

if TYPE_CHECKING:
    from rapana.fleet.data_provider import DataProvider


class MarketAnalyst(Analyst):
    """Technical-analysis analyst: blends trend / mean-reversion / breakout reads.

    Default brain is deterministic (rule-based strategies). This is deliberate:
    the research synthesis found no evidence LLM judgement beats deterministic
    signals for execution, and deterministic logic is testable + safe. The
    strategy set is injectable for experimentation.
    """

    role = "market_analyst"

    def __init__(
        self,
        strategies: list[Strategy] | None = None,
        timeframe: str = "1h",
        lookback: int = 250,
    ) -> None:
        self.strategies = strategies or [TrendFollowing(), MeanReversion(), Breakout()]
        self.timeframe = timeframe
        self.lookback = lookback

    def analyze(self, symbol: str, provider: DataProvider) -> Signal:
        df = provider.get_history(symbol, self.timeframe, self.lookback)
        if df.empty or len(df) < 20:
            return Signal(symbol, "market", "neutral", 0.0, 0.0, "insufficient history")
        sub = [s.generate(df, symbol) for s in self.strategies]
        return blend(sub, symbol, "market")

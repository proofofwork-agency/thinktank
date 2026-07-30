from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from rapana.agents.base import Analyst
from rapana.agents.brain import Brain, DeterministicBrain
from rapana.indicators import rsi
from rapana.signals import Signal

if TYPE_CHECKING:
    from rapana.fleet.data_provider import DataProvider


class RegimeAnalyst(Analyst):
    """LLM market-regime analyst — ONE fenced vote among the analyst roster.

    Asks the configured Brain to classify the near-term regime from recent
    CLOSED price action + RSI, and maps the verdict to a Signal. Like every
    other analyst this is advisory only: the deterministic combiner + Portfolio
    Manager + risk gate still decide every order, so an LLM hallucination cannot
    single-handedly move money. Fail-soft to neutral on any error, weak parse,
    or when no real brain is configured (DeterministicBrain -> no-op).

    Forward-only: never wired into replay/backtest (a "now" LLM read must not
    leak into a past bar), so the orchestrator only adds it for forward runs.
    """

    role = "llm_regime"

    def __init__(self, brain: Brain | None = None, lookback: int = 50, timeframe: str = "1h") -> None:
        self.brain = brain or DeterministicBrain()
        self.lookback = lookback
        self.timeframe = timeframe

    def analyze(self, symbol: str, provider: DataProvider) -> Signal:
        if self.brain is None or isinstance(self.brain, DeterministicBrain):
            return Signal(symbol, "llm_regime", "neutral", 0.0, 0.0, "no LLM brain configured")
        try:
            df = provider.get_history(symbol, self.timeframe, self.lookback)
        except Exception as exc:
            return Signal(symbol, "llm_regime", "neutral", 0.0, 0.0, f"history error: {exc}")
        if df is None or getattr(df, "empty", True) or len(df) < 15:
            return Signal(symbol, "llm_regime", "neutral", 0.0, 0.0, "insufficient history")
        try:
            raw = self.brain.reason(self._prompt(symbol, df))
        except Exception as exc:
            return Signal(symbol, "llm_regime", "neutral", 0.0, 0.0, f"llm error: {exc}")
        return self._parse(symbol, raw)

    def _prompt(self, symbol: str, df: pd.DataFrame) -> str:
        close = df["close"].astype(float)
        last = float(close.iloc[-1])
        ret_n = float(close.iloc[-1] / close.iloc[0] - 1.0) if close.iloc[0] else 0.0
        ret_1 = float(close.iloc[-1] / close.iloc[-2] - 1.0) if len(close) > 1 and close.iloc[-2] else 0.0
        vol = float(close.pct_change().std())
        r = float(rsi(close, 14).iloc[-1])
        return (
            f"You are a crypto market-regime classifier. Symbol: {symbol} ({self.timeframe}).\n"
            f"Last close: {last:.6g}. {len(close)}-bar return: {ret_n * 100:.2f}%. "
            f"Last-bar return: {ret_1 * 100:.2f}%. Return volatility: {vol:.4f}. RSI(14): {r:.1f}.\n"
            f"Classify the likely direction of this symbol over the NEXT few bars.\n"
            f"Respond with EXACTLY two lines and nothing else:\n"
            f"REGIME: bullish|bearish|neutral\n"
            f"CONFIDENCE: <a float from 0.0 to 1.0>\n"
        )

    def _parse(self, symbol: str, raw: str) -> Signal:
        text = (raw or "").strip().lower()
        direction = "neutral"
        confidence = 0.0
        for line in text.splitlines():
            if line.startswith("regime"):
                if "bullish" in line:
                    direction = "bullish"
                elif "bearish" in line:
                    direction = "bearish"
            elif line.startswith("confidence"):
                try:
                    confidence = max(0.0, min(1.0, float(line.split(":")[-1].strip())))
                except ValueError:
                    confidence = 0.0
        if direction == "neutral" or confidence <= 0.0:
            return Signal(symbol, "llm_regime", "neutral", 0.0, 0.0, f"llm: {direction}")
        strength = confidence if direction == "bullish" else -confidence
        return Signal(
            symbol, "llm_regime", direction, strength, confidence,
            f"llm regime {direction} (conf {confidence:.2f})",
        )

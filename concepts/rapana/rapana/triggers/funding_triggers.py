"""Funding-rate event triggers on the perp funding grid.

Each row of a funding frame is one funding settlement: its timestamp, the spot
close at/below it, and the funding rate that settled there. The rate at row ``i``
is known at ``ts[i]`` (it covers the period just ended), and the study engine
enters at ``close[i+1]`` — so a funding reading never trades its own settlement,
identical to the candle engine's one-bar lag.

These are a DIFFERENT formulation from the carry/funding-spike studies: the
trigger fires on a structural funding event (a sign flip, or sustained one-sided
crowding) and the honest gate asks whether that event predicts the NEXT move
better than random entry (drift), net of costs.
"""
from __future__ import annotations

import pandas as pd

from rapana.triggers.base import Trigger, TriggerEvent


def build_funding_frame(
    store,
    perp_symbol: str,
    spot_symbol: str,
    timeframe: str = "1h",
) -> pd.DataFrame | None:
    """Build a funding-aligned frame: rows = funding settlements, with the spot
    close at/below each (point-in-time) and the funding rate. Returns None if
    there is not enough to study."""
    from rapana.backtest.funding_spike import align_funding_price

    funding = store.fetch_funding_range(perp_symbol)
    candles = store.fetch_candles_range(spot_symbol, timeframe)
    if not funding or not candles:
        return None
    kept, closes = align_funding_price(funding, candles)
    if len(kept) < 3:
        return None
    return pd.DataFrame({
        "ts": [int(r["ts"]) for r in kept],
        "close": [float(c) for c in closes],
        "funding": [float(r["funding_rate"]) for r in kept],
    })


def _sign(x: float) -> int:
    return 0 if x == 0 else (1 if x > 0 else -1)


class FundingFlip(Trigger):
    """Fire when the funding sign changes (a positioning regime flip).

    ``mode="momentum"`` trades WITH the new sign (positive flip -> long, betting
    the flip has legs); ``mode="fade"`` trades AGAINST it (mean reversion).
    """

    def __init__(self, horizon_intervals: int = 6, mode: str = "momentum") -> None:
        self.horizon_bars = horizon_intervals
        self.mode = mode
        self.name = f"fund_flip_{mode}_h{horizon_intervals}"

    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        f = df["funding"].to_numpy(dtype=float)
        events: list[TriggerEvent] = []
        for i in range(1, len(f)):
            ps, cs = _sign(f[i - 1]), _sign(f[i])
            if ps != 0 and cs != 0 and ps != cs:
                direction = cs if self.mode == "momentum" else -cs
                events.append(TriggerEvent(i, direction))
        return events


class FundingPersistent(Trigger):
    """Fire when funding has been one-signed AND above ``threshold`` for ``k``
    consecutive intervals (sustained crowd), then FADE that crowd. Distinct from
    the funding-spike study, which fades a single extreme reading."""

    def __init__(self, k: int = 3, threshold: float = 0.0003, horizon_intervals: int = 8) -> None:
        self.k = k
        self.threshold = threshold
        self.horizon_bars = horizon_intervals
        self.name = f"fund_persist_k{k}_t{round(threshold * 1_000_000)}_h{horizon_intervals}"

    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        f = df["funding"].to_numpy(dtype=float)
        k = self.k
        events: list[TriggerEvent] = []
        for i in range(k - 1, len(f)):
            window = f[i - k + 1:i + 1]
            if any(abs(x) <= self.threshold for x in window):
                continue
            if len({_sign(x) for x in window}) == 1:
                events.append(TriggerEvent(i, -_sign(window[-1])))  # fade the crowd
        return events


FUNDING_TRIGGERS: tuple[Trigger, ...] = (
    FundingFlip(horizon_intervals=6, mode="momentum"),
    FundingFlip(horizon_intervals=6, mode="fade"),
    FundingPersistent(k=3, threshold=0.0003, horizon_intervals=8),
    FundingPersistent(k=3, threshold=0.0005, horizon_intervals=8),
)

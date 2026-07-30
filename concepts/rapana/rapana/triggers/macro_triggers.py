"""Non-price event triggers built on stored macro series.

Unlike the OHLCV triggers (price-from-price, which the hunt showed is dead at
short horizons), these fire on an EXTERNAL signal — e.g. the Crypto Fear & Greed
index — and are the first genuinely different data source the hunter can test.

Point-in-time: Fear & Greed for day ``D`` is published at the close of day ``D``.
On a daily candle frame, bar ``i`` == day ``D`` closes when F&G[D] becomes known,
so firing at bar ``i`` is honest; the study engine then enters at ``close[i+1]``
(one-bar lag). To prevent a sub-daily frame from using a still-unpublished daily
value, the trigger fires at most once per UTC day, on the first bar of that day
whose value is already known.
"""
from __future__ import annotations

import pandas as pd

from rapana.triggers.base import Trigger, TriggerEvent

_DAY_MS = 86_400_000


class FearGreedExtreme(Trigger):
    """Fade Fear & Greed extremes: buy extreme fear, sell extreme greed."""

    def __init__(
        self,
        fg_rows: list[dict],
        low: float = 25.0,
        high: float = 75.0,
        horizon_bars: int = 5,
    ) -> None:
        self.low = low
        self.high = high
        self.horizon_bars = horizon_bars
        self.name = f"fg_lo{int(low)}_hi{int(high)}_h{horizon_bars}"
        self._by_day: dict[int, float] = {
            (int(r["ts"]) // _DAY_MS) * _DAY_MS: float(r["value"]) for r in fg_rows
        }

    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        ts = df["ts"].to_numpy()
        events: list[TriggerEvent] = []
        last_fired_day: int | None = None
        for i in range(len(ts)):
            day = (int(ts[i]) // _DAY_MS) * _DAY_MS
            if day == last_fired_day:
                continue
            v = self._by_day.get(day)
            if v is None:
                continue
            if v < self.low:
                events.append(TriggerEvent(i, 1))
                last_fired_day = day
            elif v > self.high:
                events.append(TriggerEvent(i, -1))
                last_fired_day = day
        return events

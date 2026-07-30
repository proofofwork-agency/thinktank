"""Seed trigger library — NEW event formulations on data we already store.

These are deliberately *events* (flat between firings), not the continuously-
held strategies that already failed the honesty gate. Each fires only on a
well-defined condition and holds a fixed horizon. Parameter variants are
pre-committed (no post-hoc mining) — the DSR deflates across all of them.

All detection uses only rows up to and including the firing bar; the study
engine enters one bar later, so no trigger ever trades its own detection bar.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from rapana.indicators import rsi
from rapana.triggers.base import Trigger, TriggerEvent

DEFAULT_TRIGGER_MANIFEST_VERSION = "2026-06-24.v1"
DEFAULT_TRIGGER_COMMITTED_ON = "2026-06-24"


class GapFade(Trigger):
    """Fade an outsized single-bar move (short-term mean reversion)."""

    def __init__(self, threshold: float = 0.03, horizon_bars: int = 4) -> None:
        self.threshold = threshold
        self.horizon_bars = horizon_bars
        self.name = f"gap_fade_{int(threshold * 10000)}bp_h{horizon_bars}"

    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        close = df["close"].to_numpy(dtype=float)
        events: list[TriggerEvent] = []
        for i in range(1, len(close)):
            prev = close[i - 1]
            if prev <= 0:
                continue
            ret = close[i] / prev - 1.0
            if abs(ret) > self.threshold:
                events.append(TriggerEvent(i, -1 if ret > 0 else 1))
        return events


class GapMomentum(Trigger):
    """Ride an outsized single-bar move in its OWN direction (short-term momentum).

    Pre-registered as the symmetric counterpart to GapFade: one side tests
    short-term reversion after a shock, the other tests continuation after the
    same shock. Both belong in the same external trial set.
    """

    def __init__(self, threshold: float = 0.03, horizon_bars: int = 4) -> None:
        self.threshold = threshold
        self.horizon_bars = horizon_bars
        self.name = f"gap_mom_{int(threshold * 10000)}bp_h{horizon_bars}"

    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        close = df["close"].to_numpy(dtype=float)
        events: list[TriggerEvent] = []
        for i in range(1, len(close)):
            prev = close[i - 1]
            if prev <= 0:
                continue
            ret = close[i] / prev - 1.0
            if abs(ret) > self.threshold:
                events.append(TriggerEvent(i, 1 if ret > 0 else -1))
        return events


class VolumeSpikeMomentum(Trigger):
    """Ride a volume spike in the direction of the bar that spiked."""

    def __init__(self, z: float = 2.5, lookback: int = 20, horizon_bars: int = 6) -> None:
        self.z = z
        self.lookback = lookback
        self.horizon_bars = horizon_bars
        self.name = f"vol_spike_z{z}_L{lookback}_h{horizon_bars}"

    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        vol = df["volume"].to_numpy(dtype=float)
        close = df["close"].to_numpy(dtype=float)
        L = self.lookback
        events: list[TriggerEvent] = []
        for i in range(L, len(vol)):
            window = vol[i - L:i]
            m = window.mean()
            sd = window.std()
            if m <= 0 or sd <= 0:
                continue
            if (vol[i] - m) / sd > self.z and close[i - 1] > 0:
                direction = 1 if close[i] > close[i - 1] else -1
                events.append(TriggerEvent(i, direction))
        return events


class BreakoutLong(Trigger):
    """Go long when close breaks above the prior N-bar high (continuation)."""

    def __init__(self, lookback: int = 20, horizon_bars: int = 12) -> None:
        self.lookback = lookback
        self.horizon_bars = horizon_bars
        self.name = f"breakout_long_L{lookback}_h{horizon_bars}"

    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        close = df["close"].to_numpy(dtype=float)
        L = self.lookback
        events: list[TriggerEvent] = []
        for i in range(L, len(close)):
            if close[i - L:i].max() < close[i] > 0:
                events.append(TriggerEvent(i, 1))
        return events


class BreakoutFade(Trigger):
    """Fade a close that breaks the prior N-bar high/low (false-breakout reversion)."""

    def __init__(self, lookback: int = 20, horizon_bars: int = 6) -> None:
        self.lookback = lookback
        self.horizon_bars = horizon_bars
        self.name = f"breakout_fade_L{lookback}_h{horizon_bars}"

    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        close = df["close"].to_numpy(dtype=float)
        L = self.lookback
        events: list[TriggerEvent] = []
        for i in range(L, len(close)):
            prior = close[i - L:i]
            hi, lo = prior.max(), prior.min()
            if close[i] <= 0:
                continue
            if close[i] > hi:
                events.append(TriggerEvent(i, -1))
            elif close[i] < lo:
                events.append(TriggerEvent(i, 1))
        return events


class RsiExtreme(Trigger):
    """Bounce off RSI extremes: buy oversold, sell overbought (mean reversion)."""

    def __init__(self, period: int = 14, low: float = 30.0, high: float = 70.0,
                 horizon_bars: int = 8) -> None:
        self.period = period
        self.low = low
        self.high = high
        self.horizon_bars = horizon_bars
        self.name = f"rsi_p{period}_lo{int(low)}_hi{int(high)}_h{horizon_bars}"

    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        r = rsi(df["close"], self.period).to_numpy(dtype=float)
        events: list[TriggerEvent] = []
        for i in range(self.period, len(r)):  # skip the indicator warmup
            v = r[i]
            if v < self.low:
                events.append(TriggerEvent(i, 1))
            elif v > self.high:
                events.append(TriggerEvent(i, -1))
        return events


@dataclass(frozen=True)
class TriggerManifestEntry:
    """One precommitted DEFAULT_TRIGGERS trial with rationale and date."""

    trigger: Trigger
    rationale: str
    committed_on: str = DEFAULT_TRIGGER_COMMITTED_ON


# DEFAULT_TRIGGERS is a dated, versioned precommitted manifest. Adding,
# removing, or changing any trigger after seeing results is a cumulative
# external trial and must be disclosed/deflated outside this in-run DSR.
DEFAULT_TRIGGER_MANIFEST: tuple[TriggerManifestEntry, ...] = (
    TriggerManifestEntry(
        GapFade(0.03, 4),
        "Short-horizon mean reversion after a 3% one-bar shock.",
    ),
    TriggerManifestEntry(
        GapFade(0.05, 4),
        "Same shock-fade hypothesis at a higher 5% activation threshold.",
    ),
    TriggerManifestEntry(
        GapMomentum(0.03, 4),
        "Symmetric continuation test after a 3% one-bar shock.",
    ),
    TriggerManifestEntry(
        GapMomentum(0.05, 4),
        "Symmetric continuation test after a higher 5% one-bar shock.",
    ),
    TriggerManifestEntry(
        VolumeSpikeMomentum(2.5, 20, 6),
        "Volume anomaly plus same-bar direction as a short continuation event.",
    ),
    TriggerManifestEntry(
        BreakoutLong(20, 12),
        "Prior 20-bar high breakout as a continuation event.",
    ),
    TriggerManifestEntry(
        BreakoutFade(20, 6),
        "Prior 20-bar high/low break as a false-breakout reversion event.",
    ),
    TriggerManifestEntry(
        RsiExtreme(14, 30, 70, 8),
        "Classic RSI 30/70 extreme as a short-horizon reversion event.",
    ),
    TriggerManifestEntry(
        RsiExtreme(14, 25, 75, 8),
        "Stricter RSI 25/75 extreme as the paired high-conviction variant.",
    ),
)

DEFAULT_TRIGGERS: tuple[Trigger, ...] = tuple(entry.trigger for entry in DEFAULT_TRIGGER_MANIFEST)

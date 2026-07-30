"""Trigger primitives for the alpha-hunt track.

A *trigger* is a fixed-horizon event signal: when some condition fires at bar
``i`` (decided only from data up to and including ``i``), take a directional
position and hold it for ``horizon_bars``. The study engine measures the
forward return of every event out-of-sample and applies the same Deflated
Sharpe honesty gate as the rest of the codebase.

This is a deliberately different formulation from the continuously-held
strategies that already failed the gate: an overlay that is FLAT between
events, benchmarked against CASH, not buy-and-hold.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TriggerEvent:
    """A single trigger firing.

    ``bar`` is the row index in the OHLCV frame at which the condition became
    true (using rows ``<= bar`` only). The study engine enters ONE bar later to
    avoid any same-bar lookahead.
    """

    bar: int
    direction: int  # +1 = long, -1 = short


class Trigger(ABC):
    """A fixed-horizon event trigger."""

    name: str
    horizon_bars: int

    @abstractmethod
    def detect(self, df: pd.DataFrame) -> list[TriggerEvent]:
        """Return every bar where this trigger fires, with its trade direction."""
        raise NotImplementedError

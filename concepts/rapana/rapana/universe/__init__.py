"""Deterministic trading-universe selection (pair screening + ranking).

The pure ranker (``ranker``) has no network/clock/IO and is reused by both the
live ``Scout`` and the point-in-time backtest, so the same selection logic that
runs live is exactly what gets validated.
"""
from rapana.universe.ranker import (
    RankedSymbol,
    UniverseParams,
    bars_per_day_for,
    rank_universe,
    select_symbols,
)

__all__ = [
    "RankedSymbol", "UniverseParams", "bars_per_day_for", "rank_universe", "select_symbols",
]

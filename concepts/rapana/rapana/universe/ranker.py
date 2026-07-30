"""Pure, deterministic universe ranking — NO network, NO clock, NO I/O.

This is the anti-hindsight linchpin. ``rank_universe`` takes candidate OHLCV
history and returns screened, ranked symbols. The caller owns the data window,
so the SAME function ranks the live universe and each point-in-time backtest
fold — there is no way for "now" to leak in.

Kept deliberately small (3 real parameters) to resist overfitting the selector.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from rapana.indicators import rolling_volatility


@dataclass(frozen=True)
class UniverseParams:
    top_n: int = 5
    min_quote_volume_usd: float = 2_000_000.0  # median DAILY dollar-volume floor
    momentum_lookback: int = 30                 # bars for the return + vol window
    vol_floor: float = 1e-4                     # guards div-by-zero on flat coins
    bars_per_day: int = 24                      # daily-normalizes per-bar volume (1h=24)


_BARS_PER_DAY = {"1m": 1440, "5m": 288, "15m": 96, "30m": 48, "1h": 24, "4h": 6, "1d": 1}


def bars_per_day_for(timeframe: str) -> int:
    """Bars per 24h for a timeframe, so the liquidity floor means the same $/day everywhere."""
    return _BARS_PER_DAY.get(timeframe, 24)


@dataclass(frozen=True)
class RankedSymbol:
    symbol: str
    score: float
    dollar_volume: float
    momentum: float
    volatility: float


def liquidity(df: pd.DataFrame, lookback: int, bars_per_day: int = 24) -> float:
    """Median DAILY dollar-volume = median(close*volume) over ``lookback`` bars * bars/day.

    Median (not mean) so one fat print (wash trade / listing spike) can't smuggle
    a thin coin past the screen. Daily-normalized so the floor is timeframe-agnostic.
    """
    if df is None or len(df) == 0:
        return 0.0
    dollar = (df["close"] * df["volume"]).tail(lookback)
    return float(dollar.median()) * bars_per_day if len(dollar) else 0.0


def risk_adjusted_momentum(
    df: pd.DataFrame, lookback: int, vol_floor: float
) -> tuple[float, float, float]:
    """Return ``(score, momentum, volatility)`` computed from ``df`` only.

    momentum   = close[-1] / close[-1-lookback] - 1
    volatility = rolling_volatility(close, lookback).iloc[-1]   (per-bar return std)
    score      = momentum / max(volatility, vol_floor)
    """
    close = df["close"]
    if len(close) < lookback + 1:
        return (float("nan"), float("nan"), float("nan"))
    past = float(close.iloc[-1 - lookback])
    if past <= 0:
        return (float("nan"), float("nan"), float("nan"))
    momentum = float(close.iloc[-1]) / past - 1.0
    vol = float(rolling_volatility(close, lookback).iloc[-1])
    if not math.isfinite(vol):
        return (float("nan"), momentum, float("nan"))
    score = momentum / max(vol, vol_floor)
    return (score, momentum, vol)


def rank_universe(
    candidates: dict[str, pd.DataFrame], params: UniverseParams
) -> list[RankedSymbol]:
    """Pure: candidate history in -> screened, ranked symbols out.

    1. compute liquidity + risk-adjusted momentum per candidate,
    2. drop those below the liquidity floor or with a non-finite score,
    3. sort by score DESC then symbol ASC (deterministic tie-break),
    4. return the top ``top_n``.
    """
    ranked: list[RankedSymbol] = []
    for symbol in sorted(candidates):
        df = candidates[symbol]
        if df is None or len(df) < params.momentum_lookback + 1:
            continue
        dv = liquidity(df, params.momentum_lookback, params.bars_per_day)
        # `nan < floor` is False, so NaN volume would otherwise slip the screen.
        if not math.isfinite(dv) or dv < params.min_quote_volume_usd:
            continue
        score, momentum, vol = risk_adjusted_momentum(
            df, params.momentum_lookback, params.vol_floor
        )
        if not math.isfinite(score):
            continue
        ranked.append(RankedSymbol(symbol, score, dv, momentum, vol))
    ranked.sort(key=lambda r: (-r.score, r.symbol))
    return ranked[: params.top_n]


def select_symbols(candidates: dict[str, pd.DataFrame], params: UniverseParams) -> list[str]:
    """Convenience wrapper: just the ranked symbol strings."""
    return [r.symbol for r in rank_universe(candidates, params)]

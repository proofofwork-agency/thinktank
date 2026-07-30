"""Technical indicators built on pandas (no external TA C-dependency).

All functions accept a pandas Series (or DataFrame for ATR) and return Series,
so they can be composed into strategies and tested deterministically.
"""
from __future__ import annotations

import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder-style RSI. Robust to flat (zero-loss) windows via fillna(100)."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    out = 100 - (100 / (1 + rs))
    return out.fillna(100.0)


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range. df must have high/low/close columns."""
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def bollinger(
    series: pd.Series, period: int = 20, std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ma = series.rolling(period).mean()
    sd = series.rolling(period).std(ddof=0)
    upper = ma + std * sd
    lower = ma - std * sd
    return ma, upper, lower


def rolling_volatility(series: pd.Series, period: int = 20) -> pd.Series:
    """Annualized-ish volatility proxy: rolling std of bar returns."""
    returns = series.pct_change()
    return returns.rolling(period).std()

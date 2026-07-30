"""Walk-forward out-of-sample validation (D2).

Honest backtesting: instead of one window with a cherry-picked config, replay
each strategy across many consecutive out-of-sample (OOS) segments it never had
to "see" first, then correct the headline result for the number of trials with
the Deflated Sharpe Ratio. Lives OUTSIDE BacktestEngine and reuses it per fold.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from rapana.backtest.engine import BARS_PER_YEAR, BacktestConfig, BacktestEngine
from rapana.backtest.metrics import deflated_sharpe_ratio
from rapana.logging import get_logger
from rapana.strategies.base import Strategy

log = get_logger(__name__)


@dataclass
class FoldResult:
    fold: int
    bars: int
    total_return: float
    sharpe: float  # annualized (display only)
    max_drawdown: float
    trades: int


@dataclass
class ConfigResult:
    symbol: str
    strategy: str
    folds: list[FoldResult]
    oos_return: float          # compounded across folds
    oos_sharpe_annual: float   # pooled OOS Sharpe, annualized (display)
    oos_sharpe_bar: float      # pooled per-bar OOS Sharpe (drives the DSR)
    n_obs: int                 # pooled OOS bars
    skew: float
    kurtosis: float            # raw (normal = 3)
    pct_folds_positive: float
    worst_fold_return: float

    @property
    def label(self) -> str:
        return f"{self.symbol} {self.strategy}"


@dataclass
class ValidationReport:
    timeframe: str
    n_splits: int
    warmup: int
    configs: list[ConfigResult]
    n_trials: int
    best: ConfigResult | None
    deflated_sharpe: float
    is_significant: bool
    hodl_return: float = 0.0   # buy-and-hold over the same OOS windows
    passed: bool = False       # significant AND beats HODL


def make_test_folds(n: int, n_splits: int, warmup: int) -> list[tuple[int, int, int]]:
    """Contiguous, non-overlapping OOS test segments after an initial warmup.

    Returns ``(engine_start, test_start, test_end)`` index triples. Each fold
    feeds the engine ``warmup`` bars of lookback before its test segment so
    indicators are valid, but only the test segment counts toward OOS metrics.
    """
    usable = n - warmup
    if n_splits < 1 or usable < n_splits:
        return []
    seg = usable // n_splits
    folds: list[tuple[int, int, int]] = []
    for k in range(n_splits):
        test_start = warmup + k * seg
        test_end = n if k == n_splits - 1 else warmup + (k + 1) * seg
        engine_start = max(0, test_start - warmup)
        folds.append((engine_start, test_start, test_end))
    return folds


def _oos_equity(eq: pd.Series, sl: pd.DataFrame, first_oos_pos: int) -> pd.Series:
    """OOS slice of an engine equity curve, anchored on the bar BEFORE the first
    OOS bar so that bar's move + entry cost are counted (not dropped).

    Single source of truth for the OOS boundary, shared by every validator.
    """
    base = max(first_oos_pos - 1, 1)
    base_ts = int(sl["ts"].iloc[base]) if base < len(sl) else None
    return eq[eq.index >= base_ts] if base_ts is not None else eq.iloc[0:0]


def _pooled_record(
    symbol: str, strategy: str, fold_results: list[FoldResult],
    oos_returns: list[float], compounded: float, positive: int, bpy: float,
) -> ConfigResult | None:
    """Aggregate per-fold results + pooled per-bar OOS returns into a ConfigResult."""
    if not fold_results or len(oos_returns) < 2:
        return None
    s = pd.Series(oos_returns)
    std = float(s.std(ddof=0)) or 1e-9
    sharpe_bar = float(s.mean()) / std
    skew = float(s.skew()) if len(s) > 2 else 0.0
    kurt = float(s.kurt()) + 3.0 if len(s) > 3 else 3.0  # pandas kurt is excess
    skew = 0.0 if math.isnan(skew) else skew
    kurt = 3.0 if math.isnan(kurt) else kurt
    return ConfigResult(
        symbol=symbol, strategy=strategy, folds=fold_results,
        oos_return=compounded - 1.0,
        oos_sharpe_annual=sharpe_bar * math.sqrt(bpy),
        oos_sharpe_bar=sharpe_bar, n_obs=len(s),
        skew=skew, kurtosis=kurt,
        pct_folds_positive=positive / len(fold_results),
        worst_fold_return=min(f.total_return for f in fold_results),
    )


def deflated_best(records: list[ConfigResult]) -> tuple[ConfigResult | None, float]:
    """Best record by per-bar OOS Sharpe, deflated by the number of trials (their
    cross-sectional Sharpe variance is the multiple-testing input)."""
    if not records:
        return None, 0.0
    best = max(records, key=lambda c: c.oos_sharpe_bar)
    bars = [c.oos_sharpe_bar for c in records]
    var = float(pd.Series(bars).var(ddof=1)) if len(bars) > 1 else 1e-12
    var = var if var > 0 else 1e-12
    dsr = deflated_sharpe_ratio(
        best.oos_sharpe_bar, sharpe_variance=var, n_trials=max(len(records), 1),
        n_obs=best.n_obs, skew=best.skew, kurtosis=best.kurtosis,
    )
    return best, dsr


def hodl_oos_return(df: pd.DataFrame, n_splits: int, warmup: int) -> float:
    """Buy-and-hold return over the SAME OOS windows the walk-forward uses
    (price-only, no fees) — the honest "just held it" benchmark."""
    compounded = 1.0
    for es, ts, te in make_test_folds(len(df), n_splits, warmup):
        sl = df.iloc[es:te].reset_index(drop=True)
        base = max(ts - es - 1, 1)
        if len(sl) < 3 or base >= len(sl):
            continue
        first = float(sl["close"].iloc[base])
        if first > 0:
            compounded *= float(sl["close"].iloc[-1]) / first
    return compounded - 1.0


def holdout_split(
    df: pd.DataFrame, holdout: float, warmup: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into (walk-forward, locked-holdout). The holdout is the final
    ``holdout`` fraction; its slice keeps ``warmup`` lookback bars before it so
    indicators are valid. The walk-forward part never sees the holdout, so the
    holdout can be evaluated exactly once (no tuning against it)."""
    n = len(df)
    split = int(n * (1.0 - holdout))
    wf = df.iloc[:split].reset_index(drop=True)
    hold = df.iloc[max(0, split - warmup):].reset_index(drop=True)
    return wf, hold


def validate_config(
    df: pd.DataFrame,
    strategy_factory: type[Strategy],
    symbol: str,
    *,
    n_splits: int,
    warmup: int,
    timeframe: str,
    config: BacktestConfig | None = None,
) -> ConfigResult | None:
    """Run one strategy across all OOS folds of ``df``; pool the OOS results."""
    cfg = config or BacktestConfig(timeframe=timeframe)
    bpy = BARS_PER_YEAR.get(timeframe, 24 * 365)
    folds_meta = make_test_folds(len(df), n_splits, warmup)
    if not folds_meta:
        return None

    fold_results: list[FoldResult] = []
    oos_returns: list[float] = []  # concatenated OOS per-bar returns
    compounded = 1.0
    positive = 0

    for k, (es, ts, te) in enumerate(folds_meta):
        sl = df.iloc[es:te].reset_index(drop=True)
        if len(sl) < 3:
            continue
        res = BacktestEngine(cfg).run(sl, strategy_factory(), symbol)
        offset = ts - es  # first OOS bar in slice coordinates
        oos_eq = _oos_equity(res.equity_curve, sl, offset)
        if len(oos_eq) < 2:
            continue
        rets = oos_eq.pct_change().dropna()
        oos_returns.extend(float(r) for r in rets)
        fold_ret = float(oos_eq.iloc[-1] / oos_eq.iloc[0] - 1.0)
        compounded *= 1.0 + fold_ret
        positive += fold_ret > 0
        std = float(rets.std(ddof=0)) or 1e-9
        f_sharpe = float(rets.mean()) / std * math.sqrt(bpy)
        run_max = oos_eq.cummax()
        dd = float(((oos_eq - run_max) / run_max).min())
        oos_trades = sum(1 for t in res.trades if t["bar"] >= offset)
        fold_results.append(FoldResult(k, len(rets), fold_ret, f_sharpe, dd, oos_trades))

    return _pooled_record(
        symbol, getattr(strategy_factory(), "name", "strategy"),
        fold_results, oos_returns, compounded, positive, bpy,
    )


def validate_grid(
    data: dict[str, pd.DataFrame],
    strategies: dict[str, type[Strategy]],
    *,
    n_splits: int = 6,
    warmup: int = 60,
    timeframe: str = "1h",
    config: BacktestConfig | None = None,
) -> ValidationReport:
    """Validate every (symbol, strategy) and deflate the best by the trial count."""
    configs: list[ConfigResult] = []
    for symbol, df in data.items():
        for cls in strategies.values():
            cr = validate_config(
                df, cls, symbol, n_splits=n_splits, warmup=warmup,
                timeframe=timeframe, config=config,
            )
            if cr is not None:
                configs.append(cr)

    n_trials = len(configs)
    best, dsr = deflated_best(configs)
    hodl = hodl_oos_return(data[best.symbol], n_splits, warmup) if best is not None else 0.0
    passed = bool(best is not None and dsr > 0.95 and best.oos_return > hodl)

    return ValidationReport(
        timeframe=timeframe,
        n_splits=n_splits,
        warmup=warmup,
        configs=configs,
        n_trials=n_trials,
        best=best,
        deflated_sharpe=dsr,
        is_significant=dsr > 0.95,
        hodl_return=hodl,
        passed=passed,
    )

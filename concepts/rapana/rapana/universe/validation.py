"""Point-in-time validation of the universe Scout (P2).

The honesty test for pair selection: at each walk-forward fold the universe is
re-selected using ONLY data BEFORE the fold, then traded on that fold's OOS
segment. Compares the Scout-selected top-N against a fixed benchmark (the
majors). Reuses the exact OOS-boundary / pooling / Deflated-Sharpe logic from
``rapana.backtest.validation``.

SURVIVORSHIP CAVEAT: candidates are symbols listed on MEXC TODAY; coins delisted
before now are absent, so realized OOS returns are an optimistic upper bound.
Point-in-time selection removes look-ahead in RANKING — it cannot resurrect
delisted names.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from rapana.backtest.engine import BARS_PER_YEAR, BacktestConfig, BacktestEngine
from rapana.backtest.validation import (
    ConfigResult,
    FoldResult,
    _oos_equity,
    _pooled_record,
    deflated_best,
    make_test_folds,
)
from rapana.logging import get_logger
from rapana.strategies.base import Strategy
from rapana.universe.ranker import UniverseParams, select_symbols

log = get_logger(__name__)

SURVIVORSHIP_WARNING = (
    "SURVIVORSHIP CAVEAT: candidates are symbols listed on MEXC today; coins "
    "delisted before now are absent, so OOS returns are an optimistic upper bound. "
    "Point-in-time selection removes look-ahead in ranking, not survivorship."
)


@dataclass
class UniverseValidationReport:
    timeframe: str
    n_splits: int
    warmup: int
    scout: ConfigResult | None
    benchmark: ConfigResult | None
    best_label: str
    deflated_sharpe: float
    is_significant: bool
    n_candidates: int
    survivorship_warning: str = SURVIVORSHIP_WARNING
    hodl_return: float = 0.0   # equal-weight buy-and-hold of the benchmark majors
    passed: bool = False       # significant AND best arm beats HODL


def select_universe_pit(
    candidates: dict[str, pd.DataFrame], params: UniverseParams, test_start_ts: int
) -> list[str]:
    """Select the universe using ONLY bars strictly before ``test_start_ts``.

    The lookahead firewall: ``rank_universe`` never sees a bar at/after the fold
    start, so a fold's universe cannot be chosen with knowledge of its own future.
    """
    pre = {s: df[df["ts"] < test_start_ts] for s, df in candidates.items()}
    return select_symbols(pre, params)


def _fold_oos_returns_ts(
    df: pd.DataFrame, engine_start_ts: int, test_start_ts: int, test_end_ts: int,
    strategy_factory: type[Strategy], symbol: str, cfg: BacktestConfig,
) -> pd.Series:
    """One symbol's OOS per-bar returns for a TIMESTAMP-bounded fold (so symbols
    with differing histories still align). Empty Series if too short."""
    sl = df[(df["ts"] >= engine_start_ts) & (df["ts"] < test_end_ts)].reset_index(drop=True)
    if len(sl) < 3:
        return pd.Series(dtype=float)
    res = BacktestEngine(cfg).run(sl, strategy_factory(), symbol)
    oos_pos = sl.index[sl["ts"] >= test_start_ts]
    if len(oos_pos) == 0:
        return pd.Series(dtype=float)
    first = int(oos_pos[0])
    if first < 2:
        # No pre-OOS equity anchor in this fold (the engine has no equity point at
        # bar 0); skip this symbol-fold rather than anchor on an OOS/future bar.
        return pd.Series(dtype=float)
    oos_eq = _oos_equity(res.equity_curve, sl, first)
    if len(oos_eq) < 2:
        return pd.Series(dtype=float)
    # Keep the TIMESTAMP index so the basket pools align by date, not by ordinal
    # position (critical for symbols with ragged/missing histories).
    return oos_eq.pct_change().dropna()


def _run_arm(
    candidates: dict[str, pd.DataFrame],
    picker: Callable[[int], list[str]],
    strategy_factory: type[Strategy],
    ref_ts: list[int],
    folds_idx: list[tuple[int, int, int]],
    cfg: BacktestConfig,
    bpy: float,
    label: str,
) -> ConfigResult | None:
    """Walk-forward for one selection rule; equal-weight pool the fold's picks."""
    fold_results: list[FoldResult] = []
    oos_returns: list[float] = []
    compounded = 1.0
    positive = 0
    for k, (es, ts, te) in enumerate(folds_idx):
        test_start_ts = int(ref_ts[ts])
        engine_start_ts = int(ref_ts[es])
        test_end_ts = int(ref_ts[te]) if te < len(ref_ts) else int(ref_ts[-1]) + 1
        picks = picker(test_start_ts)
        if not picks:
            continue
        series: list[pd.Series] = []
        for sym in picks:
            df = candidates.get(sym)
            if df is None:
                continue
            r = _fold_oos_returns_ts(
                df, engine_start_ts, test_start_ts, test_end_ts, strategy_factory, sym, cfg
            )
            if len(r):
                series.append(r)
        if not series:
            continue
        # Align per-symbol returns BY TIMESTAMP, then equal-weight across whichever
        # symbols exist at each bar (sort so compounding/drawdown are time-ordered).
        pooled = pd.concat(series, axis=1).mean(axis=1).sort_index().dropna()
        if len(pooled) < 1:
            continue
        oos_returns.extend(float(x) for x in pooled)
        fold_ret = float((1.0 + pooled).prod() - 1.0)
        compounded *= 1.0 + fold_ret
        positive += fold_ret > 0
        std = float(pooled.std(ddof=0)) or 1e-9
        f_sharpe = float(pooled.mean()) / std * math.sqrt(bpy)
        eqc = (1.0 + pooled).cumprod()
        dd = float(((eqc - eqc.cummax()) / eqc.cummax()).min())
        fold_results.append(FoldResult(k, len(pooled), fold_ret, f_sharpe, dd, len(picks)))
    return _pooled_record("UNIVERSE", label, fold_results, oos_returns, compounded, positive, bpy)


def _hodl_basket(
    candidates: dict[str, pd.DataFrame], symbols: list[str],
    ref_ts: list[int], folds_idx: list[tuple[int, int, int]],
) -> float:
    """Equal-weight buy-and-hold of ``symbols`` over the OOS folds (price-only)."""
    compounded = 1.0
    for _es, ts, te in folds_idx:
        start_ts = int(ref_ts[ts])
        end_ts = int(ref_ts[te]) if te < len(ref_ts) else int(ref_ts[-1]) + 1
        rets: list[float] = []
        for sym in symbols:
            df = candidates.get(sym)
            if df is None:
                continue
            # Anchor on the last bar BEFORE the OOS window so the FIRST OOS bar's
            # move is counted — apples-to-apples with the strategy arms (which
            # include it via the pre-OOS equity anchor). Anchoring at the first
            # OOS bar instead would silently drop that bar and understate HODL.
            pre = df[df["ts"] < start_ts]
            oos = df[(df["ts"] >= start_ts) & (df["ts"] < end_ts)]
            if len(pre) == 0 or len(oos) == 0:
                continue
            anchor = float(pre["close"].iloc[-1])
            if anchor > 0:
                rets.append(float(oos["close"].iloc[-1]) / anchor - 1.0)
        if rets:
            compounded *= 1.0 + sum(rets) / len(rets)
    return compounded - 1.0


def validate_universe(
    candidates: dict[str, pd.DataFrame],
    strategy_factory: type[Strategy],
    params: UniverseParams,
    *,
    n_splits: int = 6,
    warmup: int = 60,
    timeframe: str = "1h",
    config: BacktestConfig | None = None,
    benchmark_symbols: list[str] | None = None,
) -> UniverseValidationReport:
    """Compare Scout-selected (point-in-time) vs a fixed benchmark universe, OOS."""
    cfg = config or BacktestConfig(timeframe=timeframe)
    bpy = BARS_PER_YEAR.get(timeframe, 24 * 365)
    # Reference timeline = the longest candidate; it defines fold boundaries.
    reference = max(candidates.values(), key=len) if candidates else pd.DataFrame({"ts": []})
    ref_ts = [int(t) for t in reference["ts"].tolist()]
    folds_idx = make_test_folds(len(ref_ts), n_splits, warmup)
    if not folds_idx:
        return UniverseValidationReport(
            timeframe, n_splits, warmup, None, None, "-", 0.0, False, len(candidates),
        )

    scout_rec = _run_arm(
        candidates, lambda t: select_universe_pit(candidates, params, t),
        strategy_factory, ref_ts, folds_idx, cfg, bpy, "scout",
    )
    bench = [s.upper() for s in (benchmark_symbols or [])]
    bench_rec = (
        _run_arm(candidates, lambda _t: bench, strategy_factory, ref_ts, folds_idx, cfg, bpy, "fixed")
        if bench else None
    )

    records = [r for r in (scout_rec, bench_rec) if r is not None]
    best, dsr = deflated_best(records)
    hodl = _hodl_basket(candidates, bench, ref_ts, folds_idx) if bench else 0.0
    best_ret = best.oos_return if best is not None else 0.0
    passed = bool(best is not None and dsr > 0.95 and best_ret > hodl)
    return UniverseValidationReport(
        timeframe=timeframe, n_splits=n_splits, warmup=warmup,
        scout=scout_rec, benchmark=bench_rec,
        best_label=best.strategy if best else "-",
        deflated_sharpe=dsr, is_significant=dsr > 0.95,
        n_candidates=len(candidates),
        hodl_return=hodl, passed=passed,
    )

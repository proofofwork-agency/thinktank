"""Family-specific evaluators that wrap existing honest validators."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

import pandas as pd

from rapana.backtest.cross_sectional import (
    load_store_universe,
    validate_cross_sectional_config,
    validate_cross_sectional_grid,
)
from rapana.backtest.engine import BacktestConfig
from rapana.backtest.metrics import deflated_sharpe_ratio
from rapana.backtest.validation import (
    holdout_split,
    validate_config,
)
from rapana.data.store import TimeSeriesStore
from rapana.research.evolve.catalog import Hypothesis
from rapana.research.evolve.gates import TrialMetrics
from rapana.strategies.breakout import Breakout
from rapana.strategies.meanrev import MeanReversion
from rapana.strategies.trend import TrendFollowing
from rapana.triggers.ohlcv_triggers import (
    BreakoutFade,
    BreakoutLong,
    GapFade,
    GapMomentum,
    RsiExtreme,
    VolumeSpikeMomentum,
)
from rapana.triggers.study import run_hunt, run_pooled_hunt, study_trigger_pooled


@dataclass
class EvalResult:
    metrics: TrialMetrics
    detail: dict[str, Any]


def _load_ohlcv(
    store: TimeSeriesStore,
    timeframe: str,
    symbols: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    if symbols is None:
        symbols = store.symbols(timeframe)
    out: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        rows = store.fetch_candles_range(sym, timeframe)
        if not rows or len(rows) < 80:
            continue
        out[sym] = pd.DataFrame(
            rows, columns=["ts", "open", "high", "low", "close", "volume"]
        )
    return out


def _strategy_factory(params: dict[str, Any]) -> Callable[[], Any]:
    name = params.get("strategy", "trend")

    def factory():
        if name == "trend":
            s = TrendFollowing(
                fast=int(params.get("fast", 20)),
                slow=int(params.get("slow", 50)),
            )
        elif name == "meanrev":
            s = MeanReversion(
                period=int(params.get("period", 14)),
                oversold=float(params.get("oversold", 35)),
                overbought=float(params.get("overbought", 65)),
            )
        elif name == "breakout":
            s = Breakout(
                period=int(params.get("period", 20)),
                std=float(params.get("std", 2.0)),
            )
        else:
            raise ValueError(f"unknown strategy {name!r}")
        # Unique label for logs / ConfigResult
        s.name = params.get("label") or f"{name}-{_param_tag(params)}"
        return s

    return factory


def _param_tag(params: dict[str, Any]) -> str:
    skip = {
        "strategy", "timeframe", "fee_pct", "slippage_pct", "vol_target",
        "n_splits", "warmup", "holdout", "label",
    }
    parts = [f"{k}{v}" for k, v in sorted(params.items()) if k not in skip]
    return "-".join(parts) if parts else "default"


def _bt_config(params: dict[str, Any], timeframe: str) -> BacktestConfig:
    return BacktestConfig(
        fee_pct=Decimal(str(params.get("fee_pct", 0.001))),
        slippage_pct=Decimal(str(params.get("slippage_pct", 0.0005))),
        timeframe=timeframe,
        vol_target=params.get("vol_target"),
        max_weight=float(params.get("max_weight", 0.95)),
    )


# Default liquid majors for directional trials (keeps multiple-testing honest
# and avoids 189-symbol grids that are mostly dead listings).
_DEFAULT_DIR_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "LTC/USDT", "TRX/USDT", "NEAR/USDT",
]


def eval_directional(store: TimeSeriesStore, hyp: Hypothesis) -> EvalResult:
    p = hyp.params
    tf = str(p.get("timeframe", "1d"))
    want = list(p.get("symbols") or _DEFAULT_DIR_SYMBOLS)
    # Keep only symbols that exist for this timeframe; fall back to top liquid.
    available = set(store.symbols(tf))
    symbols = [s for s in want if s in available]
    if len(symbols) < 3:
        # longest histories as fallback
        all_syms = store.symbols(tf)
        scored = []
        for s in all_syms:
            rows = store.fetch_candles_range(s, tf)
            if rows:
                scored.append((s, len(rows)))
        scored.sort(key=lambda x: -x[1])
        symbols = [s for s, _ in scored[:12]]
    data = _load_ohlcv(store, tf, symbols)
    if not data:
        return EvalResult(
            TrialMetrics(dsr=0.0, oos_return=0.0, n_obs=0, beats_benchmark=False),
            {"error": f"no data for {tf}"},
        )

    holdout_frac = float(p.get("holdout", 0.20))
    n_splits = int(p.get("n_splits", 6))
    warmup = int(p.get("warmup", 60))
    cfg = _bt_config(p, tf)
    factory = _strategy_factory(p)

    # Walk-forward on the non-holdout slice; deflate across symbols (external trials).
    records = []
    for symbol, df in data.items():
        wf, hold = holdout_split(df, holdout_frac, warmup)
        if len(wf) < warmup + n_splits * 10:
            continue
        cr = validate_config(
            wf, factory, symbol,
            n_splits=n_splits, warmup=warmup, timeframe=tf, config=cfg,
        )
        if cr is not None:
            records.append((symbol, cr, hold))

    if not records:
        return EvalResult(
            TrialMetrics(dsr=0.0, oos_return=0.0, n_obs=0, beats_benchmark=False),
            {"error": "no valid walk-forward records"},
        )

    # Deflate best symbol by cross-symbol variance (multiple testing across universe).
    from rapana.backtest.validation import deflated_best, hodl_oos_return

    config_results = [r[1] for r in records]
    best, dsr = deflated_best(config_results)
    assert best is not None
    best_sym, best_cr, best_hold = next(r for r in records if r[1] is best)
    # HODL over the same walk-forward window used for ranking (not the locked holdout).
    hodl = hodl_oos_return(
        holdout_split(data[best_sym], holdout_frac, warmup)[0], n_splits, warmup
    )

    # Locked holdout: single confirmation run (not used for ranking).
    holdout_return = None
    holdout_dsr = None
    if len(best_hold) >= warmup + 20:
        hold_cr = validate_config(
            best_hold, factory, best_sym,
            n_splits=max(2, min(3, n_splits // 2)),
            warmup=warmup, timeframe=tf, config=cfg,
        )
        if hold_cr is not None:
            holdout_return = hold_cr.oos_return
            # Solo DSR on holdout (n_trials=1) — confirmation, not discovery.
            holdout_dsr = deflated_sharpe_ratio(
                hold_cr.oos_sharpe_bar,
                sharpe_variance=1e-12,
                n_trials=1,
                n_obs=hold_cr.n_obs,
                skew=hold_cr.skew,
                kurtosis=hold_cr.kurtosis,
            )

    metrics = TrialMetrics(
        dsr=float(dsr),
        oos_return=float(best_cr.oos_return),
        oos_sharpe_annual=float(best_cr.oos_sharpe_annual),
        n_obs=int(best_cr.n_obs),
        benchmark_return=float(hodl),
        beats_benchmark=best_cr.oos_return > hodl,
        holdout_return=holdout_return,
        holdout_dsr=holdout_dsr,
        extra={
            "best_symbol": best_sym,
            "best_label": best_cr.label,
            "n_symbols_tested": len(records),
            "pct_folds_positive": best_cr.pct_folds_positive,
            "worst_fold_return": best_cr.worst_fold_return,
        },
    )
    return EvalResult(metrics, {
        "family": "directional",
        "best_symbol": best_sym,
        "n_records": len(records),
        "holdout_bars": len(best_hold),
    })


def _liquid_overlap_universe(
    data: dict[str, pd.DataFrame],
    *,
    min_bars: int = 800,
    max_symbols: int = 30,
) -> dict[str, pd.DataFrame]:
    """Pick longest histories that share a non-empty timestamp intersection.

    Greedy: sort by length desc, add symbol only if intersection stays ≥ min_bars.
    Avoids the full-store failure mode where a single short listing empties common ts.
    """
    ranked = sorted(data.items(), key=lambda kv: len(kv[1]), reverse=True)
    selected: dict[str, pd.DataFrame] = {}
    common: set[int] | None = None
    for sym, df in ranked:
        if len(df) < min_bars:
            continue
        ts = {int(t) for t in df["ts"].tolist()}
        trial = ts if common is None else common & ts
        if len(trial) < min_bars:
            continue
        selected[sym] = df
        common = trial
        if len(selected) >= max_symbols:
            break
    return selected


def eval_cross_sectional(store: TimeSeriesStore, hyp: Hypothesis) -> EvalResult:
    p = hyp.params
    tf = str(p.get("timeframe", "1d"))
    try:
        data = load_store_universe(store, tf)
    except ValueError as exc:
        return EvalResult(
            TrialMetrics(dsr=0.0, oos_return=0.0, n_obs=0, beats_benchmark=False),
            {"error": str(exc)},
        )

    data = _liquid_overlap_universe(
        {s: df for s, df in data.items() if len(df) >= 200},
        min_bars=int(p.get("min_bars", 800)),
        max_symbols=int(p.get("max_symbols", 25)),
    )
    if len(data) < 5:
        return EvalResult(
            TrialMetrics(dsr=0.0, oos_return=0.0, n_obs=0, beats_benchmark=False),
            {"error": f"need ≥5 overlapping symbols, got {len(data)}"},
        )

    holdout_frac = float(p.get("holdout", 0.20))
    n_splits = int(p.get("n_splits", 6))
    warmup = int(p.get("warmup", 120))
    fee = float(p.get("fee_pct", 0.001))
    cfg = BacktestConfig(
        fee_pct=Decimal(str(fee)),
        timeframe=tf,
        max_weight=float(p.get("max_weight", 0.95)),
    )

    # Holdout split on common timeline: use first symbol's length as proxy after align
    # Simple approach: trim last holdout_frac of each series by bar count.
    def trim_holdout(d: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
        n = min(len(df) for df in d.values())
        split = int(n * (1.0 - holdout_frac))
        wf, hold = {}, {}
        for sym, df in d.items():
            df = df.iloc[-n:].reset_index(drop=True)
            wf[sym] = df.iloc[:split].reset_index(drop=True)
            hold[sym] = df.iloc[max(0, split - warmup):].reset_index(drop=True)
        return wf, hold

    wf_data, hold_data = trim_holdout(data)
    signals = tuple(p.get("signals", ["momentum"]))
    lookbacks = tuple(int(x) for x in p.get("lookbacks", [20, 60]))
    top_ks = tuple(int(x) for x in p.get("top_ks", [3, 5]))
    rebalances = tuple(int(x) for x in p.get("rebalances", [5, 20]))

    report = validate_cross_sectional_grid(
        wf_data,
        signals=signals,  # type: ignore[arg-type]
        lookbacks=lookbacks,
        top_ks=top_ks,
        rebalances=rebalances,
        n_splits=n_splits,
        warmup=warmup,
        timeframe=tf,
        config=cfg,
    )

    best = report.best
    if best is None:
        return EvalResult(
            TrialMetrics(dsr=0.0, oos_return=0.0, n_obs=0, beats_benchmark=False),
            {"error": "empty cross-sectional grid"},
        )

    # Parse best label: xs-{signal}-L{lookback}-K{top_k}-R{rebalance}
    holdout_return = None
    holdout_dsr = None
    # strategy field holds the label from _pooled_record
    label = best.strategy
    try:
        # xs-momentum-L20-K3-R5
        sig = label.split("-")[1]
        L = int(label.split("-L")[1].split("-")[0])
        K = int(label.split("-K")[1].split("-")[0])
        R = int(label.split("-R")[1])
        hold_cr, _hold_hodl = validate_cross_sectional_config(
            hold_data,
            signal=sig,  # type: ignore[arg-type]
            lookback=L, top_k=K, rebalance=R,
            n_splits=max(2, min(3, n_splits // 2)),
            warmup=warmup, timeframe=tf, config=cfg,
        )
        if hold_cr is not None:
            holdout_return = hold_cr.oos_return
            holdout_dsr = deflated_sharpe_ratio(
                hold_cr.oos_sharpe_bar, sharpe_variance=1e-12, n_trials=1,
                n_obs=hold_cr.n_obs, skew=hold_cr.skew, kurtosis=hold_cr.kurtosis,
            )
    except (IndexError, ValueError, TypeError):
        pass

    metrics = TrialMetrics(
        dsr=float(report.deflated_sharpe),
        oos_return=float(best.oos_return),
        oos_sharpe_annual=float(best.oos_sharpe_annual),
        n_obs=int(best.n_obs),
        benchmark_return=float(report.hodl_return),
        beats_benchmark=best.oos_return > report.hodl_return,
        holdout_return=holdout_return,
        holdout_dsr=holdout_dsr,
        extra={
            "best_label": best.label,
            "n_trials": report.n_trials,
            "passed_grid": report.passed,
        },
    )
    return EvalResult(metrics, {
        "family": "cross_sectional",
        "n_symbols": len(wf_data),
        "n_grid_trials": report.n_trials,
        "best": best.label,
    })


def _daily_triggers() -> list:
    """Daily-scaled event triggers (pre-registered for the 1d surface)."""
    return [
        GapFade(0.05, 3),
        GapFade(0.08, 5),
        GapMomentum(0.05, 3),
        GapMomentum(0.08, 5),
        VolumeSpikeMomentum(2.5, 20, 5),
        BreakoutLong(20, 10),
        BreakoutLong(60, 20),
        BreakoutFade(20, 5),
        BreakoutFade(60, 10),
        RsiExtreme(14, 30, 70, 5),
        RsiExtreme(14, 25, 75, 8),
        RsiExtreme(7, 25, 75, 5),
    ]


def eval_event_trigger(store: TimeSeriesStore, hyp: Hypothesis) -> EvalResult:
    p = hyp.params
    tf = str(p.get("timeframe", "1d"))
    available = set(store.symbols(tf))
    symbols = [s for s in _DEFAULT_DIR_SYMBOLS if s in available]
    if len(symbols) < 3:
        symbols = None  # load all (then we may truncate below)
    data = _load_ohlcv(store, tf, symbols)
    if len(data) > 20:
        # Keep longest 20 for speed
        data = dict(sorted(data.items(), key=lambda kv: -len(kv[1]))[:20])
    if not data:
        return EvalResult(
            TrialMetrics(dsr=0.0, oos_return=0.0, n_obs=0, beats_benchmark=False),
            {"error": f"no data for {tf}"},
        )

    holdout_frac = float(p.get("holdout", 0.20))
    n_splits = int(p.get("n_splits", 5))
    warmup = int(p.get("warmup", 30))
    fee = float(p.get("fee_per_side", 0.0005))
    slip = float(p.get("slippage_per_side", 0.0005))
    min_events = int(p.get("min_events", 8))
    mode = str(p.get("mode", "pooled"))
    pass_eligible = bool(p.get("pass_eligible", True))
    triggers = _daily_triggers() if p.get("scale") == "daily" else _daily_triggers()

    # Holdout trim
    n = min(len(df) for df in data.values())
    split = int(n * (1.0 - holdout_frac))
    wf, hold = {}, {}
    for sym, df in data.items():
        df = df.iloc[-n:].reset_index(drop=True)
        wf[sym] = df.iloc[:split].reset_index(drop=True)
        hold[sym] = df.iloc[max(0, split - warmup):].reset_index(drop=True)

    if mode == "pooled":
        report = run_pooled_hunt(
            wf, triggers,
            timeframe=tf, n_splits=n_splits, warmup=warmup,
            fee_per_side=fee, slippage_per_side=slip,
            min_oos=min_events, dsr_threshold=0.95,
        )
    else:
        report = run_hunt(
            wf, triggers,
            timeframe=tf, n_splits=n_splits, warmup=warmup,
            fee_per_side=fee, slippage_per_side=slip,
            min_oos=min_events, dsr_threshold=0.95,
        )
        # per-symbol is exploratory
        pass_eligible = False

    best = report.best
    if best is None:
        return EvalResult(
            TrialMetrics(dsr=0.0, oos_return=0.0, n_obs=0, beats_benchmark=False),
            {"error": "no trigger verdicts"},
        )

    holdout_return = None
    holdout_dsr = None
    # Confirm best trigger on holdout (pooled across symbols if possible)
    try:
        best_trig = next(t for t in triggers if t.name == best.trigger)
        hold_v = study_trigger_pooled(
            hold, best_trig,
            n_splits=max(2, min(3, n_splits // 2)),
            warmup=warmup,
            fee_per_side=fee, slippage_per_side=slip,
            bars_per_year=365.0 if tf == "1d" else 24 * 365,
        )
        if hold_v is not None and hold_v.n_oos >= 3:
            holdout_return = hold_v.oos_return
            holdout_dsr = deflated_sharpe_ratio(
                hold_v.excess_sharpe_bar, sharpe_variance=1e-12, n_trials=1,
                n_obs=hold_v.n_oos, skew=hold_v.skew, kurtosis=hold_v.kurtosis,
            )
    except StopIteration:
        pass

    # Event study: benchmark is cash (flat); skill requires excess > 0
    beats = best.excess > 0.0 and best.oos_return > 0.0
    dsr = float(best.deflated_skill_sharpe)
    if not pass_eligible:
        # Exploratory: never claim edge even if numbers look good
        dsr = min(dsr, 0.94)

    metrics = TrialMetrics(
        dsr=dsr,
        oos_return=float(best.oos_return),
        oos_sharpe_annual=float(best.sharpe_annual),
        n_obs=int(best.n_oos),
        benchmark_return=float(best.drift),
        beats_benchmark=beats,
        holdout_return=holdout_return,
        holdout_dsr=holdout_dsr,
        extra={
            "best_trigger": best.trigger,
            "best_symbol": best.symbol,
            "n_trials": report.n_trials,
            "excess": best.excess,
            "pass_eligible": pass_eligible,
            "survivors": [v.trigger for v in report.survivors],
        },
    )
    return EvalResult(metrics, {
        "family": "event_trigger",
        "mode": mode,
        "best": best.label,
        "n_trials": report.n_trials,
    })


def eval_structural(store: TimeSeriesStore, hyp: Hypothesis) -> EvalResult:
    """Structural cost layer — NOT prediction alpha.

    Re-measures maker-vs-taker fee drag on a simple always-in trend proxy by
    comparing fee assumptions. A positive "edge" here is fee savings only.
    """
    p = hyp.params
    tf = str(p.get("timeframe", "1h"))
    symbols = list(p.get("symbols") or ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    data = _load_ohlcv(store, tf, symbols)
    if not data:
        return EvalResult(
            TrialMetrics(dsr=0.0, oos_return=0.0, n_obs=0, beats_benchmark=False),
            {"error": "no structural data"},
        )

    factory = _strategy_factory({"strategy": "trend", "fast": 20, "slow": 50})
    taker_cfg = BacktestConfig(
        fee_pct=Decimal("0.001"), slippage_pct=Decimal("0.0005"), timeframe=tf,
    )
    maker_cfg = BacktestConfig(
        fee_pct=Decimal("0.0005"), slippage_pct=Decimal("0.0002"), timeframe=tf,
    )

    savings = []
    details = []
    for sym, df in data.items():
        if len(df) < 200:
            continue
        tr = validate_config(df, factory, sym, n_splits=4, warmup=60, timeframe=tf, config=taker_cfg)
        mk = validate_config(df, factory, sym, n_splits=4, warmup=60, timeframe=tf, config=maker_cfg)
        if tr is None or mk is None:
            continue
        delta = mk.oos_return - tr.oos_return
        savings.append(delta)
        details.append({
            "symbol": sym,
            "taker_oos": tr.oos_return,
            "maker_oos": mk.oos_return,
            "delta": delta,
        })

    if not savings:
        return EvalResult(
            TrialMetrics(dsr=0.0, oos_return=0.0, n_obs=0, beats_benchmark=False),
            {"error": "no structural comparisons"},
        )

    mean_save = float(sum(savings) / len(savings))
    # Structural GO only if maker improves return on every symbol (fee floor).
    all_positive = all(s > 0 for s in savings)
    # Intentionally NOT an alpha claim: dsr forced below threshold for edge_found
    # unless we reclassify as structural_cost_edge in the loop.
    metrics = TrialMetrics(
        dsr=0.0,  # never prediction-alpha
        oos_return=mean_save,
        n_obs=len(savings),
        benchmark_return=0.0,
        beats_benchmark=all_positive and mean_save > 0,
        holdout_return=mean_save if all_positive else None,
        holdout_dsr=None,
        extra={
            "kind": "structural_cost",
            "mean_fee_savings_return": mean_save,
            "all_symbols_improved": all_positive,
            "details": details,
            "is_alpha": False,
        },
    )
    return EvalResult(metrics, {"family": "structural", "details": details})


def evaluate(store: TimeSeriesStore, hyp: Hypothesis) -> EvalResult:
    if hyp.family == "directional":
        return eval_directional(store, hyp)
    if hyp.family == "cross_sectional":
        return eval_cross_sectional(store, hyp)
    if hyp.family == "event_trigger":
        return eval_event_trigger(store, hyp)
    if hyp.family == "structural":
        return eval_structural(store, hyp)
    return EvalResult(
        TrialMetrics(dsr=0.0, oos_return=0.0, n_obs=0, beats_benchmark=False),
        {"error": f"unknown family {hyp.family}"},
    )

"""Cross-sectional relative-strength rotation backtest.

This is the price-edge test that single-symbol strategies cannot express:
rank the stored universe point-in-time, hold the top-k equal-weight, and compare
the walk-forward OOS result against equal-weight buy-and-hold of the same full
universe.

Anti-lookahead: the target holdings for bar ``i`` are ranked from data ending at
bar ``i - 1``. The execution bar's close is never part of the signal.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from rapana.backtest.engine import BARS_PER_YEAR, BacktestConfig
from rapana.backtest.validation import (
    ConfigResult,
    FoldResult,
    ValidationReport,
    _pooled_record,
    deflated_best,
    make_test_folds,
)
from rapana.data.store import TimeSeriesStore
from rapana.logging import get_logger
from rapana.mexc.client import to_perp_symbol

log = get_logger(__name__)

CrossSectionalSignal = Literal["momentum", "reversion", "funding_rank"]


@dataclass(frozen=True)
class CrossSectionalSpec:
    signal: CrossSectionalSignal
    lookback: int
    top_k: int
    rebalance: int

    @property
    def label(self) -> str:
        return f"xs-{self.signal}-L{self.lookback}-K{self.top_k}-R{self.rebalance}"


@dataclass(frozen=True)
class CrossSectionalSimulation:
    returns: pd.Series
    holdings: dict[int, tuple[str, ...]]
    turnovers: dict[int, float]


def load_store_universe(
    store: TimeSeriesStore,
    timeframe: str,
    *,
    since: int | None = None,
    until: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Load every stored symbol for ``timeframe`` as ascending OHLCV frames.

    The universe is exactly ``TimeSeriesStore.symbols(timeframe)``. Empty/missing
    histories fail loudly because the cross-sectional rank depends on a complete
    comparable universe.
    """
    symbols = store.symbols(timeframe)
    if not symbols:
        raise ValueError(f"no stored symbols for timeframe {timeframe!r}")
    out: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        rows = store.fetch_candles_range(sym, timeframe, since=since, until=until)
        if not rows:
            raise ValueError(f"missing stored candles for {sym} {timeframe}")
        out[sym] = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    return out


def load_store_funding(
    store: TimeSeriesStore,
    symbols: list[str],
    *,
    since: int | None = None,
    until: int | None = None,
) -> dict[str, list[dict[str, float]]]:
    """Load funding rows for every spot symbol, keyed by spot symbol."""
    out: dict[str, list[dict[str, float]]] = {}
    missing: list[str] = []
    for sym in symbols:
        rows = store.fetch_funding_range(to_perp_symbol(sym), since=since, until=until)
        if not rows:
            missing.append(sym)
        else:
            out[sym] = rows
    if missing:
        raise ValueError(f"missing funding history for: {', '.join(missing)}")
    return out


def _clean_data(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    if len(data) < 2:
        raise ValueError("cross-sectional validation needs at least two symbols")
    required = {"ts", "open", "high", "low", "close", "volume"}
    cleaned: dict[str, pd.DataFrame] = {}
    for sym, df in data.items():
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"{sym} missing columns: {', '.join(sorted(missing))}")
        if df.empty:
            raise ValueError(f"{sym} has no candles")
        sl = df.sort_values("ts").reset_index(drop=True).copy()
        if sl["ts"].duplicated().any():
            raise ValueError(f"{sym} has duplicate candle timestamps")
        if (sl["close"] <= 0).any():
            raise ValueError(f"{sym} has non-positive closes")
        cleaned[sym.upper()] = sl
    return cleaned


def _common_timestamps(data: dict[str, pd.DataFrame]) -> list[int]:
    first_sym = next(iter(data))
    return [int(t) for t in data[first_sym]["ts"].tolist()]


def _align_common(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    common: set[int] | None = None
    for sym, df in data.items():
        ts = {int(t) for t in df["ts"].tolist()}
        common = ts if common is None else common & ts
        if not common:
            raise ValueError(f"no common candle timestamps across the universe after adding {sym}")
    shared = sorted(common or [])
    if len(shared) < 3:
        raise ValueError("need at least 3 common candle timestamps across the universe")
    aligned: dict[str, pd.DataFrame] = {}
    for sym, df in data.items():
        aligned[sym] = (
            df[df["ts"].isin(shared)]
            .sort_values("ts")
            .reset_index(drop=True)
        )
    return aligned


def _rank_price_signal(
    closes: pd.DataFrame, i: int, lookback: int, signal: CrossSectionalSignal
) -> list[str]:
    prior = i - 1
    anchor = prior - lookback
    if anchor < 0:
        return []
    trailing = closes.iloc[prior] / closes.iloc[anchor] - 1.0
    scores = -trailing if signal == "reversion" else trailing
    valid = [(sym, float(score)) for sym, score in scores.items() if math.isfinite(float(score))]
    valid.sort(key=lambda x: (-x[1], x[0]))
    return [sym for sym, _score in valid]


def _funding_lookup(
    funding_by_symbol: dict[str, list[dict[str, float]]] | None,
    symbols: list[str],
) -> dict[str, list[tuple[int, float]]]:
    if funding_by_symbol is None:
        return {}
    out: dict[str, list[tuple[int, float]]] = {}
    missing: list[str] = []
    for sym in symbols:
        rows = funding_by_symbol.get(sym) or funding_by_symbol.get(sym.upper())
        if not rows:
            missing.append(sym)
            continue
        out[sym] = sorted((int(r["ts"]), float(r["funding_rate"])) for r in rows)
    if missing:
        raise ValueError(f"missing funding history for: {', '.join(missing)}")
    return out


def _latest_funding(rows: list[tuple[int, float]], ts: int) -> float | None:
    latest: float | None = None
    for row_ts, rate in rows:
        if row_ts > ts:
            break
        latest = rate
    return latest


def _rank_funding_signal(
    funding: dict[str, list[tuple[int, float]]], symbols: list[str], prior_ts: int
) -> list[str]:
    ranked: list[tuple[str, float]] = []
    missing: list[str] = []
    for sym in symbols:
        latest = _latest_funding(funding[sym], prior_ts)
        if latest is None:
            missing.append(sym)
        else:
            ranked.append((sym, latest))
    if missing:
        raise ValueError(
            f"no settled funding at or before {prior_ts} for: {', '.join(missing)}"
        )
    ranked.sort(key=lambda x: (x[1], x[0]))  # long lowest latest funding
    return [sym for sym, _rate in ranked]


def _target_weights(
    ranked: list[str], top_k: int, cfg: BacktestConfig
) -> tuple[dict[str, float], tuple[str, ...]]:
    picks = tuple(ranked[:top_k])
    if not picks:
        return {}, picks
    per_name = min(1.0 / len(picks), max(0.0, float(cfg.max_weight)))
    return {sym: per_name for sym in picks}, picks


def simulate_cross_sectional(
    data: dict[str, pd.DataFrame],
    spec: CrossSectionalSpec,
    *,
    config: BacktestConfig | None = None,
    funding_by_symbol: dict[str, list[dict[str, float]]] | None = None,
) -> CrossSectionalSimulation:
    """Simulate one cross-sectional config over already-loaded, real candles.

    Returns timestamped per-bar net returns. Each return at timestamp ``ts[i]``
    is produced by holdings ranked from closes/funding no later than ``ts[i-1]``.
    """
    if spec.lookback < 1:
        raise ValueError("lookback must be >= 1")
    if spec.top_k < 1:
        raise ValueError("top_k must be >= 1")
    if spec.rebalance < 1:
        raise ValueError("rebalance must be >= 1")
    cfg = config or BacktestConfig()
    cleaned = _align_common(_clean_data(data))
    ref_ts = _common_timestamps(cleaned)
    symbols = sorted(cleaned)
    closes = pd.DataFrame({sym: cleaned[sym]["close"].astype(float).to_numpy() for sym in symbols})
    funding = _funding_lookup(funding_by_symbol, symbols)
    if spec.signal == "funding_rank" and not funding:
        raise ValueError("funding_rank requires funding_by_symbol for every symbol")

    weights = {sym: 0.0 for sym in symbols}
    out_returns: list[float] = []
    out_index: list[int] = []
    holdings: dict[int, tuple[str, ...]] = {}
    turnovers: dict[int, float] = {}

    for i in range(1, len(ref_ts)):
        should_rebalance = i >= spec.lookback + 1 and (i - (spec.lookback + 1)) % spec.rebalance == 0
        fee = 0.0
        picks = tuple(sym for sym, weight in weights.items() if weight > 1e-12)
        if should_rebalance:
            if spec.signal == "funding_rank":
                ranked = _rank_funding_signal(funding, symbols, int(ref_ts[i - 1]))
            else:
                ranked = _rank_price_signal(closes, i, spec.lookback, spec.signal)
            target, picks = _target_weights(ranked, min(spec.top_k, len(symbols)), cfg)
            new_weights = {sym: target.get(sym, 0.0) for sym in symbols}
            turnover = sum(abs(new_weights[sym] - weights.get(sym, 0.0)) for sym in symbols)
            fee = turnover * float(cfg.fee_pct)
            turnovers[int(ref_ts[i])] = turnover
            weights = new_weights

        asset_rets = closes.iloc[i] / closes.iloc[i - 1] - 1.0
        gross = sum(weights[sym] * float(asset_rets[sym]) for sym in symbols)
        net = (1.0 - fee) * (1.0 + gross) - 1.0
        out_returns.append(float(net))
        out_index.append(int(ref_ts[i]))
        holdings[int(ref_ts[i])] = picks

        denom = 1.0 + gross
        if denom > 0:
            weights = {sym: weights[sym] * (1.0 + float(asset_rets[sym])) / denom for sym in symbols}

    return CrossSectionalSimulation(
        returns=pd.Series(out_returns, index=out_index, name=spec.label),
        holdings=holdings,
        turnovers=turnovers,
    )


def equal_weight_hodl_oos_return(
    data: dict[str, pd.DataFrame], n_splits: int, warmup: int
) -> float:
    """Equal-weight buy-and-hold of the full universe over the same OOS windows."""
    cleaned = _align_common(_clean_data(data))
    ref_ts = _common_timestamps(cleaned)
    folds = make_test_folds(len(ref_ts), n_splits, warmup)
    if not folds:
        return 0.0
    compounded = 1.0
    symbols = sorted(cleaned)
    for _es, ts, te in folds:
        base = max(ts - 1, 0)
        end = te - 1
        if end <= base:
            continue
        rets: list[float] = []
        for sym in symbols:
            first = float(cleaned[sym]["close"].iloc[base])
            last = float(cleaned[sym]["close"].iloc[end])
            if first <= 0:
                raise ValueError(f"{sym} has non-positive OOS benchmark anchor")
            rets.append(last / first - 1.0)
        compounded *= 1.0 + sum(rets) / len(rets)
    return compounded - 1.0


def validate_cross_sectional_config(
    data: dict[str, pd.DataFrame],
    *,
    signal: CrossSectionalSignal,
    lookback: int,
    top_k: int,
    rebalance: int,
    n_splits: int,
    warmup: int,
    timeframe: str,
    config: BacktestConfig | None = None,
    funding_by_symbol: dict[str, list[dict[str, float]]] | None = None,
) -> tuple[ConfigResult | None, float]:
    """Run one (signal, L, k, R) through the same OOS pooling as validation.py."""
    cfg = config or BacktestConfig(timeframe=timeframe)
    spec = CrossSectionalSpec(signal, lookback, top_k, rebalance)
    cleaned = _align_common(_clean_data(data))
    ref_ts = _common_timestamps(cleaned)
    folds_meta = make_test_folds(len(ref_ts), n_splits, warmup)
    hodl = equal_weight_hodl_oos_return(cleaned, n_splits, warmup)
    if not folds_meta:
        return None, hodl

    fold_results: list[FoldResult] = []
    oos_returns: list[float] = []
    compounded = 1.0
    positive = 0
    bpy = BARS_PER_YEAR.get(timeframe, 24 * 365)

    for k, (es, ts, te) in enumerate(folds_meta):
        fold_data = {sym: df.iloc[es:te].reset_index(drop=True) for sym, df in cleaned.items()}
        sim = simulate_cross_sectional(
            fold_data, spec, config=cfg, funding_by_symbol=funding_by_symbol
        )
        start_ts = int(ref_ts[ts])
        oos = sim.returns[sim.returns.index >= start_ts]
        if len(oos) < 2:
            continue
        oos_returns.extend(float(r) for r in oos)
        fold_ret = float((1.0 + oos).prod() - 1.0)
        compounded *= 1.0 + fold_ret
        positive += fold_ret > 0
        std = float(oos.std(ddof=0)) or 1e-9
        f_sharpe = float(oos.mean()) / std * math.sqrt(bpy)
        eqc = (1.0 + oos).cumprod()
        dd = float(((eqc - eqc.cummax()) / eqc.cummax()).min())
        oos_rebalances = sum(1 for t, v in sim.turnovers.items() if t >= start_ts and v > 1e-12)
        fold_results.append(FoldResult(k, len(oos), fold_ret, f_sharpe, dd, oos_rebalances))

    record = _pooled_record(
        "UNIVERSE", spec.label, fold_results, oos_returns, compounded, positive, bpy
    )
    return record, hodl


def validate_cross_sectional_grid(
    data: dict[str, pd.DataFrame],
    *,
    signals: tuple[CrossSectionalSignal, ...] = ("momentum", "reversion"),
    lookbacks: tuple[int, ...] = (24, 72, 168),
    top_ks: tuple[int, ...] = (1, 3, 5),
    rebalances: tuple[int, ...] = (24,),
    n_splits: int = 6,
    warmup: int = 240,
    timeframe: str = "1h",
    config: BacktestConfig | None = None,
    funding_by_symbol: dict[str, list[dict[str, float]]] | None = None,
) -> ValidationReport:
    """Validate a cross-sectional parameter grid and apply the same honest gate.

    PASS = DSR > 0.95 and best OOS return beats equal-weight buy-and-hold of the
    full universe over the identical OOS windows.
    """
    cfg = config or BacktestConfig(timeframe=timeframe)
    configs: list[ConfigResult] = []
    hodl = equal_weight_hodl_oos_return(data, n_splits, warmup)
    for signal in signals:
        for lookback in lookbacks:
            for top_k in top_ks:
                for rebalance in rebalances:
                    cr, _hodl = validate_cross_sectional_config(
                        data,
                        signal=signal,
                        lookback=lookback,
                        top_k=top_k,
                        rebalance=rebalance,
                        n_splits=n_splits,
                        warmup=warmup,
                        timeframe=timeframe,
                        config=cfg,
                        funding_by_symbol=funding_by_symbol,
                    )
                    if cr is not None:
                        configs.append(cr)

    best, dsr = deflated_best(configs)
    passed = bool(best is not None and dsr > 0.95 and best.oos_return > hodl)
    return ValidationReport(
        timeframe=timeframe,
        n_splits=n_splits,
        warmup=warmup,
        configs=configs,
        n_trials=len(configs),
        best=best,
        deflated_sharpe=dsr,
        is_significant=dsr > 0.95,
        hodl_return=hodl,
        passed=passed,
    )

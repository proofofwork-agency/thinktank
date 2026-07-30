"""Generic fixed-horizon event study + Deflated Sharpe honesty gate.

Reuses ``make_test_folds`` (walk-forward OOS segments) and
``deflated_sharpe_ratio`` (selection-bias correction) so a trigger hunt is held
to the exact same bar as the directional / carry / funding-spike validators.

Point-in-time: a trigger firing at bar ``i`` is traded at ``close[i+1]`` and
exited at ``close[i+1+H]`` — the detection bar's close is never traded, so a
signal can't see its own bar's move. Round-trip fees + slippage are charged per
event. The overlay is FLAT between events, so the honest benchmark is CASH.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from rapana.backtest.engine import BARS_PER_YEAR
from rapana.backtest.metrics import deflated_sharpe_ratio
from rapana.backtest.validation import make_test_folds
from rapana.triggers.base import Trigger

_NAN = float("nan")


@dataclass
class TriggerVerdict:
    symbol: str
    trigger: str
    horizon_bars: int
    n_events: int       # non-overlapping events retained (in-sample + OOS)
    n_oos: int          # OOS events actually scored
    mean_net: float     # mean per-event net return (OOS), after costs
    median_net: float
    sharpe_bar: float   # per-event OOS Sharpe (drives the DSR)
    sharpe_annual: float
    skew: float
    kurtosis: float     # raw (normal = 3)
    win_rate: float
    oos_return: float   # compounded net across OOS events
    worst_event: float
    drift: float = 0.0             # unconditional mean OOS forward return (the "random entry" benchmark)
    excess: float = 0.0            # trigger gross mean MINUS drift (skill, before costs)
    excess_sharpe_bar: float = 0.0 # excess / std — drives the skill-adjusted DSR
    deflated_sharpe: float = 0.0   # net (beats-cash) DSR, assigned by run_hunt
    deflated_skill_sharpe: float = 0.0  # drift-adjusted (beats-random-entry) DSR — the honest gate

    @property
    def label(self) -> str:
        return f"{self.symbol} {self.trigger}"


@dataclass
class HuntReport:
    timeframe: str
    n_splits: int
    warmup: int
    fee_per_side: float
    slippage_per_side: float
    verdicts: list[TriggerVerdict]            # sorted by deflated_sharpe desc
    n_trials: int
    best: TriggerVerdict | None
    deflated_sharpe: float                    # best trigger's DSR
    is_significant: bool                      # best DSR > threshold
    survivors: list[TriggerVerdict] = field(default_factory=list)
    pass_eligible: bool = True                # False for exploratory sweeps

    @property
    def passed(self) -> bool:
        return bool(self.pass_eligible and self.survivors)


def _oos_forward_nets(
    df: pd.DataFrame,
    events: list,
    horizon: int,
    fee_per_side: float,
    slippage_per_side: float,
    n_splits: int,
    warmup: int,
) -> list[float]:
    """Per-event net forward returns for events whose detection bar lands in an
    OOS test window. Entry = close[bar+1], exit = close[bar+1+H], round-trip cost."""
    close = df["close"].to_numpy(dtype=float)
    n = len(close)
    round_trip = 2.0 * (fee_per_side + slippage_per_side)
    folds = make_test_folds(n, n_splits, warmup)
    if not folds:
        return []
    nets: list[float] = []
    for _es, ts_start, te in folds:
        for ev in events:
            if not (ts_start <= ev.bar < te):
                continue
            entry = ev.bar + 1
            exit_ = ev.bar + 1 + horizon
            if exit_ >= n or entry >= n:
                continue
            ce = close[entry]
            if ce <= 0:
                continue
            nets.append(ev.direction * (close[exit_] / ce - 1.0) - round_trip)
    return nets


def _oos_drift(
    df: pd.DataFrame,
    horizon: int,
    n_splits: int,
    warmup: int,
) -> float:
    """Unconditional mean OOS forward return of ANY bar at this horizon — the
    "random entry" benchmark. A trigger only has skill if its forward returns
    beat this; otherwise it is just riding secular drift (e.g. a long-only
    trigger in a bull market). Same OOS folds + entry/exit convention as the
    event study, so the comparison is apples-to-apples."""
    close = df["close"].to_numpy(dtype=float)
    n = len(close)
    folds = make_test_folds(n, n_splits, warmup)
    if not folds:
        return 0.0
    rets: list[float] = []
    for _es, ts_start, te in folds:
        for bar in range(ts_start, te):
            entry = bar + 1
            exit_ = bar + 1 + horizon
            if exit_ >= n or entry >= n:
                continue
            ce = close[entry]
            if ce <= 0:
                continue
            rets.append(close[exit_] / ce - 1.0)
    return float(sum(rets) / len(rets)) if rets else 0.0


def _pooled_oos_drift(
    data_by_symbol: dict[str, pd.DataFrame],
    horizon: int,
    n_splits: int,
    warmup: int,
) -> float:
    """Unconditional mean OOS forward return of ANY bar, pooled across symbols."""
    rets: list[float] = []
    for df in data_by_symbol.values():
        if len(df) < 3:
            continue
        close = df["close"].to_numpy(dtype=float)
        n = len(close)
        for _es, ts_start, te in make_test_folds(n, n_splits, warmup):
            for bar in range(ts_start, te):
                entry = bar + 1
                exit_ = bar + 1 + horizon
                if exit_ >= n or entry >= n:
                    continue
                ce = close[entry]
                if ce <= 0:
                    continue
                rets.append(close[exit_] / ce - 1.0)
    return float(sum(rets) / len(rets)) if rets else 0.0


def solo_skill_dsr(verdict: TriggerVerdict) -> float:
    """Single-hypothesis drift-adjusted DSR: P(true excess Sharpe > 0) for ONE
    pre-registered trigger, with NO multiple-testing penalty.

    Honest only when applied to a hypothesis chosen in advance. The locked
    holdout in `confirm` is the legitimate place to read this; the exploratory
    sweep numbers are NOT single-hypothesis (the sweep itself is N trials)."""
    return deflated_sharpe_ratio(
        verdict.excess_sharpe_bar, sharpe_variance=1e-12, n_trials=1,
        n_obs=verdict.n_oos, skew=verdict.skew, kurtosis=verdict.kurtosis,
    )


def study_trigger(
    df: pd.DataFrame,
    trigger: Trigger,
    symbol: str,
    *,
    n_splits: int,
    warmup: int,
    fee_per_side: float,
    slippage_per_side: float,
    bars_per_year: float,
) -> TriggerVerdict | None:
    """Run one trigger across all OOS folds of ``df``; return its raw stats.

    The DSR is NOT computed here: it depends on the cross-trial Sharpe variance
    and trial count, which only ``run_hunt`` knows. Returns ``None`` if there
    are too few OOS events to score (< 2).
    """
    events = _non_overlapping(trigger.detect(df), trigger.horizon_bars)
    if not events:
        return None
    nets = _oos_forward_nets(
        df, events, trigger.horizon_bars,
        fee_per_side, slippage_per_side, n_splits, warmup,
    )
    if len(nets) < 2:
        return None
    s = pd.Series(nets)
    std = float(s.std(ddof=0)) or 1e-9
    sharpe_bar = float(s.mean()) / std
    skew = float(s.skew()) if len(s) > 2 else 0.0
    kurt = float(s.kurt()) + 3.0 if len(s) > 3 else 3.0  # pandas kurt is excess
    skew = 0.0 if math.isnan(skew) else skew
    kurt = 3.0 if math.isnan(kurt) else kurt
    compounded = 1.0
    for r in nets:
        compounded *= 1.0 + r
    round_trip = 2.0 * (fee_per_side + slippage_per_side)
    drift = _oos_drift(df, trigger.horizon_bars, n_splits, warmup)
    gross_mean = float(s.mean()) + round_trip
    excess = gross_mean - drift
    return TriggerVerdict(
        symbol=symbol, trigger=trigger.name, horizon_bars=trigger.horizon_bars,
        n_events=len(events), n_oos=len(nets),
        mean_net=float(s.mean()), median_net=float(s.median()),
        sharpe_bar=sharpe_bar, sharpe_annual=sharpe_bar * math.sqrt(bars_per_year),
        skew=skew, kurtosis=kurt,
        win_rate=float((s > 0).mean()),
        oos_return=compounded - 1.0,
        worst_event=float(s.min()),
        drift=drift, excess=excess, excess_sharpe_bar=excess / std,
    )


def _finalize_report(
    verdicts: list[TriggerVerdict],
    *,
    timeframe: str,
    n_splits: int,
    warmup: int,
    fee_per_side: float,
    slippage_per_side: float,
    dsr_threshold: float,
    pass_eligible: bool = True,
) -> HuntReport:
    """Deflate each verdict by the cross-trial Sharpe variance + trial count and
    build the shared HuntReport. Used by both the per-symbol and pooled hunts.

    Ranks and gates on the DRIFT-ADJUSTED (skill) DSR, not the net (beats-cash)
    DSR: a long-only trigger in a bull market beats cash by riding secular drift,
    which is not an edge. The skill DSR asks whether the trigger beats RANDOM
    ENTRY — the only question that survives a trending market.
    """
    n_trials = len(verdicts)
    sharpes = [v.sharpe_bar for v in verdicts]
    var = float(pd.Series(sharpes).var(ddof=1)) if len(sharpes) > 1 else 1e-12
    var = var if var > 0 else 1e-12
    excess_sharpes = [v.excess_sharpe_bar for v in verdicts]
    evar = float(pd.Series(excess_sharpes).var(ddof=1)) if len(excess_sharpes) > 1 else 1e-12
    evar = evar if evar > 0 else 1e-12
    for v in verdicts:
        v.deflated_sharpe = deflated_sharpe_ratio(
            v.sharpe_bar, sharpe_variance=var, n_trials=max(n_trials, 1),
            n_obs=v.n_oos, skew=v.skew, kurtosis=v.kurtosis,
        )
        v.deflated_skill_sharpe = deflated_sharpe_ratio(
            v.excess_sharpe_bar, sharpe_variance=evar, n_trials=max(n_trials, 1),
            n_obs=v.n_oos, skew=v.skew, kurtosis=v.kurtosis,
        )
    verdicts.sort(key=lambda v: v.deflated_skill_sharpe, reverse=True)
    best = verdicts[0] if verdicts else None
    survivors = []
    if pass_eligible:
        survivors = [
            v for v in verdicts
            if v.deflated_skill_sharpe > dsr_threshold and v.excess > 0.0
        ]
    return HuntReport(
        timeframe=timeframe, n_splits=n_splits, warmup=warmup,
        fee_per_side=fee_per_side, slippage_per_side=slippage_per_side,
        verdicts=verdicts, n_trials=n_trials, best=best,
        deflated_sharpe=best.deflated_skill_sharpe if best else 0.0,
        is_significant=bool(best is not None and best.deflated_skill_sharpe > dsr_threshold),
        survivors=survivors, pass_eligible=pass_eligible,
    )


def run_hunt(
    data_by_symbol: dict[str, pd.DataFrame],
    triggers: list[Trigger],
    *,
    timeframe: str = "1h",
    n_splits: int = 6,
    warmup: int = 24,
    fee_per_side: float = 0.0002,
    slippage_per_side: float = 0.0002,
    min_oos: int = 8,
    dsr_threshold: float = 0.95,
    bars_per_year: float | None = None,
) -> HuntReport:
    """Per-(symbol, trigger) hunt: deflate every trial across the full grid.

    ``min_oos`` drops triggers that fire too rarely to score — they are NOT
    counted as trials, since a non-test cannot inflate the multiple-testing bar.
    """
    bpy = bars_per_year if bars_per_year is not None else BARS_PER_YEAR.get(timeframe, 24 * 365)
    verdicts: list[TriggerVerdict] = []
    for symbol, df in data_by_symbol.items():
        if len(df) < 3:
            continue
        for trig in triggers:
            v = study_trigger(
                df, trig, symbol, n_splits=n_splits, warmup=warmup,
                fee_per_side=fee_per_side, slippage_per_side=slippage_per_side,
                bars_per_year=bpy,
            )
            if v is not None and v.n_oos >= min_oos:
                verdicts.append(v)
    return _finalize_report(
        verdicts, timeframe=timeframe, n_splits=n_splits, warmup=warmup,
        fee_per_side=fee_per_side, slippage_per_side=slippage_per_side,
        dsr_threshold=dsr_threshold, pass_eligible=False,
    )


def _non_overlapping(events: list, horizon: int) -> list:
    """Greedily drop events whose holding window would overlap a kept event's.

    Two events at bars ``i < j`` hold ``[i+1, i+1+H]`` and ``[j+1, j+1+H]``; they
    overlap unless ``j - i > H``. Enforcing this makes the pooled sample count
    genuinely independent observations rather than double-counted overlapping
    forward returns (which would inflate n_obs and overstate the DSR).
    """
    kept: list = []
    last = -(horizon + 1)
    for ev in sorted(events, key=lambda e: e.bar):
        if ev.bar - last > horizon:
            kept.append(ev)
            last = ev.bar
    return kept


def study_trigger_pooled(
    data_by_symbol: dict[str, pd.DataFrame],
    trigger: Trigger,
    *,
    n_splits: int,
    warmup: int,
    fee_per_side: float,
    slippage_per_side: float,
    bars_per_year: float,
) -> TriggerVerdict | None:
    """Pool one trigger's OOS forward returns across ALL symbols into a single
    verdict. Tests whether an effect is universe-wide, not symbol-specific.

    Events are de-overlapped per symbol first, so ``n_oos`` is an honest count
    of independent samples. This is the right lens when the per-symbol leaderboard
    shows the same trigger mildly positive on several symbols.
    """
    horizon = trigger.horizon_bars
    pooled: list[float] = []
    total_events = 0
    for df in data_by_symbol.values():
        if len(df) < 3:
            continue
        events = _non_overlapping(trigger.detect(df), horizon)
        total_events += len(events)
        pooled.extend(_oos_forward_nets(
            df, events, horizon, fee_per_side, slippage_per_side, n_splits, warmup,
        ))
    if len(pooled) < 2:
        return None
    s = pd.Series(pooled)
    std = float(s.std(ddof=0)) or 1e-9
    sharpe_bar = float(s.mean()) / std
    skew = float(s.skew()) if len(s) > 2 else 0.0
    kurt = float(s.kurt()) + 3.0 if len(s) > 3 else 3.0
    skew = 0.0 if math.isnan(skew) else skew
    kurt = 3.0 if math.isnan(kurt) else kurt
    compounded = 1.0
    for r in pooled:
        compounded *= 1.0 + r
    drift = _pooled_oos_drift(data_by_symbol, horizon, n_splits, warmup)
    round_trip = 2.0 * (fee_per_side + slippage_per_side)
    gross_mean = float(s.mean()) + round_trip
    excess = gross_mean - drift
    return TriggerVerdict(
        symbol="ALL", trigger=trigger.name, horizon_bars=horizon,
        n_events=total_events, n_oos=len(pooled),
        mean_net=float(s.mean()), median_net=float(s.median()),
        sharpe_bar=sharpe_bar, sharpe_annual=sharpe_bar * math.sqrt(bars_per_year),
        skew=skew, kurtosis=kurt,
        win_rate=float((s > 0).mean()),
        oos_return=compounded - 1.0,
        worst_event=float(s.min()),
        drift=drift, excess=excess, excess_sharpe_bar=excess / std,
    )


def run_pooled_hunt(
    data_by_symbol: dict[str, pd.DataFrame],
    triggers: list[Trigger],
    *,
    timeframe: str = "1h",
    n_splits: int = 6,
    warmup: int = 24,
    fee_per_side: float = 0.0002,
    slippage_per_side: float = 0.0002,
    min_oos: int = 8,
    dsr_threshold: float = 0.95,
    bars_per_year: float | None = None,
) -> HuntReport:
    """One trial PER TRIGGER, pooling OOS events across all symbols. Fewer trials
    (so a lower DSR bar) and large n_obs — the highest-power test of whether a
    trigger is a real cross-sectional effect."""
    bpy = bars_per_year if bars_per_year is not None else BARS_PER_YEAR.get(timeframe, 24 * 365)
    verdicts: list[TriggerVerdict] = []
    for trig in triggers:
        v = study_trigger_pooled(
            data_by_symbol, trig, n_splits=n_splits, warmup=warmup,
            fee_per_side=fee_per_side, slippage_per_side=slippage_per_side,
            bars_per_year=bpy,
        )
        if v is not None and v.n_oos >= min_oos:
            verdicts.append(v)
    return _finalize_report(
        verdicts, timeframe=timeframe, n_splits=n_splits, warmup=warmup,
        fee_per_side=fee_per_side, slippage_per_side=slippage_per_side,
        dsr_threshold=dsr_threshold,
    )

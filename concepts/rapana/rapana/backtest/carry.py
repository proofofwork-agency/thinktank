"""Funding-rate / market-neutral carry backtest (C2 — the go/no-go gate).

Directional timing on majors showed no edge out-of-sample. Carry is different:
it is structural income, not a price prediction. A delta-neutral book — **short
perp + long spot** of the same coin — has ~zero price exposure and collects the
perpetual **funding rate** each interval. A short perp *receives* funding when it
is positive (longs pay shorts) and *pays* when it is negative.

This module answers ONE question with the same honest discipline as the
directional harness (walk-forward OOS + Deflated Sharpe), but with the right
benchmark for a market-neutral strategy:

    "Does harvesting funding beat CASH, net of all costs, out-of-sample?"

Net carry per interval (as a fraction of deployed notional, ~1x unlevered) is:

    net = funding_rate(signed)  -  basis drag  -  amortized entry/exit costs

Entry/exit each pay taker fee + slippage on BOTH legs. Basis drag is a per-
interval estimate of the residual P&L from an imperfect perp/spot hedge (the
delta-neutral book cancels price, not basis noise). Leverage, liquidation, and a
*measured* basis are deferred to the risk-rails phase (C3); modelling them as
explicit costs here keeps C2 honest without over-claiming.

Point-in-time: the decision to hold across interval ``t`` uses only funding
settled strictly before ``t``; the rate that settles at ``t`` is then earned if
held — the same firewall as the directional validator.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from rapana.backtest.metrics import deflated_sharpe_ratio
from rapana.backtest.validation import make_test_folds
from rapana.logging import get_logger

log = get_logger(__name__)

_YEAR_MS = 365.0 * 24.0 * 3600.0 * 1000.0
_DEFAULT_INTERVAL_MS = 8 * 3600 * 1000  # MEXC funds every 8h


@dataclass(frozen=True)
class CarryConfig:
    """Cost model for the delta-neutral carry book (all per-leg / per-interval)."""

    fee_pct: float = 0.0002        # taker fee per leg (2 bps)
    slippage_pct: float = 0.0002   # slippage per leg (2 bps)
    basis_drag_bps: float = 0.0    # per-interval residual hedge drag, bps of notional


@dataclass(frozen=True)
class CarryPolicy:
    """An entry rule = one trial. ``threshold`` None means always-on; otherwise
    hold the next interval only when the last settled funding exceeds it."""

    name: str
    threshold: float | None


# Default trial set: always-on plus a few positive funding thresholds. The DSR
# deflates by the number of (symbol x policy) trials, so this is the multiple-
# testing input — keep it small and principled.
DEFAULT_POLICIES: tuple[CarryPolicy, ...] = (
    CarryPolicy("always", None),
    CarryPolicy("fund>0", 0.0),
    CarryPolicy("fund>1bp", 0.0001),
    CarryPolicy("fund>2bp", 0.0002),
)


@dataclass
class CarryFoldResult:
    fold: int
    intervals: int
    net_return: float
    sharpe: float          # annualized (display only)
    max_drawdown: float
    pct_held: float        # fraction of OOS intervals the book was on


@dataclass
class CarryConfigResult:
    symbol: str
    policy: str
    folds: list[CarryFoldResult]
    oos_return: float          # compounded net carry across folds
    oos_sharpe_annual: float   # pooled OOS Sharpe, annualized (display)
    oos_sharpe_bar: float      # pooled per-interval OOS Sharpe (drives the DSR)
    n_obs: int                 # pooled OOS intervals
    skew: float
    kurtosis: float            # raw (normal = 3)
    pct_intervals_positive: float
    gross_funding: float       # OOS funding earned/paid before costs (compounded)
    total_costs: float         # OOS fees + slippage + drag (fraction of notional)

    @property
    def label(self) -> str:
        return f"{self.symbol} {self.policy}"


@dataclass
class CarryReport:
    funding_interval_hours: float
    n_splits: int
    warmup: int
    configs: list[CarryConfigResult]
    n_trials: int
    best: CarryConfigResult | None
    deflated_sharpe: float
    is_significant: bool
    cash_return: float = 0.0   # benchmark = cash / stablecoin yield (default 0)
    passed: bool = False       # significant AND beats cash


def infer_intervals_per_year(ts: list[int]) -> float:
    """Funding intervals per year from the median spacing of settlement times.

    Falls back to an 8h interval (MEXC default) when there are too few points.
    """
    if len(ts) < 2:
        return _YEAR_MS / _DEFAULT_INTERVAL_MS
    diffs = sorted(int(ts[i + 1]) - int(ts[i]) for i in range(len(ts) - 1))
    median = diffs[len(diffs) // 2]
    if median <= 0:
        return _YEAR_MS / _DEFAULT_INTERVAL_MS
    return _YEAR_MS / median


def simulate_carry(
    funding: list[float], *, threshold: float | None, cfg: CarryConfig
) -> list[tuple[float, float, float]]:
    """Per-interval ``(net, gross, cost)`` of the delta-neutral carry book.

    ``gross`` is the signed funding earned that interval (short receives positive
    funding); ``cost`` bundles the entry/exit fees+slippage on both legs and the
    basis drag; ``net = gross - cost``. The position is entered the first interval
    the policy wants it and only re-charged when the policy actually flips — so
    always-on pays one entry and then rides (the carry analog of buy-and-hold).
    """
    per_leg = cfg.fee_pct + cfg.slippage_pct
    transition_cost = 2.0 * per_leg  # both legs, on entry or exit
    drag = cfg.basis_drag_bps / 10_000.0
    out: list[tuple[float, float, float]] = []
    in_pos = False
    prev: float | None = None
    for f in funding:
        desired = True if threshold is None else (prev is not None and prev > threshold)
        gross = 0.0
        cost = 0.0
        if desired and not in_pos:
            cost += transition_cost  # entry: buy spot + short perp
        elif not desired and in_pos:
            cost += transition_cost  # exit: sell spot + cover perp
        if desired:
            gross += f
            cost += drag
        out.append((gross - cost, gross, cost))
        in_pos, prev = desired, f
    return out


def _pooled_carry_record(
    symbol: str,
    policy: str,
    fold_results: list[CarryFoldResult],
    oos_nets: list[float],
    oos_gross: list[float],
    oos_costs: list[float],
    compounded: float,
    positive: int,
    ipy: float,
) -> CarryConfigResult | None:
    """Aggregate per-fold results + pooled per-interval OOS nets into a record."""
    if not fold_results or len(oos_nets) < 2:
        return None
    s = pd.Series(oos_nets)
    std = float(s.std(ddof=0)) or 1e-9
    sharpe_bar = float(s.mean()) / std
    skew = float(s.skew()) if len(s) > 2 else 0.0
    kurt = float(s.kurt()) + 3.0 if len(s) > 3 else 3.0  # pandas kurt is excess
    skew = 0.0 if math.isnan(skew) else skew
    kurt = 3.0 if math.isnan(kurt) else kurt
    gross_compounded = 1.0
    for g in oos_gross:
        gross_compounded *= 1.0 + g
    return CarryConfigResult(
        symbol=symbol,
        policy=policy,
        folds=fold_results,
        oos_return=compounded - 1.0,
        oos_sharpe_annual=sharpe_bar * math.sqrt(ipy),
        oos_sharpe_bar=sharpe_bar,
        n_obs=len(s),
        skew=skew,
        kurtosis=kurt,
        pct_intervals_positive=positive / len(fold_results),
        gross_funding=gross_compounded - 1.0,
        total_costs=sum(oos_costs),
    )


def validate_carry_config(
    funding: list[dict[str, float]],
    symbol: str,
    policy: CarryPolicy,
    *,
    n_splits: int,
    warmup: int,
    cfg: CarryConfig,
    intervals_per_year: float | None = None,
) -> CarryConfigResult | None:
    """Run one (symbol, policy) across all OOS folds; pool the OOS net returns.

    ``funding`` is ascending ``{ts, funding_rate}`` rows. Each fold simulates the
    book over its slice starting flat, but only intervals from the fold's test
    start count toward OOS metrics (the in-sample warmup absorbs the entry cost,
    mirroring the directional validator's boundary handling).
    """
    ts = [int(r["ts"]) for r in funding]
    rates = [float(r["funding_rate"]) for r in funding]
    ipy = intervals_per_year if intervals_per_year is not None else infer_intervals_per_year(ts)
    folds_meta = make_test_folds(len(rates), n_splits, warmup)
    if not folds_meta:
        return None

    fold_results: list[CarryFoldResult] = []
    oos_nets: list[float] = []
    oos_gross: list[float] = []
    oos_costs: list[float] = []
    compounded = 1.0
    positive = 0

    for k, (es, ts_start, te) in enumerate(folds_meta):
        seg = rates[es:te]
        if len(seg) < 3:
            continue
        sim = simulate_carry(seg, threshold=policy.threshold, cfg=cfg)
        offset = ts_start - es  # first OOS interval in slice coordinates
        oos = sim[offset:]
        if len(oos) < 2:
            continue
        nets = [r[0] for r in oos]
        oos_nets.extend(nets)
        oos_gross.extend(r[1] for r in oos)
        oos_costs.extend(r[2] for r in oos)

        # fold-level equity over OOS
        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        for r in nets:
            equity *= 1.0 + r
            peak = max(peak, equity)
            max_dd = min(max_dd, equity / peak - 1.0)
        fold_ret = equity - 1.0
        compounded *= 1.0 + fold_ret
        positive += fold_ret > 0

        rs = pd.Series(nets)
        std = float(rs.std(ddof=0)) or 1e-9
        f_sharpe = float(rs.mean()) / std * math.sqrt(ipy)
        held = sum(1 for r in oos if r[1] != 0.0 or r[2] != 0.0)
        fold_results.append(
            CarryFoldResult(k, len(nets), fold_ret, f_sharpe, max_dd, held / len(nets))
        )

    return _pooled_carry_record(
        symbol, policy.name, fold_results,
        oos_nets, oos_gross, oos_costs, compounded, positive, ipy,
    )


def deflated_carry_best(
    records: list[CarryConfigResult],
) -> tuple[CarryConfigResult | None, float]:
    """Best record by per-interval OOS Sharpe, deflated by the trial count."""
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


def validate_carry_grid(
    funding_by_symbol: dict[str, list[dict[str, float]]],
    *,
    policies: tuple[CarryPolicy, ...] = DEFAULT_POLICIES,
    n_splits: int = 6,
    warmup: int = 8,
    cfg: CarryConfig | None = None,
    cash_return: float = 0.0,
) -> CarryReport:
    """Validate every (symbol, policy) carry trial and deflate the best.

    Benchmark is CASH (``cash_return``, default 0) — the right bar for a market-
    neutral book — NOT buy-and-hold crypto. PASS = DSR > 0.95 AND the best OOS
    net carry beats cash. Same honest go/no-go as the directional harness.
    """
    cfg = cfg or CarryConfig()
    configs: list[CarryConfigResult] = []
    ipy_seen: list[float] = []
    for symbol, funding in funding_by_symbol.items():
        ipy = infer_intervals_per_year([int(r["ts"]) for r in funding])
        ipy_seen.append(ipy)
        for policy in policies:
            cr = validate_carry_config(
                funding, symbol, policy, n_splits=n_splits, warmup=warmup,
                cfg=cfg, intervals_per_year=ipy,
            )
            if cr is not None:
                configs.append(cr)

    n_trials = len(configs)
    best, dsr = deflated_carry_best(configs)
    passed = bool(best is not None and dsr > 0.95 and best.oos_return > cash_return)
    ipy = ipy_seen[0] if ipy_seen else _YEAR_MS / _DEFAULT_INTERVAL_MS

    return CarryReport(
        funding_interval_hours=(_YEAR_MS / ipy) / (3600.0 * 1000.0) if ipy > 0 else 8.0,
        n_splits=n_splits,
        warmup=warmup,
        configs=configs,
        n_trials=n_trials,
        best=best,
        deflated_sharpe=dsr,
        is_significant=dsr > 0.95,
        cash_return=cash_return,
        passed=passed,
    )

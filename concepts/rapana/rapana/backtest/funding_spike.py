"""Funding-spike reversion event study (event-driven track — study #1).

Three price-only TA families and delta-neutral carry all failed the honest gate;
the pivot is to *events*, not price prediction. This is the first event study and
the cheapest honest one: it reuses funding + price already in the store, and the
unlock date... is unnecessary — the "event" is an **extreme funding rate**, which
the store already records.

Hypothesis: an extreme funding rate marks crowded one-sided positioning (longs pay
shorts heavily when funding is very positive, and vice-versa). Crowded positioning
tends to *unwind*, so the contrarian side — **fade the crowd** — should be paid by
a short-horizon price reversion. Two payoffs stack on the faded side:

    * price reversion: short when longs are crowded (funding >> 0), long when shorts
      are crowded (funding << 0);
    * funding earned: the faded side RECEIVES funding by construction (a short
      receives positive funding; a long receives negative funding).

Net per interval (single-leg perp, ~1x unlevered, as a fraction of notional):

    s            = -sign(prev_funding)   if |prev_funding| > threshold else 0
    price_pnl    =  s * (close_t / close_{t-1} - 1)
    funding_pnl  = -s * funding_t                       (>= 0 on the faded side)
    cost         =  per_side * |s_t - s_{t-1}|          (entry / exit / flip)
    net          =  price_pnl + funding_pnl - cost

Point-in-time: the position for the interval ending at ``t`` is decided from the
funding settled at the START of the interval (``prev_funding``, known then); the
price move and the funding that settles at ``t`` are realised after — the same
firewall as the directional validator and the carry book.

Benchmark is CASH (default 0), not buy-and-hold: this is a sign-varying overlay
that is FLAT whenever funding is unremarkable, so the "just held it" wall does not
apply — the honest bar is "does fading funding extremes beat cash, net of costs,
out-of-sample?" The price/funding split is reported separately so a positive
result that is *only* harvested funding (i.e. disguised carry, which already
failed) is visible rather than mistaken for reversion edge.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

import pandas as pd

from rapana.backtest.carry import infer_intervals_per_year
from rapana.backtest.metrics import deflated_sharpe_ratio
from rapana.backtest.validation import make_test_folds
from rapana.logging import get_logger

log = get_logger(__name__)

_YEAR_MS = 365.0 * 24.0 * 3600.0 * 1000.0
_DEFAULT_INTERVAL_MS = 8 * 3600 * 1000  # MEXC funds every 8h


@dataclass(frozen=True)
class FundingSpikeConfig:
    """Cost model for the single-leg directional fade (per *side* = one perp leg)."""

    fee_pct: float = 0.0002        # taker fee per side (2 bps)
    slippage_pct: float = 0.0002   # slippage per side (2 bps)


@dataclass(frozen=True)
class FundingSpikePolicy:
    """An entry rule = one trial. Fade the crowded side whenever the last settled
    funding *magnitude* exceeds ``threshold`` (per-interval, as a fraction).
    ``threshold`` 0.0 means always fade the funding sign."""

    name: str
    threshold: float


# Default trial set: a small, principled ladder of |funding| thresholds. The DSR
# deflates by the number of (symbol x policy) trials, so this is the multiple-
# testing input — keep it small and pre-committed (no post-hoc threshold mining).
DEFAULT_POLICIES: tuple[FundingSpikePolicy, ...] = (
    FundingSpikePolicy("fade|f|>0", 0.0),
    FundingSpikePolicy("fade|f|>5bp", 0.0005),
    FundingSpikePolicy("fade|f|>10bp", 0.0010),
    FundingSpikePolicy("fade|f|>20bp", 0.0020),
)


@dataclass
class FundingSpikeFoldResult:
    fold: int
    intervals: int
    net_return: float
    sharpe: float          # annualized (display only)
    max_drawdown: float
    pct_held: float        # fraction of OOS intervals with a position on


@dataclass
class FundingSpikeConfigResult:
    symbol: str
    policy: str
    folds: list[FundingSpikeFoldResult]
    oos_return: float          # compounded net across folds
    oos_sharpe_annual: float   # pooled OOS Sharpe, annualized (display)
    oos_sharpe_bar: float      # pooled per-interval OOS Sharpe (drives the DSR)
    n_obs: int                 # pooled OOS intervals
    skew: float
    kurtosis: float            # raw (normal = 3)
    pct_intervals_positive: float
    gross_price: float         # OOS price-reversion P&L before costs (compounded)
    gross_funding: float       # OOS funding earned before costs (compounded)
    total_costs: float         # OOS fees + slippage (fraction of notional)
    n_events: int              # OOS intervals the fade was actually on (spike triggers)

    @property
    def label(self) -> str:
        return f"{self.symbol} {self.policy}"


@dataclass
class FundingSpikeReport:
    funding_interval_hours: float
    n_splits: int
    warmup: int
    configs: list[FundingSpikeConfigResult]
    n_trials: int
    best: FundingSpikeConfigResult | None
    deflated_sharpe: float
    is_significant: bool
    cash_return: float = 0.0   # benchmark = cash (default 0); overlay is flat-by-default
    passed: bool = False       # significant AND beats cash


def align_funding_price(
    funding: list[dict[str, float]], candles: list[dict[str, float]]
) -> tuple[list[dict[str, float]], list[float]]:
    """Join each funding settlement to the close price at or before it.

    For each ascending funding row, take the most recent candle close with
    ``candle_ts <= funding_ts`` (point-in-time: never a future price). Funding
    points with no prior candle are dropped. Returns ``(funding_kept, closes)``
    as equal-length lists ready for :func:`validate_funding_spike_config`.
    """
    if not funding or not candles:
        return [], []
    c_ts = [int(c["ts"]) for c in candles]
    c_close = [float(c["close"]) for c in candles]
    kept: list[dict[str, float]] = []
    closes: list[float] = []
    for r in funding:
        t = int(r["ts"])
        i = bisect.bisect_right(c_ts, t) - 1  # last candle with ts <= t
        if i < 0:
            continue
        kept.append(r)
        closes.append(c_close[i])
    return kept, closes


def simulate_funding_spike(
    funding: list[float], close: list[float], *, threshold: float, cfg: FundingSpikeConfig
) -> list[tuple[float, float, float, float]]:
    """Per-interval ``(net, price_pnl, funding_pnl, cost)`` of the contrarian fade.

    One entry per interval (same length as ``funding``). Interval ``i`` ends at the
    funding settlement ``funding[i]``: the position is decided from ``funding[i-1]``
    (the rate settled at the start, known then), captures the price move
    ``close[i]/close[i-1]-1`` scaled by the position sign, and earns the funding
    ``funding[i]`` that settles at the end on the faded side. Costs are charged per
    side on any change in target position (``|s_t - s_{t-1}|`` units of notional, so
    a flip costs two sides). The first interval has no prior funding/price, so it
    is flat — mirroring the carry book's boundary handling.
    """
    per_side = cfg.fee_pct + cfg.slippage_pct
    out: list[tuple[float, float, float, float]] = []
    prev_pos = 0.0
    prev_f: float | None = None
    for i in range(len(funding)):
        s = 0.0
        if prev_f is not None and abs(prev_f) > threshold:
            s = -1.0 if prev_f > 0.0 else 1.0
        r = (close[i] / close[i - 1] - 1.0) if i > 0 and close[i - 1] > 0.0 else 0.0
        price_pnl = s * r
        funding_pnl = -s * funding[i]
        cost = per_side * abs(s - prev_pos)
        out.append((price_pnl + funding_pnl - cost, price_pnl, funding_pnl, cost))
        prev_pos = s
        prev_f = funding[i]
    return out


def _compound(xs: list[float]) -> float:
    c = 1.0
    for x in xs:
        c *= 1.0 + x
    return c - 1.0


def _pooled_spike_record(
    symbol: str,
    policy: str,
    fold_results: list[FundingSpikeFoldResult],
    oos_nets: list[float],
    oos_price: list[float],
    oos_fund: list[float],
    oos_costs: list[float],
    compounded: float,
    positive: int,
    events: int,
    ipy: float,
) -> FundingSpikeConfigResult | None:
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
    return FundingSpikeConfigResult(
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
        gross_price=_compound(oos_price),
        gross_funding=_compound(oos_fund),
        total_costs=sum(oos_costs),
        n_events=events,
    )


def validate_funding_spike_config(
    funding: list[dict[str, float]],
    close: list[float],
    symbol: str,
    policy: FundingSpikePolicy,
    *,
    n_splits: int,
    warmup: int,
    cfg: FundingSpikeConfig,
    intervals_per_year: float | None = None,
) -> FundingSpikeConfigResult | None:
    """Run one (symbol, policy) across all OOS folds; pool the OOS net returns.

    ``funding`` is ascending ``{ts, funding_rate}`` rows and ``close`` the aligned
    closes (same length, from :func:`align_funding_price`). Each fold simulates the
    fade over its slice starting flat; only intervals from the fold's test start
    count toward OOS metrics — the in-sample warmup absorbs the first entry cost,
    mirroring the directional validator and carry book.
    """
    if len(funding) != len(close):
        return None
    ts = [int(r["ts"]) for r in funding]
    rates = [float(r["funding_rate"]) for r in funding]
    ipy = intervals_per_year if intervals_per_year is not None else infer_intervals_per_year(ts)
    folds_meta = make_test_folds(len(rates), n_splits, warmup)
    if not folds_meta:
        return None

    fold_results: list[FundingSpikeFoldResult] = []
    oos_nets: list[float] = []
    oos_price: list[float] = []
    oos_fund: list[float] = []
    oos_costs: list[float] = []
    compounded = 1.0
    positive = 0
    events = 0

    for k, (es, ts_start, te) in enumerate(folds_meta):
        seg_f = rates[es:te]
        seg_px = close[es:te]
        if len(seg_f) < 3:
            continue
        sim = simulate_funding_spike(seg_f, seg_px, threshold=policy.threshold, cfg=cfg)
        offset = ts_start - es  # first OOS interval in slice coordinates
        oos = sim[offset:]
        if len(oos) < 2:
            continue
        nets = [r[0] for r in oos]
        oos_nets.extend(nets)
        oos_price.extend(r[1] for r in oos)
        oos_fund.extend(r[2] for r in oos)
        oos_costs.extend(r[3] for r in oos)
        events += sum(1 for r in oos if r[1] != 0.0 or r[2] != 0.0)

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
            FundingSpikeFoldResult(k, len(nets), fold_ret, f_sharpe, max_dd, held / len(nets))
        )

    return _pooled_spike_record(
        symbol, policy.name, fold_results,
        oos_nets, oos_price, oos_fund, oos_costs, compounded, positive, events, ipy,
    )


def deflated_spike_best(
    records: list[FundingSpikeConfigResult],
) -> tuple[FundingSpikeConfigResult | None, float]:
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


def validate_funding_spike_grid(
    data_by_symbol: dict[str, tuple[list[dict[str, float]], list[float]]],
    *,
    policies: tuple[FundingSpikePolicy, ...] = DEFAULT_POLICIES,
    n_splits: int = 6,
    warmup: int = 8,
    cfg: FundingSpikeConfig | None = None,
    cash_return: float = 0.0,
) -> FundingSpikeReport:
    """Validate every (symbol, policy) fade trial and deflate the best.

    ``data_by_symbol`` maps perp symbol -> ``(funding_rows, aligned_closes)`` from
    :func:`align_funding_price`. Benchmark is CASH (``cash_return``, default 0) —
    the overlay is flat whenever funding is unremarkable, so buy-and-hold is not the
    right bar. PASS = DSR > 0.95 AND the best OOS net beats cash. Same honest
    go/no-go as the directional and carry harnesses.
    """
    cfg = cfg or FundingSpikeConfig()
    configs: list[FundingSpikeConfigResult] = []
    ipy_seen: list[float] = []
    for symbol, (funding, close) in data_by_symbol.items():
        if len(funding) != len(close) or len(funding) < 3:
            continue
        ipy = infer_intervals_per_year([int(r["ts"]) for r in funding])
        ipy_seen.append(ipy)
        for policy in policies:
            cr = validate_funding_spike_config(
                funding, close, symbol, policy, n_splits=n_splits, warmup=warmup,
                cfg=cfg, intervals_per_year=ipy,
            )
            if cr is not None:
                configs.append(cr)

    n_trials = len(configs)
    best, dsr = deflated_spike_best(configs)
    passed = bool(best is not None and dsr > 0.95 and best.oos_return > cash_return)
    ipy = ipy_seen[0] if ipy_seen else _YEAR_MS / _DEFAULT_INTERVAL_MS

    return FundingSpikeReport(
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

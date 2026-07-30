"""Token-unlock cliff event study (event-driven track — study #2).

Price-only TA, delta-neutral carry, cross-sectional rotation and the funding-spike
fade all failed the honest gate. This is the second event study and the first that
trades on genuinely *non-price* information: scheduled token unlocks. A cliff unlock
is a known-in-advance supply shock — DefiLlama publishes the date and size months
ahead — so a strategy reacting to it uses public foreknowledge, never a future
price. That makes it the cleanest possible anti-lookahead setup.

Hypothesis: a large cliff unlock (newly-liquid supply hitting a thin market) exerts
downward price pressure around the unlock date, so *shorting into the unlock* — or
its mirror — earns a short-horizon abnormal return that price-pattern strategies
cannot see.

Per event (single leg, ~1x, as a fraction of notional):

    enter at close(unlock_day + entry_offset), exit `hold` days later
    raw       = px_exit / px_entry - 1
    abnormal  = raw - market_adjust * (btc_exit / btc_entry - 1)
    gross     = direction * abnormal              (direction: +1 long, -1 short)
    cost      = 2*(fee + slippage) + short_carry  (round-trip; carry on shorts only)
    net       = gross - cost

Only events whose unlock size >= ``min_pct`` of max supply qualify; the overlay is
FLAT otherwise, so the benchmark is CASH (default 0), not buy-and-hold — the same
go/no-go bar as the funding-spike study. PASS = DSR > 0.95 AND best OOS net beats
cash, with the trial count = the pre-committed policy grid (the multiple-testing
input the DSR deflates by).

Anti-lookahead: the unlock date and size are scheduled and public before the
window; entry uses the close at or before the entry day; no price after the exit
day enters the trade. Honest caveat surfaced to the caller: unlock events cluster
in calendar time and across correlated alts, so pooled per-event observations are
not fully independent — market-adjustment reduces but does not remove this, so the
DSR's effective ``n_obs`` is mildly optimistic. A robustness pass that caps one
event per day per direction is provided via :func:`dedupe_one_per_day`.

Two further caveats (raised by independent review), both of which would make a
borderline result *weaker*, never stronger, so they do not rescue a FAIL:
  * Survivorship: an event is only admitted if its EXIT close exists, which
    conditions the sample on the token surviving / having usable candles through
    the window. A truly point-in-time universe would book delistings/halts as a
    defined (typically bad-for-longs) outcome instead of dropping them.
  * Winsorization caps realised P&L at ``±winsor``; it is an outcome-cap, not an
    executable stop. For shorts it suppresses tail losses, so a clean tradable
    model would replace it with a precommitted stop/close rule on available prices.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

import pandas as pd

from rapana.backtest.metrics import deflated_sharpe_ratio
from rapana.backtest.validation import make_test_folds
from rapana.logging import get_logger

log = get_logger(__name__)

_DAY_MS = 86_400_000
_YEAR_MS = 365.0 * _DAY_MS


@dataclass(frozen=True)
class UnlockCostConfig:
    """Round-trip cost model for the single-leg unlock trade (charged per *side*)."""

    fee_pct: float = 0.0002              # taker fee per side (2 bps)
    slippage_pct: float = 0.0010         # slippage per side (10 bps; alts are wider than majors)
    short_carry_bps_per_day: float = 0.0  # optional perp-funding drag, charged to SHORTS only


@dataclass(frozen=True)
class UnlockPolicy:
    """One entry rule = one trial. Trade ``direction`` around cliff unlocks that are
    >= ``min_pct`` of max supply, entering ``entry_offset`` days from the unlock day
    and holding ``hold`` days. ``market_adjust`` subtracts the BTC move over the same
    window (a crude market-neutral overlay)."""

    name: str
    direction: int        # +1 long, -1 short
    entry_offset: int     # days relative to the unlock day (e.g. -1 = enter the day before)
    hold: int             # holding days
    min_pct: float        # minimum unlock size as a fraction of max supply
    market_adjust: bool = True


def _default_policies() -> tuple[UnlockPolicy, ...]:
    """A small, pre-committed grid. The DSR deflates by the trial count, so this is
    the multiple-testing input — keep it principled, not mined."""
    pols: list[UnlockPolicy] = []
    for direction, dname in ((-1, "short"), (1, "long")):
        for offset in (-1, -5):
            for hold in (5, 10):
                for mp in (0.005, 0.02, 0.05):
                    pols.append(
                        UnlockPolicy(
                            name=f"{dname}@{offset:+d}/h{hold}/p{mp * 100:g}",
                            direction=direction,
                            entry_offset=offset,
                            hold=hold,
                            min_pct=mp,
                        )
                    )
    return tuple(pols)


DEFAULT_POLICIES = _default_policies()  # 2 dir x 2 offset x 2 hold x 3 threshold = 24 trials


@dataclass
class PriceSeries:
    """Day-indexed closes for one symbol (1d bars). ``days`` are ascending integer day
    numbers (``ts // 86_400_000``); ``closes`` is aligned."""

    days: list[int]
    closes: list[float]

    def on_or_before(self, day: int, tol: int) -> float | None:
        """Close at ``day`` or the most recent prior day within ``tol`` days (point-in-
        time: never a future close). ``None`` if the gap exceeds ``tol`` or no prior bar."""
        i = bisect.bisect_right(self.days, day) - 1
        if i < 0 or day - self.days[i] > tol:
            return None
        c = self.closes[i]
        return c if c > 0 else None

    @property
    def first_day(self) -> int | None:
        return self.days[0] if self.days else None


def price_series_from_candles(candles: list[dict[str, float]]) -> PriceSeries:
    """Build a :class:`PriceSeries` from ascending/unsorted 1d candle rows."""
    days: list[int] = []
    closes: list[float] = []
    for c in sorted(candles, key=lambda r: int(r["ts"])):
        d = int(c["ts"]) // _DAY_MS
        cl = float(c["close"])
        if days and days[-1] == d:
            closes[-1] = cl  # last write wins on a duplicate day
            continue
        days.append(d)
        closes.append(cl)
    return PriceSeries(days, closes)


def dedupe_one_per_day(events: list[dict]) -> list[dict]:
    """Keep at most one event per (symbol, unlock-day): the largest by ``pct_max_supply``.

    A robustness control for double-counting when a protocol logs several cliff
    allocations on the same day."""
    best: dict[tuple[str, int], dict] = {}
    for e in events:
        key = (e["symbol"], int(e["ts"]) // _DAY_MS)
        cur = best.get(key)
        if cur is None or (e.get("pct_max_supply") or 0) > (cur.get("pct_max_supply") or 0):
            best[key] = e
    return list(best.values())


def simulate_unlock_policy(
    events: list[dict],
    prices: dict[str, PriceSeries],
    market: PriceSeries | None,
    policy: UnlockPolicy,
    cost: UnlockCostConfig,
    *,
    tol: int = 3,
    min_history_days: int = 10,
    winsor: float | None = None,
) -> list[tuple[int, float, float, float]]:
    """Per-event ``(entry_ts_ms, net, gross, cost)`` for every qualifying event.

    Qualify = unlock size >= ``policy.min_pct`` AND both entry/exit closes exist within
    ``tol`` days AND the token had >= ``min_history_days`` of prior price history (so we
    trade an established listing, not the first volatile ticks of a new one). Output is
    sorted ascending by entry timestamp — the time axis the walk-forward folds over.
    """
    if policy.market_adjust and market is None:
        raise ValueError("market_adjust policy requires a market PriceSeries")
    per_side = cost.fee_pct + cost.slippage_pct
    carry = (
        cost.short_carry_bps_per_day * 1e-4 * policy.hold if policy.direction < 0 else 0.0
    )
    roundtrip = 2.0 * per_side + carry
    out: list[tuple[int, float, float, float]] = []
    for e in events:
        pct = e.get("pct_max_supply")
        if pct is None or pct < policy.min_pct:
            continue
        ps = prices.get(e["symbol"])
        if ps is None or ps.first_day is None:
            continue
        unlock_day = int(e["ts"]) // _DAY_MS
        entry_day = unlock_day + policy.entry_offset
        exit_day = entry_day + policy.hold
        if entry_day - ps.first_day < min_history_days:
            continue
        px_in = ps.on_or_before(entry_day, tol)
        px_out = ps.on_or_before(exit_day, tol)
        if px_in is None or px_out is None:
            continue
        raw = px_out / px_in - 1.0
        if policy.market_adjust:
            m_in = market.on_or_before(entry_day, tol)  # type: ignore[union-attr]
            m_out = market.on_or_before(exit_day, tol)  # type: ignore[union-attr]
            if m_in is None or m_out is None:
                continue
            abnormal = raw - (m_out / m_in - 1.0)
        else:
            abnormal = raw
        gross = policy.direction * abnormal
        if winsor is not None:
            # Symmetric per-event cap: models stops/liquidity and stops a handful of
            # microcap blow-ups (a +500% move, an unlevered short past -100%) from
            # dominating the pooled mean or compounding equity into nonsense. Applied
            # uniformly to every event — it caps P&L, it does not select events.
            gross = max(-winsor, min(winsor, gross))
        out.append((entry_day * _DAY_MS, gross - roundtrip, gross, roundtrip))
    out.sort(key=lambda r: r[0])
    return out


@dataclass
class UnlockFoldResult:
    fold: int
    events: int
    net_return: float
    sharpe: float          # annualized (display only)
    max_drawdown: float


@dataclass
class UnlockConfigResult:
    policy: str
    folds: list[UnlockFoldResult]
    oos_return: float          # compounded net across folds
    oos_sharpe_annual: float   # pooled OOS per-event Sharpe, annualized (display)
    oos_sharpe_bar: float      # pooled per-event OOS Sharpe (drives the DSR)
    n_obs: int                 # pooled OOS events
    skew: float
    kurtosis: float            # raw (normal = 3)
    pct_folds_positive: float
    gross_return: float        # OOS pre-cost net (compounded)
    total_costs: float         # OOS round-trip costs paid (sum, fraction of notional)
    win_rate: float            # fraction of OOS events with net > 0
    n_events: int
    mean_net: float = 0.0      # mean per-event net return — the robust headline
    median_net: float = 0.0    # median per-event net return (outlier-proof)

    @property
    def label(self) -> str:
        return self.policy


@dataclass
class UnlockReport:
    n_splits: int
    warmup: int
    configs: list[UnlockConfigResult]
    n_trials: int
    best: UnlockConfigResult | None
    deflated_sharpe: float
    is_significant: bool
    events_per_year: float
    cash_return: float = 0.0   # benchmark = cash (default 0); overlay is flat-by-default
    passed: bool = False       # significant AND beats cash


def _compound(xs: list[float]) -> float:
    c = 1.0
    for x in xs:
        c *= 1.0 + x
    return c - 1.0


def _events_per_year(sim: list[tuple[int, float, float, float]]) -> float:
    """Annualization factor for display: events / span-in-years. 1.0 if undefined."""
    if len(sim) < 2:
        return 1.0
    span = (sim[-1][0] - sim[0][0]) / _YEAR_MS
    return (len(sim) / span) if span > 0 else 1.0


def validate_unlock_policy(
    events: list[dict],
    prices: dict[str, PriceSeries],
    market: PriceSeries | None,
    policy: UnlockPolicy,
    *,
    n_splits: int,
    warmup: int,
    cost: UnlockCostConfig,
    winsor: float | None = None,
    min_events: int = 0,
) -> UnlockConfigResult | None:
    """Run one policy across all OOS folds of its pooled event stream.

    The events of every symbol are pooled, sorted by entry time, and split into
    contiguous walk-forward folds; the first ``warmup`` events are in-sample and only
    events from each fold's test start count toward OOS metrics. No per-fold fitting
    happens (the rule is fixed), so the event returns are computed once and sliced.
    Configs with fewer than ``min_events`` pooled OOS events are rejected (``None``) so
    a high threshold that leaves a handful of lucky events cannot pose as an edge.
    """
    sim = simulate_unlock_policy(events, prices, market, policy, cost, winsor=winsor)
    folds_meta = make_test_folds(len(sim), n_splits, warmup)
    if not folds_meta:
        return None
    epy = _events_per_year(sim)

    fold_results: list[UnlockFoldResult] = []
    oos_nets: list[float] = []
    oos_gross: list[float] = []
    oos_costs: list[float] = []
    compounded = 1.0
    positive = 0
    wins = 0

    for k, (_es, ts_start, te) in enumerate(folds_meta):
        seg = sim[ts_start:te]
        if len(seg) < 2:
            continue
        seg_nets = [r[1] for r in seg]
        oos_nets.extend(seg_nets)
        oos_gross.extend(r[2] for r in seg)
        oos_costs.extend(r[3] for r in seg)
        wins += sum(1 for x in seg_nets if x > 0)

        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        for x in seg_nets:
            equity *= 1.0 + x
            peak = max(peak, equity)
            max_dd = min(max_dd, equity / peak - 1.0)
        fold_ret = equity - 1.0
        compounded *= 1.0 + fold_ret
        positive += fold_ret > 0

        rs = pd.Series(seg_nets)
        std = float(rs.std(ddof=0)) or 1e-9
        f_sharpe = float(rs.mean()) / std * math.sqrt(epy)
        fold_results.append(UnlockFoldResult(k, len(seg_nets), fold_ret, f_sharpe, max_dd))

    if not fold_results or len(oos_nets) < max(2, min_events):
        return None

    s = pd.Series(oos_nets)
    std = float(s.std(ddof=0)) or 1e-9
    sharpe_bar = float(s.mean()) / std
    skew = float(s.skew()) if len(s) > 2 else 0.0
    kurt = float(s.kurt()) + 3.0 if len(s) > 3 else 3.0  # pandas kurt is excess
    skew = 0.0 if math.isnan(skew) else skew
    kurt = 3.0 if math.isnan(kurt) else kurt

    return UnlockConfigResult(
        policy=policy.name,
        folds=fold_results,
        oos_return=compounded - 1.0,
        oos_sharpe_annual=sharpe_bar * math.sqrt(epy),
        oos_sharpe_bar=sharpe_bar,
        n_obs=len(s),
        skew=skew,
        kurtosis=kurt,
        pct_folds_positive=positive / len(fold_results),
        gross_return=_compound(oos_gross),
        total_costs=sum(oos_costs),
        win_rate=wins / len(oos_nets),
        n_events=len(oos_nets),
        mean_net=float(s.mean()),
        median_net=float(s.median()),
    )


def deflated_unlock_best(
    records: list[UnlockConfigResult],
) -> tuple[UnlockConfigResult | None, float]:
    """Best record by per-event OOS Sharpe, deflated by the trial count."""
    if not records:
        return None, 0.0
    best = max(records, key=lambda c: c.oos_sharpe_bar)
    bars = [c.oos_sharpe_bar for c in records]
    var = float(pd.Series(bars).var(ddof=1)) if len(bars) > 1 else 1e-12
    var = var if var > 0 else 1e-12
    dsr = deflated_sharpe_ratio(
        best.oos_sharpe_bar,
        sharpe_variance=var,
        n_trials=max(len(records), 1),
        n_obs=best.n_obs,
        skew=best.skew,
        kurtosis=best.kurtosis,
    )
    return best, dsr


def validate_unlock_grid(
    events: list[dict],
    prices: dict[str, PriceSeries],
    market: PriceSeries | None,
    *,
    policies: tuple[UnlockPolicy, ...] = DEFAULT_POLICIES,
    n_splits: int = 5,
    warmup: int = 30,
    cost: UnlockCostConfig | None = None,
    cash_return: float = 0.0,
    winsor: float | None = None,
    min_events: int = 0,
) -> UnlockReport:
    """Validate every unlock policy and deflate the best by the trial count.

    ``events`` is a flat list of cliff unlocks: ``{symbol, ts, pct_max_supply}`` where
    ``symbol`` keys into ``prices``. ``market`` is the BTC (or chosen factor) series for
    market-adjustment. Benchmark is CASH — the overlay is flat away from unlocks, so
    buy-and-hold is not the right bar. PASS = DSR > 0.95 AND best OOS net beats cash.
    """
    cost = cost or UnlockCostConfig()
    configs: list[UnlockConfigResult] = []
    for policy in policies:
        cr = validate_unlock_policy(
            events, prices, market, policy,
            n_splits=n_splits, warmup=warmup, cost=cost,
            winsor=winsor, min_events=min_events,
        )
        if cr is not None:
            configs.append(cr)

    # Global annualization factor for the report header (display only).
    all_ts = sorted(int(e["ts"]) for e in events) if events else []
    span = (all_ts[-1] - all_ts[0]) / _YEAR_MS if len(all_ts) > 1 else 0.0
    epy = (len(all_ts) / span) if span > 0 else 1.0

    best, dsr = deflated_unlock_best(configs)
    # Beats-cash uses the MEAN per-event net (robust); the compounded oos_return is
    # an unrealistic sequential-full-size-bet artifact and explodes with event count.
    passed = bool(best is not None and dsr > 0.95 and best.mean_net > cash_return)
    return UnlockReport(
        n_splits=n_splits,
        warmup=warmup,
        configs=configs,
        n_trials=len(configs),
        best=best,
        deflated_sharpe=dsr,
        is_significant=dsr > 0.95,
        events_per_year=epy,
        cash_return=cash_return,
        passed=passed,
    )

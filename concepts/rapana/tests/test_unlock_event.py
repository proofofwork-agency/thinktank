"""Tests for the token-unlock cliff event study (anti-lookahead + mechanics)."""
from __future__ import annotations

from rapana.backtest.unlock_event import (
    DEFAULT_POLICIES,
    UnlockCostConfig,
    UnlockPolicy,
    dedupe_one_per_day,
    price_series_from_candles,
    simulate_unlock_policy,
    validate_unlock_grid,
    validate_unlock_policy,
)

_DAY = 86_400_000


def _candles(start_day: int, closes: list[float]) -> list[dict]:
    return [{"ts": (start_day + i) * _DAY, "close": c} for i, c in enumerate(closes)]


def _flat_market(start_day: int, n: int, level: float = 100.0):
    return price_series_from_candles(_candles(start_day, [level] * n))


def test_price_series_lookup_is_point_in_time():
    ps = price_series_from_candles(_candles(100, [10.0, 11.0, 12.0, 13.0]))
    assert ps.first_day == 100
    assert ps.on_or_before(102, tol=3) == 12.0       # exact day
    assert ps.on_or_before(105, tol=3) == 13.0       # most recent prior within tol
    assert ps.on_or_before(110, tol=3) is None       # gap beyond tol
    assert ps.on_or_before(99, tol=3) is None         # before the first bar


def test_short_into_a_drop_is_profitable():
    # Token: flat 100 through entry day, then declines to 80 by the exit day.
    closes = [100.0] * 50 + [96.0, 92.0, 88.0, 84.0, 80.0] + [80.0] * 6
    prices = {"X/USDT": price_series_from_candles(_candles(150, closes))}
    market = _flat_market(150, len(closes))  # market flat → no adjustment effect
    # unlock at day 200 → entry day 199 (close 100), exit day 204 (close 80)
    events = [{"symbol": "X/USDT", "ts": 200 * _DAY, "pct_max_supply": 0.10}]
    pol = UnlockPolicy("short", direction=-1, entry_offset=-1, hold=5, min_pct=0.05)
    cost = UnlockCostConfig()
    sim = simulate_unlock_policy(events, prices, market, pol, cost)
    assert len(sim) == 1
    _ts, net, gross, rt = sim[0]
    assert abs(gross - 0.20) < 1e-9                   # short a -20% move → +20% gross
    assert abs(rt - 2 * (cost.fee_pct + cost.slippage_pct)) < 1e-12
    assert abs(net - (0.20 - rt)) < 1e-9


def test_market_adjustment_removes_the_market_move():
    closes = [100.0] * 50 + [96.0, 92.0, 88.0, 84.0, 80.0] + [80.0] * 6
    prices = {"X/USDT": price_series_from_candles(_candles(150, closes))}
    # market falls the SAME -20% over the window → abnormal return is ~0
    market = price_series_from_candles(_candles(150, closes))
    events = [{"symbol": "X/USDT", "ts": 200 * _DAY, "pct_max_supply": 0.10}]
    pol = UnlockPolicy("short", direction=-1, entry_offset=-1, hold=5, min_pct=0.05)
    sim = simulate_unlock_policy(events, prices, market, pol, UnlockCostConfig())
    assert len(sim) == 1
    assert abs(sim[0][2]) < 1e-9                       # gross abnormal ≈ 0


def test_min_pct_threshold_filters_small_unlocks():
    prices = {"X/USDT": price_series_from_candles(_candles(150, [100.0] * 80))}
    market = _flat_market(150, 80)
    events = [{"symbol": "X/USDT", "ts": 200 * _DAY, "pct_max_supply": 0.01}]
    pol = UnlockPolicy("short", direction=-1, entry_offset=-1, hold=5, min_pct=0.05)
    assert simulate_unlock_policy(events, prices, market, pol, UnlockCostConfig()) == []


def test_no_lookahead_future_prices_are_never_used():
    # Two worlds identical up to and including the exit day, differing only AFTER it.
    base = [100.0] * 50 + [96.0, 92.0, 88.0, 84.0, 80.0]
    world_a = base + [80.0] * 10
    world_b = base + [999.0] * 10  # wildly different future
    events = [{"symbol": "X/USDT", "ts": 200 * _DAY, "pct_max_supply": 0.10}]
    pol = UnlockPolicy("short", direction=-1, entry_offset=-1, hold=5, min_pct=0.05)
    cost = UnlockCostConfig()
    sim_a = simulate_unlock_policy(
        events, {"X/USDT": price_series_from_candles(_candles(150, world_a))},
        _flat_market(150, len(world_a)), pol, cost,
    )
    sim_b = simulate_unlock_policy(
        events, {"X/USDT": price_series_from_candles(_candles(150, world_b))},
        _flat_market(150, len(world_b)), pol, cost,
    )
    assert sim_a == sim_b  # post-exit prices cannot change the trade


def test_history_guard_excludes_freshly_listed_tokens():
    # Token's first bar is day 195; entry day is 199 → only 4 days of history (< 10).
    prices = {"X/USDT": price_series_from_candles(_candles(195, [100.0] * 30))}
    market = _flat_market(195, 30)
    events = [{"symbol": "X/USDT", "ts": 200 * _DAY, "pct_max_supply": 0.10}]
    pol = UnlockPolicy("short", direction=-1, entry_offset=-1, hold=5, min_pct=0.05)
    assert simulate_unlock_policy(events, prices, market, pol, UnlockCostConfig()) == []


def test_dedupe_one_per_day_keeps_largest():
    events = [
        {"symbol": "X/USDT", "ts": 200 * _DAY, "pct_max_supply": 0.02},
        {"symbol": "X/USDT", "ts": 200 * _DAY + 3600_000, "pct_max_supply": 0.07},
        {"symbol": "Y/USDT", "ts": 200 * _DAY, "pct_max_supply": 0.01},
    ]
    out = dedupe_one_per_day(events)
    assert len(out) == 2
    x = next(e for e in out if e["symbol"] == "X/USDT")
    assert x["pct_max_supply"] == 0.07


def test_validate_grid_runs_and_reports_honest_verdict():
    # 60 unlock events on one long, gently-oscillating series → exercises folding,
    # pooling, and the DSR plumbing end to end (structural, not a numeric claim).
    n = 400
    closes = [100.0 * (1.0 + 0.002 * ((i * 7) % 5 - 2)) for i in range(n)]
    prices = {"X/USDT": price_series_from_candles(_candles(100, closes))}
    market = price_series_from_candles(_candles(100, [100.0] * n))
    events = [
        {"symbol": "X/USDT", "ts": (100 + 40 + 5 * k) * _DAY, "pct_max_supply": 0.06}
        for k in range(60)
    ]
    report = validate_unlock_grid(
        events, prices, market, n_splits=3, warmup=10, cash_return=0.0
    )
    assert report.n_trials > 0
    assert report.best is not None
    assert 0.0 <= report.deflated_sharpe <= 1.0
    assert isinstance(report.passed, bool)
    assert report.best.n_obs > 0


def test_validate_grid_fails_below_honest_cash_floor():
    n_events = 250
    n = 100 + 7 * n_events + 20
    closes = [100.0] * n
    events = []
    for k in range(n_events):
        unlock_day = 110 + 7 * k
        events.append({"symbol": "X/USDT", "ts": unlock_day * _DAY, "pct_max_supply": 0.06})
        exit_day = unlock_day - 1 + 5
        drop = 0.02 + (0.002 if k % 2 else -0.002)
        closes[exit_day] = 100.0 * (1.0 - drop)

    prices = {"X/USDT": price_series_from_candles(_candles(100, closes))}
    market = _flat_market(100, n)
    policies = (
        UnlockPolicy("short", direction=-1, entry_offset=-1, hold=5, min_pct=0.05),
        UnlockPolicy("long", direction=1, entry_offset=-1, hold=5, min_pct=0.05),
    )
    report = validate_unlock_grid(
        events,
        prices,
        market,
        policies=policies,
        n_splits=5,
        warmup=10,
        cost=UnlockCostConfig(fee_pct=0.0, slippage_pct=0.0),
        cash_return=0.035,
    )

    assert report.cash_return == 0.035
    assert report.best is not None
    assert 0.0 < report.best.mean_net < report.cash_return
    assert report.is_significant is True
    assert report.passed is False


def test_default_policies_are_a_small_precommitted_grid():
    # The DSR deflates by this count — guard against an accidental explosion of trials.
    assert 0 < len(DEFAULT_POLICIES) <= 32
    assert len({p.name for p in DEFAULT_POLICIES}) == len(DEFAULT_POLICIES)


def test_single_policy_validation_pools_events():
    closes = [100.0 + (i % 3) for i in range(300)]
    prices = {"X/USDT": price_series_from_candles(_candles(100, closes))}
    market = price_series_from_candles(_candles(100, [100.0] * 300))
    events = [
        {"symbol": "X/USDT", "ts": (100 + 30 + 4 * k) * _DAY, "pct_max_supply": 0.06}
        for k in range(50)
    ]
    pol = UnlockPolicy("short", direction=-1, entry_offset=-1, hold=5, min_pct=0.05)
    res = validate_unlock_policy(
        events, prices, market, pol, n_splits=3, warmup=10, cost=UnlockCostConfig()
    )
    assert res is not None
    assert res.n_obs > 0
    assert res.n_events == res.n_obs

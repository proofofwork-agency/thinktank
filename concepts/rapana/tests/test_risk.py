from __future__ import annotations

from decimal import Decimal

from rapana.risk.guardrails import (
    CircuitBreaker,
    KillSwitch,
    OrderRateLimiter,
    PreTradeChecker,
    RiskPolicy,
    TradeProposal,
)

POLICY = RiskPolicy(
    max_position_pct=Decimal("0.10"),
    max_total_exposure_pct=Decimal("0.50"),
    max_daily_loss_pct=Decimal("0.03"),
    max_orders_per_min=6,
    max_notional_per_order=Decimal("250"),
    sanity_price_band=Decimal("0.05"),
)


def _checker(tmp_path, **overrides):
    equity = Decimal("10000")
    return PreTradeChecker(
        policy=POLICY,
        kill_switch=KillSwitch(path=tmp_path / "KS"),
        breaker=CircuitBreaker(POLICY, starting_equity=equity),
        equity=equity,
        **overrides,
    )


def _proposal(side="buy", qty="1", price="100", ref="100"):
    return TradeProposal(
        symbol="BTC/USDT", side=side,
        qty=Decimal(qty), price=Decimal(price), reference_price=Decimal(ref),
    )


def test_clean_trade_approved(tmp_path):
    d = _checker(tmp_path).check(_proposal())
    assert d.approved


def test_notional_cap_denies(tmp_path):
    d = _checker(tmp_path).check(_proposal(qty="3", price="100"))  # 300 > 250
    assert not d.approved
    assert "notional" in d.reason


def test_sanity_band_denies_far_price(tmp_path):
    d = _checker(tmp_path).check(_proposal(price="120", ref="100"))  # 20% off
    assert not d.approved
    assert "deviates" in d.reason


def test_within_band_allows(tmp_path):
    d = _checker(tmp_path).check(_proposal(price="104", ref="100"))  # 4% off
    assert d.approved


def test_total_exposure_cap_denies(tmp_path):
    checker = _checker(tmp_path, current_exposure=Decimal("4900"))  # 49% of 10k
    # 2 units at 100 = 200 notional (< 250 cap, isolates exposure check)
    # 4900 + 200 = 5100 > 5000 (50%) -> denied
    d = checker.check(_proposal(qty="2", price="100"))
    assert not d.approved
    assert "total exposure" in d.reason


def test_per_symbol_cap_denies(tmp_path):
    checker = _checker(tmp_path, symbol_exposure={"BTC/USDT": Decimal("900")})
    # 900 + 200 = 1000 > 1000? equal; push over with 201 notional-ish
    d = checker.check(_proposal(qty="2", price="100"))  # +200 -> 1100 > 1000
    assert not d.approved
    assert "symbol exposure" in d.reason


def test_kill_switch_denies(tmp_path):
    ks_path = tmp_path / "KS"
    ks_path.touch()
    checker = _checker(tmp_path)
    assert checker.kill_switch.path == ks_path
    d = checker.check(_proposal())
    assert not d.approved
    assert "kill_switch" in d.reason


def test_circuit_breaker_trips_on_loss(tmp_path):
    breaker = CircuitBreaker(POLICY, starting_equity=Decimal("10000"))
    breaker.record_realized(Decimal("-400"))  # -4% exceeds 3% limit
    assert breaker.is_tripped()


def test_circuit_breaker_trips_on_open_unrealized_loss():
    breaker = CircuitBreaker(POLICY, starting_equity=Decimal("10000"))
    breaker.record_unrealized(Decimal("-400"))  # -4% exceeds 3% limit
    assert breaker.realized_today == Decimal("0")
    assert breaker.unrealized_today == Decimal("-400")
    assert breaker.is_tripped()


def test_circuit_breaker_unrealized_snapshot_does_not_accumulate():
    breaker = CircuitBreaker(POLICY, starting_equity=Decimal("10000"))
    breaker.record_unrealized(Decimal("-100"))
    breaker.record_unrealized(Decimal("-100"))
    assert breaker.unrealized_today == Decimal("-100")
    assert breaker.is_tripped() is False


def test_circuit_breaker_combines_realized_and_unrealized_loss():
    breaker = CircuitBreaker(POLICY, starting_equity=Decimal("10000"))
    breaker.record_realized(Decimal("-200"))
    assert breaker.is_tripped() is False
    breaker.record_unrealized(Decimal("-150"))
    assert breaker.realized_today == Decimal("-200")
    assert breaker.unrealized_today == Decimal("-150")
    assert breaker.is_tripped()


def test_circuit_breaker_latch_survives_recovering_mark():
    breaker = CircuitBreaker(POLICY, starting_equity=Decimal("10000"))
    breaker.record_unrealized(Decimal("-400"))
    assert breaker.is_tripped()
    breaker.record_unrealized(Decimal("50"))
    assert breaker.unrealized_today == Decimal("50")
    assert breaker.is_tripped()


def test_circuit_breaker_reset_day_clears_unrealized_and_latch():
    breaker = CircuitBreaker(POLICY, starting_equity=Decimal("10000"))
    breaker.record_realized(Decimal("-200"))
    breaker.record_unrealized(Decimal("-150"))
    assert breaker.is_tripped()
    breaker.reset_day()
    assert breaker.realized_today == Decimal("0")
    assert breaker.unrealized_today == Decimal("0")
    assert breaker.is_tripped() is False


def test_circuit_breaker_denies_when_tripped(tmp_path):
    checker = _checker(tmp_path)
    checker.breaker.record_realized(Decimal("-400"))
    d = checker.check(_proposal())
    assert not d.approved
    assert "circuit_breaker" in d.reason


def test_rate_limiter_denies_when_window_is_full(tmp_path):
    limiter = OrderRateLimiter(max_orders=POLICY.max_orders_per_min)
    for _ in range(POLICY.max_orders_per_min):
        limiter.record_submission()

    d = _checker(tmp_path, rate_limiter=limiter).check(_proposal())

    assert not d.approved
    assert "order rate" in d.reason


def test_rate_limiter_allows_when_under_cap(tmp_path):
    limiter = OrderRateLimiter(max_orders=POLICY.max_orders_per_min)
    for _ in range(POLICY.max_orders_per_min - 1):
        limiter.record_submission()

    d = _checker(tmp_path, rate_limiter=limiter).check(_proposal())

    assert d.approved


def test_rate_limiter_prunes_old_submissions():
    limiter = OrderRateLimiter(max_orders=1, window_seconds=60)
    limiter.record_submission(at=0)

    assert limiter.would_exceed(at=0) is True
    assert limiter.would_exceed(at=61) is False


def test_rate_limiter_tracks_cancel_ratio_without_gate():
    limiter = OrderRateLimiter(max_orders=3, window_seconds=60)
    limiter.record_submission(at=0)
    limiter.record_submission(at=1)
    limiter.record_cancel(at=2)

    assert limiter.cancel_ratio(at=2) == 0.5
    assert limiter.cancel_ratio(at=62) == 0.0

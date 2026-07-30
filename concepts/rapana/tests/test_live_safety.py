from __future__ import annotations

import re
from decimal import Decimal

from rapana.config import Settings
from rapana.fleet.capital import StagedCapital
from rapana.fleet.execution import LiveExecutor
from rapana.risk.guardrails import KillSwitch, TradeProposal
from rapana.risk.live_safety import (
    LiveGuard,
    build_client_order_id,
    classify_reconcile_orders,
    parse_client_order_id,
    preflight,
)


class FakeExchange:
    def __init__(self):
        self.apiKey = "livekey"
        self.orders = []

    def create_order(self, symbol, type, side, amount, params=None):
        self.orders.append({"symbol": symbol, "type": type, "side": side,
                            "amount": amount, "params": params or {}})
        return {"id": "o1", "filled": amount, "average": 60000.0, "fee": {"cost": 0.5}}


class FakeClient:
    def __init__(self):
        self.exchange = FakeExchange()

    def create_order(self, symbol, side, amount, *, order_type="market", price=None,
                     post_only=False, client_order_id=None, params=None):
        merged = dict(params or {})
        if client_order_id is not None:
            merged["clientOrderId"] = client_order_id
        if post_only:
            merged["postOnly"] = True
        return self.exchange.create_order(
            symbol=symbol, type=order_type, side=side, amount=amount, params=merged,
        )

    def fetch_balance(self):
        return {"total": {"USDT": 9500.0, "BTC": 0.008}}


class EmptyBalanceClient(FakeClient):
    def fetch_balance(self):
        return {"total": {}}


class NoExchangeClient:
    @property
    def exchange(self):
        raise AssertionError("exchange should not be touched before static preflight blocks")


class ZeroCapital(StagedCapital):
    @property
    def fraction(self) -> float:
        return 0.0


def _proposal():
    return TradeProposal(
        symbol="BTC/USDT", side="buy",
        qty=Decimal("0.001"), price=Decimal("60000"), reference_price=Decimal("60000"),
    )


def _long_symbol_proposal():
    return TradeProposal(
        symbol="1000PEPE/USDT", side="buy",
        qty=Decimal("12345.6789"), price=Decimal("0.00000123"),
        reference_price=Decimal("0.00000123"),
    )


def test_preflight_fails_when_paper_env():
    s = Settings(RAPANA_ENV="paper")
    res = preflight(s, StagedCapital(paper=False), KillSwitch(), has_api_key=True)
    assert res.ok is False
    assert "env_is_live" in res.failures


def test_preflight_passes_when_live():
    s = Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True)
    res = preflight(s, StagedCapital(paper=False), KillSwitch(), has_api_key=True)
    assert res.ok is True


def test_preflight_fails_when_withdraw_not_attested():
    s = Settings(RAPANA_ENV="live")  # withdraw_verified defaults False -> fail-closed
    res = preflight(s, StagedCapital(paper=False), KillSwitch(), has_api_key=True)
    assert res.ok is False
    assert "withdraw_disabled_attested" in res.failures


def test_preflight_fails_when_killswitch_tripped(tmp_path):
    s = Settings(RAPANA_ENV="live")
    ks = KillSwitch(path=tmp_path / "KS")
    ks.trip()
    res = preflight(s, StagedCapital(paper=False), ks, has_api_key=True)
    assert res.ok is False
    assert "kill_switch_clear" in res.failures
    ks.clear()


def test_live_guard_blocks_in_paper_mode():
    s = Settings(RAPANA_ENV="paper")
    guard = LiveGuard(LiveExecutor(FakeClient()), s, StagedCapital(paper=False), KillSwitch())
    result = guard.execute(_proposal(), available_cash=Decimal("10000"))
    assert result.status == "rejected"
    assert result.is_booked is False
    assert guard.inner.client.exchange.orders == []  # no order dispatched


def test_live_guard_dispatches_with_exchange_api_key_in_live():
    s = Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True)
    guard = LiveGuard(LiveExecutor(FakeClient()), s, StagedCapital(paper=False), KillSwitch())
    client_order_id = build_client_order_id(_proposal(), cycle=1, decision_ts=123)
    result = guard.execute(
        _proposal(), available_cash=Decimal("10000"), client_order_id=client_order_id,
    )
    assert result.status == "filled"
    assert result.mode == "live"
    order = guard.inner.client.exchange.orders[0]
    assert order["params"]["clientOrderId"] == client_order_id
    parsed = parse_client_order_id(client_order_id)
    assert parsed is not None
    assert parsed.symbol_hint == "BTCUSDT"


def test_live_guard_blocks_when_exchange_api_key_missing():
    client = FakeClient()
    client.exchange.apiKey = None
    s = Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True)
    guard = LiveGuard(LiveExecutor(client), s, StagedCapital(paper=False), KillSwitch())
    result = guard.execute(_proposal(), available_cash=Decimal("10000"))
    assert result.status == "rejected"
    assert result.is_booked is False
    assert guard.inner.client.exchange.orders == []
    assert "api_key_present" in guard._last_preflight.failures


def test_live_guard_execute_blocks_each_preflight_gate_independently(tmp_path):
    def _run(settings, capital, kill_switch, client):
        guard = LiveGuard(LiveExecutor(client), settings, capital, kill_switch)
        result = guard.execute(
            _proposal(),
            available_cash=Decimal("10000"),
            client_order_id=build_client_order_id(_proposal(), cycle=1, decision_ts=1),
        )
        return guard, result

    cases = []
    cases.append((
        "env_is_live",
        Settings(RAPANA_ENV="paper", RAPANA_WITHDRAW_VERIFIED=True),
        StagedCapital(paper=False),
        KillSwitch(),
        FakeClient(),
    ))

    kill_switch = KillSwitch(path=tmp_path / "KS")
    kill_switch.trip()
    cases.append((
        "kill_switch_clear",
        Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True),
        StagedCapital(paper=False),
        kill_switch,
        FakeClient(),
    ))

    missing_key = FakeClient()
    missing_key.exchange.apiKey = None
    cases.append((
        "api_key_present",
        Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True),
        StagedCapital(paper=False),
        KillSwitch(),
        missing_key,
    ))
    cases.append((
        "capital_stage_set",
        Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True),
        ZeroCapital(paper=False),
        KillSwitch(),
        FakeClient(),
    ))
    cases.append((
        "withdraw_disabled_attested",
        Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=False),
        StagedCapital(paper=False),
        KillSwitch(),
        FakeClient(),
    ))

    for expected_failure, settings, capital, ks, client in cases:
        guard, result = _run(settings, capital, ks, client)
        assert result.status == "rejected", expected_failure
        assert result.is_booked is False
        assert expected_failure in guard._last_preflight.failures
        if hasattr(client, "exchange"):
            assert client.exchange.orders == []


def test_live_guard_blocked_static_preflight_does_not_touch_exchange_or_require_id(tmp_path):
    paper_guard = LiveGuard(
        LiveExecutor(NoExchangeClient()),
        Settings(RAPANA_ENV="paper", RAPANA_WITHDRAW_VERIFIED=True),
        StagedCapital(paper=False),
        KillSwitch(),
    )
    paper_result = paper_guard.execute(_proposal(), available_cash=Decimal("10000"))
    assert paper_result.status == "rejected"
    assert "env_is_live" in paper_guard._last_preflight.failures
    assert paper_result.reason is None

    ks = KillSwitch(path=tmp_path / "KS2")
    ks.trip()
    kill_guard = LiveGuard(
        LiveExecutor(NoExchangeClient()),
        Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True),
        StagedCapital(paper=False),
        ks,
    )
    kill_result = kill_guard.execute(_proposal(), available_cash=Decimal("10000"))
    assert kill_result.status == "rejected"
    assert "kill_switch_clear" in kill_guard._last_preflight.failures
    assert kill_result.reason is None


def test_live_guard_rejects_missing_client_order_id():
    s = Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True)
    guard = LiveGuard(LiveExecutor(FakeClient()), s, StagedCapital(paper=False), KillSwitch())
    result = guard.execute(_proposal(), available_cash=Decimal("10000"))
    assert result.status == "rejected"
    assert result.reason == "missing_client_order_id"
    assert guard.inner.client.exchange.orders == []


def test_cycle_stamped_client_order_id_unique_across_cycles_stable_within_cycle():
    proposal = _proposal()
    first = build_client_order_id(proposal, cycle=7, decision_ts=1_000)
    retry = build_client_order_id(proposal, cycle=7, decision_ts=1_000)
    next_cycle = build_client_order_id(proposal, cycle=8, decision_ts=1_000)

    assert first == retry
    assert first != next_cycle
    assert first.startswith("rpn-BTCUSDT-")


def test_client_order_id_is_mexc_safe_for_realistic_timestamp_and_long_symbol():
    client_order_id = build_client_order_id(
        _long_symbol_proposal(), cycle=12_345, decision_ts=1_719_241_620_000,
    )

    assert re.fullmatch(r"[0-9a-zA-Z_-]{1,32}", client_order_id)
    assert len(client_order_id) <= 32
    assert client_order_id.startswith("rpn-1000PEPEUS-")
    parsed = parse_client_order_id(client_order_id)
    assert parsed is not None
    assert parsed.symbol_hint == "1000PEPEUS"
    assert len(parsed.digest) == 16


def test_live_guard_dedupes_in_cycle_retry_by_client_order_id():
    s = Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True)
    guard = LiveGuard(LiveExecutor(FakeClient()), s, StagedCapital(paper=False), KillSwitch())
    client_order_id = build_client_order_id(_proposal(), cycle=7, decision_ts=1_000)
    first = guard.execute(
        _proposal(), available_cash=Decimal("10000"), client_order_id=client_order_id,
    )
    retry = guard.execute(
        _proposal(), available_cash=Decimal("10000"), client_order_id=client_order_id,
    )

    assert first is retry
    assert len(guard.inner.client.exchange.orders) == 1
    assert guard.inner.client.exchange.orders[0]["params"]["clientOrderId"] == client_order_id

    next_cycle_id = build_client_order_id(_proposal(), cycle=8, decision_ts=1_000)
    guard.execute(_proposal(), available_cash=Decimal("10000"), client_order_id=next_cycle_id)
    assert len(guard.inner.client.exchange.orders) == 2


def test_reconcile_reads_real_balance():
    s = Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True)
    guard = LiveGuard(LiveExecutor(FakeClient()), s, StagedCapital(paper=False), KillSwitch())
    snap = guard.reconcile()
    assert snap is not None
    assert snap.balances["USDT"] == Decimal("9500")
    assert snap.balances["BTC"] == Decimal("0.008")


def test_reconcile_successful_empty_report_is_distinct_from_fetch_failure():
    s = Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True)
    guard = LiveGuard(LiveExecutor(EmptyBalanceClient()), s, StagedCapital(paper=False), KillSwitch())
    report = guard.reconcile()

    assert report is not None
    assert report.balances == {}
    assert report.orders == []


def test_reconcile_classifies_fake_exchange_orders():
    expected_filled = build_client_order_id(_proposal(), cycle=1, decision_ts=1000)
    expected_open = build_client_order_id(_proposal(), cycle=2, decision_ts=2000)
    missing = build_client_order_id(_proposal(), cycle=3, decision_ts=3000)
    orders = [
        {
            "id": "filled-1",
            "symbol": "BTC/USDT",
            "status": "closed",
            "filled": "0.001",
            "remaining": "0",
            "clientOrderId": expected_filled,
        },
        {
            "id": "open-1",
            "symbol": "BTC/USDT",
            "status": "open",
            "filled": "0",
            "remaining": "0.001",
            "clientOrderId": expected_open,
        },
        {"id": "foreign-1", "symbol": "ETH/USDT", "status": "open", "clientOrderId": "manual"},
    ]

    records = classify_reconcile_orders([expected_filled, expected_open, missing], orders)
    by_id = {r.client_order_id: r for r in records}

    assert by_id[expected_filled].classification == "expected-filled"
    assert by_id[expected_open].classification == "expected-open"
    assert by_id[missing].classification == "orphan/unknown"
    assert by_id[missing].status == "missing"
    assert by_id["manual"].classification == "orphan/unknown"

    s = Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True)
    guard = LiveGuard(LiveExecutor(FakeClient()), s, StagedCapital(paper=False), KillSwitch())
    report = guard.reconcile(
        expected_client_order_ids=[expected_filled, expected_open, missing],
        exchange_orders=orders,
    )
    assert report is not None
    assert [r.classification for r in report.orders].count("expected-filled") == 1
    assert [r.classification for r in report.orders].count("expected-open") == 1


def test_reconcile_returns_none_on_fetch_failure():
    class BoomClient(FakeClient):
        def fetch_balance(self):
            raise OSError("api down")

    s = Settings(RAPANA_ENV="live", RAPANA_WITHDRAW_VERIFIED=True)
    guard = LiveGuard(LiveExecutor(BoomClient()), s, StagedCapital(paper=False), KillSwitch())
    # Failure -> balance UNKNOWN (None), never conflated with an empty balance.
    assert guard.reconcile() is None

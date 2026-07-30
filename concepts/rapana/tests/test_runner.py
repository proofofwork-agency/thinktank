from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd

from rapana.agents import Analyst, ComplianceAuditor
from rapana.config import Settings
from rapana.fleet import (
    Fleet,
    FleetConfig,
    FleetRunner,
    InMemoryProvider,
    PaperExecutor,
    PerformanceTracker,
    ReplayProvider,
    StagedCapital,
)
from rapana.fleet.execution import ExecutionTrader
from rapana.fleet.maker_fill import PaperMakerFillModel
from rapana.fleet.runner import format_paper_maker_eval_report, summarize_paper_maker_eval
from rapana.journal.ledger import DecisionLedger
from rapana.notify import NullNotifier
from rapana.risk.guardrails import KillSwitch
from rapana.signals import Signal


def _uptrend(n=200, drift=0.003):
    rng = np.random.default_rng(7)
    price = 100 * np.exp(np.cumsum(rng.normal(drift, 0.008, n)))
    ts = np.arange(n) * 3600_000
    return pd.DataFrame({
        "ts": ts, "open": price, "high": price * 1.004, "low": price * 0.996,
        "close": price, "volume": 1000.0,
    })


class _ScheduledAnalyst(Analyst):
    def __init__(self, schedule: dict[int, str]) -> None:
        self.schedule = schedule
        self.units = lambda _symbol: Decimal("0")
        self.observations: list[dict] = []

    def analyze(self, symbol, provider):
        history = provider.get_history(symbol, "1h", 999)
        direction = self.schedule.get(len(history), "neutral")
        strength = 1.0 if direction == "bullish" else -1.0 if direction == "bearish" else 0.0
        self.observations.append({
            "history_len": len(history),
            "units": self.units(symbol),
            "direction": direction,
        })
        return Signal(symbol, "market", direction, strength, 1.0, "scheduled")


def _build_runner(
    tmp_path,
    df=None,
    initial=Decimal("10000"),
    today_fn=None,
    analysts=None,
    symbols=None,
    settings=None,
    max_weight=0.10,
):
    symbols = symbols or ["BTC/USDT"]
    df = _uptrend() if df is None else df
    data = df if isinstance(df, dict) else {symbols[0]: df}
    provider = InMemoryProvider(data)  # placeholder; replay swaps it
    ledger = DecisionLedger(path=tmp_path / "j.jsonl")
    auditor = ComplianceAuditor(ledger)
    capital = StagedCapital(paper=True)
    trader = ExecutionTrader(PaperExecutor(), capital)
    fleet = Fleet(
        provider=provider, capital=capital, trader=trader, auditor=auditor,
        settings=settings,
        config=FleetConfig(symbols=list(symbols), max_weight=max_weight),
        initial_equity=initial,
        analysts=analysts,
    )
    fleet.kill_switch = KillSwitch(path=tmp_path / "KS")
    perf = PerformanceTracker(initial_equity=initial)
    runner = FleetRunner(
        fleet, perf, notifier=NullNotifier(), state_path=tmp_path / "state.json",
        today_fn=today_fn,
    )
    return runner, ledger


def _flat_replay_df(*, penetrate=True, n=4):
    price = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0 if penetrate else 99.98)
    ts = np.arange(n) * 3600_000
    return pd.DataFrame({
        "ts": ts, "open": price, "high": high, "low": low,
        "close": price, "volume": 1000.0,
    })


def test_replay_runs_and_produces_summary(tmp_path):
    runner, _ = _build_runner(tmp_path)
    replay_provider = ReplayProvider({"BTC/USDT": _uptrend()})
    summary = runner.run_replay(replay_provider, warmup=60, bars_per_day=24)
    assert summary["cycles"] > 0
    assert summary["final_equity"] != "0"
    assert "total_return_pct" in summary


def test_replay_equity_recorded_per_bar(tmp_path):
    runner, _ = _build_runner(tmp_path)
    replay_provider = ReplayProvider({"BTC/USDT": _uptrend()})
    runner.run_replay(replay_provider, warmup=60, bars_per_day=24)
    # one performance record per bar (200 - 60 warmup)
    assert len(runner.performance.records) == 200 - 60


def test_state_save_and_load_roundtrip(tmp_path):
    runner, _ = _build_runner(tmp_path, initial=Decimal("10000"))
    replay_provider = ReplayProvider({"BTC/USDT": _uptrend()})
    runner.run_replay(replay_provider, warmup=60, bars_per_day=24)
    runner.save_state()

    cash_before = runner.fleet.paper.cash
    positions_before = dict(runner.fleet.paper.positions)
    realized_before = runner.fleet.paper.realized_pnl

    # mutate then reload
    runner.fleet.paper.cash = Decimal("0")
    runner.fleet.paper.positions = {"X": Decimal("999")}
    assert runner.load_state() is True

    assert runner.fleet.paper.cash == cash_before
    assert runner.fleet.paper.positions == positions_before
    assert runner.fleet.paper.realized_pnl == realized_before


def test_load_state_missing_returns_false(tmp_path):
    runner, _ = _build_runner(tmp_path)
    assert runner.load_state() is False


def test_scheduled_run_resets_breaker_on_calendar_rollover(tmp_path):
    days = iter([date(2026, 6, 24), date(2026, 6, 25)])
    runner, _ = _build_runner(tmp_path, today_fn=lambda: next(days))
    runner.fleet.breaker.record_realized(Decimal("-400"))
    assert runner.fleet.breaker.is_tripped()

    runner.run_scheduled(max_cycles=2, digest_every=0)

    assert runner.fleet.breaker.realized_today == Decimal("0")
    assert runner.fleet.breaker.unrealized_today == Decimal("0")
    assert runner.fleet.breaker.is_tripped() is False


def test_load_state_resets_stale_breaker_day(tmp_path):
    runner, _ = _build_runner(tmp_path, today_fn=lambda: date(2026, 6, 24))
    runner.fleet.breaker.record_realized(Decimal("-400"))
    runner.save_state()

    fresh, _ = _build_runner(tmp_path, today_fn=lambda: date(2026, 6, 25))
    assert fresh.load_state() is True

    assert fresh.fleet.breaker.realized_today == Decimal("0")
    assert fresh.fleet.breaker.unrealized_today == Decimal("0")
    assert fresh.fleet.breaker.is_tripped() is False


def test_paper_maker_eval_submits_then_books_fill_on_resolution_bar(tmp_path):
    analyst = _ScheduledAnalyst({2: "bullish", 3: "neutral"})
    runner, ledger = _build_runner(tmp_path, df=_flat_replay_df(), analysts=[analyst])
    analyst.units = runner.fleet.paper.units
    states = {}

    def capture(bar, state):
        states[bar] = {
            "cash": state.cash,
            "positions": dict(state.positions),
        }

    runner.run_replay(
        ReplayProvider({"BTC/USDT": _flat_replay_df()}),
        bars=4,
        warmup=2,
        on_cycle=capture,
        paper_maker_eval=True,
        maker_fill_model=PaperMakerFillModel(offset_bps=Decimal("2"), lifetime_bars=1),
    )

    assert states[2]["cash"] == Decimal("10000")
    assert states[2]["positions"].get("BTC/USDT", Decimal("0")) == Decimal("0")
    assert states[3]["positions"]["BTC/USDT"] > 0
    assert analyst.observations[0]["history_len"] == 2
    assert analyst.observations[1]["history_len"] == 3
    assert analyst.observations[1]["units"] > 0

    events = ledger.read_all()
    kinds = [e["kind"] for e in events]
    assert kinds.count("maker_submitted") == 1
    assert kinds.count("maker_filled") == 1
    assert "missed_fill" not in kinds
    assert "order_not_booked" not in kinds
    filled_idx = kinds.index("maker_filled")
    signal_indices = [i for i, kind in enumerate(kinds) if kind == "signal"]
    assert kinds.index("maker_submitted") < filled_idx < signal_indices[1]
    fill_event = next(e for e in events if e["kind"] == "maker_filled")
    assert fill_event["data"]["metadata"]["submitted_bar"] == "2"
    assert fill_event["data"]["metadata"]["fill_bar"] == "3"
    assert fill_event["data"]["metadata"]["touch_policy"] == "strict_penetration"


def test_paper_maker_eval_fill_uses_maker_fee_rate(tmp_path):
    analyst = _ScheduledAnalyst({2: "bullish", 3: "neutral"})
    settings = Settings(RAPANA_MAKER_FEE_PCT=0.0002)
    runner, ledger = _build_runner(
        tmp_path,
        df=_flat_replay_df(),
        analysts=[analyst],
        settings=settings,
    )

    runner.run_replay(
        ReplayProvider({"BTC/USDT": _flat_replay_df()}),
        bars=4,
        warmup=2,
        paper_maker_eval=True,
        maker_fill_model=PaperMakerFillModel(offset_bps=Decimal("2"), lifetime_bars=1),
    )

    fill_event = next(e for e in ledger.read_all() if e["kind"] == "maker_filled")
    assert fill_event["data"]["fee"] == "0.049990"
    assert fill_event["data"]["metadata"]["maker_fee_pct"] == "0.0002"


def test_paper_maker_eval_report_metrics_are_computed_from_maker_events():
    maker_events = [
        {"kind": "maker_submitted", "data": {}},
        {"kind": "maker_submitted", "data": {}},
        {"kind": "maker_submitted", "data": {}},
        {"kind": "maker_submitted", "data": {}},
        {
            "kind": "maker_filled",
            "data": {"filled_qty": "2", "price": "100", "fee": "0.100000"},
        },
        {
            "kind": "maker_filled",
            "data": {"filled_qty": "1", "price": "50", "fee": "0.025000"},
        },
        {
            "kind": "maker_canceled",
            "data": {"filled_qty": "0", "proposed_qty": "10", "qty": "0", "price": "10"},
        },
        {
            "kind": "order_not_booked",
            "data": {
                "status": "rejected",
                "filled_qty": "0",
                "proposed_qty": "5",
                "qty": "0",
                "price": "20",
                "metadata": {"execution_mode": "maker"},
            },
        },
    ]

    report = summarize_paper_maker_eval(
        taker_summary={"final_equity": "1000.50"},
        maker_summary={"final_equity": "1001.00"},
        maker_events=maker_events,
        taker_fee_pct=Decimal("0.001"),
        maker_fee_pct=Decimal("0.0005"),
        offset_bps=Decimal("2"),
        lifetime_bars=1,
    )

    assert report.net_execution_delta == Decimal("0.50")
    assert report.fill_rate == 0.5
    assert report.gross_fee_savings == Decimal("0.125000")
    assert report.taker_fee_equiv == Decimal("0.250000")
    assert report.maker_fee_paid == Decimal("0.125000")
    assert report.residual_path_delta == Decimal("0.375000")
    assert report.missed_count == 2
    assert report.missed_notional == Decimal("200")
    text = format_paper_maker_eval_report(report)
    assert "PRIMARY go/no-go" in text
    assert "combined limit-price improvement minus missed-fill opportunity cost minus path effects" in text
    assert "paper_maker_fill_fraction" in text


def test_paper_maker_eval_reserves_cash_for_same_bar_buys(tmp_path):
    symbols = ["AAA/USDT", "BBB/USDT"]
    data = {symbol: _flat_replay_df() for symbol in symbols}
    analyst = _ScheduledAnalyst({2: "bullish", 3: "neutral"})
    settings = Settings(
        RAPANA_MAKER_FEE_PCT=0,
        RAPANA_RISK_MAX_POSITION_PCT=1,
        RAPANA_RISK_MAX_TOTAL_EXPOSURE_PCT=2,
        RAPANA_RISK_MAX_NOTIONAL_PER_ORDER=10000,
        RAPANA_RISK_MAX_ORDERS_PER_MIN=10,
    )
    runner, ledger = _build_runner(
        tmp_path,
        df=data,
        initial=Decimal("100"),
        analysts=[analyst],
        symbols=symbols,
        settings=settings,
        max_weight=0.75,
    )

    runner.run_replay(
        ReplayProvider(data),
        bars=4,
        warmup=2,
        paper_maker_eval=True,
        maker_fill_model=PaperMakerFillModel(offset_bps=Decimal("2"), lifetime_bars=1),
    )

    events = ledger.read_all()
    kinds = [e["kind"] for e in events]
    assert kinds.count("maker_submitted") == 1
    assert kinds.count("maker_filled") == 1
    rejected = [e for e in events if e["kind"] == "order_not_booked"]
    assert len(rejected) == 1
    assert rejected[0]["data"]["reason"] in {"capital_stage", "insufficient_cash"}
    assert sum(1 for qty in runner.fleet.paper.positions.values() if qty > 0) == 1


def test_paper_maker_eval_releases_cash_reservation_on_cancel(tmp_path):
    analyst = _ScheduledAnalyst({2: "bullish", 4: "bullish"})
    df = _flat_replay_df(penetrate=False, n=5)
    settings = Settings(
        RAPANA_MAKER_FEE_PCT=0,
        RAPANA_RISK_MAX_POSITION_PCT=1,
        RAPANA_RISK_MAX_TOTAL_EXPOSURE_PCT=1,
        RAPANA_RISK_MAX_NOTIONAL_PER_ORDER=10000,
        RAPANA_RISK_MAX_ORDERS_PER_MIN=10,
    )
    runner, ledger = _build_runner(
        tmp_path,
        df=df,
        initial=Decimal("100"),
        analysts=[analyst],
        settings=settings,
        max_weight=0.75,
    )

    runner.run_replay(
        ReplayProvider({"BTC/USDT": df}),
        bars=5,
        warmup=2,
        paper_maker_eval=True,
        maker_fill_model=PaperMakerFillModel(offset_bps=Decimal("2"), lifetime_bars=1),
    )

    kinds = [e["kind"] for e in ledger.read_all()]
    assert kinds.count("maker_submitted") == 2
    assert kinds.count("maker_canceled") == 2
    assert "maker_filled" not in kinds
    assert runner.fleet.paper.cash == Decimal("100")


def test_paper_maker_eval_miss_records_only_at_expiry(tmp_path):
    analyst = _ScheduledAnalyst({2: "bullish", 3: "neutral"})
    df = _flat_replay_df(penetrate=False)
    runner, ledger = _build_runner(tmp_path, df=df, analysts=[analyst])

    runner.run_replay(
        ReplayProvider({"BTC/USDT": df}),
        bars=4,
        warmup=2,
        paper_maker_eval=True,
        maker_fill_model=PaperMakerFillModel(offset_bps=Decimal("2"), lifetime_bars=1),
    )

    assert runner.fleet.paper.units("BTC/USDT") == Decimal("0")
    kinds = [e["kind"] for e in ledger.read_all()]
    submitted_idx = kinds.index("maker_submitted")
    canceled_idx = kinds.index("maker_canceled")
    assert submitted_idx < canceled_idx
    assert "missed_fill" not in kinds[:canceled_idx]
    assert "order_not_booked" not in kinds[:canceled_idx]
    assert "missed_fill" in kinds[canceled_idx:]
    assert "order_not_booked" in kinds[canceled_idx:]


def test_paper_maker_eval_tail_order_expires_without_future_bar(tmp_path):
    analyst = _ScheduledAnalyst({2: "bullish"})
    df = _flat_replay_df(n=3)
    runner, ledger = _build_runner(tmp_path, df=df, analysts=[analyst])

    runner.run_replay(
        ReplayProvider({"BTC/USDT": df}),
        bars=3,
        warmup=2,
        paper_maker_eval=True,
        maker_fill_model=PaperMakerFillModel(offset_bps=Decimal("2"), lifetime_bars=1),
    )

    assert runner.fleet.paper.units("BTC/USDT") == Decimal("0")
    kinds = [e["kind"] for e in ledger.read_all()]
    assert "maker_submitted" in kinds
    assert "maker_canceled" in kinds
    assert "missed_fill" in kinds
    assert "maker_filled" not in kinds


def test_normal_replay_still_executes_inline_without_maker_eval(tmp_path):
    analyst = _ScheduledAnalyst({2: "bullish", 3: "neutral"})
    runner, ledger = _build_runner(tmp_path, df=_flat_replay_df(), analysts=[analyst])
    states = {}

    def capture(bar, state):
        states[bar] = dict(state.positions)

    runner.run_replay(
        ReplayProvider({"BTC/USDT": _flat_replay_df()}),
        bars=4,
        warmup=2,
        on_cycle=capture,
    )

    assert states[2]["BTC/USDT"] > 0
    kinds = [e["kind"] for e in ledger.read_all()]
    assert "fill" in kinds
    assert "maker_submitted" not in kinds

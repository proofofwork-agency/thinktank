from __future__ import annotations

from decimal import Decimal

import pandas as pd

from rapana.agents import ComplianceAuditor
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
from rapana.journal.ledger import DecisionLedger
from rapana.notify import NullNotifier


def test_synthetic_generator_shape():
    from rapana.data.synthetic import make_synthetic_ohlcv

    data = make_synthetic_ohlcv(["BTC/USDT", "ETH/USDT"], bars=300, seed=1)
    assert set(data) == {"BTC/USDT", "ETH/USDT"}
    for _sym, df in data.items():
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["ts", "open", "high", "low", "close", "volume"]
        assert len(df) == 300
        assert (df["high"] >= df["close"]).all()
        assert (df["low"] <= df["close"]).all()
        assert df["ts"].is_monotonic_increasing


def test_synthetic_is_deterministic():
    from rapana.data.synthetic import make_synthetic_ohlcv

    a = make_synthetic_ohlcv(["BTC/USDT"], bars=100, seed=42)
    b = make_synthetic_ohlcv(["BTC/USDT"], bars=100, seed=42)
    assert a["BTC/USDT"]["close"].equals(b["BTC/USDT"]["close"])


def _runner(tmp_path, symbols=("BTC/USDT", "ETH/USDT", "SOL/USDT"), initial=Decimal("10000")):
    from rapana.data.synthetic import make_synthetic_ohlcv

    data = make_synthetic_ohlcv(list(symbols), bars=400, seed=7)
    provider = InMemoryProvider({s: data[s] for s in symbols})
    ledger = DecisionLedger(path=tmp_path / "j.jsonl")
    auditor = ComplianceAuditor(ledger)
    capital = StagedCapital(paper=True)
    trader = ExecutionTrader(PaperExecutor(), capital)
    fleet = Fleet(
        provider=provider, capital=capital, trader=trader, auditor=auditor,
        config=FleetConfig(symbols=list(symbols)), initial_equity=initial,
    )
    perf = PerformanceTracker(initial_equity=initial)
    runner = FleetRunner(fleet, perf, notifier=NullNotifier(), state_path=tmp_path / "s.json")
    return runner, data


def test_replay_produces_trades(tmp_path):
    runner, data = _runner(tmp_path)
    replay_provider = ReplayProvider(data)
    summary = runner.run_replay(replay_provider, warmup=60, bars_per_day=24)
    assert summary["cycles"] > 0
    # On trending synthetic data the fleet must actually trade (realize PnL).
    assert summary["trade_events"] > 0


def test_on_cycle_callback_invoked(tmp_path):
    runner, data = _runner(tmp_path)
    replay_provider = ReplayProvider(data)
    seen = []

    def trace(bar, state):
        seen.append((bar, state.cycle))

    runner.run_replay(replay_provider, warmup=60, bars_per_day=24, on_cycle=trace)
    assert len(seen) > 50  # called once per replayed bar
    assert all(isinstance(b, int) for b, _ in seen)


def test_replay_reflection_learns(tmp_path):
    runner, data = _runner(tmp_path)
    runner.run_replay(ReplayProvider(data), warmup=60, bars_per_day=24)
    analytics = runner.fleet.memory.analytics()
    assert "market" in analytics
    assert analytics["market"]["total"] > 0


def test_memory_resolves_against_fresh_current_prices(tmp_path):
    """Pin the resolve-after-loop ordering: memory.resolve must receive THIS
    cycle's freshly-loaded prices (>0), not stale/empty pre-loop state."""
    from rapana.data.synthetic import make_synthetic_ohlcv
    from rapana.risk.guardrails import KillSwitch

    symbols = ["BTC/USDT", "ETH/USDT"]
    data = make_synthetic_ohlcv(symbols, bars=120, seed=3)
    provider = ReplayProvider(data)
    auditor = ComplianceAuditor(DecisionLedger(path=tmp_path / "j.jsonl"))
    capital = StagedCapital(paper=True)
    trader = ExecutionTrader(PaperExecutor(), capital)
    fleet = Fleet(
        provider=provider, capital=capital, trader=trader, auditor=auditor,
        config=FleetConfig(symbols=symbols), initial_equity=Decimal("10000"),
    )
    # Isolate the kill switch so a stray ./state/KILL_SWITCH can't halt the cycle.
    fleet.kill_switch = KillSwitch(path=tmp_path / "KS")

    captured: dict = {}
    real_resolve = fleet.memory.resolve

    def spy(prices, now_ts):
        captured["prices"] = dict(prices)
        captured["now_ts"] = now_ts
        return real_resolve(prices, now_ts)

    fleet.memory.resolve = spy

    provider.seek(50)
    fleet.run_cycle()

    assert set(captured["prices"]) == set(symbols)
    for s in symbols:
        # fresh == the bar we're on, and non-zero (proves not stale/empty)
        assert captured["prices"][s] == provider.get_price(s)
        assert captured["prices"][s] > 0
    assert captured["now_ts"] == provider.timestamp(symbols[0])

"""Tests for the Scout rebalance hook in the fleet orchestrator."""
from __future__ import annotations

from decimal import Decimal

from rapana.agents import ComplianceAuditor
from rapana.data.synthetic import make_synthetic_ohlcv
from rapana.fleet import Fleet, FleetConfig, InMemoryProvider, PaperExecutor, StagedCapital
from rapana.fleet.execution import ExecutionTrader
from rapana.journal.ledger import DecisionLedger


class _FakeScout:
    def __init__(self, picks, raises=False):
        self._picks = picks
        self._raises = raises
        self.calls = 0

    def select_symbols(self):
        self.calls += 1
        if self._raises:
            raise RuntimeError("boom")
        return list(self._picks)


def _fleet(tmp_path, *, symbols=("BTC/USDT", "ETH/USDT"), scout=None,
           mode="fixed", rebalance_bars=24):
    data = make_synthetic_ohlcv(list(symbols), bars=80, seed=1)
    provider = InMemoryProvider({s: data[s] for s in symbols})
    auditor = ComplianceAuditor(DecisionLedger(path=tmp_path / "j.jsonl"))
    capital = StagedCapital(paper=True)
    trader = ExecutionTrader(PaperExecutor(), capital)
    return Fleet(
        provider=provider, capital=capital, trader=trader, auditor=auditor,
        config=FleetConfig(symbols=list(symbols), universe_mode=mode, rebalance_bars=rebalance_bars),
        scout=scout,
    )


def test_fixed_mode_never_consults_scout(tmp_path):
    scout = _FakeScout(["XRP/USDT"])
    fleet = _fleet(tmp_path, scout=scout, mode="fixed")
    fleet.state.cycle = 1
    fleet._maybe_rebalance_universe()
    assert fleet.symbols == ["BTC/USDT", "ETH/USDT"]
    assert scout.calls == 0


def test_auto_mode_without_scout_is_noop(tmp_path):
    fleet = _fleet(tmp_path, scout=None, mode="auto", rebalance_bars=1)
    fleet.state.cycle = 1
    fleet._maybe_rebalance_universe()
    assert fleet.symbols == ["BTC/USDT", "ETH/USDT"]


def test_auto_mode_rebalances(tmp_path):
    scout = _FakeScout(["XRP/USDT", "DOGE/USDT"])
    fleet = _fleet(tmp_path, scout=scout, mode="auto", rebalance_bars=1)
    fleet.state.cycle = 1
    fleet._maybe_rebalance_universe()
    assert fleet.symbols == ["XRP/USDT", "DOGE/USDT"]
    assert scout.calls == 1


def test_auto_mode_unions_held_positions(tmp_path):
    scout = _FakeScout(["XRP/USDT"])
    fleet = _fleet(tmp_path, scout=scout, mode="auto", rebalance_bars=1)
    fleet.paper.positions["BTC/USDT"] = Decimal("1")  # an open position
    fleet.state.cycle = 1
    fleet._maybe_rebalance_universe()
    assert fleet.symbols == ["XRP/USDT", "BTC/USDT"]  # picks first, held kept (not orphaned)


def test_scout_failure_keeps_previous_universe(tmp_path):
    scout = _FakeScout([], raises=True)
    fleet = _fleet(tmp_path, scout=scout, mode="auto", rebalance_bars=1)
    fleet.state.cycle = 1
    fleet._maybe_rebalance_universe()  # must not raise
    assert fleet.symbols == ["BTC/USDT", "ETH/USDT"]


def test_rebalance_only_on_interval(tmp_path):
    scout = _FakeScout(["XRP/USDT"])
    fleet = _fleet(tmp_path, scout=scout, mode="auto", rebalance_bars=10)
    fleet.state.cycle = 5  # not cycle 1, not a multiple of 10
    fleet._maybe_rebalance_universe()
    assert fleet.symbols == ["BTC/USDT", "ETH/USDT"]
    assert scout.calls == 0

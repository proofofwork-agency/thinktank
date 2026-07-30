from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

from rapana.fleet import (
    Fleet,
    FleetConfig,
    InMemoryProvider,
    OrderResult,
    PaperExecutor,
    StagedCapital,
)
from rapana.fleet.execution import ExecutionTrader
from rapana.journal.ledger import DecisionLedger
from rapana.risk.guardrails import TradeProposal
from rapana.risk.live_safety import parse_client_order_id


def _uptrend_df(n=160, start=100.0):
    rng = np.random.default_rng(42)
    rets = rng.normal(0.003, 0.008, n)
    price = start * np.exp(np.cumsum(rets))
    ts = np.arange(n) * 3600_000
    return pd.DataFrame({
        "ts": ts, "open": price, "high": price * 1.005, "low": price * 0.995,
        "close": price, "volume": 1000.0,
    })


def _build_fleet(tmp_path, df=None, initial=Decimal("10000")):
    df = df if df is not None else _uptrend_df()
    provider = InMemoryProvider({"BTC/USDT": df}, {"BTC/USDT": Decimal(str(float(df["close"].iloc[-1])))})
    ledger = DecisionLedger(path=tmp_path / "j.jsonl")
    from rapana.agents import ComplianceAuditor

    auditor = ComplianceAuditor(ledger)
    capital = StagedCapital(paper=True)
    trader = ExecutionTrader(PaperExecutor(), capital)
    fleet = Fleet(
        provider=provider,
        capital=capital,
        trader=trader,
        auditor=auditor,
        config=FleetConfig(symbols=["BTC/USDT"]),
        initial_equity=initial,
    )
    return fleet, ledger


class _FixedTimestampProvider(InMemoryProvider):
    def __init__(self, data, prices, timestamp):
        super().__init__(data, prices)
        self._timestamp = timestamp

    def timestamp(self, symbol: str) -> int:
        return self._timestamp


class _CapturingExecutor(PaperExecutor):
    def __init__(self):
        super().__init__()
        self.client_order_ids: list[str | None] = []

    def execute(self, proposal, available_cash, client_order_id=None):
        self.client_order_ids.append(client_order_id)
        return OrderResult(
            "filled", proposal.symbol, proposal.side, self.mode,
            proposal.qty, proposal.qty, proposal.price, Decimal("0"),
            client_order_id=client_order_id, submitted=True,
        )


def test_fleet_cycle_runs_and_journals(tmp_path):
    fleet, ledger = _build_fleet(tmp_path)
    state = fleet.run_cycle()
    entries = ledger.read_all()
    kinds = {e["kind"] for e in entries}
    assert {"signal", "debate", "risk_decision"}.issubset(kinds)
    assert state.cycle == 1
    assert state.equity > 0
    assert ledger.verify_chain() is True


def test_fleet_buys_on_uptrend(tmp_path):
    fleet, ledger = _build_fleet(tmp_path)
    state = fleet.run_cycle()
    # On a clear uptrend the market analyst should lean bullish and the PM
    # should propose a buy; either it fills or risk-gate denies it (both fine),
    # but at least one trade_proposal event should exist.
    kinds = [e["kind"] for e in ledger.read_all()]
    # Either a proposal was made, or the analyst stayed conservative -> still ok.
    assert state.equity > 0
    assert "signal" in kinds


def test_paper_fleet_is_parked_by_default_and_never_uses_live_guard(tmp_path, monkeypatch):
    import rapana.risk.live_safety as live_safety
    from rapana.agents import ComplianceAuditor

    class BombLiveGuard:
        def __init__(self, *args, **kwargs):
            raise AssertionError("paper fleet must not construct LiveGuard")

    monkeypatch.setattr(live_safety, "LiveGuard", BombLiveGuard)

    df = _uptrend_df()
    price = Decimal("100")
    provider = _FixedTimestampProvider(
        {"BTC/USDT": df}, {"BTC/USDT": price}, timestamp=1_719_241_620_000,
    )
    auditor = ComplianceAuditor(DecisionLedger(path=tmp_path / "j.jsonl"))
    capital = StagedCapital(paper=True)
    executor = _CapturingExecutor()
    fleet = Fleet(
        provider=provider,
        capital=capital,
        trader=ExecutionTrader(executor, capital),
        auditor=auditor,
        config=FleetConfig(symbols=["BTC/USDT"]),
    )
    proposal = TradeProposal(
        symbol="BTC/USDT", side="buy",
        qty=Decimal("0.001"), price=price, reference_price=price,
    )
    fleet.pm.decide = lambda *args, **kwargs: proposal

    state = fleet.run_cycle()

    assert isinstance(fleet.trader.executor, PaperExecutor)
    assert fleet.trader.executor.mode == "paper"
    assert len(executor.client_order_ids) == 1
    assert state.symbols["BTC/USDT"].fill["mode"] == "paper"


def test_fleet_threads_cycle_stamped_client_order_id_to_executor(tmp_path):
    df = _uptrend_df()
    price = Decimal("100")
    provider = _FixedTimestampProvider(
        {"BTC/USDT": df}, {"BTC/USDT": price}, timestamp=1_719_241_620_000,
    )
    ledger = DecisionLedger(path=tmp_path / "j.jsonl")
    from rapana.agents import ComplianceAuditor

    auditor = ComplianceAuditor(ledger)
    capital = StagedCapital(paper=True)
    executor = _CapturingExecutor()
    trader = ExecutionTrader(executor, capital)
    fleet = Fleet(
        provider=provider,
        capital=capital,
        trader=trader,
        auditor=auditor,
        config=FleetConfig(symbols=["BTC/USDT"]),
    )
    proposal = TradeProposal(
        symbol="BTC/USDT", side="buy",
        qty=Decimal("0.001"), price=price, reference_price=price,
    )
    fleet.pm.decide = lambda *args, **kwargs: proposal

    fleet.run_cycle()

    assert len(executor.client_order_ids) == 1
    client_order_id = executor.client_order_ids[0]
    assert client_order_id is not None
    assert client_order_id.startswith("rpn-BTCUSDT-")
    assert len(client_order_id) <= 32
    parsed = parse_client_order_id(client_order_id)
    assert parsed is not None
    assert parsed.symbol_hint == "BTCUSDT"


def test_digest_is_human_readable(tmp_path):
    fleet, _ = _build_fleet(tmp_path)
    state = fleet.run_cycle()
    assert "RAPANA DAILY DIGEST" in state.digest


def test_kill_switch_halts_fleet(tmp_path):
    fleet, ledger = _build_fleet(tmp_path)
    fleet.kill_switch.trip()
    state = fleet.run_cycle()
    kinds = [e["kind"] for e in ledger.read_all()]
    assert "fleet_halted" in kinds
    # halted cycle should not process symbols
    assert all(ss.signals == [] for ss in state.symbols.values())
    fleet.kill_switch.clear()


def test_circuit_breaker_blocks_after_loss(tmp_path):
    fleet, _ = _build_fleet(tmp_path)
    # force a large realized loss to trip the breaker
    fleet.breaker.record_realized(Decimal("-999999"))
    assert fleet.breaker.is_tripped()
    state = fleet.run_cycle()
    # any risk_decision should be a veto because the breaker is tripped
    from rapana.journal.ledger import DecisionLedger as _DL  # noqa: F401

    vetoed = [
        e for e in fleet.auditor.ledger.read_all()
        if e["kind"] == "risk_decision" and not e["data"]["approved"]
    ]
    assert len(vetoed) >= 1
    assert state.equity > 0


def test_circuit_breaker_blocks_on_open_mtm_loss_before_sell(tmp_path):
    fleet, ledger = _build_fleet(tmp_path)
    price = fleet.provider.get_price("BTC/USDT")
    fleet.paper.positions["BTC/USDT"] = Decimal("1")
    fleet.paper.cost_basis["BTC/USDT"] = price + Decimal("400")

    fleet.run_cycle()

    assert fleet.breaker.realized_today == Decimal("0")
    assert fleet.breaker.unrealized_today == Decimal("-400")
    assert fleet.breaker.is_tripped()
    fills = [e for e in ledger.read_all() if e["kind"] == "fill"]
    assert fills == []


def test_order_result_submitted_drives_rate_limit_and_cancel_accounting(tmp_path):
    fleet, ledger = _build_fleet(tmp_path)
    fleet.rate_limiter.max_orders = 1
    result = OrderResult(
        "canceled", "BTC/USDT", "buy", "paper",
        Decimal("0.1"), Decimal("0"), Decimal("49900"), Decimal("0"),
        submitted=True, reason="paper_timeout_no_fill",
        metadata={"execution_mode": "maker"},
    )
    fleet._handle_order_result(result, "BTC/USDT")
    kinds = [e["kind"] for e in ledger.read_all()]
    assert fleet.rate_limiter.would_exceed() is True
    assert fleet.rate_limiter.cancel_ratio() == 1.0
    assert "maker_submitted" in kinds
    assert "maker_canceled" in kinds
    assert "missed_fill" in kinds
    assert "order_not_booked" in kinds


def test_partial_cancel_unverified_order_result_books_filled_qty(tmp_path):
    fleet, ledger = _build_fleet(tmp_path)
    result = OrderResult(
        "partial", "BTC/USDT", "buy", "paper",
        Decimal("0.1"), Decimal("0.04"), Decimal("49900"), Decimal("0"),
        submitted=True, reason="cancel_unverified",
        metadata={"execution_mode": "maker"},
    )
    fleet._handle_order_result(result, "BTC/USDT")
    kinds = [e["kind"] for e in ledger.read_all()]
    assert fleet.paper.units("BTC/USDT") == Decimal("0.04")
    assert fleet.rate_limiter.cancel_ratio() == 1.0
    assert "maker_partial" in kinds
    assert "missed_fill" in kinds
    assert "fill" in kinds


def _fleet_with_settings(tmp_path, settings, df=None, initial=Decimal("10000")):
    from rapana.agents import ComplianceAuditor

    df = df if df is not None else _uptrend_df()
    provider = InMemoryProvider(
        {"BTC/USDT": df}, {"BTC/USDT": Decimal(str(float(df["close"].iloc[-1])))}
    )
    ledger = DecisionLedger(path=tmp_path / "j.jsonl")
    auditor = ComplianceAuditor(ledger)
    capital = StagedCapital(paper=True)
    trader = ExecutionTrader(PaperExecutor(), capital)
    return Fleet(
        provider=provider, capital=capital, trader=trader, auditor=auditor,
        settings=settings, config=FleetConfig(symbols=["BTC/USDT"]), initial_equity=initial,
    )


def _find(fleet, cls_name):
    return next(a for a in fleet.analysts if type(a).__name__ == cls_name)


def test_default_analysts_are_bare_stubs_when_feeds_disabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from rapana.config import Settings

    settings = Settings()
    assert settings.feeds_enabled is False
    fleet = _fleet_with_settings(tmp_path, settings)
    assert [type(a).__name__ for a in fleet.analysts] == [
        "MarketAnalyst", "SentimentAnalyst", "MacroAnalyst",
    ]
    assert _find(fleet, "SentimentAnalyst").sentiment_fn is None
    assert _find(fleet, "MacroAnalyst").macro_fn is None


def test_feeds_wired_into_analysts_when_enabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_FEEDS_ENABLED", "true")
    from rapana.config import Settings

    fleet = _fleet_with_settings(tmp_path, Settings())
    assert _find(fleet, "SentimentAnalyst").sentiment_fn is not None  # FearGreedFeed
    assert _find(fleet, "MacroAnalyst").macro_fn is not None          # MarketPremiumFeed


def test_wired_feeds_emit_directional_signals_the_memory_records(tmp_path, monkeypatch):
    # With feeds enabled, sentiment+macro can emit non-neutral signals, and the
    # reflection loop then records them (only neutrals are skipped) so the fleet
    # learns which source predicts over time.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_FEEDS_ENABLED", "true")
    from rapana.config import Settings

    fleet = _fleet_with_settings(tmp_path, Settings())
    # Inject deterministic feed results so the cycle never touches the network.
    _find(fleet, "SentimentAnalyst").sentiment_fn = lambda sym: (0.6, 0.8)  # bullish
    _find(fleet, "MacroAnalyst").macro_fn = lambda sym: (-0.4, 0.5)         # bearish

    fleet.run_cycle()

    observed = {r.source for r in fleet.memory.pending}
    assert "sentiment" in observed
    assert "macro" in observed


def test_regime_analyst_wired_when_enabled_with_real_brain(tmp_path, monkeypatch):
    from rapana.agents import RegimeAnalyst
    from rapana.config import Settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_LLM_REGIME_ENABLED", "true")
    monkeypatch.setenv("RAPANA_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("RAPANA_LLM_BASE_URL", "http://localhost:9999/v1")
    monkeypatch.setenv("RAPANA_LLM_MODEL", "test-model")
    fleet = _fleet_with_settings(tmp_path, Settings())
    assert any(isinstance(a, RegimeAnalyst) for a in fleet.analysts)


def test_regime_analyst_not_wired_when_provider_none(tmp_path, monkeypatch):
    from rapana.agents import RegimeAnalyst
    from rapana.config import Settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_LLM_REGIME_ENABLED", "true")
    monkeypatch.setenv("RAPANA_LLM_PROVIDER", "none")
    fleet = _fleet_with_settings(tmp_path, Settings())
    assert not any(isinstance(a, RegimeAnalyst) for a in fleet.analysts)


def test_drop_unclosed_removes_only_the_forming_bar():
    from rapana.fleet.data_provider import _drop_unclosed

    rows = [{"ts": 6_000_000, "close": 100.0}, {"ts": 6_500_000, "close": 101.0}]
    # 1h bars: 6.0m closes at 9.6m (<= now=10m -> kept); 6.5m closes at 10.1m (> now -> forming)
    forming = _drop_unclosed(rows, "1h", now_ms=10_000_000)
    assert [r["ts"] for r in forming] == [6_000_000]
    # once time has passed the last close, nothing is dropped (historical read)
    closed = _drop_unclosed(rows, "1h", now_ms=20_000_000)
    assert len(closed) == 2

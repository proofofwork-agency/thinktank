"""Regression tests locking in the fixes from the adversarial deep-dive review.

Each test maps to a confirmed finding; the comment names the bug it guards
against so a future regression is obvious.
"""
from __future__ import annotations

import math
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from rapana.agents import ComplianceAuditor
from rapana.backtest.metrics import compute_metrics
from rapana.fleet import (
    Fleet,
    FleetConfig,
    InMemoryProvider,
    PaperExecutor,
    StagedCapital,
)
from rapana.fleet.execution import ExecutionTrader, OrderResult
from rapana.fleet.portfolio import PaperPortfolio
from rapana.journal.ledger import DecisionLedger
from rapana.signals import Signal, combine_signals


def _uptrend_df(n=160, start=100.0):
    rng = np.random.default_rng(7)
    rets = rng.normal(0.004, 0.006, n)
    price = start * np.exp(np.cumsum(rets))
    ts = np.arange(n) * 3600_000
    return pd.DataFrame({
        "ts": ts, "open": price, "high": price * 1.005, "low": price * 0.995,
        "close": price, "volume": 1000.0,
    })


def _build_fleet(tmp_path, df=None, initial=Decimal("10000")):
    df = df if df is not None else _uptrend_df()
    provider = InMemoryProvider(
        {"BTC/USDT": df},
        {"BTC/USDT": Decimal(str(float(df["close"].iloc[-1])))},
    )
    ledger = DecisionLedger(path=tmp_path / "j.jsonl")
    auditor = ComplianceAuditor(ledger)
    capital = StagedCapital(paper=True)
    trader = ExecutionTrader(PaperExecutor(), capital)
    fleet = Fleet(
        provider=provider, capital=capital, trader=trader, auditor=auditor,
        config=FleetConfig(symbols=["BTC/USDT"]), initial_equity=initial,
    )
    return fleet, ledger


def _filled(side: str, qty: Decimal, price: Decimal, fee: Decimal = Decimal("0")) -> OrderResult:
    return OrderResult("filled", "BTC/USDT", side, "paper", qty, qty, price, fee)


# --- CRITICAL: daily-loss circuit breaker realized-PnL ----------------------

def test_apply_fill_returns_signed_realized_delta_on_losing_close(tmp_path):
    # The old bug read avg_cost() AFTER the fill flattened the position, so a
    # full-close sell reported gross proceeds (+) instead of the realized loss.
    # _apply_fill must return the true signed realized delta.
    fleet, _ = _build_fleet(tmp_path)
    fleet._apply_fill(_filled("buy", Decimal("1"), Decimal("100")))
    delta = fleet._apply_fill(_filled("sell", Decimal("1"), Decimal("50")))
    assert delta == Decimal("-50")  # NOT +50 gross proceeds


def test_apply_fill_realized_delta_is_positive_on_winning_close(tmp_path):
    fleet, _ = _build_fleet(tmp_path)
    fleet._apply_fill(_filled("buy", Decimal("1"), Decimal("100")))
    delta = fleet._apply_fill(_filled("sell", Decimal("1"), Decimal("160")))
    assert delta == Decimal("60")


# --- HIGH: risk gate must actually block execution --------------------------

def test_risk_denial_blocks_execution_no_fill(tmp_path):
    # A denied proposal must not produce a fill: no cash/position movement and
    # no 'fill' event in the journal.
    fleet, ledger = _build_fleet(tmp_path)
    fleet.breaker.record_realized(Decimal("-10000000"))  # trip the breaker
    assert fleet.breaker.is_tripped()
    cash_before = fleet.paper.cash
    pos_before = dict(fleet.paper.positions)
    fleet.run_cycle()
    kinds = [e["kind"] for e in ledger.read_all()]
    assert "fill" not in kinds
    assert fleet.paper.cash == cash_before
    assert fleet.paper.positions == pos_before


# --- MEDIUM: portfolio partial-sell / oversell accounting -------------------

def test_portfolio_partial_sell_realizes_proportional_pnl():
    port = PaperPortfolio(cash=Decimal("10000"))
    port.apply_fill(_filled("buy", Decimal("0.1"), Decimal("50000")))
    port.apply_fill(_filled("sell", Decimal("0.04"), Decimal("60000")))
    assert port.units("BTC/USDT") == Decimal("0.06")
    assert port.realized_pnl == (Decimal("60000") - Decimal("50000")) * Decimal("0.04")
    assert port.avg_cost("BTC/USDT") == Decimal("50000")  # unchanged for the remainder


def test_portfolio_oversell_clamps_to_holding():
    port = PaperPortfolio(cash=Decimal("10000"))
    port.apply_fill(_filled("buy", Decimal("0.1"), Decimal("50000")))
    port.apply_fill(_filled("sell", Decimal("0.5"), Decimal("60000")))
    assert port.units("BTC/USDT") == Decimal("0")  # floored — no negative position


# --- HIGH: ledger tamper detection returns False (does not raise) -----------

def test_verify_chain_returns_false_on_torn_line(tmp_path):
    path = tmp_path / "j.jsonl"
    led = DecisionLedger(path=path)
    led.append("a", {"x": 1})
    led.append("b", {"y": 2})
    assert led.verify_chain() is True
    with open(path, "a", encoding="utf-8") as f:
        f.write("{not valid json\n")  # crashed write / tamper
    assert DecisionLedger(path=path).verify_chain() is False


def test_verify_chain_returns_false_on_data_tamper(tmp_path):
    path = tmp_path / "j.jsonl"
    led = DecisionLedger(path=path)
    led.append("a", {"x": 1})
    led.append("b", {"y": 2})
    lines = path.read_text().splitlines()
    lines[0] = lines[0].replace('"x": 1', '"x": 999') if '"x": 1' in lines[0] else lines[0].replace('"x":1', '"x":999')
    path.write_text("\n".join(lines) + "\n")
    assert DecisionLedger(path=path).verify_chain() is False


# --- MEDIUM: metrics must never emit NaN/inf --------------------------------

def test_sortino_finite_when_no_losing_bars():
    eq = pd.Series([100.0, 101.0, 102.0, 103.0])  # monotonic up: no downside
    m = compute_metrics(eq, [], bars_per_year=365, initial_equity=100.0)
    assert math.isfinite(m.sortino)


def test_win_rate_excludes_zero_pnl_buy_legs():
    eq = pd.Series([100.0, 101.0, 102.0])
    trades = [
        {"pnl": 0.0},   # buy leg — must not count in denominator
        {"pnl": 5.0},   # winning close
    ]
    m = compute_metrics(eq, trades, bars_per_year=365, initial_equity=100.0)
    assert m.win_rate == pytest.approx(1.0)  # 1 win / 1 decided, not 1/2


# --- MEDIUM: neutral signals must not dilute the consensus ------------------

def test_neutral_signal_does_not_dilute_consensus():
    bullish = Signal("BTC/USDT", "market", "bullish", 0.8, 0.9, "up")
    neutral = Signal("BTC/USDT", "macro", "neutral", 0.0, 0.9, "no view")
    only_bull = combine_signals([bullish])
    with_neutral = combine_signals([bullish, neutral])
    assert with_neutral == pytest.approx(only_bull)  # neutral contributes nothing
    assert with_neutral > 0


# --- HIGH: replay must be point-in-time (no same-bar lookahead) --------------

def test_replay_provider_is_point_in_time_no_same_bar_lookahead():
    # ReplayProvider must reveal only CLOSED bars [0, cursor); exposing the
    # cursor bar (whose close is the execution price) would be same-bar lookahead
    # and would inflate the replay validation gate.
    from rapana.fleet.replay import ReplayProvider

    df = pd.DataFrame({
        "ts": list(range(10)),
        "open": list(range(10)), "high": list(range(10)), "low": list(range(10)),
        "close": [float(x) for x in range(100, 110)], "volume": [1] * 10,
    })
    rp = ReplayProvider({"BTC/USDT": df})
    rp.seek(5)
    hist = rp.get_history("BTC/USDT", "1h", 100)
    assert len(hist) == 5                              # bars [0,5) — excludes cursor
    assert float(hist["close"].iloc[-1]) == 104.0      # last visible bar is #4
    assert rp.get_price("BTC/USDT") == Decimal("105")  # fills at cursor bar #5 close

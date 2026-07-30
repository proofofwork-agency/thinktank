"""Tests for the funding-rate / market-neutral carry track (C1 data + C2 backtest)."""
from __future__ import annotations

import pytest

import rapana.mexc.client as client_mod
from rapana.backtest.carry import (
    DEFAULT_POLICIES,
    CarryConfig,
    CarryPolicy,
    infer_intervals_per_year,
    simulate_carry,
    validate_carry_config,
    validate_carry_grid,
)
from rapana.data.ingest import FundingIngester
from rapana.data.store import TimeSeriesStore
from rapana.mexc.client import MexcFuturesClient, to_perp_symbol

INTERVAL = 8 * 3600 * 1000  # MEXC funds every 8h
BASE = 1_600_000_000_000


def _funding(rates: list[float], base: int = BASE) -> list[dict[str, float]]:
    return [{"ts": base + i * INTERVAL, "funding_rate": r} for i, r in enumerate(rates)]


# ---- symbol mapping -------------------------------------------------------
def test_to_perp_symbol_maps_spot_and_passes_through():
    assert to_perp_symbol("BTC/USDT") == "BTC/USDT:USDT"
    assert to_perp_symbol("eth/usdt") == "ETH/USDT:USDT"
    assert to_perp_symbol("BTC/USDT:USDT") == "BTC/USDT:USDT"  # already a perp


# ---- store: funding table -------------------------------------------------
def test_store_funding_roundtrip(tmp_path):
    store = TimeSeriesStore(tmp_path / "f.db")
    rows = _funding([0.0001, 0.0002, -0.0001])
    assert store.upsert_funding("BTC/USDT:USDT", rows) == 3
    got = store.fetch_funding_range("btc/usdt:usdt")  # case-insensitive
    assert len(got) == 3
    assert got[0]["funding_rate"] == 0.0001
    assert got[-1]["funding_rate"] == -0.0001  # ascending by ts
    assert store.last_funding_timestamp("BTC/USDT:USDT") == rows[-1]["ts"]
    assert store.funding_symbols() == ["BTC/USDT:USDT"]


def test_store_funding_idempotent_and_ranged(tmp_path):
    store = TimeSeriesStore(tmp_path / "f.db")
    rows = _funding([0.0001, 0.0002, 0.0003])
    store.upsert_funding("BTC/USDT:USDT", rows)
    store.upsert_funding("BTC/USDT:USDT", rows)  # duplicate ts -> replace
    assert len(store.fetch_funding_range("BTC/USDT:USDT")) == 3
    mid = rows[1]["ts"]
    assert [r["ts"] for r in store.fetch_funding_range("BTC/USDT:USDT", since=mid)] == \
        [rows[1]["ts"], rows[2]["ts"]]


# ---- futures client: paginated funding history ----------------------------
class FakeSwapExchange:
    """Minimal fake ccxt.mexc swap returning a fixed funding history."""

    def __init__(self, params):
        self.params = params
        self.markets = {"BTC/USDT:USDT": {"symbol": "BTC/USDT:USDT"}}
        self.history = [
            {"timestamp": BASE + i * INTERVAL, "fundingRate": 0.0001 + i * 1e-6}
            for i in range(5)
        ]

    def load_markets(self):
        return self.markets

    def fetch_funding_rate_history(self, symbol, since=None, limit=200):
        rows = self.history
        if since is not None:
            rows = [r for r in rows if r["timestamp"] >= since]
        return rows[:limit]


@pytest.fixture
def stub_swap(monkeypatch):
    monkeypatch.setattr(client_mod.ccxt, "mexc", FakeSwapExchange)


def test_futures_client_paginates_funding(stub_swap):
    c = MexcFuturesClient()
    # limit=2 forces multiple pages over the 5-row history; now_ms huge keeps all.
    rows = c.fetch_funding_rate_history(
        "BTC/USDT", since=BASE, limit=2, now_ms=BASE + 10 * INTERVAL
    )
    assert [r["ts"] for r in rows] == [BASE + i * INTERVAL for i in range(5)]
    assert rows[0]["funding_rate"] == pytest.approx(0.0001)


def test_futures_client_drops_unsettled_current_interval(stub_swap):
    c = MexcFuturesClient()
    # now_ms sits between the 3rd and 4th settlement -> only the first 3 are settled.
    now = BASE + 3 * INTERVAL - 1
    rows = c.fetch_funding_rate_history("BTC/USDT", since=BASE, limit=200, now_ms=now)
    assert [r["ts"] for r in rows] == [BASE, BASE + INTERVAL, BASE + 2 * INTERVAL]


# ---- ingester: resumable, perp-keyed --------------------------------------
class FakeFuturesClient:
    def __init__(self, rows):
        self._rows = rows
        self.since_calls: list[int | None] = []

    def fetch_funding_rate_history(self, symbol, *, since=None, until=None,
                                   limit=200, max_pages=None):
        self.since_calls.append(since)
        rows = self._rows
        if since is not None:
            rows = [r for r in rows if r["ts"] >= since]
        return rows


def test_funding_ingester_resumes_from_newest(tmp_path):
    store = TimeSeriesStore(tmp_path / "f.db")
    client = FakeFuturesClient(_funding([0.0001, 0.0002, 0.0003]))
    ing = FundingIngester(client=client, store=store)

    assert ing.ingest_symbol("BTC/USDT") == 3      # maps spot -> perp, stores all
    assert client.since_calls[-1] is None          # first run: no resume cursor
    assert ing.ingest_symbol("BTC/USDT") == 0       # resume past newest -> nothing new
    assert client.since_calls[-1] == BASE + 2 * INTERVAL + 1  # cursor = last + 1
    assert store.funding_symbols() == ["BTC/USDT:USDT"]


# ---- carry simulation: signs, costs, point-in-time ------------------------
def test_simulate_always_on_receives_positive_funding_one_entry_cost():
    cfg = CarryConfig(fee_pct=0.0005, slippage_pct=0.0005, basis_drag_bps=0.0)
    out = simulate_carry([0.0002, 0.0002, 0.0002], threshold=None, cfg=cfg)
    # entry (both legs) charged ONCE on the first interval; then it just rides.
    assert out[0][2] == pytest.approx(0.002)   # cost = 2 * (5bp + 5bp)
    assert out[1][2] == 0.0 and out[2][2] == 0.0
    # short perp RECEIVES positive funding (gross > 0 every held interval).
    assert all(g == pytest.approx(0.0002) for _net, g, _c in out)
    assert out[1][0] == pytest.approx(0.0002)  # net == gross once entered


def test_simulate_short_pays_negative_funding():
    cfg = CarryConfig(fee_pct=0.0, slippage_pct=0.0, basis_drag_bps=0.0)
    out = simulate_carry([-0.0001, -0.0001], threshold=None, cfg=cfg)
    assert all(net == pytest.approx(-0.0001) for net, _g, _c in out)  # short pays


def test_simulate_threshold_is_point_in_time():
    """The hold decision for interval t uses funding settled BEFORE t, never t's own."""
    cfg = CarryConfig(fee_pct=0.0, slippage_pct=0.0, basis_drag_bps=0.0)
    # funding crosses the 1bp threshold only at index 1; we may act no earlier than index 2.
    out = simulate_carry([0.0, 0.0002, 0.0002], threshold=0.0001, cfg=cfg)
    assert out[0][1] == 0.0   # interval 0: no prior funding -> flat
    assert out[1][1] == 0.0   # interval 1: prior funding 0.0 <= 1bp -> still flat
    assert out[2][1] == pytest.approx(0.0002)  # interval 2: prior 2bp > 1bp -> held


def test_simulate_charges_exit_on_flip():
    cfg = CarryConfig(fee_pct=0.0005, slippage_pct=0.0005, basis_drag_bps=0.0)
    # hold (prev>thr) then drop below -> pays an exit on the flip interval.
    out = simulate_carry([0.0002, 0.0002, 0.00005, 0.00005], threshold=0.0001, cfg=cfg)
    # idx2 decides on prev=0.0002>thr -> still held; idx3 decides on prev=0.00005<thr -> exit.
    assert out[3][2] == pytest.approx(0.002) and out[3][1] == 0.0  # exit cost, no funding


def test_simulate_basis_drag_is_a_cost():
    cfg = CarryConfig(fee_pct=0.0, slippage_pct=0.0, basis_drag_bps=1.0)  # 1bp/interval
    out = simulate_carry([0.0003, 0.0003], threshold=None, cfg=cfg)
    assert out[1][0] == pytest.approx(0.0003 - 0.0001)  # net = funding - drag


def test_infer_intervals_per_year_8h():
    ipy = infer_intervals_per_year([r["ts"] for r in _funding([0.0] * 10)])
    assert ipy == pytest.approx(3 * 365, rel=1e-6)  # 8h -> 3/day -> 1095/yr


# ---- carry validation: PASS / FAIL verdict --------------------------------
def test_validate_carry_config_pools_oos():
    rates = [0.0003 + (5e-5 if i % 2 else -5e-5) for i in range(120)]
    cr = validate_carry_config(
        _funding(rates), "BTC/USDT:USDT", CarryPolicy("always", None),
        n_splits=4, warmup=8, cfg=CarryConfig(fee_pct=0, slippage_pct=0),
    )
    assert cr is not None
    assert cr.folds and cr.n_obs >= 2
    assert cr.oos_return > 0          # positive funding, no cost -> profitable
    assert cr.gross_funding > 0
    assert 0.0 <= cr.pct_intervals_positive <= 1.0


def test_validate_carry_grid_passes_on_clean_positive_funding():
    rates = [0.0003 + (5e-5 if i % 2 else -5e-5) for i in range(200)]
    report = validate_carry_grid(
        {"BTC/USDT:USDT": _funding(rates)},
        n_splits=6, warmup=8, cfg=CarryConfig(fee_pct=0, slippage_pct=0),
    )
    assert report.n_trials == len(DEFAULT_POLICIES)
    assert report.best is not None
    assert 0.0 <= report.deflated_sharpe <= 1.0
    assert report.cash_return == 0.0
    assert report.best.oos_return > 0
    assert report.passed is True       # DSR>0.95 AND beats cash
    assert report.passed == (report.is_significant and report.best.oos_return > report.cash_return)


def test_validate_carry_grid_fails_below_honest_cash_floor():
    rates = [0.00015 for _ in range(220)]
    report = validate_carry_grid(
        {"BTC/USDT:USDT": _funding(rates)},
        n_splits=6, warmup=8, cfg=CarryConfig(fee_pct=0, slippage_pct=0),
        cash_return=0.035,
    )
    assert report.cash_return == 0.035
    assert report.best is not None
    assert 0.0 < report.best.oos_return < report.cash_return
    assert report.is_significant is True
    assert report.passed is False


def _by_policy(report, name):
    return next(c for c in report.configs if c.policy == name)


def test_validate_carry_grid_fails_on_negative_funding():
    # Bear-market funding: shorts PAY. Harvesting it (always-on) loses; a
    # funding-gated policy correctly dodges to flat (= cash). Neither BEATS cash.
    rates = [-0.0002 + (5e-5 if i % 2 else -5e-5) for i in range(200)]
    report = validate_carry_grid(
        {"BTC/USDT:USDT": _funding(rates)},
        n_splits=6, warmup=8, cfg=CarryConfig(fee_pct=0, slippage_pct=0),
    )
    assert report.best is not None
    assert _by_policy(report, "always").oos_return < 0      # harvesting loses
    assert report.best.oos_return <= report.cash_return     # best does not beat cash
    assert report.passed is False                           # -> no-go


def test_validate_carry_grid_fails_when_costs_exceed_funding():
    # Thin positive funding (0.5bp) eaten alive by a heavy 2bp/interval basis drag.
    rates = [0.00005 for _ in range(200)]
    report = validate_carry_grid(
        {"BTC/USDT:USDT": _funding(rates)},
        n_splits=6, warmup=8,
        cfg=CarryConfig(fee_pct=0.0002, slippage_pct=0.0002, basis_drag_bps=2.0),
    )
    assert report.best is not None
    assert _by_policy(report, "always").oos_return < 0      # 2bp drag > 0.5bp funding
    assert report.best.oos_return <= report.cash_return     # nothing beats cash
    assert report.passed is False

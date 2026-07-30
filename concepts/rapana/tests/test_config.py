from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapana.config import Settings, get_settings


def test_defaults_paper(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RAPANA_AUTOPILOT_PROMOTE_MIN_CYCLES", raising=False)
    monkeypatch.delenv("RAPANA_VOL_TARGET", raising=False)
    monkeypatch.delenv("RAPANA_VOL_LOOKBACK", raising=False)
    s = Settings()
    assert s.env == "paper"
    assert s.is_live is False
    assert s.watch_symbols == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    assert s.benchmark_cash_return == 0.035
    assert s.autopilot_promote_psr == 0.95
    assert s.autopilot_promote_min_cycles == 500
    assert s.vol_target is None
    assert s.vol_lookback == 20
    assert s.execution_mode == "market"
    assert s.maker_poll_timeout_sec == 2.0
    assert s.maker_poll_interval_sec == 0.25
    assert s.maker_price_peg == "passive_touch"
    assert s.maker_price_offset_ticks == 0
    assert s.maker_fee_pct == 0.0005
    assert s.paper_maker_offset_bps == 2.0
    assert s.paper_maker_lifetime_bars == 1
    assert s.paper_maker_fill_fraction == 0.0


def test_capital_budget_clamps_max_notional(tmp_path, monkeypatch):
    """$50 micro budget must never allow the $250 default order size."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_CAPITAL_BUDGET_USD", "50")
    monkeypatch.setenv("RAPANA_RISK_MAX_NOTIONAL_PER_ORDER", "250")
    s = Settings()
    assert s.capital_budget_usd == 50.0
    assert s.effective_max_notional_per_order == 47.5
    from rapana.risk.guardrails import RiskPolicy

    assert float(RiskPolicy.from_settings(s).max_notional_per_order) == 47.5


def test_env_validation_rejects_bad(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_ENV", "moon")
    with pytest.raises(ValidationError):
        Settings()


def test_env_validation_accepts_live(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_ENV", "live")
    s = Settings()
    assert s.is_live is True


def test_cash_benchmark_threads_to_cash_validator_cli_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_BENCHMARK_CASH_RETURN", "0.042")
    get_settings.cache_clear()
    try:
        from rapana.cli import build_parser

        parser = build_parser()
        carry = parser.parse_args(["validate-carry"])
        funding = parser.parse_args(["validate-funding-spike"])
        assert carry.cash_return == 0.042
        assert funding.cash_return == 0.042
    finally:
        get_settings.cache_clear()


def test_vol_target_empty_string_means_off(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_VOL_TARGET", "")
    s = Settings()
    assert s.vol_target is None


def test_execution_mode_is_safe_by_default_on_bad_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_EXECUTION_MODE", "taker-fallback")
    monkeypatch.setenv("RAPANA_MAKER_FEE_PCT", "-1")
    monkeypatch.setenv("RAPANA_PAPER_MAKER_OFFSET_BPS", "-2")
    monkeypatch.setenv("RAPANA_PAPER_MAKER_LIFETIME_BARS", "0")
    monkeypatch.setenv("RAPANA_PAPER_MAKER_FILL_FRACTION", "2")
    s = Settings()
    assert s.execution_mode == "market"
    assert s.maker_fee_pct == 0.0
    assert s.paper_maker_offset_bps == 0.0
    assert s.paper_maker_lifetime_bars == 1
    assert s.paper_maker_fill_fraction == 1.0

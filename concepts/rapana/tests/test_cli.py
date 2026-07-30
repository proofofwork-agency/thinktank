from __future__ import annotations

from rapana.config import get_settings


def test_replay_maker_eval_flag_is_off_by_default():
    from rapana.cli import build_parser

    parser = build_parser()

    assert parser.parse_args(["replay", "--synthetic"]).maker_eval is False
    assert parser.parse_args(["replay", "--synthetic", "--maker-eval"]).maker_eval is True


def test_replay_maker_eval_runs_paired_report(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_WATCH_SYMBOLS", "BTC/USDT")
    monkeypatch.setenv("RAPANA_RISK_MAX_ORDERS_PER_MIN", "100")
    get_settings.cache_clear()
    try:
        from rapana.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "replay",
            "--synthetic",
            "--limit",
            "20",
            "--warmup",
            "5",
            "--maker-eval",
        ])

        assert args.func(args) == 0
        out = capsys.readouterr().out
        assert "=== Paper Maker Eval: paired replay ===" in out
        assert "net_execution_delta" in out
        assert "maker_fill_rate" in out
        assert "paper_maker_fill_fraction" in out
        assert "synthetic paper_maker_fill_fraction knob cannot justify live maker mode" in out
    finally:
        get_settings.cache_clear()


def test_replay_forces_live_feeds_off_for_no_lookahead(tmp_path, monkeypatch):
    # Even with RAPANA_FEEDS_ENABLED=true, the replay path must build bare neutral
    # analysts so a live "now" feed reading can never leak into a past bar.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_FEEDS_ENABLED", "true")
    monkeypatch.setenv("RAPANA_WATCH_SYMBOLS", "BTC/USDT")
    get_settings.cache_clear()
    try:
        from rapana.cli import _build_paper_fleet
        from rapana.config import get_settings as _get

        settings = _get()
        assert settings.feeds_enabled is True
        fleet, _runner, _store = _build_paper_fleet(settings, allow_live_feeds=False)
        sent = next(a for a in fleet.analysts if type(a).__name__ == "SentimentAnalyst")
        macro = next(a for a in fleet.analysts if type(a).__name__ == "MacroAnalyst")
        assert sent.sentiment_fn is None
        assert macro.macro_fn is None
    finally:
        get_settings.cache_clear()


def test_forward_paper_run_wires_feeds_when_enabled(tmp_path, monkeypatch):
    # Counterpoint: the forward paper-run path wires feeds when enabled.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_FEEDS_ENABLED", "true")
    monkeypatch.setenv("RAPANA_WATCH_SYMBOLS", "BTC/USDT")
    get_settings.cache_clear()
    try:
        from rapana.cli import _build_paper_fleet
        from rapana.config import get_settings as _get

        fleet, _runner, _store = _build_paper_fleet(_get(), allow_live_feeds=True)
        sent = next(a for a in fleet.analysts if type(a).__name__ == "SentimentAnalyst")
        macro = next(a for a in fleet.analysts if type(a).__name__ == "MacroAnalyst")
        assert sent.sentiment_fn is not None
        assert macro.macro_fn is not None
    finally:
        get_settings.cache_clear()


def test_replay_excludes_regime_analyst_for_no_lookahead(tmp_path, monkeypatch):
    # Even with the LLM regime analyst enabled, the replay path must build bare
    # analysts so a live LLM "now" read can never leak into a past bar.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RAPANA_LLM_REGIME_ENABLED", "true")
    monkeypatch.setenv("RAPANA_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("RAPANA_LLM_BASE_URL", "http://localhost:9999/v1")
    monkeypatch.setenv("RAPANA_LLM_MODEL", "m")
    monkeypatch.setenv("RAPANA_WATCH_SYMBOLS", "BTC/USDT")
    get_settings.cache_clear()
    try:
        from rapana.agents import RegimeAnalyst
        from rapana.cli import _build_paper_fleet
        from rapana.config import get_settings as _get

        fleet, _runner, _store = _build_paper_fleet(_get(), allow_live_feeds=False)
        assert not any(isinstance(a, RegimeAnalyst) for a in fleet.analysts)
    finally:
        get_settings.cache_clear()

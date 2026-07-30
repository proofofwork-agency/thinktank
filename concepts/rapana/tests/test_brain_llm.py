from __future__ import annotations

import json

from rapana.agents.brain import (
    DeterministicBrain,
    OpenAICompatibleBrain,
    build_brain,
)
from rapana.agents.researchers import BullResearcher
from rapana.config import Settings
from rapana.signals import Signal


class _FakeResponse:
    """Minimal context-manager response standing in for urllib's HTTPResponse."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _patch_urlopen(monkeypatch, payload=None, exc=None):
    """Monkeypatch urllib.request.urlopen in brain.py and capture the Request."""
    captured: dict = {}

    def fake_urlopen(req, *args, **kwargs):
        captured["req"] = req
        if exc is not None:
            raise exc
        return _FakeResponse(payload or {})

    monkeypatch.setattr(
        "rapana.agents.brain.urllib.request.urlopen", fake_urlopen
    )
    return captured


def test_openai_compatible_brain_parses_content(monkeypatch):
    captured = _patch_urlopen(
        monkeypatch,
        payload={"choices": [{"message": {"content": " hello "}}]},
    )
    brain = OpenAICompatibleBrain(
        base_url="http://x/v1", api_key="sk", model="m"
    )
    assert brain.reason("hi") == "hello"
    assert "req" in captured


def test_openai_compatible_brain_sends_bearer_when_key(monkeypatch):
    captured = _patch_urlopen(
        monkeypatch,
        payload={"choices": [{"message": {"content": "ok"}}]},
    )
    brain = OpenAICompatibleBrain(
        base_url="http://x/v1", api_key="sk-test", model="m"
    )
    brain.reason("hi")
    req = captured["req"]
    assert req.get_header("Authorization") == "Bearer sk-test"


def test_openai_compatible_brain_omits_auth_without_key(monkeypatch):
    captured = _patch_urlopen(
        monkeypatch,
        payload={"choices": [{"message": {"content": "ok"}}]},
    )
    brain = OpenAICompatibleBrain(
        base_url="http://x/v1", api_key=None, model="m"
    )
    brain.reason("hi")
    req = captured["req"]
    assert req.get_header("Authorization") is None


def test_openai_compatible_brain_posts_to_chat_completions(monkeypatch):
    captured = _patch_urlopen(
        monkeypatch,
        payload={"choices": [{"message": {"content": "ok"}}]},
    )
    brain = OpenAICompatibleBrain(
        base_url="http://x/v1", api_key="sk", model="m"
    )
    brain.reason("hi")
    req = captured["req"]
    assert req.full_url.endswith("/chat/completions")
    assert req.get_method() == "POST"


def test_openai_compatible_brain_fail_soft(monkeypatch):
    _patch_urlopen(monkeypatch, exc=OSError("boom"))
    brain = OpenAICompatibleBrain(
        base_url="http://x/v1", api_key="sk", model="m"
    )
    out = brain.reason("hi")
    assert out.startswith("(brain error:")


def test_build_brain_deterministic_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = build_brain(Settings())
    assert isinstance(brain, DeterministicBrain)


def test_build_brain_openrouter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s = Settings(
        RAPANA_LLM_PROVIDER="openrouter",
        RAPANA_LLM_API_KEY="sk",
        RAPANA_LLM_MODEL="m",
    )
    brain = build_brain(s)
    assert isinstance(brain, OpenAICompatibleBrain)
    assert brain.base_url == "https://openrouter.ai/api/v1"


def test_build_brain_openrouter_no_key_falls_back(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = build_brain(Settings(RAPANA_LLM_PROVIDER="openrouter"))
    assert isinstance(brain, DeterministicBrain)


def test_build_brain_ollama(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = build_brain(Settings(RAPANA_LLM_PROVIDER="ollama"))
    assert isinstance(brain, OpenAICompatibleBrain)
    assert brain.base_url == "http://localhost:11434/v1"


def test_build_brain_local(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s = Settings(
        RAPANA_LLM_PROVIDER="local",
        RAPANA_LLM_BASE_URL="http://x:1234/v1",
        RAPANA_LLM_MODEL="m",
    )
    brain = build_brain(s)
    assert isinstance(brain, OpenAICompatibleBrain)
    assert brain.base_url == "http://x:1234/v1"


def test_build_brain_local_without_base_url_falls_back(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = build_brain(Settings(RAPANA_LLM_PROVIDER="local"))
    assert isinstance(brain, DeterministicBrain)


def test_build_brain_unknown_provider_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = build_brain(Settings(RAPANA_LLM_PROVIDER="garbage"))
    assert isinstance(brain, DeterministicBrain)


def test_deterministic_brain_does_not_change_decisions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    signals = [Signal("BTC/USDT", "market", "bullish", 0.7, 0.9, "up")]

    none_bull = BullResearcher(brain=None)
    none_thesis = none_bull.argue(signals, "BTC/USDT")
    assert none_thesis.commentary == ""

    det_bull = BullResearcher(brain=DeterministicBrain())
    det_thesis = det_bull.argue(signals, "BTC/USDT")
    # The brain may annotate commentary, but it must never change the decision.
    assert det_thesis.recommended == none_thesis.recommended
    assert det_thesis.score == none_thesis.score

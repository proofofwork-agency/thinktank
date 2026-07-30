from __future__ import annotations

from rapana.agents.brain import CallableBrain, DeterministicBrain, default_brain
from rapana.agents.researchers import BullResearcher
from rapana.signals import Signal


def test_default_brain_is_deterministic():
    b = default_brain()
    assert isinstance(b, DeterministicBrain)
    assert b.reason("anything") == "deterministic analysis (no LLM)"


def test_callable_brain():
    b = CallableBrain(lambda prompt: f"ECHO: {prompt[:5]}")
    assert b.reason("hello world").startswith("ECHO: hello")


def test_callable_brain_failure_safe():
    def boom(prompt):
        raise RuntimeError("x")

    b = CallableBrain(boom)
    out = b.reason("p")
    assert "brain error" in out


def test_brain_annotates_thesis_without_changing_score():
    bull = BullResearcher(brain=CallableBrain(lambda p: "LLM THESIS", name="test"))
    signals = [Signal("BTC/USDT", "market", "bullish", 0.7, 0.9, "up")]
    thesis = bull.argue(signals, "BTC/USDT")
    assert thesis.commentary == "LLM THESIS"
    # numeric recommendation is unchanged by the brain
    assert thesis.recommended == "buy"
    assert thesis.score > 0


def test_no_brain_leaves_empty_commentary():
    bull = BullResearcher()
    signals = [Signal("BTC/USDT", "market", "bullish", 0.7, 0.9, "up")]
    thesis = bull.argue(signals, "BTC/USDT")
    assert thesis.commentary == ""

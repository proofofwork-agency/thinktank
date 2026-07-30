from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

from rapana.agents.brain import CallableBrain, DeterministicBrain
from rapana.agents.regime import RegimeAnalyst
from rapana.fleet import InMemoryProvider


def _provider(n: int = 60, start: float = 100.0) -> InMemoryProvider:
    rng = np.random.default_rng(0)
    closes = start * np.exp(np.cumsum(rng.normal(0.001, 0.01, n)))
    ts = [i * 3_600_000 for i in range(n)]
    df = pd.DataFrame({
        "ts": ts, "open": closes, "high": closes, "low": closes,
        "close": closes, "volume": [1000.0] * n,
    })
    return InMemoryProvider(
        {"BTC/USDT": df}, {"BTC/USDT": Decimal(str(float(closes[-1])))}
    )


def test_neutral_with_deterministic_brain():
    sig = RegimeAnalyst(DeterministicBrain()).analyze("BTC/USDT", _provider())
    assert sig.direction == "neutral"
    assert sig.strength == 0.0
    assert sig.source == "llm_regime"


def test_bullish_parsed():
    a = RegimeAnalyst(CallableBrain(lambda p: "REGIME: bullish\nCONFIDENCE: 0.7"))
    sig = a.analyze("BTC/USDT", _provider())
    assert sig.direction == "bullish"
    assert sig.confidence == 0.7
    assert sig.strength == 0.7


def test_bearish_parsed():
    a = RegimeAnalyst(CallableBrain(lambda p: "regime: bearish\nconfidence: 0.6"))
    sig = a.analyze("BTC/USDT", _provider())
    assert sig.direction == "bearish"
    assert sig.strength == -0.6
    assert sig.confidence == 0.6


def test_neutral_on_unparseable():
    a = RegimeAnalyst(CallableBrain(lambda p: "the market is uncertain today"))
    sig = a.analyze("BTC/USDT", _provider())
    assert sig.direction == "neutral"
    assert sig.strength == 0.0


def test_confidence_clamped_to_unit():
    a = RegimeAnalyst(CallableBrain(lambda p: "REGIME: bullish\nCONFIDENCE: 5.0"))
    sig = a.analyze("BTC/USDT", _provider())
    assert sig.confidence == 1.0
    assert sig.strength == 1.0


def test_brain_error_fails_soft_to_neutral():
    def boom(_p):
        raise RuntimeError("api down")

    sig = RegimeAnalyst(CallableBrain(boom)).analyze("BTC/USDT", _provider())
    assert sig.direction == "neutral"

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from rapana.logging import get_logger
from rapana.signals import Signal

log = get_logger(__name__)


@dataclass
class SignalRecord:
    ts: int
    symbol: str
    source: str
    direction: str
    strength: float
    price: Decimal


@dataclass
class SourceStats:
    correct: int = 0
    total: int = 0
    profit_sum: float = 0.0  # signed outcome of resolved signals

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.5

    def as_dict(self) -> dict:
        return {
            "correct": self.correct,
            "total": self.total,
            "accuracy": round(self.accuracy, 3),
            "avg_outcome": round(self.profit_sum / self.total, 4) if self.total else 0.0,
        }


class ReflectionMemory:
    """The reflection loop: learns which analyst sources actually predict price.

    Each emitted signal is recorded with its price. After `horizon_ms`, the
    outcome (price change since the signal) is resolved and the source's
    hit-rate is updated. The Portfolio Manager then weights current signals by
    each source's learned accuracy — analysts that keep being right gain
    influence, those that don't fade. Deterministic and fully replayable.
    """

    def __init__(
        self,
        horizon_ms: int = 24 * 3_600_000,
        min_weight: float = 0.3,
        max_weight: float = 1.5,
        shrink: float = 5.0,
        max_pending_age_ms: int | None = None,
    ) -> None:
        self.horizon_ms = horizon_ms
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.shrink = shrink
        # Records that mature but stay unpriceable (missing/delisted symbol) are
        # dropped once they exceed this age, so `pending` can't grow unbounded.
        # Defaults to 3x the scoring horizon: slack for late data, bounded after.
        self.max_pending_age_ms = (
            max_pending_age_ms if max_pending_age_ms is not None else horizon_ms * 3
        )
        self.pending: list[SignalRecord] = []
        self.stats: dict[str, SourceStats] = defaultdict(SourceStats)

    def observe(self, signal: Signal, price: Decimal, ts: int) -> None:
        if signal.direction == "neutral" or price <= 0:
            return
        self.pending.append(
            SignalRecord(ts, signal.symbol, signal.source, signal.direction, signal.strength, price)
        )

    def resolve(self, prices: dict[str, Decimal], now_ts: int) -> int:
        """Score pending signals whose horizon has elapsed. Returns count resolved."""
        still_pending: list[SignalRecord] = []
        resolved = 0
        dropped = 0
        for rec in self.pending:
            age = now_ts - rec.ts
            if age < self.horizon_ms:
                still_pending.append(rec)
                continue
            price_now = prices.get(rec.symbol, Decimal("0"))
            if price_now <= 0 or rec.price <= 0:
                # Matured but unpriceable. Keep briefly in case data is late, but
                # drop past the staleness bound so missing/delisted symbols don't
                # accumulate pending records forever.
                if age < self.max_pending_age_ms:
                    still_pending.append(rec)
                else:
                    dropped += 1
                continue
            outcome = float((price_now - rec.price) / rec.price)
            predicted_up = rec.direction == "bullish"
            correct = (outcome > 0) == predicted_up
            stats = self.stats[rec.source]
            stats.total += 1
            if correct:
                stats.correct += 1
            stats.profit_sum += outcome * (1 if predicted_up else -1)
            resolved += 1
        self.pending = still_pending
        if resolved or dropped:
            log.info("memory_resolved", count=resolved, dropped=dropped, pending=len(self.pending))
        return resolved

    def weight(self, source: str) -> float:
        stats = self.stats.get(source)
        if stats is None or stats.total < self.shrink:
            return 1.0  # neutral until we have enough evidence
        # Bayesian-shrink accuracy toward 0.5, then map: acc=0.5 -> weight 1.0
        acc = (stats.correct + self.shrink * 0.5) / (stats.total + self.shrink)
        w = acc / 0.5  # 0.5 -> 1.0, 1.0 -> 2.0, 0.0 -> 0.0
        return max(self.min_weight, min(self.max_weight, w))

    def weights(self, sources: list[str]) -> dict[str, float]:
        return {s: self.weight(s) for s in sources}

    def analytics(self) -> dict[str, dict]:
        return {s: stats.as_dict() for s, stats in self.stats.items()}

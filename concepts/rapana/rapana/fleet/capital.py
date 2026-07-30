from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rapana.logging import get_logger

log = get_logger(__name__)


@dataclass
class StagedCapital:
    """Staged live-capital deployment: 1% -> 5% -> 25% -> 100%.

    Caps the fraction of total equity the fleet may deploy. Stage advances are
    human-approved (Phase 3 gate). In paper mode the fleet uses stage 1.0 so the
    full simulated balance trades, but `available()` still respects the cap so
    live promotion is a config flip, not a behaviour change.
    """

    stages: tuple[float, ...] = (0.01, 0.05, 0.25, 1.0)
    stage_index: int = 0
    paper: bool = True

    @property
    def fraction(self) -> float:
        # Paper mode trades the full simulated balance so strategies are
        # exercised at realistic size; the staged cap only governs LIVE, where
        # promotion to a larger fraction is a human-approved step.
        if self.paper:
            return 1.0
        return max(self.stages[0], self.stages[self.stage_index])

    def available(self, equity: Decimal) -> Decimal:
        return (Decimal(str(self.fraction)) * equity).quantize(Decimal("0.000001"))

    def can_trade(self, notional: Decimal, equity: Decimal) -> bool:
        return notional <= self.available(equity)

    def advance(self) -> float:
        """Human-approved bump to the next stage. Returns new fraction."""
        if self.stage_index < len(self.stages) - 1:
            self.stage_index += 1
        log.warning("capital_stage_advanced", stage_index=self.stage_index, fraction=self.fraction)
        return self.fraction

    def reset(self) -> None:
        self.stage_index = 0

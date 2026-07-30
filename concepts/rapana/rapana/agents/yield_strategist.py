from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from rapana.agents.base import Analyst
from rapana.signals import Signal

if TYPE_CHECKING:
    from rapana.fleet.data_provider import DataProvider


@dataclass(frozen=True)
class IdleCashDrag:
    """Opportunity cost of leaving stable cash idle instead of earning the benchmark."""

    idle_cash: Decimal
    annual_return: Decimal
    annual_drag: Decimal
    period_drag: Decimal
    periods_per_year: int


def estimate_idle_cash_drag(
    idle_cash: Decimal,
    annual_cash_return: float | Decimal,
    *,
    periods_per_year: int = 365,
) -> IdleCashDrag:
    """Estimate benchmark yield foregone by idle cash.

    This is telemetry only: it does not move capital or emit trade instructions.
    """
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be > 0")
    cash = max(Decimal("0"), idle_cash)
    rate = Decimal(str(annual_cash_return))
    annual = cash * rate
    return IdleCashDrag(
        idle_cash=cash,
        annual_return=rate,
        annual_drag=annual,
        period_drag=annual / Decimal(periods_per_year),
        periods_per_year=periods_per_year,
    )


class YieldStrategist(Analyst):
    """Staking / lending / LP yield evaluator.

    Evaluates whether idle capital earns more in yield than in a spot trade.
    Inject `yield_fn(symbol) -> (yield_score[-1..1], confidence)`. Neutral by
    default (no DeFi/lending feed wired).
    """

    role = "yield_strategist"

    def __init__(
        self,
        yield_fn: Callable[[str], tuple[float, float]] | None = None,
        *,
        idle_cash_fn: Callable[[], Decimal] | None = None,
        benchmark_cash_return: float = 0.035,
    ) -> None:
        self.yield_fn = yield_fn
        self.idle_cash_fn = idle_cash_fn
        self.benchmark_cash_return = benchmark_cash_return

    def analyze(self, symbol: str, provider: DataProvider) -> Signal:
        if self.yield_fn is None:
            extras = {}
            rationale = "no yield feed configured"
            if self.idle_cash_fn is not None:
                drag = estimate_idle_cash_drag(
                    self.idle_cash_fn(), self.benchmark_cash_return
                )
                extras = {
                    "idle_cash": str(drag.idle_cash),
                    "benchmark_cash_return": float(drag.annual_return),
                    "idle_cash_drag_annual": str(drag.annual_drag),
                    "idle_cash_drag_daily": str(drag.period_drag),
                }
                rationale = (
                    f"idle cash drag annual={drag.annual_drag:.2f} "
                    f"at {drag.annual_return:.2%}"
                )
            return Signal(symbol, "yield", "neutral", 0.0, 0.0, rationale, extras=extras)
        score, confidence = self.yield_fn(symbol)
        direction = "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral"
        return Signal(symbol, "yield", direction, score, confidence, f"yield score={score:.2f}")

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from rapana.agents.researchers import Thesis
from rapana.risk.guardrails import RiskDecision, TradeProposal
from rapana.signals import Signal


@dataclass
class SymbolState:
    """Per-symbol blackboard slice for one decision cycle."""

    symbol: str
    price: Decimal = Decimal("0")
    ref_price: Decimal = Decimal("0")
    signals: list[Signal] = field(default_factory=list)
    bull: Thesis | None = None
    bear: Thesis | None = None
    proposal: TradeProposal | None = None
    risk_decision: RiskDecision | None = None
    fill: dict | None = None


@dataclass
class FleetState:
    """Top-level blackboard shared across agents during a cycle."""

    cycle: int = 0
    equity: Decimal = Decimal("0")
    cash: Decimal = Decimal("0")
    positions: dict[str, Decimal] = field(default_factory=dict)   # base-asset units
    symbols: dict[str, SymbolState] = field(default_factory=dict)
    digest: str = ""

    def position_value(self, symbol: str) -> Decimal:
        ss = self.symbols.get(symbol)
        price = ss.price if ss else Decimal("0")
        return self.positions.get(symbol, Decimal("0")) * price

    def total_exposure(self) -> Decimal:
        return sum((self.position_value(s) for s in self.symbols), Decimal("0"))

    def symbol_exposure(self) -> dict[str, Decimal]:
        return {s: self.position_value(s) for s in self.symbols}

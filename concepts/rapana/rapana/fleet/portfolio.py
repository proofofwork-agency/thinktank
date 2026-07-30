from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from rapana.fleet.execution import OrderResult


@dataclass
class PaperPortfolio:
    """In-memory spot portfolio for paper trading.

    Tracks cash (quote), base-asset positions, per-unit cost basis, and realized
    PnL so the circuit breaker can trip on daily losses.
    """

    cash: Decimal
    positions: dict[str, Decimal] = field(default_factory=dict)
    cost_basis: dict[str, Decimal] = field(default_factory=dict)   # total cost per symbol
    realized_pnl: Decimal = Decimal("0")

    def units(self, symbol: str) -> Decimal:
        return self.positions.get(symbol, Decimal("0"))

    def avg_cost(self, symbol: str) -> Decimal:
        u = self.units(symbol)
        if u <= 0:
            return Decimal("0")
        return self.cost_basis.get(symbol, Decimal("0")) / u

    def apply_fill(self, result: OrderResult) -> None:
        if not result.is_booked:
            return
        sym = result.symbol
        if result.side == "buy":
            cost = result.filled_qty * result.price + result.fee
            self.cash -= cost
            self.positions[sym] = self.units(sym) + result.filled_qty
            self.cost_basis[sym] = self.cost_basis.get(sym, Decimal("0")) + result.filled_qty * result.price
        else:  # sell
            sell_units = min(result.filled_qty, self.units(sym))
            if sell_units <= 0:
                # nothing to sell (no position); treat as a no-op
                return
            avg = self.avg_cost(sym)
            proceeds = sell_units * result.price - result.fee
            self.realized_pnl += proceeds - avg * sell_units
            self.cash += proceeds
            self.positions[sym] = self.units(sym) - sell_units
            remaining_cost = avg * self.units(sym)
            self.cost_basis[sym] = remaining_cost
            if self.units(sym) <= 0:
                self.positions[sym] = Decimal("0")
                self.cost_basis[sym] = Decimal("0")
        # fee already applied inside cost/proceeds above

    def equity(self, prices: dict[str, Decimal]) -> Decimal:
        total = self.cash
        for sym, units in self.positions.items():
            total += units * prices.get(sym, Decimal("0"))
        return total

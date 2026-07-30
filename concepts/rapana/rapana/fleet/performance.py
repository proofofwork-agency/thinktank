from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from rapana.agents.yield_strategist import estimate_idle_cash_drag


@dataclass
class PerformanceTracker:
    """Tracks fleet-level paper performance across cycles.

    The evidence gate: replay / paper-run summaries feed the human's decision to
    advance to live capital. Computes total return, max drawdown, and a realized
    win rate from per-cycle PnL deltas.
    """

    initial_equity: Decimal
    benchmark_cash_return: float = 0.0
    records: list[dict] = field(default_factory=list)
    _realized_deltas: list[float] = field(default_factory=list)
    _last_realized: Decimal = Decimal("0")

    def record(
        self,
        bar: int,
        equity: Decimal,
        realized_total: Decimal,
        ts: int = 0,
        idle_cash: Decimal | None = None,
    ) -> None:
        delta = realized_total - self._last_realized
        if delta != 0:
            self._realized_deltas.append(float(delta))
        self._last_realized = realized_total
        record = {"bar": bar, "ts": ts, "equity": str(equity), "realized": str(realized_total)}
        if idle_cash is not None:
            record["idle_cash"] = str(idle_cash)
        self.records.append(record)

    @property
    def equity_series(self) -> list[Decimal]:
        return [Decimal(r["equity"]) for r in self.records]

    def total_return(self) -> float:
        if not self.records or self.initial_equity <= 0:
            return 0.0
        final = Decimal(self.records[-1]["equity"])
        return float(final / self.initial_equity - 1)

    def max_drawdown(self) -> float:
        peak = Decimal("-1")
        max_dd = Decimal("0")
        for eq in self.equity_series:
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = (peak - eq) / peak
                if dd > max_dd:
                    max_dd = dd
        return float(max_dd)

    def current_drawdown(self) -> float:
        """Drawdown from the running peak to the *latest* equity.

        Unlike max_drawdown() (the historical worst, which never decreases),
        this returns to 0 once equity makes a new high — so it reflects the
        *current* risk state and is the correct input for reactive de-risk/halt
        decisions. max_drawdown() stays the right metric for reporting and for a
        historical "clean-run" promotion gate.
        """
        series = self.equity_series
        if not series:
            return 0.0
        peak = series[0]
        for eq in series:
            if eq > peak:
                peak = eq
        if peak <= 0:
            return 0.0
        return float((peak - series[-1]) / peak)

    def win_rate(self) -> float:
        if not self._realized_deltas:
            return 0.0
        wins = sum(1 for d in self._realized_deltas if d > 0)
        return wins / len(self._realized_deltas)

    def summary(self) -> dict:
        final = self.records[-1]["equity"] if self.records else str(self.initial_equity)
        realized = self.records[-1]["realized"] if self.records else "0"
        idle_cash = Decimal(self.records[-1].get("idle_cash", "0")) if self.records else Decimal("0")
        idle_drag = estimate_idle_cash_drag(idle_cash, self.benchmark_cash_return)
        return {
            "cycles": len(self.records),
            "initial_equity": str(self.initial_equity),
            "final_equity": final,
            "total_return_pct": round(self.total_return() * 100, 2),
            "max_drawdown_pct": round(self.max_drawdown() * 100, 2),
            "realized_pnl": realized,
            "idle_cash": str(idle_drag.idle_cash),
            "benchmark_cash_return_pct": round(float(idle_drag.annual_return) * 100, 2),
            "idle_cash_drag_annual": str(idle_drag.annual_drag),
            "idle_cash_drag_daily": str(idle_drag.period_drag),
            "win_rate_pct": round(self.win_rate() * 100, 1),
            "trade_events": len(self._realized_deltas),
        }

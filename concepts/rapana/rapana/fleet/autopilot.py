from __future__ import annotations

import math
from dataclasses import dataclass

from rapana.backtest.metrics import probabilistic_sharpe_ratio
from rapana.config import Settings
from rapana.fleet.capital import StagedCapital
from rapana.fleet.performance import PerformanceTracker
from rapana.logging import get_logger
from rapana.notify import Notifier, NullNotifier
from rapana.risk.guardrails import KillSwitch

log = get_logger(__name__)

_YEAR_MS = 365.0 * 24.0 * 3600.0 * 1000.0


@dataclass
class AutopilotPolicy:
    """Thresholds for autonomous capital scaling. Set at start; then hands-off.

    De-risking is always evaluated before promotion (safety first). When the
    policy is disabled, the autopilot never acts (manual `promote`/`demote` only).
    """

    enabled: bool = False
    promote_sharpe: float = 1.0
    promote_psr: float = 0.95
    promote_min_cycles: int = 500
    promote_max_drawdown: float = 0.10
    promote_cycles_per_year: int = 365
    demote_drawdown: float = 0.08
    halt_drawdown: float = 0.20

    @classmethod
    def from_settings(cls, s: Settings) -> AutopilotPolicy:
        return cls(
            enabled=s.autopilot_enabled,
            promote_sharpe=s.autopilot_promote_sharpe,
            promote_psr=s.autopilot_promote_psr,
            promote_min_cycles=s.autopilot_promote_min_cycles,
            promote_max_drawdown=s.autopilot_promote_max_drawdown,
            promote_cycles_per_year=s.autopilot_promote_cycles_per_year,
            demote_drawdown=s.autopilot_demote_drawdown,
            halt_drawdown=s.autopilot_halt_drawdown,
        )


class Autopilot:
    """Autonomous capital manager: promotes on evidence, de-risks on drawdown.

    Called once per cycle by the runner. Decisions are purely rule-based from
    the PerformanceTracker, so they are deterministic and auditable. A promote
    fires only after `promote_min_cycles` of clean, risk-adjusted performance;
    a demote fires the moment drawdown breaches — no human in the loop.
    """

    def __init__(
        self,
        policy: AutopilotPolicy,
        capital: StagedCapital,
        performance: PerformanceTracker,
        notifier: Notifier | None = None,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        self.policy = policy
        self.capital = capital
        self.performance = performance
        self.notifier = notifier or NullNotifier()
        self.kill_switch = kill_switch

    def evaluate(self) -> str:
        if not self.policy.enabled:
            return "hold"
        summary = self.performance.summary()
        cycles = summary["cycles"]
        # Reactive risk uses CURRENT drawdown (peak-to-last), which clears once
        # equity recovers to a new high. max_drawdown is the historical worst and
        # never decreases, so it must NOT gate reactive demote/halt (it would
        # latch forever after any dip); it only feeds the promotion clean-run gate.
        current_dd = self.performance.current_drawdown()
        max_dd = summary["max_drawdown_pct"] / 100.0

        # Safety hierarchy: halt > demote > promote.
        if current_dd >= self.policy.halt_drawdown and self.kill_switch is not None:
            return "halt"
        if current_dd >= self.policy.demote_drawdown:
            return "demote"
        if (
            cycles >= self.policy.promote_min_cycles
            and max_dd <= self.policy.promote_max_drawdown
            and self._promotion_psr() > self.policy.promote_psr
            and self._annualized_return() > self.performance.benchmark_cash_return
            and self.capital.fraction < 1.0
        ):
            return "promote"
        return "hold"

    def step(self) -> str:
        """Evaluate and apply the autopilot action for this cycle.

        Returns the *evaluated* action ("halt"/"demote"/"promote"/"hold") — i.e.
        which policy condition is currently breached, NOT a guarantee that a side
        effect ran. Side effects (kill-switch trip, capital reset/advance, alert)
        are edge-triggered and fire only on an actual state transition, so a
        sustained breach returns the same action every cycle while acting and
        alerting exactly once.
        """
        action = self.evaluate()
        if action == "halt":
            # Edge-trigger: trip + alert only on the transition into halt, so a
            # sustained breach doesn't re-trip/re-alert every cycle.
            if self.kill_switch is not None and not self.kill_switch.is_tripped():
                self.kill_switch.trip()
                self._alert("AUTOMATED HALT", f"drawdown breached {self.policy.halt_drawdown:.0%}")
        elif action == "demote":
            # Edge-trigger: only de-risk when capital is actually above the floor,
            # so a sustained drawdown doesn't re-alert with no real state change.
            if self.capital.stage_index > 0:
                before_stage = self.capital.stage_index
                before_frac = self.capital.fraction
                self.capital.reset()
                # Report the stage transition (not just fraction): in paper mode
                # fraction is always 1.0, so a fraction-only message reads a
                # misleading "100% -> 100%".
                self._alert(
                    "AUTOMATED DE-RISK",
                    f"drawdown breach: capital stage {before_stage}->{self.capital.stage_index} "
                    f"(fraction {before_frac:.0%}->{self.capital.fraction:.0%})",
                )
        elif action == "promote":
            before_stage = self.capital.stage_index
            before_frac = self.capital.fraction
            self.capital.advance()
            if self.capital.stage_index != before_stage:
                self._alert(
                    "AUTOMATED PROMOTE",
                    f"capital stage {before_stage}->{self.capital.stage_index} "
                    f"(fraction {before_frac:.0%}->{self.capital.fraction:.0%})",
                )
        return action

    def _sharpe(self) -> float:
        returns = self._returns()
        if not returns:
            return 0.0
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        std = math.sqrt(var)
        # Floor std relative to the mean so a near-constant/degenerate return
        # series (var ~ 0) can't produce an explosive Sharpe that trivially
        # clears the promote gate. Real noisy returns have std >> this floor, so
        # it only binds on suspiciously smooth curves.
        std = max(std, abs(mean) * 1e-3, 1e-9)
        # Per-cycle Sharpe; thresholds are relative, not annualised.
        return mean / std

    def _returns(self) -> list[float]:
        eq = self.performance.equity_series
        if len(eq) < 5:
            return []
        return [
            float((eq[i] / eq[i - 1]) - 1) for i in range(1, len(eq)) if eq[i - 1] > 0
        ]

    def _promotion_psr(self) -> float:
        returns = self._returns()
        if len(returns) < 2:
            return 0.0
        psr = probabilistic_sharpe_ratio(self._sharpe(), 0.0, len(returns))
        return psr if math.isfinite(psr) else 0.0

    def _annualized_return(self) -> float:
        records = self.performance.records
        if len(records) < 2 or self.performance.initial_equity <= 0:
            return 0.0
        final = float(self.performance.equity_series[-1])
        initial = float(self.performance.initial_equity)
        if initial <= 0 or final <= 0:
            return -1.0
        total_growth = final / initial
        elapsed_ms = int(records[-1].get("ts", 0)) - int(records[0].get("ts", 0))
        if elapsed_ms > 0:
            years = elapsed_ms / _YEAR_MS
            if years > 0:
                annual = total_growth ** (1.0 / years) - 1.0
                return annual if math.isfinite(annual) else 0.0
        returns = self._returns()
        if not returns:
            return 0.0
        cpy = max(1, self.policy.promote_cycles_per_year)
        per_cycle_growth = total_growth ** (1.0 / len(returns))
        annual = per_cycle_growth ** cpy - 1.0
        return annual if math.isfinite(annual) else 0.0

    def _alert(self, title: str, body: str) -> None:
        log.warning("autopilot_action", action=title, detail=body)
        self.notifier.send(f"RAPANA {title}", body, tags=["robot", "warning"])

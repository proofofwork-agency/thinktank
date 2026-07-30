from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from rapana.config import Settings, get_settings
from rapana.journal.ledger import DecisionLedger
from rapana.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class RiskPolicy:
    """Deterministic risk limits. The LLM cannot override these."""

    max_position_pct: Decimal          # max fraction of capital per symbol
    max_total_exposure_pct: Decimal    # max fraction of capital deployed total
    max_daily_loss_pct: Decimal        # drawdown that trips the circuit breaker
    max_orders_per_min: int            # execution-boundary throughput cap
    max_notional_per_order: Decimal    # hard size cap per order
    sanity_price_band: Decimal         # reject quotes beyond this band vs ref

    @classmethod
    def from_settings(cls, settings: Settings) -> RiskPolicy:
        s = settings
        return cls(
            max_position_pct=Decimal(str(s.risk_max_position_pct)),
            max_total_exposure_pct=Decimal(str(s.risk_max_total_exposure_pct)),
            max_daily_loss_pct=Decimal(str(s.risk_max_daily_loss_pct)),
            max_orders_per_min=s.risk_max_orders_per_min,
            max_notional_per_order=Decimal(str(s.effective_max_notional_per_order)),
            sanity_price_band=Decimal(str(s.risk_sanity_price_band)),
        )


@dataclass
class TradeProposal:
    """Pre-trade proposal emitted by the portfolio manager, vetted by risk."""

    symbol: str
    side: str               # "buy" | "sell"
    qty: Decimal
    price: Decimal
    reference_price: Decimal
    notional: Decimal = field(init=False)

    def __post_init__(self) -> None:
        self.side = self.side.lower()
        if self.side not in {"buy", "sell"}:
            raise ValueError(f"side must be buy/sell, got {self.side!r}")
        self.notional = (self.qty * self.price).quantize(Decimal("0.000001"))


@dataclass
class RiskDecision:
    approved: bool
    reason: str


class OrderRateLimiter:
    """Rolling submission limiter for the execution boundary.

    PreTradeChecker may consult this limiter, but only the order-submission path
    should call record_submission(). A dry-run risk check can happen more than
    once for a single order and must not consume throughput budget.
    """

    def __init__(self, max_orders: int, window_seconds: float = 60.0) -> None:
        if max_orders < 1:
            raise ValueError("max_orders must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self.max_orders = max_orders
        self.window_seconds = window_seconds
        self._submissions: deque[float] = deque()
        self._cancels: deque[float] = deque()
        # Optional clock so the limiter can run on decision-time (bar time in
        # replay) instead of wall-clock. Defaults to wall-clock monotonic.
        self.time_source: Callable[[], float] | None = None

    def _now(self) -> float:
        return self.time_source() if self.time_source is not None else time.monotonic()

    def record_submission(self, at: float | None = None) -> None:
        now = at if at is not None else self._now()
        self._prune(now)
        self._submissions.append(now)

    def record_cancel(self, at: float | None = None) -> None:
        now = at if at is not None else self._now()
        self._prune(now)
        self._cancels.append(now)

    def cancel_ratio(self, at: float | None = None) -> float:
        now = at if at is not None else self._now()
        self._prune(now)
        submissions = len(self._submissions)
        return len(self._cancels) / submissions if submissions else 0.0

    def would_exceed(self, at: float | None = None) -> bool:
        now = at if at is not None else self._now()
        self._prune(now)
        return len(self._submissions) >= self.max_orders

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._submissions and self._submissions[0] <= cutoff:
            self._submissions.popleft()
        while self._cancels and self._cancels[0] <= cutoff:
            self._cancels.popleft()


class KillSwitch:
    """File-based kill switch. Presence of the flag file halts the entire fleet.

    Touch the file (default ./state/KILL_SWITCH) to halt. This is deliberately
    out-of-band so it works even if the orchestrator is wedged.
    """

    def __init__(self, path: Path | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.path = Path(path) if path else self.settings.kill_switch_path

    def is_tripped(self) -> bool:
        return self.path.exists()

    def trip(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch()
        log.warning("kill_switch_tripped", path=str(self.path))

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
        log.info("kill_switch_cleared", path=str(self.path))


class CircuitBreaker:
    """Daily-loss circuit breaker. Trips when realized + open loss exceeds limit."""

    def __init__(self, policy: RiskPolicy, starting_equity: Decimal) -> None:
        self.policy = policy
        self.starting_equity = starting_equity
        self.realized_today = Decimal("0")
        self.unrealized_today = Decimal("0")
        self._tripped = False

    def record_realized(self, pnl: Decimal) -> None:
        self.realized_today += pnl
        if self._loss_breach():
            self._trip()

    def record_unrealized(self, mark_pnl: Decimal) -> None:
        self.unrealized_today = mark_pnl
        if self._loss_breach():
            self._trip()

    def _trip(self) -> None:
        self._tripped = True
        log.error(
            "circuit_breaker_tripped",
            realized=str(self.realized_today),
            unrealized=str(self.unrealized_today),
            total=str(self._total_pnl()),
            limit=str(self._loss_limit()),
        )

    def _loss_limit(self) -> Decimal:
        return -(self.starting_equity * self.policy.max_daily_loss_pct)

    def _total_pnl(self) -> Decimal:
        return self.realized_today + self.unrealized_today

    def _loss_breach(self) -> bool:
        return self._total_pnl() <= self._loss_limit()

    def is_tripped(self) -> bool:
        return self._tripped

    def reset_day(self) -> None:
        self.realized_today = Decimal("0")
        self.unrealized_today = Decimal("0")
        self._tripped = False


class PreTradeChecker:
    """Deterministic pre-trade gate. Approves/rejects a TradeProposal.

    All checks are pure policy — no LLM. This is the hard veto the Bull/Bear
    debate and Portfolio Manager cannot bypass.
    """

    def __init__(
        self,
        policy: RiskPolicy,
        kill_switch: KillSwitch,
        breaker: CircuitBreaker,
        equity: Decimal,
        current_exposure: Decimal = Decimal("0"),
        symbol_exposure: dict[str, Decimal] | None = None,
        rate_limiter: OrderRateLimiter | None = None,
        ledger: DecisionLedger | None = None,
    ) -> None:
        self.policy = policy
        self.kill_switch = kill_switch
        self.breaker = breaker
        self.equity = equity
        self.current_exposure = current_exposure
        self.symbol_exposure = symbol_exposure or {}
        self.rate_limiter = rate_limiter
        self.ledger = ledger

    def check(self, proposal: TradeProposal) -> RiskDecision:
        if self.kill_switch.is_tripped():
            return self._deny("kill_switch_tripped")
        if self.breaker.is_tripped():
            return self._deny("circuit_breaker_tripped")
        if self.rate_limiter is not None and self.rate_limiter.would_exceed():
            return self._deny(
                f"order rate would exceed {self.policy.max_orders_per_min}/min"
            )

        # Per-order notional cap.
        if proposal.notional > self.policy.max_notional_per_order:
            return self._deny(
                f"notional {proposal.notional} exceeds max "
                f"{self.policy.max_notional_per_order}"
            )

        # Sanity band: reject quotes far from reference (Flash-Crash proofing).
        band = self.policy.sanity_price_band
        ref = proposal.reference_price
        if ref > 0:
            deviation = abs(proposal.price - ref) / ref
            if deviation > band:
                return self._deny(
                    f"price {proposal.price} deviates {deviation:.2%} from ref {ref} "
                    f"(band {band:.2%})"
                )

        if proposal.side == "buy":
            # Total exposure cap.
            new_total = self.current_exposure + proposal.notional
            total_limit = self.equity * self.policy.max_total_exposure_pct
            if new_total > total_limit:
                return self._deny(
                    f"total exposure {new_total} would exceed limit {total_limit}"
                )
            # Per-symbol cap.
            sym_new = self.symbol_exposure.get(proposal.symbol, Decimal("0")) + proposal.notional
            sym_limit = self.equity * self.policy.max_position_pct
            if sym_new > sym_limit:
                return self._deny(
                    f"symbol exposure {sym_new} would exceed limit {sym_limit}"
                )

        return RiskDecision(approved=True, reason="ok")

    def _deny(self, reason: str) -> RiskDecision:
        log.warning("trade_denied", reason=reason)
        if self.ledger is not None:
            self.ledger.append("risk_veto", {"reason": reason})
        return RiskDecision(approved=False, reason=reason)

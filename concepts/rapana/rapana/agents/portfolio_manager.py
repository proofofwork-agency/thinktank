from __future__ import annotations

import math
from decimal import ROUND_DOWN, Decimal

from rapana.agents.base import Agent
from rapana.agents.researchers import Thesis
from rapana.risk.guardrails import TradeProposal
from rapana.signals import Signal, weighted_combine


class PortfolioManager(Agent):
    """Converts the analyst consensus + debate into a sized trade proposal.

    Sizing logic (spot-only): a bullish net score proposes a buy sized by the
    score up to `max_weight` of equity; a bearish score proposes a sell to
    flatten the position. Neutral scores -> no proposal (hold).
    """

    role = "portfolio_manager"

    def __init__(
        self,
        max_weight: float = 0.10,
        threshold: float = 0.20,
        max_notional: Decimal | None = None,
    ) -> None:
        self.max_weight = max_weight
        self.threshold = threshold
        # Per-order hard cap (from the risk policy). The PM sizes within it so a
        # proposal isn't immediately vetoed by the notional guard on every bar.
        self.max_notional = max_notional

    def decide(
        self,
        symbol: str,
        signals: list[Signal],
        bull: Thesis,
        bear: Thesis,
        price: Decimal,
        equity: Decimal,
        position_value: Decimal,
        source_weights: dict[str, float] | None = None,
        vol_scale: float = 1.0,
    ) -> TradeProposal | None:
        """Size a proposal from the accuracy-weighted analyst consensus.

        ``bull``/``bear`` are accepted as advisory debate context (recorded
        elsewhere for audit/explainability) and deliberately do NOT override the
        decision: direction and size come solely from ``weighted_combine`` of the
        signals. This mirrors the brain-can't-move-orders safety design —
        narrative research informs humans; deterministic math moves capital.
        """
        if price <= 0 or equity <= 0:
            return None

        net = weighted_combine(signals, source_weights)
        reference = price

        if net > self.threshold:
            scale = float(vol_scale)
            if not math.isfinite(scale):
                scale = 1.0
            weight = max(0.0, min(self.max_weight, abs(net) * scale))
            target_value = Decimal(str(weight)) * equity
            if self.max_notional is not None:
                target_value = min(target_value, self.max_notional)
            # Round qty DOWN so qty*price never creeps just over the notional cap.
            qty = (target_value / price).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
            if qty <= 0:
                return None
            return TradeProposal(
                symbol=symbol, side="buy", qty=qty, price=price, reference_price=reference,
            )

        if net < -self.threshold and position_value > 0:
            # Flatten, but respect the per-order notional cap (chunk if needed).
            sell_value = position_value
            if self.max_notional is not None:
                sell_value = min(position_value, self.max_notional)
            qty = (sell_value / price).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
            if qty <= 0:
                return None
            return TradeProposal(
                symbol=symbol, side="sell", qty=qty, price=price, reference_price=reference,
            )

        return None

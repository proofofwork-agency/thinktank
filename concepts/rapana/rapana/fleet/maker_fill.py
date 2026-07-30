from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from rapana.risk.guardrails import TradeProposal

MakerSide = Literal["buy", "sell"]
MakerFillStatus = Literal["filled", "canceled"]

PAPER_MAKER_DEFAULT_OFFSET_BPS = Decimal("2")
PAPER_MAKER_DEFAULT_LIFETIME_BARS = 1
PAPER_MAKER_TOUCH_POLICY = "strict_penetration"
PAPER_MAKER_SOURCE = "replay_ohlcv"


@dataclass(frozen=True)
class PaperMakerBar:
    index: int
    high: Decimal
    low: Decimal


@dataclass(frozen=True)
class PaperMakerOrder:
    symbol: str
    side: MakerSide
    qty: Decimal
    reference_price: Decimal
    limit_price: Decimal
    submitted_bar: int
    lifetime_bars: int
    offset_bps: Decimal

    @property
    def expiry_bar(self) -> int:
        return self.submitted_bar + self.lifetime_bars


@dataclass(frozen=True)
class PaperMakerFillOutcome:
    status: MakerFillStatus
    filled_qty: Decimal
    limit_price: Decimal
    submitted_bar: int
    expiry_bar: int
    lifetime_bars: int
    fill_bar: int | None = None
    reason: str | None = None
    offset_bps: Decimal = PAPER_MAKER_DEFAULT_OFFSET_BPS

    @property
    def is_filled(self) -> bool:
        return self.status == "filled"

    @property
    def metadata(self) -> dict[str, str]:
        metadata = {
            "touch_policy": PAPER_MAKER_TOUCH_POLICY,
            "submitted_bar": str(self.submitted_bar),
            "expiry_bar": str(self.expiry_bar),
            "lifetime_bars": str(self.lifetime_bars),
            "limit_price": str(self.limit_price),
            "source": PAPER_MAKER_SOURCE,
            "paper_maker_offset_bps": str(self.offset_bps),
        }
        if self.fill_bar is not None:
            metadata["fill_bar"] = str(self.fill_bar)
        return metadata


class PaperMakerFillModel:
    """Replay-only maker fill model based on conservative OHLCV penetration."""

    def __init__(
        self,
        *,
        offset_bps: Decimal | float | str = PAPER_MAKER_DEFAULT_OFFSET_BPS,
        lifetime_bars: int = PAPER_MAKER_DEFAULT_LIFETIME_BARS,
    ) -> None:
        self.offset_bps = Decimal(str(offset_bps))
        if self.offset_bps < 0:
            raise ValueError("offset_bps must be >= 0")
        if lifetime_bars < 1:
            raise ValueError("lifetime_bars must be >= 1")
        self.lifetime_bars = lifetime_bars

    def passive_limit(self, side: str, reference_price: Decimal) -> Decimal:
        side = self._side(side)
        if reference_price <= 0:
            raise ValueError("reference_price must be > 0")
        offset = self.offset_bps / Decimal("10000")
        multiplier = Decimal("1") - offset if side == "buy" else Decimal("1") + offset
        return reference_price * multiplier

    def submit(self, proposal: TradeProposal, submitted_bar: int) -> PaperMakerOrder:
        side = self._side(proposal.side)
        limit_price = self.passive_limit(side, proposal.reference_price)
        return PaperMakerOrder(
            symbol=proposal.symbol,
            side=side,
            qty=proposal.qty,
            reference_price=proposal.reference_price,
            limit_price=limit_price,
            submitted_bar=submitted_bar,
            lifetime_bars=self.lifetime_bars,
            offset_bps=self.offset_bps,
        )

    def resolve(
        self,
        order: PaperMakerOrder,
        bars: Sequence[PaperMakerBar | Mapping[str, object]],
    ) -> PaperMakerFillOutcome:
        for raw_bar in bars:
            bar = self._bar(raw_bar)
            if bar.index <= order.submitted_bar:
                continue
            if bar.index > order.expiry_bar:
                continue
            if self._strictly_penetrates(order, bar):
                return PaperMakerFillOutcome(
                    status="filled",
                    filled_qty=order.qty,
                    limit_price=order.limit_price,
                    submitted_bar=order.submitted_bar,
                    expiry_bar=order.expiry_bar,
                    lifetime_bars=order.lifetime_bars,
                    fill_bar=bar.index,
                    offset_bps=order.offset_bps,
                )

        return PaperMakerFillOutcome(
            status="canceled",
            filled_qty=Decimal("0"),
            limit_price=order.limit_price,
            submitted_bar=order.submitted_bar,
            expiry_bar=order.expiry_bar,
            lifetime_bars=order.lifetime_bars,
            reason="paper_timeout_no_fill",
            offset_bps=order.offset_bps,
        )

    @staticmethod
    def _side(side: str) -> MakerSide:
        normalized = side.lower()
        if normalized not in {"buy", "sell"}:
            raise ValueError(f"side must be buy/sell, got {side!r}")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _bar(raw_bar: PaperMakerBar | Mapping[str, object]) -> PaperMakerBar:
        if isinstance(raw_bar, PaperMakerBar):
            return raw_bar
        try:
            index = int(raw_bar["index"])
            high = Decimal(str(raw_bar["high"]))
            low = Decimal(str(raw_bar["low"]))
        except KeyError as exc:
            raise ValueError("bar must include index, high, and low") from exc
        return PaperMakerBar(index=index, high=high, low=low)

    @staticmethod
    def _strictly_penetrates(order: PaperMakerOrder, bar: PaperMakerBar) -> bool:
        if order.side == "buy":
            return bar.low < order.limit_price
        return bar.high > order.limit_price

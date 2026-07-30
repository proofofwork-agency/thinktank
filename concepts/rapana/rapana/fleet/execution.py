from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from rapana.fleet.capital import StagedCapital
from rapana.logging import get_logger
from rapana.mexc.client import MexcClient, is_post_only_reject
from rapana.risk.guardrails import KillSwitch, TradeProposal

log = get_logger(__name__)

OrderStatus = Literal["filled", "partial", "resting", "rejected", "canceled"]


@dataclass
class OrderResult:
    status: OrderStatus
    symbol: str
    side: str
    mode: str  # "paper" | "live"
    proposed_qty: Decimal
    filled_qty: Decimal
    price: Decimal
    fee: Decimal
    order_id: str | None = None
    client_order_id: str | None = None
    submitted: bool = False
    reason: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def is_booked(self) -> bool:
        return self.status in {"filled", "partial"}

    @property
    def qty(self) -> Decimal:
        return self.filled_qty

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "qty": str(self.filled_qty),
            "price": str(self.price),
            "fee": str(self.fee),
            "mode": self.mode,
            "status": self.status,
            "proposed_qty": str(self.proposed_qty),
            "filled_qty": str(self.filled_qty),
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "submitted": self.submitted,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


class Executor(ABC):
    """Abstract order executor."""

    mode: str = "abstract"

    @abstractmethod
    def execute(
        self, proposal: TradeProposal, available_cash: Decimal, client_order_id: str | None = None
    ) -> OrderResult: ...


class PaperExecutor(Executor):
    """Simulated executor: tracks cash/positions in memory, applies fee+slippage."""

    mode = "paper"

    def __init__(
        self,
        fee_pct: Decimal = Decimal("0.001"),
        slippage_pct: Decimal = Decimal("0.0005"),
        execution_mode: str = "market",
        paper_maker_fill_fraction: float = 0.0,
    ) -> None:
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct
        self.execution_mode = execution_mode
        self.paper_maker_fill_fraction = max(0.0, min(1.0, paper_maker_fill_fraction))

    def execute(
        self, proposal: TradeProposal, available_cash: Decimal, client_order_id: str | None = None
    ) -> OrderResult:
        if self.execution_mode == "maker":
            return self._execute_maker(proposal, available_cash, client_order_id=client_order_id)
        return self._execute_market(proposal, available_cash, client_order_id=client_order_id)

    def _execute_market(
        self, proposal: TradeProposal, available_cash: Decimal, client_order_id: str | None = None
    ) -> OrderResult:
        slip = self.slippage_pct
        price = proposal.price * (Decimal("1") + slip) if proposal.side == "buy" else proposal.price * (Decimal("1") - slip)
        notional = proposal.qty * price
        cost = notional + notional * self.fee_pct

        if proposal.side == "buy" and cost > available_cash:
            log.warning("paper_buy_skipped_insufficient_cash", symbol=proposal.symbol, cost=str(cost))
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=price,
                fee=Decimal("0"),
                client_order_id=client_order_id,
                reason="insufficient_cash",
            )

        fee = (notional * self.fee_pct).quantize(Decimal("0.000001"))
        return OrderResult(
            status="filled",
            symbol=proposal.symbol,
            side=proposal.side,
            mode=self.mode,
            proposed_qty=proposal.qty,
            filled_qty=proposal.qty,
            price=price,
            fee=fee,
            client_order_id=client_order_id,
            submitted=True,
        )

    def _execute_maker(
        self, proposal: TradeProposal, available_cash: Decimal, client_order_id: str | None = None
    ) -> OrderResult:
        limit_price = proposal.price
        mark = proposal.reference_price
        would_cross = (
            proposal.side == "buy" and limit_price >= mark
        ) or (
            proposal.side == "sell" and limit_price <= mark
        )
        if would_cross:
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=limit_price,
                fee=Decimal("0"),
                client_order_id=client_order_id,
                submitted=True,
                reason="post_only_rejected",
                metadata={"execution_mode": "maker"},
            )

        fill_qty = (proposal.qty * Decimal(str(self.paper_maker_fill_fraction))).quantize(Decimal("0.00000001"))
        notional = fill_qty * limit_price
        fee = (notional * self.fee_pct).quantize(Decimal("0.000001")) if fill_qty > 0 else Decimal("0")
        if proposal.side == "buy" and (notional + fee) > available_cash:
            log.warning("paper_maker_buy_skipped_insufficient_cash", symbol=proposal.symbol, cost=str(notional + fee))
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=limit_price,
                fee=Decimal("0"),
                client_order_id=client_order_id,
                reason="insufficient_cash",
                metadata={"execution_mode": "maker"},
            )
        if fill_qty <= 0:
            status: OrderStatus = "canceled"
            reason = "paper_timeout_no_fill"
        elif fill_qty >= proposal.qty:
            status = "filled"
            reason = None
            fill_qty = proposal.qty
        else:
            status = "partial"
            reason = "paper_partial_then_cancel"
        return OrderResult(
            status=status,
            symbol=proposal.symbol,
            side=proposal.side,
            mode=self.mode,
            proposed_qty=proposal.qty,
            filled_qty=fill_qty,
            price=limit_price,
            fee=fee,
            client_order_id=client_order_id,
            submitted=True,
            reason=reason,
            metadata={"execution_mode": "maker", "paper_maker_fill_fraction": str(self.paper_maker_fill_fraction)},
        )


class LiveExecutor(Executor):
    """Real MEXC spot executor. ONLY used when RAPANA_ENV=live.

    Places market orders via CCXT, stamped with a client order id for idempotency
    so retries cannot double-fill. The withdraw API is never touched. The risk
    gate and staged capital must already have approved the proposal.
    """

    mode = "live"

    def __init__(
        self,
        client: MexcClient,
        *,
        execution_mode: str = "market",
        maker_poll_timeout_sec: float = 2.0,
        maker_poll_interval_sec: float = 0.25,
        maker_price_peg: str = "passive_touch",
        maker_price_offset_ticks: int = 0,
        kill_switch: KillSwitch | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.client = client
        self.execution_mode = execution_mode
        self.maker_poll_timeout_sec = maker_poll_timeout_sec
        self.maker_poll_interval_sec = maker_poll_interval_sec
        self.maker_price_peg = maker_price_peg
        self.maker_price_offset_ticks = maker_price_offset_ticks
        self.kill_switch = kill_switch
        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic

    def execute(
        self, proposal: TradeProposal, available_cash: Decimal, client_order_id: str | None = None
    ) -> OrderResult:
        if self.execution_mode == "maker":
            return self._execute_maker(proposal, client_order_id=client_order_id)
        return self._execute_market(proposal, client_order_id=client_order_id)

    def _execute_market(
        self, proposal: TradeProposal, client_order_id: str | None = None
    ) -> OrderResult:
        try:
            order = self.client.create_order(
                symbol=proposal.symbol,
                side=proposal.side,
                amount=float(proposal.qty),
                order_type="market",
                client_order_id=client_order_id,
            )
            result = self._order_result_from_order(
                order, proposal, client_order_id=client_order_id, default_filled=proposal.qty,
            )
            log.warning(
                "live_order_placed", symbol=proposal.symbol, side=proposal.side,
                qty=str(result.filled_qty), price=str(result.price), status=result.status,
                client_order_id=client_order_id,
            )
            return result
        except Exception as exc:
            log.error("live_order_failed", symbol=proposal.symbol, error=str(exc))
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=proposal.price,
                fee=Decimal("0"),
                client_order_id=client_order_id,
                reason="order_failed",
                metadata={"error": str(exc), "exc_type": type(exc).__name__},
            )

    def _execute_maker(
        self, proposal: TradeProposal, client_order_id: str | None = None
    ) -> OrderResult:
        peg = self._maker_price(proposal)
        if peg.status != "filled":
            return peg
        try:
            order = self.client.create_order(
                proposal.symbol,
                proposal.side,
                float(proposal.qty),
                order_type="limit",
                price=float(peg.price),
                post_only=True,
                client_order_id=client_order_id,
            )
        except Exception as exc:
            if is_post_only_reject(exc):
                log.warning("maker_post_only_rejected", symbol=proposal.symbol, side=proposal.side, error=str(exc))
                return OrderResult(
                    status="rejected",
                    symbol=proposal.symbol,
                    side=proposal.side,
                    mode=self.mode,
                    proposed_qty=proposal.qty,
                    filled_qty=Decimal("0"),
                    price=peg.price,
                    fee=Decimal("0"),
                    client_order_id=client_order_id,
                    submitted=True,
                    reason="post_only_rejected",
                    metadata={"execution_mode": "maker", "error": str(exc), "exc_type": type(exc).__name__},
                )
            log.error("maker_order_failed", symbol=proposal.symbol, side=proposal.side, error=str(exc))
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=peg.price,
                fee=Decimal("0"),
                client_order_id=client_order_id,
                submitted=False,
                reason="order_failed",
                metadata={"execution_mode": "maker", "error": str(exc), "exc_type": type(exc).__name__},
            )

        order_id = str(order.get("id")) if order.get("id") is not None else None
        latest = order
        poll_count = 0
        deadline = self._clock() + self.maker_poll_timeout_sec
        while order_id is not None and self._clock() < deadline:
            latest = self.client.fetch_order(order_id, proposal.symbol)
            poll_count += 1
            result = self._order_result_from_order(
                latest, proposal, client_order_id=client_order_id, fallback_price=peg.price,
            )
            if result.status in {"filled", "canceled"}:
                result.metadata.update({"execution_mode": "maker", "poll_count": str(poll_count), "peg_price": str(peg.price)})
                return result
            if result.status == "partial":
                break
            self._sleep(self.maker_poll_interval_sec)

        result = self._order_result_from_order(
            latest, proposal, client_order_id=client_order_id, fallback_price=peg.price,
        )
        if order_id is None:
            return result
        if result.status == "filled":
            return result
        try:
            self.client.cancel_order(order_id, proposal.symbol)
            canceled = self.client.fetch_order(order_id, proposal.symbol)
        except Exception as exc:
            log.error("maker_cancel_failed", symbol=proposal.symbol, order_id=order_id, error=str(exc))
            return self._cancel_unverified_result(
                proposal, result.price, order_id, client_order_id, result.filled_qty, fee=result.fee,
                metadata={"error": str(exc), "exc_type": type(exc).__name__, "poll_count": str(poll_count)},
            )

        if str(canceled.get("status", "")).lower() == "open":
            return self._cancel_unverified_result(
                proposal, result.price, order_id, client_order_id, result.filled_qty, fee=result.fee,
                metadata={"execution_mode": "maker", "poll_count": str(poll_count)},
            )
        canceled_result = self._order_result_from_order(
            canceled, proposal, client_order_id=client_order_id, fallback_price=peg.price,
        )
        authoritative = canceled_result if canceled.get("filled") is not None else result
        if canceled.get("filled") is None:
            authoritative.status = "partial" if authoritative.filled_qty > 0 else canceled_result.status
        if authoritative.filled_qty >= proposal.qty:
            authoritative.status = "filled"
            authoritative.reason = None
            authoritative.metadata.update({
                "execution_mode": "maker",
                "poll_count": str(poll_count),
                "cancel_confirmed": "true",
            })
            return authoritative
        if authoritative.filled_qty > 0:
            return OrderResult(
                status="partial",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=authoritative.filled_qty,
                price=authoritative.price,
                fee=authoritative.fee,
                order_id=order_id,
                client_order_id=client_order_id,
                submitted=True,
                reason="partial_then_cancel",
                metadata={"execution_mode": "maker", "poll_count": str(poll_count), "cancel_confirmed": "true"},
            )
        canceled_result.reason = canceled_result.reason or "timeout_no_fill"
        canceled_result.metadata.update({"execution_mode": "maker", "poll_count": str(poll_count), "cancel_confirmed": "true"})
        return canceled_result

    def _maker_price(self, proposal: TradeProposal) -> OrderResult:
        if self.maker_price_peg != "passive_touch":
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=proposal.price,
                fee=Decimal("0"),
                submitted=False,
                reason="unsupported_price_peg",
                metadata={"execution_mode": "maker"},
            )
        try:
            book = self.client.fetch_order_book(proposal.symbol, limit=5)
        except Exception as exc:
            log.error("maker_order_book_failed", symbol=proposal.symbol, error=str(exc))
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=proposal.price,
                fee=Decimal("0"),
                submitted=False,
                reason="no_order_book",
                metadata={"execution_mode": "maker", "error": str(exc), "exc_type": type(exc).__name__},
            )
        bids = book.get("bids") or []
        asks = book.get("asks") or []
        if not bids or not asks:
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=proposal.price,
                fee=Decimal("0"),
                submitted=False,
                reason="no_order_book",
                metadata={"execution_mode": "maker"},
            )
        best_bid = Decimal(str(bids[0][0]))
        best_ask = Decimal(str(asks[0][0]))
        tick = self._price_tick(proposal.symbol)
        offset = tick * Decimal(self.maker_price_offset_ticks)
        price = best_bid - offset if proposal.side == "buy" else best_ask + offset
        would_cross = (proposal.side == "buy" and price >= best_ask) or (
            proposal.side == "sell" and price <= best_bid
        )
        if would_cross:
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=price,
                fee=Decimal("0"),
                submitted=False,
                reason="would_cross_local_guard",
                metadata={"execution_mode": "maker", "best_bid": str(best_bid), "best_ask": str(best_ask)},
            )
        return OrderResult(
            status="filled",
            symbol=proposal.symbol,
            side=proposal.side,
            mode=self.mode,
            proposed_qty=proposal.qty,
            filled_qty=Decimal("0"),
            price=price,
            fee=Decimal("0"),
            metadata={
                "execution_mode": "maker",
                "best_bid": str(best_bid),
                "best_ask": str(best_ask),
                "price_peg": self.maker_price_peg,
            },
        )

    def _price_tick(self, symbol: str) -> Decimal:
        self.client.load_markets()
        market = self.client.exchange.markets.get(symbol, {})
        precision = (market.get("precision") or {}).get("price")
        if isinstance(precision, int):
            return Decimal("1").scaleb(-precision)
        return Decimal("0")

    def _cancel_unverified_result(
        self,
        proposal: TradeProposal,
        price: Decimal,
        order_id: str,
        client_order_id: str | None,
        filled_qty: Decimal,
        fee: Decimal = Decimal("0"),
        metadata: dict[str, str] | None = None,
    ) -> OrderResult:
        log.error("maker_cancel_unverified", symbol=proposal.symbol, order_id=order_id)
        if self.kill_switch is not None:
            self.kill_switch.trip()
        merged_metadata = {"execution_mode": "maker"}
        merged_metadata.update(metadata or {})
        return OrderResult(
            status="partial" if filled_qty > 0 else "resting",
            symbol=proposal.symbol,
            side=proposal.side,
            mode=self.mode,
            proposed_qty=proposal.qty,
            filled_qty=filled_qty,
            price=price,
            fee=fee,
            order_id=order_id,
            client_order_id=client_order_id,
            submitted=True,
            reason="cancel_unverified",
            metadata=merged_metadata,
        )

    def _order_result_from_order(
        self,
        order: dict,
        proposal: TradeProposal,
        *,
        client_order_id: str | None,
        fallback_price: Decimal | None = None,
        default_filled: Decimal = Decimal("0"),
    ) -> OrderResult:
        filled = Decimal(str(order.get("filled") if order.get("filled") is not None else default_filled))
        avg_price = Decimal(str(order.get("average") or order.get("price") or fallback_price or proposal.price))
        fee_cost = Decimal(str((order.get("fee") or {}).get("cost", 0)))
        raw_status = str(order.get("status", "")).lower()
        if filled >= proposal.qty:
            status: OrderStatus = "filled"
        elif filled > 0:
            status = "partial"
        elif raw_status == "canceled":
            status = "canceled"
        elif raw_status == "open":
            status = "resting"
        else:
            status = "rejected"
        reason = None
        if status == "canceled" and filled <= 0:
            reason = "timeout_no_fill"
        return OrderResult(
            status=status,
            symbol=proposal.symbol,
            side=proposal.side,
            mode=self.mode,
            proposed_qty=proposal.qty,
            filled_qty=filled,
            price=avg_price,
            fee=fee_cost,
            order_id=str(order.get("id")) if order.get("id") is not None else None,
            client_order_id=client_order_id,
            submitted=True,
            reason=reason,
        )


class ExecutionTrader:
    """Bridges the Portfolio Manager output to an executor behind staged capital.

    Enforces the capital cap and applies the chosen executor (paper/live).
    """

    def __init__(self, executor: Executor, capital: StagedCapital) -> None:
        self.executor = executor
        self.capital = capital

    def execute(
        self,
        proposal: TradeProposal,
        equity: Decimal,
        cash: Decimal,
        client_order_id: str | None = None,
    ) -> OrderResult:
        notional = proposal.qty * proposal.price
        if proposal.side == "buy" and not self.capital.can_trade(notional, equity):
            log.warning(
                "trade_blocked_by_capital_stage",
                symbol=proposal.symbol, notional=str(notional),
                available=str(self.capital.available(equity)),
            )
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.executor.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=proposal.price,
                fee=Decimal("0"),
                client_order_id=client_order_id,
            )
        return self.executor.execute(proposal, cash, client_order_id=client_order_id)

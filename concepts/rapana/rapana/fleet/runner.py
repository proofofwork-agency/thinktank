from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from rapana.fleet.autopilot import Autopilot
from rapana.fleet.execution import OrderResult
from rapana.fleet.maker_fill import (
    PAPER_MAKER_SOURCE,
    PAPER_MAKER_TOUCH_POLICY,
    PaperMakerFillModel,
    PaperMakerFillOutcome,
    PaperMakerOrder,
)
from rapana.fleet.orchestrator import Fleet
from rapana.fleet.performance import PerformanceTracker
from rapana.fleet.replay import ReplayProvider
from rapana.fleet.state import FleetState
from rapana.logging import get_logger
from rapana.notify import Notifier, NullNotifier
from rapana.risk.guardrails import TradeProposal

log = get_logger(__name__)


@dataclass
class _PendingPaperMakerOrder:
    order: PaperMakerOrder
    fee_pct: Decimal
    reserved_quote: Decimal = Decimal("0")
    reserved_notional: Decimal = Decimal("0")


@dataclass(frozen=True)
class PaperMakerEvalReport:
    taker_summary: dict
    maker_summary: dict
    net_execution_delta: Decimal
    fill_rate: float
    maker_submitted: int
    maker_filled: int
    gross_fee_savings: Decimal
    taker_fee_equiv: Decimal
    maker_fee_paid: Decimal
    residual_path_delta: Decimal
    missed_notional: Decimal
    missed_count: int
    taker_fee_pct: Decimal
    maker_fee_pct: Decimal
    offset_bps: Decimal
    lifetime_bars: int

    def as_dict(self) -> dict:
        return {
            "taker_final_equity": self.taker_summary.get("final_equity"),
            "maker_final_equity": self.maker_summary.get("final_equity"),
            "net_execution_delta": str(self.net_execution_delta),
            "fill_rate": self.fill_rate,
            "maker_submitted": self.maker_submitted,
            "maker_filled": self.maker_filled,
            "gross_fee_savings": str(self.gross_fee_savings),
            "taker_fee_equiv": str(self.taker_fee_equiv),
            "maker_fee_paid": str(self.maker_fee_paid),
            "residual_path_delta": str(self.residual_path_delta),
            "missed_notional": str(self.missed_notional),
            "missed_count": self.missed_count,
            "taker_fee_pct": str(self.taker_fee_pct),
            "maker_fee_pct": str(self.maker_fee_pct),
            "offset_bps": str(self.offset_bps),
            "lifetime_bars": self.lifetime_bars,
        }


def summarize_paper_maker_eval(
    *,
    taker_summary: dict,
    maker_summary: dict,
    maker_events: list[dict],
    taker_fee_pct: Decimal,
    maker_fee_pct: Decimal,
    offset_bps: Decimal,
    lifetime_bars: int,
) -> PaperMakerEvalReport:
    maker_submitted = sum(1 for e in maker_events if e.get("kind") == "maker_submitted")
    maker_filled_events = [e for e in maker_events if e.get("kind") == "maker_filled"]
    maker_filled = len(maker_filled_events)
    fill_notional = sum((_event_notional(e) for e in maker_filled_events), Decimal("0"))
    maker_fee_paid = sum((Decimal(str(e["data"].get("fee", "0"))) for e in maker_filled_events), Decimal("0"))
    taker_fee_equiv = (fill_notional * taker_fee_pct).quantize(Decimal("0.000001"))
    gross_fee_savings = taker_fee_equiv - maker_fee_paid

    missed_events = [
        e for e in maker_events
        if e.get("kind") == "maker_canceled" or _is_rejected_maker_order_not_booked(e)
    ]
    missed_notional = sum((_event_notional(e) for e in missed_events), Decimal("0"))

    taker_final = Decimal(str(taker_summary.get("final_equity", "0")))
    maker_final = Decimal(str(maker_summary.get("final_equity", "0")))
    net_execution_delta = maker_final - taker_final
    residual_path_delta = net_execution_delta - gross_fee_savings
    fill_rate = maker_filled / maker_submitted if maker_submitted else 0.0

    return PaperMakerEvalReport(
        taker_summary=taker_summary,
        maker_summary=maker_summary,
        net_execution_delta=net_execution_delta,
        fill_rate=fill_rate,
        maker_submitted=maker_submitted,
        maker_filled=maker_filled,
        gross_fee_savings=gross_fee_savings,
        taker_fee_equiv=taker_fee_equiv,
        maker_fee_paid=maker_fee_paid,
        residual_path_delta=residual_path_delta,
        missed_notional=missed_notional,
        missed_count=len(missed_events),
        taker_fee_pct=taker_fee_pct,
        maker_fee_pct=maker_fee_pct,
        offset_bps=offset_bps,
        lifetime_bars=lifetime_bars,
    )


def format_paper_maker_eval_report(report: PaperMakerEvalReport) -> str:
    fill_pct = report.fill_rate * 100
    lines = [
        "=== Paper Maker Eval: paired replay ===",
        "Runs: taker baseline uses default inline paper execution; maker eval uses replay-only pending maker orders.",
        f"taker_final_equity    : {report.taker_summary.get('final_equity')}",
        f"maker_final_equity    : {report.maker_summary.get('final_equity')}",
        f"net_execution_delta   : {report.net_execution_delta}  (PRIMARY go/no-go)",
        f"maker_fill_rate       : {fill_pct:.2f}%  ({report.maker_filled}/{report.maker_submitted})",
        f"gross_fee_savings     : {report.gross_fee_savings}",
        f"  taker_fee_equiv     : {report.taker_fee_equiv}",
        f"  maker_fee_paid      : {report.maker_fee_paid}",
        f"residual_path_delta   : {report.residual_path_delta}",
        "  residual label      : combined limit-price improvement minus missed-fill opportunity cost minus path effects",
        f"missed_count          : {report.missed_count}",
        f"missed_notional       : {report.missed_notional}",
        "",
        "Assumptions:",
        f"  lifetime_bars       : {report.lifetime_bars}",
        f"  offset_bps          : {report.offset_bps}",
        f"  taker_fee_pct       : {report.taker_fee_pct}",
        f"  maker_fee_pct       : {report.maker_fee_pct}",
        "  fill_rate sensitivity: highly sensitive to offset_bps.",
        "  maker fee model     : conservative positive maker fee by default; no rebate assumed.",
        "",
        "Honesty gate: only this realistic replay eval can support a future live-flip case;",
        "the synthetic paper_maker_fill_fraction knob cannot justify live maker mode.",
    ]
    return "\n".join(lines)


def _event_notional(event: dict) -> Decimal:
    data = event.get("data") or {}
    qty = Decimal("0")
    for key in ("filled_qty", "proposed_qty", "qty"):
        raw = data.get(key)
        if raw is None:
            continue
        candidate = Decimal(str(raw))
        if candidate > 0:
            qty = candidate
            break
    price = Decimal(str(data.get("price") or "0"))
    return qty * price


def _is_rejected_maker_order_not_booked(event: dict) -> bool:
    if event.get("kind") != "order_not_booked":
        return False
    data = event.get("data") or {}
    metadata = data.get("metadata") or {}
    return data.get("status") == "rejected" and metadata.get("execution_mode") == "maker"


class FleetRunner:
    """Runs the fleet in two paper-trading modes:

    - ``run_replay``: drive the *entire* fleet bar-by-bar over history to validate
      behaviour before any live capital (the Phase-2 evidence gate).
    - ``run_scheduled``: a live paper daemon that cycles on a timer, persists
      state, and emits periodic digests.

    Both persist fleet state to disk so a crash/restart resumes in place.
    """

    def __init__(
        self,
        fleet: Fleet,
        performance: PerformanceTracker,
        notifier: Notifier | None = None,
        state_path: Path | str | None = None,
        autopilot: Autopilot | None = None,
        today_fn: Callable[[], date] | None = None,
    ) -> None:
        self.fleet = fleet
        self.performance = performance
        self.notifier = notifier or NullNotifier()
        self.state_path = Path(state_path) if state_path else fleet.settings.state_path
        self.autopilot = autopilot
        self.today_fn = today_fn or (lambda: datetime.now(UTC).date())
        self._breaker_day: date | None = None

    # ------------------------------------------------------------------ replay
    def run_replay(
        self,
        provider: ReplayProvider,
        bars: int | None = None,
        bars_per_day: int = 24,
        warmup: int = 30,
        on_progress: Callable[[int, int], None] | None = None,
        on_cycle: Callable[[int, FleetState], None] | None = None,
        paper_maker_eval: bool = False,
        maker_fill_model: PaperMakerFillModel | None = None,
    ) -> dict:
        total = provider.max_bars if bars is None else min(bars, provider.max_bars)
        log.info("replay_start", total_bars=total, warmup=warmup, bars_per_day=bars_per_day)
        model = maker_fill_model or PaperMakerFillModel()
        pending_maker_orders: list[_PendingPaperMakerOrder] = []

        # The fleet must read point-in-time from the replay provider (bar-time
        # timestamps), not whatever provider it was constructed with.
        previous_provider = self.fleet.provider
        previous_submitter = self.fleet.deferred_order_submitter
        self.fleet.provider = provider
        if paper_maker_eval:
            self.fleet.deferred_order_submitter = self._paper_maker_submitter(
                model, pending_maker_orders, provider,
            )
        try:
            for i in range(warmup, total):
                provider.seek(i)
                if paper_maker_eval:
                    self._set_replay_clock(provider)
                    self._resolve_paper_maker_orders(provider, pending_maker_orders, i, model)
                # Reset the daily-loss breaker each "day" (every bars_per_day bars).
                if bars_per_day > 0 and i > warmup and i % bars_per_day == 0:
                    self.fleet.breaker.reset_day()

                try:
                    state = self.fleet.run_cycle()
                except Exception as exc:
                    log.error("replay_cycle_failed", bar=i, error=str(exc))
                    continue

                self.performance.record(
                    bar=i,
                    equity=state.equity,
                    realized_total=self.fleet.paper.realized_pnl,
                    ts=provider.timestamp(self.fleet.symbols[0]) if self.fleet.symbols else 0,
                    idle_cash=self.fleet.paper.cash,
                )
                if self.autopilot is not None:
                    self.autopilot.step()
                if on_progress:
                    on_progress(i + 1, total)
                if on_cycle is not None:
                    on_cycle(i, state)
            if paper_maker_eval and pending_maker_orders:
                self._expire_tail_paper_maker_orders(pending_maker_orders, total - 1)
        finally:
            self.fleet.provider = previous_provider
            self.fleet.deferred_order_submitter = previous_submitter

        summary = self.performance.summary()
        self.notifier.send(
            "RAPANA replay complete",
            _format_summary(summary),
            tags=["chart_with_upwards_trend", "robot"],
        )
        return summary

    def _paper_maker_submitter(
        self,
        model: PaperMakerFillModel,
        pending: list[_PendingPaperMakerOrder],
        provider: ReplayProvider,
    ) -> Callable[[TradeProposal, str, Decimal, Decimal, str], OrderResult]:
        def submit(
            proposal: TradeProposal,
            symbol: str,
            equity: Decimal,
            cash: Decimal,
            client_order_id: str,
        ) -> OrderResult:
            order = model.submit(proposal, provider.cursor)
            notional = proposal.qty * order.limit_price
            fee_pct = self._paper_maker_fee_pct()
            fee = (notional * fee_pct).quantize(Decimal("0.000001"))
            reserved_quote = self._reserved_quote(pending)
            reserved_notional = self._reserved_notional(pending)
            available_capital = self.fleet.capital.available(equity) - reserved_notional
            if proposal.side == "buy" and notional > available_capital:
                log.warning(
                    "trade_blocked_by_capital_stage",
                    symbol=proposal.symbol,
                    notional=str(notional),
                    available=str(available_capital),
                )
                return OrderResult(
                    status="rejected",
                    symbol=proposal.symbol,
                    side=proposal.side,
                    mode="paper",
                    proposed_qty=proposal.qty,
                    filled_qty=Decimal("0"),
                    price=order.limit_price,
                    fee=Decimal("0"),
                    client_order_id=client_order_id,
                    reason="capital_stage",
                    metadata={"execution_mode": "maker"},
                )
            required_quote = notional + fee if proposal.side == "buy" else Decimal("0")
            available_cash = cash - reserved_quote
            if proposal.side == "buy" and required_quote > available_cash:
                log.warning(
                    "paper_maker_buy_skipped_insufficient_cash",
                    symbol=proposal.symbol,
                    cost=str(required_quote),
                )
                return OrderResult(
                    status="rejected",
                    symbol=proposal.symbol,
                    side=proposal.side,
                    mode="paper",
                    proposed_qty=proposal.qty,
                    filled_qty=Decimal("0"),
                    price=order.limit_price,
                    fee=Decimal("0"),
                    client_order_id=client_order_id,
                    reason="insufficient_cash",
                    metadata={"execution_mode": "maker"},
                )
            pending.append(
                _PendingPaperMakerOrder(
                    order=order,
                    fee_pct=fee_pct,
                    reserved_quote=required_quote,
                    reserved_notional=notional if proposal.side == "buy" else Decimal("0"),
                )
            )
            return OrderResult(
                status="resting",
                symbol=proposal.symbol,
                side=proposal.side,
                mode="paper",
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=order.limit_price,
                fee=Decimal("0"),
                client_order_id=client_order_id,
                submitted=True,
                metadata=self._pending_order_metadata(order) | {
                    "maker_fee_pct": str(fee_pct),
                    "reserved_quote": str(required_quote),
                },
            )

        return submit

    def _resolve_paper_maker_orders(
        self,
        provider: ReplayProvider,
        pending: list[_PendingPaperMakerOrder],
        bar_index: int,
        model: PaperMakerFillModel,
    ) -> None:
        remaining: list[_PendingPaperMakerOrder] = []
        for pending_order in pending:
            order = pending_order.order
            if bar_index <= order.submitted_bar:
                remaining.append(pending_order)
                continue
            bar = provider.execution_bar_at(order.symbol, bar_index)
            if bar is None:
                if bar_index >= order.expiry_bar:
                    self._book_paper_maker_resolution(pending_order, model.resolve(order, []))
                else:
                    remaining.append(pending_order)
                continue
            outcome = model.resolve(order, [bar])
            if outcome.is_filled or bar_index >= order.expiry_bar:
                self._book_paper_maker_resolution(pending_order, outcome)
            else:
                remaining.append(pending_order)
        pending[:] = remaining

    def _expire_tail_paper_maker_orders(
        self,
        pending: list[_PendingPaperMakerOrder],
        resolution_bar: int,
    ) -> None:
        for pending_order in list(pending):
            order = pending_order.order
            outcome = PaperMakerFillModel(
                offset_bps=order.offset_bps,
                lifetime_bars=order.lifetime_bars,
            ).resolve(order, [])
            self._book_paper_maker_resolution(pending_order, outcome, resolution_bar=resolution_bar)
        pending.clear()

    def _book_paper_maker_resolution(
        self,
        pending_order: _PendingPaperMakerOrder,
        outcome: PaperMakerFillOutcome,
        *,
        resolution_bar: int | None = None,
    ) -> None:
        order = pending_order.order
        filled = outcome.is_filled
        fill_qty = outcome.filled_qty if filled else Decimal("0")
        notional = fill_qty * order.limit_price
        fee = (notional * pending_order.fee_pct).quantize(Decimal("0.000001")) if filled else Decimal("0")
        result = OrderResult(
            status="filled" if filled else "canceled",
            symbol=order.symbol,
            side=order.side,
            mode="paper",
            proposed_qty=order.qty,
            filled_qty=fill_qty,
            price=order.limit_price,
            fee=fee,
            submitted=True,
            reason=None if filled else "paper_timeout_no_fill",
            metadata=outcome.metadata | {
                "execution_mode": "maker",
                "maker_fee_pct": str(pending_order.fee_pct),
                "paper_maker_resolution": "true",
                "resolution_bar": str(
                    resolution_bar if resolution_bar is not None
                    else outcome.fill_bar or outcome.expiry_bar
                ),
            },
        )
        self.fleet._handle_order_resolution_result(result, order.symbol)

    def _set_replay_clock(self, provider: ReplayProvider) -> None:
        self.fleet._now_ts = provider.timestamp(self.fleet.symbols[0]) if self.fleet.symbols else 0
        self.fleet.rate_limiter.time_source = lambda: (self.fleet._now_ts or 0) / 1000.0

    def _paper_maker_fee_pct(self) -> Decimal:
        return Decimal(str(self.fleet.settings.maker_fee_pct))

    @staticmethod
    def _reserved_quote(pending: list[_PendingPaperMakerOrder]) -> Decimal:
        return sum((p.reserved_quote for p in pending), Decimal("0"))

    @staticmethod
    def _reserved_notional(pending: list[_PendingPaperMakerOrder]) -> Decimal:
        return sum((p.reserved_notional for p in pending), Decimal("0"))

    @staticmethod
    def _pending_order_metadata(order: PaperMakerOrder) -> dict[str, str]:
        return {
            "execution_mode": "maker",
            "paper_maker_pending": "true",
            "touch_policy": PAPER_MAKER_TOUCH_POLICY,
            "submitted_bar": str(order.submitted_bar),
            "expiry_bar": str(order.expiry_bar),
            "lifetime_bars": str(order.lifetime_bars),
            "limit_price": str(order.limit_price),
            "source": PAPER_MAKER_SOURCE,
            "paper_maker_offset_bps": str(order.offset_bps),
        }

    # --------------------------------------------------------------- scheduled
    def run_scheduled(
        self,
        interval: int | None = None,
        max_cycles: int | None = None,
        digest_every: int | None = None,
    ) -> None:
        interval = interval or self.fleet.settings.paper_interval
        digest_every = digest_every or self.fleet.settings.digest_every
        cycle = 0
        log.info("scheduled_run_start", interval=interval, digest_every=digest_every)
        try:
            while max_cycles is None or cycle < max_cycles:
                self._reset_breaker_on_day_rollover()
                cycle += 1
                state = self.fleet.run_cycle()
                self.performance.record(
                    bar=cycle,
                    equity=state.equity,
                    realized_total=self.fleet.paper.realized_pnl,
                    idle_cash=self.fleet.paper.cash,
                )
                if self.autopilot is not None:
                    self.autopilot.step()
                self.save_state()
                if digest_every > 0 and cycle % digest_every == 0:
                    self.notifier.send(
                        "RAPANA daily digest",
                        state.digest + "\n\n" + _format_summary(self.performance.summary()),
                        tags=["robot"],
                    )
                if max_cycles is None:
                    time.sleep(interval)
        except KeyboardInterrupt:
            log.warning("scheduled_run_interrupted")
            self.save_state()

    # ------------------------------------------------------------ persistence
    def _reset_breaker_on_day_rollover(self) -> None:
        today = self.today_fn()
        if self._breaker_day is None:
            self._breaker_day = today
            return
        if today != self._breaker_day:
            self.fleet.breaker.reset_day()
            self._breaker_day = today

    def save_state(self) -> None:
        if self._breaker_day is None:
            self._breaker_day = self.today_fn()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "paper": {
                "cash": str(self.fleet.paper.cash),
                "positions": {k: str(v) for k, v in self.fleet.paper.positions.items()},
                "cost_basis": {k: str(v) for k, v in self.fleet.paper.cost_basis.items()},
                "realized_pnl": str(self.fleet.paper.realized_pnl),
            },
            "breaker": {
                "realized_today": str(self.fleet.breaker.realized_today),
                "tripped": self.fleet.breaker.is_tripped(),
                "day": self._breaker_day.isoformat(),
            },
            "capital": {"stage_index": self.fleet.capital.stage_index},
            "performance": self.performance.summary(),
        }
        tmp = self.state_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(self.state_path)
        log.info("fleet_state_saved", path=str(self.state_path))

    def load_state(self) -> bool:
        if not self.state_path.exists():
            return False
        with open(self.state_path, encoding="utf-8") as f:
            payload = json.load(f)
        paper = payload.get("paper", {})
        self.fleet.paper.cash = Decimal(paper.get("cash", str(self.fleet.paper.cash)))
        self.fleet.paper.positions = {k: Decimal(v) for k, v in paper.get("positions", {}).items()}
        self.fleet.paper.cost_basis = {k: Decimal(v) for k, v in paper.get("cost_basis", {}).items()}
        self.fleet.paper.realized_pnl = Decimal(paper.get("realized_pnl", "0"))

        breaker = payload.get("breaker", {})
        today = self.today_fn()
        breaker_day_raw = breaker.get("day")
        if breaker_day_raw == today.isoformat():
            self._breaker_day = today
            self.fleet.breaker.realized_today = Decimal(breaker.get("realized_today", "0"))
            self.fleet.breaker.unrealized_today = Decimal("0")
            self.fleet.breaker._tripped = bool(breaker.get("tripped", False))
        else:
            self._breaker_day = today
            self.fleet.breaker.reset_day()
        self.fleet._refresh_current_prices()
        self.fleet.state.positions = dict(self.fleet.paper.positions)
        self.fleet.state.cash = self.fleet.paper.cash
        self.fleet.state.equity = self.fleet.paper.equity(self.fleet._current_prices())
        self.fleet.record_mark_to_market_unrealized()

        cap = payload.get("capital", {})
        self.fleet.capital.stage_index = int(cap.get("stage_index", 0))
        log.info("fleet_state_loaded", path=str(self.state_path))
        return True


def _format_summary(s: dict) -> str:
    return (
        "=== RAPANA performance ===\n"
        f"cycles         : {s['cycles']}\n"
        f"initial equity : {s['initial_equity']}\n"
        f"final equity   : {s['final_equity']}\n"
        f"total return   : {s['total_return_pct']}%\n"
        f"max drawdown   : {s['max_drawdown_pct']}%\n"
        f"realized PnL   : {s['realized_pnl']}\n"
        f"idle cash      : {s['idle_cash']}\n"
        f"idle drag/yr   : {s['idle_cash_drag_annual']} "
        f"(@ {s['benchmark_cash_return_pct']}%)\n"
        f"win rate       : {s['win_rate_pct']}%\n"
        f"trade events   : {s['trade_events']}"
    )

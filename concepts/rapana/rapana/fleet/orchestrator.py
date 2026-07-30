from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from rapana.agents import (
    BearResearcher,
    BullResearcher,
    ComplianceAuditor,
    MacroAnalyst,
    MarketAnalyst,
    PortfolioManager,
    RegimeAnalyst,
    RiskManager,
    SentimentAnalyst,
)
from rapana.agents.base import Analyst
from rapana.agents.brain import DeterministicBrain, build_brain
from rapana.config import Settings, get_settings
from rapana.feeds.feargreed import FearGreedFeed
from rapana.feeds.market_premium import MarketPremiumFeed
from rapana.fleet.capital import StagedCapital
from rapana.fleet.data_provider import DataProvider
from rapana.fleet.execution import ExecutionTrader, OrderResult
from rapana.fleet.memory import ReflectionMemory
from rapana.fleet.portfolio import PaperPortfolio
from rapana.fleet.state import FleetState, SymbolState
from rapana.logging import get_logger
from rapana.risk.guardrails import (
    CircuitBreaker,
    KillSwitch,
    OrderRateLimiter,
    PreTradeChecker,
    RiskPolicy,
    TradeProposal,
)
from rapana.risk.live_safety import build_client_order_id
from rapana.sizing import BARS_PER_YEAR, vol_scale

if TYPE_CHECKING:
    from rapana.universe.scout import Scout

log = get_logger(__name__)

_BAR_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
           "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def _horizon_ms(timeframe: str, bars: int = 24) -> int:
    return bars * _BAR_MS.get(timeframe, 3_600_000)


@dataclass
class FleetConfig:
    symbols: list[str] | None = None
    max_weight: float = 0.10
    decision_threshold: float = 0.20
    timeframe: str = "1h"
    universe_mode: str = "fixed"   # "fixed" | "auto" (auto = Scout-selected)
    rebalance_bars: int = 24       # auto: re-select the universe every N cycles


class Fleet:
    """Multi-agent trading fleet orchestrator.

    Pipeline per symbol per cycle:
      analysts -> Bull/Bear debate -> Portfolio Manager -> Risk gate
        -> Execution (paper/live) -> Compliance audit.

    The Risk gate and staged-capital gate are deterministic and cannot be
    bypassed by the analysis/research stages. Shared state flows through a
    FleetState blackboard; every step is journaled.
    """

    def __init__(
        self,
        provider: DataProvider,
        capital: StagedCapital,
        trader: ExecutionTrader,
        auditor: ComplianceAuditor,
        settings: Settings | None = None,
        config: FleetConfig | None = None,
        analysts: list[Analyst] | None = None,
        initial_equity: Decimal = Decimal("10000"),
        memory: ReflectionMemory | None = None,
        scout: Scout | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.config = config or FleetConfig(symbols=self.settings.watch_symbols)
        self.provider = provider
        self.capital = capital
        self.trader = trader
        self.auditor = auditor
        self.policy = RiskPolicy.from_settings(self.settings)
        self.kill_switch = KillSwitch(settings=self.settings)
        self.analysts = analysts or self._default_analysts()
        self.brain = build_brain(self.settings)
        # DeterministicBrain keeps the default offline with empty commentary so
        # existing tests/behaviour are unchanged; only inject a real brain when
        # one is actually configured.
        _brain = None if isinstance(self.brain, DeterministicBrain) else self.brain
        self.bull = BullResearcher(brain=_brain)
        self.bear = BearResearcher(brain=_brain)
        self.pm = PortfolioManager(
            max_weight=self.config.max_weight,
            threshold=self.config.decision_threshold,
            max_notional=self.policy.max_notional_per_order,
        )
        self.breaker = CircuitBreaker(self.policy, starting_equity=initial_equity)
        # One long-lived limiter for the whole fleet so the throughput cap is
        # enforced across symbols/cycles (consulted in the risk gate, consumed
        # only on actual submission).
        self.rate_limiter = OrderRateLimiter(max(1, self.policy.max_orders_per_min))
        self.paper = PaperPortfolio(cash=initial_equity)
        self.state = FleetState(equity=initial_equity, cash=initial_equity)
        self.symbols = self.config.symbols or self.settings.watch_symbols
        self.scout = scout
        # Reflection loop: learn which sources predict price (P4).
        self.memory = memory or ReflectionMemory(horizon_ms=_horizon_ms(self.config.timeframe))
        self.deferred_order_submitter: Callable[
            [TradeProposal, str, Decimal, Decimal, str], OrderResult
        ] | None = None

    def _default_analysts(self) -> list[Analyst]:
        """Default analyst roster.

        The two external-feed analysts (sentiment = Crypto Fear & Greed,
        macro = CoinGecko cross-source premium) are wired only when
        ``settings.feeds_enabled`` is on, and only for forward paper/live.
        Historical replay/backtest bypass this entirely by constructing bare
        analysts, so a live "now" reading can never leak into a past bar
        (lookahead bias). Both feeds fail soft to (0.0, 0.0) on any outage.
        """
        roster: list[Analyst] = [MarketAnalyst(timeframe=self.config.timeframe)]
        if getattr(self.settings, "feeds_enabled", False):
            roster.append(SentimentAnalyst(sentiment_fn=FearGreedFeed().score))
            macro_feed = MarketPremiumFeed(
                self.provider.get_price, api_key=self.settings.coingecko_api_key,
            )
            roster.append(MacroAnalyst(macro_fn=macro_feed.score))
        else:
            roster.append(SentimentAnalyst())
            roster.append(MacroAnalyst())
        # LLM regime analyst: a fenced forward-only vote. Only wired when a real
        # brain is configured (provider != none) AND the flag is on; the brain
        # built here is independent of the Bull/Bear prose brain. Replay bypasses
        # _default_analysts entirely (bare analysts), so no "now" LLM read can
        # leak into a past bar.
        if getattr(self.settings, "llm_regime_enabled", False):
            brain = build_brain(self.settings)
            if not isinstance(brain, DeterministicBrain):
                roster.append(RegimeAnalyst(brain, timeframe=self.config.timeframe))
        return roster

    # ------------------------------------------------------------------ run
    def run_cycle(self) -> FleetState:
        if self.kill_switch.is_tripped():
            self.auditor.record("fleet_halted", {"reason": "kill_switch_tripped"})
            log.warning("fleet_halted_by_kill_switch")
            return self.state

        self.state.cycle += 1
        self._maybe_rebalance_universe()
        self.state.positions = dict(self.paper.positions)
        self.state.cash = self.paper.cash
        self._refresh_current_prices()
        self.state.equity = self.paper.equity(self._current_prices())
        self.record_mark_to_market_unrealized()

        # Establish decision-time before processing. The order-rate limiter runs
        # on decision-time (bar time in replay, wall-clock in live) so a fast
        # replay isn't throttled after 6 orders.
        self._now_ts = self.provider.timestamp(self.symbols[0]) if self.symbols else 0
        self.rate_limiter.time_source = lambda: (self._now_ts or 0) / 1000.0

        for symbol in self.symbols:
            self._process_symbol(symbol)

        self.state.equity = self.paper.equity(self._current_prices())
        # Resolve matured signals against THIS cycle's freshly-loaded prices.
        # Must run after _process_symbol populates state.symbols; running it
        # earlier scored against stale (previous-bar) or empty (first-cycle)
        # prices. This cycle's just-observed signals have ts == now and won't
        # have matured yet, so they are unaffected by resolving here.
        self.memory.resolve(self._current_prices(), self._now_ts)
        events = self.auditor.ledger.read_all()
        self.state.digest = self.auditor.digest(events)
        return self.state

    def _maybe_rebalance_universe(self) -> None:
        """Auto mode: re-select the trading universe from the Scout, periodically.

        Runs on cycle 1 and every ``rebalance_bars`` cycles. Currently-held
        positions are unioned with the picks so a dropped symbol keeps being
        managed by the risk gate instead of being silently orphaned. Never
        raises — on any failure it keeps the previous universe.
        """
        if self.scout is None or self.config.universe_mode != "auto":
            return
        rb = self.config.rebalance_bars
        if not (self.state.cycle == 1 or (rb > 0 and self.state.cycle % rb == 0)):
            return
        try:
            picks = self.scout.select_symbols()
        except Exception as exc:
            self.auditor.record("scout_failed", {"error": str(exc), "cycle": self.state.cycle})
            return
        if not picks:
            return
        held = [s for s, units in self.paper.positions.items() if units]
        new_symbols = list(dict.fromkeys(picks + held))  # picks first, keep held, dedup
        if new_symbols != self.symbols:
            self.auditor.record(
                "universe_selected",
                {"cycle": self.state.cycle, "symbols": new_symbols, "previous": self.symbols},
            )
        self.symbols = new_symbols

    def _current_prices(self) -> dict[str, Decimal]:
        prices: dict[str, Decimal] = {}
        for s in self.symbols:
            ss = self.state.symbols.get(s)
            prices[s] = ss.price if ss else Decimal("0")
        return prices

    def _refresh_current_prices(self) -> None:
        self.state.symbols = {
            symbol: SymbolState(symbol=symbol, price=price, ref_price=price)
            for symbol in self.symbols
            if (price := self.provider.get_price(symbol)) > 0
        }

    def record_mark_to_market_unrealized(self) -> Decimal:
        prices = self._current_prices()
        unrealized = Decimal("0")
        for symbol, units in self.paper.positions.items():
            if units <= 0:
                continue
            price = prices.get(symbol, Decimal("0"))
            if price <= 0:
                continue
            unrealized += (price - self.paper.avg_cost(symbol)) * units
        self.breaker.record_unrealized(unrealized)
        return unrealized

    def _client_order_id(self, proposal: TradeProposal) -> str:
        return build_client_order_id(
            proposal,
            cycle=self.state.cycle,
            decision_ts=int(getattr(self, "_now_ts", 0) or 0),
        )

    def _vol_scale_for_symbol(self, symbol: str) -> float:
        if self.settings.vol_target is None:
            return 1.0
        try:
            limit = max(2, self.settings.vol_lookback + 1)
            history = self.provider.get_history(symbol, self.config.timeframe, limit)
        except Exception as exc:
            log.warning("vol_scale_history_failed", symbol=symbol, error=str(exc))
            return 1.0
        if history.empty or "close" not in history:
            return 1.0
        return vol_scale(
            history["close"],
            vol_target=self.settings.vol_target,
            lookback=self.settings.vol_lookback,
            bars_per_year=BARS_PER_YEAR.get(self.config.timeframe, 24 * 365),
        )

    def _process_symbol(self, symbol: str) -> None:
        price = self._current_prices().get(symbol, Decimal("0"))
        ss = SymbolState(symbol=symbol, price=price, ref_price=price)
        self.state.symbols[symbol] = ss

        if price <= 0:
            self.auditor.record("no_price", {"symbol": symbol})
            return

        # 1) Analysts
        signals = [a.analyze(symbol, self.provider) for a in self.analysts]
        ss.signals = signals
        for sig in signals:
            self.auditor.record(
                "signal",
                {"symbol": symbol, "source": sig.source, "direction": sig.direction,
                 "strength": sig.strength, "confidence": sig.confidence, "rationale": sig.rationale},
            )
            # Feed the reflection loop: remember this call for later scoring.
            self.memory.observe(sig, price, getattr(self, "_now_ts", 0))

        # 2) Bull/Bear debate
        ss.bull = self.bull.argue(signals, symbol)
        ss.bear = self.bear.argue(signals, symbol)
        self.auditor.record(
            "debate",
            {"symbol": symbol, "bull_score": ss.bull.score, "bear_score": ss.bear.score,
             "bull_rec": ss.bull.recommended, "bear_rec": ss.bear.recommended,
             "bull_comment": ss.bull.commentary or "",
             "bear_comment": ss.bear.commentary or ""},
        )

        # 3) Portfolio Manager (signals weighted by each source's learned accuracy)
        position_value = self.paper.units(symbol) * price
        source_weights = {
            src: self.memory.weight(src) for src in {s.source for s in signals}
        }
        scale = self._vol_scale_for_symbol(symbol)
        ss.proposal = self.pm.decide(
            symbol, signals, ss.bull, ss.bear, price,
            self.state.equity, position_value, source_weights=source_weights, vol_scale=scale,
        )
        if ss.proposal is not None:
            self.auditor.record(
                "trade_proposal",
                {"symbol": symbol, "side": ss.proposal.side,
                 "qty": ss.proposal.qty, "price": ss.proposal.price},
            )

        # 4) Risk gate (fresh checker reflecting current exposure)
        checker = PreTradeChecker(
            policy=self.policy,
            kill_switch=self.kill_switch,
            breaker=self.breaker,
            equity=self.state.equity,
            current_exposure=self.state.total_exposure(),
            symbol_exposure=self.state.symbol_exposure(),
            rate_limiter=self.rate_limiter,
            ledger=self.auditor.ledger,
        )
        ss.risk_decision = RiskManager(checker).review(ss.proposal)
        self.auditor.record(
            "risk_decision",
            {"symbol": symbol, "approved": ss.risk_decision.approved, "reason": ss.risk_decision.reason},
        )

        # 5) Execution
        if ss.risk_decision.approved and ss.proposal is not None:
            client_order_id = self._client_order_id(ss.proposal)
            if self.deferred_order_submitter is not None:
                result = self.deferred_order_submitter(
                    ss.proposal, symbol, self.state.equity, self.paper.cash, client_order_id,
                )
            else:
                result = self.trader.execute(
                    ss.proposal,
                    self.state.equity,
                    self.paper.cash,
                    client_order_id=client_order_id,
                )
            ss.fill = result.as_dict()
            if result.metadata.get("paper_maker_pending") == "true":
                self._handle_pending_order_submission(result, symbol)
            else:
                self._handle_order_result(result, symbol)

    def _handle_pending_order_submission(self, result: OrderResult, symbol: str) -> None:
        if result.submitted:
            self.rate_limiter.record_submission()
        if result.metadata.get("execution_mode") != "maker":
            return
        payload = result.as_dict() | {
            "symbol_cycle": symbol,
            "cancel_ratio": self.rate_limiter.cancel_ratio(),
        }
        self.auditor.record("maker_submitted", payload)

    def _handle_order_result(self, result: OrderResult, symbol: str) -> None:
        if result.submitted:
            # Actual exchange/paper submission consumed throughput even if no
            # fill was booked. Dry-run risk checks remain free.
            self.rate_limiter.record_submission()
        self._handle_order_resolution_result(result, symbol)

    def _handle_order_resolution_result(self, result: OrderResult, symbol: str) -> None:
        self._record_order_telemetry(result, symbol)
        if result.is_booked:
            realized_delta = self._apply_fill(result)
            self.record_mark_to_market_unrealized()
            self.auditor.record("fill", result.as_dict() | {"symbol_cycle": symbol})
            if result.side == "sell":
                # Realized PnL (signed, fee-inclusive) feeds the daily-loss
                # circuit breaker as the single source of truth.
                self.breaker.record_realized(realized_delta)
        else:
            log.warning(
                "order_not_booked",
                symbol=symbol,
                side=result.side,
                status=result.status,
                proposed_qty=str(result.proposed_qty),
                filled_qty=str(result.filled_qty),
            )
            self.auditor.record("order_not_booked", result.as_dict() | {"symbol_cycle": symbol})

    def _record_order_telemetry(self, result: OrderResult, symbol: str) -> None:
        if result.reason in {
            "timeout_no_fill",
            "paper_timeout_no_fill",
            "partial_then_cancel",
            "paper_partial_then_cancel",
            "cancel_unverified",
        }:
            self.rate_limiter.record_cancel()
        if result.metadata.get("execution_mode") != "maker":
            return

        payload = result.as_dict() | {
            "symbol_cycle": symbol,
            "cancel_ratio": self.rate_limiter.cancel_ratio(),
        }
        if result.submitted and result.metadata.get("paper_maker_resolution") != "true":
            self.auditor.record("maker_submitted", payload)
        if result.status == "filled":
            self.auditor.record("maker_filled", payload)
        elif result.status == "partial":
            self.auditor.record("maker_partial", payload)
            if result.reason == "cancel_unverified":
                self.auditor.record("missed_fill", payload)
        elif result.status == "canceled":
            self.auditor.record("maker_canceled", payload)
            self.auditor.record("missed_fill", payload)
        elif result.reason in {
            "post_only_rejected",
            "no_order_book",
            "would_cross_local_guard",
            "paper_timeout_no_fill",
            "timeout_no_fill",
            "cancel_unverified",
        }:
            self.auditor.record("missed_fill", payload)

    def _apply_fill(self, result: OrderResult) -> Decimal:
        """Apply a fill and return the realized-PnL delta it produced.

        Capturing the delta around PaperPortfolio.apply_fill makes it the single
        source of truth for the circuit breaker. Reading avg_cost() *after* the
        fill would see a flattened position (avg_cost == 0 on a full close) and
        report gross proceeds as profit, silently defeating the loss breaker.
        """
        realized_before = self.paper.realized_pnl
        self.paper.apply_fill(result)
        self.state.positions = dict(self.paper.positions)
        self.state.cash = self.paper.cash
        return self.paper.realized_pnl - realized_before

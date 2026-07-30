from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from rapana.backtest.metrics import PerformanceMetrics, compute_metrics
from rapana.logging import get_logger
from rapana.signals import Signal
from rapana.sizing import BARS_PER_YEAR, vol_scale
from rapana.strategies.base import Strategy

log = get_logger(__name__)


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: Decimal = Decimal("10000")
    fee_pct: Decimal = Decimal("0.001")        # 0.1% taker
    slippage_pct: Decimal = Decimal("0.0005")  # 5 bps
    max_weight: float = 0.95                   # max fraction of equity per position
    min_notional: Decimal = Decimal("10")      # ignore orders below this notional
    timeframe: str = "1h"
    vol_target: float | None = None            # annualized vol target (None = off)
    vol_lookback: int = 20                     # bars for the realized-vol estimate


@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    config: BacktestConfig
    equity_curve: pd.Series
    trades: list[dict] = field(default_factory=list)
    metrics: PerformanceMetrics | None = None

    def finalize(self) -> BacktestResult:
        self.metrics = compute_metrics(
            self.equity_curve,
            self.trades,
            bars_per_year=BARS_PER_YEAR.get(self.config.timeframe, 24 * 365),
            initial_equity=float(self.config.initial_equity),
        )
        return self


class BacktestEngine:
    """Event-driven, point-in-time-correct single-symbol backtester.

    Anti-lookahead: at bar i the strategy only sees rows [0, i) and the order
    is filled at bar i's close price. A one-bar lag models realistic execution.
    """

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    def run(self, df: pd.DataFrame, strategy: Strategy, symbol: str) -> BacktestResult:
        cfg = self.config
        if len(df) < 3:
            raise ValueError(f"need at least 3 bars, got {len(df)}")

        cash = Decimal(str(cfg.initial_equity))
        position = Decimal("0")
        equity_idx: list[int] = []
        equity_vals: list[float] = []
        trades: list[dict] = []
        entry_price = Decimal("0")

        for i in range(1, len(df) + 1):
            # Decision at bar i uses history strictly before i.
            if i >= len(df):
                break
            history = df.iloc[:i]
            price_dec = Decimal(str(float(df["close"].iloc[i])))
            if price_dec <= 0:
                continue

            signal = strategy.generate(history, symbol)
            vol_scale = self._vol_scale(history, cfg)
            target_value = self._target_value(signal, cfg, cash, position, price_dec, vol_scale)
            target_units = (target_value / price_dec) if price_dec > 0 else Decimal("0")
            delta = target_units - position

            equity = cash + position * price_dec
            if abs(delta) * price_dec >= cfg.min_notional:
                slip = cfg.slippage_pct
                fill_price = price_dec * (Decimal("1") + slip) if delta > 0 else price_dec * (Decimal("1") - slip)
                fee = (abs(delta) * fill_price * cfg.fee_pct).quantize(Decimal("0.000001"))
                # cash flows: buying spends, selling receives
                cash = cash - delta * fill_price - fee
                position = position + delta
                # record a trade on every real position change
                if delta < 0:
                    # sell / reduce: realize PnL on the units sold against the
                    # running average entry. Partial reductions are booked too;
                    # the remaining position keeps the same average entry price.
                    sold = -delta
                    pnl = (fill_price - entry_price) * sold if entry_price > 0 else Decimal("0")
                    trades.append({
                        "bar": i, "side": "sell", "qty": float(sold),
                        "price": float(fill_price), "fee": float(fee), "pnl": float(pnl),
                    })
                    if position == 0:
                        entry_price = Decimal("0")
                elif delta > 0:
                    # weighted avg entry
                    if entry_price > 0 and position - delta > 0:
                        old = (position - delta) * entry_price
                        entry_price = (old + delta * fill_price) / position
                    else:
                        entry_price = fill_price
                    trades.append({
                        "bar": i, "side": "buy", "qty": float(delta),
                        "price": float(fill_price), "fee": float(fee), "pnl": 0.0,
                    })

            equity = cash + position * price_dec
            equity_idx.append(int(df["ts"].iloc[i]) if "ts" in df else i)
            equity_vals.append(float(equity))

        equity_curve = pd.Series(equity_vals, index=equity_idx, name="equity")
        result = BacktestResult(
            symbol=symbol,
            strategy=strategy.name,
            config=cfg,
            equity_curve=equity_curve,
            trades=trades,
        )
        return result.finalize()

    @staticmethod
    def _vol_scale(history: pd.DataFrame, cfg: BacktestConfig) -> float:
        """Volatility-targeting multiplier: aim each position at a target annualized
        vol, so calm markets get more exposure and turbulent ones get less (long-only,
        so the final weight is still capped by max_weight). Returns 1.0 when off."""
        return vol_scale(
            history["close"],
            vol_target=cfg.vol_target,
            lookback=cfg.vol_lookback,
            bars_per_year=BARS_PER_YEAR.get(cfg.timeframe, 24 * 365),
        )

    @staticmethod
    def _target_value(
        signal: Signal,
        cfg: BacktestConfig,
        cash: Decimal,
        position: Decimal,
        price: Decimal,
        vol_scale: float = 1.0,
    ) -> Decimal:
        equity = cash + position * price
        if signal.direction == "bullish":
            base = abs(signal.strength) * signal.confidence
            # long-only: clamp to [0, max_weight] so no scale can create a short
            weight = max(0.0, min(cfg.max_weight, base * vol_scale))
            return Decimal(str(weight)) * equity
        if signal.direction == "bearish":
            return Decimal("0")  # spot: flatten
        return position * price  # neutral: hold

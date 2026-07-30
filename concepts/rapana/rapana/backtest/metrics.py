from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

import pandas as pd

_NORMAL = NormalDist()


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    annualized_return: float
    sharpe: float
    sortino: float
    max_drawdown: float
    volatility: float
    num_trades: int
    win_rate: float
    profit_factor: float
    final_equity: float

    def as_dict(self) -> dict:
        return self.__dict__ | {
            "total_return_pct": self.total_return * 100,
            "annualized_return_pct": self.annualized_return * 100,
            "max_drawdown_pct": self.max_drawdown * 100,
            "sharpe": round(self.sharpe, 3),
        }


def compute_metrics(
    equity: pd.Series,
    trades: list[dict],
    *,
    bars_per_year: float,
    initial_equity: float,
) -> PerformanceMetrics:
    equity = equity.dropna()
    if len(equity) < 2:
        return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, float(equity.iloc[-1]) if len(equity) else initial_equity)

    returns = equity.pct_change().dropna()
    final = float(equity.iloc[-1])
    total_return = final / initial_equity - 1.0
    years = len(equity) / bars_per_year if bars_per_year else 1.0
    annualized = (final / initial_equity) ** (1 / years) - 1.0 if years > 0 else 0.0

    std = float(returns.std(ddof=0)) or 1e-9
    sharpe = float(returns.mean()) / std * math.sqrt(bars_per_year)

    downside = returns[returns < 0]
    if len(downside) > 0:
        dstd = float(downside.std(ddof=0)) or 1e-9
        sortino = float(returns.mean()) / dstd * math.sqrt(bars_per_year)
    else:
        # No losing bars → no downside deviation. Sortino is unbounded in the
        # limit; report the finite Sharpe as a non-misleading stand-in rather
        # than NaN (empty-Series std), which also serialized as invalid JSON.
        sortino = sharpe

    volatility = std * math.sqrt(bars_per_year)

    # Max drawdown
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    max_dd = float(dd.min())

    wins = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) < 0]
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses)
    # Win rate over decided round-trips only: buy legs are booked with pnl=0 by
    # the engine, so including them in the denominator systematically deflates it.
    decided = len(wins) + len(losses)
    win_rate = len(wins) / decided if decided else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=max_dd,
        volatility=volatility,
        num_trades=len(trades),
        win_rate=win_rate,
        profit_factor=profit_factor,
        final_equity=final,
    )


# ---------------------------------------------------------------------------
# Selection-bias-aware statistics (Bailey & Lopez de Prado).
# These take PER-OBSERVATION (non-annualized) Sharpe ratios. ``kurtosis`` is the
# raw (non-excess) kurtosis: 3.0 for a normal distribution.
# ---------------------------------------------------------------------------
def probabilistic_sharpe_ratio(
    sharpe: float, benchmark: float, n_obs: int, *, skew: float = 0.0, kurtosis: float = 3.0
) -> float:
    """P(true Sharpe > ``benchmark``) given a noisy estimate from ``n_obs`` bars.

    Accounts for sample length and non-normal returns (skew/kurtosis).
    """
    if n_obs <= 1:
        return float("nan")
    denom = 1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * sharpe * sharpe
    if denom <= 0:
        return float("nan")
    z = (sharpe - benchmark) * math.sqrt(n_obs - 1) / math.sqrt(denom)
    return _NORMAL.cdf(z)


def expected_max_sharpe(sharpe_variance: float, n_trials: int) -> float:
    """Expected MAXIMUM Sharpe across ``n_trials`` independent strategies under
    the null of zero true skill — the bar a backtest must clear to be credible.

    Grows with the number of strategies tried: try enough, one looks great by
    luck alone. ``sharpe_variance`` is the variance of the trial Sharpes.
    """
    if n_trials < 2 or sharpe_variance <= 0:
        return 0.0
    gamma = 0.5772156649015329  # Euler-Mascheroni constant
    z1 = _NORMAL.inv_cdf(1.0 - 1.0 / n_trials)
    z2 = _NORMAL.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return math.sqrt(sharpe_variance) * ((1.0 - gamma) * z1 + gamma * z2)


def deflated_sharpe_ratio(
    sharpe: float,
    *,
    sharpe_variance: float,
    n_trials: int,
    n_obs: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Probability the best of ``n_trials`` strategies has a TRUE Sharpe > 0,
    correcting for selection bias, sample length, and non-normal returns.

    DSR > 0.95 is the usual bar for "this edge is statistically credible".
    """
    threshold = expected_max_sharpe(sharpe_variance, n_trials)
    return probabilistic_sharpe_ratio(sharpe, threshold, n_obs, skew=skew, kurtosis=kurtosis)

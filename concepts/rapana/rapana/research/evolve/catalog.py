"""Pre-registered hypothesis catalog for the evolve loop.

IMPORTANT: This catalog is the external trial set. Adding families after seeing
results inflates the multiple-testing bar and must be reflected in n_trials.
Families already falsified on 1h are re-opened only on NEW surfaces (1d history,
maker fee assumptions, vol-targeting) — not blind re-runs of the closed hunt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FamilyKind = Literal[
    "directional",
    "cross_sectional",
    "event_trigger",
    "structural",
]


@dataclass(frozen=True)
class Hypothesis:
    """One pre-registered experiment the loop may run."""

    id: str
    family: FamilyKind
    description: str
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 100  # lower = sooner
    # If True, mutations of near-misses are allowed within mutate_bounds.
    mutable: bool = True
    mutate_bounds: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None
    depth: int = 0


# ---------------------------------------------------------------------------
# Catalog v1 — re-open on surfaces the closure did NOT fully exhaust.
# Surface A: multi-year daily bars (1d) for directional + event triggers
# Surface B: cross-sectional rotation on 1d mid-caps with proper lookbacks
# Surface C: maker-cost (5bp) vs taker (10bp) on the best directional configs
# Surface D: structural verification (maker fee floor) — not prediction alpha
# ---------------------------------------------------------------------------

CATALOG_VERSION = "2026-07-30.v1"


def seed_catalog() -> list[Hypothesis]:
    """Return the ordered seed queue (lowest priority first)."""
    hyps: list[Hypothesis] = []

    # --- A. Daily directional strategies (parameterized) ---
    # Prior work focused on 1h defaults. Daily multi-year data is a distinct
    # surface; params pre-committed here before any result is seen.
    for fast, slow in ((5, 20), (10, 40), (20, 50), (12, 26)):
        hyps.append(Hypothesis(
            id=f"dir-1d-trend-f{fast}-s{slow}",
            family="directional",
            description=f"1d EMA trend fast={fast} slow={slow}, taker fees",
            priority=10,
            params={
                "strategy": "trend",
                "timeframe": "1d",
                "fast": fast,
                "slow": slow,
                "fee_pct": 0.001,
                "slippage_pct": 0.0005,
                "vol_target": None,
                "n_splits": 6,
                "warmup": 60,
                "holdout": 0.20,
            },
            mutate_bounds={"fast": [5, 8, 10, 12, 15, 20], "slow": [20, 26, 40, 50, 60]},
        ))

    for period, lo, hi in ((14, 30, 70), (14, 25, 75), (7, 25, 75), (21, 30, 70)):
        hyps.append(Hypothesis(
            id=f"dir-1d-meanrev-p{period}-lo{lo}-hi{hi}",
            family="directional",
            description=f"1d RSI mean-rev period={period} band=[{lo},{hi}]",
            priority=15,
            params={
                "strategy": "meanrev",
                "timeframe": "1d",
                "period": period,
                "oversold": float(lo),
                "overbought": float(hi),
                "fee_pct": 0.001,
                "slippage_pct": 0.0005,
                "vol_target": None,
                "n_splits": 6,
                "warmup": 60,
                "holdout": 0.20,
            },
            mutate_bounds={
                "period": [7, 10, 14, 21],
                "oversold": [20.0, 25.0, 30.0, 35.0],
                "overbought": [65.0, 70.0, 75.0, 80.0],
            },
        ))

    for period, std in ((20, 2.0), (20, 2.5), (30, 2.0), (14, 2.0)):
        hyps.append(Hypothesis(
            id=f"dir-1d-breakout-p{period}-s{std}",
            family="directional",
            description=f"1d Bollinger breakout period={period} std={std}",
            priority=20,
            params={
                "strategy": "breakout",
                "timeframe": "1d",
                "period": period,
                "std": std,
                "fee_pct": 0.001,
                "slippage_pct": 0.0005,
                "vol_target": None,
                "n_splits": 6,
                "warmup": 60,
                "holdout": 0.20,
            },
            mutate_bounds={"period": [10, 14, 20, 30, 40], "std": [1.5, 2.0, 2.5, 3.0]},
        ))

    # Vol-targeted variants of the three defaults (defensive sizing edge probe).
    for strat in ("trend", "meanrev", "breakout"):
        hyps.append(Hypothesis(
            id=f"dir-1d-{strat}-voltarget-0.5",
            family="directional",
            description=f"1d {strat} with 50% annualized vol target",
            priority=25,
            params={
                "strategy": strat,
                "timeframe": "1d",
                "fee_pct": 0.001,
                "slippage_pct": 0.0005,
                "vol_target": 0.5,
                "n_splits": 6,
                "warmup": 60,
                "holdout": 0.20,
            },
            mutable=False,
        ))

    # Maker-cost re-test of defaults (cost layer, not new signal).
    for strat in ("trend", "meanrev", "breakout"):
        hyps.append(Hypothesis(
            id=f"dir-1d-{strat}-maker-5bp",
            family="directional",
            description=f"1d {strat} with maker-like 5bp fee (cost layer probe)",
            priority=30,
            params={
                "strategy": strat,
                "timeframe": "1d",
                "fee_pct": 0.0005,
                "slippage_pct": 0.0002,
                "vol_target": None,
                "n_splits": 6,
                "warmup": 60,
                "holdout": 0.20,
            },
            mutable=False,
        ))

    # --- B. Cross-sectional on 1d (lookbacks in days) ---
    # Pre-committed grid; DSR deflates across the whole family when scored as a batch.
    hyps.append(Hypothesis(
        id="xs-1d-momentum-grid",
        family="cross_sectional",
        description="1d cross-sectional momentum rotation pre-registered grid",
        priority=5,
        params={
            "timeframe": "1d",
            "signals": ["momentum"],
            "lookbacks": [20, 60, 120],
            "top_ks": [3, 5],
            "rebalances": [5, 20],
            "n_splits": 6,
            "warmup": 120,
            "holdout": 0.20,
            "fee_pct": 0.001,
            "max_weight": 0.95,
        },
        mutable=True,
        mutate_bounds={
            "lookbacks": [[10, 20, 40], [20, 60, 120], [60, 120, 180]],
            "top_ks": [[1, 3], [3, 5], [5, 8]],
            "rebalances": [[5], [10, 20], [20]],
        },
    ))
    hyps.append(Hypothesis(
        id="xs-1d-reversion-grid",
        family="cross_sectional",
        description="1d cross-sectional short-horizon reversion grid",
        priority=8,
        params={
            "timeframe": "1d",
            "signals": ["reversion"],
            "lookbacks": [5, 10, 20],
            "top_ks": [3, 5],
            "rebalances": [5],
            "n_splits": 6,
            "warmup": 60,
            "holdout": 0.20,
            "fee_pct": 0.001,
            "max_weight": 0.95,
        },
        mutable=True,
        mutate_bounds={
            "lookbacks": [[3, 5, 10], [5, 10, 20], [10, 20]],
            "top_ks": [[1, 3], [3, 5]],
            "rebalances": [[1, 5], [5]],
        },
    ))

    # --- C. Event triggers on 1d (new surface vs 1h hunt) ---
    hyps.append(Hypothesis(
        id="evt-1d-default-pooled",
        family="event_trigger",
        description="Pooled 1d event-trigger hunt (DEFAULT_TRIGGERS scaled horizons)",
        priority=12,
        params={
            "timeframe": "1d",
            "mode": "pooled",
            "n_splits": 5,
            "warmup": 30,
            "fee_per_side": 0.0005,
            "slippage_per_side": 0.0005,
            "min_events": 8,
            "holdout": 0.20,
            "scale": "daily",  # use daily-appropriate trigger params
        },
        mutable=False,
    ))
    hyps.append(Hypothesis(
        id="evt-1d-default-per-symbol",
        family="event_trigger",
        description="Per-symbol 1d event-trigger hunt (exploratory; no PASS claim alone)",
        priority=40,
        params={
            "timeframe": "1d",
            "mode": "per_symbol",
            "n_splits": 5,
            "warmup": 30,
            "fee_per_side": 0.0005,
            "slippage_per_side": 0.0005,
            "min_events": 6,
            "holdout": 0.20,
            "scale": "daily",
            "pass_eligible": False,  # exploratory only
        },
        mutable=False,
    ))

    # --- D. Structural (not prediction alpha) ---
    hyps.append(Hypothesis(
        id="struct-maker-fee-floor",
        family="structural",
        description="Re-verify maker fee savings on stored 1h majors (cost layer, not alpha)",
        priority=50,
        params={
            "timeframe": "1h",
            "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
            "offset_bps": 2.0,
        },
        mutable=False,
    ))

    hyps.sort(key=lambda h: (h.priority, h.id))
    return hyps


def hypothesis_fingerprint(h: Hypothesis) -> str:
    """Stable id for dedup of mutated children."""
    import hashlib
    import json

    blob = json.dumps(
        {"family": h.family, "params": h.params, "parent": h.parent_id},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha1(blob.encode()).hexdigest()[:12]

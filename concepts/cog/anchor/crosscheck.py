#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""Reproduce the offline COG/Epoch methodology cross-check.

The Epoch events have exact release dates; the COG backtest has monthly
resolution. Each event is therefore evaluated against the COG value for its
release month while retaining the exact Epoch date in the report.

From the repository root:
    python3 concepts/cog/anchor/crosscheck.py
"""

import re
import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
COGFIX_DIR = ROOT / "cogfix"
if str(COGFIX_DIR) not in sys.path:
    sys.path.insert(0, str(COGFIX_DIR))

from anchor import anchor_series, normalize_blend  # noqa: E402
import cogfix  # noqa: E402

SIX = Decimal("0.000001")
SAME_MODEL = "SAME-MODEL"
DIFFERENT_MODEL = "DIFFERENT-MODEL"
INSIDE = "INSIDE"
OUTSIDE = "OUTSIDE"


@dataclass(frozen=True)
class CrosscheckRow:
    epoch_date: str
    epoch_model: str
    epoch_usd_per_million: str
    cog_fix: str
    ratio_cog_to_epoch: str
    cog_basis: str
    model_comparison: str
    blend_band: str


def _six(value: Decimal) -> str:
    return format(value.quantize(SIX, rounding=ROUND_HALF_UP), "f")


def _model_family(name: str) -> str:
    """Normalize release-stamped names without merging distinct model families."""
    family = re.sub(r"-(?:\d{4}-\d{2}|\d{4})$", "", name.strip(), flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", "", family.casefold())


def _selected_cog_models() -> dict[int, frozenset[str]]:
    """Return model families that set each exact monthly COG observation."""
    selected: dict[int, tuple[Decimal, set[str]]] = {}
    for point in cogfix.DATA["frontier_tier_series"]:
        if point["status"] == "provisional":
            continue
        month = cogfix.month_index(point["date"])
        price = Decimal(str(point["blended_usd_per_M"]))
        family = _model_family(point["model"])
        current = selected.get(month)
        if current is None or price < current[0]:
            selected[month] = (price, {family})
        elif price == current[0]:
            current[1].add(family)
    return {month: frozenset(families) for month, (_, families) in selected.items()}


def blend_ratio_band() -> tuple[Decimal, Decimal]:
    """Return the admissible COG-4:1 / Epoch-3:1 ratio from normalize_blend()."""
    normalized = normalize_blend("1")
    return Decimal(normalized["lower"]), Decimal(normalized["upper"])


def crosscheck_rows() -> list[CrosscheckRow]:
    """Join every vendored Epoch event to the COG value in its release month."""
    lower, upper = blend_ratio_band()
    selected_models = _selected_cog_models()
    rows = []
    for event in anchor_series():
        release_date = event["release_date"]
        month_text = release_date.strftime("%Y-%m")
        month = cogfix.month_index(month_text)
        cog_value, exact = cogfix.fix_at(month_text)
        cog_decimal = Decimal(str(cog_value))
        epoch_decimal = event["usd_per_million_tokens"]
        ratio = cog_decimal / epoch_decimal
        same_model = (
            exact
            and _model_family(event["Model Name"]) in selected_models.get(month, ())
        )
        rows.append(
            CrosscheckRow(
                epoch_date=release_date.isoformat(),
                epoch_model=event["Model Name"],
                epoch_usd_per_million=_six(epoch_decimal),
                cog_fix=_six(cog_decimal),
                ratio_cog_to_epoch=_six(ratio),
                cog_basis="exact" if exact else "interpolated",
                model_comparison=SAME_MODEL if same_model else DIFFERENT_MODEL,
                blend_band=INSIDE if lower <= ratio <= upper else OUTSIDE,
            )
        )
    return rows


def render_report(rows: list[CrosscheckRow] | None = None) -> str:
    """Render the deterministic artifact quoted by the project documentation."""
    rows = crosscheck_rows() if rows is None else rows
    lower, upper = blend_ratio_band()
    header = (
        f"{'epoch date':<12}{'epoch model':<27}{'epoch $/M':>11}"
        f"{'cog fix':>11}{'cog/epoch':>11}  {'cog basis':<14}"
        f"{'model comparison':<18}{'blend band'}"
    )
    lines = [
        "COG / Epoch cross-check (offline; vendored data only)",
        "COG backtest resolution: monthly; Epoch dates below are exact event dates.",
        "Admissible COG/Epoch blend ratio band from normalize_blend(): "
        f"[{_six(lower)}, {_six(upper)}]",
        "",
        header,
        "-" * len(header),
    ]
    for row in rows:
        lines.append(
            f"{row.epoch_date:<12}{row.epoch_model:<27}"
            f"{row.epoch_usd_per_million:>11}{row.cog_fix:>11}"
            f"{row.ratio_cog_to_epoch:>11}  {row.cog_basis:<14}"
            f"{row.model_comparison:<18}{row.blend_band}"
        )
    same_inside = sum(
        row.model_comparison == SAME_MODEL and row.blend_band == INSIDE
        for row in rows
    )
    different_outside = sum(
        row.model_comparison == DIFFERENT_MODEL and row.blend_band == OUTSIDE
        for row in rows
    )
    lines.extend(
        [
            "",
            f"Classification: {same_inside} SAME-MODEL/INSIDE; "
            f"{different_outside} DIFFERENT-MODEL/OUTSIDE.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    print(render_report())


if __name__ == "__main__":
    main()

# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""Offline access to the vendored Epoch AI inference-price anchor."""

import csv
import hashlib
import io
import json
import os
import tempfile
import urllib.request
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshot" / "epoch_llm_inference_prices.csv"
SIX = Decimal("0.000001")


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{label} must be finite")
    return result


def _six(value: Decimal) -> str:
    return format(value.quantize(SIX, rounding=ROUND_HALF_UP), "f")


def _read_rows(handle) -> list[dict]:
    reader = csv.DictReader(handle)
    expected = {
        "bench",
        "threshold_model",
        "performance_range",
        "Model Name",
        "Release Date",
        "USD per 1M Tokens",
        "predicted_log_price",
        "benchmark_score",
    }
    if set(reader.fieldnames or ()) != expected:
        raise ValueError(f"unexpected Epoch columns: {reader.fieldnames}")
    rows = []
    for raw in reader:
        row = dict(raw)
        row["release_date"] = date.fromisoformat(raw["Release Date"])
        row["usd_per_million_tokens"] = _decimal(
            raw["USD per 1M Tokens"], "USD per 1M Tokens"
        )
        row["benchmark_score_decimal"] = _decimal(
            raw["benchmark_score"], "benchmark_score"
        )
        rows.append(row)
    return rows


def load_snapshot(path: str | Path = SNAPSHOT) -> list[dict]:
    """Load the local CSV. This function never refreshes it."""
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return _read_rows(handle)


def anchor_series(
    rows: list[dict] | None = None,
    *,
    bench: str = "MMLU",
    threshold_model: str = "GPT-4",
) -> list[dict]:
    """Select the GPT-4-class MMLU step events in release-date order."""
    rows = rows if rows is not None else load_snapshot()
    aliases = {
        "GPT-4": {"GPT-4", "GPT-4-0314"},
        "GPT-4-0314": {"GPT-4-0314"},
    }
    accepted = aliases.get(threshold_model, {threshold_model})
    selected = [
        row
        for row in rows
        if row["bench"] == bench and row["threshold_model"] in accepted
    ]
    return sorted(selected, key=lambda row: row["release_date"])


def anchor_at(
    when: str | date,
    series: list[dict] | None = None,
) -> dict:
    """Return the last event on or before ``when`` (a step function).

    Interpolation would invent observations between Epoch release events and is
    therefore intentionally absent.
    """
    target = when if isinstance(when, date) else date.fromisoformat(when)
    events = series if series is not None else anchor_series()
    eligible = [row for row in events if row["release_date"] <= target]
    if not eligible:
        raise LookupError(f"no Epoch anchor on or before {target.isoformat()}")
    row = max(eligible, key=lambda item: item["release_date"])
    return {
        "date": row["release_date"].isoformat(),
        "usd_per_million_tokens": _six(row["usd_per_million_tokens"]),
        "model": row["Model Name"],
        "bench": row["bench"],
        "threshold_model": row["threshold_model"],
        "performance_range": row["performance_range"],
        "benchmark_score": str(row["benchmark_score"]),
        "lookup": "step-function",
    }


def normalize_blend(
    value: dict | str | Decimal,
    *,
    input_usd_per_million: str | Decimal | None = None,
    output_usd_per_million: str | Decimal | None = None,
    source_input_weight: str | Decimal = Decimal("0.75"),
    source_output_weight: str | Decimal = Decimal("0.25"),
    target_input_weight: str | Decimal = Decimal("0.8"),
    target_output_weight: str | Decimal = Decimal("0.2"),
) -> dict:
    """Normalize an upstream mix to COG-1, with an honest uncertainty band.

    Epoch's public series uses a 3:1 input/output mix.  Without its separate
    input and output component prices there is no exact conversion to COG-1's
    4:1 mix.  Non-negative component prices bound the possible ratio.
    """
    if isinstance(value, dict):
        source_value = _decimal(
            value.get("usd_per_million_tokens", value.get("usd_per_cog")),
            "anchor value",
        )
    else:
        source_value = _decimal(value, "anchor value")
    si = _decimal(source_input_weight, "source input weight")
    so = _decimal(source_output_weight, "source output weight")
    ti = _decimal(target_input_weight, "target input weight")
    to = _decimal(target_output_weight, "target output weight")
    if si <= 0 or so <= 0 or ti < 0 or to < 0:
        raise ValueError("blend weights must be positive for source and non-negative for target")

    if input_usd_per_million is not None and output_usd_per_million is not None:
        pin = _decimal(input_usd_per_million, "input price")
        pout = _decimal(output_usd_per_million, "output price")
        source_rebuilt = si * pin + so * pout
        if abs(source_rebuilt - source_value) > Decimal("0.000001"):
            raise ValueError("component prices do not reconstruct the published source blend")
        exact = ti * pin + to * pout
        return {
            "usd_per_cog": _six(exact),
            "center": _six(exact),
            "lower": _six(exact),
            "upper": _six(exact),
            "exact": True,
            "source_mix": "3:1 input/output",
            "target_mix": "4:1 input/output",
        }

    ratios = (ti / si, to / so)
    lower = source_value * min(ratios)
    upper = source_value * max(ratios)
    return {
        "usd_per_cog": _six(source_value),
        "center": _six(source_value),
        "lower": _six(lower),
        "upper": _six(upper),
        "exact": False,
        "source_mix": "3:1 input/output",
        "target_mix": "4:1 input/output",
        "uncertainty_reason": (
            "input/output component prices are unavailable; center preserves "
            "the published mixed price and bounds assume non-negative components"
        ),
    }


def divergence(local_usd_per_cog: Any, normalized_anchor: dict | Any) -> dict:
    local = _decimal(local_usd_per_cog, "local fix")
    if isinstance(normalized_anchor, dict):
        anchor = _decimal(
            normalized_anchor.get("usd_per_cog", normalized_anchor.get("center")),
            "normalized anchor",
        )
        lower = normalized_anchor.get("lower")
        upper = normalized_anchor.get("upper")
    else:
        anchor = _decimal(normalized_anchor, "normalized anchor")
        lower = upper = None
    if anchor <= 0:
        raise ValueError("anchor must be positive")
    out = {
        "local_usd_per_cog": _six(local),
        "anchor_usd_per_cog": _six(anchor),
        "ratio_local_to_anchor": _six(local / anchor),
        "difference_pct": _six((local / anchor - Decimal(1)) * Decimal(100)),
    }
    if lower is not None and upper is not None:
        lo, hi = _decimal(lower, "anchor lower"), _decimal(upper, "anchor upper")
        out["inside_anchor_uncertainty"] = lo <= local <= hi
    return out


def refresh(
    url: str,
    destination: str | Path = SNAPSHOT,
    *,
    expected_sha256: str | None = None,
) -> dict:
    """MANUAL ONLY: download, validate, and atomically replace the snapshot."""
    request = urllib.request.Request(url, headers={"User-Agent": "cog-anchor-refresh/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise ValueError(f"snapshot sha256 mismatch: expected {expected_sha256}, got {digest}")
    rows = _read_rows(io.StringIO(raw.decode("utf-8")))
    if not anchor_series(rows):
        raise ValueError("snapshot has no MMLU/GPT-4 anchor rows")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return {"path": str(destination), "sha256": digest, "rows": len(rows)}


def snapshot_manifest() -> dict:
    raw = SNAPSHOT.read_bytes()
    events = anchor_series()
    latest = anchor_at(date.max, events)
    return {
        "snapshot": str(SNAPSHOT.relative_to(HERE)),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "rows": len(events),
        "latest": latest,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot_manifest(), indent=2))

# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""Pure COG settlement over signed, local fixer archives."""

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    _REPO_ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_REPO_ROOT))
    from contracts.canon import canon_sha256
    from contracts.cdo import (
        ROOT,
        SchemaValidationError,
        validate_document,
        verify_obligation_id,
    )
else:
    from .canon import canon_sha256
    from .cdo import ROOT, SchemaValidationError, validate_document, verify_obligation_id

FIX_QUANTUM = Decimal("0.000001")
MONEY_QUANTUM = Decimal("0.01")
TIER_RANK = {
    "bundled-snapshot": 0,
    "external-anchor": 0,
    "venue-quote-live": 1,
    "venue-quote": 2,
    "receipted-depth": 3,
}
LOCAL_TIERS = frozenset(("venue-quote-live", "venue-quote", "receipted-depth"))
INVOICE_SCHEMA = ROOT / "spec" / "invoice-0.1.schema.json"


class SettlementUnavailable(ValueError):
    """No contract-permitted settlement rung can produce a value."""


def _decimal(value: Any, label: str = "value") -> Decimal:
    if isinstance(value, bool) or value is None:
        raise SettlementUnavailable(f"{label} is not a decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise SettlementUnavailable(f"{label} is not a decimal") from exc
    if not result.is_finite():
        raise SettlementUnavailable(f"{label} must be finite")
    return result


def _fix_text(value: Decimal) -> str:
    return format(value.quantize(FIX_QUANTUM, rounding=ROUND_HALF_UP), "f")


def _money_text(value: Decimal) -> str:
    return format(value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP), "f")


def _day(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def _median(values: list[Decimal]) -> Decimal:
    if not values:
        raise SettlementUnavailable("cannot take the median of an empty series")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _tier(payload: dict) -> str:
    explicit = payload.get("tier")
    if explicit in TIER_RANK:
        return explicit
    if payload.get("mode") == "receipt-lite" and payload.get("receipts"):
        return "receipted-depth"
    if payload.get("mode") == "quote":
        return "venue-quote"
    if payload.get("mode") == "quote-live":
        return "venue-quote-live"
    if payload.get("mode") == "anchor":
        return "external-anchor"
    return "bundled-snapshot"


def _verify_archive(path: Path, allowed_signers: Path, namespace: str = "cogfix") -> bool:
    signature = Path(f"{path}.sig")
    if not signature.exists() or not allowed_signers.exists():
        return False
    try:
        subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "verify",
                "-f",
                str(allowed_signers),
                "-I",
                namespace,
                "-n",
                namespace,
                "-s",
                str(signature),
            ],
            input=path.read_bytes(),
            check=True,
            capture_output=True,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def load_series(archive_dir: str | Path, verify_sigs: bool = True) -> list[dict]:
    """Load dated fixer archives and attach verifiable evidence metadata."""
    archive_dir = Path(archive_dir)
    allowed_signers = archive_dir.parent / "allowed_signers"
    series: list[dict] = []
    for path in sorted(archive_dir.glob("*.json")):
        try:
            archive_date = date.fromisoformat(path.stem)
        except ValueError:
            continue
        raw = path.read_bytes()
        try:
            payload = json.loads(raw)
            price = _decimal(payload["fix_usd"], f"{path.name} fix_usd")
        except (json.JSONDecodeError, KeyError, SettlementUnavailable) as exc:
            raise SettlementUnavailable(f"invalid archive {path}: {exc}") from exc
        payload_date = _day(payload["date"])
        if payload_date != archive_date:
            raise SettlementUnavailable(
                f"archive date mismatch: {path.name} contains {payload['date']}"
            )
        sig_ok = (
            _verify_archive(path, allowed_signers) if verify_sigs else True
        )
        series.append(
            {
                "date": payload_date.isoformat(),
                "price": price,
                "fix_usd": _fix_text(price),
                "tier": _tier(payload),
                "publisher": payload.get("publisher", "unknown"),
                "sig_ok": sig_ok,
                "archive_sha256": hashlib.sha256(raw).hexdigest(),
                "archive_path": str(path),
                "anchor_check": payload.get("anchor_check"),
            }
        )
    return series


def _normalized_entry(raw: dict) -> dict:
    entry = dict(raw)
    entry["date"] = _day(entry["date"])
    entry["tier"] = entry.get("tier", "bundled-snapshot")
    entry["publisher"] = entry.get("publisher", "unknown")
    entry["sig_ok"] = bool(entry.get("sig_ok", False))
    value = entry.get("price", entry.get("fix_usd", entry.get("usd_per_cog")))
    entry["price"] = _decimal(value, "series price")
    return entry


def _public_fix(entry: dict, *, price: Decimal | None = None, source: str | None = None) -> dict:
    result = {
        "date": entry["date"].isoformat(),
        "usd_per_cog": _fix_text(price if price is not None else entry["price"]),
        "tier": entry["tier"],
        "publisher": entry["publisher"],
        "sig_ok": entry["sig_ok"],
    }
    for key in ("archive_sha256", "committed_archive_sha256"):
        if entry.get(key):
            result[key] = entry[key]
    if source:
        result["source"] = source
    return result


def _result(
    price: Decimal,
    status: str,
    fixes: list[dict],
    *,
    period_end: date,
    window_days: int,
    min_tier: str,
    provisional: bool = False,
    payable: bool = True,
    true_up_required: bool = False,
    ack_required: bool = False,
    extra: dict | None = None,
) -> dict:
    out = {
        "usd_per_cog": _fix_text(price),
        "status": status,
        "provisional": provisional,
        "payable": payable,
        "true_up_required": true_up_required,
        "ack_required": ack_required,
        "window": {
            "start": (period_end - timedelta(days=window_days - 1)).isoformat(),
            "end": period_end.isoformat(),
            "days": window_days,
            "anchor": "period.end",
        },
        "fixes_used": fixes,
        "n_used": len(fixes),
        "n_expected": 7,
        "min_tier_required": min_tier,
    }
    if extra:
        out.update(extra)
    return out


def _precommitted_anchor(entry: dict) -> tuple[Decimal, dict] | None:
    anchor = entry.get("anchor_check")
    if not isinstance(anchor, dict):
        return None
    normalized = anchor.get("normalized")
    candidates = (
        anchor.get("ratio_adjusted_usd_per_cog"),
        anchor.get("normalized_usd_per_cog"),
        normalized.get("usd_per_cog") if isinstance(normalized, dict) else None,
        normalized.get("center") if isinstance(normalized, dict) else None,
    )
    value = next((item for item in candidates if item is not None), None)
    if value is None:
        return None
    # The precommit is useful only if it was covered by the signed local archive.
    if not entry.get("sig_ok") or not entry.get("archive_sha256"):
        return None
    return _decimal(value, "precommitted anchor"), anchor


def settlement_fix(
    series: list[dict],
    invoice_date: str | date,
    window_days: int = 7,
    min_tier: str = "venue-quote",
    *,
    publishers: list[str] | None = None,
    counterparty_ack: bool = False,
) -> dict:
    """Resolve a period-end Settlement Fix using the unavailability ladder.

    ``invoice_date`` is retained as the public API name for compatibility, but
    callers MUST pass the service period end.  The result records this invariant
    as ``window.anchor == "period.end"``.
    """
    if window_days != 7:
        raise ValueError("COG-SETTLE-1 currently fixes the normal window at 7 days")
    if min_tier not in TIER_RANK or min_tier in ("external-anchor", "bundled-snapshot"):
        raise ValueError(f"invalid settlement min_tier: {min_tier}")
    end = _day(invoice_date)
    entries = sorted((_normalized_entry(item) for item in series), key=lambda item: item["date"])
    eligible = [
        item
        for item in entries
        if item["date"] <= end
        and item["tier"] in LOCAL_TIERS
        and TIER_RANK[item["tier"]] >= TIER_RANK[min_tier]
        and item["sig_ok"]
    ]
    if publishers:
        def publisher_rank(actual: str) -> int | None:
            for index, expected in enumerate(publishers):
                if actual == expected or actual.startswith(f"{expected} "):
                    return index
            return None

        by_day: dict[date, dict] = {}
        for item in eligible:
            rank = publisher_rank(item["publisher"])
            if rank is None:
                continue
            existing = by_day.get(item["date"])
            if existing is None or rank < publisher_rank(existing["publisher"]):
                by_day[item["date"]] = item
        eligible = sorted(by_day.values(), key=lambda item: item["date"])

    start7 = end - timedelta(days=6)
    in7 = [item for item in eligible if start7 <= item["date"] <= end]
    if len(in7) >= 4:
        price = _median([item["price"] for item in in7])
        return _result(
            price,
            "normal",
            [_public_fix(item) for item in in7],
            period_end=end,
            window_days=7,
            min_tier=min_tier,
        )

    start14 = end - timedelta(days=13)
    in14 = [item for item in eligible if start14 <= item["date"] <= end]
    if in14:
        price = _median([item["price"] for item in in14])
        return _result(
            price,
            "degraded-window",
            [_public_fix(item) for item in in14],
            period_end=end,
            window_days=14,
            min_tier=min_tier,
            ack_required=True,
        )

    if not eligible:
        raise SettlementUnavailable(
            f"no signed local fix at or above tier {min_tier}; external data cannot bootstrap settlement"
        )
    last_local = eligible[-1]
    outage_days = (end - last_local["date"]).days
    if outage_days < 45:
        return _result(
            last_local["price"],
            "carry-forward",
            [_public_fix(last_local)],
            period_end=end,
            window_days=14,
            min_tier=min_tier,
            ack_required=True,
            extra={"outage_days": outage_days},
        )

    if outage_days >= 90:
        price = last_local["price"]
        return _result(
            price,
            "converted",
            [_public_fix(last_local)],
            period_end=end,
            window_days=90,
            min_tier=min_tier,
            ack_required=True,
            extra={
                "outage_days": outage_days,
                "conversion": {
                    "usd_per_cog": _fix_text(price),
                    "from_fix_date": last_local["date"].isoformat(),
                },
            },
        )

    precommit = _precommitted_anchor(last_local)
    if precommit is None:
        raise SettlementUnavailable(
            "45-day outage requires a ratio-adjusted anchor value precommitted in "
            "the last signed local archive"
        )
    anchor_price, anchor = precommit
    anchor_fix = {
        "date": last_local["date"].isoformat(),
        "usd_per_cog": _fix_text(anchor_price),
        "tier": "external-anchor",
        "publisher": anchor.get("publisher", "Epoch AI"),
        "sig_ok": True,
        "committed_archive_sha256": last_local["archive_sha256"],
        "source": "ratio-adjusted anchor precommitted in signed local archive",
    }
    return _result(
        anchor_price,
        "anchor-fallback",
        [anchor_fix],
        period_end=end,
        window_days=45,
        min_tier=min_tier,
        provisional=True,
        payable=bool(counterparty_ack),
        true_up_required=True,
        ack_required=True,
        extra={"counterparty_ack": bool(counterparty_ack), "outage_days": outage_days},
    )


def chain_link(
    series_old: list[dict],
    series_new: list[dict],
    overlap_start: str | date,
    overlap_end: str | date,
) -> dict:
    """Median new/old ratio over matching signed local observations."""
    start, end = _day(overlap_start), _day(overlap_end)
    old = {
        item["date"]: item
        for item in (_normalized_entry(raw) for raw in series_old)
        if start <= item["date"] <= end and item["sig_ok"] and item["tier"] in LOCAL_TIERS
    }
    new = {
        item["date"]: item
        for item in (_normalized_entry(raw) for raw in series_new)
        if start <= item["date"] <= end and item["sig_ok"] and item["tier"] in LOCAL_TIERS
    }
    dates = sorted(set(old) & set(new))
    if not dates:
        raise SettlementUnavailable("no matching signed observations in chain-link overlap")
    ratios = []
    for day in dates:
        if old[day]["price"] <= 0:
            raise SettlementUnavailable("chain-link denominator must be positive")
        ratios.append(new[day]["price"] / old[day]["price"])
    factor = _median(ratios)
    return {
        "factor_new_per_old": _fix_text(factor),
        "overlap_start": start.isoformat(),
        "overlap_end": end.isoformat(),
        "observations": len(dates),
        "dates": [day.isoformat() for day in dates],
    }


def _period(value: dict | str) -> dict:
    if isinstance(value, dict):
        result = {"start": _day(value["start"]), "end": _day(value["end"])}
    elif len(value) == 7:
        year, month = map(int, value.split("-"))
        result = {
            "start": date(year, month, 1),
            "end": date(year, month, monthrange(year, month)[1]),
        }
    else:
        single = _day(value)
        result = {"start": single, "end": single}
    if result["end"] < result["start"]:
        raise ValueError("period.end precedes period.start")
    return result


def _prior_price(series: list[dict], before: date, min_tier: str) -> Decimal | None:
    candidates = []
    for raw in series:
        item = _normalized_entry(raw)
        if (
            item["date"] < before
            and item["sig_ok"]
            and item["tier"] in LOCAL_TIERS
            and TIER_RANK[item["tier"]] >= TIER_RANK[min_tier]
        ):
            candidates.append(item)
    return candidates[-1]["price"] if candidates else None


def _apply_collar(
    price: Decimal, collar: dict, prior: Decimal | None
) -> tuple[Decimal, list[dict]]:
    adjusted = price
    operations: list[dict] = []
    floor = collar.get("floor")
    ceiling = collar.get("ceiling")
    cap = collar.get("period_change_cap_pct")
    if floor is not None:
        floor_d = _decimal(floor, "collar floor")
        if adjusted < floor_d:
            operations.append({"operation": "floor", "value": _fix_text(floor_d)})
            adjusted = floor_d
    if ceiling is not None:
        ceiling_d = _decimal(ceiling, "collar ceiling")
        if adjusted > ceiling_d:
            operations.append({"operation": "ceiling", "value": _fix_text(ceiling_d)})
            adjusted = ceiling_d
    if cap is not None:
        if prior is None:
            raise SettlementUnavailable(
                "period_change_cap_pct requires a prior eligible local fix"
            )
        cap_d = _decimal(cap, "period change cap") / Decimal(100)
        low, high = prior * (Decimal(1) - cap_d), prior * (Decimal(1) + cap_d)
        capped = min(max(adjusted, low), high)
        if capped != adjusted:
            operations.append(
                {
                    "operation": "period_change_cap_pct",
                    "value": str(cap),
                    "prior_usd_per_cog": _fix_text(prior),
                }
            )
            adjusted = capped
    return adjusted, operations


def _invoice_digest(document: dict) -> str:
    return canon_sha256(document, exclude_keys=("signatures", "invoice_id"))


def _indexed_total(document: dict) -> Decimal:
    return sum(
        (
            _decimal(line["amount_usd"], "indexed amount")
            for line in document["lines"]
            if line["kind"] == "indexed"
        ),
        Decimal(0),
    )


def invoice(
    cdo: dict,
    period: dict | str,
    series: list[dict],
    *,
    prior_invoices: list[dict] | None = None,
    recompute_invoice_path: str = "invoice.json",
    recompute_archive_dir: str = "fixer/archive",
    recompute_allowed_signers: str | None = None,
) -> dict:
    """Recompute a deterministic, unsigned invoice from a CDO and local series."""
    validate_document(cdo)
    if not verify_obligation_id(cdo):
        raise SchemaValidationError("obligation_id does not match the canonical CDO")
    service_period = _period(period)
    settlement_terms = cdo["settlement"]
    fix = settlement_fix(
        series,
        service_period["end"],
        min_tier=settlement_terms["min_tier"],
        publishers=settlement_terms.get("publishers"),
        counterparty_ack=bool(settlement_terms.get("counterparty_ack", False)),
    )
    raw_price = _decimal(fix["usd_per_cog"], "settlement fix")
    prior = _prior_price(series, service_period["start"], settlement_terms["min_tier"])
    applied_price, collar_ops = _apply_collar(
        raw_price, settlement_terms.get("collar") or {}, prior
    )
    fix["uncollared_usd_per_cog"] = _fix_text(raw_price)
    fix["usd_per_cog"] = _fix_text(applied_price)
    fix["collar_operations"] = collar_ops

    lines: list[dict] = []
    remaining_cogs = Decimal(0)
    for leg in cdo["legs"]:
        if leg["kind"] == "fixed":
            amount = _decimal(leg["USD"], "fixed USD leg")
            lines.append({"kind": "fixed", "amount_usd": _money_text(amount)})
        else:
            quantity = _decimal(leg["quantity"], "cog quantity")
            remaining_cogs += quantity
            amount = quantity * applied_price
            lines.append(
                {
                    "kind": "indexed",
                    "quantity_cog": format(quantity, "f"),
                    "usd_per_cog": _fix_text(applied_price),
                    "amount_usd": _money_text(amount),
                }
            )

    if fix["status"] == "converted":
        converted = remaining_cogs * applied_price
        fix["conversion"].update(
            {
                "remaining_cogs": format(remaining_cogs, "f"),
                "converted_usd": _money_text(converted),
            }
        )

    # A resumed local publisher can reconcile explicitly supplied provisional
    # invoices.  References make the signed delta independently auditable.
    for old in prior_invoices or []:
        if not old.get("settlement", {}).get("true_up_required"):
            continue
        replacement = invoice(cdo, old["period"], series)
        if replacement["settlement"]["provisional"]:
            continue
        delta = _indexed_total(replacement) - _indexed_total(old)
        lines.append(
            {
                "kind": "true_up",
                "amount_usd": _money_text(delta),
                "reference_invoice_id": old["invoice_id"],
                "reference_obligation_id": old["obligation_id"],
                "reference_period": old["period"],
            }
        )

    subtotal = sum((_decimal(line["amount_usd"]) for line in lines), Decimal(0))
    evidence = []
    for used in fix["fixes_used"]:
        digest = used.get("archive_sha256") or used.get("committed_archive_sha256")
        if digest:
            evidence.append(
                {
                    "date": used["date"],
                    "archive_sha256": digest,
                    "sig_ok": bool(used["sig_ok"]),
                    "publisher": used["publisher"],
                    "tier": used["tier"],
                }
            )
    document = {
        "invoice_version": "0.1",
        "invoice_id": "",
        "obligation_id": cdo["obligation_id"],
        "period": {
            "start": service_period["start"].isoformat(),
            "end": service_period["end"].isoformat(),
        },
        "unit": {
            "basket": cdo["unit"]["basket"],
            "spec_sha256": cdo["unit"]["spec_sha256"],
        },
        "settlement": fix,
        "lines": lines,
        "subtotal_usd": _money_text(subtotal),
        "amount_due_usd": _money_text(subtotal) if fix["payable"] else None,
        "archive_evidence": evidence,
        "recompute": " ".join(
            [
                "python3",
                "contracts/settle.py",
                "--verify",
                shlex.quote(recompute_invoice_path),
                "--archive",
                shlex.quote(recompute_archive_dir),
            ]
            + (
                ["--allowed-signers", shlex.quote(recompute_allowed_signers)]
                if recompute_allowed_signers
                else []
            )
        ),
        "signatures": [],
    }
    document["invoice_id"] = f"urn:cog:invoice:{_invoice_digest(document)}"
    schema = json.loads(INVOICE_SCHEMA.read_text())
    validate_document(document, schema=schema)
    return document


def verify_invoice(
    document: dict | str | Path,
    archive_dir: str | Path,
    *,
    invoice_allowed_signers: str | Path | None = None,
) -> dict:
    """Verify canonical identity, arithmetic, archive hashes, and signatures."""
    path = Path(document) if isinstance(document, (str, Path)) else None
    invoice_doc = json.loads(path.read_text()) if path else document
    errors: list[str] = []
    try:
        validate_document(invoice_doc, schema=json.loads(INVOICE_SCHEMA.read_text()))
    except (SchemaValidationError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"schema: {exc}")
    expected_id = f"urn:cog:invoice:{_invoice_digest(invoice_doc)}"
    if invoice_doc.get("invoice_id") != expected_id:
        errors.append("invoice_id does not match canonical invoice")
    try:
        for line in invoice_doc["lines"]:
            if line["kind"] == "indexed":
                expected_line = _decimal(line["quantity_cog"]) * _decimal(
                    line["usd_per_cog"]
                )
                if _money_text(expected_line) != line["amount_usd"]:
                    errors.append("indexed line does not equal quantity times fix")
        line_total = sum(
            (_decimal(line["amount_usd"]) for line in invoice_doc["lines"]), Decimal(0)
        )
        if _money_text(line_total) != invoice_doc.get("subtotal_usd"):
            errors.append("subtotal does not equal line amounts")
        expected_due = (
            _money_text(line_total)
            if invoice_doc.get("settlement", {}).get("payable")
            else None
        )
        if invoice_doc.get("amount_due_usd") != expected_due:
            errors.append("amount_due_usd disagrees with payable status")
    except (KeyError, SettlementUnavailable) as exc:
        errors.append(f"arithmetic: {exc}")

    try:
        archives = load_series(archive_dir, verify_sigs=True)
        available = {
            item["archive_sha256"]: item for item in archives if item["sig_ok"]
        }
        for evidence in invoice_doc.get("archive_evidence", []):
            if evidence["archive_sha256"] not in available:
                errors.append(
                    f"archive evidence unavailable or signature invalid: "
                    f"{evidence['archive_sha256']}"
                )
        settlement = invoice_doc.get("settlement", {})
        recomputed = settlement_fix(
            archives,
            invoice_doc["period"]["end"],
            min_tier=settlement.get("min_tier_required", "venue-quote"),
            counterparty_ack=bool(settlement.get("counterparty_ack", False)),
        )
        claimed_raw = settlement.get(
            "uncollared_usd_per_cog", settlement.get("usd_per_cog")
        )
        if recomputed["usd_per_cog"] != claimed_raw:
            errors.append("Settlement Fix does not recompute from signed archives")
        for field in (
            "status",
            "provisional",
            "payable",
            "true_up_required",
            "ack_required",
            "window",
            "n_used",
            "min_tier_required",
        ):
            if recomputed.get(field) != settlement.get(field):
                errors.append(f"settlement field {field!r} does not recompute")
        recomputed_hashes = {
            used.get("archive_sha256") or used.get("committed_archive_sha256")
            for used in recomputed["fixes_used"]
        } - {None}
        claimed_hashes = {
            item.get("archive_sha256")
            for item in invoice_doc.get("archive_evidence", [])
        } - {None}
        if recomputed_hashes != claimed_hashes:
            errors.append("archive evidence set does not match recomputed Settlement Fix")
    except SettlementUnavailable as exc:
        errors.append(f"archive: {exc}")

    signature_ok = None
    if path is not None and Path(f"{path}.sig").exists():
        invoice_trust = (
            Path(invoice_allowed_signers)
            if invoice_allowed_signers is not None
            else Path(archive_dir).parent / "allowed_signers"
        )
        signature_ok = _verify_archive(
            path, invoice_trust, namespace="cog-invoice"
        )
        if not signature_ok:
            errors.append("detached invoice signature failed verification")
    return {
        "valid": not errors,
        "invoice_id": invoice_doc.get("invoice_id"),
        "signature_ok": signature_ok,
        "errors": errors,
    }


def sign_invoice(path: str | Path) -> bool:
    """Sign an already-written invoice with the shared fixer signer."""
    fixer_dir = ROOT / "fixer"
    if str(fixer_dir) not in sys.path:
        sys.path.insert(0, str(fixer_dir))
    import fixerd  # noqa: E402

    return fixerd.sign(Path(path), namespace="cog-invoice")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Settle or independently verify a COG invoice from local archives."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--verify", metavar="INVOICE")
    action.add_argument("--settle", metavar="CDO")
    action.add_argument("--sign", metavar="INVOICE")
    parser.add_argument("--archive", default="fixer/archive")
    parser.add_argument("--period", help="settlement period (YYYY-MM or JSON start/end)")
    parser.add_argument("--output", help="write a settled invoice to this path")
    parser.add_argument("--allowed-signers", help="trust file for a detached invoice signature")
    parser.add_argument(
        "--sign-output",
        action="store_true",
        help="sign --output with the configured shared signer",
    )
    args = parser.parse_args(argv)

    if args.sign:
        if not sign_invoice(args.sign):
            parser.error("invoice signing failed")
        return 0
    if args.verify:
        report = verify_invoice(
            args.verify,
            args.archive,
            invoice_allowed_signers=args.allowed_signers,
        )
        print(json.dumps(report, indent=2))
        return 0 if report["valid"] else 1

    if not args.period:
        parser.error("--settle requires --period")
    cdo_document = json.loads(Path(args.settle).read_text())
    try:
        period: dict | str = json.loads(args.period)
    except json.JSONDecodeError:
        period = args.period
    output = args.output or "invoice.json"
    document = invoice(
        cdo_document,
        period,
        load_series(args.archive),
        recompute_invoice_path=output,
        recompute_archive_dir=args.archive,
        recompute_allowed_signers=args.allowed_signers,
    )
    encoded = json.dumps(document, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(encoded)
        if args.sign_output and not sign_invoice(args.output):
            parser.error("settled invoice was written but signing failed")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

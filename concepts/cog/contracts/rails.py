# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""Reference denomination emitters for x402 and AP2.

These functions do not implement either protocol.  They preserve the payment
rail and attach enough COG metadata for a counterparty to recompute the USD
amount carried by that rail.
"""

from copy import deepcopy
from typing import Any

from .canon import canon_sha256


def denomination(
    *,
    basket: str,
    spec_sha256: str,
    quantity: str,
    usd_per_cog: str,
    rule: str,
    publisher: str,
    fix_window_end: str,
    invoice_sha256: str,
) -> dict:
    return {
        "unit": "cog",
        "basket": basket,
        "spec_sha256": spec_sha256,
        "quantity": str(quantity),
        "resolved": {
            "usd_per_cog": str(usd_per_cog),
            "rule": rule,
            "publisher": publisher,
            "fix_window_end": fix_window_end,
            "invoice_sha256": invoice_sha256,
        },
    }


def from_invoice(invoice: dict, quantity: str, publisher: str | None = None) -> dict:
    fixes = invoice["settlement"].get("fixes_used") or []
    selected_publisher = publisher or (
        fixes[0].get("publisher") if fixes else "unavailable"
    )
    invoice_sha = invoice["invoice_id"].rsplit(":", 1)[-1]
    if invoice_sha != canon_sha256(
        invoice, exclude_keys=("signatures", "invoice_id")
    ):
        raise ValueError("invoice_id does not match the canonical invoice")
    return denomination(
        basket=invoice["unit"]["basket"],
        spec_sha256=invoice["unit"]["spec_sha256"],
        quantity=quantity,
        usd_per_cog=invoice["settlement"]["usd_per_cog"],
        rule=invoice["settlement"]["status"],
        publisher=selected_publisher,
        fix_window_end=invoice["period"]["end"],
        invoice_sha256=invoice_sha,
    )


def emit_x402(payment: dict, denom: dict) -> dict:
    """Attach denomination to every x402 acceptance without changing assets."""
    out = deepcopy(payment)
    accepts = out.get("accepts")
    if not isinstance(accepts, list) or not accepts:
        raise ValueError("x402 payload requires a non-empty accepts array")
    for acceptance in accepts:
        extra = acceptance.setdefault("extra", {})
        if not isinstance(extra, dict):
            raise ValueError("x402 accepts[].extra must be an object")
        extra["denomination"] = deepcopy(denom)
    return out


def emit_ap2(mandate: dict, denom: dict) -> dict:
    """Attach denomination directly to an AP2 mandate."""
    out = deepcopy(mandate)
    target: dict[str, Any]
    if "mandate" in out:
        if not isinstance(out["mandate"], dict):
            raise ValueError("AP2 mandate must be an object")
        target = out["mandate"]
    else:
        target = out
    target["denomination"] = deepcopy(denom)
    return out

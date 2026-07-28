# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""Construction and validation of Cog-Denominated Obligations (CDOs)."""

import json
import re
import sys
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .canon import canon_sha256

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "spec" / "cdo-0.1.schema.json"
HASHES_PATH = ROOT / "spec" / "SPEC-HASHES.json"
CDO_VERSION = "0.1"


class SchemaValidationError(ValueError):
    """A document failed the bundled, deterministic schema subset."""


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        Decimal(str(value))
        return True
    except (InvalidOperation, TypeError, ValueError):
        return False


def _resolve_ref(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise SchemaValidationError(f"unsupported external schema reference: {ref}")
    target: Any = root
    for part in ref[2:].split("/"):
        target = target[part.replace("~1", "/").replace("~0", "~")]
    return target


def _validate(value: Any, schema: dict, root: dict, path: str, errors: list[str]) -> None:
    """Validate the JSON-Schema subset used by the two COG schemas."""
    if "$ref" in schema:
        _validate(value, _resolve_ref(root, schema["$ref"]), root, path, errors)
        return
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: not one of {schema['enum']!r}")

    branches = schema.get("oneOf") or schema.get("anyOf")
    if branches:
        matches = 0
        for branch in branches:
            branch_errors: list[str] = []
            _validate(value, branch, root, path, branch_errors)
            if not branch_errors:
                matches += 1
        required = 1 if "oneOf" in schema else None
        if (required is not None and matches != required) or (
            required is None and matches == 0
        ):
            errors.append(f"{path}: does not match the required schema branch")
        return

    expected = schema.get("type")
    type_ok = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": _is_number(value),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, True)
    if not type_ok:
        errors.append(f"{path}: expected {expected}")
        return

    if isinstance(value, dict):
        required_keys = schema.get("required", ())
        for key in required_keys:
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected property {key!r}")
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], root, f"{path}.{key}", errors)

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: requires at least {schema['minItems']} item(s)")
        if schema.get("uniqueItems"):
            serial = [json.dumps(item, sort_keys=True) for item in value]
            if len(serial) != len(set(serial)):
                errors.append(f"{path}: items must be unique")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _validate(item, item_schema, root, f"{path}[{index}]", errors)

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is too short")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            errors.append(f"{path}: does not match {schema['pattern']!r}")
        if schema.get("format") == "date":
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"{path}: is not an ISO date")

    if _is_number(value):
        number = Decimal(str(value))
        if "minimum" in schema and number < Decimal(str(schema["minimum"])):
            errors.append(f"{path}: is below minimum {schema['minimum']}")
        if "exclusiveMinimum" in schema and number <= Decimal(str(schema["exclusiveMinimum"])):
            errors.append(f"{path}: must be greater than {schema['exclusiveMinimum']}")


def validate_document(document: dict, schema: dict | None = None) -> dict:
    schema = schema or json.loads(SCHEMA_PATH.read_text())
    errors: list[str] = []
    _validate(document, schema, schema, "$", errors)
    if errors:
        raise SchemaValidationError("; ".join(errors))
    return document


def obligation_digest(document: dict) -> str:
    """Digest the obligation body without signatures or its self-referential id."""
    return canon_sha256(document, exclude_keys=("signatures", "obligation_id"))


def verify_obligation_id(document: dict) -> bool:
    return document.get("obligation_id") == f"urn:cog:cdo:{obligation_digest(document)}"


def _default_unit() -> dict:
    hashes = json.loads(HASHES_PATH.read_text())
    return {
        "basket": "COG-1",
        "spec_uri": "spec/COG-1.md",
        "spec_sha256": hashes["COG-1.md"],
    }


def draft_obligation(
    *,
    parties: dict,
    legs: list[dict],
    term: dict,
    unit: dict | None = None,
    settlement: dict | None = None,
    versioning: dict | None = None,
    metering: dict | None = None,
    signatures: list | None = None,
) -> dict:
    """Build, validate, and identify a CDO.

    Monetary and cog quantities are represented as decimal strings.  This keeps
    their exact lexical value across JSON implementations and prevents binary
    floating-point from entering settlement.

    Optional basis-risk and administration terms (``region``,
    ``correction_window_days``, and ``on_publisher_cessation``) are copied only
    when explicitly supplied in ``settlement``.  They intentionally have no
    implicit defaults: omission is a valid contractual choice and historical
    signed CDO bytes remain unchanged.
    """
    default_settlement = {
        "currency": "USD",
        "fix_rule": "median-7d",
        "publishers": ["proofofwork-agency/cog"],
        "multi_publisher_rule": "priority-order",
        "min_tier": "venue-quote",
        "collar": {
            "floor": None,
            "ceiling": None,
            "period_change_cap_pct": None,
        },
        "rounding": "ROUND_HALF_UP",
        "rail": "invoice",
    }
    if settlement:
        default_settlement.update(deepcopy(settlement))
        if settlement.get("collar"):
            collar = {
                "floor": None,
                "ceiling": None,
                "period_change_cap_pct": None,
            }
            collar.update(deepcopy(settlement["collar"]))
            default_settlement["collar"] = collar

    document = {
        "cdo_version": CDO_VERSION,
        "obligation_id": "",
        "parties": deepcopy(parties),
        "unit": deepcopy(unit or _default_unit()),
        "legs": deepcopy(legs),
        "term": deepcopy(term),
        "settlement": default_settlement,
        "versioning": deepcopy(versioning or {
            "on_basket_retirement": "chain_link",
            "min_overlap_days": 180,
        }),
        "signatures": deepcopy(signatures or []),
    }
    if metering is not None:
        document["metering"] = deepcopy(metering)
    document["obligation_id"] = f"urn:cog:cdo:{obligation_digest(document)}"
    validate_document(document)
    if not verify_obligation_id(document):
        raise SchemaValidationError("obligation_id does not identify the canonical obligation")
    return document


def sign_obligation(path: str | Path) -> bool:
    """Sign an already-written CDO through the one shared SSH signer."""
    fixer_dir = ROOT / "fixer"
    if str(fixer_dir) not in sys.path:
        sys.path.insert(0, str(fixer_dir))
    import fixerd  # noqa: E402

    return fixerd.sign(Path(path), namespace="cog-cdo")

# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""Canonical JSON used by COG document identifiers and fingerprints."""

import hashlib
import json
from collections.abc import Iterable
from typing import Any


def _without_keys(value: Any, excluded: frozenset[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_keys(item, excluded)
            for key, item in value.items()
            if key not in excluded
        }
    if isinstance(value, list):
        return [_without_keys(item, excluded) for item in value]
    if isinstance(value, tuple):
        return [_without_keys(item, excluded) for item in value]
    return value


def canonical_json(obj: Any, exclude_keys: Iterable[str] = ("signatures",)) -> str:
    """Return deterministic, whitespace-free JSON.

    Excluded keys are removed recursively.  Signatures are excluded by default
    so adding an enveloped signature does not change the identifier of the
    document it authenticates.
    """
    clean = _without_keys(obj, frozenset(exclude_keys))
    return json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_bytes(obj: Any, exclude_keys: Iterable[str] = ("signatures",)) -> bytes:
    return canonical_json(obj, exclude_keys=exclude_keys).encode("utf-8")


def canon_sha256(obj: Any, exclude_keys: Iterable[str] = ("signatures",)) -> str:
    return hashlib.sha256(canonical_bytes(obj, exclude_keys=exclude_keys)).hexdigest()

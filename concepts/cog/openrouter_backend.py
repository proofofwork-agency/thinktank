#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""Shared OpenRouter-dialect endpoint, credential, and price-provenance rules."""

import os
import urllib.error
from urllib.parse import urlsplit

CANONICAL_METERED_BASE = "https://openrouter.ai/api/v1"
PRICE_PROVENANCE_VALUES = frozenset(("metered", "modelled"))


class RequestFailed(RuntimeError):
    """An OpenRouter-dialect request failed with user-actionable context."""


def request_failed(action: str, url: str, error: Exception) -> RequestFailed:
    """Build a concise provider error while preserving the original as its cause."""
    if isinstance(error, urllib.error.HTTPError):
        detail = f"HTTP {error.code} {error.reason}"
    elif isinstance(error, urllib.error.URLError):
        detail = f"URL error: {error.reason}"
    else:
        detail = str(error)
    return RequestFailed(f"{action} at {url}: {detail}")


def base_url(environ=None) -> str:
    """Return a normalized OpenRouter-dialect base URL."""
    environ = os.environ if environ is None else environ
    value = environ.get("COG_OPENROUTER_BASE", CANONICAL_METERED_BASE).strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("COG_OPENROUTER_BASE must be an absolute http(s) URL")
    return value


def is_canonical_metered_base(value: str) -> bool:
    return value.rstrip("/") == CANONICAL_METERED_BASE


def api_key(environ=None) -> str | None:
    """Prefer the COG-scoped credential, falling back to the legacy variable."""
    environ = os.environ if environ is None else environ
    return environ.get("COG_API_KEY") or environ.get("OPENROUTER_API_KEY")


def resolve_price_provenance(value: str, environ=None) -> tuple[str, str]:
    """Return (provenance, basis), validating any explicit operator assertion."""
    environ = os.environ if environ is None else environ
    asserted = environ.get("COG_PRICE_PROVENANCE")
    if asserted is not None:
        asserted = asserted.strip().lower()
        if asserted not in PRICE_PROVENANCE_VALUES:
            allowed = ", ".join(sorted(PRICE_PROVENANCE_VALUES))
            raise ValueError(f"COG_PRICE_PROVENANCE must be one of: {allowed}")
        return asserted, "operator assertion via COG_PRICE_PROVENANCE"
    if is_canonical_metered_base(value):
        return "metered", "canonical OpenRouter endpoint"
    return "modelled", "non-canonical endpoint default"


def authorization_headers(key: str | None) -> dict[str, str]:
    """Omit Authorization for local OpenRouter-dialect endpoints that need no key."""
    return {"Authorization": f"Bearer {key}"} if key else {}

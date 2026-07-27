# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""Negotiation rider templates stored as reviewable Markdown data."""

from pathlib import Path
from string import Template
from typing import Any

TEMPLATE_DIR = Path(__file__).with_name("riders")
NAMES = ("msa-hybrid", "msa-collar", "agent-sla", "rfp-clause", "metered-trueup")


def render(name: str, values: dict[str, Any] | None = None, **kwargs: Any) -> str:
    """Render a bundled rider with ``string.Template``.

    ``safe_substitute`` is intentionally not used: an unbound legal term is a
    defect and should fail loudly instead of leaking ``$placeholder`` text into
    a negotiation draft.
    """
    if name not in NAMES:
        raise ValueError(f"unknown rider {name!r}; choose one of {', '.join(NAMES)}")
    context = {
        "provider": "Provider",
        "client": "Client",
        "fixed_usd_per_period": "0.00",
        "cogs_per_period": "0",
        "term": "12 months",
        "period": "calendar month",
        "fix_usd": "not resolved",
        "estimated_total_usd": "not resolved",
        "fix_source": "not resolved",
        "qualification": "unknown",
        "receipts": "0",
        "basis_warning": "",
        "floor": "none",
        "ceiling": "none",
        "period_change_cap_pct": "none",
        "agent_service": "the agent service",
        "service_level": "the agreed service level",
        "rfp_name": "this procurement",
        "meter_name": "qualifying blended tokens",
        "included_cogs": "0",
        "true_up_timing": "the next invoice",
    }
    if values:
        context.update(values)
    context.update(kwargs)
    source = (TEMPLATE_DIR / f"{name}.md").read_text()
    return Template(source).substitute({key: str(value) for key, value in context.items()})

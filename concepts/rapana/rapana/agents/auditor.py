from __future__ import annotations

import time
from decimal import Decimal

from rapana.agents.base import Agent
from rapana.journal.ledger import DecisionLedger


class ComplianceAuditor(Agent):
    """Compliance / Ledger Auditor.

    Writes every fleet event (signals, debate theses, proposals, risk decisions,
    fills) to the append-only, hash-chained DecisionLedger so each cycle is
    fully reconstructable. Also produces the daily digest the human reviews.
    """

    role = "compliance_auditor"

    def __init__(self, ledger: DecisionLedger) -> None:
        self.ledger = ledger

    def record(self, kind: str, payload: dict) -> None:
        clean = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in payload.items()}
        self.ledger.append(kind, clean)

    def digest(self, events: list[dict]) -> str:
        fills = [e for e in events if e["kind"] == "fill"]
        vetoes = [e for e in events if e["kind"] == "risk_veto"]
        proposals = [e for e in events if e["kind"] == "trade_proposal"]
        lines = [
            "=== RAPANA DAILY DIGEST ===",
            f"timestamp      : {int(time.time())}",
            f"proposals      : {len(proposals)}",
            f"fills executed : {len(fills)}",
            f"risk vetoes    : {len(vetoes)}",
        ]
        for f in fills[-5:]:
            lines.append(f"  fill: {f['data']}")
        for v in vetoes[-5:]:
            lines.append(f"  veto: {v['data'].get('reason')}")
        # Recent non-empty LLM thesis annotations (purely explanatory prose).
        debates = [e for e in events if e["kind"] == "debate"]
        seen: set[str] = set()
        thesis_lines: list[str] = []
        for e in debates:
            for key in ("bull_comment", "bear_comment"):
                text = (e.get("data") or {}).get(key, "")
                text = (text or "").strip()
                if text and text not in seen and not text.startswith("(brain error"):
                    seen.add(text)
                    thesis_lines.append(f"  thesis: {text}")
            if len(thesis_lines) >= 3:
                break
        lines.extend(thesis_lines[:3])
        return "\n".join(lines)

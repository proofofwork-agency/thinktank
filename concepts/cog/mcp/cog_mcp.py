#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""cog-fix MCP server — puts the price of intelligence in every agent's hands.

A minimal Model Context Protocol server (stdio, JSON-RPC 2.0, one message per
line) with zero dependencies. Register with Claude Code:

  claude mcp add cog-fix -- python3 /path/to/cog/mcp/cog_mcp.py

Tools:
  get_fix           today's COG-1 fix (published fixer/fix.json > live quote > bundled snapshot)
  price_in_cogs     convert a USD amount or a blended-token workload into cogs
  reprice_contract  fixed-USD vs cog-indexed contract comparison (hybrid leg supported)
  generate_sla      hybrid cog-denominated SLA rider text (template, not legal advice)
"""

import json
import math
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cogfix"))
sys.path.insert(0, str(ROOT / "fixer"))
import cogfix  # noqa: E402
import fixerd  # noqa: E402
from anchor import anchor_at, normalize_blend  # noqa: E402
from contracts import cdo as cdo_contract  # noqa: E402
from contracts import riders  # noqa: E402
from contracts.settle import (  # noqa: E402
    LOCAL_TIERS,
    _tier as classify_evidence_tier,
    invoice as settle_cdo_invoice,
    load_series,
    settlement_fix as resolve_settlement_fix,
    verify_invoice as verify_cog_invoice,
)


# ---------------------------------------------------------------- fix lookup

def current_fix():
    """Best available fix across five explicitly labeled evidence rungs.

    Every result carries the basis it actually earned — age, qualification, and
    receipt count — so a caller can tell a receipted fix from a provisional
    posted-price quote. A corrupt or unreadable fix.json falls through to the
    live quote rather than propagating an exception.
    """
    fix_file = ROOT / "fixer" / "fix.json"
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        p = json.loads(fix_file.read_text())
        fix_value = float(p["fix_usd"])
        if not math.isfinite(fix_value) or fix_value <= 0:
            raise ValueError("published fix_usd must be finite and positive")
        age = (date.fromisoformat(today) - date.fromisoformat(p["date"])).days
        receipts = len(p.get("receipts") or [])
        tier = classify_evidence_tier(p)
        provenance = {
            "publisher": p.get("publisher", "unknown"),
            "artifact": "fixer/fix.json",
        }
        provenance.update(p.get("provenance") or {})
        provenance["settleable"] = tier in LOCAL_TIERS
        stale = age < 0 or age > 1
        return {"fix_usd": fix_value, "date": p["date"], "mode": p["mode"],
                "source": "published fixer/fix.json"
                          + (f" (unusable age {age}d — rerun fixerd)" if stale else ""),
                "floor_usd": p.get("floor_usd"),
                "age_days": age, "stale": stale,
                "qualification": (p.get("qualification") or {}).get("basis", "unknown"),
                "receipts": receipts, "tier": tier,
                "provenance": provenance}
    except (OSError, ValueError, KeyError):
        pass  # missing, corrupt, or malformed — fall through to the live quote
    try:
        quotes = fixerd.posted_quotes(fixerd.fetch_models())
        if len(quotes) < 3:
            raise ValueError("fewer than 3 qualifying quotes in feed")
        fix = statistics.median(r["blended_usd_per_M"] for r in quotes[:3])
        return {"fix_usd": round(fix, 6), "date": today, "mode": "quote-live",
                "source": "live OpenRouter posted prices (unreceipted)",
                "floor_usd": quotes[0]["blended_usd_per_M"],
                "age_days": 0, "stale": False,
                "qualification": "assumed static allowlist (no exam run)", "receipts": 0,
                "tier": "venue-quote-live",
                "provenance": {"provider": "OpenRouter", "network": "live"}}
    except Exception:
        pass
    try:
        event = anchor_at(today)
        normalized = normalize_blend(event)
        age = (date.fromisoformat(today) - date.fromisoformat(event["date"])).days
        return {
            "fix_usd": float(normalized["usd_per_cog"]),
            "date": event["date"],
            "mode": "external-anchor",
            "source": "Epoch AI vendored snapshot (CC-BY; 3:1 mix, normalized with uncertainty)",
            "floor_usd": None,
            "age_days": age,
            "stale": True,
            "qualification": "external MMLU/GPT-4 anchor; not COG exam-qualified",
            "receipts": 0,
            "tier": "external-anchor",
            "provenance": {
                "provider": "Epoch AI",
                "artifact": "anchor/snapshot/epoch_llm_inference_prices.csv",
                "model": event["model"],
                "lookup": "step-function",
                "normalization": normalized,
                "settleable": False,
            },
        }
    except Exception:
        s = cogfix.official_series()
        return {"fix_usd": s[-1][1], "date": "2026-06", "mode": "bundled",
                "source": "bundled snapshot (offline fallback)", "floor_usd": None,
                "age_days": None, "stale": True,
                "qualification": "assumed static allowlist (no exam run)", "receipts": 0,
                "tier": "bundled-snapshot",
                "provenance": {"artifact": "cogfix/data.json", "settleable": False}}


def unit_description(f):
    """Describe the unit at the confidence this particular fix actually earned.

    The COG-1 spec defines the cog as *depth-verified*; claiming that label for a
    posted-price quote with no receipts is exactly the LIBOR failure the
    whitepaper argues against, so the wording tracks the evidence.
    """
    evidence_tier = classify_evidence_tier(f)
    price = {
        "receipted-depth": "depth-verified",
        "receipted-lite": "receipted execution (LIMITED DEPTH; does not satisfy K/N)",
        "venue-quote": "posted-price (PROVISIONAL, unreceipted)",
        "venue-quote-live": "live posted-price (PROVISIONAL, unreceipted)",
        "external-anchor": "external research anchor (NON-SETTLEABLE)",
        "bundled-snapshot": "bundled historical snapshot (NON-SETTLEABLE)",
    }.get(evidence_tier, "unknown evidence")
    tier = ("exam-qualified" if str(f.get("qualification", "")).startswith("exam-qualified")
            else "assumed-qualifying (no exam administered)")
    return (f"1 cog = {price} price of 1M blended tokens (800k in / 200k out) "
            f"at frozen GPT-4-class capability; tier basis: {tier}")


# ---------------------------------------------------------------- tools

def t_get_fix(_args):
    f = current_fix()
    f["unit"] = unit_description(f)
    return f


def t_price_in_cogs(args):
    f = current_fix()
    out = {"fix_usd_per_cog": f["fix_usd"], "fix_source": f["source"]}
    if args.get("usd") is not None:
        usd = float(args["usd"])
        out["usd"] = usd
        out["cogs_for_usd"] = round(usd / f["fix_usd"], 2)
        out["meaning"] = f"${usd:,.2f} buys ~{out['cogs_for_usd']:,.0f} reference workloads today"
    if args.get("blended_tokens") is not None:
        tok = float(args["blended_tokens"])
        cogs = tok / 1e6
        out["blended_tokens"] = tok
        out["workload_cogs"] = round(cogs, 4)
        out["workload_usd_today"] = round(cogs * f["fix_usd"], 4)
        out["note"] = ("a job's size in cogs is fix-independent (tokens/1M at qualifying tier); "
                       "only its USD settlement value moves with the fix")
    if "usd" not in out and "blended_tokens" not in out:
        return {"error": "pass usd and/or blended_tokens"}
    return out


def t_reprice_contract(args):
    usd = float(args["usd_per_month"])
    months = int(args["months"])
    start = args["start"]
    fixed = float(args.get("fixed_usd_per_month", 0))
    total_usd, total_cog = cogfix.reprice(usd, months, start, fixed=fixed, quiet=True)
    f0, _ = cogfix.fix_at(start)
    cogs = (usd - fixed) / f0
    rows = []
    for k in (list(range(months))[:3] + list(range(months))[-3:] if months > 6 else range(months)):
        ym = cogfix.ym_add(start, k)
        fx, _ = cogfix.fix_at(ym)
        rows.append({"month": ym, "fix": round(fx, 4), "indexed_invoice": round(fixed + cogs * fx, 2)})
    return {
        "deal": f"${usd:,.0f}/mo x {months}mo from {start}"
                + (f" as ${fixed:,.0f} fixed + {cogs:,.0f} cogs/mo" if fixed else f" as {cogs:,.0f} cogs/mo"),
        "signing_fix_usd": round(f0, 6),
        "fixed_usd_total": round(total_usd, 2),
        "cog_indexed_total": round(total_cog, 2),
        "hidden_short_usd": round(total_usd - total_cog, 2),
        "hidden_short_pct": round(100 * (total_usd - total_cog) / total_usd, 1),
        "sample_months": rows,
        "caveat": "fix interpolated from documented backtest; months beyond last data point hold flat",
    }


def t_generate_sla(args):
    provider = args.get("provider", "Provider")
    client = args.get("client", "Client")
    fixed = float(args.get("fixed_usd_per_month", 0))
    cogs = float(args["cogs_per_month"])
    term = int(args.get("term_months", 12))
    f = current_fix()
    est = fixed + cogs * f["fix_usd"]
    unmet = []
    if f.get("receipts", 0) == 0:
        unmet.append("no execution receipts (fix is a posted-price quote, PROVISIONAL)")
    if not str(f.get("qualification", "")).startswith("exam-qualified"):
        unmet.append("capability tier assumed, not exam-administered")
    if f.get("stale"):
        unmet.append(f"published fix is stale (age {f.get('age_days')}d)")
    warning = (
        "!! BASIS WARNING — the displayed reference fix does not currently meet "
        "the rider's settlement standard:\n"
        + "\n".join(f"- {item}" for item in unmet)
    ) if unmet else ""
    text = riders.render(
        "msa-hybrid",
        provider=provider,
        client=client,
        fixed_usd_per_period=f"{fixed:.2f}",
        cogs_per_period=f"{cogs:.0f}",
        term=f"{term} months",
        fix_usd=str(f["fix_usd"]),
        estimated_total_usd=f"{est:.2f}",
        fix_source=(
            f"{f['source']} ({f['date']}, mode {f['mode']}, "
            f"tier {f.get('tier', 'venue-quote')})"
        ),
        qualification=f.get("qualification", "unknown"),
        receipts=f.get("receipts", 0),
        basis_warning=warning,
    )
    return {"rider_text": text, "estimated_month1_usd": round(est, 2),
            "fix_used": f["fix_usd"], "fix_basis_unmet": unmet,
            "disclaimer": "template for negotiation; not legal advice"}


def t_generate_rider(args):
    name = args["template"]
    values = args.get("values") or {}
    return {
        "template": name,
        "rider_text": riders.render(name, values),
        "disclaimer": "template for negotiation; not legal advice",
    }


def t_draft_obligation(args):
    parties = args.get("parties") or {
        "provider": {"name": args.get("provider", "Provider")},
        "client": {"name": args.get("client", "Client")},
    }
    legs = args.get("legs")
    if legs is None:
        legs = []
        if args.get("fixed_usd_per_period") is not None:
            legs.append({"kind": "fixed", "USD": str(args["fixed_usd_per_period"])})
        if args.get("cogs_per_period") is not None:
            legs.append({
                "kind": "indexed",
                "cog": "COG-1",
                "quantity": str(args["cogs_per_period"]),
            })
    term = args.get("term") or {
        "start": args["start"],
        "end": args["end"],
        "period": args.get("period", "month"),
    }
    document = cdo_contract.draft_obligation(
        parties=parties,
        legs=legs,
        term=term,
        unit=args.get("unit"),
        settlement=args.get("settlement"),
        versioning=args.get("versioning"),
        metering=args.get("metering"),
    )
    return document


def _tool_series(args):
    if args.get("series") is not None:
        return args["series"]
    return load_series(
        args.get("archive_dir", str(ROOT / "fixer" / "archive")),
        verify_sigs=bool(args.get("verify_sigs", True)),
    )


def t_settlement_fix(args):
    return resolve_settlement_fix(
        _tool_series(args),
        args["period_end"],
        min_tier=args.get("min_tier", "venue-quote"),
        publishers=args.get("publishers"),
        multi_publisher_rule=args.get("multi_publisher_rule", "priority-order"),
        counterparty_ack=bool(args.get("counterparty_ack", False)),
    )


def t_settle_invoice(args):
    document = settle_cdo_invoice(
        args["cdo"],
        args["period"],
        _tool_series(args),
        prior_invoices=args.get("prior_invoices"),
    )
    return document


def t_verify_invoice(args):
    return verify_cog_invoice(
        args["invoice"],
        args.get("archive_dir", str(ROOT / "fixer" / "archive")),
        invoice_allowed_signers=args.get("allowed_signers"),
    )


TOOLS = {
    "get_fix": {
        "fn": t_get_fix,
        "description": "Get today's COG-1 fix: the price of intelligence (USD per cog). "
                       "1 cog = 1M blended tokens at frozen GPT-4-class capability.",
        "schema": {"type": "object", "properties": {}, "required": []},
    },
    "price_in_cogs": {
        "fn": t_price_in_cogs,
        "description": "Convert a USD amount and/or a blended-token workload into cogs at the current fix.",
        "schema": {"type": "object", "properties": {
            "usd": {"type": "number", "description": "USD amount to convert to cogs"},
            "blended_tokens": {"type": "number", "description": "workload size in blended tokens (0.8*in+0.2*out mix)"},
        }, "required": []},
    },
    "reprice_contract": {
        "fn": t_reprice_contract,
        "description": "Compare a fixed-USD AI contract with the same deal indexed in cogs "
                       "(optionally hybrid: fixed non-AI leg + cog leg). Returns the hidden short.",
        "schema": {"type": "object", "properties": {
            "usd_per_month": {"type": "number"},
            "months": {"type": "integer"},
            "start": {"type": "string", "description": "signing month, YYYY-MM (2023-03..2026-06)"},
            "fixed_usd_per_month": {"type": "number", "description": "non-AI leg kept in USD (default 0)"},
        }, "required": ["usd_per_month", "months", "start"]},
    },
    "generate_sla": {
        "fn": t_generate_sla,
        "description": "Generate a hybrid cog-denominated pricing rider (fixed USD leg + N cogs/month, "
                       "settled at the 7-day median fix). Template text, not legal advice.",
        "schema": {"type": "object", "properties": {
            "provider": {"type": "string"}, "client": {"type": "string"},
            "fixed_usd_per_month": {"type": "number"},
            "cogs_per_month": {"type": "number"},
            "term_months": {"type": "integer"},
        }, "required": ["cogs_per_month"]},
    },
    "generate_rider": {
        "fn": t_generate_rider,
        "description": "Render one of the five COG contracting riders from reviewable Markdown data.",
        "schema": {"type": "object", "properties": {
            "template": {"type": "string", "enum": list(riders.NAMES)},
            "values": {"type": "object"},
        }, "required": ["template"]},
    },
    "draft_obligation": {
        "fn": t_draft_obligation,
        "description": "Draft and schema-validate a canonical Cog-Denominated Obligation (CDO).",
        "schema": {"type": "object", "properties": {
            "parties": {"type": "object"},
            "provider": {"type": "string"},
            "client": {"type": "string"},
            "legs": {"type": "array"},
            "fixed_usd_per_period": {"type": ["number", "string"]},
            "cogs_per_period": {"type": ["number", "string"]},
            "term": {"type": "object"},
            "start": {"type": "string"},
            "end": {"type": "string"},
            "period": {"type": "string"},
            "unit": {"type": "object"},
            "settlement": {"type": "object"},
            "versioning": {"type": "object"},
            "metering": {"type": "object"},
        }, "required": []},
    },
    "settlement_fix": {
        "fn": t_settlement_fix,
        "description": "Resolve the labeled COG-SETTLE-1 period-end fix from local archive evidence.",
        "schema": {"type": "object", "properties": {
            "period_end": {"type": "string", "description": "UTC service-period end, YYYY-MM-DD"},
            "min_tier": {"type": "string"},
            "publishers": {"type": "array", "items": {"type": "string"}},
            "multi_publisher_rule": {"type": "string"},
            "counterparty_ack": {"type": "boolean"},
            "series": {"type": "array"},
            "archive_dir": {"type": "string"},
            "verify_sigs": {"type": "boolean"},
        }, "required": ["period_end"]},
    },
    "settle_invoice": {
        "fn": t_settle_invoice,
        "description": "Purely recompute an unsigned COG invoice from a CDO and signed local series.",
        "schema": {"type": "object", "properties": {
            "cdo": {"type": "object"},
            "period": {"type": ["object", "string"]},
            "series": {"type": "array"},
            "archive_dir": {"type": "string"},
            "verify_sigs": {"type": "boolean"},
            "prior_invoices": {"type": "array"},
        }, "required": ["cdo", "period"]},
    },
    "verify_invoice": {
        "fn": t_verify_invoice,
        "description": "Verify a COG invoice's canonical id, Decimal arithmetic, and archive evidence.",
        "schema": {"type": "object", "properties": {
            "invoice": {"type": ["object", "string"]},
            "archive_dir": {"type": "string"},
            "allowed_signers": {"type": "string"},
        }, "required": ["invoice"]},
    },
}


# ---------------------------------------------------------------- MCP plumbing

def rpc_result(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def rpc_error(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def handle(req):
    method, id_ = req.get("method"), req.get("id")
    if method == "initialize":
        proto = req.get("params", {}).get("protocolVersion", "2024-11-05")
        return rpc_result(id_, {"protocolVersion": proto, "capabilities": {"tools": {}},
                                "serverInfo": {"name": "cog-fix", "version": "0.1.0"}})
    if method == "ping":
        return rpc_result(id_, {})
    if method == "tools/list":
        return rpc_result(id_, {"tools": [
            {"name": k, "description": v["description"], "inputSchema": v["schema"]}
            for k, v in TOOLS.items()]})
    if method == "tools/call":
        name = req["params"]["name"]
        if name not in TOOLS:
            return rpc_error(id_, -32602, f"unknown tool {name}")
        try:
            out = TOOLS[name]["fn"](req["params"].get("arguments") or {})
            return rpc_result(id_, {"content": [{"type": "text", "text": json.dumps(out, indent=2)}],
                                    "isError": False})
        except Exception as e:
            return rpc_result(id_, {"content": [{"type": "text", "text": f"error: {e}"}],
                                    "isError": True})
    if id_ is None:  # notification (e.g. notifications/initialized) — no response
        return None
    return rpc_error(id_, -32601, f"method not found: {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

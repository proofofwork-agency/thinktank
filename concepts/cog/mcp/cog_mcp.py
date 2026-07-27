#!/usr/bin/env python3
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
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "cogfix"))
sys.path.insert(0, str(ROOT / "fixer"))
import cogfix  # noqa: E402
import fixerd  # noqa: E402


# ---------------------------------------------------------------- fix lookup

def current_fix():
    """Best available fix: published file, else live quote, else bundled snapshot.

    Every result carries the basis it actually earned — age, qualification, and
    receipt count — so a caller can tell a receipted fix from a provisional
    posted-price quote. A corrupt or unreadable fix.json falls through to the
    live quote rather than propagating an exception.
    """
    fix_file = ROOT / "fixer" / "fix.json"
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        p = json.loads(fix_file.read_text())
        age = (date.fromisoformat(today) - date.fromisoformat(p["date"])).days
        return {"fix_usd": p["fix_usd"], "date": p["date"], "mode": p["mode"],
                "source": "published fixer/fix.json"
                          + (f" (stale by {age}d — rerun fixerd)" if age > 1 else ""),
                "floor_usd": p.get("floor_usd"),
                "age_days": age, "stale": age > 1,
                "qualification": (p.get("qualification") or {}).get("basis", "unknown"),
                "receipts": len(p.get("receipts") or [])}
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
                "qualification": "assumed static allowlist (no exam run)", "receipts": 0}
    except Exception:
        s = cogfix.official_series()
        return {"fix_usd": s[-1][1], "date": "2026-06", "mode": "bundled",
                "source": "bundled snapshot (offline fallback)", "floor_usd": None,
                "age_days": None, "stale": True,
                "qualification": "assumed static allowlist (no exam run)", "receipts": 0}


def unit_description(f):
    """Describe the unit at the confidence this particular fix actually earned.

    The COG-1 spec defines the cog as *depth-verified*; claiming that label for a
    posted-price quote with no receipts is exactly the LIBOR failure the
    whitepaper argues against, so the wording tracks the evidence.
    """
    price = ("depth-verified" if f.get("receipts", 0) > 0
             else "posted-price (PROVISIONAL, unreceipted)")
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
    # §1 and §6 below describe the COG-1 publication standard (receipted, auditable).
    # If today's fix does not yet meet that standard, say so in the document itself —
    # a rider whose audit clause references receipts that do not exist is a trap.
    unmet = []
    if f.get("receipts", 0) == 0:
        unmet.append("no execution receipts (fix is a posted-price quote, PROVISIONAL)")
    if not str(f.get("qualification", "")).startswith("exam-qualified"):
        unmet.append("capability tier assumed, not exam-administered")
    if f.get("stale"):
        unmet.append(f"published fix is stale (age {f.get('age_days')}d)")
    warning = ("\n\n!! BASIS WARNING — the reference publisher does NOT currently meet the\n"
               "   standard described in §1 and §6:\n"
               + "\n".join(f"     - {u}" for u in unmet)
               + "\n   Do not rely on §6 (Audit) until the publisher publishes receipts.") if unmet else ""
    text = f"""COG-DENOMINATED PRICING RIDER (TEMPLATE v0.1 — NOT LEGAL ADVICE)
between {provider} ("Provider") and {client} ("Client")

1. DEFINITIONS
   "COG-1 Fix" means the published daily price, in USD, of the COG-1 Reference
   Workload (1,000,000 blended tokens, 800,000 input / 200,000 output, executed
   at COG-1 qualifying capability), as defined in the COG specification
   (WHITEPAPER.md, draft 0.1) and published by the Fix Publisher with execution
   receipts. "Settlement Fix" means the arithmetic median of the COG-1 Fix over
   the seven (7) calendar days preceding the invoice date.

2. PRICE
   Client shall pay Provider, per calendar month:
   (a) a fixed component of USD {fixed:,.2f}; plus
   (b) an indexed component of {cogs:,.0f} cogs, settled in USD at the
       Settlement Fix on the invoice date.
   (Indicative month-1 total at today's fix of ${f['fix_usd']}/cog: ~USD {est:,.2f}.)

3. TERM
   {term} months. Neither party may reprice the cog quantity during the term;
   the USD value of the indexed component floats with the Settlement Fix by
   construction.

4. FIX UNAVAILABILITY & VERSIONING
   If no COG-1 Fix is published for 14 consecutive days, the last published
   fix applies until publication resumes. If the publisher retires COG-1 in
   favor of a successor basket, the indexed component converts at the published
   chain-linking factor over the parallel-publication window.

5. SYMMETRY
   The indexed component rises and falls with the Settlement Fix in both
   directions. Neither party bears renegotiation obligations from fix movement.

6. AUDIT
   Either party may verify any Settlement Fix against the publisher's receipts
   archive. Disputes use the recomputed value from published receipts.

Fix source today: {f['source']} ({f['date']}, mode {f['mode']}).
Qualification basis: {f.get('qualification', 'unknown')}. Receipts: {f.get('receipts', 0)}.{warning}"""
    return {"rider_text": text, "estimated_month1_usd": round(est, 2),
            "fix_used": f["fix_usd"], "fix_basis_unmet": unmet,
            "disclaimer": "template for negotiation; not legal advice"}


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

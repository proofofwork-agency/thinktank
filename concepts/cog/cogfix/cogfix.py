#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""cogfix — reference implementation of the COG-1 fix.

The cog: a capability-indexed unit of account for the intelligence economy.
1 cog = the depth-verified market price of executing the COG-1 Reference Workload
(1M blended tokens, 800k in / 200k out) on a model that passes the frozen
COG-1 capability basket — median executable price across qualifying sized
purchases (>= K=5 independent buys of >= N=10M tokens each), never a single
cheapest sip. See WHITEPAPER.md.

Usage:
  python3 cogfix.py                          # fix series, current fix, worked examples
  python3 cogfix.py --contract 10000 24 2024-05              # pure cog repricing (mechanics)
  python3 cogfix.py --contract 10000 24 2024-05 --fixed 3000 # hybrid: fixed USD leg + cogs
  python3 cogfix.py --live                   # provisional live fix from OpenRouter prices

The production template is HYBRID (fixed USD + N cogs): only the cognition leg
deflates ~10x/yr; the vendor's humans, support, and compliance do not. Index only
the volatile leg — the fuel-surcharge pattern. --fixed is that non-AI leg.

Stdlib only. The backtest uses documented launch/posted prices as a proxy for
receipted runs and is approximate by construction (see data.json caveats).
"""

import json
import math
import sys
import urllib.request
from pathlib import Path

DATA = json.loads((Path(__file__).parent / "data.json").read_text())

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# COG-1's 4:1 reference mix (800k in / 200k out), defined once. fixerd aliases this and the
# demo mirrors it; data.json states it in prose. A blend rule that drifts between call sites
# is a unit that means different things in different places.
BLEND_IN, BLEND_OUT = 0.8, 0.2


def blend(input_usd_per_M: float, output_usd_per_M: float) -> float:
    """COG-1 blended price per million tokens."""
    return BLEND_IN * input_usd_per_M + BLEND_OUT * output_usd_per_M


def month_index(ym: str) -> int:
    y, m = ym.split("-")
    return int(y) * 12 + int(m) - 1


def official_series():
    """(month_index, blended_price) for non-provisional frontier-tier points."""
    pts = [p for p in DATA["frontier_tier_series"] if p["status"] != "provisional"]
    out = {}
    for p in pts:  # if two points share a month, the fix is the cheapest
        i = month_index(p["date"])
        out[i] = min(out.get(i, math.inf), p["blended_usd_per_M"])
    return sorted(out.items())


def fix_at(ym: str, series=None) -> tuple[float, bool]:
    """COG-1 fix (USD per cog) at month ym, log-linearly interpolated.

    Returns (fix, exact_or_interpolated). Before the first point: error.
    After the last point: held flat (no extrapolation), flagged False.
    """
    s = series or official_series()
    i = month_index(ym)
    if i < s[0][0]:
        raise ValueError(f"{ym} predates the COG-1 backtest ({DATA['frontier_tier_series'][0]['date']})")
    if i >= s[-1][0]:
        return s[-1][1], i == s[-1][0]
    for (i0, p0), (i1, p1) in zip(s, s[1:]):
        if i0 <= i <= i1:
            t = (i - i0) / (i1 - i0)
            return math.exp(math.log(p0) + t * (math.log(p1) - math.log(p0))), i in (i0, i1)
    raise AssertionError


def ym_add(ym: str, k: int) -> str:
    i = month_index(ym) + k
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def print_series():
    print("COG-1 backtest — frontier tier (approximate; documented prices as proxy for receipted runs)")
    print(f"{'date':<9}{'model':<24}{'blended $/M':>12}   status")
    for p in DATA["frontier_tier_series"]:
        print(f"{p['date']:<9}{p['model']:<24}{p['blended_usd_per_M']:>12.4f}   {p['status']}")
    s = official_series()
    first, last = s[0], s[-1]
    factor = first[1] / last[1]
    months = last[0] - first[0]
    annual = factor ** (12 / months)
    print(f"\nOfficial fix: ${first[1]:.2f} -> ${last[1]:.4f} over {months} months "
          f"= {factor:,.0f}x cheaper (~{annual:.1f}x per year).")
    prov = [p for p in DATA["frontier_tier_series"] if p["status"] == "provisional"]
    if prov:
        p = min(prov, key=lambda q: q["blended_usd_per_M"])
        print(f"Provisional fix ({p['date']}): ${p['blended_usd_per_M']:.4f}  "
              f"[{p['model']}, pending qualifying basket run]")
    lo = DATA["mmlu42_tier_series"]
    print(f"\nLong arc (MMLU~42 tier, a16z): ${lo[0]['blended_usd_per_M']:.2f} ({lo[0]['date']}) -> "
          f"${lo[-1]['blended_usd_per_M']:.2f} ({lo[-1]['date']}) = "
          f"{lo[0]['blended_usd_per_M']/lo[-1]['blended_usd_per_M']:,.0f}x in 3 years.")


def reprice(usd_per_month: float, months: int, start: str, fixed: float = 0.0, quiet=False):
    """Compare a fixed-USD contract with the same deal indexed in cogs.

    fixed = the non-AI leg (people, support, compliance) that stays in USD;
    only the remainder (the cognition leg) is converted to cogs at the signing fix.
    """
    if not 0 <= fixed < usd_per_month:
        raise ValueError("--fixed must be >= 0 and below the monthly total")
    f0, _ = fix_at(start)
    cogs_per_month = (usd_per_month - fixed) / f0
    rows, total_cog = [], 0.0
    held = False
    for k in range(months):
        ym = ym_add(start, k)
        f, exact = fix_at(ym)
        if month_index(ym) > official_series()[-1][0]:
            held = True
        inv = fixed + cogs_per_month * f
        total_cog += inv
        rows.append((k + 1, ym, f, inv))
    total_usd = usd_per_month * months
    if not quiet:
        leg = (f" = ${fixed:,.0f} fixed leg + {cogs_per_month:,.0f} cogs/mo"
               if fixed else f" vs {cogs_per_month:,.0f} cogs/mo")
        print(f"\nContract: {months} months from {start} — fixed ${usd_per_month:,.0f}/mo"
              f"{leg} (same price at signing; fix ${f0:.4f}/cog)")
        print(f"{'mo':>3} {'date':<9}{'fix $/cog':>11}{'cog invoice $':>15}")
        shown = rows if months <= 8 else rows[:3] + [None] + rows[-3:]
        for r in shown:
            if r is None:
                print("  …")
                continue
            print(f"{r[0]:>3} {r[1]:<9}{r[2]:>11.4f}{r[3]:>15,.0f}")
        print(f"\n  fixed-USD total : ${total_usd:>12,.0f}")
        print(f"  cog-indexed     : ${total_cog:>12,.0f}")
        print(f"  the hidden short: ${total_usd - total_cog:>12,.0f} "
              f"({(total_usd - total_cog) / total_usd:.0%} of the contract) — "
              f"what denominating in a bending ruler costs the buyer.")
        if fixed:
            print(f"  hybrid: the ${fixed:,.0f} people-leg never deflates — the vendor's "
                  f"payroll survives; the buyer still captures all cognition deflation.")
        if held:
            print("  note: months beyond the last data point hold the fix flat (no extrapolation).")
    return total_usd, total_cog


def live_fix():
    print("Fetching live posted prices from OpenRouter…")
    req = urllib.request.Request(OPENROUTER_MODELS_URL, headers={"User-Agent": "cogfix/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            models = {m["id"]: m for m in json.load(r)["data"]}
    except Exception as e:
        print(f"  network unavailable ({e}); falling back to bundled snapshot (2026-06-10).")
        print_series()
        return
    print(f"\nProvisional live COG-1 fix (allowlist of assumed-qualifying models — a real")
    print(f"fixer replaces this assumption with receipted basket runs):\n")
    print(f"{'model':<36}{'in $/M':>9}{'out $/M':>9}{'blended':>9}")
    best = None
    for mid in DATA["live_fix_allowlist"]:
        m = models.get(mid)
        if not m:
            continue
        pin = float(m["pricing"]["prompt"]) * 1e6
        pout = float(m["pricing"]["completion"]) * 1e6
        b = blend(pin, pout)
        print(f"{mid:<36}{pin:>9.3f}{pout:>9.3f}{b:>9.4f}")
        if best is None or b < best[1]:
            best = (mid, b)
    if best:
        print(f"\n  PROVISIONAL LIVE FIX: 1 cog = ${best[1]:.4f}   ({best[0]}, posted price, unreceipted)")
    else:
        print("  no allowlisted models found in feed.")


def main(argv):
    if "--live" in argv:
        live_fix()
        return
    fixed = float(argv[argv.index("--fixed") + 1]) if "--fixed" in argv else 0.0
    if "--contract" in argv:
        i = argv.index("--contract")
        usd, months, start = float(argv[i + 1]), int(argv[i + 2]), argv[i + 3]
        reprice(usd, months, start, fixed=fixed)
        return
    print_series()
    print("\n" + "=" * 72)
    print("Worked example (WHITEPAPER.md §4) — mechanics: pure cog leg")
    reprice(10_000, 24, "2024-05")
    print("\n" + "=" * 72)
    print("Production template (WHITEPAPER.md §4) — hybrid: $3,000 people-leg + cogs")
    reprice(10_000, 24, "2024-05", fixed=3_000)
    print("\nTry:  python3 cogfix.py --contract <usd/mo> <months> <YYYY-MM> [--fixed <usd>]")
    print("      python3 cogfix.py --live")


if __name__ == "__main__":
    main(sys.argv[1:])

#!/usr/bin/env python3
"""fixerd — the COG-1 fixer daemon. Publishes the daily price of intelligence.

Phase 1 of WHITEPAPER.md: one fixer, methodology open, receipts published,
anyone can verify or fork. Stdlib only.

Modes:
  quote        (default) free — pulls posted prices from OpenRouter, publishes a
               PROVISIONAL fix = median of the 3 cheapest allowlisted blended prices.
  receipt-lite real micro-buys — actually executes small completions against the
               3 cheapest qualifying models and publishes execution receipts.
               Requires OPENROUTER_API_KEY. Spends real money (capped, default $0.50).
               Depth-lite: proves the price existed for real requests, not capacity.
               The full COG-1 depth gate (K=5 buys x 10M tokens) is the same plumbing
               with bigger numbers.

Usage:
  python3 fixer/fixerd.py                     # quote mode, writes fix.json + archive
  python3 fixer/fixerd.py --receipt           # receipt-lite (needs OPENROUTER_API_KEY)
  python3 fixer/fixerd.py --receipt --max-spend-usd 0.25 --buys 3 --max-tokens 256

Cron (daily 09:07 UTC):
  7 9 * * * cd <repo> && python3 fixer/fixerd.py >> fixer/fixerd.log 2>&1

Output:
  fixer/fix.json                  latest published fix (signed if ssh-keygen available)
  fixer/fix.json.sig              SSH signature (ed25519, namespace "cogfix")
  fixer/allowed_signers           verify with:
    ssh-keygen -Y verify -f fixer/allowed_signers -I cogfix -n cogfix \
      -s fixer/fix.json.sig < fixer/fix.json
  fixer/archive/YYYY-MM-DD.json   immutable daily archive
"""

import hashlib
import json
import os
import statistics
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "cogfix"))
import cogfix  # noqa: E402  (DATA, allowlist, blend rule)

OPENROUTER = "https://openrouter.ai/api/v1"
BLEND = lambda pin, pout: 0.8 * pin + 0.2 * pout  # noqa: E731 — COG-1 4:1 blend
REFERENCE_PROMPT = (
    "You are executing one unit of the COG-1 reference workload. "
    "Summarize, in exactly three paragraphs, the economic consequences of the price "
    "of a production input falling tenfold per year while contracts for it remain "
    "denominated in a fixed currency."
)


def fetch_models():
    req = urllib.request.Request(f"{OPENROUTER}/models", headers={"User-Agent": "cogfix-fixerd/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return {m["id"]: m for m in json.load(r)["data"]}


def load_qualification(today: str):
    """Prefer exam-qualified models (harness/qualify.py) over the static allowlist.

    A live exam result gates the fix while fresh (<= 7 days); anything else —
    missing, stale, dry-run, or empty — falls back to the assumed list, labeled.
    """
    qpath = HERE / "qualified.json"
    if not qpath.exists():
        return None, {"basis": "assumed static allowlist (no exam run yet — run harness/qualify.py)"}
    q = json.loads(qpath.read_text())
    age = (date.fromisoformat(today) - date.fromisoformat(q["date"])).days
    if q.get("mode") != "live" or age > 7 or not q.get("qualified"):
        return None, {"basis": f"assumed static allowlist (exam result unusable: "
                               f"mode={q.get('mode')}, age={age}d, qualified={len(q.get('qualified', []))})"}
    return q["qualified"], {"basis": "exam-qualified", "exam": q["exam"],
                            "exam_sha256": q["exam_sha256"], "exam_date": q["date"],
                            "threshold": q["threshold"], "qualified_count": len(q["qualified"])}


def posted_quotes(models, ids=None):
    """Blended posted $/M for each candidate model, cheapest first."""
    rows = []
    for mid in (ids or cogfix.DATA["live_fix_allowlist"]):
        m = models.get(mid)
        if not m:
            continue
        pin = float(m["pricing"]["prompt"]) * 1e6
        pout = float(m["pricing"]["completion"]) * 1e6
        rows.append({"model": mid, "in_usd_per_M": round(pin, 6), "out_usd_per_M": round(pout, 6),
                     "blended_usd_per_M": round(BLEND(pin, pout), 6)})
    return sorted(rows, key=lambda r: r["blended_usd_per_M"])


def vw_median(runs):
    """Volume-weighted median of runs: [{'price': $/M, 'weight': tokens}, ...]."""
    runs = sorted(runs, key=lambda r: r["price"])
    total = sum(r["weight"] for r in runs)
    acc = 0
    for r in runs:
        acc += r["weight"]
        if acc * 2 >= total:
            return r["price"]
    return runs[-1]["price"]


def buy_run(model_row, api_key, max_tokens):
    """Execute one real micro-buy; return an execution receipt."""
    body = json.dumps({
        "model": model_row["model"],
        "messages": [{"role": "user", "content": REFERENCE_PROMPT}],
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        f"{OPENROUTER}/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "User-Agent": "cogfix-fixerd/0.1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    resp = json.loads(raw)
    usage = resp.get("usage", {})
    pt, ct = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    cost = (pt * model_row["in_usd_per_M"] + ct * model_row["out_usd_per_M"]) / 1e6
    return {
        "model": model_row["model"],
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "request_sha256": hashlib.sha256(body).hexdigest(),
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "response_id": resp.get("id"),
        "usage": {"prompt_tokens": pt, "completion_tokens": ct},
        "posted_in_usd_per_M": model_row["in_usd_per_M"],
        "posted_out_usd_per_M": model_row["out_usd_per_M"],
        "blended_usd_per_M": model_row["blended_usd_per_M"],
        "cost_usd_est": round(cost, 6),
    }


def sign(fix_path: Path):
    """Sign fix.json with a repo-local ed25519 SSH key (generated on first run)."""
    key = HERE / "keys" / "cogfix_ed25519"
    try:
        if not key.exists():
            key.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-f", str(key), "-N", "",
                            "-C", "cogfix-fixer"], check=True, capture_output=True)
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", "cogfix",
                        str(fix_path)], check=True, capture_output=True)
        pub = (key.with_suffix(".pub")).read_text().strip()
        (HERE / "allowed_signers").write_text(f"cogfix {pub.split(' ')[0]} {pub.split(' ')[1]}\n")
        return True
    except Exception as e:  # signing is best-effort; the fix still publishes
        print(f"  sign skipped ({e})", file=sys.stderr)
        return False


def main(argv):
    receipt_mode = "--receipt" in argv
    arg = lambda flag, default: (argv[argv.index(flag) + 1] if flag in argv else default)  # noqa: E731
    max_spend = float(arg("--max-spend-usd", "0.50"))
    buys = int(arg("--buys", "3"))
    max_tokens = int(arg("--max-tokens", "256"))

    today = datetime.now(timezone.utc).date().isoformat()
    print(f"fixerd — COG-1 fix for {today} ({'receipt-lite' if receipt_mode else 'quote'} mode)")

    qualified_ids, qualification = load_qualification(today)
    quotes = posted_quotes(fetch_models(), ids=qualified_ids)
    if len(quotes) < 3:
        sys.exit("fewer than 3 qualifying models in feed; refusing to fix")
    candidates = quotes[:3]

    receipts, spent = [], 0.0
    if receipt_mode:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            sys.exit("receipt mode needs OPENROUTER_API_KEY (this mode spends real money)")
        for row in candidates:
            for _ in range(buys):
                est = (200 * row["in_usd_per_M"] + max_tokens * row["out_usd_per_M"]) / 1e6
                if spent + est > max_spend:
                    print(f"  spend cap ${max_spend} reached; stopping buys")
                    break
                rcpt = buy_run(row, api_key, max_tokens)
                receipts.append(rcpt)
                spent += rcpt["cost_usd_est"]
                print(f"  receipt {rcpt['response_id']}: {rcpt['model']} "
                      f"{rcpt['usage']} ${rcpt['cost_usd_est']:.5f}")
        if receipts:
            fix = vw_median([{"price": r["blended_usd_per_M"],
                              "weight": r["usage"]["prompt_tokens"] + r["usage"]["completion_tokens"]}
                             for r in receipts])
            method = (f"volume-weighted median of {len(receipts)} receipted micro-runs "
                      f"(receipt-lite: existence proof, not the full K=5x10M depth gate)")
            mode = "receipt-lite"
        else:
            sys.exit("no receipts executed; not publishing")
    else:
        fix = statistics.median(r["blended_usd_per_M"] for r in candidates)
        method = "median of 3 cheapest allowlisted posted blended prices (PROVISIONAL, unreceipted)"
        mode = "quote"

    payload = {
        "basket": "COG-1 (draft)",
        "date": today,
        "mode": mode,
        "fix_usd": round(fix, 6),
        "floor_usd": quotes[0]["blended_usd_per_M"],
        "method": method,
        "blend": "blended $/M = 0.8*input + 0.2*output (4:1 reference mix)",
        "reference_workload": "1,000,000 blended tokens (800k in / 200k out) at COG-1 tier",
        "qualification": qualification,
        "models": quotes,
        "receipts": receipts,
        "spend_usd_est": round(spent, 6),
        "publisher": "proofofwork-agency/cog fixerd v0.1",
        "spec": "WHITEPAPER.md (COG-1 draft 0.1)",
    }

    fix_path = HERE / "fix.json"
    fix_path.write_text(json.dumps(payload, indent=2) + "\n")
    archive = HERE / "archive"
    archive.mkdir(exist_ok=True)
    (archive / f"{today}.json").write_text(json.dumps(payload, indent=2) + "\n")
    signed = sign(fix_path)

    print(f"\n  PUBLISHED: 1 cog = ${payload['fix_usd']}  ({mode})")
    print(f"  qualification: {qualification['basis']}")
    print(f"  floor ${payload['floor_usd']}  ·  models {len(quotes)}  ·  receipts {len(receipts)}"
          f"  ·  signed {'yes' if signed else 'no'}")
    print(f"  -> {fix_path}\n  -> {archive / (today + '.json')}")


if __name__ == "__main__":
    main(sys.argv[1:])

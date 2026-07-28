#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
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
  fixer/archive/YYYY-MM-DD.json.sig
"""

import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "cogfix"))
sys.path.insert(0, str(HERE.parent / "harness"))
import cogfix  # noqa: E402  (DATA, allowlist, blend rule)
import qualify  # noqa: E402  (exam fingerprint for qualification validation)
from anchor import anchor_at, divergence, normalize_blend  # noqa: E402

OPENROUTER = "https://openrouter.ai/api/v1"
BLEND = cogfix.blend
MIN_RESOLVED_FRACTION = 0.80
SIGNING_NAMESPACES = ("cogfix", "cog-cdo", "cog-invoice")
EST_PROMPT_TOKENS = 200
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
    if q.get("mode") != "live" or not 0 <= age <= 7 or not q.get("qualified"):
        return None, {"basis": f"assumed static allowlist (exam result unusable: "
                               f"mode={q.get('mode')}, age={age}d, qualified={len(q.get('qualified', []))})"}
    current_exam_sha256 = qualify.fingerprint()
    if q.get("exam_sha256") != current_exam_sha256:
        return None, {"basis": "assumed static allowlist (exam result unusable: "
                               "fingerprint does not match the current exam)"}
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
        try:
            pin = float(m["pricing"]["prompt"]) * 1e6
            pout = float(m["pricing"]["completion"]) * 1e6
            if not math.isfinite(pin) or not math.isfinite(pout) or pin < 0 or pout < 0:
                raise ValueError("prices must be finite and non-negative")
        except (KeyError, TypeError, ValueError) as exc:
            print(f"  FEED INVALID: {mid}: {exc}", file=sys.stderr)
            continue
        rows.append({"model": mid, "in_usd_per_M": round(pin, 6), "out_usd_per_M": round(pout, 6),
                     "blended_usd_per_M": round(BLEND(pin, pout), 6)})
    return sorted(rows, key=lambda r: r["blended_usd_per_M"])


def median_executable_price(runs):
    """Return one equally weighted executable-price observation per eligible buy.

    The depth protocol fixes the eligibility floor and purchase count: at least
    K=5 independent buys of at least N=10M tokens each.  Token counts are
    protocol-selected, not observed market volume, so they MUST NOT weight the
    result or be described as market-volume weighting.  The protection is
    admission through the eligibility floor, not weighting.
    """
    return statistics.median(run["price"] for run in runs)


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
    usage = resp.get("usage")
    usage_reported = (
        isinstance(usage, dict)
        and isinstance(usage.get("prompt_tokens"), int)
        and not isinstance(usage.get("prompt_tokens"), bool)
        and usage["prompt_tokens"] >= 0
        and isinstance(usage.get("completion_tokens"), int)
        and not isinstance(usage.get("completion_tokens"), bool)
        and usage["completion_tokens"] >= 0
    )
    if usage_reported:
        pt, ct = usage["prompt_tokens"], usage["completion_tokens"]
    else:
        # Without provider usage there is no honest observed cost or volume.
        # Reserve the same conservative request maximum used by the spend gate.
        pt, ct = EST_PROMPT_TOKENS, max_tokens
    cost = (pt * model_row["in_usd_per_M"] + ct * model_row["out_usd_per_M"]) / 1e6
    return {
        "model": model_row["model"],
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "request_sha256": hashlib.sha256(body).hexdigest(),
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "response_id": resp.get("id"),
        "usage": {"prompt_tokens": pt, "completion_tokens": ct},
        "usage_estimated": not usage_reported,
        "posted_in_usd_per_M": model_row["in_usd_per_M"],
        "posted_out_usd_per_M": model_row["out_usd_per_M"],
        "blended_usd_per_M": model_row["blended_usd_per_M"],
        "cost_usd_est": cost,
    }


def buy_receipts(candidates, api_key, buys, max_tokens, max_spend):
    """Execute capped receipt-lite buys, stopping all candidates at the ceiling."""
    receipts, spent = [], 0.0
    cap_reached = False
    for row in candidates:
        for _ in range(buys):
            est = (EST_PROMPT_TOKENS * row["in_usd_per_M"]
                   + max_tokens * row["out_usd_per_M"]) / 1e6
            if spent + est > max_spend:
                print(f"  spend cap ${max_spend} reached; stopping buys")
                cap_reached = True
                break
            rcpt = buy_run(row, api_key, max_tokens)
            receipts.append(rcpt)
            spent += rcpt["cost_usd_est"]
            print(f"  receipt {rcpt['response_id']}: {rcpt['model']} "
                  f"{rcpt['usage']} ${rcpt['cost_usd_est']:.5f}")
        if cap_reached:
            break
    return receipts, spent


def _allowed_signers_trusts(
    allowed_signers: Path, public_key: str, principal: str = "cogfix"
) -> bool:
    """Return whether the trust file authorizes ``principal`` with our key."""
    key_type, key_blob = public_key.split()[:2]
    for raw_line in allowed_signers.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        principals = fields[0].split(",")
        if principal not in principals:
            continue
        if any(fields[i:i + 2] == [key_type, key_blob] for i in range(1, len(fields) - 1)):
            return True
    return False


def sign(
    payload_path: Path,
    namespace: str = "cogfix",
    key: Path | None = None,
    allowed_signers: Path | None = None,
):
    """Sign and verify a payload with the shared ed25519 SSH signer."""
    payload_path = Path(payload_path)
    key = Path(key) if key is not None else HERE / "keys" / "cogfix_ed25519"
    signature = Path(f"{payload_path}.sig")
    allowed_signers = (
        Path(allowed_signers) if allowed_signers is not None else HERE / "allowed_signers"
    )
    try:
        if namespace not in SIGNING_NAMESPACES:
            raise ValueError(f"unsupported signing namespace: {namespace}")
        # ssh-keygen otherwise prompts before overwriting and can return success
        # without changing the signature when its stdin is closed.
        signature.unlink(missing_ok=True)
        if not key.exists():
            key.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-f", str(key), "-N", "",
                            "-C", "cog-shared-signer"], check=True, capture_output=True,
                           stdin=subprocess.DEVNULL)
        public_key = Path(f"{key}.pub").read_text().strip()
        if allowed_signers.exists():
            if not _allowed_signers_trusts(allowed_signers, public_key, namespace):
                print(f"  SIGNING REFUSED: allowed_signers does not trust the current key "
                      f"for principal {namespace!r}",
                      file=sys.stderr)
                return False
        else:
            key_type, key_blob = public_key.split()[:2]
            allowed_signers.parent.mkdir(parents=True, exist_ok=True)
            principals = ",".join(SIGNING_NAMESPACES)
            allowed_signers.write_text(f"{principals} {key_type} {key_blob}\n")

        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", namespace,
                        str(payload_path)], check=True, capture_output=True,
                       stdin=subprocess.DEVNULL)
        subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers),
                        "-I", namespace, "-n", namespace, "-s", str(signature)],
                       input=payload_path.read_bytes(), check=True, capture_output=True)
        return True
    except Exception as e:  # signing is best-effort; the fix still publishes
        try:
            signature.unlink(missing_ok=True)
        except OSError as cleanup_error:
            print(f"  SIGNATURE CLEANUP FAILED ({cleanup_error})", file=sys.stderr)
        print(f"  sign skipped ({e})", file=sys.stderr)
        return False


def _write_immutable(path: Path, payload: bytes):
    """Create an archive payload once; accept identical reruns, reject changes."""
    if path.exists():
        if path.read_bytes() != payload:
            raise FileExistsError(f"archive conflict: {path} already contains different bytes")
        return
    path.write_bytes(payload)


def local_anchor_check(local_fix, today: str):
    """Compare against the vendored Epoch snapshot without touching the network."""
    event = anchor_at(today)
    normalized = normalize_blend(event)
    return {
        "publisher": "Epoch AI",
        "source": "anchor/snapshot/epoch_llm_inference_prices.csv (CC-BY)",
        "event_date": event["date"],
        "model": event["model"],
        "lookup": event["lookup"],
        "source_usd_per_million_tokens": event["usd_per_million_tokens"],
        "ratio_adjusted_usd_per_cog": normalized["usd_per_cog"],
        "normalized": normalized,
        "divergence": divergence(local_fix, normalized),
        "settlement_use": (
            "precommitted external anchor only; provisional, acknowledgement-gated, "
            "and subject to true-up"
        ),
    }


def main(argv):
    receipt_mode = "--receipt" in argv
    arg = lambda flag, default: (argv[argv.index(flag) + 1] if flag in argv else default)  # noqa: E731
    max_spend = float(arg("--max-spend-usd", "0.50"))
    buys = int(arg("--buys", "3"))
    max_tokens = int(arg("--max-tokens", "256"))

    today = datetime.now(timezone.utc).date().isoformat()
    print(f"fixerd — COG-1 fix for {today} ({'receipt-lite' if receipt_mode else 'quote'} mode)")

    qualified_ids, qualification = load_qualification(today)
    requested_ids = qualified_ids or cogfix.DATA["live_fix_allowlist"]
    model_feed = fetch_models()
    quotes = posted_quotes(model_feed, ids=qualified_ids)
    resolved_ids = {row["model"] for row in quotes}
    missing_ids = [model_id for model_id in requested_ids if model_id not in resolved_ids]
    # An empty feed is used by the offline main() regression with posted_quotes
    # patched to deterministic rows. A real, non-empty provider response must
    # meet the configured allowlist coverage floor.
    if model_feed:
        for model_id in missing_ids:
            print(f"  FEED MISS: allowlisted model did not resolve: {model_id}", file=sys.stderr)
        minimum = max(3, math.ceil(len(requested_ids) * MIN_RESOLVED_FRACTION))
        if len(resolved_ids) < minimum:
            sys.exit(
                f"only {len(resolved_ids)}/{len(requested_ids)} allowlisted models resolved "
                f"(minimum {minimum}); refusing to publish"
            )
    if len(quotes) < 3:
        sys.exit("fewer than 3 qualifying models in feed; refusing to fix")
    candidates = quotes[:3]

    receipts, spent = [], 0.0
    if receipt_mode:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            sys.exit("receipt mode needs OPENROUTER_API_KEY (this mode spends real money)")
        receipts, spent = buy_receipts(candidates, api_key, buys, max_tokens, max_spend)
        if receipts:
            fix = median_executable_price(
                [{"price": r["blended_usd_per_M"]} for r in receipts]
            )
            method = (
                f"median executable price across {len(receipts)} receipted micro-runs "
                f"(receipt-lite: execution evidence only, not the full >= K=5 "
                f"independent buys of >= N=10M tokens each depth gate)"
            )
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
        "tier": "receipted-depth" if mode == "receipt-lite" else "venue-quote",
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
        "spec": "spec/COG-1.md",
        "provenance": {
            "feed": "OpenRouter model catalogue",
            "resolved_allowlisted": len(resolved_ids),
            "requested_allowlisted": len(requested_ids),
            "missing_allowlisted": missing_ids,
        },
        "anchor_check": local_anchor_check(fix, today),
    }

    payload_bytes = (json.dumps(payload, indent=2) + "\n").encode()
    archive = HERE / "archive"
    archive.mkdir(exist_ok=True)
    archive_path = archive / f"{today}.json"
    try:
        _write_immutable(archive_path, payload_bytes)
    except FileExistsError as e:
        sys.exit(str(e))

    fix_path = HERE / "fix.json"
    fix_path.write_bytes(payload_bytes)
    fix_signed = sign(fix_path)
    archive_signed = sign(archive_path)

    print(f"\n  PUBLISHED: 1 cog = ${payload['fix_usd']}  ({mode})")
    print(f"  qualification: {qualification['basis']}")
    print(f"  floor ${payload['floor_usd']}  ·  models {len(quotes)}  ·  receipts {len(receipts)}"
          f"  ·  signed current {'yes' if fix_signed else 'no'}"
          f" / archive {'yes' if archive_signed else 'no'}")
    print(f"  -> {fix_path}\n  -> {archive_path}")


if __name__ == "__main__":
    main(sys.argv[1:])

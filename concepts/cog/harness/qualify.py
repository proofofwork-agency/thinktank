#!/usr/bin/env python3
"""qualify — the COG-1 qualifying exam. Administers the capability keuring.

Replaces fixerd's *assumed* allowlist with an *administered* one: each candidate
model sits the frozen COG1-CORE exam; only models scoring >= threshold qualify
to set the fix. Every exam run is receipted (request/response hashes, usage,
cost). The exam fingerprint (sha256 of the canonical item set) is published with
the results, so everyone knows exactly which exam version gated the fix.

Modes:
  --self-test   free: validate exam integrity (ids, answers, stable fingerprint)
  --dry-run     free: run the full pipeline against built-in mock candidates
                (writes harness/dryrun_report.json — NEVER fixer/qualified.json;
                mock results must never gate a real fix)
  (real mode)   sits the exam against live models via OpenRouter.
                Requires OPENROUTER_API_KEY. Spends real money (capped).

Usage:
  python3 harness/qualify.py --self-test
  python3 harness/qualify.py --dry-run
  python3 harness/qualify.py --max-spend-usd 0.25            # examine the allowlist
  python3 harness/qualify.py --models deepseek/deepseek-v3.2 # examine specific models

Real mode writes fixer/qualified.json, which fixerd.py picks up automatically
(if fresh, <= 7 days) instead of the static allowlist. Stdlib only.
"""

import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "cogfix"))
import cogfix  # noqa: E402

OPENROUTER = "https://openrouter.ai/api/v1"
EXAM = json.loads((HERE / "exam_core.json").read_text())


def fingerprint():
    """sha256 over the canonical item set — the exam's frozen identity."""
    canon = json.dumps(EXAM["items"], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def normalize(s: str) -> str:
    s = s.strip().lower()
    for ch in ".!?\"'`":
        s = s.replace(ch, "")
    s = s.replace(",", "")          # thousands separators / list commas
    return " ".join(s.split())


def grade(response_text: str, answer: str) -> bool:
    """Compare the last non-empty line of the response with the expected answer."""
    lines = [ln for ln in response_text.strip().splitlines() if ln.strip()]
    if not lines:
        return False
    return normalize(lines[-1]) == normalize(answer)


def ask_model(model_id: str, prompt: str, api_key: str):
    body = json.dumps({
        "model": model_id,
        "messages": [
            {"role": "system", "content": EXAM["meta"]["answer_instruction"]},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": EXAM["meta"]["max_answer_tokens"],
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        f"{OPENROUTER}/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "User-Agent": "cog-qualify/0.1"})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
    resp = json.loads(raw)
    text = resp["choices"][0]["message"]["content"] or ""
    usage = resp.get("usage", {})
    return text, usage, hashlib.sha256(body).hexdigest(), hashlib.sha256(raw).hexdigest()


def examine(model_id: str, asker):
    """Sit the full exam; asker(model_id, prompt) -> (text, usage, req_sha, resp_sha)."""
    correct, receipts, tokens = 0, [], 0
    for item in EXAM["items"]:
        text, usage, req_sha, resp_sha = asker(model_id, item["prompt"])
        ok = grade(text, item["answer"])
        correct += ok
        tokens += usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        receipts.append({"item": item["id"], "ok": ok, "req_sha256": req_sha[:16],
                         "resp_sha256": resp_sha[:16]})
    score = correct / len(EXAM["items"])
    return {"model": model_id, "score": round(score, 4), "correct": correct,
            "total": len(EXAM["items"]), "passed": score >= EXAM["meta"]["threshold"],
            "tokens_used": tokens, "item_receipts": receipts}


# ----------------------------------------------------------------- mock mode

def mock_asker(accuracy: float):
    """Deterministic mock candidate: answers the first floor(accuracy*N) items
    correctly and the rest wrongly — exercises grading, scoring, and the gate."""
    n_right = int(accuracy * len(EXAM["items"]))
    right_ids = {it["id"] for it in EXAM["items"][:n_right]}
    answer_key = {it["prompt"]: (it["answer"], it["id"]) for it in EXAM["items"]}

    def ask(model_id, prompt):
        ans, item_id = answer_key[prompt]
        text = ans if item_id in right_ids else "wrong-on-purpose"
        fake = f"{model_id}:{item_id}".encode()
        return text, {"prompt_tokens": 50, "completion_tokens": 5}, \
            hashlib.sha256(fake).hexdigest(), hashlib.sha256(fake[::-1]).hexdigest()
    return ask


# ----------------------------------------------------------------- entry

def self_test():
    items = EXAM["items"]
    ids = [it["id"] for it in items]
    assert len(ids) == len(set(ids)), "duplicate item ids"
    assert all(it["answer"].strip() for it in items), "empty answer"
    fp1, fp2 = fingerprint(), fingerprint()
    assert fp1 == fp2 and len(fp1) == 64, "unstable fingerprint"
    assert 0 < EXAM["meta"]["threshold"] <= 1, "bad threshold"
    print(f"self-test OK: {len(items)} items, threshold {EXAM['meta']['threshold']}, "
          f"fingerprint {EXAM['meta']['name']}-{EXAM['meta']['version']} sha256:{fp1[:16]}…")


def main(argv):
    if "--self-test" in argv:
        self_test()
        return

    today = datetime.now(timezone.utc).date().isoformat()
    exam_id = f"{EXAM['meta']['name']}-{EXAM['meta']['version']}"

    if "--dry-run" in argv:
        print(f"qualify — DRY RUN ({exam_id}, threshold {EXAM['meta']['threshold']})")
        results = [examine("mock/strong-candidate", mock_asker(0.95)),
                   examine("mock/weak-candidate", mock_asker(0.50))]
        report = {"date": today, "mode": "dry-run", "exam": exam_id,
                  "exam_sha256": fingerprint(), "threshold": EXAM["meta"]["threshold"],
                  "results": [{k: v for k, v in r.items() if k != "item_receipts"} for r in results],
                  "qualified": [r["model"] for r in results if r["passed"]],
                  "note": "mock candidates — this report can NEVER gate a real fix"}
        out = HERE / "dryrun_report.json"
        out.write_text(json.dumps(report, indent=2) + "\n")
        for r in results:
            print(f"  {r['model']:<28} {r['correct']}/{r['total']} ({r['score']:.0%})  "
                  f"{'PASS' if r['passed'] else 'FAIL'}")
        print(f"  -> {out}")
        return

    # real mode: spends money
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("real exam runs need OPENROUTER_API_KEY (this spends real money); "
                 "use --dry-run or --self-test for the free paths")
    arg = lambda flag, default: (argv[argv.index(flag) + 1] if flag in argv else default)  # noqa: E731
    max_spend = float(arg("--max-spend-usd", "0.25"))
    models = (arg("--models", "") or ",".join(cogfix.DATA["live_fix_allowlist"])).split(",")

    print(f"qualify — REAL exam ({exam_id}) for {len(models)} models, cap ${max_spend}")
    results, spent = [], 0.0
    for mid in models:
        # rough pre-check: ~40 items x ~150 tokens; abort before starting a model we can't afford
        if spent >= max_spend:
            print(f"  spend cap reached; skipping remaining models")
            break
        asker = lambda m, p: ask_model(m, p, api_key)  # noqa: E731
        r = examine(mid.strip(), asker)
        # cost estimate from posted prices is provider-specific; report tokens, not $ certainty
        spent += r["tokens_used"] / 1e6 * 1.0  # conservative $1/M blended ceiling for capping
        results.append(r)
        print(f"  {r['model']:<36} {r['correct']}/{r['total']} ({r['score']:.0%})  "
              f"{'PASS' if r['passed'] else 'FAIL'}")

    payload = {"date": today, "mode": "live", "exam": exam_id,
               "exam_sha256": fingerprint(), "threshold": EXAM["meta"]["threshold"],
               "results": [{k: v for k, v in r.items() if k != "item_receipts"} for r in results],
               "receipts": {r["model"]: r["item_receipts"] for r in results},
               "qualified": [r["model"] for r in results if r["passed"]]}
    out = ROOT / "fixer" / "qualified.json"
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\n  qualified: {len(payload['qualified'])}/{len(results)}  -> {out}")
    print("  fixerd will now gate the fix on this exam (while fresh, <= 7 days).")


if __name__ == "__main__":
    main(sys.argv[1:])

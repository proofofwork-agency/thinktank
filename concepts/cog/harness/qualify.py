#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""qualify — the COG-1 qualifying exam. Administers the capability keuring.

Replaces fixerd's *assumed* allowlist with an *administered* one: each candidate
model sits the frozen COG1-CORE exam; only models scoring >= threshold qualify
to set the fix. Every exam run is receipted (request/response hashes, usage,
cost). The exam fingerprint (sha256 of the canonical items *and* the meta fields
that define the gate — threshold, answer instruction, token budget, version) is
published with the results, so everyone knows exactly which exam, at which pass
mark, gated the fix.

Modes:
  --self-test   free: validate exam integrity (ids, answers, stable fingerprint)
  --dry-run     free: run the full pipeline against built-in mock candidates
                (writes harness/dryrun_report.json — NEVER fixer/qualified.json;
                mock results must never gate a real fix)
  (real mode)   sits the exam against live models via OpenRouter.
                The canonical endpoint requires COG_API_KEY or OPENROUTER_API_KEY.
                Custom OpenRouter-dialect endpoints may run without a key.
                Spends real money when the selected backend charges per call.

Backend:
  COG_OPENROUTER_BASE  OpenRouter-dialect base URL (defaults to OpenRouter)
  COG_API_KEY          credential, falling back to OPENROUTER_API_KEY

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
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cogfix"))
import cogfix  # noqa: E402
import openrouter_backend as backend  # noqa: E402
from contracts.canon import canon_sha256  # noqa: E402

EXAM = json.loads((HERE / "exam_core.json").read_text())


# Everything that changes what "passing" MEANS must be inside the fingerprint.
# Hashing items alone was not enough: meta.threshold could move 0.8 -> 0.05 while
# every published fix still cited a byte-identical "frozen" exam hash.
FINGERPRINT_META = ("name", "version", "threshold", "answer_instruction", "max_answer_tokens")


def fingerprint():
    """sha256 over the canonical exam — the items AND the meta that defines the gate."""
    return canon_sha256(
        {
            "items": EXAM["items"],
            "meta": {k: EXAM["meta"][k] for k in FINGERPRINT_META},
        },
        exclude_keys=(),
    )


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


def ask_model(model_id: str, prompt: str, api_key: str | None, base_url=None):
    base_url = backend.base_url() if base_url is None else base_url.rstrip("/")
    body = json.dumps({
        "model": model_id,
        "messages": [
            {"role": "system", "content": EXAM["meta"]["answer_instruction"]},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": EXAM["meta"]["max_answer_tokens"],
        "temperature": 0,
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "cog-qualify/0.1",
    }
    headers.update(backend.authorization_headers(api_key))
    url = f"{base_url}/chat/completions"
    req = urllib.request.Request(
        url, data=body, method="POST", headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read()
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        action = f"exam request failed for model {model_id!r}"
        raise backend.request_failed(action, url, exc) from exc
    resp = json.loads(raw)
    text = resp["choices"][0]["message"]["content"] or ""
    usage = resp.get("usage", {})
    return text, usage, hashlib.sha256(body).hexdigest(), hashlib.sha256(raw).hexdigest()


class Budget:
    """A spend ceiling enforced BEFORE each paid call.

    The old cap was checked only between whole models, so any positive cap still
    funded all 40 calls of the next model. This projects the cost of the next
    single call and refuses it if that would breach the cap.
    """

    RATE_USD_PER_M = 1.0  # conservative blended ceiling; posted prices are provider-specific

    def __init__(self, cap_usd: float):
        self.cap = cap_usd
        self.spent = 0.0

    def _usd(self, tokens: int) -> float:
        return tokens / 1e6 * self.RATE_USD_PER_M

    def can_afford(self, projected_tokens: int) -> bool:
        return self.spent + self._usd(projected_tokens) <= self.cap

    def charge(self, tokens: int) -> None:
        # A missing usage block must never charge 0, or the cap never advances.
        self.spent += self._usd(tokens if tokens else self.projected_item_tokens())

    @staticmethod
    def projected_item_tokens() -> int:
        longest = max(len(it["prompt"]) for it in EXAM["items"])
        return longest // 3 + EXAM["meta"]["max_answer_tokens"]  # ~3 chars/token, worst case


def examine(model_id: str, asker, budget: "Budget | None" = None):
    """Sit the full exam; asker(model_id, prompt) -> (text, usage, req_sha, resp_sha).

    An exam cut short by the spend cap CANNOT pass: a partial score is not a
    qualification, and letting one through would put an unexamined model in the fix.
    """
    correct, receipts, tokens = 0, [], 0
    aborted = False
    for item in EXAM["items"]:
        if budget is not None and not budget.can_afford(Budget.projected_item_tokens()):
            aborted = True
            break
        text, usage, req_sha, resp_sha = asker(model_id, item["prompt"])
        used = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        if budget is not None:
            budget.charge(used)
        ok = grade(text, item["answer"])
        correct += ok
        tokens += used
        receipts.append({"item": item["id"], "ok": ok, "req_sha256": req_sha[:16],
                         "resp_sha256": resp_sha[:16]})
    total = len(EXAM["items"])
    score = correct / total
    return {"model": model_id, "score": round(score, 4), "correct": correct,
            "total": total, "administered": len(receipts), "aborted": aborted,
            "passed": (not aborted) and len(receipts) == total
                      and score >= EXAM["meta"]["threshold"],
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
    if "--help" in argv or "-h" in argv:
        print(__doc__.strip())
        return

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

    # Real mode measures capability. Price provenance does not affect an exam verdict.
    try:
        api_base = backend.base_url()
    except ValueError as exc:
        sys.exit(str(exc))
    api_key = backend.api_key()
    if backend.is_canonical_metered_base(api_base) and not api_key:
        sys.exit(
            "real exam runs need COG_API_KEY or OPENROUTER_API_KEY at the canonical "
            "OpenRouter endpoint (this spends real money); use --dry-run or "
            "--self-test for the free paths"
        )
    def arg(flag, default):
        i = argv.index(flag) + 1 if flag in argv else -1
        if i > 0 and i >= len(argv):
            sys.exit(f"{flag} needs a value")
        return argv[i] if i > 0 else default

    max_spend = float(arg("--max-spend-usd", "0.25"))
    if max_spend <= 0:
        sys.exit("--max-spend-usd must be positive")
    models = (arg("--models", "") or ",".join(cogfix.DATA["live_fix_allowlist"])).split(",")

    budget = Budget(max_spend)
    per_model = Budget.projected_item_tokens() * len(EXAM["items"])
    print(f"qualify — REAL exam ({exam_id}) for {len(models)} models, cap ${max_spend} "
          f"(worst case ~${budget._usd(per_model):.3f}/model)")
    results = []
    for mid in models:
        # Refuse to start a model we cannot afford to finish — a half-sat exam is
        # worthless (it can never pass) and paying for one is pure waste.
        if not budget.can_afford(per_model):
            print(f"  spend cap ${max_spend} reached (${budget.spent:.4f} used); "
                  f"skipping {mid.strip()} and remaining models")
            break
        asker = lambda m, p: ask_model(m, p, api_key, api_base)  # noqa: E731
        try:
            r = examine(mid.strip(), asker, budget=budget)
        except backend.RequestFailed as exc:
            sys.exit(str(exc))
        results.append(r)
        note = "  ABORTED mid-exam (spend cap)" if r["aborted"] else ""
        print(f"  {r['model']:<36} {r['correct']}/{r['total']} ({r['score']:.0%})  "
              f"{'PASS' if r['passed'] else 'FAIL'}{note}")

    payload = {"date": today, "mode": "live", "exam": exam_id,
               "exam_sha256": fingerprint(), "threshold": EXAM["meta"]["threshold"],
               "endpoint": api_base,
               "spend_cap_usd": max_spend, "spend_usd_est": round(budget.spent, 6),
               "results": [{k: v for k, v in r.items() if k != "item_receipts"} for r in results],
               "receipts": {r["model"]: r["item_receipts"] for r in results},
               "qualified": [r["model"] for r in results if r["passed"]]}
    out = ROOT / "fixer" / "qualified.json"
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\n  qualified: {len(payload['qualified'])}/{len(results)}  -> {out}")
    print("  fixerd will now gate the fix on this exam (while fresh, <= 7 days).")


if __name__ == "__main__":
    main(sys.argv[1:])

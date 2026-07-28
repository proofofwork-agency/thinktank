"""Independent verification of the S3 result. Written BEFORE any S3 number existed.

The coordinator does not grade an experiment by reading the executor's summary. This re-derives
the verdict from per-task raw outcomes, applies the thresholds fixed in docs/S3_PREREGISTRATION.md
(commit 8ee0170), and audits the split for leakage itself.

Deliberately paranoid about the things that make a training result look better than it is:

  L  LEAKAGE      no test-family expression may appear in training, by expression identity
                  (sympy srepr) — not by task id, which is trivially made to differ
  B  BUDGET       base and trained must have been sampled at identical N / temperature / prompt;
                  an asymmetry here manufactures a gain
  P  PAIRED       same tasks to both models => McNemar/sign over DISCORDANT pairs only.
                  The unpaired proportion test wastes most of the signal and is not used.
  S  SEEDS        one seed is not a result; >=3, reported separately, never averaged into one
  D  DIRECTION    in-domain gain with no held-out gain is a NEGATIVE for the thesis (memorisation),
                  and no movement anywhere is a BROKEN RUN, not evidence

Input: a JSONL of per-task outcomes, one record per (task, model, seed):

  {"task_id": "...", "family": "arctan", "split": "test"|"train",
   "model": "base"|"trained", "seed": 0, "solved": true,
   "n": 8, "temperature": 0.7, "prompt_sha": "..."}

  python experiments/verify_s3.py --results s3_outcomes.jsonl \
      --train-tasks tasks/s3_train.jsonl --test-tasks tasks/s3_test.jsonl
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from math import comb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TRAIN_FAMILIES = {"poly", "trig", "chain", "exp", "prod", "log", "mixed"}
TEST_FAMILIES = {"arctan", "arcsin", "sqrtpow", "byparts", "hyper", "trigpow", "loglin", "ratio"}


def sign_test_critical(b: int):
    """Smallest wins-in-one-direction with two-sided p < 0.05, given b discordant pairs."""
    for k in range(b // 2 + 1, b + 1):
        p = 2 * sum(comb(b, i) for i in range(k, b + 1)) / 2 ** b
        if p < 0.05:
            return k, p
    return None, None


def sign_test_p(wins: int, b: int) -> float:
    """Exact two-sided sign-test p-value for `wins` of `b` discordant pairs."""
    if b == 0:
        return 1.0
    hi = max(wins, b - wins)
    return min(1.0, 2 * sum(comb(b, i) for i in range(hi, b + 1)) / 2 ** b)


def audit_leakage(train_path, test_path):
    """L — expression identity, not task id. Returns (n_train, n_test, overlap)."""
    import sympy as sp

    def ident(path):
        out = set()
        for line in open(path):
            t = json.loads(line)
            try:
                out.add(sp.srepr(sp.sympify(t["gold"])))
            except Exception:
                out.add("RAW:" + str(t.get("gold")))
        return out

    tr, te = ident(train_path), ident(test_path)
    return len(tr), len(te), tr & te


def load(results_path):
    rows = [json.loads(l) for l in open(results_path) if l.strip()]
    for r in rows:
        for k in ("task_id", "model", "seed", "solved", "split"):
            if k not in r:
                raise SystemExit(f"record missing {k!r}: {r}")
    return rows


def check_budget(rows):
    """B — an asymmetric inference budget manufactures a gain. Refuse to grade if it differs."""
    keys = ("n", "temperature", "prompt_sha")
    seen = collections.defaultdict(set)
    for r in rows:
        for k in keys:
            if k in r:
                seen[k].add((r["model"], r[k]))
    problems = []
    for k, pairs in seen.items():
        by_model = collections.defaultdict(set)
        for m, v in pairs:
            by_model[m].add(v)
        vals = {m: sorted(v) for m, v in by_model.items()}
        if len({tuple(v) for v in vals.values()}) > 1:
            problems.append(f"{k} differs between models: {vals}")
    return problems


def analyse(rows, split):
    """P/S — per-seed paired comparison over discordant pairs."""
    per_seed = collections.defaultdict(dict)
    for r in rows:
        if r["split"] != split:
            continue
        per_seed[r["seed"]][(r["task_id"], r["model"])] = bool(r["solved"])

    out = []
    for seed in sorted(per_seed):
        d = per_seed[seed]
        tasks = {t for (t, _m) in d}
        both = won = lost = neither = 0
        for t in tasks:
            b, tr = d.get((t, "base")), d.get((t, "trained"))
            if b is None or tr is None:
                continue
            if b and tr:
                both += 1
            elif tr and not b:
                won += 1
            elif b and not tr:
                lost += 1
            else:
                neither += 1
        disc = won + lost
        crit, _ = sign_test_critical(disc) if disc else (None, None)
        out.append({
            "seed": seed, "n_tasks": both + won + lost + neither,
            "both_right": both, "trained_only": won, "base_only": lost, "both_wrong": neither,
            "discordant": disc, "critical": crit,
            "p": round(sign_test_p(won, disc), 4),
            "base_pass": both + lost, "trained_pass": both + won,
            "significant": bool(disc and crit and won >= crit),
        })
    return out


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--train-tasks")
    ap.add_argument("--test-tasks")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = load(args.results)
    report = {"leakage": None, "budget_problems": check_budget(rows)}

    if args.train_tasks and args.test_tasks:
        n_tr, n_te, overlap = audit_leakage(args.train_tasks, args.test_tasks)
        report["leakage"] = {"train": n_tr, "test": n_te, "overlap": len(overlap),
                             "examples": sorted(overlap)[:5]}

    report["test"] = analyse(rows, "test")
    report["train"] = analyse(rows, "train")

    # D — apply the pre-registered decision rules.
    test_sig = [s["significant"] for s in report["test"]]
    train_sig = [s["significant"] for s in report["train"]]
    held_out_wins = sum(test_sig)
    if report["leakage"] and report["leakage"]["overlap"]:
        verdict = "INVALID — train/test leakage detected"
    elif report["budget_problems"]:
        verdict = "INVALID — inference budget differs between models"
    elif len(report["test"]) < 3:
        verdict = "INCOMPLETE — fewer than 3 seeds; a single seed is not a result"
    elif held_out_wins >= 2:
        verdict = "POSITIVE — held-out gain survives on a majority of seeds"
    elif any(train_sig) and not held_out_wins:
        verdict = "NEGATIVE (memorisation) — trains in-domain, does NOT transfer"
    elif not any(train_sig) and not held_out_wins:
        verdict = "BROKEN RUN or TRUE NULL — no movement in-domain either; debug before citing"
    else:
        verdict = "NEGATIVE — held-out effect not distinguishable from noise"
    report["verdict"] = verdict

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        lk = report["leakage"]
        print(f"L leakage        : {'(not checked)' if not lk else f'''train {lk['train']} / test {lk['test']} / OVERLAP {lk['overlap']}'''}")
        print(f"B budget         : {'OK' if not report['budget_problems'] else report['budget_problems']}")
        for split in ("test", "train"):
            print(f"\n{split.upper()} split ({'held-out concepts' if split=='test' else 'in-domain'}):")
            if not report[split]:
                print("  (no records)")
            for s in report[split]:
                mark = "SIGNIFICANT" if s["significant"] else "not significant"
                print(f"  seed {s['seed']}: base {s['base_pass']}/{s['n_tasks']} -> "
                      f"trained {s['trained_pass']}/{s['n_tasks']} | "
                      f"trained-only {s['trained_only']} base-only {s['base_only']} "
                      f"(discordant {s['discordant']}, need {s['critical']}) p={s['p']} -> {mark}")
        print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

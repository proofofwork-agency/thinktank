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


def outcome(r, metric):
    """Resolve pass@1 / pass@N from whichever fields the executor emitted.

    pass@1 and pass@N are DIFFERENT CLAIMS and the pre-registration requires both. A pass@N gain
    with flat pass@1 means training improved sampling diversity, not first-guess accuracy — and
    since the project's claim is cost-per-solved-task, that is the difference between "cheaper"
    and "no cheaper, just luckier". `solved` alone is ambiguous and is treated as pass@N.
    """
    if metric in r:
        return bool(r[metric])
    idx = r.get("first_certified_index", "__absent__")
    if idx != "__absent__":
        if idx is None:
            return False
        return idx == 0 if metric == "pass_at_1" else True
    if "attempts" in r and isinstance(r["attempts"], list):
        certified = [a["index"] for a in r["attempts"] if a.get("status") == "certified"]
        if not certified:
            return False
        return min(certified) == 0 if metric == "pass_at_1" else True
    if "solved" in r:                       # ambiguous legacy field: means pass@N
        return bool(r["solved"]) if metric == "pass_at_n" else None
    return None


def load(results_path):
    rows = [json.loads(l) for l in open(results_path) if l.strip()]
    for r in rows:
        for k in ("task_id", "model", "seed", "split"):
            if k not in r:
                raise SystemExit(f"record missing {k!r}: {r}")
        if all(outcome(r, m) is None for m in ("pass_at_1", "pass_at_n")):
            raise SystemExit(
                "record carries no resolvable outcome — need pass_at_1/pass_at_n, "
                f"first_certified_index, attempts[], or solved: {r}"
            )
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


def analyse(rows, split, metric, dedupe_prompts=False):
    """P/S — per-seed paired comparison over discordant pairs, for one metric.

    dedupe_prompts collapses tasks sharing a prompt_sha to a single trial. The forge dedupes on
    the ANSWER (str(F)); two distinct antiderivatives differing by a constant are the SAME
    QUESTION, so 244 held-out tasks carry only ~226 independent problems. Duplicated prompts are
    perfectly correlated — solve one, solve all — and the sign test assumes independent trials,
    so p-values on the raw set are slightly optimistic. Reported as a sensitivity check.
    """
    per_seed = collections.defaultdict(dict)
    seen_prompt = collections.defaultdict(set)
    for r in rows:
        if r["split"] != split:
            continue
        val = outcome(r, metric)
        if val is None:
            continue
        key = r["task_id"]
        if dedupe_prompts:
            sha = r.get("prompt_sha")
            if sha is not None:
                bucket = seen_prompt[(r["seed"], r["model"], sha)]
                if bucket:
                    continue          # a later task with the same question: same trial
                bucket.add(key)
                key = f"prompt:{sha}"
        per_seed[r["seed"]][(key, r["model"])] = val

    out = []
    for seed in sorted(per_seed):
        d = per_seed[seed]
        tasks = {t for (t, _m) in d}
        both = won = lost = neither = unpaired = 0
        for t in tasks:
            b, tr = d.get((t, "base")), d.get((t, "trained"))
            if b is None or tr is None:
                # A task present for one model and not the other cannot be paired. Silently
                # dropping it is how a manifest divergence turns into a confident verdict over
                # whatever happened to survive — so it is counted and surfaced, never swallowed.
                unpaired += 1
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
            "unpaired_dropped": unpaired,
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

    report["metrics"] = {}
    for metric in ("pass_at_1", "pass_at_n"):
        report["metrics"][metric] = {
            "test": analyse(rows, "test", metric),
            "train": analyse(rows, "train", metric),
        }
    # Sensitivity: same test on prompt-unique trials only. If the verdict agrees on both, the
    # duplicate questions are immaterial and we say so with a number rather than an assurance.
    report["prompt_deduped"] = {
        m: {sp_: analyse(rows, sp_, m, dedupe_prompts=True) for sp_ in ("test", "train")}
        for m in ("pass_at_1", "pass_at_n")
    }
    # The headline verdict is pass@1: it is the one that supports a cost-per-solved-task claim.
    report["test"] = report["metrics"]["pass_at_1"]["test"] or report["metrics"]["pass_at_n"]["test"]
    report["train"] = report["metrics"]["pass_at_1"]["train"] or report["metrics"]["pass_at_n"]["train"]
    report["headline_metric"] = ("pass_at_1" if report["metrics"]["pass_at_1"]["test"]
                                 else "pass_at_n")

    # D — apply the pre-registered decision rules.
    test_sig = [s["significant"] for s in report["test"]]
    train_sig = [s["significant"] for s in report["train"]]
    held_out_wins = sum(test_sig)
    # "the train split showed nothing" and "the train split was never measured" are different
    # facts and must not collapse into the same verdict — inferring BROKEN RUN from missing
    # records would report a clean negative as a bug. Caught by testing this grader on synthetic
    # cases with known answers, before any real result existed.
    train_measured = bool(report["train"])
    train_moved = any(train_sig)
    # Did the in-domain split move at all, even below significance? Distinguishes a genuinely
    # inert run from one that trained weakly.
    train_any_discordant = any(s["discordant"] for s in report["train"])

    worst_unpaired = max((s["unpaired_dropped"] for m in report["metrics"].values()
                          for sp_ in m.values() for s in sp_), default=0)
    total_seen = max((s["n_tasks"] for m in report["metrics"].values()
                      for sp_ in m.values() for s in sp_), default=0)
    report["max_unpaired_dropped"] = worst_unpaired

    if report["leakage"] and report["leakage"]["overlap"]:
        verdict = "INVALID — train/test leakage detected"
    elif worst_unpaired and worst_unpaired > 0.05 * max(total_seen + worst_unpaired, 1):
        verdict = (f"INVALID — {worst_unpaired} tasks appear for only one model and could not be "
                   "paired (>5%). The two runs did not evaluate the same manifest.")
    elif report["budget_problems"]:
        verdict = "INVALID — inference budget differs between models"
    elif len(report["test"]) < 3:
        verdict = "INCOMPLETE — fewer than 3 seeds; a single seed is not a result"
    elif held_out_wins >= 2:
        verdict = "POSITIVE — held-out gain survives on a majority of seeds"
    elif not train_measured:
        verdict = ("NEGATIVE (held-out) — but the TRAIN split was not measured, so this cannot "
                   "distinguish 'did not transfer' from 'training never took'. Re-run with both "
                   "splits, as the pre-registration requires.")
    elif train_moved:
        verdict = "NEGATIVE (memorisation) — trains in-domain, does NOT transfer"
    elif not train_any_discordant:
        verdict = "BROKEN RUN — the trained model is identical to base in-domain; debug before citing"
    else:
        verdict = "NEGATIVE — held-out effect not distinguishable from noise"
    report["verdict"] = verdict
    report["train_measured"] = train_measured

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        lk = report["leakage"]
        print(f"L leakage        : {'(not checked)' if not lk else f'''train {lk['train']} / test {lk['test']} / OVERLAP {lk['overlap']}'''}")
        print(f"B budget         : {'OK' if not report['budget_problems'] else report['budget_problems']}")
        for metric in ("pass_at_1", "pass_at_n"):
          for split in ("test", "train"):
            rowset = report["metrics"][metric][split]
            if not rowset:
                continue
            print(f"\n[{metric}] {split.upper()} split "
                  f"({'held-out concepts' if split=='test' else 'in-domain'}):")
            for s in rowset:
                mark = "SIGNIFICANT" if s["significant"] else "not significant"
                print(f"  seed {s['seed']}: base {s['base_pass']}/{s['n_tasks']} -> "
                      f"trained {s['trained_pass']}/{s['n_tasks']} | "
                      f"trained-only {s['trained_only']} base-only {s['base_only']} "
                      f"(discordant {s['discordant']}, need {s['critical']}) p={s['p']} -> {mark}")
        print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

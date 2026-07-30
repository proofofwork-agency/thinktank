#!/usr/bin/env python3
"""Run IRO POMDP ablations and print a compact report."""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

# allow running as script from this dir
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import run_episode

MODES = [
    "full",
    "no_eyes",
    "no_search",
    "no_verify",
    "random_sense",
    "always_look",
    "never_look",
]


def aggregate(mode: str, n: int = 30, shift: bool = True) -> dict:
    successes = []
    looks = []
    steps = []
    false_commits = []
    rewards = []
    for i in range(n):
        st = run_episode(mode, seed=1000 + i, shift=shift)
        successes.append(1.0 if st.success else 0.0)
        looks.append(st.looks)
        steps.append(st.steps)
        false_commits.append(st.false_commits)
        rewards.append(st.reward)
    return {
        "mode": mode,
        "n": n,
        "success_rate": statistics.mean(successes),
        "mean_looks": statistics.mean(looks),
        "mean_steps": statistics.mean(steps),
        "mean_false_commits": statistics.mean(false_commits),
        "mean_reward": statistics.mean(rewards),
    }


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    rows = [aggregate(m, n=n, shift=True) for m in MODES]
    # pretty table
    headers = ["mode", "success", "looks", "steps", "false_cmt", "reward"]
    print("IRO POMDP v0 — n={} episodes, mid-run door shift on".format(n))
    print(
        f"{'mode':<14} {'success':>8} {'looks':>8} {'steps':>8} {'false_cmt':>10} {'reward':>8}"
    )
    print("-" * 62)
    for r in rows:
        print(
            f"{r['mode']:<14} {r['success_rate']:>8.2f} {r['mean_looks']:>8.2f} "
            f"{r['mean_steps']:>8.2f} {r['mean_false_commits']:>10.2f} {r['mean_reward']:>8.3f}"
        )
    out = Path(__file__).resolve().parent / "last_results.json"
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nWrote {out}")

    full = next(r for r in rows if r["mode"] == "full")
    rnd = next(r for r in rows if r["mode"] == "random_sense")
    nv = next(r for r in rows if r["mode"] == "no_verify")
    # soft pass criteria (toy) — Run ablation must be *causal* on success/false geometry
    ok_looks = full["mean_looks"] <= rnd["mean_looks"] + 0.5 or full["success_rate"] >= rnd["success_rate"]
    ok_verify_fc = full["mean_false_commits"] < nv["mean_false_commits"]
    ok_verify_succ = full["success_rate"] > nv["success_rate"] + 0.05
    ok_success = full["success_rate"] >= 0.3
    print(
        "\nClaim check (soft): "
        f"looks/success vs random_sense={'PASS' if ok_looks else 'WEAK'}; "
        f"false_commits full<no_verify={'PASS' if ok_verify_fc else 'FAIL'}; "
        f"success full>no_verify={'PASS' if ok_verify_succ else 'FAIL'}; "
        f"full success>={0.3}={'PASS' if ok_success else 'FAIL'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

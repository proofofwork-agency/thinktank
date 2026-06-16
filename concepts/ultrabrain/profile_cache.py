"""Profile EvidenceStore active projection cache behavior.

This is a tiny local harness, not a benchmark suite. It appends a configurable
number of trusted beliefs, then compares repeated warm active_beliefs() calls
against cold full-replay calls from fresh EvidenceStore instances.
"""

import argparse
import json
import os
import tempfile
import time

from ultrabrain.evidence import EvidenceStore


def _time(label, fn):
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    return label, elapsed, result


def run(k=2000, n=200, root=None):
    cleanup = None
    if root is None:
        cleanup = tempfile.TemporaryDirectory()
        root = cleanup.name
    state_root = os.path.join(root, "state")
    store = EvidenceStore("profile", root=state_root)

    for i in range(k):
        store.record_user_claim(f"depends_on(module_{i},core)", note="cache profile")

    # Prime the cache before timing repeated warm reads.
    store.active_beliefs()

    _label, warm_seconds, _ = _time("warm", lambda: [store.active_beliefs() for _ in range(n)])
    _label, cold_seconds, _ = _time(
        "cold",
        lambda: [EvidenceStore("profile", root=state_root).active_beliefs() for _ in range(n)],
    )
    one_write_start = time.perf_counter()
    store.record_user_claim(f"depends_on(module_{k},core)", note="cache profile write")
    after_write_count = len(store.active_beliefs())
    write_plus_read_seconds = time.perf_counter() - one_write_start

    report = {
        "beliefs": k,
        "repeated_reads": n,
        "warm_total_seconds": round(warm_seconds, 6),
        "warm_per_read_ms": round((warm_seconds / n) * 1000, 6),
        "cold_total_seconds": round(cold_seconds, 6),
        "cold_per_read_ms": round((cold_seconds / n) * 1000, 6),
        "speedup_x": round(cold_seconds / warm_seconds, 2) if warm_seconds else None,
        "write_plus_first_read_seconds": round(write_plus_read_seconds, 6),
        "after_write_active_beliefs": after_write_count,
    }
    if cleanup is not None:
        cleanup.cleanup()
    return report


def main():
    parser = argparse.ArgumentParser(description="Profile EvidenceStore projection cache")
    parser.add_argument("--beliefs", type=int, default=2000)
    parser.add_argument("--reads", type=int, default=200)
    parser.add_argument("--root", default=None, help="optional existing scratch root")
    args = parser.parse_args()
    print(json.dumps(run(k=args.beliefs, n=args.reads, root=args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

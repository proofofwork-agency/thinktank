"""Slice 2 — the verified-search loop (the data-forge).

For each task a proposer samples N candidates; the hardened gate certifies; CERTIFIED solutions
are appended to the HMAC ledger AND to an SFT dataset (``data/verified_traces.jsonl``) of
``{task_id, prompt, solution, kind}`` — the verified, sovereign training data for QLoRA.
This is how the weights get better without a frontier teacher: ``no evidence -> no clean training
example`` (thoughts/22, 24).

On the CAS path only, every proposed candidate is judged (no first-success break). Certified and
rejected outcomes are also projected into a separate, explicitly UNTRUSTED preference artifact for
DPO. That artifact is not a ledger and never contains raw verifier diagnostics or expected values.

SECURITY (Codex review): safety is a capability of the selected VERIFIER, not the proposer name or a
task ``kind`` string.  ``CASVerifier`` treats model output as inert, allowlisted math data and never
executes it, so real-model CAS certificates may enter trusted sinks.  The code verifiers execute
UNTRUSTED model output and remain fail-closed: their in-process judge is forgeable via stdlib
reflection and rlimits are not a host jail. ``--unsafe`` runs those executing paths for diagnostics
only (no trusted writes). Sound code certification awaits the subordinate-jailed executor.

  python run_verified_search.py --proposer mock --ledger_secret dev    # zero-ML, tests the loop
  ULTRABRAIN_LEDGER_SECRET=$(openssl rand -hex 16) \
  python run_verified_search.py --proposer llm \
      --base_url http://localhost:8000/v1 --model Qwen/Qwen3-Coder-14B  # your local Qwen3-Coder-14B
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from ultrabrain.propose import DiffusionFIMProposer, NoisyProposer  # noqa: E402
from ultrabrain.propose.llm import LLMProposer, prompt_for  # noqa: E402
from ultrabrain.verify import (  # noqa: E402
    CASVerifier,
    CERTIFIED,
    CodeTestVerifier,
    Gate,
    ISOLATION_AVAILABLE,
    Ledger,
    REJECTED,
    StructuredCodeVerifier,
    harden,
    run_tests_isolated,
)

_TASK_ERROR_ARCHETYPES = {"scalar_multiple", "plus_x", "derivative"}
_TASK_FAMILIES = {"poly", "prod", "trig", "exp", "chain", "log", "unlabelled"}


def load_jsonl(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def _append_jsonl(path: str, records: list[dict]) -> None:
    if not records:
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


def _digest_text(text) -> str:
    raw = (
        text.encode("utf-8", errors="replace")
        if isinstance(text, str)
        else f"<{type(text).__name__}>".encode()
    )
    return hashlib.sha256(raw).hexdigest()


def _error_archetype(task: dict, rejected_candidate: str, rejected_signal: dict) -> str:
    """Return trusted task metadata when available; otherwise a fixed verifier-code bucket."""
    distractors = task.get("distractors", [])
    archetypes = task.get("distractor_archetypes", [])
    if (
        isinstance(distractors, list)
        and isinstance(archetypes, list)
        and len(distractors) == len(archetypes)
    ):
        for distractor, archetype in zip(distractors, archetypes):
            if (
                rejected_candidate == distractor
                and isinstance(archetype, str)
                and archetype in _TASK_ERROR_ARCHETYPES
            ):
                return archetype
    # Model-generated errors have no trusted semantic label. Grouping by the sanitized decision
    # code is intentionally coarse and reported as such; it must not flatter raw pair volume.
    return f"verdict_{rejected_signal['code'].replace('.', '_')}"


def _task_family(task: dict) -> str:
    family = task.get("task_family", "unlabelled")
    return family if family in _TASK_FAMILIES else "unlabelled"


def _unique_projected_candidates(projected_candidates):
    unique = {}
    for projected in projected_candidates:
        unique.setdefault(_digest_text(projected["candidate"]), projected)
    return list(unique.values())


def _cas_preference_pairs(task: dict, projected_candidates) -> list[dict]:
    """Build unique CAS preference pairs from sanitized projections of both outcomes.

    ``chosen`` and ``rejected`` are the two explicit DPO training slots and therefore necessarily
    contain candidate expressions. No other field can carry candidate text; the signal projection
    itself is fixed-schema codes/counts/digests produced at the Gate boundary.
    """
    certified = _unique_projected_candidates(
        [item for item in projected_candidates if item["signal"]["status"] == CERTIFIED]
    )
    rejected = _unique_projected_candidates(
        [item for item in projected_candidates if item["signal"]["status"] == REJECTED]
    )
    pairs = []
    for chosen in certified:
        chosen_signal = chosen["signal"]
        for negative in rejected:
            rejected_signal = negative["signal"]
            pair_digest = hashlib.sha256(
                json.dumps(
                    {
                        "task_id": task.get("id"),
                        "chosen_digest": chosen_signal["evidence"]["candidate_digest"],
                        "rejected_digest": rejected_signal["evidence"]["candidate_digest"],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            pairs.append({
                "schema": "ultrabrain.cas.preference_pair.v1",
                "artifact_class": "untrusted_preference_diagnostics",
                "trusted": False,
                "ledger_eligible": False,
                "task_id": task.get("id"),
                "kind": "cas",
                "task_family": _task_family(task),
                "prompt": prompt_for(task),
                "chosen": chosen["candidate"],
                "rejected": negative["candidate"],
                "chosen_signal": chosen_signal,
                "rejected_signal": rejected_signal,
                "error_archetype": _error_archetype(
                    task,
                    negative["candidate"],
                    rejected_signal,
                ),
                "pair_digest": pair_digest,
            })
    return pairs


def build_proposer(args):
    if args.proposer == "llm":
        return LLMProposer(base_url=args.base_url, model=args.model, temperature=args.temperature)
    if args.proposer == "fim":
        kw = {"temperature": args.temperature, "seed": args.seed}
        if args.fim_checkpoint:
            kw["checkpoint"] = args.fim_checkpoint
        if args.fim_tokenizer:
            kw["tokenizer_path"] = args.fim_tokenizer
        return DiffusionFIMProposer(**kw)
    return NoisyProposer(seed=args.seed)


def verifier_for(task, isolated=False):
    """Pick the certifier for a task on this TRUST path (ledger + SFT). JUDGE-ONLY.

    * cas -> airtight CAS (symbolic, not candidate-forgeable).
    * code -> the parent-owned-oracle :class:`StructuredCodeVerifier` (judge_v1). A code task WITHOUT a
      judge_v1 spec ABSTAINS — it is NEVER certified via the forgeable assert runner (Codex final
      review). judge_v1 closes the original frame-walk forgery but is NOT adversarially sound in-process
      (the same-address-space residual remains; sound verdict integrity needs the subordinate candidate
      executor — see judge.py). Untrusted-model output is fail-closed upstream regardless.
    ``isolated`` is retained for signature compatibility only; it does not apply (the judge runs its own
    child process). rlimits are defense in depth, not a jail.
    """
    if task.get("kind") == "cas":
        return CASVerifier()
    # TRUST PATH IS JUDGE-ONLY (Codex final review): the legacy assert runner is a live false-cert
    # authority (a candidate frame-mutates its in-interpreter verdict), so a code task WITHOUT a
    # judge_v1 spec ABSTAINS here — it is never certified into the ledger/SFT via the assert runner.
    # ``isolated`` no longer applies; the judge isolates its own worker.
    return StructuredCodeVerifier()


def verifier_executes_candidate(verifier) -> bool:
    """Fail-closed capability query used before any real-model proposer is constructed.

    A concrete verifier class must opt in explicitly to the non-executing trust path.  The lookup
    deliberately does not inherit: a subclass that overrides ``verify`` but forgets to redeclare
    the capability defaults to executing. Missing, malformed, or truthy declarations are treated
    as executing; neither proposer class nor task metadata can confer trust.
    """
    return type(verifier).__dict__.get("executes_candidate", True) is not False


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default=os.path.join(ROOT, "tasks", "micro_codebench.jsonl"))
    ap.add_argument("--proposer", choices=["mock", "llm", "fim"], default="mock")
    ap.add_argument("--n", type=int, default=8, help="candidates sampled per task")
    ap.add_argument("--base_url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="Qwen/Qwen3-Coder-14B")
    ap.add_argument("--fim_checkpoint", default=None,
                    help="diffusion denoiser checkpoint for --proposer fim (default: checkpoints/diffusion.pt)")
    ap.add_argument("--fim_tokenizer", default=None,
                    help="tokenizer json for --proposer fim (default: checkpoints/tokenizer.json)")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "verified_traces.jsonl"))
    ap.add_argument(
        "--pairs_out",
        default=os.path.join(ROOT, "data", "cas_preference_pairs_UNTRUSTED.jsonl"),
        help="append-only CAS DPO diagnostics (explicitly untrusted; never a belief ledger)",
    )
    ap.add_argument("--ledger", default=os.path.join(ROOT, "state", "verified_ledger.jsonl"))
    ap.add_argument("--ledger_secret", default=None, help="HMAC secret (else ULTRABRAIN_LEDGER_SECRET)")
    ap.add_argument("--unsafe", action="store_true",
                    help="DANGEROUS: run an untrusted proposer for DIAGNOSTICS ONLY (no ledger/SFT "
                         "writes) and allow the insecure default ledger secret. rlimits are not a host "
                         "jail; use a throwaway environment.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.n < 1:
        print("ERROR: --n must be >= 1", file=sys.stderr)
        return 2
    if os.path.abspath(args.pairs_out) in {
        os.path.abspath(args.out),
        os.path.abspath(args.ledger),
    }:
        print("ERROR: --pairs_out must be separate from the trusted trace and ledger paths",
              file=sys.stderr)
        return 2

    tasks = load_jsonl(args.tasks)
    verifiers = [verifier_for(task) for task in tasks]

    # Model output is untrusted, but whether it is EXECUTED is a capability of the selected verifier.
    # Never infer this from proposer identity or task ``kind``: unknown verifier capabilities fail
    # closed. For an executing verifier there are TWO DISTINCT, currently UNBUILT requirements:
    #   (1) VERDICT INTEGRITY needs a SUBORDINATE candidate executor (candidate in its OWN process,
    #       separate from the signer/decider). The in-process judge is forgeable via stdlib reflection.
    #   (2) HOST CONTAINMENT needs an outer OS boundary (uid/container/seccomp). rlimits are NOT a jail.
    # An outer boundary (2) does NOT provide (1).
    untrusted = args.proposer in ("llm", "fim")
    executes_candidate = any(verifier_executes_candidate(v) for v in verifiers)
    unsafe_execution = untrusted and executes_candidate
    isolated = unsafe_execution and not args.unsafe
    if isolated and not ISOLATION_AVAILABLE:
        print("ERROR: POSIX rlimits unavailable but required to execute untrusted model output "
              "(--proposer llm/fim). Run where `resource` works / in a container, or pass --unsafe.",
              file=sys.stderr)
        return 2

    # Model output executed as code CANNOT be soundly certified into trusted sinks by judge_v1:
    # the candidate shares the worker's interpreter with the signer, so stdlib reflection can drive the
    # honest worker to HMAC-sign forged values (KNOWN residual). An outer container / separate uid /
    # seccomp boundary does NOT fix this — it isolates the host, not candidate-from-signer WITHIN the
    # worker (Codex final review). The only sound fix is a subordinate-jailed EXECUTOR (candidate in
    # its OWN process, decider/signer OUTSIDE it, value-only authenticated channel), which is NOT built.
    # Therefore: real proposer + executing verifier -> NEVER writes trusted ledger/SFT. No flag
    # enables it. A non-executing verifier (currently CASVerifier) does not need this boundary.
    if unsafe_execution and not args.unsafe:
        print("ERROR: --proposer llm/fim executes UNTRUSTED code and the in-process judge cannot "
              "soundly certify it — the candidate shares the worker interpreter with the signer, so "
              "stdlib reflection forges signed values (KNOWN residual; see judge.py). No trusted "
              "ledger/SFT will be written until a subordinate-jailed EXECUTOR exists (candidate in its "
              "own process, decider outside; an outer container does NOT substitute). Pass --unsafe to "
              "run DIAGNOSTICS ONLY (no ledger / no SFT writes).", file=sys.stderr)
        return 2

    # An explicitly unsafe executing run is diagnostics-only. A real proposer behind a verifier that
    # declares ``executes_candidate = False`` remains eligible for trusted CAS sinks.
    suppress_trusted = unsafe_execution

    # Trace collection writes trusted beliefs: require a private secret (unless we suppress writes).
    secret = args.ledger_secret or os.environ.get("ULTRABRAIN_LEDGER_SECRET")
    if secret is None and not args.unsafe:
        print("ERROR: trace collection writes trusted beliefs to the ledger. Set --ledger_secret or "
              "ULTRABRAIN_LEDGER_SECRET (or pass --unsafe to use the insecure default).", file=sys.stderr)
        return 2

    if any(task.get("kind") == "cas" for task in tasks):
        try:
            CASVerifier.require_available()
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    proposer = build_proposer(args)
    # No trusted sink when suppressed: the gate gets no ledger, and no SFT traces are written.
    ledger = None if suppress_trusted else Ledger(args.ledger, secret=secret)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    count_before = ledger.count() if ledger is not None else 0

    traces, pairs, solved, attempts = [], [], 0, 0
    cas_attempts = code_attempts = certified_attempts = 0
    status_counts = Counter()
    distinct_candidates_by_task = {}
    cas_candidate_digests = set()
    certified_candidate_digests = set()
    rejected_candidate_digests = set()
    t0 = time.time()
    for task, verifier in zip(tasks, verifiers):
        gate = Gate(verifier, ledger)
        task_projected_candidates = []
        task_solved = False
        task_candidate_digests = set()
        for candidate in proposer.propose(task, args.n):
            attempts += 1
            is_cas = task.get("kind") == "cas"
            cas_attempts += int(is_cas)
            code_attempts += int(not is_cas)
            if is_cas:
                candidate_digest = _digest_text(candidate)
                task_candidate_digests.add(candidate_digest)
                cas_candidate_digests.add(candidate_digest)
            outcome = gate.judge(task, candidate)
            status_counts[outcome.verdict.status] += 1
            if is_cas:
                # Project EVERY CAS outcome at the source boundary, including certified and
                # abstaining outcomes. Pair construction later can only see this sanitized view.
                signal = outcome.cas_training_signal()
                task_projected_candidates.append({
                    "candidate": candidate,
                    "signal": signal,
                })
                if signal["status"] == CERTIFIED:
                    certified_candidate_digests.add(signal["evidence"]["candidate_digest"])
                elif signal["status"] == REJECTED:
                    rejected_candidate_digests.add(signal["evidence"]["candidate_digest"])
            if outcome.certified:
                traces.append({
                    "task_id": task.get("id"),
                    "kind": task.get("kind", "code"),
                    "prompt": prompt_for(task),
                    "solution": candidate,
                    "verify_detail": outcome.verdict.detail,
                })
                certified_attempts += 1
                task_solved = True
                if not is_cas:
                    break  # code path remains first-success and fail-closed pending S4
        solved += int(task_solved)
        if task.get("kind") == "cas":
            distinct_candidates_by_task[task.get("id", "?")] = len(task_candidate_digests)
            pairs.extend(_cas_preference_pairs(task, task_projected_candidates))
    wall = time.time() - t0

    # SFT + ledger are TRUSTED sinks: write them only when the run is trusted (the mock proposer — our
    # own reference code). Any untrusted proposer is a suppressed diagnostics run and writes neither.
    if not suppress_trusted:
        _append_jsonl(args.out, traces)

    # Preference pairs are a separate UNTRUSTED artifact, never a belief sink. They may be useful
    # even in an explicitly unsafe diagnostics run, but are produced for CAS outcomes only.
    _append_jsonl(args.pairs_out, pairs)

    if ledger is not None:
        expected_count = count_before + len(traces)
        expected_head = ledger.head()
        chain_ok = ledger.verify_chain(expected_count=expected_count, expected_head=expected_head)
        ledger_count = ledger.count()
    else:
        expected_head, chain_ok, ledger_count = None, None, None

    distinct_errors = {
        (pair["task_id"], pair["rejected_signal"]["evidence"]["candidate_digest"]):
            (pair["task_family"], pair["error_archetype"])
        for pair in pairs
    }
    error_archetype_counts_by_family = {
        family: dict(sorted(Counter(
            archetype
            for item_family, archetype in distinct_errors.values()
            if item_family == family
        ).items()))
        for family in sorted({family for family, _ in distinct_errors.values()})
    }
    task_family_counts = Counter(_task_family(task) for task in tasks if task.get("kind") == "cas")
    result = {
        "proposer": args.proposer,
        "rlimits_applied": isolated,          # POSIX rlimits — defense in depth, NOT a jail
        "trusted_writes": not suppress_trusted,
        "tasks": len(tasks),
        "solved": solved,
        "attempts": attempts,
        "cas_attempts": cas_attempts,
        "code_attempts": code_attempts,
        "certified_attempts": certified_attempts,
        "outcome_counts": dict(sorted(status_counts.items())),
        "traces_written": 0 if suppress_trusted else len(traces),
        "out": None if suppress_trusted else args.out,
        "pairs_written": len(pairs),
        "pairs_out": args.pairs_out,
        "pairs_trusted": False,
        "distinct_candidates": len(cas_candidate_digests),
        "distinct_certified_candidates": len(certified_candidate_digests),
        "distinct_rejected_candidates": len(rejected_candidate_digests),
        "distinct_candidates_by_task": distinct_candidates_by_task,
        "mean_distinct_candidates_per_cas_task": (
            round(sum(distinct_candidates_by_task.values()) / len(distinct_candidates_by_task), 3)
            if distinct_candidates_by_task else 0.0
        ),
        "distinct_pair_digests": len({pair["pair_digest"] for pair in pairs}),
        "distinct_error_archetypes": len({
            archetype for _, archetype in distinct_errors.values()
        }),
        "error_archetype_counts": dict(sorted(Counter(
            archetype for _, archetype in distinct_errors.values()
        ).items())),
        "error_archetype_counts_by_family": error_archetype_counts_by_family,
        "task_family_counts": dict(sorted(task_family_counts.items())),
        "distinct_task_families": len(task_family_counts),
        "pairs_by_family": dict(sorted(Counter(
            pair["task_family"] for pair in pairs
        ).items())),
        "wall_seconds": round(wall, 3),
        "seconds_per_solved": round(wall / solved, 4) if solved else None,
        "ledger_count": ledger_count,
        "ledger_head": expected_head,
        "ledger_chain_ok": chain_ok,
        "note": ("DIAGNOSTICS ONLY (untrusted proposer): certificates are NOT "
                 "trustworthy and no ledger/SFT was written" if suppress_trusted else
                 "every written trace passed the gate -> the SFT set is verified by construction"),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif suppress_trusted:
        print(f"proposer={args.proposer} DIAGNOSTICS-ONLY (untrusted proposer) solved "
              f"{solved}/{len(tasks)} ({attempts} attempts) — certificates NOT trusted, no ledger/SFT written")
    else:
        print(f"proposer={args.proposer} rlimits={isolated} solved "
              f"{solved}/{len(tasks)} ({attempts} attempts, {result['seconds_per_solved']}s/solved)")
        print(f"wrote {result['traces_written']} verified traces -> {args.out}  "
              f"ledger_ok={chain_ok} (count={result['ledger_count']})")
        if cas_attempts:
            print(
                f"CAS preference diagnostics: {result['pairs_written']} pairs, "
                f"{result['distinct_candidates']} distinct candidates "
                f"(mean {result['mean_distinct_candidates_per_cas_task']}/task), "
                f"{result['distinct_error_archetypes']} error archetypes -> {args.pairs_out} "
                "[UNTRUSTED; not a ledger]"
            )
    return result


def main(argv=None):
    result = run(argv)
    return result if isinstance(result, int) else 0  # propagate fail-closed exit code to the process


if __name__ == "__main__":
    raise SystemExit(main())

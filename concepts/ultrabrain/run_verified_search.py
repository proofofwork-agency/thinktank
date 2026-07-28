"""Slice 2 — the verified-search loop (the data-forge).

For each task a proposer samples N candidates; the hardened gate certifies; CERTIFIED solutions
are written to the HMAC ledger AND to an SFT dataset (``data/verified_traces.jsonl``) of
``{task_id, prompt, solution, kind}`` — the verified, sovereign training data for QLoRA.
This is how the weights get better without a frontier teacher: ``no evidence -> no clean training
example`` (thoughts/22, 24).

SECURITY (Codex review): ``--proposer llm/fim`` executes UNTRUSTED model output. The in-process judge
is NOT adversarially sound at the same uid (a candidate can forge signed verdicts AND write host files
via stdlib reflection), and rlimits are not a host jail — so untrusted proposers FAIL CLOSED here and
NEVER write the ledger/SFT. ``--unsafe`` runs them for DIAGNOSTICS ONLY (no trusted writes). Only the
mock proposer (our own reference code) writes trusted beliefs, and it requires a private ledger secret.
Sound certification of real model output awaits the subordinate-jailed executor (see judge.py).

  python run_verified_search.py --proposer mock --ledger_secret dev    # zero-ML, tests the loop
  ULTRABRAIN_LEDGER_SECRET=$(openssl rand -hex 16) \
  python run_verified_search.py --proposer llm \
      --base_url http://localhost:8000/v1 --model Qwen/Qwen3-Coder-14B  # your local Qwen3-Coder-14B
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from ultrabrain.propose import DiffusionFIMProposer, NoisyProposer  # noqa: E402
from ultrabrain.propose.llm import LLMProposer, prompt_for  # noqa: E402
from ultrabrain.verify import (  # noqa: E402
    CASVerifier,
    CodeTestVerifier,
    Gate,
    ISOLATION_AVAILABLE,
    Ledger,
    StructuredCodeVerifier,
    harden,
    run_tests_isolated,
)


def load_jsonl(path):
    return [json.loads(line) for line in open(path) if line.strip()]


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
    ap.add_argument("--ledger", default=os.path.join(ROOT, "state", "verified_ledger.jsonl"))
    ap.add_argument("--ledger_secret", default=None, help="HMAC secret (else ULTRABRAIN_LEDGER_SECRET)")
    ap.add_argument("--unsafe", action="store_true",
                    help="DANGEROUS: run an untrusted proposer for DIAGNOSTICS ONLY (no ledger/SFT "
                         "writes) and allow the insecure default ledger secret. rlimits are not a host "
                         "jail; use a throwaway environment.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    # Untrusted model output (llm OR diffusion-fim) executes candidate code. TWO DISTINCT, currently
    # UNBUILT requirements — do not conflate them, and NEITHER is an env flag (Codex final review):
    #   (1) VERDICT INTEGRITY needs a SUBORDINATE candidate executor (candidate in its OWN process,
    #       separate from the signer/decider). The in-process judge is forgeable via stdlib reflection.
    #   (2) HOST CONTAINMENT needs an outer OS boundary (uid/container/seccomp). rlimits are NOT a jail.
    # An outer boundary (2) does NOT provide (1). So untrusted proposers fail closed here regardless.
    untrusted = args.proposer in ("llm", "fim")
    isolated = untrusted and not args.unsafe          # apply rlimits to the legacy assert-runner path
    if isolated and not ISOLATION_AVAILABLE:
        print("ERROR: POSIX rlimits unavailable but required to execute untrusted model output "
              "(--proposer llm/fim). Run where `resource` works / in a container, or pass --unsafe.",
              file=sys.stderr)
        return 2

    # Untrusted model output CANNOT be soundly certified into trusted sinks by the in-process judge:
    # the candidate shares the worker's interpreter with the signer, so stdlib reflection can drive the
    # honest worker to HMAC-sign forged values (KNOWN residual). An outer container / separate uid /
    # seccomp boundary does NOT fix this — it isolates the host, not candidate-from-signer WITHIN the
    # worker (Codex final review). The only sound fix is a subordinate-jailed EXECUTOR (candidate in
    # its OWN process, decider/signer OUTSIDE it, value-only authenticated channel), which is NOT built.
    # Therefore: untrusted proposer -> NEVER writes trusted ledger/SFT. No env flag enables it.
    if untrusted and not args.unsafe:
        print("ERROR: --proposer llm/fim executes UNTRUSTED code and the in-process judge cannot "
              "soundly certify it — the candidate shares the worker interpreter with the signer, so "
              "stdlib reflection forges signed values (KNOWN residual; see judge.py). No trusted "
              "ledger/SFT will be written until a subordinate-jailed EXECUTOR exists (candidate in its "
              "own process, decider outside; an outer container does NOT substitute). Pass --unsafe to "
              "run DIAGNOSTICS ONLY (no ledger / no SFT writes).", file=sys.stderr)
        return 2

    # Untrusted proposer -> diagnostics only, trusted writes suppressed regardless of any flag.
    suppress_trusted = untrusted

    # Trace collection writes trusted beliefs: require a private secret (unless we suppress writes).
    secret = args.ledger_secret or os.environ.get("ULTRABRAIN_LEDGER_SECRET")
    if secret is None and not args.unsafe:
        print("ERROR: trace collection writes trusted beliefs to the ledger. Set --ledger_secret or "
              "ULTRABRAIN_LEDGER_SECRET (or pass --unsafe to use the insecure default).", file=sys.stderr)
        return 2

    tasks = load_jsonl(args.tasks)
    proposer = build_proposer(args)
    # No trusted sink when suppressed: the gate gets no ledger, and no SFT traces are written.
    ledger = None if suppress_trusted else Ledger(args.ledger, secret=secret)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    count_before = ledger.count() if ledger is not None else 0

    traces, solved, attempts = [], 0, 0
    t0 = time.time()
    for task in tasks:
        gate = Gate(verifier_for(task, isolated), ledger)
        for candidate in proposer.propose(task, args.n):
            attempts += 1
            outcome = gate.judge(task, candidate)
            if outcome.certified:
                traces.append({
                    "task_id": task.get("id"),
                    "kind": task.get("kind", "code"),
                    "prompt": prompt_for(task),
                    "solution": candidate,
                    "verify_detail": outcome.verdict.detail,
                })
                solved += 1
                break  # one verified trace per task is enough for the dataset
    wall = time.time() - t0

    # SFT + ledger are TRUSTED sinks: write them only when the run is trusted (the mock proposer — our
    # own reference code). Any untrusted proposer is a suppressed diagnostics run and writes neither.
    if not suppress_trusted:
        with open(args.out, "w") as fh:
            for tr in traces:
                fh.write(json.dumps(tr) + "\n")

    if ledger is not None:
        expected_count = count_before + len(traces)
        expected_head = ledger.head()
        chain_ok = ledger.verify_chain(expected_count=expected_count, expected_head=expected_head)
        ledger_count = ledger.count()
    else:
        expected_head, chain_ok, ledger_count = None, None, None

    result = {
        "proposer": args.proposer,
        "rlimits_applied": isolated,          # POSIX rlimits — defense in depth, NOT a jail
        "trusted_writes": not suppress_trusted,  # untrusted output never writes trusted sinks (no flag enables it)
        "tasks": len(tasks),
        "solved": solved,
        "attempts": attempts,
        "traces_written": 0 if suppress_trusted else len(traces),
        "out": None if suppress_trusted else args.out,
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
    return result


def main(argv=None):
    result = run(argv)
    return result if isinstance(result, int) else 0  # propagate fail-closed exit code to the process


if __name__ == "__main__":
    raise SystemExit(main())

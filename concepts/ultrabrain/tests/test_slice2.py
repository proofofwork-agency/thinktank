import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ultrabrain.propose.llm import clean_expr, extract_code, prompt_for
from ultrabrain.verify import (
    ABSTAIN,
    CASVerifier,
    CERTIFIED,
    CodeTestVerifier,
    Outcome,
    StructuredCodeVerifier,
    Verdict,
    harden,
)


def _code_tasks():
    path = os.path.join(ROOT, "tasks", "micro_codebench.jsonl")
    return {t["id"]: t for t in (json.loads(l) for l in open(path) if l.strip())}


def test_extract_code_handles_fenced_and_bare():
    fenced = "Sure:\n```python\ndef f():\n    return 1\n```\nthat works"
    assert extract_code(fenced).strip() == "def f():\n    return 1"
    assert extract_code("def g():\n    return 2").strip().startswith("def g")


def test_clean_expr_and_prompts():
    assert clean_expr("The answer is\n`x**2`") == "x**2"
    code_p = prompt_for({"kind": "code", "prompt": "do x", "entry_point": "foo"})
    assert "foo" in code_p and "python" in code_p.lower()
    cas_p = prompt_for({"kind": "cas", "prompt": "integral", "var": "t"})
    assert "t" in cas_p


def test_verified_search_collects_only_verified_traces(tmp_path):
    import run_verified_search as rvs
    out = str(tmp_path / "traces.jsonl")
    res = rvs.run(["--proposer", "mock", "--n", "16", "--seed", "0",
                   "--out", out, "--ledger", str(tmp_path / "led.jsonl"), "--ledger_secret", "t"])
    assert res["solved"] >= 1 and res["traces_written"] == res["solved"]
    assert res["ledger_chain_ok"]
    assert res["cas_attempts"] == 0 and res["pairs_written"] == 0
    assert res["attempts"] < res["tasks"] * 16  # code path deliberately keeps first-success behavior

    # THE load-bearing property: every collected trace independently passes the hardened gate,
    # so the SFT dataset is verified by construction (no teacher, no unverified data).
    tasks = _code_tasks()
    traces = [json.loads(l) for l in open(out) if l.strip()]
    assert traces, "expected at least one verified trace"
    for tr in traces:
        task = tasks[tr["task_id"]]
        assert CodeTestVerifier(harden(task)).verify(task, tr["solution"]).status == CERTIFIED, tr["task_id"]


def test_cas_search_uncaps_attempts_reports_mock_saturation_and_appends(tmp_path, monkeypatch):
    import run_verified_search as rvs

    task = {
        "id": "cas_uncap",
        "kind": "cas",
        "task_family": "poly",
        "op": "antiderivative",
        "prompt": "Antiderivative of 2*x.",
        "var": "x",
        "integrand": "2*x",
        "gold": "x**2",
        "distractors": ["x**2/2", "x**3", "x**2 + x"],
        "distractor_archetypes": ["scalar_multiple", "derivative", "plus_x"],
    }
    tasks_path = tmp_path / "cas.jsonl"
    tasks_path.write_text(json.dumps(task) + "\n")

    class FixedPoolProposer:
        def propose(self, current_task, n):
            pool = [current_task["gold"], *current_task["distractors"]]
            return [pool[index % len(pool)] for index in range(n)]

    monkeypatch.setattr(rvs, "build_proposer", lambda _args: FixedPoolProposer())

    out = tmp_path / "traces.jsonl"
    pairs = tmp_path / "cas_pairs_UNTRUSTED.jsonl"
    ledger = tmp_path / "ledger.jsonl"

    def collect(n):
        return rvs.run([
            "--tasks", str(tasks_path),
            "--proposer", "mock",
            "--n", str(n),
            "--out", str(out),
            "--pairs_out", str(pairs),
            "--ledger", str(ledger),
            "--ledger_secret", "test",
        ])

    one = collect(1)
    eight = collect(8)
    sixty_four = collect(64)

    # The mechanism is uncapped: every CAS proposal is judged, so attempts follow --n exactly.
    assert (one["attempts"], eight["attempts"], sixty_four["attempts"]) == (1, 8, 64)
    assert (one["cas_attempts"], eight["cas_attempts"], sixty_four["cas_attempts"]) == (1, 8, 64)

    # The fixed-pool mock is a Slice-1 instrument, not a source of variation: diversity saturates
    # at its four pool members even though the now-functional compute knob keeps scaling.
    assert one["distinct_candidates_by_task"]["cas_uncap"] == 1
    assert eight["distinct_candidates_by_task"]["cas_uncap"] == 4
    assert sixty_four["distinct_candidates_by_task"]["cas_uncap"] == 4
    assert eight["pairs_written"] == sixty_four["pairs_written"] == 3
    assert sixty_four["distinct_error_archetypes"] == 3
    assert sixty_four["task_family_counts"] == {"poly": 1}
    assert sixty_four["pairs_by_family"] == {"poly": 3}
    assert set(sixty_four["error_archetype_counts_by_family"]["poly"]) == {
        "scalar_multiple", "derivative", "plus_x",
    }

    # Every run appends. It never truncates either artifact or the certified-only ledger.
    trace_lines = [json.loads(line) for line in out.read_text().splitlines()]
    pair_lines = [json.loads(line) for line in pairs.read_text().splitlines()]
    assert len(trace_lines) == sum(run["traces_written"] for run in (one, eight, sixty_four))
    assert len(pair_lines) == sum(run["pairs_written"] for run in (one, eight, sixty_four))
    assert sixty_four["ledger_count"] == len(trace_lines)

    for pair in pair_lines:
        assert pair["trusted"] is False
        assert pair["ledger_eligible"] is False
        assert pair["artifact_class"] == "untrusted_preference_diagnostics"
        assert pair["kind"] == "cas"
        assert set(pair["chosen_signal"]) == {"schema", "status", "code", "evidence"}
        assert set(pair["rejected_signal"]) == {"schema", "status", "code", "evidence"}
        assert pair["chosen_signal"]["status"] == CERTIFIED
        assert pair["rejected_signal"]["status"] == "rejected"
        serialized_signals = json.dumps({
            "chosen": pair["chosen_signal"],
            "rejected": pair["rejected_signal"],
        })
        assert "residual" not in serialized_signals
        assert "exception" not in serialized_signals
        assert "expected" not in serialized_signals


def test_cas_training_projection_sanitizes_at_the_gate_source():
    candidate = "TRAIN_THIS_CANDIDATE"
    expected = "DO_NOT_LEAK_EXPECTED"
    verdict = Verdict(
        CERTIFIED,
        "cas.certified.exact_zero",
        {
            "code": "cas.certified.exact_zero",
            "op": "equivalent",
            "candidate_digest": "a" * 64,
            "reference_digest": "b" * 64,
            "candidate_nodes": 1,
            "candidate_depth": 1,
            "reference_nodes": 1,
            "reference_depth": 1,
            "method": "simplify_exact_zero",
            "raw_candidate": candidate,
            "raw_expected": expected,
            "exception": "TRAIN_THIS_EXCEPTION",
        },
    )
    signal = Outcome("t", candidate, verdict, 0.0).cas_training_signal()
    serialized = json.dumps(signal, sort_keys=True)
    assert candidate not in serialized
    assert expected not in serialized
    assert "TRAIN_THIS_EXCEPTION" not in serialized
    assert set(signal) == {"schema", "status", "code", "evidence"}
    assert set(signal["evidence"]) == {
        "code",
        "op",
        "candidate_digest",
        "reference_digest",
        "candidate_nodes",
        "candidate_depth",
        "reference_nodes",
        "reference_depth",
        "method",
    }

    forged = Verdict(CERTIFIED, "FORGED RAW DETAIL", dict(verdict.evidence))
    with pytest.raises(ValueError, match="cas_signal.invalid_verdict"):
        Outcome("t", candidate, forged, 0.0).cas_training_signal()

    injected_code = "cas.certified.TRAIN_THIS_CODE"
    injected = Verdict(CERTIFIED, injected_code, {**verdict.evidence, "code": injected_code})
    with pytest.raises(ValueError, match="cas_signal.invalid_verdict"):
        Outcome("t", candidate, injected, 0.0).cas_training_signal()

    abstain_code = "cas.abstain.disallowed_name"
    abstain = Verdict(
        ABSTAIN,
        abstain_code,
        {
            **verdict.evidence,
            "code": abstain_code,
            "raw_candidate": candidate,
            "raw_expected": expected,
        },
    )
    abstain_signal = Outcome("t", candidate, abstain, 0.0).cas_training_signal()
    assert abstain_signal["status"] == ABSTAIN
    assert candidate not in json.dumps(abstain_signal)
    assert expected not in json.dumps(abstain_signal)


def test_pair_artifact_cannot_alias_a_trusted_sink(tmp_path):
    import run_verified_search as rvs

    shared = str(tmp_path / "shared.jsonl")
    result = rvs.run([
        "--out", shared,
        "--pairs_out", shared,
        "--ledger", str(tmp_path / "ledger.jsonl"),
        "--ledger_secret", "test",
    ])
    assert result == 2
    assert not os.path.exists(shared)


def test_symbolic_forge_labels_families_and_fails_loudly_past_finite_space(capsys):
    from experiments import exp_task_forge as forge

    tasks = forge.mint(12, seed=7)
    assert len(tasks) == 12
    # Reference the DECLARED family set rather than a hardcoded copy, so widening the grammar
    # does not silently rot this test (it did exactly that on the 2026-07-28 widening).
    assert all(task["task_family"] in set(forge._FORGE_FAMILIES) for task in tasks)
    # The widening exists to buy CONCEPTUAL coverage, so a small corpus must already span
    # several families — a single-family corpus is the degeneracy S0b was fixing.
    assert len({task["task_family"] for task in tasks}) >= 4
    assert all(
        len(task["distractors"]) == len(task["distractor_archetypes"])
        and set(task["distractor_archetypes"]) <= {
            "scalar_multiple", "plus_x", "derivative",
        }
        for task in tasks
    )
    with pytest.raises(ValueError, match="space exhausted.*measured grammar maximum"):
        forge.mint(forge._MEASURED_FORGE_SPACE + 1)
    assert forge.run(["--n", str(forge._MEASURED_FORGE_SPACE + 1), "--json"]) == 2
    error = json.loads(capsys.readouterr().out)
    assert error["error"] == "forge_space_exhausted"
    assert str(forge._MEASURED_FORGE_SPACE) in error["detail"]


def test_train_qlora_dry_run(tmp_path):
    import train_qlora
    data = str(tmp_path / "traces.jsonl")
    with open(data, "w") as fh:
        fh.write(json.dumps({"task_id": "t", "kind": "code", "prompt": "do x",
                             "solution": "def f():\n    return 1\n"}) + "\n")
    examples, stats = train_qlora.prepare(data)
    assert stats["usable_examples"] == 1
    assert "### Instruction:" in examples[0]["text"] and "def f" in examples[0]["text"]
    assert train_qlora.main(["--dry_run", "--data", data]) == 0


def test_llm_execution_is_isolated_and_ledger_secret_required():
    # Codex blockers for the real Qwen run: untrusted (llm) code execution must not run un-isolated,
    # and trace collection must refuse to write beliefs without a private ledger secret.
    import run_verified_search as rvs
    task = _code_tasks()["is_even"]
    # A migrated task certifies through the parent-owned-oracle judge (which runs the candidate in a
    # scrubbed child of its own). The TRUST PATH IS JUDGE-ONLY: a code task WITHOUT a judge spec
    # ABSTAINS — it is never certified via the forgeable assert runner (Codex final review).
    assert isinstance(rvs.verifier_for(task), StructuredCodeVerifier)
    legacy = {k: v for k, v in task.items() if k != "judge"}
    assert rvs.verifier_for(legacy).verify(legacy, task["gold"]).status == ABSTAIN
    assert rvs.run(["--proposer", "mock"]) == 2  # fails closed: no --ledger_secret / env, no --unsafe


def test_verifier_execution_capability_defaults_closed_and_does_not_inherit():
    import run_verified_search as rvs

    class UndeclaredVerifier:
        pass

    class ExplicitExecutingVerifier:
        executes_candidate = True

    class InheritedCASCapability(CASVerifier):
        # Overriding verify makes this a new execution boundary. Forgetting to redeclare the
        # capability must not inherit CASVerifier's non-executing authorization.
        def verify(self, task, candidate):
            raise AssertionError("must never run in this test")

    class ExplicitNonExecutingVerifier(CASVerifier):
        executes_candidate = False

    assert rvs.verifier_executes_candidate(UndeclaredVerifier()) is True
    assert rvs.verifier_executes_candidate(ExplicitExecutingVerifier()) is True
    assert rvs.verifier_executes_candidate(InheritedCASCapability()) is True
    assert rvs.verifier_executes_candidate(ExplicitNonExecutingVerifier()) is False
    assert rvs.verifier_executes_candidate(CASVerifier()) is False


def test_real_proposer_cas_only_can_write_verified_trace_but_executing_verifier_cannot(
    tmp_path, monkeypatch,
):
    import run_verified_search as rvs

    task = {
        "id": "cas_real_proposer",
        "kind": "cas",
        "task_family": "poly",
        "op": "antiderivative",
        "prompt": "Antiderivative of 2*x.",
        "var": "x",
        "integrand": "2*x",
        "gold": "x**2",
        "distractors": [],
    }
    tasks_path = tmp_path / "cas.jsonl"
    tasks_path.write_text(json.dumps(task) + "\n")

    class GoldProposer:
        def propose(self, _task, n):
            return ["x**2"] * n

    monkeypatch.setattr(rvs, "build_proposer", lambda _args: GoldProposer())
    out = tmp_path / "traces.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    result = rvs.run([
        "--proposer", "llm",
        "--tasks", str(tasks_path),
        "--n", "1",
        "--out", str(out),
        "--pairs_out", str(tmp_path / "pairs.jsonl"),
        "--ledger", str(ledger),
        "--ledger_secret", "test-secret",
    ])
    assert result["trusted_writes"] is True
    assert result["traces_written"] == 1
    trace = json.loads(out.read_text().strip())
    assert trace["solution"] == "x**2"
    row = json.loads(ledger.read_text().strip())
    assert row["evidence"]["parser_safety_basis"] == "no_bypass_found_not_proven"

    class ExecutingVerifier:
        executes_candidate = True

        def verify(self, _task, _candidate):
            raise AssertionError("fail-closed gate must run before proposer construction")

    constructed = {"value": False}

    def should_not_build(_args):
        constructed["value"] = True
        raise AssertionError("executing trust path must fail before proposer construction")

    monkeypatch.setattr(rvs, "verifier_for", lambda _task, isolated=False: ExecutingVerifier())
    monkeypatch.setattr(rvs, "build_proposer", should_not_build)
    monkeypatch.setattr(rvs, "ISOLATION_AVAILABLE", True)
    assert rvs.run([
        "--proposer", "llm",
        "--tasks", str(tasks_path),
        "--n", "1",
        "--out", str(tmp_path / "blocked-traces.jsonl"),
        "--pairs_out", str(tmp_path / "blocked-pairs.jsonl"),
        "--ledger", str(tmp_path / "blocked-ledger.jsonl"),
        "--ledger_secret", "test-secret",
    ]) == 2
    assert constructed["value"] is False


def test_eval_code_untrusted_fails_closed_without_unsafe():
    # HOST CONTAINMENT (Codex final review): eval_code must NOT execute untrusted llm/fim output by
    # default — rlimits are not a host jail. The gate fires before the proposer is built or run, so no
    # candidate code executes; only --unsafe opts into throwaway diagnostics.
    import eval_code
    res = eval_code.run(["--proposer", "fim", "--tasks",
                         os.path.join(ROOT, "tasks", "micro_fim.jsonl"), "--n", "1"])
    assert res.get("error") == "untrusted_execution_requires_unsafe_or_host_jail"


def test_cli_fail_closed_exit_codes(tmp_path):
    # fail-closed must hold at the PROCESS boundary (Codex): main() propagates the exit code.
    import subprocess
    p = subprocess.run(
        [sys.executable, os.path.join(ROOT, "run_verified_search.py"), "--proposer", "mock", "--n", "1",
         "--out", str(tmp_path / "t.jsonl"), "--ledger", str(tmp_path / "l.jsonl")],
        capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 2, (p.returncode, p.stderr)  # no ledger secret -> nonzero exit
    p2 = subprocess.run(
        [sys.executable, os.path.join(ROOT, "self_improve.py"), "--rounds", "1", "--proposer", "mock",
         "--n", "2", "--json", "--traces", str(tmp_path / "tr.jsonl"), "--ledger", str(tmp_path / "led.jsonl")],
        capture_output=True, text=True, cwd=ROOT)
    assert p2.returncode == 0, (p2.returncode, p2.stderr)  # mock dry-run is safe-anywhere

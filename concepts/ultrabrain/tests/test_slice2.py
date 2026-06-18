import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ultrabrain.propose.llm import clean_expr, extract_code, prompt_for
from ultrabrain.verify import CASVerifier, CodeTestVerifier, harden, CERTIFIED


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

    # THE load-bearing property: every collected trace independently passes the hardened gate,
    # so the SFT dataset is verified by construction (no teacher, no unverified data).
    tasks = _code_tasks()
    traces = [json.loads(l) for l in open(out) if l.strip()]
    assert traces, "expected at least one verified trace"
    for tr in traces:
        task = tasks[tr["task_id"]]
        assert CodeTestVerifier(harden(task)).verify(task, tr["solution"]).status == CERTIFIED, tr["task_id"]


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
    # Codex blockers for the real Qwen run: untrusted (llm) code execution must use the OS-isolated
    # runner, and trace collection must refuse to write beliefs without a private ledger secret.
    import run_verified_search as rvs
    from ultrabrain.verify import run_tests_isolated
    task = _code_tasks()["is_even"]
    assert rvs.verifier_for(task, isolated=True).runner is run_tests_isolated
    assert rvs.verifier_for(task, isolated=False).runner is not run_tests_isolated
    assert rvs.run(["--proposer", "mock"]) == 2  # fails closed: no --ledger_secret / env, no --unsafe


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

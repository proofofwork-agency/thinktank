import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiment.metrics import aggregate
from experiment.report import render_report
from experiment.run_experiment import run


def test_offline_experiment_smoke_reports_trusted_write_audit():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init"], cwd=d, check=True, capture_output=True)
        with open(os.path.join(d, "test_pass.py"), "w") as f:
            f.write("def test_pass():\n    assert 1 + 1 == 2\n")
        with open(os.path.join(d, "test_fail.py"), "w") as f:
            f.write("def test_fail():\n    assert 1 == 2\n")
        tasks = [
            {
                "id": "pass_only",
                "session": 1,
                "kind": "code_fix",
                "prompt": "Run the passing pytest file.",
                "setup": {},
                "oracle": {"cmd": ["python3", "-m", "pytest", "-q", "test_pass.py"], "expect_exit": 0},
                "gold_belief": "pytest_passed(0)",
                "false_claim": None,
                "repeat_of": None,
            },
            {
                "id": "fail_only",
                "session": 1,
                "kind": "code_fix",
                "prompt": "Run the failing pytest file and remember the failure.",
                "setup": {},
                "oracle": {"cmd": ["python3", "-m", "pytest", "-q", "test_fail.py"], "expect_exit": 1},
                "gold_belief": "pytest_failed(1)",
                "false_claim": None,
                "repeat_of": None,
            },
            {
                "id": "false_probe",
                "session": 2,
                "kind": "faithful_false_probe",
                "prompt": "Teacher claims pytest passed without an oracle run.",
                "setup": {},
                "oracle": {"cmd": ["python3", "-m", "pytest", "-q", "test_pass.py"], "expect_exit": 0},
                "gold_belief": None,
                "false_claim": "pytest_passed_without_oracle",
                "repeat_of": None,
            },
        ]

        result = run(tasks=tasks, sessions=2, out=os.path.join(d, "out"), repo=d)
        metrics = result["metrics"]
        report = render_report(metrics)

        assert metrics["B"]["unsupported_trusted_writes"] == 0
        assert metrics["B"]["provenance_audit_rate"] == 1.0
        assert "# UltraBrain Decisive Experiment Report" in report
        assert os.path.exists(os.path.join(d, "out", "report.md"))

        solved_b = [event for event in result["events"] if event["system"] == "B" and event["success"]]
        assert solved_b
        assert all(event["provenance_ok"] for event in solved_b)

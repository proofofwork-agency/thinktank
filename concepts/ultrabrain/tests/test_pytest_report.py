import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultrabrain.pytest_report import parse_results


def test_parse_results_from_real_pytest_rA_output():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test_sample.py")
        with open(path, "w") as f:
            f.write(
                "import pytest\n\n"
                "def test_ok():\n    assert True\n\n"
                "def test_fail():\n    assert False\n\n"
                "def test_skip():\n    pytest.skip('skip')\n\n"
                "@pytest.mark.xfail(reason='xfail')\n"
                "def test_xfail():\n    assert False\n\n"
                "@pytest.mark.xfail(reason='xpass')\n"
                "def test_xpass():\n    assert True\n"
            )
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-rA", "."],
            cwd=d,
            text=True,
            capture_output=True,
        )

        parsed = parse_results(proc.stdout)

        assert proc.returncode == 1
        assert parsed == [
            ("test_sample.py::test_ok", True),
            ("test_sample.py::test_xpass", True),
            ("test_sample.py::test_fail", False),
        ]


def test_parse_results_handles_error_and_ignores_non_summary_lines():
    stdout = """
FAILED noise_before_summary.py::test_not_counted
=========================== short test summary info ============================
PASSED pkg/test_a.py::test_ok
ERROR pkg/test_b.py::test_import_error
XFAIL pkg/test_c.py::test_expected - reason
SKIPPED [1] pkg/test_d.py:12: reason
"""

    assert parse_results(stdout) == [
        ("pkg/test_a.py::test_ok", True),
        ("pkg/test_b.py::test_import_error", False),
    ]


def test_parse_results_dedupes_by_nodeid_last_wins_preserving_first_order():
    stdout = """
=========================== short test summary info ============================
FAILED pkg/test_a.py::test_flaky
PASSED pkg/test_b.py::test_ok
PASSED pkg/test_a.py::test_flaky
FAILED pkg/test_b.py::test_ok
"""

    assert parse_results(stdout) == [
        ("pkg/test_a.py::test_flaky", True),
        ("pkg/test_b.py::test_ok", False),
    ]


def test_parse_results_returns_empty_without_summary():
    assert parse_results("PASSED pkg/test_a.py::test_ok\n") == []

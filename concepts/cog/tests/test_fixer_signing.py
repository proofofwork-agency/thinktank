#!/usr/bin/env python3
"""Offline regressions for the fixer's publication and trust boundary."""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "cogfix"))
sys.path.insert(0, str(ROOT / "fixer"))

import fixerd  # noqa: E402


@unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen is required")
class TestFixerSigning(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.here = Path(self.tempdir.name)
        self.real_here = fixerd.HERE
        fixerd.HERE = self.here

    def tearDown(self):
        fixerd.HERE = self.real_here
        self.tempdir.cleanup()

    def assert_verifies(self, payload):
        result = subprocess.run(
            [
                "ssh-keygen", "-Y", "verify",
                "-f", str(self.here / "allowed_signers"),
                "-I", "cogfix",
                "-n", "cogfix",
                "-s", f"{payload}.sig",
            ],
            input=payload.read_bytes(),
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_resigning_same_path_replaces_signature(self):
        payload = self.here / "fix.json"
        payload.write_text('{"payload":"A"}\n')
        self.assertTrue(fixerd.sign(payload))
        first_signature = Path(f"{payload}.sig").read_bytes()
        trust_anchor = (self.here / "allowed_signers").read_bytes()

        payload.write_text('{"payload":"B"}\n')
        self.assertTrue(fixerd.sign(payload))
        second_signature = Path(f"{payload}.sig").read_bytes()

        self.assertNotEqual(first_signature, second_signature)
        self.assertEqual((self.here / "allowed_signers").read_bytes(), trust_anchor)
        self.assert_verifies(payload)

    def test_failed_verification_returns_false_and_removes_signature(self):
        payload = self.here / "fix.json"
        payload.write_text('{"payload":"cannot-verify"}\n')
        real_run = subprocess.run

        def fail_verify(args, **kwargs):
            if args[1:3] == ["-Y", "verify"]:
                raise subprocess.CalledProcessError(
                    255, args, output=b"", stderr=b"forced verify failure"
                )
            return real_run(args, **kwargs)

        with (
            mock.patch.object(fixerd.subprocess, "run", side_effect=fail_verify),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertFalse(fixerd.sign(payload))
        self.assertFalse(Path(f"{payload}.sig").exists())

    def test_existing_mismatched_trust_anchor_is_not_rewritten(self):
        payload = self.here / "fix.json"
        payload.write_text('{"payload":"A"}\n')
        self.assertTrue(fixerd.sign(payload))
        allowed_signers = self.here / "allowed_signers"
        allowed_signers.write_text("cogfix ssh-ed25519 not-the-current-key\n")

        payload.write_text('{"payload":"B"}\n')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertFalse(fixerd.sign(payload))
        self.assertEqual(
            allowed_signers.read_text(),
            "cogfix ssh-ed25519 not-the-current-key\n",
        )
        self.assertFalse(Path(f"{payload}.sig").exists())


class TestFixerPublication(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.here = Path(self.tempdir.name)
        self.real_here = fixerd.HERE
        fixerd.HERE = self.here

    def tearDown(self):
        fixerd.HERE = self.real_here
        self.tempdir.cleanup()

    def test_future_qualification_falls_back_to_assumed_allowlist(self):
        qualification = {
            "date": "2099-01-01",
            "mode": "live",
            "exam": "COG1-CORE-v0",
            "exam_sha256": fixerd.qualify.fingerprint(),
            "threshold": 0.8,
            "qualified": ["model/that-never-sat-the-exam"],
        }
        (self.here / "qualified.json").write_text(json.dumps(qualification))

        ids, metadata = fixerd.load_qualification("2026-07-27")

        self.assertIsNone(ids)
        self.assertIn("assumed", metadata["basis"])

    def test_mismatched_exam_fingerprint_falls_back_to_assumed_allowlist(self):
        qualification = {
            "date": "2026-07-27",
            "mode": "live",
            "exam": "COG1-CORE-v0",
            "exam_sha256": "not-the-current-exam",
            "threshold": 0.8,
            "qualified": ["model/that-sat-a-different-exam"],
        }
        (self.here / "qualified.json").write_text(json.dumps(qualification))

        ids, metadata = fixerd.load_qualification("2026-07-27")

        self.assertIsNone(ids)
        self.assertIn("assumed", metadata["basis"])
        self.assertIn("fingerprint", metadata["basis"])

    def test_matching_exam_fingerprint_allows_fresh_live_qualification(self):
        qualification = {
            "date": "2026-07-27",
            "mode": "live",
            "exam": "COG1-CORE-v0",
            "exam_sha256": fixerd.qualify.fingerprint(),
            "threshold": 0.8,
            "qualified": ["model/that-passed-current-exam"],
        }
        (self.here / "qualified.json").write_text(json.dumps(qualification))

        ids, metadata = fixerd.load_qualification("2026-07-27")

        self.assertEqual(ids, ["model/that-passed-current-exam"])
        self.assertEqual(metadata["basis"], "exam-qualified")

    def test_archive_is_idempotent_but_rejects_different_bytes(self):
        archive = self.here / "archive.json"
        fixerd._write_immutable(archive, b"first\n")
        fixerd._write_immutable(archive, b"first\n")

        with self.assertRaises(FileExistsError):
            fixerd._write_immutable(archive, b"second\n")
        self.assertEqual(archive.read_bytes(), b"first\n")

    def test_main_signs_current_fix_and_dated_archive(self):
        rows = [
            {
                "model": f"mock/{i}",
                "in_usd_per_M": float(i),
                "out_usd_per_M": float(i),
                "blended_usd_per_M": float(i),
            }
            for i in (1, 2, 3)
        ]
        with (
            mock.patch.object(fixerd, "fetch_models", return_value={}),
            mock.patch.object(fixerd, "posted_quotes", return_value=rows),
            mock.patch.object(fixerd, "sign", return_value=True) as sign,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            fixerd.main([])

        signed_paths = [call.args[0] for call in sign.call_args_list]
        self.assertEqual(signed_paths[0], self.here / "fix.json")
        self.assertEqual(signed_paths[1].parent, self.here / "archive")
        self.assertEqual(signed_paths[1].suffix, ".json")
        self.assertEqual(signed_paths[0].read_bytes(), signed_paths[1].read_bytes())

    def test_missing_usage_reserves_worst_case_cost(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"id":"response-without-usage"}'

        row = {
            "model": "mock/model",
            "in_usd_per_M": 1.0,
            "out_usd_per_M": 2.0,
            "blended_usd_per_M": 1.2,
        }
        with mock.patch.object(fixerd.urllib.request, "urlopen", return_value=FakeResponse()):
            receipt = fixerd.buy_run(row, "unused-test-key", max_tokens=256)

        self.assertTrue(receipt["usage_estimated"])
        self.assertEqual(
            receipt["usage"],
            {"prompt_tokens": fixerd.EST_PROMPT_TOKENS, "completion_tokens": 256},
        )
        expected = (fixerd.EST_PROMPT_TOKENS * 1.0 + 256 * 2.0) / 1e6
        self.assertEqual(receipt["cost_usd_est"], expected)

    def test_receipt_cap_stops_all_candidate_loops(self):
        candidates = [
            {
                "model": f"mock/{i}",
                "in_usd_per_M": 1000.0,
                "out_usd_per_M": 1000.0,
                "blended_usd_per_M": 1000.0,
            }
            for i in range(3)
        ]
        receipt = {
            "response_id": "one",
            "model": "mock/0",
            "usage": {"prompt_tokens": 200, "completion_tokens": 100},
            "cost_usd_est": 0.3,
        }
        output = io.StringIO()
        with (
            mock.patch.object(fixerd, "buy_run", return_value=receipt) as buy,
            contextlib.redirect_stdout(output),
        ):
            receipts, spent = fixerd.buy_receipts(
                candidates,
                api_key="unused-test-key",
                buys=3,
                max_tokens=100,
                max_spend=0.31,
            )

        self.assertEqual(buy.call_count, 1)
        self.assertEqual(receipts, [receipt])
        self.assertEqual(spent, 0.3)
        self.assertEqual(output.getvalue().count("spend cap"), 1)


if __name__ == "__main__":
    unittest.main()

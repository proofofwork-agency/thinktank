#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
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
    MODELLED_REFUSAL = (
        "receipt mode refuses modelled price provenance: subscription/rate-card "
        "costs prove execution and token counts, not an executable market price; "
        "no settleable fix was published"
    )

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
        self.assertEqual(
            metadata["endpoint"], fixerd.backend.CANONICAL_METERED_BASE
        )

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

    def test_backend_defaults_and_api_key_precedence(self):
        backend = fixerd.backend
        self.assertEqual(
            backend.base_url({}), backend.CANONICAL_METERED_BASE
        )
        self.assertEqual(
            backend.resolve_price_provenance(backend.CANONICAL_METERED_BASE, {}),
            ("metered", "canonical OpenRouter endpoint"),
        )
        self.assertEqual(
            backend.resolve_price_provenance("http://127.0.0.1:8788/api/v1", {}),
            ("modelled", "non-canonical endpoint default"),
        )
        self.assertEqual(
            backend.resolve_price_provenance(
                "http://127.0.0.1:8788/api/v1",
                {"COG_PRICE_PROVENANCE": "metered"},
            ),
            ("metered", "operator assertion via COG_PRICE_PROVENANCE"),
        )
        self.assertEqual(
            backend.api_key(
                {"COG_API_KEY": "cog-key", "OPENROUTER_API_KEY": "legacy-key"}
            ),
            "cog-key",
        )
        self.assertEqual(
            backend.api_key({"OPENROUTER_API_KEY": "legacy-key"}), "legacy-key"
        )
        with self.assertRaisesRegex(ValueError, "metered, modelled"):
            backend.resolve_price_provenance(
                "http://127.0.0.1:8788/api/v1",
                {"COG_PRICE_PROVENANCE": "receipted"},
            )
        transport_error = fixerd.urllib.error.URLError("connection refused")
        self.assertEqual(
            str(
                backend.request_failed(
                    "exam request failed",
                    "http://127.0.0.1:8788/api/v1/chat/completions",
                    transport_error,
                )
            ),
            "exam request failed at http://127.0.0.1:8788/api/v1/chat/completions: "
            "URL error: connection refused",
        )

    def test_help_exits_without_credentials_or_network(self):
        qualify = fixerd.qualify
        output = io.StringIO()
        with (
            mock.patch.dict(fixerd.os.environ, {}, clear=True),
            mock.patch.object(fixerd, "fetch_models") as fetch,
            mock.patch.object(qualify, "ask_model") as ask,
            contextlib.redirect_stdout(output),
        ):
            fixerd.main(["--help"])
            qualify.main(["--help"])

        fetch.assert_not_called()
        ask.assert_not_called()
        self.assertIn("COG_OPENROUTER_BASE", output.getvalue())

    def test_modelled_receipt_mode_refuses_before_fetch_buy_or_write(self):
        with (
            mock.patch.dict(
                fixerd.os.environ,
                {"COG_OPENROUTER_BASE": "http://127.0.0.1:8788/api/v1"},
                clear=True,
            ),
            mock.patch.object(fixerd, "fetch_models") as fetch,
            mock.patch.object(fixerd, "buy_receipts") as buy,
            self.assertRaises(SystemExit) as raised,
        ):
            fixerd.main(["--receipt"])

        self.assertEqual(str(raised.exception), self.MODELLED_REFUSAL)
        fetch.assert_not_called()
        buy.assert_not_called()
        self.assertFalse((self.here / "fix.json").exists())
        self.assertFalse((self.here / "archive").exists())

    def test_fixer_catalogue_http_error_names_endpoint_and_status(self):
        endpoint = "http://127.0.0.1:8788/api/v1"
        error = fixerd.urllib.error.HTTPError(
            f"{endpoint}/models", 400, "Bad Request", {}, None
        )
        expected = (
            f"model catalogue request failed at {endpoint}/models: "
            "HTTP 400 Bad Request"
        )
        with (
            mock.patch.dict(
                fixerd.os.environ, {"COG_OPENROUTER_BASE": endpoint}, clear=True
            ),
            mock.patch.object(
                fixerd.urllib.request, "urlopen", side_effect=error
            ),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            fixerd.main([])

        error.close()
        self.assertEqual(str(raised.exception), expected)
        self.assertFalse((self.here / "fix.json").exists())
        self.assertFalse((self.here / "archive").exists())

    def test_custom_quote_payload_carries_modelled_provenance(self):
        rows = [
            {
                "model": f"mock/{i}",
                "in_usd_per_M": float(i),
                "out_usd_per_M": float(i),
                "blended_usd_per_M": float(i),
            }
            for i in (1, 2, 3)
        ]
        endpoint = "http://127.0.0.1:8788/api/v1"
        with (
            mock.patch.dict(
                fixerd.os.environ, {"COG_OPENROUTER_BASE": endpoint}, clear=True
            ),
            mock.patch.object(fixerd, "fetch_models", return_value={}) as fetch,
            mock.patch.object(fixerd, "posted_quotes", return_value=rows),
            mock.patch.object(fixerd, "local_anchor_check", return_value={}),
            mock.patch.object(fixerd, "sign", return_value=False),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            fixerd.main([])

        payload = json.loads((self.here / "fix.json").read_text())
        fetch.assert_called_once_with(endpoint)
        self.assertEqual(payload["endpoint"], endpoint)
        self.assertEqual(payload["price_provenance"], "modelled")
        self.assertEqual(
            payload["price_provenance_basis"], "non-canonical endpoint default"
        )
        self.assertEqual(payload["mode"], "quote")

    def test_noncanonical_receipts_require_explicit_metered_assertion(self):
        rows = [
            {
                "model": f"mock/{i}",
                "in_usd_per_M": float(i),
                "out_usd_per_M": float(i),
                "blended_usd_per_M": float(i),
            }
            for i in (1, 2, 3)
        ]
        endpoint = "http://127.0.0.1:8788/api/v1"
        receipts = [
            {
                "model": "mock/1",
                "response_id": "metered-buy",
                "blended_usd_per_M": 1.0,
                "cost_usd_est": 0.01,
                "price_provenance": "metered",
            }
        ]
        with (
            mock.patch.dict(
                fixerd.os.environ,
                {
                    "COG_OPENROUTER_BASE": endpoint,
                    "COG_PRICE_PROVENANCE": "metered",
                },
                clear=True,
            ),
            mock.patch.object(fixerd, "fetch_models", return_value={}),
            mock.patch.object(fixerd, "posted_quotes", return_value=rows),
            mock.patch.object(
                fixerd, "buy_receipts", return_value=(receipts, 0.01)
            ) as buy,
            mock.patch.object(fixerd, "local_anchor_check", return_value={}),
            mock.patch.object(fixerd, "sign", return_value=False),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            fixerd.main(["--receipt"])

        payload = json.loads((self.here / "fix.json").read_text())
        self.assertEqual(payload["mode"], "receipt-lite")
        self.assertEqual(payload["price_provenance"], "metered")
        self.assertEqual(
            payload["price_provenance_basis"],
            "operator assertion via COG_PRICE_PROVENANCE",
        )
        self.assertEqual(buy.call_args.kwargs["base_url"], endpoint)
        self.assertEqual(buy.call_args.kwargs["price_provenance"], "metered")

    def test_fixer_buy_http_error_names_model_endpoint_and_status(self):
        rows = [
            {
                "model": f"mock/{i}",
                "in_usd_per_M": float(i),
                "out_usd_per_M": float(i),
                "blended_usd_per_M": float(i),
            }
            for i in (1, 2, 3)
        ]
        endpoint = "http://127.0.0.1:8788/api/v1"
        error = fixerd.urllib.error.HTTPError(
            f"{endpoint}/chat/completions", 429, "Too Many Requests", {}, None
        )
        expected = (
            "price execution request failed for model 'mock/1' at "
            f"{endpoint}/chat/completions: HTTP 429 Too Many Requests"
        )
        with (
            mock.patch.dict(
                fixerd.os.environ,
                {
                    "COG_OPENROUTER_BASE": endpoint,
                    "COG_PRICE_PROVENANCE": "metered",
                },
                clear=True,
            ),
            mock.patch.object(fixerd, "fetch_models", return_value={}),
            mock.patch.object(fixerd, "posted_quotes", return_value=rows),
            mock.patch.object(
                fixerd.urllib.request, "urlopen", side_effect=error
            ),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            fixerd.main(["--receipt"])

        error.close()
        self.assertEqual(str(raised.exception), expected)
        self.assertFalse((self.here / "fix.json").exists())
        self.assertFalse((self.here / "archive").exists())

    def test_custom_capability_exam_needs_no_key_and_records_endpoint(self):
        qualify = fixerd.qualify
        exam_root = self.here / "exam-root"
        (exam_root / "fixer").mkdir(parents=True)
        endpoint = "http://127.0.0.1:8788/api/v1"
        result = {
            "model": "mock/model",
            "score": 1.0,
            "correct": len(qualify.EXAM["items"]),
            "total": len(qualify.EXAM["items"]),
            "administered": len(qualify.EXAM["items"]),
            "aborted": False,
            "passed": True,
            "tokens_used": 1,
            "item_receipts": [],
        }
        with (
            mock.patch.dict(
                qualify.os.environ,
                {
                    "COG_OPENROUTER_BASE": endpoint,
                    "COG_PRICE_PROVENANCE": "modelled",
                },
                clear=True,
            ),
            mock.patch.object(qualify, "ROOT", exam_root),
            mock.patch.object(qualify, "examine", return_value=result) as examine,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            qualify.main(["--models", "mock/model"])

        payload = json.loads((exam_root / "fixer" / "qualified.json").read_text())
        self.assertEqual(payload["endpoint"], endpoint)
        self.assertEqual(payload["qualified"], ["mock/model"])
        self.assertNotIn("price_provenance", payload)
        examine.assert_called_once()

    def test_capability_request_uses_custom_endpoint_without_authorization(self):
        qualify = fixerd.qualify

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return (
                    b'{"choices":[{"message":{"content":"answer"}}],'
                    b'"usage":{"prompt_tokens":2,"completion_tokens":1}}'
                )

        endpoint = "http://127.0.0.1:8788/api/v1"
        with mock.patch.object(
            qualify.urllib.request, "urlopen", return_value=FakeResponse()
        ) as urlopen:
            text, usage, _request_hash, _response_hash = qualify.ask_model(
                "mock/model", "question", None, endpoint
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, f"{endpoint}/chat/completions")
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(text, "answer")
        self.assertEqual(usage["prompt_tokens"], 2)

    def test_capability_http_error_names_model_endpoint_and_status(self):
        qualify = fixerd.qualify
        endpoint = "http://127.0.0.1:8788/api/v1"
        error = qualify.urllib.error.HTTPError(
            f"{endpoint}/chat/completions", 400, "Bad Request", {}, None
        )
        expected = (
            "exam request failed for model 'mock/model' at "
            f"{endpoint}/chat/completions: HTTP 400 Bad Request"
        )
        with (
            mock.patch.dict(
                qualify.os.environ,
                {"COG_OPENROUTER_BASE": endpoint},
                clear=True,
            ),
            mock.patch.object(
                qualify.urllib.request, "urlopen", side_effect=error
            ),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            qualify.main(["--models", "mock/model"])

        error.close()
        self.assertEqual(str(raised.exception), expected)

    def test_canonical_capability_exam_still_requires_a_key(self):
        qualify = fixerd.qualify
        message = (
            "real exam runs need COG_API_KEY or OPENROUTER_API_KEY at the canonical "
            "OpenRouter endpoint (this spends real money); use --dry-run or "
            "--self-test for the free paths"
        )
        with (
            mock.patch.dict(qualify.os.environ, {}, clear=True),
            self.assertRaises(SystemExit) as raised,
        ):
            qualify.main(["--models", "mock/model"])
        self.assertEqual(str(raised.exception), message)

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
        endpoint = "http://127.0.0.1:8788/api/v1"
        with (
            mock.patch.dict(
                fixerd.os.environ, {"COG_OPENROUTER_BASE": endpoint}, clear=True
            ),
            mock.patch.object(
                fixerd.urllib.request, "urlopen", return_value=FakeResponse()
            ) as urlopen,
        ):
            receipt = fixerd.buy_run(row, "unused-test-key", max_tokens=256)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, f"{endpoint}/chat/completions")
        self.assertEqual(receipt["endpoint"], endpoint)
        self.assertEqual(receipt["price_provenance"], "modelled")
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

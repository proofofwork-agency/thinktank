# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fixer"))

from contracts.canon import canon_sha256, canonical_json
from contracts.cdo import (
    SchemaValidationError,
    draft_obligation,
    verify_obligation_id,
)
from contracts.rails import denomination, emit_ap2, emit_x402
from contracts.settle import (
    SettlementUnavailable,
    chain_link,
    invoice,
    load_series,
    settlement_fix,
    verify_invoice,
)
import fixerd


def entry(day, price, tier="venue-quote", publisher="test/publisher", **extra):
    out = {
        "date": day.isoformat() if isinstance(day, date) else day,
        "price": str(price),
        "tier": tier,
        "publisher": publisher,
        "sig_ok": True,
        "archive_sha256": extra.pop("archive_sha256", "a" * 64),
    }
    out.update(extra)
    return out


def obligation(**settlement):
    terms = {"publishers": ["test/publisher"]}
    terms.update(settlement)
    return draft_obligation(
        parties={
            "provider": {"name": "Provider", "id": "did:example:provider"},
            "client": {"name": "Client", "id": "did:example:client"},
        },
        legs=[
            {"kind": "fixed", "USD": "10.00"},
            {"kind": "indexed", "cog": "COG-1", "quantity": "1000"},
        ],
        term={"start": "2026-06-01", "end": "2027-05-31", "period": "month"},
        settlement=terms,
    )


class CanonAndCdoTests(unittest.TestCase):
    def test_canonical_hash_is_order_independent_and_excludes_signatures(self):
        left = {"b": 2, "a": {"signatures": ["x"], "v": 1}}
        right = {"a": {"v": 1, "signatures": ["different"]}, "b": 2}
        self.assertEqual(canonical_json(left), '{"a":{"v":1},"b":2}')
        self.assertEqual(canon_sha256(left), canon_sha256(right))

    def test_cdo_id_commits_to_terms_but_not_signatures(self):
        cdo = obligation()
        self.assertTrue(verify_obligation_id(cdo))
        signed = json.loads(json.dumps(cdo))
        signed["signatures"] = [{"key": "alice", "sig": "abc"}]
        self.assertTrue(verify_obligation_id(signed))
        signed["legs"][1]["quantity"] = "1001"
        self.assertFalse(verify_obligation_id(signed))

    def test_schema_rejects_binary_float_money(self):
        with self.assertRaises(SchemaValidationError):
            draft_obligation(
                parties={"provider": {"name": "P"}, "client": {"name": "C"}},
                legs=[{"kind": "fixed", "USD": 0.1}],
                term={"start": "2026-01-01", "end": "2026-12-31", "period": "month"},
            )

    def test_optional_basis_and_publisher_terms_are_explicit_only(self):
        baseline = obligation()
        for key in ("region", "correction_window_days", "on_publisher_cessation"):
            self.assertNotIn(key, baseline["settlement"])

        governed = obligation(
            region="EU",
            correction_window_days=30,
            on_publisher_cessation="fallback-publisher",
        )
        self.assertEqual(governed["settlement"]["region"], "EU")
        self.assertEqual(governed["settlement"]["correction_window_days"], 30)
        self.assertEqual(
            governed["settlement"]["on_publisher_cessation"],
            "fallback-publisher",
        )
        self.assertTrue(verify_obligation_id(governed))

        nullable = obligation(region=None, correction_window_days=None)
        self.assertIsNone(nullable["settlement"]["region"])
        self.assertIsNone(nullable["settlement"]["correction_window_days"])

    def test_schema_rejects_unknown_publisher_cessation_rule(self):
        with self.assertRaises(SchemaValidationError):
            obligation(on_publisher_cessation="silently-change-the-fix")


class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.end = date(2026, 6, 30)

    def test_normal_median_is_six_decimal_decimal_arithmetic(self):
        rows = [
            entry(self.end - timedelta(days=6 - i), f"0.10000{i + 1}")
            for i in range(7)
        ]
        result = settlement_fix(rows, self.end)
        self.assertEqual(result["status"], "normal")
        self.assertEqual(result["usd_per_cog"], "0.100004")
        self.assertEqual(result["window"]["anchor"], "period.end")
        self.assertIsInstance(result["usd_per_cog"], str)

    def test_degraded_and_carry_forward_are_labeled(self):
        degraded = settlement_fix(
            [entry(self.end - timedelta(days=2), "1.00")], self.end
        )
        self.assertEqual(degraded["status"], "degraded-window")
        self.assertTrue(degraded["ack_required"])
        carried = settlement_fix(
            [entry(self.end - timedelta(days=20), "1.00")], self.end
        )
        self.assertEqual(carried["status"], "carry-forward")
        self.assertTrue(carried["payable"])

    def test_anchor_requires_signed_precommit_and_ack(self):
        last = entry(
            self.end - timedelta(days=60),
            "1.00",
            archive_sha256="b" * 64,
            anchor_check={
                "publisher": "Epoch AI",
                "ratio_adjusted_usd_per_cog": "0.800001",
            },
        )
        result = settlement_fix([last], self.end)
        self.assertEqual(result["status"], "anchor-fallback")
        self.assertTrue(result["provisional"])
        self.assertFalse(result["payable"])
        self.assertTrue(result["true_up_required"])
        self.assertEqual(
            result["fixes_used"][0]["committed_archive_sha256"], "b" * 64
        )
        acknowledged = settlement_fix([last], self.end, counterparty_ack=True)
        self.assertTrue(acknowledged["payable"])
        uncommitted = dict(last)
        uncommitted.pop("anchor_check")
        with self.assertRaises(SettlementUnavailable):
            settlement_fix([uncommitted], self.end)

    def test_90_day_conversion_uses_last_local_not_external(self):
        local = entry(self.end - timedelta(days=91), "0.123456")
        external = entry(
            self.end - timedelta(days=1),
            "99",
            tier="external-anchor",
        )
        result = settlement_fix([local, external], self.end)
        self.assertEqual(result["status"], "converted")
        self.assertEqual(result["usd_per_cog"], "0.123456")
        self.assertEqual(result["conversion"]["from_fix_date"], local["date"])

    def test_min_tier_is_enforced(self):
        rows = [
            entry(self.end - timedelta(days=i), "1", tier="venue-quote")
            for i in range(7)
        ]
        with self.assertRaises(SettlementUnavailable):
            settlement_fix(rows, self.end, min_tier="receipted-depth")

    def test_receipt_lite_payload_cannot_satisfy_receipted_depth(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "archive"
            archive.mkdir()
            for offset, explicit_tier in enumerate((None, "receipted-depth")):
                day = self.end - timedelta(days=offset)
                payload = {
                    "date": day.isoformat(),
                    "fix_usd": "1.000000",
                    "mode": "receipt-lite",
                    "publisher": "test/publisher",
                    "receipts": [{"response_id": f"micro-{offset}"}],
                }
                if explicit_tier is not None:
                    payload["tier"] = explicit_tier
                (archive / f"{day.isoformat()}.json").write_text(
                    json.dumps(payload) + "\n"
                )

            rows = load_series(archive, verify_sigs=False)

        self.assertEqual([row["tier"] for row in rows], ["receipted-lite"] * 2)
        with self.assertRaisesRegex(SettlementUnavailable, "receipted-depth"):
            settlement_fix(rows, self.end, min_tier="receipted-depth")
        with self.assertRaisesRegex(SettlementUnavailable, "receipted-depth"):
            settlement_fix(
                [
                    entry(
                        self.end,
                        "1",
                        tier="receipted-depth",
                        mode="receipt-lite",
                        receipts=[{"response_id": "micro-direct"}],
                    )
                ],
                self.end,
                min_tier="receipted-depth",
            )
        self.assertEqual(
            obligation(min_tier="receipted-lite")["settlement"]["min_tier"],
            "receipted-lite",
        )

    def test_unsupported_multi_publisher_rule_refuses_direct_and_invoice_settlement(self):
        rows = [
            entry(self.end - timedelta(days=i), "1")
            for i in range(7)
        ]
        message = "supports only 'priority-order'"
        with self.assertRaisesRegex(SettlementUnavailable, message):
            settlement_fix(rows, self.end, multi_publisher_rule="median")
        with self.assertRaisesRegex(SettlementUnavailable, message):
            invoice(
                obligation(multi_publisher_rule="quorum-median"),
                {"start": "2026-06-01", "end": "2026-06-30"},
                rows,
            )

    def test_chain_link_uses_matching_dates(self):
        old = [entry("2026-01-01", "2"), entry("2026-01-02", "4")]
        new = [entry("2026-01-01", "3"), entry("2026-01-02", "6")]
        result = chain_link(old, new, "2026-01-01", "2026-01-02")
        self.assertEqual(result["factor_new_per_old"], "1.500000")
        self.assertEqual(result["observations"], 2)

    def test_invoice_is_pure_unsigned_and_uses_decimal_strings(self):
        rows = [
            entry(self.end - timedelta(days=6 - i), f"0.10000{i + 1}")
            for i in range(7)
        ]
        cdo = obligation()
        first = invoice(cdo, {"start": "2026-06-01", "end": "2026-06-30"}, rows)
        second = invoice(cdo, {"start": "2026-06-01", "end": "2026-06-30"}, rows)
        self.assertEqual(first, second)
        self.assertEqual(first["signatures"], [])
        self.assertEqual(first["lines"][1]["amount_usd"], "100.00")
        self.assertEqual(first["subtotal_usd"], "110.00")
        self.assertEqual(first["amount_due_usd"], "110.00")
        self.assertEqual(first["settlement"]["window"]["end"], "2026-06-30")
        self.assertEqual(
            first["recompute"],
            "python3 contracts/settle.py --verify invoice.json --archive fixer/archive",
        )


class ArchiveAndRailTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen is required")
    def test_worked_example_recompute_command_runs_verbatim(self):
        example = json.loads(
            (ROOT / "contracts" / "examples" / "reference-invoice.json").read_text()
        )
        completed = subprocess.run(
            shlex.split(example["recompute"]),
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        report = json.loads(completed.stdout)
        self.assertTrue(report["valid"], report["errors"])
        self.assertTrue(report["signature_ok"])

    def test_shared_signer_supports_contract_namespaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = root / "key"
            allowed = root / "allowed_signers"
            cdo_path = root / "cdo.json"
            invoice_path = root / "invoice.json"
            cdo_path.write_text('{"kind":"cdo"}\n')
            invoice_path.write_text('{"kind":"invoice"}\n')
            self.assertTrue(
                fixerd.sign(
                    cdo_path,
                    namespace="cog-cdo",
                    key=key,
                    allowed_signers=allowed,
                )
            )
            self.assertTrue(
                fixerd.sign(
                    invoice_path,
                    namespace="cog-invoice",
                    key=key,
                    allowed_signers=allowed,
                )
            )
            self.assertIn("cogfix,cog-cdo,cog-invoice", allowed.read_text())

    def test_load_series_verifies_the_archive_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "archive"
            archive.mkdir()
            payload = archive / "2026-06-30.json"
            payload.write_text(
                json.dumps(
                    {
                        "date": "2026-06-30",
                        "fix_usd": 0.125,
                        "mode": "quote",
                        "publisher": "test/publisher",
                        "receipts": [],
                    },
                    indent=2,
                )
                + "\n"
            )
            self.assertTrue(
                fixerd.sign(
                    payload,
                    key=root / "key",
                    allowed_signers=root / "allowed_signers",
                )
            )
            loaded = load_series(archive)
            self.assertEqual(len(loaded), 1)
            self.assertTrue(loaded[0]["sig_ok"])
            self.assertEqual(loaded[0]["fix_usd"], "0.125000")
            payload.write_text(payload.read_text().replace("0.125", "9.125"))
            self.assertFalse(load_series(archive)[0]["sig_ok"])

    def test_verify_invoice_rejects_unavailable_archive_evidence(self):
        rows = [
            entry(date(2026, 6, 24) + timedelta(days=i), "0.1")
            for i in range(7)
        ]
        document = invoice(
            obligation(), {"start": "2026-06-01", "end": "2026-06-30"}, rows
        )
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "archive"
            archive.mkdir()
            report = verify_invoice(document, archive)
        self.assertFalse(report["valid"])
        self.assertIn("archive evidence unavailable", " ".join(report["errors"]))

    def test_verify_invoice_recomputes_from_signed_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "archive"
            archive.mkdir()
            key = root / "key"
            allowed = root / "allowed_signers"
            for index in range(7):
                day = date(2026, 6, 24) + timedelta(days=index)
                payload = archive / f"{day.isoformat()}.json"
                payload.write_text(
                    json.dumps(
                        {
                            "date": day.isoformat(),
                            "fix_usd": f"0.10000{index + 1}",
                            "mode": "quote",
                            "publisher": "test/publisher",
                            "receipts": [],
                        },
                        indent=2,
                    )
                    + "\n"
                )
                self.assertTrue(
                    fixerd.sign(payload, key=key, allowed_signers=allowed)
                )
            series = load_series(archive)
            document = invoice(
                obligation(),
                {"start": "2026-06-01", "end": "2026-06-30"},
                series,
            )
            report = verify_invoice(document, archive)
            self.assertTrue(report["valid"], report["errors"])
            tampered = json.loads(json.dumps(document))
            tampered["settlement"]["uncollared_usd_per_cog"] = "9.000000"
            tampered["invoice_id"] = (
                "urn:cog:invoice:"
                + canon_sha256(
                    tampered, exclude_keys=("signatures", "invoice_id")
                )
            )
            report = verify_invoice(tampered, archive)
            self.assertFalse(report["valid"])
            self.assertIn("does not recompute", " ".join(report["errors"]))
            first_archive = archive / "2026-06-24.json"
            first_archive.write_bytes(
                first_archive.read_bytes().replace(b"0.100001", b"9.100001", 1)
            )
            report = verify_invoice(document, archive)
            self.assertFalse(report["valid"])
            self.assertIn(
                "signature invalid",
                " ".join(report["errors"]),
            )

    def test_rail_emitters_preserve_usdc_and_match_golden_shape(self):
        denom = denomination(
            basket="COG-1",
            spec_sha256="a" * 64,
            quantity="1000",
            usd_per_cog="0.123456",
            rule="normal",
            publisher="example/publisher",
            fix_window_end="2026-06-30",
            invoice_sha256="b" * 64,
        )
        x402 = emit_x402(
            {
                "accepts": [
                    {
                        "scheme": "exact",
                        "network": "eip155:8453",
                        "asset": "USDC",
                        "amount": "1234500",
                        "extra": {},
                    }
                ]
            },
            denom,
        )
        ap2 = emit_ap2(
            {
                "mandate": {
                    "id": "mandate-123",
                    "currency": "USDC",
                    "maximum": "1234500",
                }
            },
            denom,
        )
        expected_x402 = json.loads(
            (ROOT / "contracts" / "fixtures" / "x402-denomination.json").read_text()
        )
        expected_ap2 = json.loads(
            (ROOT / "contracts" / "fixtures" / "ap2-denomination.json").read_text()
        )
        self.assertEqual(x402, expected_x402)
        self.assertEqual(ap2, expected_ap2)
        self.assertEqual(x402["accepts"][0]["asset"], "USDC")


if __name__ == "__main__":
    unittest.main()

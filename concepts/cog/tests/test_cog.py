#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""COG test suite — stdlib unittest, no network.

Run:  python3 -m unittest discover -s tests -v
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
for sub in ("cogfix", "fixer", "harness", "mcp"):
    sys.path.insert(0, str(ROOT / sub))

import cogfix          # noqa: E402
import fixerd          # noqa: E402
import qualify         # noqa: E402
import cog_mcp         # noqa: E402


class TestCogfixMath(unittest.TestCase):
    def test_fix_at_exact_point(self):
        f, exact = cogfix.fix_at("2024-05")
        self.assertAlmostEqual(f, 7.0)
        self.assertTrue(exact)

    def test_fix_at_interpolates_log_linearly(self):
        f, exact = cogfix.fix_at("2024-06")
        self.assertFalse(exact)
        self.assertTrue(4.0 < f < 7.0)   # between Aug-2024 and May-2024 points

    def test_fix_at_holds_flat_after_last_point(self):
        last = cogfix.official_series()[-1][1]
        f, _ = cogfix.fix_at("2027-01")
        self.assertAlmostEqual(f, last)

    def test_fix_at_rejects_prehistory(self):
        with self.assertRaises(ValueError):
            cogfix.fix_at("2022-01")

    def test_reprice_pure_worked_example(self):
        total_usd, total_cog = cogfix.reprice(10_000, 24, "2024-05", quiet=True)
        self.assertEqual(total_usd, 240_000)
        self.assertAlmostEqual(total_cog, 44_591, delta=1)

    def test_reprice_hybrid_worked_example(self):
        total_usd, total_cog = cogfix.reprice(10_000, 24, "2024-05", fixed=3_000, quiet=True)
        self.assertEqual(total_usd, 240_000)
        self.assertAlmostEqual(total_cog, 103_214, delta=1)

    def test_reprice_hybrid_equals_fixed_plus_scaled_pure(self):
        # invoices are linear in the cog leg: hybrid = fixed*months + pure(cog_leg)
        _, pure = cogfix.reprice(7_000, 24, "2024-05", quiet=True)
        _, hybrid = cogfix.reprice(10_000, 24, "2024-05", fixed=3_000, quiet=True)
        self.assertAlmostEqual(hybrid, 3_000 * 24 + pure, places=6)

    def test_reprice_rejects_bad_fixed_leg(self):
        for bad in (-1, 10_000, 10_001):
            with self.assertRaises(ValueError):
                cogfix.reprice(10_000, 12, "2024-05", fixed=bad, quiet=True)

    def test_month_arithmetic(self):
        self.assertEqual(cogfix.ym_add("2024-11", 3), "2025-02")
        self.assertEqual(cogfix.ym_add("2024-01", -1), "2023-12")


class TestFixerd(unittest.TestCase):
    FAKE_FEED = {
        "cheap/model":  {"pricing": {"prompt": "0.0000001", "completion": "0.0000002"}},
        "mid/model":    {"pricing": {"prompt": "0.0000005", "completion": "0.000001"}},
        "pricey/model": {"pricing": {"prompt": "0.000001", "completion": "0.000002"}},
    }

    def test_blend_rule(self):
        self.assertAlmostEqual(fixerd.BLEND(10, 30), 0.8 * 10 + 0.2 * 30)

    def test_posted_quotes_sorted_and_filtered(self):
        rows = fixerd.posted_quotes(self.FAKE_FEED, ids=list(self.FAKE_FEED) + ["absent/model"])
        self.assertEqual([r["model"] for r in rows], ["cheap/model", "mid/model", "pricey/model"])
        self.assertAlmostEqual(rows[0]["blended_usd_per_M"], 0.8 * 0.1 + 0.2 * 0.2)

    def test_vw_median(self):
        runs = [{"price": 1.0, "weight": 1}, {"price": 2.0, "weight": 1}, {"price": 9.0, "weight": 1}]
        self.assertEqual(fixerd.vw_median(runs), 2.0)
        # heavy cheap run pulls the median down
        runs = [{"price": 1.0, "weight": 10}, {"price": 2.0, "weight": 1}, {"price": 9.0, "weight": 1}]
        self.assertEqual(fixerd.vw_median(runs), 1.0)

    def test_load_qualification_missing_falls_back(self):
        ids, meta = fixerd.load_qualification("2026-06-10")
        # no qualified.json in a clean checkout — assumed-basis fallback
        if not (ROOT / "fixer" / "qualified.json").exists():
            self.assertIsNone(ids)
            self.assertIn("assumed", meta["basis"])


class TestQualifyHarness(unittest.TestCase):
    def test_exam_integrity(self):
        items = qualify.EXAM["items"]
        self.assertEqual(len(items), 40)
        self.assertEqual(len({it["id"] for it in items}), 40)
        self.assertTrue(all(it["answer"].strip() for it in items))
        self.assertEqual(len(qualify.fingerprint()), 64)
        self.assertEqual(qualify.fingerprint(), qualify.fingerprint())

    def test_grading_normalization(self):
        self.assertTrue(qualify.grade("  Bob.\n", "bob"))
        self.assertTrue(qualify.grade("reasoning...\nblah\n3/8", "3/8"))
        self.assertTrue(qualify.grade("FALLS  Intelligence of   price", "falls intelligence of price"))
        self.assertFalse(qualify.grade("", "x"))
        self.assertFalse(qualify.grade("wrong", "right"))

    def test_mock_exam_gates_correctly(self):
        strong = qualify.examine("mock/strong", qualify.mock_asker(0.95))
        weak = qualify.examine("mock/weak", qualify.mock_asker(0.50))
        self.assertTrue(strong["passed"])
        self.assertFalse(weak["passed"])
        self.assertEqual(weak["correct"], 20)
        self.assertEqual(strong["total"], 40)


class TestMcpServer(unittest.TestCase):
    def setUp(self):
        self._real = cog_mcp.current_fix
        cog_mcp.current_fix = lambda: {"fix_usd": 0.144, "date": "2026-06-10",
                                       "mode": "test", "source": "test", "floor_usd": 0.118}

    def tearDown(self):
        cog_mcp.current_fix = self._real

    def call(self, method, params=None, id_=1):
        return cog_mcp.handle({"jsonrpc": "2.0", "id": id_, "method": method,
                               "params": params or {}})

    def tool(self, name, args):
        resp = self.call("tools/call", {"name": name, "arguments": args})
        self.assertFalse(resp["result"]["isError"])
        return json.loads(resp["result"]["content"][0]["text"])

    def test_initialize_and_list(self):
        init = self.call("initialize", {"protocolVersion": "2024-11-05"})
        self.assertEqual(init["result"]["serverInfo"]["name"], "cog-fix")
        tools = self.call("tools/list")
        names = [t["name"] for t in tools["result"]["tools"]]
        # The original four stay first and in order — agents bind to that surface, so
        # adding tools must not reshuffle it. Growth beyond them is allowed.
        self.assertEqual(names[:4],
                         ["get_fix", "price_in_cogs", "reprice_contract", "generate_sla"])

    def test_contracting_tools_are_exposed(self):
        names = [t["name"] for t in self.call("tools/list")["result"]["tools"]]
        for expected in ("generate_rider", "draft_obligation", "settlement_fix",
                         "settle_invoice", "verify_invoice"):
            self.assertIn(expected, names)

    def test_every_tool_declares_a_schema(self):
        for t in self.call("tools/list")["result"]["tools"]:
            self.assertIn("inputSchema", t, f"{t['name']} has no inputSchema")
            self.assertEqual(t["inputSchema"].get("type"), "object", t["name"])
            self.assertTrue(t["description"].strip(), f"{t['name']} has no description")

    def test_notification_gets_no_response(self):
        self.assertIsNone(cog_mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_unknown_method_errors(self):
        resp = self.call("bogus/method")
        self.assertEqual(resp["error"]["code"], -32601)

    def test_price_in_cogs(self):
        out = self.tool("price_in_cogs", {"usd": 144, "blended_tokens": 2_000_000})
        self.assertAlmostEqual(out["cogs_for_usd"], 1000.0)
        self.assertAlmostEqual(out["workload_cogs"], 2.0)
        self.assertAlmostEqual(out["workload_usd_today"], 0.288)

    def test_reprice_contract_hybrid(self):
        out = self.tool("reprice_contract", {"usd_per_month": 10_000, "months": 24,
                                             "start": "2024-05", "fixed_usd_per_month": 3_000})
        self.assertEqual(out["fixed_usd_total"], 240_000)
        self.assertAlmostEqual(out["hidden_short_pct"], 57.0, delta=0.1)

    def test_generate_sla(self):
        out = self.tool("generate_sla", {"provider": "P", "client": "C",
                                         "fixed_usd_per_month": 3000, "cogs_per_month": 1000})
        self.assertAlmostEqual(out["estimated_month1_usd"], 3000 + 1000 * 0.144)
        self.assertIn("COG-1 Fix", out["rider_text"])
        self.assertIn("Settlement Fix", out["rider_text"])


class TestUnitHonesty(unittest.TestCase):
    """The published label must never claim more evidence than the fix actually carries."""

    def test_unit_label_not_depth_verified_without_receipts(self):
        desc = cog_mcp.unit_description({"receipts": 0, "qualification": "assumed static allowlist"})
        self.assertNotIn("depth-verified", desc)
        self.assertIn("PROVISIONAL", desc)
        self.assertIn("assumed-qualifying", desc)

    def test_unit_label_earns_depth_verified_with_receipts_and_exam(self):
        desc = cog_mcp.unit_description({"receipts": 5, "qualification": "exam-qualified"})
        self.assertIn("depth-verified", desc)
        self.assertIn("exam-qualified", desc)

    def test_sla_rider_warns_when_publisher_misses_its_own_standard(self):
        real = cog_mcp.current_fix
        cog_mcp.current_fix = lambda: {"fix_usd": 0.144, "date": "2026-06-10", "mode": "quote",
                                       "source": "test", "floor_usd": 0.118, "age_days": 47,
                                       "stale": True, "receipts": 0,
                                       "qualification": "assumed static allowlist"}
        try:
            out = cog_mcp.t_generate_sla({"cogs_per_month": 1000})
        finally:
            cog_mcp.current_fix = real
        # §6 tells the client to audit against receipts; if there are none, say so.
        self.assertIn("BASIS WARNING", out["rider_text"])
        self.assertTrue(out["fix_basis_unmet"])

    def test_corrupt_fix_json_falls_through_instead_of_raising(self):
        import shutil
        import tempfile
        real_root, real_fetch = cog_mcp.ROOT, fixerd.fetch_models
        tmp = Path(tempfile.mkdtemp())
        (tmp / "fixer").mkdir()
        (tmp / "fixer" / "fix.json").write_text("{ this is not json")
        cog_mcp.ROOT = tmp
        fixerd.fetch_models = lambda: (_ for _ in ()).throw(OSError("offline"))
        try:
            f = cog_mcp.current_fix()
        finally:
            cog_mcp.ROOT, fixerd.fetch_models = real_root, real_fetch
            shutil.rmtree(tmp)
        # Corrupt published fix + no network drops past both settleable rungs. It lands on
        # the Epoch anchor (rung 4), not the bundled snapshot (rung 5) — the anchor is the
        # better-sourced of the two non-settleable fallbacks.
        self.assertEqual(f["tier"], "external-anchor")
        self.assertFalse(f["provenance"]["settleable"])

    def test_non_settleable_rungs_are_marked_as_such(self):
        """The whole point of the tier label: a research CSV must never quietly settle
        an invoice. Rungs 4 and 5 have to say so in the payload."""
        for tier in ("external-anchor", "bundled-snapshot"):
            desc = cog_mcp.unit_description({"tier": tier, "receipts": 0, "qualification": "x"})
            self.assertIn("NON-SETTLEABLE", desc, tier)


class TestQualifyGate(unittest.TestCase):
    def test_fingerprint_covers_the_pass_mark(self):
        before = qualify.fingerprint()
        original = qualify.EXAM["meta"]["threshold"]
        qualify.EXAM["meta"]["threshold"] = 0.05
        try:
            self.assertNotEqual(before, qualify.fingerprint())
        finally:
            qualify.EXAM["meta"]["threshold"] = original
        self.assertEqual(before, qualify.fingerprint())

    def test_spend_cap_aborts_mid_exam_and_a_partial_run_cannot_pass(self):
        r = qualify.examine("mock/perfect", qualify.mock_asker(1.0), budget=qualify.Budget(0.0005))
        self.assertTrue(r["aborted"])
        self.assertLess(r["administered"], r["total"])
        self.assertFalse(r["passed"])   # a half-sat exam is not a qualification

    def test_generous_budget_completes_the_exam(self):
        r = qualify.examine("mock/strong", qualify.mock_asker(0.95), budget=qualify.Budget(100.0))
        self.assertFalse(r["aborted"])
        self.assertEqual(r["administered"], r["total"])
        self.assertTrue(r["passed"])


class TestBlendIsDefinedOnce(unittest.TestCase):
    """The 4:1 mix is quoted in four places; a unit that means different things in
    different call sites is not a unit."""

    def test_python_definitions_agree(self):
        self.assertAlmostEqual(cogfix.blend(10, 30), fixerd.BLEND(10, 30))
        self.assertAlmostEqual(cogfix.blend(10, 30), 0.8 * 10 + 0.2 * 30)

    def test_data_json_prose_matches_the_code(self):
        prose = cogfix.DATA["spec"]["blend"]
        self.assertIn(f"{cogfix.BLEND_IN} * input_usd_per_M", prose)
        self.assertIn(f"{cogfix.BLEND_OUT} * output_usd_per_M", prose)

    def test_every_series_point_blends_correctly(self):
        # Stored to 4dp: the 2026 points came off a live feed and were rounded for
        # publication (0.25168 -> 0.2517, 0.11796 -> 0.1180). The rounding is left alone
        # because 0.2517 is the last official point and every headline figure in the repo
        # is computed from it. Asserting at stored precision still catches a leg/blend
        # mismatch, which is what this guards.
        for p in cogfix.DATA["frontier_tier_series"]:
            if "input_usd_per_M" not in p:
                continue
            self.assertAlmostEqual(
                p["blended_usd_per_M"],
                cogfix.blend(p["input_usd_per_M"], p["output_usd_per_M"]),
                places=4, msg=f"{p['date']} {p['model']} blended price does not match its legs")


class TestDemoMirrors(unittest.TestCase):
    """demo/index.html hardcodes copies of data.json so it works from file://.
    Drift is what left two dead endpoints quoted on the page for weeks."""

    DEMO = (ROOT / "demo" / "index.html").read_text()

    def test_demo_allowlist_matches_data_json(self):
        import re
        block = re.search(r"const ALLOWLIST = \[(.*?)\];", self.DEMO, re.S).group(1)
        demo_ids = set(re.findall(r'"([^"]+)"', block))
        self.assertEqual(demo_ids, set(cogfix.DATA["live_fix_allowlist"]))

    def test_demo_quotes_no_retired_endpoint(self):
        for entry in cogfix.DATA.get("retired_from_allowlist", []):
            self.assertNotIn(entry["id"], self.DEMO,
                             f"{entry['id']} was retired {entry['retired']} but the demo still quotes it")

    def test_demo_blend_matches_the_code(self):
        self.assertIn(f"{cogfix.BLEND_IN}*pin + {cogfix.BLEND_OUT}*pout", self.DEMO)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from anchor import (
    anchor_at,
    anchor_series,
    divergence,
    load_snapshot,
    normalize_blend,
)


class AnchorTests(unittest.TestCase):
    def test_vendored_snapshot_has_gpt4_mmlu_events(self):
        rows = load_snapshot()
        series = anchor_series(rows)
        self.assertEqual(len(series), 5)
        self.assertTrue(all(row["bench"] == "MMLU" for row in series))

    def test_anchor_at_is_step_function_never_interpolated(self):
        series = anchor_series()
        before_next = anchor_at("2024-05-20", series)
        self.assertEqual(before_next["date"], "2024-05-13")
        self.assertEqual(before_next["usd_per_million_tokens"], "7.500000")
        self.assertEqual(before_next["lookup"], "step-function")

    def test_blend_mismatch_is_explicit_with_uncertainty(self):
        normalized = normalize_blend("0.175")
        self.assertFalse(normalized["exact"])
        self.assertEqual(normalized["center"], "0.175000")
        self.assertEqual(normalized["lower"], "0.140000")
        self.assertEqual(normalized["upper"], "0.186667")

    def test_exact_normalization_requires_reconstructing_components(self):
        normalized = normalize_blend(
            "2.5",
            input_usd_per_million="2",
            output_usd_per_million="4",
        )
        self.assertTrue(normalized["exact"])
        self.assertEqual(normalized["usd_per_cog"], "2.400000")

    def test_divergence_uses_decimal_and_uncertainty_band(self):
        normalized = normalize_blend("0.175")
        result = divergence("0.144", normalized)
        self.assertEqual(result["difference_pct"], "-17.714286")
        self.assertTrue(result["inside_anchor_uncertainty"])

if __name__ == "__main__":
    unittest.main()

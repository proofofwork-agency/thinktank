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
from anchor.crosscheck import (
    DIFFERENT_MODEL,
    INSIDE,
    OUTSIDE,
    SAME_MODEL,
    blend_ratio_band,
    crosscheck_rows,
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

    def test_crosscheck_pins_ratios_and_selection_classification(self):
        rows = crosscheck_rows()
        self.assertEqual(
            [row.ratio_cog_to_epoch for row in rows],
            ["0.960000", "0.933333", "0.933333", "3.196347", "2.221041"],
        )
        self.assertEqual(
            [row.cog_basis for row in rows],
            ["exact", "exact", "exact", "exact", "interpolated"],
        )
        self.assertEqual(
            [(row.model_comparison, row.blend_band) for row in rows],
            [
                (SAME_MODEL, INSIDE),
                (SAME_MODEL, INSIDE),
                (SAME_MODEL, INSIDE),
                (DIFFERENT_MODEL, OUTSIDE),
                (DIFFERENT_MODEL, OUTSIDE),
            ],
        )
        self.assertEqual(
            tuple(str(value) for value in blend_ratio_band()),
            ("0.800000", "1.066667"),
        )

if __name__ == "__main__":
    unittest.main()

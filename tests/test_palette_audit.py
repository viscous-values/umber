"""Tests for scripts/palette_audit.py — color math and the palette checks.

Run: python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import palette_audit as pa  # noqa: E402
import palette_lib  # noqa: E402


class ColorMathTest(unittest.TestCase):
    def test_oklab_matches_reference_red(self):
        L, a, b = pa.oklab("#FF0000")
        self.assertAlmostEqual(L, 0.62796, places=3)
        self.assertAlmostEqual(a, 0.22486, places=3)
        self.assertAlmostEqual(b, 0.12585, places=3)

    def test_oklch_of_white_is_achromatic(self):
        L, C, _ = pa.oklch("#FFFFFF")
        self.assertAlmostEqual(L, 1.0, places=3)
        self.assertLess(C, 1e-3)

    def test_delta_e_of_identical_colors_is_zero(self):
        self.assertEqual(pa.delta_e("#26221E", "#26221E"), 0)

    def test_wcag_contrast_extremes_and_midgrey(self):
        self.assertAlmostEqual(pa.contrast("#FFFFFF", "#000000"), 21.0, places=2)
        self.assertAlmostEqual(pa.contrast("#777777", "#FFFFFF"), 4.48, places=2)

    def test_apca_reference_values(self):
        self.assertAlmostEqual(pa.apca("#000000", "#FFFFFF"), 106.04, places=1)
        self.assertAlmostEqual(pa.apca("#FFFFFF", "#000000"), -107.88, places=1)

    def test_cvd_simulation_keeps_greys(self):
        for kind in ("protan", "deutan", "tritan"):
            with self.subTest(kind=kind):
                self.assertLess(pa.delta_e(pa.simulate_cvd("#808080", kind), "#808080"), 0.01)

    def test_deutan_pulls_red_and_green_together(self):
        normal = pa.delta_e("#E06C75", "#98C379")
        deutan = pa.delta_e(pa.simulate_cvd("#E06C75", "deutan"), pa.simulate_cvd("#98C379", "deutan"))
        self.assertLess(deutan, normal)


def _canon():
    return palette_lib.prepare(REPO / "palette.toml")


def _by_id(checks):
    return {c.id: c for c in checks}


class VariantChecksTest(unittest.TestCase):
    """Today's canonical palette should reproduce the PALETTE-REVISIT.md table."""

    def setUp(self):
        self.checks = _by_id(pa.audit_variant(_canon()))

    def test_body_text_contrast_passes(self):
        self.assertTrue(self.checks["contrast:fg/bg"].ok)

    def test_link_too_close_to_body_text(self):
        self.assertFalse(self.checks["distinct:fg~link"].ok)

    def test_selected_link_equals_selected_warning(self):
        self.assertFalse(self.checks["onsel:link~neutral"].ok)

    def test_window_and_panel_surfaces_merge(self):
        self.assertFalse(self.checks["surface:bg>bg_panel"].ok)

    def test_terminal_black_invisible(self):
        self.assertFalse(self.checks["ansi:black/bg"].ok)

    def test_terminal_blue_and_cyan_close(self):
        self.assertFalse(self.checks["ansi:blue~cyan"].ok)

    def test_types_merge_with_variables(self):
        self.assertFalse(self.checks["syntax:variable~type"].ok)

    def test_comments_do_not_recede(self):
        self.assertFalse(self.checks["comment-recedes"].ok)

    def test_protan_merges_success_and_warning(self):
        self.assertFalse(self.checks["cvd-protan:success~warning"].ok)

    def test_focus_is_not_an_accent(self):
        self.assertFalse(self.checks["distinct:fg~accent"].ok)

    def test_accent_vs_status_is_advisory(self):
        check = self.checks["accent-vs-status:accent~error"]
        self.assertEqual(check.level, "warn")
        self.assertEqual(check.threshold, pa.THRESHOLDS["accent_vs_status_de"])


class FamilyChecksTest(unittest.TestCase):
    def test_todays_grounds_are_indistinct(self):
        pals = {name: pal for name, (_, pal) in pa.load_targets().items()}
        checks = _by_id(pa.audit_family(pals))
        self.assertFalse(checks["cross-ground:ash~slate"].ok)
        self.assertFalse(checks["cross-accent:slate~storm"].ok)


class CliTest(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, "-B", str(REPO / "scripts" / "palette_audit.py"), *args],
                              capture_output=True, text=True)

    def test_strict_exits_nonzero_on_todays_palettes(self):
        self.assertEqual(self._run("--strict").returncode, 1)

    def test_report_without_strict_exits_zero(self):
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("umber", result.stdout)

    def test_dir_without_palettes_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            result = self._run("--dir", d)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no palette", result.stderr)


if __name__ == "__main__":
    unittest.main()

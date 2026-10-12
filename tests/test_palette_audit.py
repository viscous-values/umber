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


class MeasureTest(unittest.TestCase):
    def test_dl_is_positive_when_b_sits_above_a(self):
        self.assertGreater(pa.measure("dl", "#202020", "#404040"), 0)
        self.assertLess(pa.measure("dl", "#404040", "#202020"), 0)

    def test_de_is_symmetric(self):
        self.assertAlmostEqual(pa.measure("de", "#E06C75", "#98C379"), pa.measure("de", "#98C379", "#E06C75"))

    def test_hue_delta_takes_the_short_way_round(self):
        # red sits at ~29°, magenta at ~328°: 61° apart across 0°, not 299°
        self.assertAlmostEqual(pa.hue_delta("#FF0000", "#FF00FF"), 60.87, places=1)

    def test_hue_delta_with_a_grey_is_zero(self):
        # a grey has no hue; it can never satisfy a "differs in hue" check
        self.assertEqual(pa.hue_delta("#808080", "#FF0000"), 0.0)


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

    def test_input_outline_must_reach_three_to_one(self):
        for bg in ("bg", "bg_panel"):
            check = self.checks[f"contrast:input_border/{bg}"]
            self.assertEqual(check.level, "error")
            self.assertEqual(check.threshold, pa.THRESHOLDS["nontext_contrast"])
            self.assertFalse(check.ok)  # hearth.3 on today's grounds: ~1.6:1

    def test_text_on_status_fills_must_read(self):
        for fill in ("error", "warning", "debug"):
            check = self.checks[f"contrast:fg_on_accent/{fill}"]
            self.assertEqual(check.level, "error")
            self.assertTrue(check.ok)  # VSCode status-bar items pass today

    def test_link_must_stand_off_body_text_by_the_plan_margin(self):
        check = self.checks["distinct:fg~link"]
        self.assertEqual(check.threshold, pa.THRESHOLDS["link_vs_fg_de"])
        self.assertEqual(pa.THRESHOLDS["link_vs_fg_de"], 0.10)

    def test_info_text_should_not_look_like_a_link(self):
        check = self.checks["distinct:link~info"]
        self.assertEqual(check.level, "warn")
        self.assertEqual(check.threshold, pa.THRESHOLDS["link_vs_info_de"])

    def test_accent_vs_status_is_advisory(self):
        check = self.checks["accent-vs-status:accent~error"]
        self.assertEqual(check.level, "warn")
        self.assertEqual(check.threshold, pa.THRESHOLDS["accent_vs_status_de"])


@unittest.skipUnless((REPO / "palettes" / "next").is_dir(), "no drafts")
class DraftChecksTest(unittest.TestCase):
    """Positive guard: the drafts clear every per-variant error-level check."""

    def test_every_draft_passes_per_variant_errors(self):
        for name, (_, pal) in pa.load_targets(REPO / "palettes" / "next").items():
            with self.subTest(draft=name):
                failing = [c.id for c in pa.audit_variant(pal) if c.level == "error" and not c.ok]
                self.assertEqual(failing, [])


class FamilyChecksTest(unittest.TestCase):
    def test_todays_grounds_are_indistinct(self):
        pals = {name: pal for name, (_, pal) in pa.load_targets().items()}
        checks = _by_id(pa.audit_family(pals))
        self.assertFalse(checks["cross-ground:ash~slate"].ok)
        self.assertFalse(checks["cross-accent:slate~storm"].ok)

    def test_todays_identity_and_syntax_keys_collapse(self):
        pals = {name: pal for name, (_, pal) in pa.load_targets().items()}
        checks = _by_id(pa.audit_family(pals))
        self.assertFalse(checks["cross-identity:slate~storm"].ok)   # same ground family, same accent
        syntax = [c for cid, c in checks.items() if cid.startswith("cross-syntax:")]
        self.assertEqual(len(syntax), 10)
        self.assertTrue(all(c.value == 0 for c in syntax))           # identical keys in all five
        self.assertFalse(any(cid.startswith("cross-fingerprint") for cid in checks))


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

    def test_invalid_palette_is_reported_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            text = (REPO / "palettes" / "tide.toml").read_text().replace('"0" = "#', '"0" = "#zz', 1)
            (Path(d) / "tide.toml").write_text(text)
            result = self._run("--dir", d)
        self.assertEqual(result.returncode, 2)
        self.assertIn("INVALID", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_dir_without_palettes_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            result = self._run("--dir", d)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no palette", result.stderr)


if __name__ == "__main__":
    unittest.main()

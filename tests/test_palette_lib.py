"""Tests for scripts/palette_lib.py — palette loading, role merge, reference resolution.

Run: python3 -m unittest discover -s tests
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import palette_lib  # noqa: E402


def _pal(**extra):
    pal = {
        "hearth": {"0": "#26221E", "1": "#2D2823"},
        "mist": {"2": "#88A6C5"},
        "var": {"name": "Umber"},
    }
    pal.update(extra)
    return pal


class ResolveTest(unittest.TestCase):
    def test_tier_key_returns_its_hex(self):
        self.assertEqual(palette_lib.resolve(_pal(), "hearth.0"), "#26221E")

    def test_reference_chain_is_followed_to_hex(self):
        pal = _pal(role={"focus_ring": "role.interactive", "interactive": "mist.2"})
        self.assertEqual(palette_lib.resolve(pal, "role.focus_ring"), "#88A6C5")

    def test_cycle_is_reported(self):
        pal = _pal(role={"a": "role.b", "b": "role.a"})
        with self.assertRaisesRegex(ValueError, "cycle"):
            palette_lib.resolve(pal, "role.a")

    def test_lowercase_hex_is_rejected(self):
        pal = _pal(role={"bg": "#26221e"})
        with self.assertRaisesRegex(ValueError, "#RRGGBB"):
            palette_lib.resolve(pal, "role.bg")

    def test_alpha_hex_is_rejected(self):
        pal = _pal(role={"scrim": "#00000080"})
        with self.assertRaisesRegex(ValueError, "#RRGGBB"):
            palette_lib.resolve(pal, "role.scrim")

    def test_missing_reference_names_the_chain(self):
        pal = _pal(role={"link": "glow.9"})
        with self.assertRaisesRegex(ValueError, r"role\.link -> glow\.9"):
            palette_lib.resolve(pal, "role.link")

    def test_var_values_are_returned_verbatim(self):
        self.assertEqual(palette_lib.resolve(_pal(), "var.name"), "Umber")


class VariantSlugTest(unittest.TestCase):
    def test_canonical_palette_is_umber_wherever_it_lives(self):
        self.assertEqual(palette_lib.variant_slug(Path("palette.toml")), "umber")
        self.assertEqual(palette_lib.variant_slug(Path("palettes/next/palette.toml")), "umber")

    def test_variant_slug_is_the_file_stem(self):
        self.assertEqual(palette_lib.variant_slug(Path("palettes/tide.toml")), "tide")

    def test_markup_in_a_filename_is_rejected(self):
        for name in ("x<b>.toml", "Tide.toml", "tide two.toml", 'a"b.toml'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "lowercase"):
                palette_lib.variant_slug(Path(name))


class DeepMergeTest(unittest.TestCase):
    def test_override_replaces_leaf_and_keeps_others(self):
        merged = palette_lib.deep_merge({"a": "x", "b": "y"}, {"b": "z"})
        self.assertEqual(merged, {"a": "x", "b": "z"})

    def test_nested_tables_merge(self):
        merged = palette_lib.deep_merge(
            {"syntax": {"string": "spark.green", "number": "spark.orange"}},
            {"syntax": {"number": "spark.amber"}},
        )
        self.assertEqual(merged, {"syntax": {"string": "spark.green", "number": "spark.amber"}})

    def test_unknown_override_key_is_rejected(self):
        with self.assertRaisesRegex(ValueError, r"role\.lnik"):
            palette_lib.deep_merge({"link": "glow.2"}, {"lnik": "mist.2"}, path="role")

    def test_table_scalar_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            palette_lib.deep_merge({"syntax": {"string": "spark.green"}}, {"syntax": "mist.2"})

    def test_defaults_are_not_mutated(self):
        defaults = {"syntax": {"string": "spark.green"}}
        palette_lib.deep_merge(defaults, {"syntax": {"string": "mist.1"}})
        self.assertEqual(defaults, {"syntax": {"string": "spark.green"}})


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.roles = d / "roles.toml"
        self.roles.write_text(
            '[role]\nbg = "hearth.0"\nlink = "mist.2"\n'
            '[role.syntax]\nfunction = "role.link"\n'
        )
        self.variant = d / "slate.toml"
        self.variant.write_text(
            '[hearth]\n"0" = "#232527"\n[mist]\n"2" = "#88A6C5"\n"3" = "#A8BDD6"\n'
            '[role]\nlink = "mist.3"\n'
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_roles_resolve_to_hex_with_variant_override(self):
        pal = palette_lib.prepare(self.variant, self.roles)
        self.assertEqual(pal["role"]["bg"], "#232527")
        self.assertEqual(pal["role"]["link"], "#A8BDD6")

    def test_nested_role_follows_overridden_reference(self):
        pal = palette_lib.prepare(self.variant, self.roles)
        self.assertEqual(pal["role"]["syntax"]["function"], "#A8BDD6")

    def test_variant_without_role_table_gets_defaults(self):
        self.variant.write_text('[hearth]\n"0" = "#232527"\n[mist]\n"2" = "#88A6C5"\n')
        pal = palette_lib.prepare(self.variant, self.roles)
        self.assertEqual(pal["role"]["link"], "#88A6C5")


if __name__ == "__main__":
    unittest.main()

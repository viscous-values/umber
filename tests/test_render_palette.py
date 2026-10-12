"""render_palette.py guards and draft-palette rendering.

Run: python3 -m unittest discover -s tests
"""

import argparse
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import render_palette  # noqa: E402

NEXT = REPO / "palettes" / "next"


class DraftGuardTest(unittest.TestCase):
    """Drafts in palettes/next/ share filenames with real variants; rendering one
    would overwrite that variant's shipped files. render must refuse."""

    def setUp(self):
        self.calls = []
        self._render_one = render_palette.render_one
        render_palette.render_one = lambda pal, variant: self.calls.append(variant) or []

    def tearDown(self):
        render_palette.render_one = self._render_one

    def _args(self, palette, force=False):
        return argparse.Namespace(palette=palette, variant=None, force=force)

    def test_render_refuses_draft_palettes(self):
        with self.assertRaises(SystemExit) as cm:
            render_palette.cmd_render(self._args(NEXT / "palette.toml"))
        self.assertIn("draft", str(cm.exception.code))
        self.assertEqual(self.calls, [])

    def test_force_renders_a_draft(self):
        with contextlib.redirect_stdout(io.StringIO()):
            render_palette.cmd_render(self._args(NEXT / "tide.toml", force=True))
        self.assertEqual(self.calls, ["tide"])

    def test_shipped_palettes_render(self):
        with contextlib.redirect_stdout(io.StringIO()):
            render_palette.cmd_render(self._args(REPO / "palettes" / "tide.toml"))
        self.assertEqual(self.calls, ["tide"])


@unittest.skipUnless(NEXT.is_dir(), "no drafts")
class DraftConsumerRolesTest(unittest.TestCase):
    """Browser sites that name a job (link, field focus) must follow that job's
    role, so a draft's link/focus decision reaches Chromium and Firefox too."""

    def _render(self, tmpl, path):
        pal = render_palette.prepare_palette(path, render_palette.derive_variant(path))
        text = (render_palette.TEMPLATE_DIR / tmpl).read_text()
        return pal, render_palette.render_template(text, pal)

    def test_chromium_new_tab_links_use_the_link_role(self):
        for path in sorted(NEXT.glob("*.toml")):
            with self.subTest(draft=path.name):
                pal, out = self._render("chromium-manifest.json.tmpl", path)
                ntp_link = json.loads(out)["theme"]["colors"]["ntp_link"]
                self.assertEqual(ntp_link, list(render_palette.hex_to_rgb(pal["role"]["link"])))

    def test_firefox_field_focus_border_uses_the_focus_role(self):
        # The drafts set focus_ring = accent, which would hide a template that
        # names role.accent directly; use a variant whose focus ring differs.
        import tempfile
        text = (NEXT / "tide.toml").read_text()
        self.assertIn('focus_ring        = "role.accent"', text)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "tide.toml"
            path.write_text(text.replace('focus_ring        = "role.accent"', 'focus_ring        = "mist.1"'))
            pal, out = self._render("firefox-manifest.json.tmpl", path)
        border = json.loads(out)["theme"]["colors"]["toolbar_field_border_focus"]
        self.assertEqual(border, pal["mist"]["1"])


if __name__ == "__main__":
    unittest.main()

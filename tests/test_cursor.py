"""Per-variant cursors: the Nordic-cursors recolor, the committed themes, and
the Global Theme / install.sh wiring.

The committed-theme checks need only the repo; the recolor itself needs
~/.icons/Nordic-cursors and runs via scripts/build-cursor.sh.

Run: python3 -m unittest discover -s tests
"""

import configparser
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))

import palette_audit as pa  # noqa: E402
import palette_lib  # noqa: E402
import recolor_nordic_inplace as recolor  # noqa: E402
import render_palette  # noqa: E402
from test_plasma_color_scheme import bash_functions, package_dir  # noqa: E402

SHIPPED = [REPO / "palette.toml", *sorted((REPO / "palettes").glob("*.toml"))]
VARIANTS = {palette_lib.variant_slug(p): p for p in SHIPPED}


def hexrgb(h):
    return tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))


def as_hex(rgb):
    return "#%02X%02X%02X" % tuple(rgb)


def frames(path, size=60):
    """(r, g, b, a) pixels, still premultiplied, of every image chunk of one size."""
    b = path.read_bytes()
    hdr, ntoc = struct.unpack_from("<I", b, 4)[0], struct.unpack_from("<I", b, 12)[0]
    out = []
    for i in range(ntoc):
        kind, _sub, pos = struct.unpack_from("<III", b, hdr + i * 12)
        if kind != recolor.IMG_TYPE:
            continue
        chunk, _t, _s, _v, w, h, *_ = struct.unpack_from("<IIIIIIIII", b, pos)
        if w != size:
            continue
        px = b[pos + chunk:pos + chunk + w * h * 4]
        out.append([(px[k + 2], px[k + 1], px[k], px[k + 3]) for k in range(0, len(px), 4)])
    return out


def opaque_colors(path):
    return Counter((r, g, b) for f in frames(path) for r, g, b, a in f if a == 255)


def ab_distance(x, y):
    """OKLab chroma-plane distance: same hue and chroma, lightness ignored."""
    (_, a1, b1), (_, a2, b2) = pa.oklab(x), pa.oklab(y)
    return ((a1 - a2) ** 2 + (b1 - b2) ** 2) ** 0.5


def defaults_cursor(variant):
    section = None
    for line in (package_dir(variant) / "contents" / "defaults").read_text().splitlines():
        if line.startswith("["):
            section = line.strip()
        elif section == "[kcminputrc][Mouse]" and line.startswith("cursorTheme="):
            return line.split("=", 1)[1].strip()
    return None


class RecolorMappingTest(unittest.TestCase):
    """What each Nord color in the source becomes, per variant."""

    def setUp(self):
        self.maps = {v: (palette_lib.prepare(p), recolor.mapper(palette_lib.prepare(p))) for v, p in VARIANTS.items()}

    def test_body_takes_the_ground_hue_and_keeps_nords_value(self):
        for v, (pal, remap) in self.maps.items():
            with self.subTest(variant=v):
                body = as_hex(remap(hexrgb(recolor.NORD["body"])))
                self.assertAlmostEqual(pa.oklab(body)[0], pa.oklab(recolor.NORD["body"])[0], delta=0.01)
                self.assertLess(ab_distance(body, pal["hearth"]["2"]), 0.01)

    def test_outline_takes_the_text_hue_and_keeps_nords_value(self):
        for v, (pal, remap) in self.maps.items():
            with self.subTest(variant=v):
                out = as_hex(remap(hexrgb(recolor.NORD["outline"])))
                self.assertAlmostEqual(pa.oklab(out)[0], pa.oklab(recolor.NORD["outline"])[0], delta=0.01)
                self.assertLess(ab_distance(out, pal["role"]["fg"]), 0.01)

    def test_spinner_teal_becomes_the_signature_accent(self):
        for v, (pal, remap) in self.maps.items():
            with self.subTest(variant=v):
                self.assertLess(pa.delta_e(as_hex(remap(hexrgb(recolor.NORD["teal"]))), pal["role"]["accent"]), 0.01)

    def test_status_badges_take_the_variants_status_colors(self):
        for v, (pal, remap) in self.maps.items():
            with self.subTest(variant=v):
                self.assertLess(pa.delta_e(as_hex(remap(hexrgb(recolor.NORD["red"]))), pal["role"]["error"]), 0.01)
                self.assertLess(pa.delta_e(as_hex(remap(hexrgb(recolor.NORD["green"]))), pal["role"]["success"]), 0.01)

    def test_body_to_outline_edge_blend_stays_off_the_accent(self):
        # The anti-aliased step between the dark body and light outline sits
        # nearer Nord's blues than either end; it must stay a body/outline blend.
        mid = "#8A909D"
        for v, (pal, remap) in self.maps.items():
            with self.subTest(variant=v):
                got = as_hex(remap(hexrgb(mid)))
                body, line = (as_hex(remap(hexrgb(recolor.NORD[k]))) for k in ("body", "outline"))
                t = (pa.oklab(got)[0] - pa.oklab(body)[0]) / (pa.oklab(line)[0] - pa.oklab(body)[0])
                blend = tuple(x + (y - x) * t for x, y in zip(pa.oklab(body), pa.oklab(line)))
                self.assertLess(sum((a - b) ** 2 for a, b in zip(pa.oklab(got), blend)) ** 0.5, 0.015)

    def test_premultiplied_pixels_keep_their_alpha(self):
        _pal, remap = self.maps["umber"]
        r, g, b = hexrgb(recolor.NORD["body"])
        out = recolor.remap_pixel(r * 128 // 255, g * 128 // 255, b * 128 // 255, 128, remap)
        full = remap((r, g, b))
        self.assertEqual(out[3], 128)
        for got, want in zip(out[:3], full):
            self.assertLessEqual(abs(got - want * 128 // 255), 2)
        self.assertEqual(recolor.remap_pixel(0, 0, 0, 0, remap), (0, 0, 0, 0))


class RecolorCliTest(unittest.TestCase):
    def test_refuses_draft_and_archived_palettes(self):
        # palettes/next/tide.toml would build into cursors/Umber-Tide-cursor.
        calls = []
        real = recolor.build
        recolor.build = lambda *a: calls.append(a) or True
        try:
            with self.assertRaises(SystemExit) as cm:
                recolor.main(["--palette", str(REPO / "palettes" / "archive" / "classic" / "tide.toml")])
            self.assertIn("draft or archived", str(cm.exception.code))
            self.assertEqual(calls, [])
        finally:
            recolor.build = real


class CommittedCursorTest(unittest.TestCase):
    def test_each_global_theme_names_its_own_committed_cursor(self):
        names = set()
        for v in VARIANTS:
            with self.subTest(variant=v):
                name = defaults_cursor(v)
                self.assertEqual(name, render_palette.cursor_theme(v))
                theme = REPO / "cursors" / name
                self.assertTrue((theme / "cursors" / "default").is_file(), theme)
                index = configparser.ConfigParser(interpolation=None)
                index.read(theme / "index.theme")
                self.assertEqual(index["Icon Theme"]["Name"], render_palette.compute_var({}, v)["name"])
                names.add(name)
        self.assertEqual(len(names), len(VARIANTS))

    def test_alias_links_stay_inside_their_theme(self):
        for v in VARIANTS:
            with self.subTest(variant=v):
                cursors = REPO / "cursors" / render_palette.cursor_theme(v) / "cursors"
                links = [p for p in cursors.iterdir() if p.is_symlink()]
                self.assertGreater(len(links), 0)
                for link in links:
                    self.assertTrue(link.resolve().is_relative_to(cursors.resolve()), link)

    def test_committed_cursor_matches_the_current_palette(self):
        # The source's body, outline and spinner are exact Nord colors, so the
        # committed pixels must be exactly what the palette maps them to now.
        for v, path in VARIANTS.items():
            with self.subTest(variant=v):
                remap = recolor.mapper(palette_lib.prepare(path))
                cursors = REPO / "cursors" / render_palette.cursor_theme(v) / "cursors"
                arrow, spinner = opaque_colors(cursors / "default"), opaque_colors(cursors / "wait")
                self.assertEqual(arrow.most_common(1)[0][0], remap(hexrgb(recolor.NORD["body"])),
                                 "cursor is stale: run scripts/build-cursor.sh")
                self.assertIn(remap(hexrgb(recolor.NORD["outline"])), arrow)
                self.assertIn(remap(hexrgb(recolor.NORD["teal"])), spinner)


class InstallCursorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _bash(self, script):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env, cwd=REPO)

    def test_install_names_the_global_themes_cursor(self):
        funcs = bash_functions(REPO / "install.sh", "set_variant_names")
        for v in VARIANTS:
            with self.subTest(variant=v):
                out = self._bash(f'{funcs}\nset_variant_names {v}\necho "$CURSOR_THEME"')
                self.assertEqual(out.stdout.strip(), defaults_cursor(v))

    def test_install_puts_each_variants_cursor_in_the_icon_dir(self):
        funcs = bash_functions(REPO / "install.sh", "set_variant_names", "install_variant_user_files")
        h = self.home
        out = self._bash(
            'set -u; step() { :; }; ok() { :; }; note() { :; }\n'
            f'REPO_ROOT="{REPO}"; ICONS_DIR="{h}/icons"; SCHEMES_DIR="{h}/schemes"; LNF_DIR="{h}/lnf"; '
            f'SHELLS_DIR="{h}/shells"; KONSOLE_DIR="{h}/konsole"; APPS_DIR="{h}/apps"\n'
            'mkdir -p "$ICONS_DIR" "$SCHEMES_DIR" "$LNF_DIR" "$SHELLS_DIR" "$KONSOLE_DIR" "$APPS_DIR"\n'
            f'{funcs}\ninstall_variant_user_files tide')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue((h / "icons" / defaults_cursor("tide") / "cursors" / "default").is_file())


if __name__ == "__main__":
    unittest.main()

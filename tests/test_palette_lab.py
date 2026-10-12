"""Tests for scripts/render_lab.py and the lab's JS color engine.

The engine test runs scripts/templates/palette-lab-engine.js under node and
requires it to reproduce palette_audit.py's numbers for every check.

Run: python3 -m unittest discover -s tests
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import palette_audit  # noqa: E402
import render_lab  # noqa: E402

ENGINE = REPO / "scripts" / "templates" / "palette-lab-engine.js"
NOWHERE = REPO / "palettes" / "does-not-exist"


class BuildDataTest(unittest.TestCase):
    def test_current_set_lists_all_five_variants_in_family_order(self):
        data = render_lab.build_data(next_dir=NOWHERE)
        slugs = [v["slug"] for v in data["sets"]["current"]["variants"]]
        self.assertEqual(slugs, ["umber", "ash", "slate", "tide", "storm"])

    def test_specs_are_the_audit_specs(self):
        data = render_lab.build_data(next_dir=NOWHERE)
        self.assertEqual(data["specs"], palette_audit.check_specs())
        self.assertEqual(data["thresholds"], palette_audit.THRESHOLDS)

    def test_no_draft_set_without_next_dir(self):
        self.assertNotIn("draft", render_lab.build_data(next_dir=NOWHERE)["sets"])

    def test_draft_set_loads_from_next_dir(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(REPO / "palettes" / "tide.toml", Path(d) / "tide.toml")
            data = render_lab.build_data(next_dir=Path(d))
        self.assertEqual([v["slug"] for v in data["sets"]["draft"]["variants"]], ["tide"])

    def test_variant_carries_raw_tiers_overrides_and_python_audit(self):
        import palette_lib
        raw = palette_lib.load_toml(REPO / "palette.toml")
        umber = render_lab.build_data(next_dir=NOWHERE)["sets"]["current"]["variants"][0]
        self.assertEqual(umber["tiers"]["hearth"], raw["hearth"])
        self.assertEqual(umber["role"], raw.get("role", {}))
        self.assertEqual(umber["meta"], raw["meta"])
        self.assertIn("contrast:fg/bg", umber["audit"])


class RenderTest(unittest.TestCase):
    def test_render_inlines_engine_and_data(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "lab.html"
            render_lab.render(out=out, next_dir=NOWHERE)
            html = out.read_text()
        self.assertIn("const DATA = ", html)
        self.assertIn("function oklchToHex", html)
        self.assertNotIn("/*__DATA__*/", html)
        self.assertNotIn("/*__ENGINE__*/", html)

    def test_hostile_meta_text_cannot_leave_the_data_script(self):
        hostile = '</script><script>alert(1)</script><!-- & "quotes"'
        with tempfile.TemporaryDirectory() as d:
            text = (REPO / "palettes" / "tide.toml").read_text()
            text = re.sub(r'(?m)^concept = .*\n', '', text)
            text = text.replace('[meta]\n', '[meta]\nconcept = ' + json.dumps(hostile) + '\n', 1)
            (Path(d) / "tide.toml").write_text(text)
            out = Path(d) / "lab.html"
            render_lab.render(out=out, next_dir=Path(d))
            html = out.read_text()
        payload = html.split("const DATA = ", 1)[1].split(";\n", 1)[0]
        self.assertNotIn("<", payload)
        self.assertEqual(json.loads(payload)["sets"]["draft"]["variants"][0]["concept"], hostile)

    def test_committed_lab_page_is_current(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "lab.html"
            render_lab.render(out=out)
            self.assertEqual(out.read_text(), render_lab.OUT.read_text(),
                             "mockups/palette-lab.html is stale: run python3 scripts/render_lab.py")


@unittest.skipUnless(shutil.which("node"), "node not installed")
class EngineParityTest(unittest.TestCase):
    def _node(self, js, data):
        with tempfile.TemporaryDirectory() as d:
            data_path = Path(d) / "data.json"
            data_path.write_text(json.dumps(data))
            result = subprocess.run(
                ["node", "-e", js, str(ENGINE), str(data_path)],
                capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_js_audit_matches_python_for_every_check(self):
        data = render_lab.build_data(next_dir=NOWHERE)
        js = """
        const E = require(process.argv[1]);
        const data = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
        const out = {};
        for (const v of data.sets.current.variants) {
          const pal = E.prepare(v, data.roles);
          out[v.slug] = Object.fromEntries(E.auditVariant(pal, data.specs).map(c => [c.id, c.value]));
        }
        console.log(JSON.stringify(out));
        """
        js_values = self._node(js, data)
        for v in data["sets"]["current"]["variants"]:
            for check_id, py_value in v["audit"].items():
                with self.subTest(variant=v["slug"], check=check_id):
                    self.assertAlmostEqual(js_values[v["slug"]][check_id], py_value, places=6)

    def test_saved_edits_apply_only_while_the_file_value_is_unchanged(self):
        js = """
        const E = require(process.argv[1]);
        const original = {hearth: {"0": "#111111", "1": "#222222"}, glow: {"1": "#CCCCCC"}};
        const tuned = structuredClone(original); tuned.hearth["0"] = "#151515"; tuned.glow["1"] = "#DDDDDD";
        const edits = E.diffEdits(original, tuned);
        // the file was regenerated: glow.1 changed underneath the saved edit, hearth.1 vanished
        const regenerated = {hearth: {"0": "#111111"}, glow: {"1": "#C0C0C0"}};
        const res = E.applyEdits(regenerated, {...edits, "hearth.1": {from: "#222222", to: "#2A2A2A"}});
        console.log(JSON.stringify({edits, res}));
        """
        out = self._node(js, {})
        self.assertEqual(out["edits"], {"hearth.0": {"from": "#111111", "to": "#151515"},
                                        "glow.1": {"from": "#CCCCCC", "to": "#DDDDDD"}})
        self.assertEqual(out["res"]["tiers"], {"hearth": {"0": "#151515"}, "glow": {"1": "#C0C0C0"}})
        self.assertEqual(out["res"]["applied"], ["hearth.0"])
        self.assertEqual(sorted(out["res"]["stale"]), ["glow.1", "hearth.1"])

    def test_exported_toml_round_trips_through_palette_lib(self):
        import palette_lib
        data = render_lab.build_data()
        js = """
        const E = require(process.argv[1]);
        const data = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
        const out = {};
        for (const [setName, set] of Object.entries(data.sets))
          for (const v of set.variants) out[`${setName}/${v.slug}`] = E.toToml(v);
        console.log(JSON.stringify(out));
        """
        exported = self._node(js, data)
        entries = {f"{s}/{v['slug']}": v for s, st in data["sets"].items() for v in st["variants"]}
        self.assertEqual(set(exported), set(entries))
        with tempfile.TemporaryDirectory() as d:
            for key, toml_text in exported.items():
                with self.subTest(variant=key):
                    path = Path(d) / "export.toml"
                    path.write_text(toml_text)
                    got, want = palette_lib.prepare(path), palette_lib.prepare(REPO / entries[key]["file"])
                    self.assertEqual(got, want)

    def test_js_hue_delta_with_a_grey_is_zero(self):
        js = """
        const E = require(process.argv[1]);
        console.log(JSON.stringify([E.hueDelta('#808080', '#FF0000'), E.hueDelta('#FF0000', '#FF00FF')]));
        """
        grey, wrap = self._node(js, {})
        self.assertEqual(grey, 0)
        self.assertAlmostEqual(wrap, palette_audit.hue_delta("#FF0000", "#FF00FF"), places=9)

    def test_js_oklch_round_trips_palette_hexes(self):
        data = render_lab.build_data(next_dir=NOWHERE)
        hexes = sorted({h for v in data["sets"]["current"]["variants"]
                        for tier in v["tiers"].values() for h in tier.values()})
        js = """
        const E = require(process.argv[1]);
        const hexes = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
        console.log(JSON.stringify(hexes.map(h => { const [L, C, H] = E.oklch(h); return E.oklchToHex(L, C, H).hex; })));
        """
        self.assertEqual(self._node(js, hexes), hexes)


if __name__ == "__main__":
    unittest.main()

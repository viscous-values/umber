"""Tests for scripts/render_lab.py and the lab's JS color engine.

The engine test runs scripts/templates/palette-lab-engine.js under node and
requires it to reproduce palette_audit.py's numbers for every check.

Run: python3 -m unittest discover -s tests
"""

import json
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
        umber = render_lab.build_data(next_dir=NOWHERE)["sets"]["current"]["variants"][0]
        self.assertEqual(umber["tiers"]["hearth"]["0"], "#26221E")
        self.assertEqual(umber["role"], {})
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
        self.assertNotIn("</script><", html.split("const DATA = ")[1].split(";\n")[0])


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

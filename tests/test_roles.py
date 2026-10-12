"""Role-layer integration: roles.toml resolves for every palette, templates
speak in roles, and rendered consumer files stay in sync.

Run: python3 -m unittest discover -s tests
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import palette_lib  # noqa: E402

TEMPLATES = REPO / "scripts" / "templates"
TOKEN_RE = re.compile(r"\{\{\s*([\w.]+)")


def all_palettes():
    return [REPO / "palette.toml", *sorted((REPO / "palettes").glob("*.toml"))]


def template_tokens(path):
    """Yield (line_no, key) for tokens outside documentation lines.

    Documentation lines are comments ('#', '//') and the VSCode "_palette"
    block, which deliberately dump raw tiers for readers.
    """
    in_palette_dump = False
    for no, line in enumerate(path.read_text().splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith('"_palette"'):
            in_palette_dump = True
        if in_palette_dump:
            if stripped.startswith("}"):
                in_palette_dump = False
            continue
        if stripped.startswith(("#", "//")):
            continue
        for key in TOKEN_RE.findall(line):
            yield no, key


class RolesTest(unittest.TestCase):
    def test_every_palette_resolves_all_roles(self):
        for path in all_palettes():
            with self.subTest(palette=path.name):
                pal = palette_lib.prepare(path)
                self.assertIn("syntax", pal["role"])
                self.assertIn("ansi", pal["role"])

    def test_templates_reference_roles_not_tiers(self):
        offenders = []
        for tmpl in sorted(TEMPLATES.glob("*.tmpl")):
            for no, key in template_tokens(tmpl):
                if not key.startswith(("role.", "var.")):
                    offenders.append(f"{tmpl.name}:{no} {key}")
        self.assertEqual(offenders, [], "templates must use role.* (tiers only in doc lines)")

    def test_rendered_consumers_match_templates(self):
        result = subprocess.run(
            [sys.executable, "-B", str(REPO / "scripts" / "render_palette.py"), "check"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

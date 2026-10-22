"""Web export: umber-web/<variant>.css carries every role, named by its path.

Run: python3 -m unittest discover -s tests
"""

import re
import sys
import tomllib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import palette_lib  # noqa: E402
import render_palette  # noqa: E402

TEMPLATE = REPO / "scripts" / "templates" / "web-theme.css.tmpl"
DECL_RE = re.compile(r"^\s*(--umber-[a-z0-9-]+):\s*\{\{\s*role\.([\w.]+)\s*\}\};\s*$")
RENDERED_RE = re.compile(r"^\s*(--umber-[a-z0-9-]+):\s*(#[0-9A-F]{6});\s*$")
TOKEN_RE = re.compile(r"\{\{\s*([\w.]+)")


def flat(path):
    return "--umber-" + path.replace(".", "-").replace("_", "-")


def leaves(tree, prefix=""):
    """(path, value) for every leaf role: "bg", "on_selection.fg", "bracket.1", ..."""
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            yield from leaves(value, f"{path}.")
        else:
            yield path, value


def all_palettes():
    return [REPO / "palette.toml", *sorted((REPO / "palettes").glob("*.toml"))]


class WebExportTest(unittest.TestCase):
    def setUp(self):
        self.roles = [path for path, _ in leaves(tomllib.loads((REPO / "roles.toml").read_text())["role"])]
        self.decls = []
        self.other_tokens = []
        for line in TEMPLATE.read_text().splitlines():
            m = DECL_RE.match(line)
            if m:
                self.decls.append((m.group(1), m.group(2)))
            else:
                self.other_tokens.extend(TOKEN_RE.findall(line))

    def test_template_declares_every_role_once(self):
        declared = [role for _, role in self.decls]
        self.assertEqual(sorted(declared), sorted(self.roles),
                         "a role in roles.toml is missing from (or extra in) the web template")
        self.assertEqual(len(declared), len(set(declared)), "a role is declared twice")
        self.assertTrue(all(t.startswith("var.") for t in self.other_tokens),
                        f"tokens outside declarations must be var.*: {self.other_tokens}")

    def test_property_names_follow_the_role_path(self):
        for name, role in self.decls:
            self.assertEqual(name, flat(role))
        names = [flat(role) for role in self.roles]
        self.assertEqual(len(names), len(set(names)), "two roles flatten to one property name")

    def test_rendered_values_are_the_resolved_roles(self):
        template = TEMPLATE.read_text()
        for path in all_palettes():
            with self.subTest(palette=path.name):
                variant = palette_lib.variant_slug(path)
                pal = render_palette.prepare_palette(path, variant)
                rendered = render_palette.render_template(template, pal)
                values = {m.group(1): m.group(2) for line in rendered.splitlines()
                          if (m := RENDERED_RE.match(line))}
                resolved = palette_lib.prepare(path)["role"]
                self.assertEqual(values, {flat(p): v for p, v in leaves(resolved)})

    def test_selector_and_path_use_the_package_slug(self):
        for path in all_palettes():
            with self.subTest(palette=path.name):
                variant = palette_lib.variant_slug(path)
                slug = "umber" if variant == "umber" else f"umber-{variant}"
                out = render_palette.outputs_for(variant)["web-theme.css.tmpl"]
                self.assertEqual(out, f"umber-web/{slug}.css")
                text = (REPO / out).read_text()
                self.assertEqual(re.findall(r'\[data-theme="([^"]+)"\]', text), [slug])


if __name__ == "__main__":
    unittest.main()

"""Global Theme -> color scheme: Plasma must find each variant's .colors file.

When System Settings applies a Global Theme, Plasma reads ColorScheme= from the
package's contents/defaults and finds the file with a name heuristic
(KLookAndFeelManager::colorSchemeFile in plasma-workspace 6.x): separators are
dropped and the letter after each is upper-cased, then the first installed
*.colors file whose name ends with the result wins. "Umber-Slate" becomes
"UmberSlate", so a file named Umber-Slate.colors is never found and the theme
silently keeps the previous variant's colors.

Run: python3 -m unittest discover -s tests
"""

import configparser
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import palette_lib  # noqa: E402

SHIPPED = [REPO / "palette.toml", *sorted((REPO / "palettes").glob("*.toml"))]
VARIANTS = [palette_lib.variant_slug(p) for p in SHIPPED]


def package_dir(variant):
    slug = "umber" if variant == "umber" else f"umber-{variant}"
    return REPO / f"io.github.viscous-values.{slug}"


def kde_scheme_suffix(name):
    """The file-name ending KLookAndFeelManager::colorSchemeFile looks for."""
    name = name.replace("'", "")
    fixer = re.compile(r"[\W,.-]+(.?)", re.ASCII)
    while m := fixer.search(name):
        name = name[:m.start()] + m.group(1).upper() + name[m.end():]
    return name[:1].upper() + name[1:] + ".colors"


def defaults_color_scheme(variant):
    section = None
    for line in (package_dir(variant) / "contents" / "defaults").read_text().splitlines():
        if line.startswith("["):
            section = line.strip()
        elif section == "[kdeglobals][General]" and line.startswith("ColorScheme="):
            return line.split("=", 1)[1].strip()
    return None


def shipped_colors(variant):
    (path,) = (package_dir(variant) / "contents" / "colors").glob("*.colors")
    return path


def bash_functions(script, *names):
    """Source just the named top-level functions out of a bash script."""
    text = script.read_text()
    bodies = []
    for name in names:
        m = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", text, re.M | re.S)
        assert m, f"{name}() not found in {script.name}"
        bodies.append(m.group(0))
    return "\n".join(bodies)


class GlobalThemeColorSchemeTest(unittest.TestCase):
    def test_global_theme_finds_its_own_color_scheme(self):
        # install.sh puts every variant's .colors in one color-schemes dir.
        installed = sorted(shipped_colors(v).name for v in VARIANTS)
        for v in VARIANTS:
            with self.subTest(variant=v):
                suffix = kde_scheme_suffix(defaults_color_scheme(v))
                found = [f for f in installed if f.endswith(suffix)]
                self.assertEqual(found, [shipped_colors(v).name])

    def test_color_scheme_id_is_the_file_name(self):
        # plasma-apply-colorscheme and System Settings → Colors name a scheme
        # by its file stem, and Global Theme apply writes the defaults value.
        for v in VARIANTS:
            with self.subTest(variant=v):
                colors = shipped_colors(v)
                conf = configparser.ConfigParser(interpolation=None)
                conf.optionxform = str
                conf.read(colors)
                self.assertEqual(conf["General"]["ColorScheme"], colors.stem)
                self.assertEqual(defaults_color_scheme(v), colors.stem)


class InstallScriptsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _bash(self, script):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env, cwd=REPO)

    def test_install_copies_and_applies_the_global_themes_scheme(self):
        funcs = bash_functions(REPO / "install.sh", "set_variant_names")
        for v in VARIANTS:
            with self.subTest(variant=v):
                out = self._bash(f'{funcs}\nset_variant_names {v}\n'
                                 'echo "$PKG_ID/contents/colors/$SCHEME_FILE"\necho "$COLOR_SCHEME"')
                src, applied = out.stdout.split("\n")[:2]
                self.assertEqual(REPO / src, shipped_colors(v))
                self.assertEqual(applied, defaults_color_scheme(v))

    def test_install_removes_the_hyphenated_scheme_an_older_install_left(self):
        # Left in place it shows a second, stale "Umber Slate" in System Settings → Colors.
        schemes = self.home / "color-schemes"
        schemes.mkdir()
        (schemes / "Umber-Slate.colors").write_text("[General]\nColorScheme=Umber-Slate\n")
        funcs = bash_functions(REPO / "install.sh", "set_variant_names", "install_variant_user_files")
        out = self._bash(
            'set -u; step() { :; }; ok() { :; }; note() { :; }\n'
            f'REPO_ROOT="{REPO}"; SCHEMES_DIR="{schemes}"; ICONS_DIR="{self.home}/icons"; LNF_DIR="{self.home}/lnf"; '
            f'SHELLS_DIR="{self.home}/shells"; KONSOLE_DIR="{self.home}/konsole"; APPS_DIR="{self.home}/apps"\n'
            'mkdir -p "$ICONS_DIR" "$LNF_DIR" "$SHELLS_DIR" "$KONSOLE_DIR" "$APPS_DIR"\n'
            f'{funcs}\ninstall_variant_user_files slate')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(sorted(p.name for p in schemes.iterdir()), [shipped_colors("slate").name])

    def test_apply_variant_applies_the_global_themes_scheme(self):
        # With the LnF package present but no .colors installed, the script
        # stops before touching the session and names the scheme it wanted.
        for v in VARIANTS:
            with self.subTest(variant=v):
                (self.home / ".local/share/plasma/look-and-feel" / package_dir(v).name).mkdir(parents=True, exist_ok=True)
                out = self._bash(f'"{REPO}/scripts/apply-variant.sh" {v}')
                self.assertEqual(out.returncode, 1)
                self.assertIn(f"ERROR: {defaults_color_scheme(v)}.colors not installed", out.stderr)


if __name__ == "__main__":
    unittest.main()

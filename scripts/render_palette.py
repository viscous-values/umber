#!/usr/bin/env python3
"""Render Umber's per-consumer palette files from palette.toml.

Templates live in scripts/templates/ and use {{ key }} placeholders:

    {{ hearth.0 }}              -> #242424   (hex with #, default)
    {{ hearth.0 | rgb }}        -> 36,36,36  (RGB decimal triple, no spaces)
    {{ hearth.0 | rgb_sp }}     -> 36, 36, 36 (with spaces — Chromium arrays)
    {{ hearth.0 | py }}         -> 0x24, 0x24, 0x24 (Python hex tuple body)
    {{ glow.1  | rgba 33 }}     -> #D4BC9133 (RGBA: alpha at end — VSCode/CSS)
    {{ glow.1  | argb FF }}     -> #FFD4BC91 (ARGB: alpha at start — Qt/QML)

Subcommands:
    render — write all consumer files from templates
    check  — diff generated vs on-disk; nonzero exit if any drift
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PALETTE_FILE = REPO / "palette.toml"
TEMPLATE_DIR = REPO / "scripts" / "templates"

OUTPUTS = {
    "Umber.colors.tmpl":           "com.tyler.umber/contents/colors/Umber.colors",
    "Umber.colorscheme.tmpl":      "konsole/Umber.colorscheme",
    "Umber-color-theme.json.tmpl": "umber-vscode/themes/Umber-color-theme.json",
    "firefox-manifest.json.tmpl":  "umber-firefox/manifest.json",
    "chromium-manifest.json.tmpl": "umber-chromium/manifest.json",
    "sddm-theme.conf.tmpl":        "umber-sddm/theme.conf",
    "Splash.qml.tmpl":             "com.tyler.umber/contents/splash/Splash.qml",
    "LockScreenUi.qml.tmpl":       "com.tyler.umber/contents/lockscreen/LockScreenUi.qml",
}


def hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def lookup(palette, key):
    val = palette
    for p in key.split("."):
        val = val[p]
    return val


def fmt_hex(h):
    return h


def fmt_rgb(h):
    r, g, b = hex_to_rgb(h)
    return f"{r},{g},{b}"


def fmt_rgb_sp(h):
    r, g, b = hex_to_rgb(h)
    return f"{r}, {g}, {b}"


def fmt_py(h):
    h_clean = h.lstrip("#").upper()
    return f"0x{h_clean[:2]}, 0x{h_clean[2:4]}, 0x{h_clean[4:6]}"


def fmt_argb(h, alpha):
    return "#" + alpha.upper() + h.lstrip("#").upper()


def fmt_rgba(h, alpha):
    return "#" + h.lstrip("#").upper() + alpha.upper()


FILTERS_NOARG = {
    "rgb":    fmt_rgb,
    "rgb_sp": fmt_rgb_sp,
    "py":     fmt_py,
}

FILTERS_ALPHA = {
    "argb": fmt_argb,
    "rgba": fmt_rgba,
}

TOKEN_RE = re.compile(
    r"\{\{\s*([\w.]+)\s*"
    r"(?:\|\s*(\w+)"
    r"(?:\s+([0-9A-Fa-f]{2}))?"
    r"\s*)?"
    r"\}\}"
)


def render_template(text, palette):
    def repl(m):
        key, filter_name, alpha = m.group(1), m.group(2), m.group(3)
        h = lookup(palette, key)
        if filter_name is None:
            return fmt_hex(h)
        if filter_name in FILTERS_NOARG:
            return FILTERS_NOARG[filter_name](h)
        if filter_name in FILTERS_ALPHA:
            if alpha is None:
                raise ValueError(
                    f"filter {filter_name!r} requires an alpha hex byte (key={key})"
                )
            return FILTERS_ALPHA[filter_name](h, alpha)
        raise ValueError(f"unknown filter: {filter_name!r}")
    return TOKEN_RE.sub(repl, text)


def load_palette():
    with open(PALETTE_FILE, "rb") as f:
        return tomllib.load(f)


def cmd_render(palette):
    for tmpl_name, out_rel in OUTPUTS.items():
        tmpl = (TEMPLATE_DIR / tmpl_name).read_text()
        rendered = render_template(tmpl, palette)
        out = REPO / out_rel
        out.write_text(rendered)
        print(f"  wrote {out_rel}")
    return 0


def cmd_check(palette):
    drift = []
    for tmpl_name, out_rel in OUTPUTS.items():
        tmpl = (TEMPLATE_DIR / tmpl_name).read_text()
        rendered = render_template(tmpl, palette)
        out = REPO / out_rel
        current = out.read_text() if out.exists() else ""
        if rendered != current:
            drift.append(out_rel)
    if drift:
        print("Out of sync with templates (run: python scripts/render_palette.py render):", file=sys.stderr)
        for d in drift:
            print(f"  - {d}", file=sys.stderr)
        return 1
    print("OK: all consumer files match templates.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["render", "check"])
    args = ap.parse_args()
    palette = load_palette()
    return cmd_render(palette) if args.cmd == "render" else cmd_check(palette)


if __name__ == "__main__":
    sys.exit(main())

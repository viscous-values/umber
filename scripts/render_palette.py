#!/usr/bin/env python3
"""Render Umber's per-consumer palette files from a palette TOML.

Templates live in scripts/templates/ and use {{ key }} placeholders:

    {{ hearth.0 }}              -> #242424   (hex with #, default)
    {{ hearth.0 | rgb }}        -> 36,36,36  (RGB decimal triple, no spaces)
    {{ hearth.0 | rgb_sp }}     -> 36, 36, 36 (with spaces — Chromium arrays)
    {{ hearth.0 | py }}         -> 0x24, 0x24, 0x24 (Python hex tuple body)
    {{ glow.1  | rgba 33 }}     -> #D4BC9133 (RGBA: alpha at end — VSCode/CSS)
    {{ glow.1  | argb FF }}     -> #FFD4BC91 (ARGB: alpha at start — Qt/QML)
    {{ var.name }}              -> "Umber" / "Umber Ash"
    {{ var.slug }}              -> "umber" / "umber-ash"
    {{ var.scheme }}            -> "Umber" / "Umber-Ash"  (filename-style)
    {{ var.id }}                -> "io.github.viscous-values.umber" / "io.github.viscous-values.umber-ash"
    {{ var.shell_id }}          -> "io.github.viscous-values.umber-shell" / "io.github.viscous-values.umber-ash-shell"
    {{ var.shell_name }}        -> "Umber Shell" / "Umber Ash Shell"
    {{ var.description }}       -> palette[meta][description]
    {{ var.wallpaper_description }} -> palette[meta][wallpaper_description]

Subcommands:
    render — write all consumer files for ONE palette/variant
    check  — diff generated vs on-disk for canonical + every palettes/*.toml;
             nonzero exit if any drift

The default palette is palette.toml (canonical warm Umber). Pass --palette
palettes/ash.toml to render a variant; the variant slug is derived from
the filename unless --variant is given explicitly.
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

import render_extension_icon

REPO = Path(__file__).resolve().parent.parent
PALETTE_FILE = REPO / "palette.toml"
PALETTES_DIR = REPO / "palettes"
TEMPLATE_DIR = REPO / "scripts" / "templates"


# --------------------------------------------------------------------------- #
# variant resolution                                                          #
# --------------------------------------------------------------------------- #

def derive_variant(palette_path):
    stem = Path(palette_path).stem
    return "umber" if stem == "palette" else stem


def compute_var(palette, variant):
    """Build the `var.*` namespace injected into the palette dict for templates."""
    is_canon = (variant == "umber")
    slug = "umber" if is_canon else f"umber-{variant}"
    name = "Umber" if is_canon else f"Umber {variant.title()}"
    scheme = "Umber" if is_canon else f"Umber-{variant.title()}"
    pkg_id = f"io.github.viscous-values.{slug}"
    shell_id = f"{pkg_id}-shell"
    shell_name = f"{name} Shell"

    meta = palette.get("meta", {})
    description = meta.get("description", f"{name} — Umber palette family.")
    wallpaper_description = meta.get(
        "wallpaper_description",
        "Procedurally generated palette-tinted gradient — see scripts/render_wallpaper.py.")

    return {
        "name":        name,
        "slug":        slug,
        "scheme":      scheme,
        "id":          pkg_id,
        "shell_id":    shell_id,
        "shell_name":  shell_name,
        "description": description,
        "wallpaper_description": wallpaper_description,
    }


def outputs_for(variant):
    """Map template filename -> output path (relative to repo) for ONE variant.

    Canonical variant ("umber") writes to today's existing layout.
    Variants suffix every package directory and color-scheme filename.
    """
    is_canon = (variant == "umber")
    slug = "umber" if is_canon else f"umber-{variant}"
    scheme = "Umber" if is_canon else f"Umber-{variant.title()}"
    pkg_id = f"io.github.viscous-values.{slug}"
    shell_dir = f"{slug}-shell"

    return {
        # Plasma colorscheme.
        "Umber.colors.tmpl":           f"{pkg_id}/contents/colors/{scheme}.colors",
        # Konsole colorscheme.
        "Umber.colorscheme.tmpl":      f"konsole/{scheme}.colorscheme",
        # VSCode theme JSON (single extension dir, multiple theme files).
        "Umber-color-theme.json.tmpl": f"umber-vscode/themes/{scheme}-color-theme.json",
        # Browser themes — per-variant directories at top level.
        "firefox-manifest.json.tmpl":  f"{slug}-firefox/manifest.json",
        "chromium-manifest.json.tmpl": f"{slug}-chromium/manifest.json",
        # SDDM — per-variant theme directory.
        "sddm-theme.conf.tmpl":        f"{slug}-sddm/theme.conf",
        "sddm-metadata.desktop.tmpl":  f"{slug}-sddm/metadata.desktop",
        # Plasma Splash + lockscreen QML.
        "Splash.qml.tmpl":             f"{pkg_id}/contents/splash/Splash.qml",
        "LockScreenUi.qml.tmpl":       f"{shell_dir}/contents/lockscreen/LockScreenUi.qml",
        # LookAndFeel + Plasma Shell metadata files.
        "lookandfeel-metadata.json.tmpl":           f"{pkg_id}/metadata.json",
        "lookandfeel-defaults.tmpl":                f"{pkg_id}/contents/defaults",
        "lookandfeel-wallpaper-metadata.json.tmpl": f"{pkg_id}/contents/wallpapers/{scheme}/metadata.json",
        "plasma-shell-metadata.json.tmpl":          f"{shell_dir}/metadata.json",
    }


# --------------------------------------------------------------------------- #
# template substitution                                                       #
# --------------------------------------------------------------------------- #

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


def load_palette(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def prepare_palette(path, variant):
    """Load + inject `var` namespace, ready to feed to render_template."""
    palette = load_palette(path)
    palette["var"] = compute_var(palette, variant)
    return palette


# --------------------------------------------------------------------------- #
# render / check                                                              #
# --------------------------------------------------------------------------- #

def icon_outputs_for(variant):
    """Return list of icon output paths the icon renderer will write for `variant`."""
    slug = "umber" if variant == "umber" else f"umber-{variant}"
    paths = []
    for ext_dir in (f"{slug}-firefox", f"{slug}-chromium"):
        for size in render_extension_icon.ICON_SIZES:
            paths.append(f"{ext_dir}/icons/icon-{size}.png")
    return paths


def render_one(palette, variant):
    outputs = outputs_for(variant)
    written = []
    for tmpl_name, out_rel in outputs.items():
        tmpl = (TEMPLATE_DIR / tmpl_name).read_text()
        rendered = render_template(tmpl, palette)
        out = REPO / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered)
        written.append(out_rel)
    written.extend(render_extension_icon.render_for_variant(palette, variant))
    return written


def check_one(palette, variant):
    """Return list of out_rel paths whose on-disk content drifted from templates."""
    drift = []
    outputs = outputs_for(variant)
    for tmpl_name, out_rel in outputs.items():
        tmpl = (TEMPLATE_DIR / tmpl_name).read_text()
        rendered = render_template(tmpl, palette)
        out = REPO / out_rel
        current = out.read_text() if out.exists() else ""
        if rendered != current:
            drift.append(out_rel)
    # Icons are binary; we only check existence (full pixel-diff on every
    # check would be slow and would flag innocuous PIL/encoder changes).
    for icon_rel in icon_outputs_for(variant):
        if not (REPO / icon_rel).exists():
            drift.append(icon_rel)
    return drift


def cmd_render(args):
    palette_path = args.palette or PALETTE_FILE
    variant = args.variant or derive_variant(palette_path)
    palette = prepare_palette(palette_path, variant)
    written = render_one(palette, variant)
    print(f"[{variant}] wrote {len(written)} files from {palette_path.name}:")
    for path in written:
        print(f"  {path}")
    return 0


def cmd_check(args):
    """Validate canonical + every palettes/*.toml. Nonzero exit on any drift."""
    targets = [(PALETTE_FILE, "umber")]
    if PALETTES_DIR.is_dir():
        for p in sorted(PALETTES_DIR.glob("*.toml")):
            targets.append((p, derive_variant(p)))

    any_drift = False
    for palette_path, variant in targets:
        palette = prepare_palette(palette_path, variant)
        drift = check_one(palette, variant)
        if drift:
            any_drift = True
            print(f"[{variant}] OUT OF SYNC ({palette_path.name}):", file=sys.stderr)
            for d in drift:
                print(f"  - {d}", file=sys.stderr)
        else:
            print(f"[{variant}] OK ({palette_path.name})")

    if any_drift:
        print("\nRun: python scripts/render_palette.py render "
              "[--palette palettes/<name>.toml] for each drifting variant.",
              file=sys.stderr)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    render_p = sub.add_parser("render", help="render all consumer files for one palette")
    render_p.add_argument("--palette", type=Path,
                          help="palette TOML (default: palette.toml)")
    render_p.add_argument("--variant", type=str,
                          help="variant slug (default: derived from --palette filename)")
    render_p.set_defaults(func=cmd_render)

    check_p = sub.add_parser("check", help="validate canonical + all palettes/*.toml")
    check_p.set_defaults(func=cmd_check)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

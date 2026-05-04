#!/usr/bin/env python3
"""Render per-variant browser-extension icons from a palette TOML.

Output: PNG icons at 48/96/128 px under <slug>-firefox/icons/ and
<slug>-chromium/icons/. The icon is a palette-driven mark — dark hearth.0
field with a centered hearth.1 "card" tile, an amber spark accent line
across its top edge, and a glow.1 cream stripe across its bottom third.
That mirrors the Firefox/Chromium tab visual idiom (tab_line + tab_text)
in miniature, so the icon reads as "an Umber-palette-themed browser tab"
no matter which variant.

Called by render_palette.py during `render`. Standalone invocation:
    python scripts/render_extension_icon.py --palette palettes/tide.toml
"""

import argparse
import tomllib
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parent.parent
PALETTE_FILE = REPO / "palette.toml"
PALETTES_DIR = REPO / "palettes"

ICON_SIZES = (48, 96, 128)


def hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def derive_slug(variant):
    return "umber" if variant == "umber" else f"umber-{variant}"


def derive_variant(palette_path):
    stem = Path(palette_path).stem
    return "umber" if stem == "palette" else stem


def render_icon(palette, size):
    """Return a PIL Image of the variant's icon at `size` px square."""
    hearth_0 = hex_to_rgb(palette["hearth"]["0"])
    hearth_1 = hex_to_rgb(palette["hearth"]["1"])
    hearth_2 = hex_to_rgb(palette["hearth"]["2"])
    glow_1 = hex_to_rgb(palette["glow"]["1"])
    spark_amber = hex_to_rgb(palette["spark"]["amber"])

    # Render at 4x then downscale for crisp anti-aliased edges.
    scale = 4
    s = size * scale
    pad = s // 8
    radius = s // 10
    card_box = (pad, pad, s - pad, s - pad)
    inner_h = s - 2 * pad

    # Card content layer (rectangular; card mask handles the rounding).
    # Default fill is hearth.1 (toolbar-ish surface). Bottom 22% gets the
    # glow.1 cream stripe — the Umber-family foreground signature.
    card_content = Image.new("RGBA", (s, s), hearth_1 + (255,))
    cdraw = ImageDraw.Draw(card_content)
    stripe_top = pad + inner_h * 78 // 100
    cdraw.rectangle((0, stripe_top, s, s), fill=glow_1 + (255,))

    # Top accent line — amber spark, mirroring tab_line in the Firefox theme.
    accent_h = max(2 * scale, s // 24)
    cdraw.rectangle((0, pad, s, pad + accent_h), fill=spark_amber + (255,))

    # Two faint "text-line" hints in hearth.2, between the accent line and
    # the cream stripe. Cues that this is a toolbar surface, not flat color.
    hint_h = max(scale, s // 48)
    hint_w_long = inner_h * 5 // 8
    hint_w_short = inner_h * 3 // 8
    hint_x = pad + (inner_h - hint_w_long) // 2
    hint_band_top = pad + accent_h + inner_h * 22 // 100
    cdraw.rectangle(
        (hint_x, hint_band_top, hint_x + hint_w_long, hint_band_top + hint_h),
        fill=hearth_2 + (255,),
    )
    cdraw.rectangle(
        (hint_x, hint_band_top + hint_h * 4, hint_x + hint_w_short, hint_band_top + hint_h * 5),
        fill=hearth_2 + (255,),
    )

    # Card mask — rounded rectangle, full opacity inside, transparent outside.
    card_mask = Image.new("L", (s, s), 0)
    mdraw = ImageDraw.Draw(card_mask)
    mdraw.rounded_rectangle(card_box, radius=radius, fill=255)

    # Composite: hearth.0 background, then card_content clipped to card_mask.
    img = Image.new("RGBA", (s, s), hearth_0 + (255,))
    img = Image.composite(card_content, img, card_mask)

    return img.resize((size, size), Image.LANCZOS)


def render_for_variant(palette, variant):
    slug = derive_slug(variant)
    written = []
    for ext_dir in (f"{slug}-firefox", f"{slug}-chromium"):
        icons_dir = REPO / ext_dir / "icons"
        icons_dir.mkdir(parents=True, exist_ok=True)
        for size in ICON_SIZES:
            out = icons_dir / f"icon-{size}.png"
            render_icon(palette, size).save(out, "PNG", optimize=True)
            written.append(str(out.relative_to(REPO)))
    return written


def cmd_render(args):
    palette_path = args.palette or PALETTE_FILE
    variant = args.variant or derive_variant(palette_path)
    with open(palette_path, "rb") as f:
        palette = tomllib.load(f)
    written = render_for_variant(palette, variant)
    print(f"[{variant}] wrote {len(written)} icon files:")
    for path in written:
        print(f"  {path}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--palette", type=Path, default=None,
                        help="palette TOML (default: palette.toml; pass palettes/<v>.toml for variants)")
    parser.add_argument("--variant", default=None,
                        help="variant slug override (default: derived from palette filename stem)")
    parser.set_defaults(func=cmd_render)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

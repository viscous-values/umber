"""Render a palette-tinted wallpaper: deep-to-faint-glow horizon gradient with
subtle grain. Anchors derive from the supplied palette so canonical and each
variant produce their own family-tinted wallpaper.

Default palette is palette.toml (canonical). Pass --palette palettes/ash.toml
(etc.) to render a variant wallpaper. The full output is committed to the
LookAndFeel package; only the author re-runs this on palette changes."""

import argparse
import random
import tomllib
from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parent.parent

HORIZON = 0.72       # fraction of height where the glow peaks
GLOW_WIDTH = 0.18    # gaussian-ish width of the horizon band
GRAIN_AMPLITUDE = 4  # +/- per-pixel luminance jitter


def _hex_rgb(h):
    h = h.lstrip("#")
    return (int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def palette_anchors(palette):
    """Return (deep, elev, base, band) anchors derived from the palette.

    deep — top of frame  (hearth.0)
    elev — at horizon    (hearth.2)
    base — below horizon (hearth.1)
    band — horizon-glow tone (glow.2 darkened toward hearth.0 by ~55%)
    """
    deep = _hex_rgb(palette["hearth"]["0"])
    elev = _hex_rgb(palette["hearth"]["2"])
    base = _hex_rgb(palette["hearth"]["1"])
    glow_emph = _hex_rgb(palette["glow"]["2"])
    band = lerp(deep, glow_emph, 0.45)
    return deep, elev, base, band


def horizon_weight(y_frac):
    d = abs(y_frac - HORIZON) / GLOW_WIDTH
    if d >= 1.0:
        return 0.0
    return (1 - d * d) ** 2


def base_color(y_frac, deep, elev, base):
    if y_frac < HORIZON:
        return lerp(deep, elev, y_frac / HORIZON)
    return lerp(elev, base, (y_frac - HORIZON) / (1.0 - HORIZON))


def render(width: int, height: int, palette, seed: int = 1729) -> Image.Image:
    deep, elev, base, band = palette_anchors(palette)
    rng = random.Random(seed)
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        y_frac = y / (height - 1)
        bc = base_color(y_frac, deep, elev, base)
        glow_t = horizon_weight(y_frac)
        row = lerp(bc, band, glow_t * 0.55)
        for x in range(width):
            jitter = rng.randint(-GRAIN_AMPLITUDE, GRAIN_AMPLITUDE)
            r = max(0, min(255, row[0] + jitter))
            g = max(0, min(255, row[1] + jitter))
            b = max(0, min(255, row[2] + jitter))
            px[x, y] = (r, g, b)
    return img


def load_palette(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--palette", type=Path, default=REPO / "palette.toml",
                    help="palette TOML providing wallpaper anchors")
    ap.add_argument("--width", type=int, default=3840)
    ap.add_argument("--height", type=int, default=2160)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    palette = load_palette(args.palette)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    img = render(args.width, args.height, palette)
    img.save(args.out, optimize=True)
    print(f"Wrote {args.out} ({args.width}x{args.height}) from {args.palette.name}")


if __name__ == "__main__":
    main()

"""Render the Umber wallpaper: charcoal-to-faint-peach horizon gradient with
subtle grain. Output is committed to the LnF package; only the author re-runs
this on palette changes."""

import argparse
import random
from pathlib import Path
from PIL import Image

# Palette anchors (from README). Hearth.deep at the top fading down through
# hearth.elev with a faint peach-glow horizon roughly 70% down the frame.
HEARTH_DEEP = (0x24, 0x24, 0x24)   # #242424
HEARTH_ELEV = (0x33, 0x33, 0x33)   # #333333
GLOW_PEACH  = (0x6E, 0x55, 0x40)   # damped glow toward horizon
HEARTH_BASE = (0x2B, 0x2B, 0x2B)   # below horizon settles back to hearth

HORIZON = 0.72   # fraction of height where the glow peaks
GLOW_WIDTH = 0.18  # gaussian-ish width of the horizon band
GRAIN_AMPLITUDE = 4  # +/- per-pixel luminance jitter


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def horizon_weight(y_frac):
    # Smooth band peaking at HORIZON.
    d = abs(y_frac - HORIZON) / GLOW_WIDTH
    if d >= 1.0:
        return 0.0
    # Smooth-step falloff (1 - d^2)^2.
    return (1 - d * d) ** 2


def base_color(y_frac):
    if y_frac < HORIZON:
        # Top: hearth.deep -> hearth.elev as we approach horizon.
        t = y_frac / HORIZON
        return lerp(HEARTH_DEEP, HEARTH_ELEV, t)
    else:
        # Below horizon: hearth.elev -> hearth.base.
        t = (y_frac - HORIZON) / (1.0 - HORIZON)
        return lerp(HEARTH_ELEV, HEARTH_BASE, t)


def render(width: int, height: int, seed: int = 1729) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        y_frac = y / (height - 1)
        base = base_color(y_frac)
        glow_t = horizon_weight(y_frac)
        row = lerp(base, GLOW_PEACH, glow_t * 0.55)  # cap the peach influence
        for x in range(width):
            jitter = rng.randint(-GRAIN_AMPLITUDE, GRAIN_AMPLITUDE)
            r = max(0, min(255, row[0] + jitter))
            g = max(0, min(255, row[1] + jitter))
            b = max(0, min(255, row[2] + jitter))
            px[x, y] = (r, g, b)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=3840)
    ap.add_argument("--height", type=int, default=2160)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    img = render(args.width, args.height)
    img.save(args.out, optimize=True)
    print(f"Wrote {args.out} ({args.width}x{args.height})")


if __name__ == "__main__":
    main()

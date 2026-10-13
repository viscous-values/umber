"""Recolor the installed Nordic-cursors into one Umber cursor theme per variant.

Nordic-cursors is drawn with a handful of Nord palette colors, so each one maps
onto a job in the variant's palette:

    body     #3B4252  -> ground hue (hearth.2), Nord's lightness kept
    outline  #D8DEE9  -> text hue (role.fg), Nord's lightness kept
    teal     #8FBCBB  -> signature accent (wait / progress spinners); the
                         other Nord blues follow it, keeping their offsets
    red / orange / green -> role.error / spark.orange / role.success

Keeping Nord's lightness on the body and outline keeps the cursor's contrast
against dark and light windows alike; only hue and chroma change. Pixels on
the anti-aliased ramp between body and outline stay on that ramp; every other
pixel moves by a distance-weighted blend of the nearby anchors' shifts.

XCursor stores pixels as 32-bit ARGB little-endian (= BGRA byte order) with
premultiplied alpha. We un-premultiply, recolor, then re-premultiply.

    python3 scripts/recolor_nordic_inplace.py --palette palettes/ash.toml
    (scripts/build-cursor.sh runs it for every shipped palette)
"""

import argparse
import math
import os
import shutil
import struct
import sys
from functools import lru_cache
from pathlib import Path

import palette_lib
import render_palette
from palette_audit import _to_srgb8, oklab

SRC = Path(os.environ.get("UMBER_CURSOR_SRC", Path.home() / ".icons" / "Nordic-cursors"))
OUT_DIR = palette_lib.REPO / "cursors"

IMG_TYPE = 0xfffd0002

# The Nord colors Nordic-cursors is drawn with.
NORD = {
    "body":    "#3B4252",  # nord1
    "outline": "#D8DEE9",  # nord4
    "teal":    "#8FBCBB",  # nord7: wait / progress spinners
    "frost":   "#88C0D0",  # nord8: context-menu
    "blue":    "#81A1C1",  # nord9: help badge, resize arrows
    "red":     "#BF616A",  # nord11: not-allowed, pirate
    "orange":  "#D08770",  # nord12
    "green":   "#A3BE8C",  # nord14: copy, alias
}
RAMP_TOLERANCE = 0.02  # OKLab a/b distance from the body→outline line that still counts as an edge blend
SIGMA = 0.05           # how far an anchor's shift reaches


def oklab_to_rgb(L, a, b):
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
           -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
           -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
    return tuple(int(round(_to_srgb8(c))) for c in lin)


def anchors(pal):
    """(Nord color, Umber target) pairs in OKLab."""
    role = pal["role"]

    def keep_value(src, hue_from):
        return (oklab(src)[0], *oklab(hue_from)[1:])

    def follow_teal(src):
        L, a, b = oklab(role["accent"])
        return (L + oklab(src)[0] - oklab(NORD["teal"])[0], a, b)

    return [
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),  # drop shadow stays black
        (oklab(NORD["body"]), keep_value(NORD["body"], pal["hearth"]["2"])),
        (oklab(NORD["outline"]), keep_value(NORD["outline"], role["fg"])),
        (oklab(NORD["teal"]), oklab(role["accent"])),
        (oklab(NORD["frost"]), follow_teal(NORD["frost"])),
        (oklab(NORD["blue"]), follow_teal(NORD["blue"])),
        (oklab(NORD["red"]), oklab(role["error"])),
        (oklab(NORD["orange"]), oklab(pal["spark"]["orange"])),
        (oklab(NORD["green"]), oklab(role["success"])),
    ]


def mapper(pal):
    """Return remap((r, g, b)) -> (r, g, b) for straight-alpha pixels."""
    pairs = anchors(pal)
    (sL, sa0, sb0), (tL, sa1, sb1) = oklab(NORD["body"]), oklab(NORD["outline"])
    (_, ta0, tb0), (_, ta1, tb1) = pairs[1][1], pairs[2][1]

    def on_ramp(L, a, b):
        t = max(0.0, min(1.0, (L - sL) / (tL - sL)))
        ra, rb = sa0 + (sa1 - sa0) * t, sb0 + (sb1 - sb0) * t
        if math.hypot(a - ra, b - rb) > RAMP_TOLERANCE:
            return None
        return (L, ta0 + (ta1 - ta0) * t + (a - ra), tb0 + (tb1 - tb0) * t + (b - rb))

    def shifted(lab):
        # Gaussian reach, sharpened by 1/d² so a pixel exactly on an anchor
        # lands exactly on its target.
        weights = []
        for src, _ in pairs:
            d2 = sum((x - y) ** 2 for x, y in zip(lab, src))
            weights.append(math.exp(-d2 / SIGMA ** 2) / (d2 + 1e-9))
        total = sum(weights)
        if total < 1e-12:
            nearest = min(range(len(pairs)), key=lambda i: math.dist(lab, pairs[i][0]))
            weights, total = [float(i == nearest) for i in range(len(pairs))], 1.0
        return tuple(lab[c] + sum(w * (t[c] - s[c]) for w, (s, t) in zip(weights, pairs)) / total
                     for c in range(3))

    @lru_cache(maxsize=None)
    def remap(rgb):
        lab = oklab("#%02X%02X%02X" % rgb)
        return oklab_to_rgb(*(on_ramp(*lab) or shifted(lab)))

    return remap


def remap_pixel(r, g, b, a, remap):
    """Recolor one premultiplied pixel."""
    if a == 0:
        return (0, 0, 0, 0)
    if a < 255:
        r, g, b = (min(255, c * 255 // a) for c in (r, g, b))
    nr, ng, nb = remap((r, g, b))
    if a < 255:
        nr, ng, nb = (c * a // 255 for c in (nr, ng, nb))
    return (nr, ng, nb, a)


def recolor_xcursor(path, remap):
    """Recolor an xcursor binary in place. Returns True on success."""
    blob = bytearray(path.read_bytes())
    if blob[:4] != b"Xcur":
        return False
    # XCursor file header: magic "Xcur", header size (always 16), version,
    # ntoc. ntoc is at offset 12, not 8.
    file_hdr_size = struct.unpack_from("<I", blob, 4)[0]
    ntoc = struct.unpack_from("<I", blob, 12)[0]
    for i in range(ntoc):
        type_, _sub, pos = struct.unpack_from("<III", blob, file_hdr_size + i * 12)
        if type_ != IMG_TYPE:
            continue
        chunk_hdr, _ct, _cs, _cv, w, h, _xh, _yh, _dly = struct.unpack_from("<IIIIIIIII", blob, pos)
        offset = pos + chunk_hdr
        for px in range(w * h):
            o = offset + px * 4
            b, g, r, a = blob[o], blob[o + 1], blob[o + 2], blob[o + 3]
            nr, ng, nb, na = remap_pixel(r, g, b, a, remap)
            blob[o], blob[o + 1], blob[o + 2], blob[o + 3] = nb, ng, nr, na
    path.write_bytes(bytes(blob))
    return True


def build(src, dst, pal, name, palette_path):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)  # keeps the alias symlinks as links
    (dst / "index.theme").write_text(
        "[Icon Theme]\n"
        f"Name={name}\n"
        f"Comment={name} — Nordic-cursors recolored from {palette_path}\n"
        "Inherits=hicolor\n"
    )
    remap = mapper(pal)
    cursors = dst / "cursors"
    real = [p for p in sorted(cursors.iterdir()) if p.is_file() and not p.is_symlink()]
    ok = sum(1 for p in real if recolor_xcursor(p, remap))
    links = sum(1 for p in cursors.iterdir() if p.is_symlink())
    print(f"{name}: recolored {ok}/{len(real)} cursors (+{links} alias links) -> {dst}")
    return ok == len(real)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--palette", type=Path, default=palette_lib.PALETTE_FILE)
    ap.add_argument("--src", type=Path, default=SRC, help="installed Nordic-cursors (default %(default)s)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--force", action="store_true", help="build from a draft or archived palette anyway")
    args = ap.parse_args(argv)
    if palette_lib.is_unshipped(args.palette) and not args.force:
        sys.exit(f"{args.palette} is a draft or archived palette; its cursor would overwrite the shipped "
                 "variant of the same name. Pass --force to build it anyway.")
    if not (args.src / "cursors").is_dir():
        sys.exit(f"Nordic-cursors not found at {args.src} (set UMBER_CURSOR_SRC or pass --src).")
    variant = palette_lib.variant_slug(args.palette)
    pal = palette_lib.prepare(args.palette)
    name = render_palette.compute_var(pal, variant)["name"]
    dst = args.out_dir / render_palette.cursor_theme(variant)
    try:
        shown = args.palette.resolve().relative_to(palette_lib.REPO)
    except ValueError:
        shown = args.palette
    return 0 if build(args.src, dst, pal, name, shown) else 1


if __name__ == "__main__":
    sys.exit(main())

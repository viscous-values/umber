"""Copy ~/.icons/Nordic-cursors to a Umber-cursor theme, then walk every
xcursor binary inside it and remap pixel colors from the Nord palette to the
Umber palette.

XCursor stores pixels as 32-bit ARGB little-endian (= BGRA byte order) with
*premultiplied* alpha. We un-premultiply, recolor, then re-premultiply.

Recolor strategy:
- Transparent / near-transparent pixels: leave alone.
- Saturated colored pixels (emblems like the help blue, copy green, context
  red): classify by hue and snap to the matching Umber spark/mist palette
  while preserving the original lightness/alpha.
- Low-saturation pixels (the bulk of the cursor — dark body + bright border +
  anti-aliased edges): linearly interpolate luminance between Nord polar
  night and Nord snow storm onto Umber hearth.deep ↔ Umber glow.peach.
"""

import os
import shutil
import struct
from pathlib import Path

SRC = Path(os.environ.get("HUSH_CURSOR_SRC", Path.home() / ".icons" / "Nordic-cursors"))
DST = Path(os.environ.get("HUSH_CURSOR_DST", Path.home() / ".local" / "share" / "icons" / "Umber-cursor"))

IMG_TYPE = 0xfffd0002

# Endpoints for luminance remap (low-saturation pixels).
HUSH_DARK  = (0x24, 0x24, 0x24)   # hearth.deep — body
HUSH_LIGHT = (0xE1, 0xCD, 0xA5)   # glow.peach  — border / highlight

# Hue buckets for saturated pixels. Hues in [0, 360).
SATURATED_TARGETS = [
    # (low_h, high_h, hush_rgb)
    ((345, 360), (0x88, 0xA6, 0xC5)),    # wraparound red→ unused but reserved
    ((0,   25),  (0xE0, 0x6C, 0x75)),    # red          -> spark.red
    ((25,  50),  (0xD1, 0x9A, 0x66)),    # orange       -> spark.orange
    ((50,  75),  (0xE5, 0xC0, 0x7B)),    # yellow/amber -> spark.amber
    ((75, 165),  (0x98, 0xC3, 0x79)),    # green        -> spark.green
    ((165, 200), (0xE5, 0xC0, 0x7B)),    # nord teal/cyan -> Umber spark.amber (accent slot)
    ((200, 260), (0x88, 0xA6, 0xC5)),    # blue         -> mist.blue
    ((260, 345), (0xC5, 0x86, 0xB0)),    # purple       -> spark.violet
]
SAT_THRESHOLD = 0.18  # saturation below this is treated as monochrome


def rgb_to_hsv(r, g, b):
    r_, g_, b_ = r/255.0, g/255.0, b/255.0
    mx = max(r_, g_, b_); mn = min(r_, g_, b_)
    d = mx - mn
    if d == 0:
        h = 0
    elif mx == r_:
        h = (60 * ((g_ - b_) / d) + 360) % 360
    elif mx == g_:
        h = 60 * ((b_ - r_) / d) + 120
    else:
        h = 60 * ((r_ - g_) / d) + 240
    s = 0 if mx == 0 else d / mx
    v = mx
    return h, s, v


def lerp(a, b, t):
    return int(round(a + (b - a) * t))


def remap_pixel(r, g, b, a):
    if a == 0:
        return (0, 0, 0, 0)
    # Un-premultiply.
    if a < 255:
        ur = min(255, r * 255 // a)
        ug = min(255, g * 255 // a)
        ub = min(255, b * 255 // a)
    else:
        ur, ug, ub = r, g, b

    h, s, _v = rgb_to_hsv(ur, ug, ub)
    if s >= SAT_THRESHOLD:
        # Saturated: snap to Umber palette by hue, preserve original lightness.
        for (lo, hi), (tr, tg, tb) in SATURATED_TARGETS:
            if lo <= h < hi:
                # Preserve relative lightness — mix the target with original
                # luminance so anti-aliased edges still feather correctly.
                lum = (ur + ug + ub) / 3 / 255.0  # 0..1
                # Blend target * lum + black * (1 - lum) is too dark for
                # bright emblems. Use a softer rule: lerp from Umber hearth
                # to target, with t = lum.
                nr = lerp(HUSH_DARK[0], tr, lum)
                ng = lerp(HUSH_DARK[1], tg, lum)
                nb = lerp(HUSH_DARK[2], tb, lum)
                break
        else:
            nr, ng, nb = ur, ug, ub
    else:
        # Monochrome: luminance interpolation onto Umber hearth ↔ glow.peach.
        lum = (ur + ug + ub) / 3 / 255.0
        nr = lerp(HUSH_DARK[0], HUSH_LIGHT[0], lum)
        ng = lerp(HUSH_DARK[1], HUSH_LIGHT[1], lum)
        nb = lerp(HUSH_DARK[2], HUSH_LIGHT[2], lum)

    # Re-premultiply.
    if a < 255:
        nr = nr * a // 255
        ng = ng * a // 255
        nb = nb * a // 255
    return (nr, ng, nb, a)


def recolor_xcursor(path: Path) -> bool:
    """Recolor an xcursor binary in place. Returns True on success."""
    blob = bytearray(path.read_bytes())
    if blob[:4] != b"Xcur":
        return False
    # XCursor file header layout:
    #   0..3  magic "Xcur"
    #   4..7  file header size (uint32, always 16)
    #   8..11 version
    #   12..15 ntoc
    file_hdr_size = struct.unpack_from("<I", blob, 4)[0]
    ntoc = struct.unpack_from("<I", blob, 12)[0]
    for i in range(ntoc):
        type_, _sub, pos = struct.unpack_from("<III", blob, file_hdr_size + i * 12)
        if type_ != IMG_TYPE:
            continue
        chunk_hdr, _ct, _cs, _cv, w, h, _xh, _yh, _dly = struct.unpack_from(
            "<IIIIIIIII", blob, pos)
        offset = pos + chunk_hdr
        for px in range(w * h):
            o = offset + px * 4
            b, g, r, a = blob[o], blob[o + 1], blob[o + 2], blob[o + 3]
            nr, ng, nb, na = remap_pixel(r, g, b, a)
            blob[o]     = nb
            blob[o + 1] = ng
            blob[o + 2] = nr
            blob[o + 3] = na
    path.write_bytes(bytes(blob))
    return True


def main():
    if DST.exists():
        shutil.rmtree(DST)
    # Preserve symlinks (copytree by default copies symlinks as symlinks).
    shutil.copytree(SRC, DST, symlinks=True)

    # Update theme metadata.
    idx = DST / "index.theme"
    idx.write_text(
        "[Icon Theme]\n"
        "Name=Umber\n"
        "Comment=Umber — peach-on-charcoal recolor of Nordic-cursors\n"
        "Inherits=hicolor\n"
    )

    cursors_dir = DST / "cursors"
    real_files = [p for p in cursors_dir.iterdir() if p.is_file() and not p.is_symlink()]
    print(f"{len(real_files)} real cursor binaries to recolor "
          f"(plus {sum(1 for p in cursors_dir.iterdir() if p.is_symlink())} symlinks left as-is)")
    ok = 0
    for p in real_files:
        try:
            if recolor_xcursor(p):
                ok += 1
        except Exception as e:
            print(f"  FAIL {p.name}: {e}")
    print(f"Recolored {ok}/{len(real_files)} cursors. Installed to {DST}")


if __name__ == "__main__":
    main()

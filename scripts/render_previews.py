"""Render synthetic Plasma-desktop preview images for the Hush LnF package.

Outputs:
- contents/previews/preview.png            — small thumbnail
- contents/previews/fullscreenpreview.jpg  — large preview

The render is symbolic, not a real screenshot: a desktop with the Hush
wallpaper, a panel, and a faux window/titlebar/buttons that show the active
[WM], [Colors:Window], and [Colors:View] groups so a viewer in System Settings
can see the palette at a glance.
"""

import argparse
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Palette
HEARTH = {
    "deep":  (0x24, 0x24, 0x24),
    "base":  (0x2B, 0x2B, 0x2B),
    "elev":  (0x33, 0x33, 0x33),
    "high":  (0x44, 0x44, 0x44),
}
GLOW = {
    "dim":   (0xA8, 0x99, 0x86),
    "warm":  (0xD4, 0xBC, 0x91),
    "peach": (0xE1, 0xCD, 0xA5),
    "near":  (0xE1, 0xE1, 0xE1),
}
MIST = {
    "teal":  (0x7A, 0xA8, 0xAC),
    "blue":  (0x88, 0xA6, 0xC5),
    "sky":   (0xA8, 0xBD, 0xD6),
}
SPARK = {
    "red":    (0xE0, 0x6C, 0x75),
    "orange": (0xD1, 0x9A, 0x66),
    "amber":  (0xE5, 0xC0, 0x7B),
    "green":  (0x98, 0xC3, 0x79),
    "violet": (0xC5, 0x86, 0xB0),
}

# Wallpaper-ish backdrop (matches render_wallpaper.py rules in spirit).
HORIZON = 0.72
GLOW_WIDTH = 0.18
GRAIN = 3


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def horizon_weight(y_frac):
    d = abs(y_frac - HORIZON) / GLOW_WIDTH
    if d >= 1.0:
        return 0.0
    return (1 - d * d) ** 2


def base_color(y_frac):
    if y_frac < HORIZON:
        return lerp(HEARTH["deep"], HEARTH["elev"], y_frac / HORIZON)
    return lerp(HEARTH["elev"], HEARTH["base"], (y_frac - HORIZON) / (1.0 - HORIZON))


def render_wallpaper(width, height, seed=1729):
    rng = random.Random(seed)
    img = Image.new("RGB", (width, height))
    px = img.load()
    GLOW_PEACH_WP = (0x6E, 0x55, 0x40)
    for y in range(height):
        y_frac = y / (height - 1)
        base = base_color(y_frac)
        glow_t = horizon_weight(y_frac) * 0.55
        row = lerp(base, GLOW_PEACH_WP, glow_t)
        for x in range(width):
            j = rng.randint(-GRAIN, GRAIN)
            px[x, y] = (
                max(0, min(255, row[0] + j)),
                max(0, min(255, row[1] + j)),
                max(0, min(255, row[2] + j)),
            )
    return img


def load_font(size):
    candidates = [
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def draw_panel(draw, w, h, font_small):
    panel_h = max(36, h // 22)
    y0 = h - panel_h
    draw.rectangle([0, y0, w, h], fill=HEARTH["deep"])
    # Thin separator
    draw.line([0, y0, w, y0], fill=HEARTH["high"])
    # Application launcher dot
    pad = panel_h // 4
    draw.rectangle([pad, y0 + pad, pad + panel_h - 2 * pad, h - pad],
                   fill=GLOW["peach"])
    # Faux taskbar items
    x = pad * 3 + (panel_h - 2 * pad)
    for i, c in enumerate([HEARTH["high"], HEARTH["high"], HEARTH["high"]]):
        draw.rectangle([x, y0 + pad, x + panel_h * 2, h - pad], fill=c)
        x += panel_h * 2 + pad
    # Clock on the right
    clock = "20:42"
    bbox = draw.textbbox((0, 0), clock, font=font_small)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((w - tw - pad * 3, y0 + (panel_h - th) // 2 - 2),
              clock, font=font_small, fill=GLOW["warm"])


def draw_window(img, x, y, w, h, font_title, font_body):
    draw = ImageDraw.Draw(img, "RGBA")
    titlebar_h = max(28, h // 14)
    radius = 8

    # Drop shadow (soft, 4 layers).
    for i in range(4):
        alpha = 36 - i * 8
        draw.rounded_rectangle([x - i * 2, y - i, x + w + i * 2, y + h + i * 3],
                               radius=radius + i, fill=(0, 0, 0, alpha))
    # Window body (View bg).
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                           fill=HEARTH["deep"])
    # Titlebar (WM activeBackground).
    draw.rounded_rectangle([x, y, x + w, y + titlebar_h], radius=radius,
                           fill=HEARTH["elev"])
    draw.rectangle([x, y + titlebar_h - radius, x + w, y + titlebar_h],
                   fill=HEARTH["elev"])
    draw.line([x, y + titlebar_h, x + w, y + titlebar_h], fill=HEARTH["high"])

    # Title text (WM activeForeground).
    title = "Hush"
    tb = draw.textbbox((0, 0), title, font=font_title)
    draw.text((x + 16, y + (titlebar_h - (tb[3] - tb[1])) // 2 - 2),
              title, font=font_title, fill=GLOW["warm"])

    # Window control buttons.
    btn_r = max(6, titlebar_h // 4)
    by = y + titlebar_h // 2
    bx = x + w - 18
    for color in (SPARK["red"], SPARK["amber"], SPARK["green"]):
        draw.ellipse([bx - btn_r, by - btn_r, bx + btn_r, by + btn_r],
                     fill=color)
        bx -= btn_r * 2 + 8

    # Sidebar (alternate Window bg).
    side_w = w // 4
    draw.rectangle([x, y + titlebar_h, x + side_w, y + h - radius],
                   fill=HEARTH["base"])
    # Sidebar items
    item_h = max(22, h // 18)
    iy = y + titlebar_h + 14
    for label, accent in [
        ("Hearth", GLOW["warm"]),
        ("Glow",   GLOW["peach"]),
        ("Mist",   MIST["blue"]),
        ("Spark",  SPARK["amber"]),
    ]:
        # Hover/selected effect on Glow row
        if label == "Glow":
            draw.rounded_rectangle(
                [x + 8, iy - 4, x + side_w - 8, iy + item_h - 4],
                radius=4, fill=GLOW["warm"])
            text_color = HEARTH["deep"]
        else:
            text_color = GLOW["dim"]
        # Color swatch
        sw = item_h - 8
        draw.rectangle([x + 16, iy + (item_h - sw) // 2 - 2,
                        x + 16 + sw, iy + (item_h + sw) // 2 - 2],
                       fill=accent, outline=HEARTH["high"])
        draw.text((x + 16 + sw + 10, iy - 2), label,
                  font=font_body, fill=text_color)
        iy += item_h + 6

    # Main content area.
    cx = x + side_w + 24
    cy = y + titlebar_h + 22
    # Headline
    headline = "Quiet warm-on-charcoal"
    draw.text((cx, cy), headline, font=font_title, fill=GLOW["peach"])
    cy += font_title.size + 8
    # Body lines
    body_lines = [
        "16 colors. 4 tiers.",
        "Hearth surfaces, glow foregrounds,",
        "mist counterweights, spark accents.",
    ]
    for line in body_lines:
        draw.text((cx, cy), line, font=font_body, fill=GLOW["dim"])
        cy += font_body.size + 4
    cy += 10

    # Code/terminal block
    block_w = w - side_w - 48
    block_h = max(70, h // 4)
    draw.rounded_rectangle([cx, cy, cx + block_w, cy + block_h],
                           radius=4, fill=HEARTH["base"])
    code_lines = [
        ("def ", SPARK["violet"]), ("hush", SPARK["amber"]),
        ("(palette):", GLOW["dim"]),
    ]
    code_y = cy + 12
    code_x = cx + 14
    for text, color in code_lines:
        draw.text((code_x, code_y), text, font=font_body, fill=color)
        bb = draw.textbbox((0, 0), text, font=font_body)
        code_x += bb[2] - bb[0]
    code_y += font_body.size + 6
    draw.text((cx + 14, code_y), "    return ", font=font_body, fill=SPARK["violet"])
    bb = draw.textbbox((0, 0), "    return ", font=font_body)
    draw.text((cx + 14 + bb[2] - bb[0], code_y), "calm", font=font_body, fill=SPARK["green"])

    # Status row
    sy = cy + block_h + 14
    chips = [
        ("OK",       SPARK["green"]),
        ("Warning",  SPARK["amber"]),
        ("Error",    SPARK["red"]),
        ("Link",     MIST["blue"]),
    ]
    sx = cx
    for label, color in chips:
        bb = draw.textbbox((0, 0), label, font=font_body)
        chip_w = (bb[2] - bb[0]) + 16
        chip_h = font_body.size + 8
        draw.rounded_rectangle([sx, sy, sx + chip_w, sy + chip_h],
                               radius=chip_h // 2, fill=HEARTH["high"])
        draw.text((sx + 8, sy + 2), label, font=font_body, fill=color)
        sx += chip_w + 8


def render(width: int, height: int) -> Image.Image:
    img = render_wallpaper(width, height)
    font_title = load_font(max(14, height // 36))
    font_body  = load_font(max(11, height // 56))
    font_small = load_font(max(11, height // 60))

    # Centered window taking ~70% width, 65% height.
    win_w = int(width * 0.72)
    win_h = int(height * 0.66)
    win_x = (width - win_w) // 2
    win_y = int(height * 0.10)
    draw_window(img, win_x, win_y, win_w, win_h, font_title, font_body)

    draw = ImageDraw.Draw(img)
    draw_panel(draw, width, height, font_small)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-thumb", type=Path, required=True)
    ap.add_argument("--out-full", type=Path, required=True)
    args = ap.parse_args()

    full = render(1920, 1214)
    args.out_full.parent.mkdir(parents=True, exist_ok=True)
    full.save(args.out_full, quality=88, optimize=True)
    print(f"Wrote {args.out_full}")

    thumb = full.resize((512, 324), Image.LANCZOS)
    args.out_thumb.parent.mkdir(parents=True, exist_ok=True)
    thumb.save(args.out_thumb, optimize=True)
    print(f"Wrote {args.out_thumb}")


if __name__ == "__main__":
    main()

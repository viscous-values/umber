"""Render preview + review images for the Umber palette family.

Outputs (one per --out-* flag, all independent and optional):

- --out-full PATH        desktop with wallpaper + panel + faux window (1920x1214)
- --out-thumb PATH       same, downscaled to 512x324
- --out-swatches PATH    17-cell tier grid (900x320)
- --out-filemanager PATH Dolphin-style window (1200x760)
- --out-textsample PATH  code editor surface (1200x760)
- --out-ui-catalog PATH  control gallery (1200x760)

The desktop view (--out-full / --out-thumb) is the synthetic Plasma
preview that ships inside the LookAndFeel package. The other views are
review-only artifacts used to evaluate a palette before regenerating
consumer files.

A run takes one palette (--palette, default palette.toml) and one title
(--title, default derived from the palette filename) and produces only
the views requested by --out-* flags.
"""

import argparse
import random
import tomllib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# palette                                                                     #
# --------------------------------------------------------------------------- #

def _hex_rgb(h):
    h = h.lstrip("#")
    return (int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def load_palette(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def palette_aliases(palette):
    """Return semantic-role dicts for hearth/glow/mist/spark.

    Renaming a key here repoints every downstream draw call without any
    further edits.
    """
    hearth = {
        "deep": _hex_rgb(palette["hearth"]["0"]),
        "base": _hex_rgb(palette["hearth"]["1"]),
        "elev": _hex_rgb(palette["hearth"]["2"]),
        "high": _hex_rgb(palette["hearth"]["3"]),
    }
    glow = {
        "dim":   _hex_rgb(palette["glow"]["0"]),
        "warm":  _hex_rgb(palette["glow"]["1"]),
        "peach": _hex_rgb(palette["glow"]["2"]),
        "near":  _hex_rgb(palette["glow"]["3"]),
    }
    mist = {
        "deep": _hex_rgb(palette["mist"]["0"]),
        "teal": _hex_rgb(palette["mist"]["1"]),
        "blue": _hex_rgb(palette["mist"]["2"]),
        "sky":  _hex_rgb(palette["mist"]["3"]),
    }
    spark = {
        "red":    _hex_rgb(palette["spark"]["red"]),
        "orange": _hex_rgb(palette["spark"]["orange"]),
        "amber":  _hex_rgb(palette["spark"]["amber"]),
        "green":  _hex_rgb(palette["spark"]["green"]),
        "violet": _hex_rgb(palette["spark"]["violet"]),
    }
    return hearth, glow, mist, spark


def _wallpaper_glow(palette):
    """Horizon-band tone derived from the palette so cool palettes get cool bands."""
    deep = _hex_rgb(palette["hearth"]["0"])
    emph = _hex_rgb(palette["glow"]["2"])
    return lerp(deep, emph, 0.45)


# --------------------------------------------------------------------------- #
# common helpers                                                              #
# --------------------------------------------------------------------------- #

def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


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


def load_mono(size):
    candidates = [
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/noto/NotoMono-Regular.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return load_font(size)


def text_w(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def text_h(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def derive_title(palette_path):
    stem = Path(palette_path).stem
    if stem == "palette":
        return "Umber"
    if stem.startswith("umber-"):
        return "Umber " + stem[len("umber-"):].replace("-", " ").title()
    return "Umber " + stem.replace("-", " ").title()


# --------------------------------------------------------------------------- #
# wallpaper                                                                   #
# --------------------------------------------------------------------------- #

HORIZON = 0.72
GLOW_WIDTH = 0.18
GRAIN = 3


def horizon_weight(y_frac):
    d = abs(y_frac - HORIZON) / GLOW_WIDTH
    if d >= 1.0:
        return 0.0
    return (1 - d * d) ** 2


def base_color(y_frac, hearth):
    if y_frac < HORIZON:
        return lerp(hearth["deep"], hearth["elev"], y_frac / HORIZON)
    return lerp(hearth["elev"], hearth["base"], (y_frac - HORIZON) / (1.0 - HORIZON))


def render_wallpaper(width, height, palette, hearth, seed=1729):
    rng = random.Random(seed)
    img = Image.new("RGB", (width, height))
    px = img.load()
    band = _wallpaper_glow(palette)
    for y in range(height):
        y_frac = y / (height - 1)
        base = base_color(y_frac, hearth)
        glow_t = horizon_weight(y_frac) * 0.55
        row = lerp(base, band, glow_t)
        for x in range(width):
            j = rng.randint(-GRAIN, GRAIN)
            px[x, y] = (
                max(0, min(255, row[0] + j)),
                max(0, min(255, row[1] + j)),
                max(0, min(255, row[2] + j)),
            )
    return img


# --------------------------------------------------------------------------- #
# desktop view (ships in-package as preview.png / fullscreenpreview.jpg)      #
# --------------------------------------------------------------------------- #

def _draw_panel(draw, w, h, hearth, glow, font_small):
    panel_h = max(36, h // 22)
    y0 = h - panel_h
    draw.rectangle([0, y0, w, h], fill=hearth["deep"])
    draw.line([0, y0, w, y0], fill=hearth["high"])
    pad = panel_h // 4
    draw.rectangle([pad, y0 + pad, pad + panel_h - 2 * pad, h - pad],
                   fill=glow["peach"])
    x = pad * 3 + (panel_h - 2 * pad)
    for _ in range(3):
        draw.rectangle([x, y0 + pad, x + panel_h * 2, h - pad], fill=hearth["high"])
        x += panel_h * 2 + pad
    clock = "20:42"
    tw = text_w(draw, clock, font_small)
    th = text_h(draw, clock, font_small)
    draw.text((w - tw - pad * 3, y0 + (panel_h - th) // 2 - 2),
              clock, font=font_small, fill=glow["warm"])


def _draw_window(img, x, y, w, h, title, hearth, glow, mist, spark,
                 font_title, font_body):
    draw = ImageDraw.Draw(img, "RGBA")
    titlebar_h = max(28, h // 14)
    radius = 8

    # Drop shadow.
    for i in range(4):
        alpha = 36 - i * 8
        draw.rounded_rectangle(
            [x - i * 2, y - i, x + w + i * 2, y + h + i * 3],
            radius=radius + i, fill=(0, 0, 0, alpha))

    # Window body + titlebar.
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=hearth["deep"])
    draw.rounded_rectangle([x, y, x + w, y + titlebar_h], radius=radius, fill=hearth["elev"])
    draw.rectangle([x, y + titlebar_h - radius, x + w, y + titlebar_h], fill=hearth["elev"])
    draw.line([x, y + titlebar_h, x + w, y + titlebar_h], fill=hearth["high"])

    th = text_h(draw, title, font_title)
    draw.text((x + 16, y + (titlebar_h - th) // 2 - 2),
              title, font=font_title, fill=glow["warm"])

    btn_r = max(6, titlebar_h // 4)
    by = y + titlebar_h // 2
    bx = x + w - 18
    for color in (spark["red"], spark["amber"], spark["green"]):
        draw.ellipse([bx - btn_r, by - btn_r, bx + btn_r, by + btn_r], fill=color)
        bx -= btn_r * 2 + 8

    # Sidebar.
    side_w = w // 4
    draw.rectangle([x, y + titlebar_h, x + side_w, y + h - radius], fill=hearth["base"])
    item_h = max(22, h // 18)
    iy = y + titlebar_h + 14
    rows = [
        ("Hearth", glow["warm"]),
        ("Glow",   glow["peach"]),
        ("Mist",   mist["blue"]),
        ("Spark",  spark["amber"]),
    ]
    for label, accent in rows:
        if label == "Glow":
            draw.rounded_rectangle(
                [x + 8, iy - 4, x + side_w - 8, iy + item_h - 4],
                radius=4, fill=glow["peach"])
            text_color = hearth["deep"]
        else:
            text_color = glow["dim"]
        sw = item_h - 8
        draw.rectangle(
            [x + 16, iy + (item_h - sw) // 2 - 2,
             x + 16 + sw, iy + (item_h + sw) // 2 - 2],
            fill=accent, outline=hearth["high"])
        draw.text((x + 16 + sw + 10, iy - 2), label, font=font_body, fill=text_color)
        iy += item_h + 6

    # Main content.
    cx = x + side_w + 24
    cy = y + titlebar_h + 22
    headline = "Calm cream on charcoal"
    draw.text((cx, cy), headline, font=font_title, fill=glow["peach"])
    cy += font_title.size + 8
    body_lines = [
        "16 colors. 4 tiers.",
        "Hearth surfaces, glow foregrounds,",
        "mist counterweights, spark accents.",
    ]
    for line in body_lines:
        draw.text((cx, cy), line, font=font_body, fill=glow["dim"])
        cy += font_body.size + 4
    cy += 10

    block_w = w - side_w - 48
    block_h = max(70, h // 4)
    draw.rounded_rectangle([cx, cy, cx + block_w, cy + block_h],
                           radius=4, fill=hearth["base"])
    code_y = cy + 12
    code_x = cx + 14
    for token, color in [
        ("def ",      spark["violet"]),
        ("umber",     spark["amber"]),
        ("(palette):", glow["dim"]),
    ]:
        draw.text((code_x, code_y), token, font=font_body, fill=color)
        code_x += text_w(draw, token, font_body)
    code_y += font_body.size + 6
    draw.text((cx + 14, code_y), "    return ", font=font_body, fill=spark["violet"])
    rw = text_w(draw, "    return ", font_body)
    draw.text((cx + 14 + rw, code_y), "calm", font=font_body, fill=spark["green"])

    # Status chips.
    sy = cy + block_h + 14
    sx = cx
    for label, color in [
        ("OK",      spark["green"]),
        ("Warning", spark["amber"]),
        ("Error",   spark["red"]),
        ("Link",    mist["blue"]),
    ]:
        cw = text_w(draw, label, font_body) + 16
        ch = font_body.size + 8
        draw.rounded_rectangle([sx, sy, sx + cw, sy + ch],
                               radius=ch // 2, fill=hearth["high"])
        draw.text((sx + 8, sy + 2), label, font=font_body, fill=color)
        sx += cw + 8


def render_desktop(width, height, palette, title):
    hearth, glow, mist, spark = palette_aliases(palette)
    img = render_wallpaper(width, height, palette, hearth)
    font_title = load_font(max(14, height // 36))
    font_body  = load_font(max(11, height // 56))
    font_small = load_font(max(11, height // 60))

    win_w = int(width * 0.72)
    win_h = int(height * 0.66)
    win_x = (width - win_w) // 2
    win_y = int(height * 0.10)
    _draw_window(img, win_x, win_y, win_w, win_h, title,
                 hearth, glow, mist, spark, font_title, font_body)

    draw = ImageDraw.Draw(img)
    _draw_panel(draw, width, height, hearth, glow, font_small)
    return img


# --------------------------------------------------------------------------- #
# review view: swatches grid                                                  #
# --------------------------------------------------------------------------- #

def render_swatches(palette, title, width=900, height=320):
    hearth, glow, mist, spark = palette_aliases(palette)
    img = Image.new("RGB", (width, height), color=hearth["deep"])
    draw = ImageDraw.Draw(img)
    font_title = load_font(20)
    font_label = load_font(11)
    font_hex   = load_mono(10)

    draw.text((20, 14), title, font=font_title, fill=glow["warm"])
    draw.text((20, 40), "tier · role · hex", font=font_label, fill=glow["dim"])

    rows = [
        ("hearth", [("deep", hearth["deep"], palette["hearth"]["0"]),
                    ("base", hearth["base"], palette["hearth"]["1"]),
                    ("elev", hearth["elev"], palette["hearth"]["2"]),
                    ("high", hearth["high"], palette["hearth"]["3"])]),
        ("glow",   [("dim",   glow["dim"],   palette["glow"]["0"]),
                    ("warm",  glow["warm"],  palette["glow"]["1"]),
                    ("peach", glow["peach"], palette["glow"]["2"]),
                    ("near",  glow["near"],  palette["glow"]["3"])]),
        ("mist",   [("deep", mist["deep"], palette["mist"]["0"]),
                    ("teal", mist["teal"], palette["mist"]["1"]),
                    ("blue", mist["blue"], palette["mist"]["2"]),
                    ("sky",  mist["sky"],  palette["mist"]["3"])]),
        ("spark",  [("red",    spark["red"],    palette["spark"]["red"]),
                    ("orange", spark["orange"], palette["spark"]["orange"]),
                    ("amber",  spark["amber"],  palette["spark"]["amber"]),
                    ("green",  spark["green"],  palette["spark"]["green"]),
                    ("violet", spark["violet"], palette["spark"]["violet"])]),
    ]

    grid_top = 70
    cell_w = 130
    cell_h = 50
    pad = 8
    label_w = 70
    for ri, (tier, cells) in enumerate(rows):
        ry = grid_top + ri * (cell_h + pad)
        draw.text((20, ry + (cell_h - 16) // 2), tier, font=font_label, fill=glow["warm"])
        cx = 20 + label_w
        for role, rgb, hex_str in cells:
            # Cell fill + 1px outline.
            draw.rectangle([cx, ry, cx + cell_w, ry + cell_h], fill=rgb,
                           outline=hearth["high"])
            # Pick legible text color by luminance.
            lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
            text_fg = hearth["deep"] if lum > 140 else glow["near"]
            draw.text((cx + 8, ry + 6), role, font=font_label, fill=text_fg)
            draw.text((cx + 8, ry + 24), hex_str.upper(), font=font_hex, fill=text_fg)
            cx += cell_w + pad
    return img


# --------------------------------------------------------------------------- #
# review view: file manager (Dolphin-shaped)                                  #
# --------------------------------------------------------------------------- #

def _frame_window(img, x, y, w, h, title, hearth, glow, spark, font_title):
    """Shared window chrome. Returns (content_x, content_y, content_w, content_h)."""
    draw = ImageDraw.Draw(img, "RGBA")
    titlebar_h = max(30, h // 22)
    radius = 8
    for i in range(4):
        alpha = 36 - i * 8
        draw.rounded_rectangle(
            [x - i * 2, y - i, x + w + i * 2, y + h + i * 3],
            radius=radius + i, fill=(0, 0, 0, alpha))
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=hearth["deep"])
    draw.rounded_rectangle([x, y, x + w, y + titlebar_h], radius=radius, fill=hearth["elev"])
    draw.rectangle([x, y + titlebar_h - radius, x + w, y + titlebar_h], fill=hearth["elev"])
    draw.line([x, y + titlebar_h, x + w, y + titlebar_h], fill=hearth["high"])
    th = text_h(draw, title, font_title)
    draw.text((x + 16, y + (titlebar_h - th) // 2 - 2),
              title, font=font_title, fill=glow["warm"])
    btn_r = max(6, titlebar_h // 4)
    by = y + titlebar_h // 2
    bx = x + w - 18
    for color in (spark["red"], spark["amber"], spark["green"]):
        draw.ellipse([bx - btn_r, by - btn_r, bx + btn_r, by + btn_r], fill=color)
        bx -= btn_r * 2 + 8
    return x, y + titlebar_h, w, h - titlebar_h


def render_filemanager(palette, title, width=1200, height=760):
    hearth, glow, mist, spark = palette_aliases(palette)
    img = Image.new("RGB", (width, height), color=lerp(hearth["deep"], (0, 0, 0), 0.35))
    font_title = load_font(15)
    font_body  = load_font(13)
    font_small = load_font(11)
    font_mono  = load_mono(12)

    win_x, win_y, win_w, win_h = 40, 40, width - 80, height - 80
    cx, cy, cw, ch = _frame_window(
        img, win_x, win_y, win_w, win_h,
        f"Documents — {title}",
        hearth, glow, spark, font_title)

    draw = ImageDraw.Draw(img, "RGBA")

    # Toolbar.
    tb_h = 36
    draw.rectangle([cx, cy, cx + cw, cy + tb_h], fill=hearth["base"])
    draw.line([cx, cy + tb_h, cx + cw, cy + tb_h], fill=hearth["high"])
    nav_x = cx + 14
    for glyph in ["←", "→", "↑", "⟳"]:
        draw.text((nav_x, cy + 10), glyph, font=font_body, fill=glow["dim"])
        nav_x += 26
    # Breadcrumb.
    bc_x = nav_x + 16
    bc_y = cy + 10
    crumbs = [("Home", mist["blue"]), (" / ", glow["dim"]),
              ("tyler", mist["blue"]), (" / ", glow["dim"]),
              ("Documents", glow["warm"])]
    for txt, color in crumbs:
        draw.text((bc_x, bc_y), txt, font=font_body, fill=color)
        bc_x += text_w(draw, txt, font_body)

    # Sidebar.
    sb_x = cx
    sb_y = cy + tb_h
    sb_w = 230
    sb_h = ch - tb_h
    draw.rectangle([sb_x, sb_y, sb_x + sb_w, sb_y + sb_h], fill=hearth["base"])
    draw.line([sb_x + sb_w, sb_y, sb_x + sb_w, sb_y + sb_h], fill=hearth["high"])

    draw.text((sb_x + 16, sb_y + 14), "Places", font=font_small, fill=glow["dim"])
    places = [
        ("Home",      mist["blue"],  False),
        ("Documents", mist["teal"],  True),
        ("Downloads", mist["sky"],   False),
        ("Pictures",  mist["deep"],  False),
        ("Music",     spark["violet"], False),
        ("Trash",     spark["red"],  False),
    ]
    item_h = 30
    item_y = sb_y + 34
    for label, icon_color, selected in places:
        if selected:
            draw.rounded_rectangle(
                [sb_x + 8, item_y, sb_x + sb_w - 8, item_y + item_h - 2],
                radius=4, fill=glow["peach"])
            txt_color = hearth["deep"]
            icon_outline = hearth["deep"]
        else:
            txt_color = glow["warm"]
            icon_outline = hearth["high"]
        # Icon: filled square swatch.
        draw.rectangle(
            [sb_x + 18, item_y + 7, sb_x + 32, item_y + item_h - 9],
            fill=icon_color, outline=icon_outline)
        draw.text((sb_x + 42, item_y + 6), label, font=font_body, fill=txt_color)
        item_y += item_h + 2

    # Devices section.
    item_y += 8
    draw.text((sb_x + 16, item_y), "Devices", font=font_small, fill=glow["dim"])
    item_y += 22
    for label, icon_color in [("SSD",  mist["sky"]), ("USB Drive", mist["teal"])]:
        draw.rectangle(
            [sb_x + 18, item_y + 7, sb_x + 32, item_y + item_h - 9],
            fill=icon_color, outline=hearth["high"])
        draw.text((sb_x + 42, item_y + 6), label, font=font_body, fill=glow["warm"])
        item_y += item_h + 2

    # File list pane.
    fl_x = sb_x + sb_w
    fl_y = sb_y
    fl_w = cw - sb_w
    fl_h = sb_h
    draw.rectangle([fl_x, fl_y, fl_x + fl_w, fl_y + fl_h], fill=hearth["deep"])

    # Header row.
    hdr_h = 28
    draw.rectangle([fl_x, fl_y, fl_x + fl_w, fl_y + hdr_h], fill=hearth["base"])
    draw.line([fl_x, fl_y + hdr_h, fl_x + fl_w, fl_y + hdr_h], fill=hearth["high"])
    cols = [("Name", 16), ("Size", fl_w - 240), ("Modified", fl_w - 130)]
    for label, dx in cols:
        draw.text((fl_x + dx, fl_y + 7), label, font=font_small, fill=glow["dim"])

    files = [
        ("📁 Projects",        mist["blue"],   "—",       "Apr 28 14:02", "folder"),
        ("📁 Reports",         mist["blue"],   "—",       "Apr 27 09:11", "folder"),
        ("📁 Receipts",        mist["blue"],   "—",       "Apr 21 17:43", "folder"),
        ("notes.md",          glow["warm"],   "12.4 KB", "Apr 28 16:33", "selected"),
        ("budget.numbers",    glow["warm"],   "84.0 KB", "Apr 26 11:08", "file"),
        ("invoice-042.pdf",   glow["warm"],   "210 KB",  "Apr 25 22:15", "hover"),
        ("portrait.jpg",      glow["warm"],   "1.4 MB",  "Apr 24 08:30", "file"),
        ("spec.txt",          glow["warm"],   "3.1 KB",  "Apr 22 19:57", "file"),
        ("agenda.docx",       glow["warm"],   "27.0 KB", "Apr 22 09:00", "file"),
        ("config.toml",       glow["warm"],   "1.2 KB",  "Apr 21 13:14", "file"),
        ("archive.tar.gz",    glow["warm"],   "8.7 MB",  "Apr 18 10:42", "file"),
        ("README",            glow["warm"],   "0.8 KB",  "Apr 16 23:01", "file"),
    ]
    row_h = 30
    row_y = fl_y + hdr_h + 2
    for name, name_color, size, mtime, state in files:
        if state == "selected":
            draw.rectangle([fl_x + 4, row_y, fl_x + fl_w - 4, row_y + row_h - 2],
                           fill=glow["peach"])
            n_color = hearth["deep"]
            m_color = hearth["deep"]
        elif state == "hover":
            draw.rectangle([fl_x + 4, row_y, fl_x + fl_w - 4, row_y + row_h - 2],
                           fill=hearth["elev"])
            n_color = glow["warm"]
            m_color = glow["dim"]
        else:
            n_color = name_color
            m_color = glow["dim"]
        draw.text((fl_x + 16, row_y + 7), name, font=font_body, fill=n_color)
        draw.text((fl_x + cols[1][1], row_y + 7), size, font=font_mono, fill=m_color)
        draw.text((fl_x + cols[2][1], row_y + 7), mtime, font=font_mono, fill=m_color)
        row_y += row_h
        if row_y > fl_y + fl_h - 30:
            break

    # Statusbar.
    st_h = 24
    st_y = win_y + win_h - st_h - 4
    draw.rectangle([cx, st_y, cx + cw, st_y + st_h], fill=hearth["base"])
    draw.line([cx, st_y, cx + cw, st_y], fill=hearth["high"])
    draw.text((cx + 16, st_y + 5), "12 items · 3 folders · 1 selected (12.4 KB)",
              font=font_small, fill=glow["dim"])

    return img


# --------------------------------------------------------------------------- #
# review view: text sample (code editor)                                      #
# --------------------------------------------------------------------------- #

def render_textsample(palette, title, width=1200, height=760):
    hearth, glow, mist, spark = palette_aliases(palette)
    img = Image.new("RGB", (width, height), color=lerp(hearth["deep"], (0, 0, 0), 0.35))
    font_title = load_font(15)
    font_body  = load_font(12)
    font_small = load_font(11)
    font_mono  = load_mono(13)

    win_x, win_y, win_w, win_h = 40, 40, width - 80, height - 80
    cx, cy, cw, ch = _frame_window(
        img, win_x, win_y, win_w, win_h,
        f"render.py — {title}",
        hearth, glow, spark, font_title)

    draw = ImageDraw.Draw(img, "RGBA")

    # Tab strip.
    tab_h = 32
    draw.rectangle([cx, cy, cx + cw, cy + tab_h], fill=hearth["base"])
    draw.line([cx, cy + tab_h, cx + cw, cy + tab_h], fill=hearth["high"])
    tabs = [("render.py", True), ("palette.toml", False), ("README.md", False)]
    tab_x = cx + 8
    for label, active in tabs:
        tw = text_w(draw, label, font_body) + 28
        if active:
            draw.rectangle([tab_x, cy, tab_x + tw, cy + tab_h], fill=hearth["deep"])
            draw.rectangle([tab_x, cy + tab_h - 2, tab_x + tw, cy + tab_h],
                           fill=glow["peach"])
            tcolor = glow["warm"]
        else:
            tcolor = glow["dim"]
        draw.text((tab_x + 12, cy + 8), label, font=font_body, fill=tcolor)
        tab_x += tw + 2

    # Gutter + code area.
    gutter_w = 56
    gx, gy = cx, cy + tab_h
    gh = ch - tab_h - 28  # leave room for statusbar
    draw.rectangle([gx, gy, gx + gutter_w, gy + gh], fill=hearth["base"])
    draw.line([gx + gutter_w, gy, gx + gutter_w, gy + gh], fill=hearth["high"])

    code_x = gx + gutter_w + 14
    code_w = cw - gutter_w - 110  # leave room for minimap on right
    code_y = gy + 12
    line_h = font_mono.size + 6

    # Each line is a list of (text, color, decoration) tuples; decoration
    # ∈ {None, "warn", "error"} drives squiggle underlines.
    Vio = spark["violet"]
    Grn = spark["green"]
    Org = spark["orange"]
    Amb = spark["amber"]
    Red = spark["red"]
    Tea = mist["teal"]
    Blu = mist["blue"]
    Sky = mist["sky"]
    Dep = mist["deep"]
    Bod = glow["warm"]

    lines = [
        [('"""Calm cream on charcoal — palette renderer."""', Sky, None)],
        [('', Bod, None)],
        [('import ', Vio, None), ('json', Bod, None)],
        [('from ', Vio, None), ('pathlib', Bod, None),
         (' import ', Vio, None), ('Path', Blu, None)],
        [('', Bod, None)],
        [('PALETTE_VERSION', Bod, None), (' = ', Bod, None),
         ('17', Org, None)],
        [('RE_HEX', Bod, None), (' = ', Bod, None),
         ("r'^#[0-9A-F]{6}$'", Tea, None)],
        [('', Bod, None)],
        [('def ', Vio, None), ('render', Blu, None),
         ('(', Bod, None), ('palette', Bod, None),
         (': ', Bod, None), ('dict', Blu, None),
         (') -> ', Bod, None), ('Image', Blu, None), (':', Bod, None)],
        [('    """Render the preview."""', Sky, None)],
        [('    result', Bod, None), (' = [', Dep, None),
         ("'header'", Grn, None), (']', Dep, None)],
        [('    for ', Vio, None), ('tier', Bod, None),
         (' in ', Vio, None), ('palette', Bod, None), (':', Bod, None)],
        [('        if ', Vio, None), ('tier', Bod, None),
         (' == ', Vio, None), ("'spark'", Grn, None), (':', Bod, None)],
        [('            result', Bod, None), ('.', Bod, None),
         ('append', Blu, None), ('(', Bod, None),
         ('tier', Bod, None), (')', Bod, None)],
        [('        else', Vio, None), (':', Bod, None)],
        [('            raise ', Vio, None), ('ValueError', Red, None),
         ('(', Bod, None), ("'unknown tier'", Grn, None), (')', Bod, None)],
        [('    return ', Vio, None), ('result', Bod, None)],
        [('', Bod, None)],
        [('unused_var', Bod, "warn"), (' = ', Bod, None), ('42', Org, None)],
        [('undefined', Bod, "error"), ('()', Bod, None)],
    ]

    # Selection band — across lines 11-13 (0-indexed 10-12).
    sel_top = code_y + 10 * line_h - 2
    sel_bot = code_y + 13 * line_h - 2
    draw.rectangle([code_x - 4, sel_top, code_x + code_w, sel_bot],
                   fill=glow["peach"])

    for i, segs in enumerate(lines):
        ly = code_y + i * line_h
        # Line number.
        ln = str(i + 1).rjust(3)
        draw.text((gx + 10, ly), ln, font=font_mono, fill=glow["dim"])
        x_cursor = code_x
        in_selection = 10 <= i <= 12
        for text, color, decoration in segs:
            fg = hearth["deep"] if in_selection else color
            draw.text((x_cursor, ly), text, font=font_mono, fill=fg)
            tw = text_w(draw, text, font_mono)
            if decoration in ("warn", "error"):
                under_color = Amb if decoration == "warn" else Red
                _draw_squiggle(draw, x_cursor, ly + font_mono.size + 1,
                               x_cursor + tw, under_color)
            x_cursor += tw

    # Cursor at end of line 16 (0-indexed 15).
    cursor_y = code_y + 15 * line_h
    cursor_x = code_x + text_w(draw, "            raise ValueError('unknown tier')", font_mono)
    draw.line([cursor_x, cursor_y, cursor_x, cursor_y + font_mono.size + 1],
              fill=glow["near"], width=2)

    # Minimap (right column).
    mm_x = cx + cw - 90
    mm_y = gy + 8
    mm_w = 76
    mm_h = gh - 16
    draw.rectangle([mm_x, mm_y, mm_x + mm_w, mm_y + mm_h], fill=hearth["base"])
    draw.line([mm_x, mm_y, mm_x, mm_y + mm_h], fill=hearth["high"])
    # Each code line becomes a thin colored bar, length proportional to its
    # text length (capped at mm_w-4); color from the dominant token color.
    bar_h = max(1, (mm_h - 8) // max(1, len(lines)))
    for i, segs in enumerate(lines):
        char_count = sum(len(t) for t, _, _ in segs)
        bar_w = min(mm_w - 6, max(2, char_count // 2))
        # Pick the most "saturated" segment color as bar color, falling back
        # to a desaturated body tone.
        dominant = None
        for _, color, _ in segs:
            if color in (Vio, Grn, Org, Red, Blu, Tea, Sky):
                dominant = color
                break
        if dominant is None:
            dominant = lerp(Bod, hearth["base"], 0.5)
        else:
            dominant = lerp(dominant, hearth["base"], 0.4)
        by_ = mm_y + 4 + i * bar_h
        draw.rectangle([mm_x + 3, by_, mm_x + 3 + bar_w, by_ + max(1, bar_h - 1)],
                       fill=dominant)

    # Statusbar.
    st_h = 24
    st_y = win_y + win_h - st_h - 4
    draw.rectangle([cx, st_y, cx + cw, st_y + st_h], fill=hearth["base"])
    draw.line([cx, st_y, cx + cw, st_y], fill=hearth["high"])
    left = "main · render.py"
    right = "Ln 17, Col 12 · UTF-8 · Python · LF"
    draw.text((cx + 16, st_y + 5), left, font=font_small, fill=mist["blue"])
    rw = text_w(draw, right, font_small)
    draw.text((cx + cw - rw - 16, st_y + 5), right, font=font_small, fill=glow["dim"])

    return img


def _draw_squiggle(draw, x1, y, x2, color, amplitude=2, period=4):
    """Wavy underline between (x1, y) and (x2, y)."""
    x = x1
    up = True
    while x < x2:
        nx = min(x + period, x2)
        draw.line([x, y + (-amplitude if up else amplitude),
                   nx, y + (amplitude if up else -amplitude)],
                  fill=color, width=1)
        up = not up
        x = nx


# --------------------------------------------------------------------------- #
# review view: UI catalog                                                     #
# --------------------------------------------------------------------------- #

def render_ui_catalog(palette, title, width=1200, height=760):
    hearth, glow, mist, spark = palette_aliases(palette)
    img = Image.new("RGB", (width, height), color=lerp(hearth["deep"], (0, 0, 0), 0.35))
    font_title = load_font(15)
    font_h2    = load_font(13)
    font_body  = load_font(12)
    font_small = load_font(11)

    win_x, win_y, win_w, win_h = 40, 40, width - 80, height - 80
    cx, cy, cw, ch = _frame_window(
        img, win_x, win_y, win_w, win_h,
        f"UI Catalog — {title}",
        hearth, glow, spark, font_title)

    draw = ImageDraw.Draw(img, "RGBA")

    # Two columns.
    col_gap = 16
    col_w = (cw - col_gap - 48) // 2
    L = cx + 24
    R = L + col_w + col_gap
    # ---- left column ----
    y = cy + 18

    # Buttons.
    draw.text((L, y), "Buttons", font=font_h2, fill=glow["warm"])
    y += 22
    btn_h = 32
    bx = L
    for label, bg, fg in [
        ("Save",   mist["blue"],   hearth["deep"]),
        ("Cancel", hearth["elev"], glow["warm"]),
        ("Delete", spark["red"],   hearth["deep"]),
        ("Submit", hearth["elev"], glow["dim"]),
    ]:
        bw = text_w(draw, label, font_body) + 36
        draw.rounded_rectangle([bx, y, bx + bw, y + btn_h], radius=5, fill=bg,
                               outline=hearth["high"])
        draw.text((bx + 18, y + 8), label, font=font_body, fill=fg)
        bx += bw + 10
    y += btn_h + 26

    # Chips.
    draw.text((L, y), "Chips", font=font_h2, fill=glow["warm"])
    y += 22
    chip_h = 26
    bx = L
    for label, color in [
        ("OK",      spark["green"]),
        ("Warning", spark["amber"]),
        ("Error",   spark["red"]),
        ("Info",    mist["blue"]),
        ("Neutral", glow["dim"]),
    ]:
        cw_chip = text_w(draw, label, font_body) + 28
        draw.rounded_rectangle([bx, y, bx + cw_chip, y + chip_h],
                               radius=chip_h // 2, fill=hearth["high"])
        # Color dot.
        dot_r = 4
        draw.ellipse([bx + 8, y + chip_h // 2 - dot_r,
                      bx + 8 + dot_r * 2, y + chip_h // 2 + dot_r],
                     fill=color)
        draw.text((bx + 22, y + 5), label, font=font_body, fill=glow["warm"])
        bx += cw_chip + 8
    y += chip_h + 26

    # Tabs.
    draw.text((L, y), "Tabs", font=font_h2, fill=glow["warm"])
    y += 22
    tab_h = 30
    bx = L
    for label, active in [("Overview", True), ("Settings", False), ("Logs", False)]:
        tw_tab = text_w(draw, label, font_body) + 24
        if active:
            draw.text((bx + 12, y + 7), label, font=font_body, fill=glow["warm"])
            draw.rectangle([bx, y + tab_h - 3, bx + tw_tab, y + tab_h],
                           fill=glow["peach"])
        else:
            draw.text((bx + 12, y + 7), label, font=font_body, fill=glow["dim"])
        bx += tw_tab + 2
    draw.line([L, y + tab_h, L + col_w, y + tab_h], fill=hearth["high"])
    y += tab_h + 26

    # Form fields.
    draw.text((L, y), "Form fields", font=font_h2, fill=glow["warm"])
    y += 22
    inp_h = 32
    # Email input — focused state with mist.blue ring.
    draw.rounded_rectangle([L, y, L + col_w - 20, y + inp_h], radius=4,
                           fill=hearth["deep"], outline=mist["blue"], width=2)
    draw.text((L + 12, y + 9), "user@example.com",
              font=font_body, fill=glow["warm"])
    y += inp_h + 14
    # Checkbox.
    cb = 18
    draw.rounded_rectangle([L, y, L + cb, y + cb], radius=3,
                           fill=spark["green"], outline=hearth["high"])
    # Check glyph.
    draw.line([L + 4, y + 9, L + 8, y + 13], fill=hearth["deep"], width=2)
    draw.line([L + 8, y + 13, L + 14, y + 5], fill=hearth["deep"], width=2)
    draw.text((L + cb + 10, y + 2), "Remember me on this device",
              font=font_body, fill=glow["warm"])
    y += cb + 14
    # Radio (selected).
    rr = 9
    draw.ellipse([L, y, L + rr * 2, y + rr * 2], outline=mist["blue"], width=2)
    draw.ellipse([L + 4, y + 4, L + rr * 2 - 4, y + rr * 2 - 4], fill=mist["blue"])
    draw.text((L + rr * 2 + 10, y + 1), "Standard tier",
              font=font_body, fill=glow["warm"])
    y += rr * 2 + 18

    # Links.
    draw.text((L, y), "Links", font=font_h2, fill=glow["warm"])
    y += 22
    # Default.
    txt = "Visit the docs"
    draw.text((L, y), txt, font=font_body, fill=mist["blue"])
    tl_w = text_w(draw, txt, font_body)
    draw.line([L, y + font_body.size + 1, L + tl_w, y + font_body.size + 1],
              fill=mist["blue"])
    # Visited.
    txt2 = "Read changelog"
    draw.text((L + tl_w + 24, y), txt2, font=font_body, fill=spark["violet"])
    tl_w2 = text_w(draw, txt2, font_body)
    draw.line([L + tl_w + 24, y + font_body.size + 1,
               L + tl_w + 24 + tl_w2, y + font_body.size + 1],
              fill=spark["violet"])

    # ---- right column ----
    y = cy + 18
    draw.text((R, y), "Alerts", font=font_h2, fill=glow["warm"])
    y += 22
    alerts = [
        ("Saved successfully.",             spark["green"]),
        ("Configuration may be incomplete.", spark["amber"]),
        ("Failed to apply theme.",           spark["red"]),
        ("3 updates available.",             mist["blue"]),
    ]
    for msg, accent in alerts:
        ah = 38
        draw.rectangle([R, y, R + col_w - 20, y + ah], fill=hearth["elev"])
        draw.rectangle([R, y, R + 4, y + ah], fill=accent)
        draw.text((R + 16, y + 11), msg, font=font_body, fill=glow["warm"])
        y += ah + 6
    y += 14

    # Toast.
    draw.text((R, y), "Toast", font=font_h2, fill=glow["warm"])
    y += 22
    th_t = 50
    draw.rounded_rectangle([R, y, R + col_w - 60, y + th_t], radius=6,
                           fill=hearth["base"], outline=hearth["high"])
    draw.rectangle([R, y, R + 4, y + th_t], fill=mist["blue"])
    draw.text((R + 16, y + 8), "Palette saved.", font=font_body, fill=glow["warm"])
    draw.text((R + 16, y + 26), "Click to view file.",
              font=font_small, fill=glow["dim"])
    y += th_t + 22

    # Progress.
    draw.text((R, y), "Progress", font=font_h2, fill=glow["warm"])
    y += 22
    pr_h = 8
    pr_w = col_w - 30
    draw.rounded_rectangle([R, y, R + pr_w, y + pr_h], radius=pr_h // 2,
                           fill=hearth["base"])
    draw.rounded_rectangle([R, y, R + int(pr_w * 0.62), y + pr_h],
                           radius=pr_h // 2, fill=mist["blue"])
    draw.text((R + pr_w + 8, y - 2), "62%", font=font_small, fill=glow["dim"])
    y += pr_h + 22

    # Scrollbar sample.
    draw.text((R, y), "Scrollbar", font=font_h2, fill=glow["warm"])
    y += 22
    sc_w = col_w - 30
    sc_h = 8
    draw.rounded_rectangle([R, y, R + sc_w, y + sc_h], radius=sc_h // 2,
                           fill=hearth["base"])
    th_thumb = int(sc_w * 0.25)
    draw.rounded_rectangle([R + 30, y, R + 30 + th_thumb, y + sc_h],
                           radius=sc_h // 2, fill=glow["dim"])
    y += sc_h + 22

    # Code chips (for completeness — show all 5 spark + 4 mist hexes inline).
    draw.text((R, y), "Tier roles", font=font_h2, fill=glow["warm"])
    y += 22
    role_y = y
    for label, color in [
        ("spark.red",    spark["red"]),
        ("spark.orange", spark["orange"]),
        ("spark.amber",  spark["amber"]),
        ("spark.green",  spark["green"]),
        ("spark.violet", spark["violet"]),
        ("mist.deep",    mist["deep"]),
        ("mist.teal",    mist["teal"]),
        ("mist.blue",    mist["blue"]),
        ("mist.sky",     mist["sky"]),
    ]:
        draw.rectangle([R, role_y + 4, R + 14, role_y + 14], fill=color,
                       outline=hearth["high"])
        draw.text((R + 22, role_y), label, font=font_small, fill=glow["dim"])
        role_y += 16

    return img


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--palette", type=Path, default=REPO / "palette.toml",
                    help="Palette TOML to render from (default: palette.toml).")
    ap.add_argument("--title", type=str, default=None,
                    help="Title shown in window chrome / mockup labels. "
                         "Default: derived from palette filename.")
    ap.add_argument("--out-full",        type=Path)
    ap.add_argument("--out-thumb",       type=Path)
    ap.add_argument("--out-swatches",    type=Path)
    ap.add_argument("--out-filemanager", type=Path)
    ap.add_argument("--out-textsample",  type=Path)
    ap.add_argument("--out-ui-catalog",  type=Path)
    args = ap.parse_args()

    if not any([args.out_full, args.out_thumb, args.out_swatches,
                args.out_filemanager, args.out_textsample, args.out_ui_catalog]):
        ap.error("at least one --out-* flag is required")

    palette = load_palette(args.palette)
    title = args.title or derive_title(args.palette)

    # Desktop view (full + thumb share a single render).
    if args.out_full or args.out_thumb:
        full = render_desktop(1920, 1214, palette, title)
        if args.out_full:
            args.out_full.parent.mkdir(parents=True, exist_ok=True)
            full.save(args.out_full, quality=88, optimize=True)
            print(f"Wrote {args.out_full}")
        if args.out_thumb:
            thumb = full.resize((512, 324), Image.LANCZOS)
            args.out_thumb.parent.mkdir(parents=True, exist_ok=True)
            thumb.save(args.out_thumb, optimize=True)
            print(f"Wrote {args.out_thumb}")

    if args.out_swatches:
        img = render_swatches(palette, title)
        args.out_swatches.parent.mkdir(parents=True, exist_ok=True)
        img.save(args.out_swatches, optimize=True)
        print(f"Wrote {args.out_swatches}")

    if args.out_filemanager:
        img = render_filemanager(palette, title)
        args.out_filemanager.parent.mkdir(parents=True, exist_ok=True)
        img.save(args.out_filemanager, optimize=True)
        print(f"Wrote {args.out_filemanager}")

    if args.out_textsample:
        img = render_textsample(palette, title)
        args.out_textsample.parent.mkdir(parents=True, exist_ok=True)
        img.save(args.out_textsample, optimize=True)
        print(f"Wrote {args.out_textsample}")

    if args.out_ui_catalog:
        img = render_ui_catalog(palette, title)
        args.out_ui_catalog.parent.mkdir(parents=True, exist_ok=True)
        img.save(args.out_ui_catalog, optimize=True)
        print(f"Wrote {args.out_ui_catalog}")


if __name__ == "__main__":
    main()

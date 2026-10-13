"""Render preview + review images for the Umber palette family.

Outputs (one per --out-* flag, all independent and optional):

- --out-full PATH        desktop with wallpaper + panel + faux window (1920x1214)
- --out-thumb PATH       same, downscaled to 512x324
- --out-swatches PATH    pigment-tier grid: hearth, glow, mist, spark, accent (900x320)
- --out-filemanager PATH Dolphin-style window (1200x760)
- --out-textsample PATH  VSCode-style editor surface (1200x760)
- --out-ui-catalog PATH  control gallery (1200x760)

The desktop view (--out-full / --out-thumb) is the synthetic Plasma
preview that ships inside the LookAndFeel package. The other views are
review-only artifacts used to evaluate a palette before regenerating
consumer files.

Colors come from palette_lib.prepare(). Every UI and code element is
drawn with the resolved semantic role (roles.toml) that the real theme
file uses for the same element: window chrome and the Dolphin view follow
scripts/templates/Umber.colors.tmpl, the editor and most controls follow
Umber-color-theme.json.tmpl, and the window buttons and panel follow
store-preview.svg.tmpl. Only the swatch grid, the wallpaper and the
stand-in icon fills read pigment tiers directly.

A run takes one palette (--palette, default palette.toml) and one title
(--title, default derived from the palette filename) and produces only
the views requested by --out-* flags.
"""

import argparse
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

import palette_lib

REPO = palette_lib.REPO


# --------------------------------------------------------------------------- #
# palette                                                                     #
# --------------------------------------------------------------------------- #

def _hex_rgb(h):
    h = h.lstrip("#")
    return (int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def load_palette(path):
    """Palette dict with pal["role"] merged from roles.toml and resolved to hex."""
    return palette_lib.prepare(path)


def roles(pal):
    """pal["role"] as RGB tuples, nested tables kept: R["syntax"]["keyword"]."""
    def conv(table):
        return {k: conv(v) if isinstance(v, dict) else _hex_rgb(v) for k, v in table.items()}
    return conv(pal["role"])


def tier(pal, table, key):
    """A pigment straight from a tier table: swatches, wallpaper and stand-in icons only."""
    return _hex_rgb(pal[table][key])


# Swatch grid: (tier table, [(key, label), ...]). Labels name each pigment's
# main job; roles.toml is the authority on what uses it.
SWATCH_ROWS = [
    ("hearth", [("0", "0 · bg"), ("1", "1 · panel"), ("2", "2 · raised"),
                ("3", "3 · active"), ("4", "4 · outline"), ("hover", "hover")]),
    ("glow",   [("0", "0 · muted"), ("1", "1 · body"), ("2", "2 · emphasis"),
                ("3", "3 · strong")]),
    ("mist",   [("0", "0 · type"), ("1", "1 · info, regex"), ("2", "2 · link, fn"),
                ("3", "3 · comment")]),
    ("spark",  [(k, k) for k in ("red", "orange", "amber", "green", "violet")]),
    ("accent", [("signature", "signature"), ("signature_hover", "signature hover"),
                ("highlight", "highlight"), ("highlight_alt", "highlight alt")]),
]

# Accent swatches label themselves in the palette's own on-colors.
ACCENT_ON = {"signature": "on_signature", "signature_hover": "on_signature",
             "highlight": "highlight_text", "highlight_alt": "highlight_text"}


def tier_rows(pal):
    """[(table, [(key, label, rgb, hex), ...]), ...] for the swatch grid."""
    return [(table, [(key, label, tier(pal, table, key), pal[table][key])
                     for key, label in cells])
            for table, cells in SWATCH_ROWS]


def _wallpaper_glow(pal):
    """Horizon-band tone derived from the palette so cool palettes get cool bands."""
    return lerp(tier(pal, "hearth", "0"), tier(pal, "glow", "2"), 0.45)


# --------------------------------------------------------------------------- #
# common helpers                                                              #
# --------------------------------------------------------------------------- #

def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _first_font(candidates, size, fallback):
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return fallback(size)


def load_font(size):
    return _first_font([
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ], size, lambda s: ImageFont.load_default())


def load_mono(size):
    return _first_font([
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/noto/NotoMono-Regular.ttf",
    ], size, load_font)


def load_mono_italic(size):
    return _first_font([
        "/usr/share/fonts/TTF/DejaVuSansMono-Oblique.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono-Oblique.ttf",
    ], size, load_mono)


def load_symbols(size):
    """A face with arrows and the multiplication sign (Noto Sans lacks the arrows)."""
    return _first_font([
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ], size, load_font)


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


def _backdrop(R):
    """Desktop tone behind the review windows."""
    return lerp(R["bg"], (0, 0, 0), 0.35)


def _window_chrome(img, x, y, w, h, title, R, font_title, titlebar_h, body, rule):
    """Breeze-style window frame. Returns the client box (x, y, w, h).

    Titlebar: Plasma [WM] activeBackground = role.bg_raised, activeForeground
    = role.fg. Buttons follow store-preview.svg.tmpl: the outermost in
    role.accent, the others role.fg_muted. `body` fills the client area;
    `rule` is the line under the titlebar (None when a toolbar continues the
    header, as Plasma's [Colors:Header] does).
    """
    draw = ImageDraw.Draw(img, "RGBA")
    radius = 8
    for i in range(4):
        alpha = 36 - i * 8
        draw.rounded_rectangle(
            [x - i * 2, y - i, x + w + i * 2, y + h + i * 3],
            radius=radius + i, fill=R["shadow"] + (alpha,))
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=body)
    draw.rounded_rectangle([x, y, x + w, y + titlebar_h], radius=radius,
                           fill=R["bg_raised"], corners=(True, True, False, False))
    if rule is not None:
        draw.line([x, y + titlebar_h, x + w, y + titlebar_h], fill=rule)
    th = text_h(draw, title, font_title)
    draw.text((x + 16, y + (titlebar_h - th) // 2 - 2),
              title, font=font_title, fill=R["fg"])
    btn_r = max(6, titlebar_h // 4)
    by = y + titlebar_h // 2
    bx = x + w - 18
    for color in (R["accent"], R["fg_muted"], R["fg_muted"]):
        draw.ellipse([bx - btn_r, by - btn_r, bx + btn_r, by + btn_r], fill=color)
        bx -= btn_r * 2 + 8
    return x, y + titlebar_h, w, h - titlebar_h


def _draw_runs(draw, x, y, runs, font):
    """Draw [(text, color), ...] left to right; returns the end x."""
    for text, color in runs:
        draw.text((x, y), text, font=font, fill=color)
        x += font.getlength(text)
    return x


def _folder_icon(draw, x, y, s, fill, outline=None):
    """Stand-in folder glyph inside an s x s box."""
    draw.rounded_rectangle([x, y + s // 6, x + s * 2 // 5, y + s // 3 + 1], radius=1, fill=fill)
    draw.rounded_rectangle([x, y + s // 4, x + s, y + s * 5 // 6], radius=2,
                           fill=fill, outline=outline)


def _page_icon(draw, x, y, s, color):
    """Stand-in document glyph inside an s x s box."""
    w = s * 3 // 4
    left = x + (s - w) // 2
    draw.rectangle([left, y, left + w, y + s], outline=color)
    for i in (1, 2, 3):
        ly = y + i * s // 4
        draw.line([left + 3, ly, left + w - 3, ly], fill=color)


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


def base_color(y_frac, deep, base, elev):
    if y_frac < HORIZON:
        return lerp(deep, elev, y_frac / HORIZON)
    return lerp(elev, base, (y_frac - HORIZON) / (1.0 - HORIZON))


def render_wallpaper(width, height, pal, seed=1729):
    rng = random.Random(seed)
    img = Image.new("RGB", (width, height))
    px = img.load()
    deep, base, elev = (tier(pal, "hearth", k) for k in ("0", "1", "2"))
    band = _wallpaper_glow(pal)
    for y in range(height):
        y_frac = y / (height - 1)
        row = lerp(base_color(y_frac, deep, base, elev), band, horizon_weight(y_frac) * 0.55)
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

def _draw_panel(draw, w, h, R, font_small):
    """Plasma panel after store-preview.svg.tmpl: role.bg bar, role.accent launcher, role.fg clock."""
    panel_h = max(36, h // 22)
    y0 = h - panel_h
    draw.rectangle([0, y0, w, h], fill=R["bg"])
    draw.line([0, y0, w, y0], fill=R["border"])
    pad = panel_h // 4
    d = panel_h - 2 * pad
    draw.ellipse([pad, y0 + pad, pad + d, y0 + pad + d], fill=R["accent"])
    # Task buttons: the focused one is bg_active with an accent indicator line.
    x = pad * 3 + d
    for i in range(3):
        x2 = x + panel_h * 2
        draw.rectangle([x, y0 + pad, x2, h - pad], fill=R["bg_active"] if i == 0 else R["bg_raised"])
        if i == 0:
            draw.rectangle([x, h - pad - 2, x2, h - pad], fill=R["accent"])
        x = x2 + pad
    clock = "20:42"
    tw = text_w(draw, clock, font_small)
    th = text_h(draw, clock, font_small)
    draw.text((w - tw - pad * 3, y0 + (panel_h - th) // 2 - 2),
              clock, font=font_small, fill=R["fg"])


def concept_blurb(pal, width=36, max_lines=3):
    """Headline + wrapped body lines from the palette's [meta] concept.

    "Indigo night. Deep ultramarine ground, ..." -> ("Indigo night", [...]).
    """
    import textwrap
    concept = pal.get("meta", {}).get("concept") or pal.get("meta", {}).get("description", "")
    sentences = [x.strip() for x in concept.split(". ") if x.strip()]
    if not sentences:
        return "Umber", []
    headline = sentences[0].rstrip(".")
    body = sentences[1].rstrip(".") + "." if len(sentences) > 1 else ""
    return headline, textwrap.wrap(body, width, break_on_hyphens=False)[:max_lines]


def _draw_window(img, x, y, w, h, title, pal, R, font_title, font_body):
    titlebar_h = max(28, h // 14)
    radius = 8
    _, top, _, _ = _window_chrome(img, x, y, w, h, title, R, font_title, titlebar_h,
                                  body=R["bg"], rule=R["border"])
    draw = ImageDraw.Draw(img, "RGBA")
    S, B, sel = R["syntax"], R["bracket"], R["on_selection"]

    # Sidebar = Plasma [Colors:Window]; the main pane is [Colors:View].
    side_w = w // 4
    draw.rounded_rectangle([x, top + 1, x + side_w, y + h], radius=radius,
                           fill=R["bg_panel"], corners=(False, False, False, True))
    item_h = max(22, h // 18)
    iy = top + 14
    rows = [  # (label, stand-in icon fill, selected)
        ("Hearth", tier(pal, "hearth", "4"),     False),
        ("Glow",   tier(pal, "glow", "2"),       True),
        ("Mist",   tier(pal, "mist", "2"),       False),
        ("Spark",  tier(pal, "spark", "amber"),  False),
    ]
    for label, icon, selected in rows:
        if selected:
            draw.rounded_rectangle(
                [x + 8, iy - 4, x + side_w - 8, iy + item_h - 4],
                radius=4, fill=R["selection_bg"])
            text_color, outline = sel["fg_soft"], sel["decoration"]
        else:
            text_color, outline = R["fg"], R["border"]
        sw = item_h - 8
        draw.rectangle(
            [x + 16, iy + (item_h - sw) // 2 - 2,
             x + 16 + sw, iy + (item_h + sw) // 2 - 2],
            fill=icon, outline=outline)
        draw.text((x + 16 + sw + 10, iy - 2), label, font=font_body, fill=text_color)
        iy += item_h + 6

    # Main content.
    cx = x + side_w + 24
    cy = top + 22
    headline, blurb = concept_blurb(pal)
    draw.text((cx, cy), headline, font=font_title, fill=R["fg_emphasis"])
    cy += font_title.size + 8
    for line in blurb:
        draw.text((cx, cy), line, font=font_body, fill=R["fg_muted"])
        cy += font_body.size + 4
    cy += 10

    # Code block on a widget surface; tokens use the VSCode token roles.
    block_w = w - side_w - 48
    block_h = max(70, h // 4)
    draw.rounded_rectangle([cx, cy, cx + block_w, cy + block_h],
                           radius=4, fill=R["bg_panel"])
    code_y = cy + 12
    _draw_runs(draw, cx + 14, code_y, [
        ("def ", S["storage"]), ("umber", S["function"]), ("(", B["1"]),
        ("palette", S["parameter"]), (")", B["1"]), (":", S["punctuation"]),
    ], font_body)
    code_y += font_body.size + 6
    _draw_runs(draw, cx + 14, code_y, [
        ("    return ", S["keyword"]), ('"calm"', S["string"]),
    ], font_body)

    # Status chips: status text on bg_panel (the pairs palette_audit checks).
    sy = cy + block_h + 14
    sx = cx
    for label, color in [
        ("OK",      R["success"]),
        ("Warning", R["warning"]),
        ("Error",   R["error"]),
        ("Link",    R["link"]),
    ]:
        cw = text_w(draw, label, font_body) + 16
        ch = font_body.size + 8
        draw.rounded_rectangle([sx, sy, sx + cw, sy + ch],
                               radius=ch // 2, fill=R["bg_panel"])
        draw.text((sx + 8, sy + 2), label, font=font_body, fill=color)
        sx += cw + 8


def render_desktop(width, height, pal, title):
    R = roles(pal)
    img = render_wallpaper(width, height, pal)
    font_title = load_font(max(14, height // 36))
    font_body  = load_font(max(11, height // 56))
    font_small = load_font(max(11, height // 60))

    win_w = int(width * 0.72)
    win_h = int(height * 0.66)
    win_x = (width - win_w) // 2
    win_y = int(height * 0.10)
    _draw_window(img, win_x, win_y, win_w, win_h, title, pal, R, font_title, font_body)

    draw = ImageDraw.Draw(img)
    _draw_panel(draw, width, height, R, font_small)
    return img


# --------------------------------------------------------------------------- #
# review view: swatches grid                                                  #
# --------------------------------------------------------------------------- #

def render_swatches(pal, title, width=900, height=320):
    R = roles(pal)
    img = Image.new("RGB", (width, height), color=R["bg"])
    draw = ImageDraw.Draw(img)
    font_title = load_font(20)
    font_label = load_font(11)
    font_hex   = load_mono(10)

    draw.text((20, 14), title, font=font_title, fill=R["fg_emphasis"])
    draw.text((20, 40), "tier · job · hex", font=font_label, fill=R["fg_muted"])

    rows = tier_rows(pal)
    grid_top = 64
    cell_h = 42
    pad = 7
    label_w = 70
    max_cells = max(len(cells) for _, cells in rows)
    cell_w = (width - 40 - label_w - (max_cells - 1) * pad) // max_cells
    for ri, (table, cells) in enumerate(rows):
        ry = grid_top + ri * (cell_h + pad)
        draw.text((20, ry + (cell_h - 16) // 2), table, font=font_label, fill=R["fg"])
        cx = 20 + label_w
        for key, label, rgb, hex_str in cells:
            draw.rectangle([cx, ry, cx + cell_w, ry + cell_h], fill=rgb, outline=R["border"])
            if table == "accent":
                text_fg = tier(pal, "accent", ACCENT_ON[key])
            else:
                lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                text_fg = R["bg"] if lum > 140 else R["fg_strong"]
            draw.text((cx + 8, ry + 5), label, font=font_label, fill=text_fg)
            draw.text((cx + 8, ry + 23), hex_str.upper(), font=font_hex, fill=text_fg)
            cx += cell_w + pad
    return img


# --------------------------------------------------------------------------- #
# review view: file manager (Dolphin-shaped, Umber.colors.tmpl)               #
# --------------------------------------------------------------------------- #

def render_filemanager(pal, title, width=1200, height=760):
    R = roles(pal)
    sel = R["on_selection"]
    img = Image.new("RGB", (width, height), color=_backdrop(R))
    font_title = load_font(15)
    font_body  = load_font(13)
    font_small = load_font(11)
    font_mono  = load_mono(12)
    font_sym   = load_symbols(15)

    win_x, win_y, win_w, win_h = 40, 40, width - 80, height - 80
    # [Colors:Window] body; the toolbar continues the [Colors:Header] titlebar.
    cx, cy, cw, ch = _window_chrome(
        img, win_x, win_y, win_w, win_h, f"Documents — {title}", R, font_title,
        titlebar_h=max(30, win_h // 22), body=R["bg_panel"], rule=None)

    draw = ImageDraw.Draw(img, "RGBA")

    # Toolbar ([Colors:Header]).
    tb_h = 36
    draw.rectangle([cx, cy, cx + cw, cy + tb_h], fill=R["bg_raised"])
    draw.line([cx, cy + tb_h, cx + cw, cy + tb_h], fill=R["border"])
    nav_x = cx + 14
    for glyph, color in [("←", R["fg"]), ("→", R["fg_muted"]),   # forward: disabled
                         ("↑", R["fg"]), ("↻", R["fg"])]:
        draw.text((nav_x, cy + 8), glyph, font=font_sym, fill=color)
        nav_x += 26
    # Breadcrumb: parent crumbs inactive, current folder normal.
    _draw_runs(draw, nav_x + 16, cy + 9, [
        ("Home", R["fg_muted"]), (" / ", R["fg_muted"]),
        ("user", R["fg_muted"]), (" / ", R["fg_muted"]),
        ("Documents", R["fg"]),
    ], font_body)

    # Places panel ([Colors:Window]).
    sb_x = cx
    sb_y = cy + tb_h
    sb_w = 230
    sb_h = ch - tb_h
    draw.line([sb_x + sb_w, sb_y, sb_x + sb_w, sb_y + sb_h], fill=R["border"])

    draw.text((sb_x + 16, sb_y + 14), "Places", font=font_small, fill=R["fg_muted"])
    places = [  # (label, stand-in icon fill, selected)
        ("Home",      tier(pal, "mist", "2"),        False),
        ("Documents", tier(pal, "mist", "1"),        True),
        ("Downloads", tier(pal, "mist", "3"),        False),
        ("Pictures",  tier(pal, "mist", "0"),        False),
        ("Music",     tier(pal, "spark", "violet"),  False),
        ("Trash",     tier(pal, "spark", "red"),     False),
    ]
    item_h = 30
    item_y = sb_y + 34
    for label, icon, selected in places:
        if selected:
            draw.rounded_rectangle(
                [sb_x + 8, item_y, sb_x + sb_w - 8, item_y + item_h - 2],
                radius=4, fill=R["selection_bg"])
            txt_color, icon_outline = sel["fg_soft"], sel["decoration"]
        else:
            txt_color, icon_outline = R["fg"], R["border"]
        draw.rectangle(
            [sb_x + 18, item_y + 7, sb_x + 32, item_y + item_h - 9],
            fill=icon, outline=icon_outline)
        draw.text((sb_x + 42, item_y + 6), label, font=font_body, fill=txt_color)
        item_y += item_h + 2

    item_y += 8
    draw.text((sb_x + 16, item_y), "Devices", font=font_small, fill=R["fg_muted"])
    item_y += 22
    for label, icon in [("SSD", tier(pal, "mist", "3")), ("USB Drive", tier(pal, "mist", "1"))]:
        draw.rectangle(
            [sb_x + 18, item_y + 7, sb_x + 32, item_y + item_h - 9],
            fill=icon, outline=R["border"])
        draw.text((sb_x + 42, item_y + 6), label, font=font_body, fill=R["fg"])
        item_y += item_h + 2

    # File list ([Colors:View]: BackgroundNormal, BackgroundAlternate rows).
    fl_x = sb_x + sb_w + 1
    fl_y = sb_y + 1
    fl_w = cw - sb_w - 1
    fl_h = sb_h - 1
    draw.rectangle([fl_x, fl_y, fl_x + fl_w, fl_y + fl_h], fill=R["bg"])

    # Column header (section-header surface, as VSCode's sideBarSectionHeader).
    hdr_h = 28
    draw.rectangle([fl_x, fl_y, fl_x + fl_w, fl_y + hdr_h], fill=R["bg_raised"])
    draw.line([fl_x, fl_y + hdr_h, fl_x + fl_w, fl_y + hdr_h], fill=R["border"])
    cols = [("Name", 16), ("Size", fl_w - 240), ("Modified", fl_w - 130)]
    for label, dx in cols:
        draw.text((fl_x + dx, fl_y + 7), label, font=font_small, fill=R["fg"])

    files = [
        ("Projects",        "—",       "Apr 28 14:02", "folder"),
        ("Reports",         "—",       "Apr 27 09:11", "folder"),
        ("Receipts",        "—",       "Apr 21 17:43", "folder"),
        ("notes.md",        "12.4 KB", "Apr 28 16:33", "selected"),
        ("budget.numbers",  "84.0 KB", "Apr 26 11:08", "selected"),
        ("invoice-042.pdf", "210 KB",  "Apr 25 22:15", "hover"),
        ("portrait.jpg",    "1.4 MB",  "Apr 24 08:30", "file"),
        ("spec.txt",        "3.1 KB",  "Apr 22 19:57", "file"),
        ("agenda.docx",     "27.0 KB", "Apr 22 09:00", "file"),
        ("config.toml",     "1.2 KB",  "Apr 21 13:14", "file"),
        ("archive.tar.gz",  "8.7 MB",  "Apr 18 10:42", "file"),
        ("README",          "0.8 KB",  "Apr 16 23:01", "file"),
    ]
    folder_fill = tier(pal, "mist", "2")   # stand-in icon, same as the Home place
    row_h = 30
    row_y = fl_y + hdr_h + 1
    for i, (name, size, mtime, state) in enumerate(files):
        alternate = i % 2 == 1
        box = [fl_x + 4, row_y, fl_x + fl_w - 4, row_y + row_h - 2]
        if alternate:
            draw.rectangle([fl_x, row_y, fl_x + fl_w, row_y + row_h - 1], fill=R["bg_panel"])
        if state == "selected":
            draw.rounded_rectangle(box, radius=3,
                                   fill=R["selection_alt"] if alternate else R["selection_bg"])
            n_color = m_color = sel["fg_soft"]
        elif state == "hover":
            draw.rounded_rectangle(box, radius=3, fill=R["bg_raised"])
            n_color, m_color = R["fg"], R["fg_muted"]
        else:
            n_color, m_color = R["fg"], R["fg_muted"]
        if state == "folder":
            _folder_icon(draw, fl_x + 14, row_y + 6, 16, folder_fill)
        else:
            _page_icon(draw, fl_x + 14, row_y + 6, 16, m_color)
        draw.text((fl_x + 40, row_y + 6), name, font=font_body, fill=n_color)
        draw.text((fl_x + cols[1][1], row_y + 7), size, font=font_mono, fill=m_color)
        draw.text((fl_x + cols[2][1], row_y + 7), mtime, font=font_mono, fill=m_color)
        row_y += row_h
        if row_y > fl_y + fl_h - 30:
            break

    # Status bar ([Colors:Window]).
    st_h = 26
    st_y = win_y + win_h - st_h
    draw.rounded_rectangle([cx, st_y, cx + cw, st_y + st_h], radius=8,
                           fill=R["bg_panel"], corners=(False, False, True, True))
    draw.line([cx, st_y, cx + cw, st_y], fill=R["border"])
    draw.text((cx + 16, st_y + 6), "12 items · 3 folders · 2 selected (96.4 KB)",
              font=font_small, fill=R["fg"])

    return img


# --------------------------------------------------------------------------- #
# review view: text sample (VSCode-shaped, Umber-color-theme.json.tmpl)       #
# --------------------------------------------------------------------------- #

def render_textsample(pal, title, width=1200, height=760):
    R = roles(pal)
    S, B = R["syntax"], R["bracket"]
    img = Image.new("RGB", (width, height), color=_backdrop(R))
    font_title = load_font(15)
    font_body  = load_font(12)
    font_small = load_font(11)
    font_mono  = load_mono(13)
    font_ital  = load_mono_italic(13)
    font_sym   = load_symbols(12)

    win_x, win_y, win_w, win_h = 40, 40, width - 80, height - 80
    # titleBar.activeBackground / activeForeground / border.
    cx, cy, cw, ch = _window_chrome(
        img, win_x, win_y, win_w, win_h, f"render.py — {title}", R, font_title,
        titlebar_h=max(30, win_h // 22), body=R["bg"], rule=R["divider"])

    draw = ImageDraw.Draw(img, "RGBA")

    # Tab strip: editorGroupHeader.tabsBackground, tab.* colors.
    tab_h = 34
    draw.rectangle([cx, cy + 1, cx + cw, cy + tab_h], fill=R["bg_panel"])
    tab_x = cx
    active_span = None
    for label, active in [("render.py", True), ("palette.toml", False), ("README.md", False)]:
        tw = int(font_body.getlength(label)) + 32
        if active:
            draw.rectangle([tab_x, cy + 1, tab_x + tw, cy + tab_h], fill=R["bg"])
            draw.rectangle([tab_x, cy + 1, tab_x + tw, cy + 2], fill=R["accent"])  # activeBorderTop
            tcolor = R["fg_emphasis"]
            active_span = (tab_x, tab_x + tw)
        else:
            tcolor = R["fg_muted"]
        draw.text((tab_x + 16, cy + 9), label, font=font_body, fill=tcolor)
        draw.line([tab_x + tw, cy + 1, tab_x + tw, cy + tab_h], fill=R["divider"])   # tab.border
        tab_x += tw + 1
    # editorGroupHeader.tabsBorder runs under every tab but the active one.
    draw.line([active_span[1], cy + tab_h, cx + cw, cy + tab_h], fill=R["divider"])

    # Breadcrumbs: breadcrumb.background / foreground / focusForeground.
    bc_h = 22
    bc_y = cy + tab_h + 1
    _draw_runs(draw, cx + 16, bc_y + 4, [
        ("scripts", R["fg_muted"]), ("  ›  ", R["fg_muted"]),
        ("render.py", R["fg_muted"]), ("  ›  ", R["fg_muted"]),
        ("render", R["fg"]),
    ], font_small)

    # Editor: gutter shares editor.background.
    st_h = 24
    gutter_w = 56
    gx, gy = cx, bc_y + bc_h
    gh = (win_y + win_h - st_h) - gy
    ruler_w = 14
    ruler_x = cx + cw - ruler_w
    mm_w = 80
    mm_x = ruler_x - mm_w
    code_x = gx + gutter_w + 14
    code_y = gy + 8
    line_h = font_mono.size + 6
    char_w = font_mono.getlength("M")

    # Token kinds -> (color, italic) per tokenColors / semanticTokenColors
    # (Python grammar scopes, Pylance semantic tokens, bracket-pair colorization).
    K = {
        "comment": (S["comment"], True),       # comment                       (italic)
        "keyword": (S["keyword"], False),      # keyword.control
        "storage": (S["storage"], False),      # storage.type (def, r-prefix)
        "ns":      (S["namespace"], False),    # semantic namespace (modules)
        "class":   (S["class"], False),        # semantic class (Path, dict, ValueError)
        "fn":      (S["function"], False),     # entity.name.function / semantic method
        "param":   (S["parameter"], True),     # variable.parameter              (italic)
        "var":     (S["variable"], False),     # semantic variable
        "const":   (S["constant"], False),     # constant.other.caps / *.readonly
        "num":     (S["number"], False),       # constant.numeric
        "str":     (S["string"], False),       # string, docstrings, quote marks
        "regex":   (S["regex"], False),        # string.regexp
        "op":      (S["operator"], False),     # keyword.operator.assignment / comparison
        "punc":    (S["punctuation"], False),  # : . ->
        "b1":      (B["1"], False),            # editorBracketHighlight.foreground1
        "b2":      (B["2"], False),            # editorBracketHighlight.foreground2
        "ws":      (R["fg"], False),
    }

    lines = [
        [("# Palette renderer: tiers in, roles out.", "comment")],
        [],
        [("import", "keyword"), (" ", "ws"), ("json", "ns")],
        [("from", "keyword"), (" ", "ws"), ("pathlib", "ns"), (" ", "ws"),
         ("import", "keyword"), (" ", "ws"), ("Path", "class")],
        [],
        [("PALETTE_VERSION", "const"), (" = ", "op"), ("17", "num")],
        [("RE_HEX", "const"), (" = ", "op"), ("r", "storage"), ("'", "str"),
         ("^#[0-9A-F]{6}$", "regex"), ("'", "str")],
        [],
        [("def", "storage"), (" ", "ws"), ("render", "fn"), ("(", "b1"),
         ("palette", "param"), (":", "punc"), (" ", "ws"), ("dict", "class"),
         (")", "b1"), (" -> ", "punc"), ("Image", "class"), (":", "punc")],
        [("    ", "ws"), ('"""Render the preview."""', "str")],
        [("    ", "ws"), ("result", "var"), (" = ", "op"), ("[", "b1"),
         ("'header'", "str"), ("]", "b1")],
        [("    ", "ws"), ("for", "keyword"), (" ", "ws"), ("tier", "var"), (" ", "ws"),
         ("in", "keyword"), (" ", "ws"), ("palette", "param"), (":", "punc")],
        [("        ", "ws"), ("if", "keyword"), (" ", "ws"), ("tier", "var"),
         (" == ", "op"), ("'spark'", "str"), (":", "punc")],
        [("            ", "ws"), ("result", "var"), (".", "punc"), ("append", "fn"),
         ("(", "b1"), ("str", "class"), ("(", "b2"), ("tier", "var"), (")", "b2"), (")", "b1")],
        [("        ", "ws"), ("else", "keyword"), (":", "punc")],
        [("            ", "ws"), ("raise", "keyword"), (" ", "ws"), ("ValueError", "class"),
         ("(", "b1"), ("'unknown tier'", "str"), (")", "b1")],
        [("    ", "ws"), ("return", "keyword"), (" ", "ws"), ("result", "var")],
        [],
        [("unused_var", "var", "warning"), (" = ", "op"), ("42", "num")],
        [("undefined", "var", "error"), ("(", "b1"), (")", "b1")],
    ]
    texts = ["".join(seg[0] for seg in segs) for segs in lines]
    cursor_line = 15                     # 0-based; status bar reads 1-based
    cursor_col = len(texts[cursor_line])
    sel_lines = range(10, 13)            # full lines 11-13 selected
    find_word = "result"
    find_hits = [(i, t.find(find_word)) for i, t in enumerate(texts) if find_word in t]
    find_current = 1                     # "2 of 3"

    def line_top(i):
        return code_y + i * line_h - 3

    # Current line: editor.lineHighlightBackground (content area only).
    draw.rectangle([gx + gutter_w, line_top(cursor_line), mm_x - 1,
                    line_top(cursor_line) + line_h - 1], fill=R["line_highlight"])
    # Find matches: findMatchBackground (66) / findMatchHighlightBackground (33).
    for n, (i, col) in enumerate(find_hits):
        x0 = code_x + col * char_w
        draw.rectangle([x0, line_top(i) + 1, x0 + len(find_word) * char_w, line_top(i) + line_h - 2],
                       fill=R["attention"] + (0x66 if n == find_current else 0x33,))
    # Selection: editor.selectionBackground = selection_bg at 2E, to end of text + EOL.
    for i in sel_lines:
        draw.rectangle([code_x, line_top(i), code_x + (len(texts[i]) + 1) * char_w,
                        line_top(i) + line_h - 1],
                       fill=R["selection_bg"] + (0x2E,))

    # Gutter: line numbers, git decorations.
    gutter_marks = {13: R["diff_modified"], 18: R["diff_added"], 19: R["diff_added"]}
    for i in range(len(lines)):
        ly = code_y + i * line_h
        num_color = R["fg"] if i == cursor_line else R["fg_muted"]
        draw.text((gx + 10, ly), str(i + 1).rjust(3), font=font_mono, fill=num_color)
        if i in gutter_marks:
            draw.rectangle([gx + gutter_w - 4, line_top(i), gx + gutter_w - 2,
                            line_top(i) + line_h - 1], fill=gutter_marks[i])

    # Code.
    for i, segs in enumerate(lines):
        ly = code_y + i * line_h
        x_cursor = code_x
        for seg in segs:
            text, kind = seg[0], seg[1]
            color, italic = K[kind]
            font = font_ital if italic else font_mono
            draw.text((x_cursor, ly), text, font=font, fill=color)
            tw = font_mono.getlength(text)
            if len(seg) > 2:   # editorWarning / editorError squiggle
                _draw_squiggle(draw, x_cursor, ly + font_mono.size + 2,
                               x_cursor + tw, R[seg[2]])
            x_cursor += tw

    # Cursor: editorCursor.foreground.
    cursor_x = code_x + cursor_col * char_w
    cursor_y = code_y + cursor_line * line_h
    draw.line([cursor_x, cursor_y, cursor_x, cursor_y + font_mono.size + 2],
              fill=R["cursor"], width=2)

    # Find widget: editorWidget.background / border, focused input = focusBorder.
    fw_w, fw_h = 290, 34
    fw_x = mm_x - fw_w - 16
    fw_y = gy
    for k in range(3):
        draw.rectangle([fw_x - k, fw_y, fw_x + fw_w + k, fw_y + fw_h + k + 1],
                       fill=R["shadow"] + (40 - k * 12,))
    draw.rectangle([fw_x, fw_y, fw_x + fw_w, fw_y + fw_h], fill=R["bg_panel"], outline=R["border"])
    inp = [fw_x + 8, fw_y + 6, fw_x + 160, fw_y + fw_h - 6]
    draw.rectangle(inp, fill=R["bg"], outline=R["focus_ring"])
    draw.text((inp[0] + 6, inp[1] + 4), find_word, font=font_body, fill=R["fg"])
    draw.text((inp[2] + 10, inp[1] + 4), f"{find_current + 1} of {len(find_hits)}",
              font=font_body, fill=R["fg"])
    gx_ = fw_x + fw_w - 62
    for glyph in ("↑", "↓", "×"):
        draw.text((gx_, inp[1] + 3), glyph, font=font_sym, fill=R["fg"])
        gx_ += 20

    # Minimap: tokens shrunk onto editor.background.
    mm_y = gy + 8
    bar_h = 4
    for i, segs in enumerate(lines):
        char_count = sum(len(seg[0]) for seg in segs)
        if not char_count:
            continue
        dominant = next((K[seg[1]][0] for seg in segs
                         if seg[1] not in ("ws", "var", "param", "op", "punc", "b1", "b2")),
                        R["fg"])
        indent = len(texts[i]) - len(texts[i].lstrip())
        bx0 = mm_x + 6 + indent
        bar_w = min(mm_w - 12 - indent, max(2, (char_count - indent)))
        by_ = mm_y + i * bar_h
        draw.rectangle([bx0, by_, bx0 + bar_w, by_ + bar_h - 2],
                       fill=lerp(dominant, R["bg"], 0.4))

    # Overview ruler: border, find / warning / error / git markers.
    draw.line([ruler_x, gy, ruler_x, gy + gh], fill=R["divider"])
    marks = [(i, R["attention"]) for i, _ in find_hits]
    marks += [(18, R["warning"]), (19, R["error"])]
    for i, color in marks:
        my = line_top(i) + line_h // 2
        draw.rectangle([ruler_x + 4, my - 1, ruler_x + ruler_w - 2, my + 1], fill=color)
    for i, color in gutter_marks.items():
        my = line_top(i) + line_h // 2
        draw.rectangle([ruler_x + 1, my - 1, ruler_x + 3, my + 1], fill=color)

    # Status bar: statusBar.background / foreground / border.
    st_y = win_y + win_h - st_h
    draw.rounded_rectangle([cx, st_y, cx + cw, st_y + st_h], radius=8,
                           fill=R["bg_raised"], corners=(False, False, True, True))
    draw.line([cx, st_y, cx + cw, st_y], fill=R["divider"])
    left = "main  ·  1 error, 1 warning"
    right = f"Ln {cursor_line + 1}, Col {cursor_col + 1}  ·  Spaces: 4  ·  UTF-8  ·  LF  ·  Python"
    draw.text((cx + 16, st_y + 5), left, font=font_small, fill=R["fg"])
    rw = text_w(draw, right, font_small)
    draw.text((cx + cw - rw - 16, st_y + 5), right, font=font_small, fill=R["fg"])

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

def render_ui_catalog(pal, title, width=1200, height=760):
    R = roles(pal)
    sel = R["on_selection"]
    img = Image.new("RGB", (width, height), color=_backdrop(R))
    font_title = load_font(15)
    font_h2    = load_font(13)
    font_body  = load_font(12)
    font_small = load_font(11)

    win_x, win_y, win_w, win_h = 40, 40, width - 80, height - 80
    # A Plasma window: [Colors:Window] body.
    cx, cy, cw, ch = _window_chrome(
        img, win_x, win_y, win_w, win_h, f"UI Catalog — {title}", R, font_title,
        titlebar_h=max(30, win_h // 22), body=R["bg_panel"], rule=R["border"])

    draw = ImageDraw.Draw(img, "RGBA")

    def heading(x, y, text):
        draw.text((x, y), text, font=font_h2, fill=R["fg_emphasis"])
        return y + 22

    col_gap = 16
    col_w = (cw - col_gap - 48) // 2
    L = cx + 24
    R_x = L + col_w + col_gap

    # ---- left column ----
    y = heading(L, cy + 16, "Buttons")
    btn_h = 32
    bx = L
    for label, bg, fg in [
        ("Save",   R["button_bg"],  R["fg_on_accent"]),   # button.background / foreground
        ("Cancel", R["bg_active"],  R["fg"]),             # button.secondaryBackground / Foreground
        ("Delete", R["error"],      R["fg_on_accent"]),   # destructive: error fill, on-accent text
        ("Submit", R["bg_raised"],  R["fg_muted"]),       # disabled: Button bg, ForegroundInactive
    ]:
        bw = text_w(draw, label, font_body) + 36
        draw.rounded_rectangle([bx, y, bx + bw, y + btn_h], radius=5, fill=bg)
        draw.text((bx + 18, y + 8), label, font=font_body, fill=fg)
        bx += bw + 10
    y += btn_h + 22

    y = heading(L, y, "Chips")
    chip_h = 26
    bx = L
    for label, color in [
        ("OK",      R["success"]),
        ("Warning", R["warning"]),
        ("Error",   R["error"]),
        ("Info",    R["info"]),
        ("Neutral", R["fg_muted"]),
    ]:
        cw_chip = text_w(draw, label, font_body) + 28
        draw.rounded_rectangle([bx, y, bx + cw_chip, y + chip_h],
                               radius=chip_h // 2, fill=R["bg_raised"])
        dot_r = 4
        draw.ellipse([bx + 8, y + chip_h // 2 - dot_r,
                      bx + 8 + dot_r * 2, y + chip_h // 2 + dot_r], fill=color)
        draw.text((bx + 22, y + 5), label, font=font_body, fill=R["fg"])
        bx += cw_chip + 8
    y += chip_h + 22

    # Tabs: panelTitle.activeBorder / activeForeground / inactiveForeground.
    y = heading(L, y, "Tabs")
    tab_h = 30
    bx = L
    for label, active in [("Overview", True), ("Settings", False), ("Logs", False)]:
        tw_tab = text_w(draw, label, font_body) + 24
        draw.text((bx + 12, y + 7), label, font=font_body,
                  fill=R["fg_emphasis"] if active else R["fg_muted"])
        if active:
            draw.rectangle([bx, y + tab_h - 2, bx + tw_tab, y + tab_h], fill=R["accent"])
        bx += tw_tab + 2
    draw.line([L, y + tab_h + 1, L + col_w, y + tab_h + 1], fill=R["border"])
    y += tab_h + 22

    # Form fields: input.background / border, focusBorder, placeholder.
    y = heading(L, y, "Form fields")
    inp_h = 32
    draw.rounded_rectangle([L, y, L + col_w - 20, y + inp_h], radius=4,
                           fill=R["bg"], outline=R["focus_ring"], width=2)
    end = _draw_runs(draw, L + 12, y + 8, [("viscous-values@example.com", R["fg"])], font_body)
    draw.line([end + 2, y + 8, end + 2, y + inp_h - 8], fill=R["cursor"], width=1)
    y += inp_h + 10
    draw.rounded_rectangle([L, y, L + col_w - 20, y + inp_h], radius=4,
                           fill=R["bg"], outline=R["input_border"], width=1)
    draw.text((L + 12, y + 8), "Search settings…", font=font_body, fill=R["fg_muted"])
    y += inp_h + 12
    # Checkbox: checkbox.background / border / foreground.
    cb = 18
    draw.rounded_rectangle([L, y, L + cb, y + cb], radius=3,
                           fill=R["bg"], outline=R["input_border"])
    draw.line([L + 4, y + 9, L + 8, y + 13], fill=R["fg"], width=2)
    draw.line([L + 8, y + 13, L + 14, y + 5], fill=R["fg"], width=2)
    draw.text((L + cb + 10, y + 1), "Remember me on this device",
              font=font_body, fill=R["fg"])
    y += cb + 12
    # Radio: control outline, accent dot (an active indicator).
    rr = 9
    draw.ellipse([L, y, L + rr * 2, y + rr * 2], fill=R["bg"], outline=R["input_border"])
    draw.ellipse([L + 5, y + 5, L + rr * 2 - 5, y + rr * 2 - 5], fill=R["accent"])
    draw.text((L + rr * 2 + 10, y + 1), "Standard tier",
              font=font_body, fill=R["fg"])
    y += rr * 2 + 18

    y = heading(L, y, "Links")
    lx = L
    for txt, color in [("Visit the docs", R["link"]), ("Read changelog", R["link_visited"])]:
        draw.text((lx, y), txt, font=font_body, fill=color)
        tl_w = text_w(draw, txt, font_body)
        draw.line([lx, y + font_body.size + 3, lx + tl_w, y + font_body.size + 3], fill=color)
        lx += tl_w + 24
    y += font_body.size + 22

    # List: list.activeSelection*, list.hoverBackground on a [Colors:View] base.
    y = heading(L, y, "List")
    row_h = 26
    lw = col_w - 20
    draw.rectangle([L, y, L + lw, y + row_h * 3 + 4], fill=R["bg"], outline=R["border"])
    ry = y + 2
    for name, detail, state in [("Documents", "12 items", "selected"),
                                ("Downloads", "3 items", "hover"),
                                ("Pictures", "48 items", None)]:
        box = [L + 2, ry, L + lw - 2, ry + row_h - 1]
        if state == "selected":
            draw.rectangle(box, fill=R["selection_bg"])
            n_color, d_color = sel["fg"], sel["fg_inactive"]
        elif state == "hover":
            draw.rectangle(box, fill=R["bg_raised"])
            n_color, d_color = R["fg"], R["fg_muted"]
        else:
            n_color, d_color = R["fg"], R["fg_muted"]
        draw.text((L + 12, ry + 5), name, font=font_body, fill=n_color)
        dw = text_w(draw, detail, font_small)
        draw.text((L + lw - dw - 12, ry + 6), detail, font=font_small, fill=d_color)
        ry += row_h

    # ---- right column ----
    y = heading(R_x, cy + 16, "Alerts")
    for msg, accent in [
        ("Saved successfully.",              R["success"]),
        ("Configuration may be incomplete.", R["warning"]),
        ("Failed to apply theme.",           R["error"]),
        ("3 updates available.",             R["info"]),
    ]:
        ah = 38
        draw.rectangle([R_x, y, R_x + col_w - 20, y + ah], fill=R["bg_raised"])
        draw.rectangle([R_x, y, R_x + 4, y + ah], fill=accent)
        draw.text((R_x + 16, y + 11), msg, font=font_body, fill=R["fg"])
        y += ah + 6
    y += 12

    # Toast: notifications.background / border, notificationsInfoIcon.
    y = heading(R_x, y, "Toast")
    th_t = 50
    tx2 = R_x + col_w - 60
    for k in range(3):
        draw.rounded_rectangle([R_x - k, y + 1, tx2 + k, y + th_t + k + 2], radius=6 + k,
                               fill=R["shadow"] + (40 - k * 12,))
    draw.rounded_rectangle([R_x, y, tx2, y + th_t], radius=6,
                           fill=R["bg_panel"], outline=R["border"])
    draw.ellipse([R_x + 12, y + 10, R_x + 28, y + 26], outline=R["info"], width=2)
    draw.line([R_x + 20, y + 16, R_x + 20, y + 21], fill=R["info"], width=2)
    draw.point([(R_x + 20, y + 13), (R_x + 19, y + 13)], fill=R["info"])
    draw.text((R_x + 38, y + 8), "Palette saved.", font=font_body, fill=R["fg"])
    draw.text((R_x + 38, y + 26), "Click to view file.", font=font_small, fill=R["fg_muted"])
    y += th_t + 20

    # Progress: progressBar.background on a bg groove.
    y = heading(R_x, y, "Progress")
    pr_h = 8
    pr_w = col_w - 30
    draw.rounded_rectangle([R_x, y, R_x + pr_w, y + pr_h], radius=pr_h // 2, fill=R["bg"])
    draw.rounded_rectangle([R_x, y, R_x + int(pr_w * 0.62), y + pr_h],
                           radius=pr_h // 2, fill=R["interactive"])
    draw.text((R_x + pr_w + 8, y - 2), "62%", font=font_small, fill=R["fg_muted"])
    y += pr_h + 20

    # Scrollbar: scrollbarSlider (bg_active) on a bg groove.
    y = heading(R_x, y, "Scrollbar")
    sc_w = col_w - 30
    sc_h = 8
    draw.rounded_rectangle([R_x, y, R_x + sc_w, y + sc_h], radius=sc_h // 2, fill=R["bg"])
    th_thumb = int(sc_w * 0.25)
    draw.rounded_rectangle([R_x + 30, y, R_x + 30 + th_thumb, y + sc_h],
                           radius=sc_h // 2, fill=R["bg_active"])
    y += sc_h + 20

    # Legend: the roles this page draws with, resolved for this palette.
    y = heading(R_x, y, "Roles")
    for key in ("accent", "selection_bg", "link", "link_visited", "info",
                "success", "warning", "error", "hint"):
        draw.rectangle([R_x, y + 4, R_x + 14, y + 14], fill=R[key], outline=R["border"])
        draw.text((R_x + 22, y), f"role.{key}", font=font_small, fill=R["fg_muted"])
        draw.text((R_x + 150, y), pal["role"][key], font=font_small, fill=R["fg_muted"])
        y += 16

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

    pal = load_palette(args.palette)
    title = args.title or derive_title(args.palette)

    # Desktop view (full + thumb share a single render).
    if args.out_full or args.out_thumb:
        full = render_desktop(1920, 1214, pal, title)
        if args.out_full:
            args.out_full.parent.mkdir(parents=True, exist_ok=True)
            full.save(args.out_full, quality=88, optimize=True)
            print(f"Wrote {args.out_full}")
        if args.out_thumb:
            thumb = full.resize((512, 324), Image.LANCZOS)
            args.out_thumb.parent.mkdir(parents=True, exist_ok=True)
            thumb.save(args.out_thumb, optimize=True)
            print(f"Wrote {args.out_thumb}")

    for path, render in [(args.out_swatches,    render_swatches),
                         (args.out_filemanager, render_filemanager),
                         (args.out_textsample,  render_textsample),
                         (args.out_ui_catalog,  render_ui_catalog)]:
        if path:
            img = render(pal, title)
            path.parent.mkdir(parents=True, exist_ok=True)
            img.save(path, optimize=True)
            print(f"Wrote {path}")


if __name__ == "__main__":
    main()

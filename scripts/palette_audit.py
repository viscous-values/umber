#!/usr/bin/env python3
"""Measure an Umber palette family: contrast, role separation, variant identity.

Every check reads resolved roles (palette_lib.prepare), i.e. the colors the
templates actually draw, not raw tiers. Distances are Euclidean ΔE in OKLab,
where ~0.02 is the smallest difference most people notice side by side.

    python3 scripts/palette_audit.py                   # report canonical + palettes/*.toml
    python3 scripts/palette_audit.py --dir palettes/next
    python3 scripts/palette_audit.py --strict          # exit 1 if any error-level check fails
    python3 scripts/palette_audit.py --failures-only

Levels: "error" checks guard readability (WCAG AA) and the separations the
redesign exists for; "warn" checks are advisory. --strict gates on errors.
THRESHOLDS below are the single source of truth; render_lab.py embeds them.
"""

import argparse
import itertools
import math
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import palette_lib

# --------------------------------------------------------------------------- #
# thresholds                                                                  #
# --------------------------------------------------------------------------- #

THRESHOLDS = {
    "text_contrast":      4.5,    # WCAG 1.4.3 AA body text
    "nontext_contrast":   3.0,    # WCAG 1.4.11 focus indicators / control boundaries
    "surface_step":       {"bg>bg_panel": 0.03, "bg_panel>bg_raised": 0.035, "bg_raised>bg_active": 0.06},
    "distinct_from_fg":   0.08,   # body text vs accent / syntax roles
    "link_vs_fg_de":      0.10,   # links must stand off body text (plan: hue does it, underline backs it)
    "link_vs_info_de":    0.08,   # info text must not look clickable
    "link_visited_de":    0.10,
    "link_visited_dh":    45.0,   # degrees of hue
    "syntax_pair_de":     0.06,
    "onsel_pair_de":      0.08,
    "comment_recede_dl":  0.10,   # comment at least this much darker than body text
    "accent_vs_fg_de":    0.10,
    "accent_vs_status_de": 0.08,  # focus/selection accent must not read as an error/warning
    "cvd_pair_de":        0.05,
    "ansi_black_dl":      0.10,
    "ansi_blue_cyan_de":  0.08,
    "selection_alt_de":   0.10,   # alternate selected row must stay a tint of the selection
    "cross_ground_de":    0.025,
    "cross_accent_de":    0.10,
    "cross_identity":     0.06,   # mean over IDENTITY: what tells variants apart at a glance
    "cross_syntax_key":   0.03,   # mean over SYNTAX_KEY: keys may share conventions, not be identical
}

SYNTAX_SET = ["variable", "operator", "comment", "keyword", "function", "type",
              "string", "number", "regex", "tag"]
IDENTITY = ["bg", "bg_panel", "fg", "accent", "selection_bg"]
SYNTAX_KEY = ["syntax.keyword", "syntax.function", "syntax.type",
              "syntax.string", "syntax.number", "syntax.comment"]
ACHROMATIC_C = 0.02   # below this chroma a color has no meaningful hue

# --------------------------------------------------------------------------- #
# color math                                                                  #
# --------------------------------------------------------------------------- #

def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def _to_linear(c8):
    c = c8 / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_srgb8(lin):
    lin = max(0.0, min(1.0, lin))
    c = 12.92 * lin if lin <= 0.0031308 else 1.055 * lin ** (1 / 2.4) - 0.055
    return c * 255


def oklab(h):
    r, g, b = (_to_linear(c) for c in hex_rgb(h))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklch(h):
    L, a, b = oklab(h)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def delta_e(x, y):
    return math.dist(oklab(x), oklab(y))


def hue_delta(x, y):
    """Hue angle between two colors; 0 when either is too grey to have a hue."""
    (_, cx, hx), (_, cy, hy) = oklch(x), oklch(y)
    if min(cx, cy) < ACHROMATIC_C:
        return 0.0
    d = abs(hx - hy) % 360
    return min(d, 360 - d)


def luminance(h):
    r, g, b = (_to_linear(c) for c in hex_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(x, y):
    hi, lo = sorted((luminance(x), luminance(y)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def apca(text, bg):
    """APCA 0.0.98G Lc (informational; positive = dark text on light)."""
    def y(h):
        r, g, b = ((c / 255) ** 2.4 for c in hex_rgb(h))
        v = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
        return v + (0.022 - v) ** 1.414 if v < 0.022 else v
    yt, yb = y(text), y(bg)
    if abs(yb - yt) < 0.0005:
        return 0.0
    if yb > yt:
        sapc = (yb ** 0.56 - yt ** 0.57) * 1.14
        return 0.0 if sapc < 0.1 else (sapc - 0.027) * 100
    sapc = (yb ** 0.65 - yt ** 0.62) * 1.14
    return 0.0 if sapc > -0.1 else (sapc + 0.027) * 100


# Machado, Oliveira & Fernandes 2009, severity 1.0, applied in linear RGB.
CVD_MATRICES = {
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def simulate_cvd(h, kind):
    lin = [_to_linear(c) for c in hex_rgb(h)]
    out = [sum(row[i] * lin[i] for i in range(3)) for row in CVD_MATRICES[kind]]
    return rgb_hex(_to_srgb8(c) for c in out)


# --------------------------------------------------------------------------- #
# checks                                                                      #
# --------------------------------------------------------------------------- #

@dataclass
class Check:
    id: str
    group: str
    value: float
    op: str          # ">=" or "<="
    threshold: float
    level: str = "error"
    note: str = ""

    @property
    def ok(self):
        return self.value >= self.threshold if self.op == ">=" else self.value <= self.threshold

    def fmt_value(self):
        return f"{self.value:.2f}:1" if self.group == "contrast" else f"{self.value:.3f}"


# A check spec is plain data so the Palette Lab (scripts/render_lab.py) can
# evaluate the exact same list in the browser. Kinds:
#   contrast  WCAG ratio of roles a and b
#   dl        OKLab L(b) - L(a)                 (b should sit above a)
#   de        OKLab ΔE(a, b)
#   dh        hue angle between a and b, degrees
#   cvd       ΔE(a, b) after simulating spec["cvd"] (protan / deutan / tritan)
#   apca      |APCA Lc| of text a on background b
def _spec(id, group, kind, a, b, threshold, op=">=", level="error", **extra):
    return {"id": id, "group": group, "kind": kind, "a": a, "b": b,
            "op": op, "threshold": threshold, "level": level, **extra}


def check_specs():
    t = THRESHOLDS
    text, nontext = t["text_contrast"], t["nontext_contrast"]
    specs = []

    def contrast_spec(fg, bg, minimum=text, level="error"):
        specs.append(_spec(f"contrast:{fg}/{bg}", "contrast", "contrast", fg, bg, minimum, level=level))

    # Text on the surfaces it is drawn on.
    for fg in ("fg", "fg_muted"):
        for bg in ("bg", "bg_panel", "bg_raised"):
            contrast_spec(fg, bg)
    for fg, bg in (("fg_emphasis", "bg_active"), ("fg_strong", "bg_raised"), ("fg", "bg_overlay"), ("link", "bg_panel"),
                   ("link_visited", "bg_panel"), ("fg_on_accent", "button_bg"), ("fg_on_accent", "interactive"),
                   ("fg_on_accent", "error"), ("fg_on_accent", "warning"), ("fg_on_accent", "debug")):
        contrast_spec(fg, bg)
    for status in ("error", "warning", "success", "info"):
        contrast_spec(status, "bg_panel")
    for syn in SYNTAX_SET:
        contrast_spec(f"syntax.{syn}", "bg")
    for key in ("fg", "fg_soft", "link", "visited", "negative", "neutral", "positive"):
        contrast_spec(f"on_selection.{key}", "selection_bg")
    contrast_spec("on_selection.fg_inactive", "selection_bg", level="warn")
    for ansi in ("red", "green", "yellow", "blue", "magenta", "cyan", "white"):
        contrast_spec(f"ansi.{ansi}", "ansi.bg")

    # Non-text: focus indicators and control boundaries.
    contrast_spec("focus_ring", "bg", nontext)
    contrast_spec("focus_ring", "bg_panel", nontext)
    # SDDM and the lockscreen use AccentColor (decoration_focus) for typed text
    # and hover labels, and draw AccentTextColor (fg_on_accent) on it: text rules.
    contrast_spec("decoration_focus", "bg_panel")
    contrast_spec("fg_on_accent", "decoration_focus")
    contrast_spec("input_border", "bg", nontext)
    contrast_spec("input_border", "bg_panel", nontext)

    # Surfaces must read as separate planes.
    for pair, minimum in t["surface_step"].items():
        lo, hi = pair.split(">")
        specs.append(_spec(f"surface:{pair}", "surface", "dl", lo, hi, minimum))

    # Body text vs everything that has to read as "not body text".
    for other in ("link", "accent", "syntax.type", "syntax.keyword", "syntax.function",
                  "syntax.string", "syntax.number"):
        minimum = {"accent": t["accent_vs_fg_de"], "link": t["link_vs_fg_de"]}.get(other, t["distinct_from_fg"])
        specs.append(_spec(f"distinct:fg~{other}", "distinct", "de", "fg", other, minimum))
    specs.append(_spec("distinct:link~info", "distinct", "de", "link", "info", t["link_vs_info_de"], level="warn"))

    # The signature accent must not be mistaken for a status color.
    for status in ("error", "warning", "success", "info"):
        specs.append(_spec(f"accent-vs-status:accent~{status}", "distinct", "de", "accent", status,
                           t["accent_vs_status_de"], level="warn"))

    # Links.
    specs.append(_spec("link:link~link_visited", "distinct", "de", "link", "link_visited", t["link_visited_de"]))
    specs.append(_spec("link-hue:link~link_visited", "distinct", "dh", "link", "link_visited", t["link_visited_dh"]))

    # Syntax roles against each other.
    for a, b in itertools.combinations(SYNTAX_SET, 2):
        specs.append(_spec(f"syntax:{a}~{b}", "distinct", "de", f"syntax.{a}", f"syntax.{b}", t["syntax_pair_de"]))

    # Colors drawn on the selection must stay distinguishable from each other.
    for a, b in itertools.combinations(["fg", "link", "visited", "negative", "neutral", "positive"], 2):
        specs.append(_spec(f"onsel:{a}~{b}", "distinct", "de", f"on_selection.{a}", f"on_selection.{b}",
                           t["onsel_pair_de"]))
    specs.append(_spec("selection-alt:selection_alt~selection_bg", "distinct", "de", "selection_alt",
                       "selection_bg", t["selection_alt_de"], op="<=", level="warn"))

    # Comments recede below body text.
    specs.append(_spec("comment-recedes", "distinct", "dl", "syntax.comment", "fg", t["comment_recede_dl"]))

    # Color-vision deficiency: semantic pairs must survive simulation.
    for kind in CVD_MATRICES:
        for a, b in (("error", "success"), ("diff_added", "diff_removed"), ("success", "warning")):
            specs.append(_spec(f"cvd-{kind}:{a}~{b}", "cvd", "cvd", a, b, t["cvd_pair_de"], cvd=kind))

    # Terminal.
    specs.append(_spec("ansi:black/bg", "ansi", "dl", "ansi.bg", "ansi.black", t["ansi_black_dl"]))
    specs.append(_spec("ansi:blue~cyan", "ansi", "de", "ansi.blue", "ansi.cyan", t["ansi_blue_cyan_de"]))

    # APCA readout for the two texts people read most (informational).
    for fg in ("fg", "syntax.comment"):
        specs.append(_spec(f"apca:{fg}/bg", "apca", "apca", fg, "bg", 0, level="info"))
    return specs


def role(pal, key):
    return palette_lib.resolve(pal, "role." + key)


def measure(kind, a, b, cvd=None):
    """Evaluate one spec kind on two hex colors."""
    if kind == "contrast":
        return contrast(a, b)
    if kind == "dl":
        return oklch(b)[0] - oklch(a)[0]
    if kind == "de":
        return delta_e(a, b)
    if kind == "dh":
        return hue_delta(a, b)
    if kind == "cvd":
        return delta_e(simulate_cvd(a, cvd), simulate_cvd(b, cvd))
    if kind == "apca":
        return abs(apca(a, b))
    raise ValueError(f"unknown check kind {kind!r}")


def evaluate(spec, pal):
    value = measure(spec["kind"], role(pal, spec["a"]), role(pal, spec["b"]), spec.get("cvd"))
    return Check(spec["id"], spec["group"], value, spec["op"], spec["threshold"], spec["level"])


def audit_variant(pal):
    return [evaluate(spec, pal) for spec in check_specs()]


def family_specs():
    """Cross-variant checks: one role, or the mean over a role group, compared between two variants."""
    t = THRESHOLDS
    return [
        {"id": "cross-ground", "roles": ["bg"], "threshold": t["cross_ground_de"]},
        {"id": "cross-accent", "roles": ["accent"], "threshold": t["cross_accent_de"]},
        {"id": "cross-identity", "roles": IDENTITY, "threshold": t["cross_identity"]},
        {"id": "cross-syntax", "roles": SYNTAX_KEY, "threshold": t["cross_syntax_key"]},
    ]


def audit_family(pals):
    """Cross-variant identity checks. `pals` maps variant name -> prepared palette."""
    checks = []
    for (na, a), (nb, b) in itertools.combinations(pals.items(), 2):
        for spec in family_specs():
            value = sum(delta_e(role(a, k), role(b, k)) for k in spec["roles"]) / len(spec["roles"])
            checks.append(Check(f"{spec['id']}:{na}~{nb}", "cross", value, ">=", spec["threshold"]))
    return checks


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def load_targets(directory=None):
    """name -> (path, prepared palette). Default: palette.toml + palettes/*.toml."""
    if directory is None:
        paths = [palette_lib.PALETTE_FILE, *sorted(palette_lib.PALETTES_DIR.glob("*.toml"))]
    else:
        paths = sorted(Path(directory).glob("*.toml"))
    return {palette_lib.variant_slug(p): (p, palette_lib.prepare(p)) for p in paths}


def report(name, path, checks, failures_only):
    bad = [c for c in checks if not c.ok and c.level != "info"]
    print(f"\n{name}  ({path.name})  —  {len(bad)} below threshold")
    for c in checks:
        if failures_only and (c.ok or c.level == "info"):
            continue
        mark = "·" if c.level == "info" else ("ok" if c.ok else ("!!" if c.level == "error" else "~~"))
        bound = "" if c.level == "info" else f"{c.op} {c.threshold:g}"
        print(f"  {mark:2} {c.group:9} {c.id:48} {c.fmt_value():>9}  {bound}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", type=Path, help="audit every *.toml in this directory instead")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any error-level check fails")
    ap.add_argument("--failures-only", action="store_true", help="print only checks below threshold")
    args = ap.parse_args(argv)

    if args.dir is None:
        paths = [palette_lib.PALETTE_FILE, *sorted(palette_lib.PALETTES_DIR.glob("*.toml"))]
    else:
        paths = sorted(Path(args.dir).glob("*.toml"))
    if not paths:
        print(f"no palette TOMLs found in {args.dir}", file=sys.stderr)
        return 2
    targets, invalid = {}, 0
    for path in paths:
        try:
            targets[palette_lib.variant_slug(path)] = (path, palette_lib.prepare(path))
        except (ValueError, tomllib.TOMLDecodeError) as e:
            invalid += 1
            print(f"{path.name}: INVALID — {e}", file=sys.stderr)

    errors = 0
    for name, (path, pal) in targets.items():
        checks = audit_variant(pal)
        errors += sum(1 for c in checks if c.level == "error" and not c.ok)
        report(name, path, checks, args.failures_only)
    if len(targets) > 1:
        fam = audit_family({n: p for n, (_, p) in targets.items()})
        errors += sum(1 for c in fam if c.level == "error" and not c.ok)
        report("family", Path("cross-variant"), fam, args.failures_only)

    print(f"\n{errors} error-level check(s) below threshold.")
    if invalid:
        return 2
    return 1 if (args.strict and errors) else 0


if __name__ == "__main__":
    sys.exit(main())

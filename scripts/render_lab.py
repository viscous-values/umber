#!/usr/bin/env python3
"""Build the Umber Palette Lab: one self-contained HTML page for judging the family.

    python3 scripts/render_lab.py                 # -> mockups/palette-lab.html
    python3 scripts/render_lab.py --out /tmp/lab.html --next-dir palettes/next

The page embeds two palette sets: "current" (palette.toml + palettes/*.toml)
and, when palettes/next/ holds proposals, "draft". It shows the five variants
as mock Plasma / VSCode / Konsole surfaces, a lightness ladder, a hue wheel,
distance matrices, the audit, and an OKLCH tuner that exports TOML.

The page's color engine (scripts/templates/palette-lab-engine.js) resolves
roles and runs palette_audit's check specs in the browser, so tuning re-audits
live. Python's own audit numbers are embedded too; the page logs a parity
check against them to the console.
"""

import argparse
import json
import sys
from pathlib import Path

import palette_audit
import palette_lib

REPO = palette_lib.REPO
NEXT_DIR = palette_lib.PALETTES_DIR / "next"
OUT = REPO / "mockups" / "palette-lab.html"
TEMPLATE = REPO / "scripts" / "templates" / "palette-lab.html"
ENGINE = REPO / "scripts" / "templates" / "palette-lab-engine.js"

FAMILY_ORDER = ["umber", "ash", "slate", "tide", "storm"]
TIER_KEYS = ["hearth", "glow", "mist", "spark", "accent", "ansi"]


def variant_entry(path):
    slug = palette_lib.variant_slug(path)
    raw = palette_lib.load_toml(path)
    pal = palette_lib.prepare(path)
    meta = raw.get("meta", {})
    return {
        "slug": slug,
        "name": "Umber" if slug == "umber" else f"Umber {slug.title()}",
        "file": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else path.name,
        "description": meta.get("description", ""),
        "concept": meta.get("concept", ""),
        "meta": meta,
        "tiers": {k: raw[k] for k in TIER_KEYS if k in raw},
        "role": raw.get("role", {}),
        "audit": {c.id: c.value for c in palette_audit.audit_variant(pal)},
    }


def build_set(paths, label):
    entries = [variant_entry(p) for p in paths]
    rank = {slug: i for i, slug in enumerate(FAMILY_ORDER)}
    entries.sort(key=lambda e: (rank.get(e["slug"], len(rank)), e["slug"]))
    return {"label": label, "variants": entries}


def build_data(next_dir=NEXT_DIR):
    current = [palette_lib.PALETTE_FILE, *sorted(palette_lib.PALETTES_DIR.glob("*.toml"))]
    sets = {"current": build_set(current, "Current")}
    drafts = sorted(Path(next_dir).glob("*.toml")) if Path(next_dir).is_dir() else []
    if drafts:
        sets["draft"] = build_set(drafts, "Draft")
    return {
        "roles": palette_lib.load_toml(palette_lib.ROLES_FILE)["role"],
        "specs": palette_audit.check_specs(),
        "familySpecs": palette_audit.family_specs(),
        "thresholds": palette_audit.THRESHOLDS,
        "syntaxSet": palette_audit.SYNTAX_SET,
        "sets": sets,
    }


def render(out=OUT, next_dir=NEXT_DIR):
    # No "<" may survive inside the <script>: "</script" or "<!--" in palette text
    # would end or comment out the page script. JSON reads \u003c back as "<".
    data = json.dumps(build_data(next_dir), separators=(",", ":")).replace("<", "\\u003c")
    html = TEMPLATE.read_text()
    html = html.replace("/*__ENGINE__*/", ENGINE.read_text())
    html = html.replace("/*__DATA__*/", f"const DATA = {data};\n")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--next-dir", type=Path, default=NEXT_DIR)
    args = ap.parse_args()
    out = render(args.out, args.next_dir)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

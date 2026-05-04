#!/bin/bash
# Build a signed-ready .xpi per variant for AMO submission.
#
# Output: dist/<slug>-firefox-<version>.xpi for each of:
#   umber, umber-ash, umber-slate, umber-tide, umber-storm
# An .xpi is just a zip of manifest.json + icons/ at the archive root
# (no top-level directory; AMO rejects nested layouts). Each variant has
# a distinct gecko id (umber@tyler, umber-tide@tyler, etc.) so they
# upload to AMO as separate listings under one developer account.
#
# Usage:
#   ./scripts/build-firefox-xpi.sh           # all five variants
#   ./scripts/build-firefox-xpi.sh tide      # one variant
#
# After build, upload the .xpi at:
#   https://addons.mozilla.org/developers/addon/submit/distribution

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
mkdir -p "$DIST_DIR"

ALL_VARIANTS=(umber ash slate tide storm)
if (( $# > 0 )); then
    VARIANTS=("$@")
else
    VARIANTS=("${ALL_VARIANTS[@]}")
fi

slug_for() {
    [[ "$1" == "umber" ]] && echo "umber" || echo "umber-$1"
}

for v in "${VARIANTS[@]}"; do
    case "$v" in
        umber|ash|slate|tide|storm) ;;
        *) echo "ERROR: unknown variant '$v' (expected: ${ALL_VARIANTS[*]})" >&2; exit 2 ;;
    esac

    slug=$(slug_for "$v")
    src="$REPO_ROOT/${slug}-firefox"

    if [[ ! -f "$src/manifest.json" ]]; then
        echo "ERROR: $src/manifest.json missing — run scripts/render_palette.py first" >&2
        exit 1
    fi
    if [[ ! -d "$src/icons" ]]; then
        echo "ERROR: $src/icons/ missing — run scripts/render_extension_icon.py first" >&2
        exit 1
    fi

    version=$(python3 -c "import json,sys; print(json.load(open('$src/manifest.json'))['version'])")
    out="$DIST_DIR/${slug}-firefox-${version}.xpi"

    rm -f "$out"
    # Build via Python's zipfile so this script doesn't depend on /usr/bin/zip.
    # Walks $src, writes manifest.json + icons/* with paths relative to $src
    # (i.e. archive root), DEFLATE-compressed.
    SRC="$src" OUT="$out" python3 - <<'PYEOF'
import os, sys, zipfile
src = os.environ["SRC"]; out = os.environ["OUT"]
def add(z, abs_path, arc_path):
    z.write(abs_path, arc_path)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    add(z, os.path.join(src, "manifest.json"), "manifest.json")
    icons_dir = os.path.join(src, "icons")
    for name in sorted(os.listdir(icons_dir)):
        add(z, os.path.join(icons_dir, name), f"icons/{name}")
# Sanity: confirm manifest is at archive root, no nested top-level dir.
with zipfile.ZipFile(out) as z:
    names = z.namelist()
    if "manifest.json" not in names:
        sys.stderr.write(f"ERROR: {out} missing manifest.json at root\n"); sys.exit(1)
    bad = [n for n in names if n.startswith("/") or ".." in n.split("/")]
    if bad:
        sys.stderr.write(f"ERROR: bad paths in {out}: {bad}\n"); sys.exit(1)
PYEOF

    size=$(stat -c%s "$out")
    printf "  built %s (%d bytes)\n" "$out" "$size"
done

echo
echo "Upload each .xpi at: https://addons.mozilla.org/developers/addon/submit/distribution"
echo "Each variant has its own gecko id, so they can be submitted as separate listings."

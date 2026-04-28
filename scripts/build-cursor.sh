#!/bin/bash
# Rebuild cursors/Umber-cursor/ from the user's installed Nordic-cursors.
# Output is committed to the repo so users don't need to run this — only the
# author regenerates after a palette change.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${HUSH_CURSOR_SRC:-$HOME/.icons/Nordic-cursors}"
DST="$REPO_ROOT/cursors/Umber-cursor"

if [[ ! -d "$SRC" ]]; then
    echo "ERROR: source theme not found at $SRC" >&2
    echo "Install Nordic-cursors first (e.g. from https://github.com/EliverLara/Nordic-cursors)," >&2
    echo "or set HUSH_CURSOR_SRC to point at your copy." >&2
    exit 1
fi

echo "Recoloring $SRC -> $DST"
HUSH_CURSOR_SRC="$SRC" HUSH_CURSOR_DST="$DST" \
    python3 "$REPO_ROOT/scripts/recolor_nordic_inplace.py"

echo "Done. Review with: ls $DST/cursors | wc -l"

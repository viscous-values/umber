#!/bin/bash
# Rebuild every variant's cursor theme (cursors/Umber-cursor/,
# cursors/Umber-Ash-cursor/, ...) from the user's installed Nordic-cursors.
# Output is committed to the repo so users don't need to run this — only the
# author regenerates after a palette change (tests/test_cursor.py fails on a
# stale cursor).
#
# Usage: ./scripts/build-cursor.sh            all shipped variants
#        ./scripts/build-cursor.sh slate      one variant

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${UMBER_CURSOR_SRC:-$HOME/.icons/Nordic-cursors}"

if [[ ! -d "$SRC/cursors" ]]; then
    echo "ERROR: source theme not found at $SRC" >&2
    echo "Install Nordic-cursors first (e.g. from https://github.com/EliverLara/Nordic-cursors)," >&2
    echo "or set UMBER_CURSOR_SRC to point at your copy." >&2
    exit 1
fi

case "${1:-}" in
    "")     PALETTES=("$REPO_ROOT/palette.toml" "$REPO_ROOT"/palettes/*.toml) ;;
    umber)  PALETTES=("$REPO_ROOT/palette.toml") ;;
    *)      PALETTES=("$REPO_ROOT/palettes/$1.toml") ;;
esac

for palette in "${PALETTES[@]}"; do
    python3 "$REPO_ROOT/scripts/recolor_nordic_inplace.py" --src "$SRC" --palette "$palette"
done

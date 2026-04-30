#!/bin/bash
# Switch the live Plasma session to a previously-installed Umber variant.
#
# Why this exists: Plasma 6's plasma-apply-lookandfeel — the same code path
# System Settings → Global Theme → Apply uses — STRIPS every [Colors:*]
# section out of ~/.config/kdeglobals when it loads any of our LnF packages
# (a quirk triggered by us bundling contents/colors/<scheme>.colors inside
# the package; stock Plasma packages like BreezeDark don't ship a colors/
# dir and don't trigger the wipe). After the strip, plasma-apply-lookandfeel
# does NOT repopulate [Colors:*] from the user-installed scheme at
# ~/.local/share/color-schemes/<scheme>.colors — it only repopulates from
# /usr/share/color-schemes/. So running apps fall back to compiled-in Breeze
# Light defaults: white window borders, white taskbar, etc.
#
# This script does the LnF apply, then the BreezeLight → real-scheme flicker
# that defeats plasma-apply-colorscheme's "already set" short-circuit and
# writes [Colors:*] back into kdeglobals. Same recipe install.sh uses.
#
# Usage: ./scripts/apply-variant.sh <variant>   (one of: umber ash slate tide storm)

set -euo pipefail

VARIANT="${1:-}"
case "$VARIANT" in
    umber|ash|slate|tide|storm) ;;
    *)
        echo "Usage: $0 <variant>" >&2
        echo "  variant: umber | ash | slate | tide | storm" >&2
        exit 2
        ;;
esac

if [[ "$VARIANT" == "umber" ]]; then
    PKG_ID="com.tyler.umber"
    SCHEME="Umber"
else
    PKG_ID="com.tyler.umber-$VARIANT"
    SCHEME="Umber-${VARIANT^}"   # ash → Ash, slate → Slate, ...
fi

LNF_DIR="$HOME/.local/share/plasma/look-and-feel/$PKG_ID"
SCHEME_FILE="$HOME/.local/share/color-schemes/$SCHEME.colors"
if [[ ! -d "$LNF_DIR" ]]; then
    echo "ERROR: $PKG_ID not installed at $LNF_DIR" >&2
    echo "       Run: ./install.sh --variant $VARIANT" >&2
    exit 1
fi
if [[ ! -f "$SCHEME_FILE" ]]; then
    echo "ERROR: $SCHEME.colors not installed at $SCHEME_FILE" >&2
    echo "       Run: ./install.sh --variant $VARIANT" >&2
    exit 1
fi

# cd /tmp before plasma-apply-lookandfeel: KPackage's loader scans cwd, and
# if it sees a directory matching $PKG_ID (e.g., when invoked from the repo
# root) it preferentially "loads" that path with a trailing slash and the
# binary fails with "Unable to find the theme named <pkg>/".
LNF_LOG="$(mktemp -t umber-apply-XXXXXX.log)"
( cd /tmp && plasma-apply-lookandfeel -a "$PKG_ID" ) >"$LNF_LOG" 2>&1 \
    && echo "ok  plasma-apply-lookandfeel $PKG_ID" \
    || { echo "ERROR: plasma-apply-lookandfeel failed — see $LNF_LOG" >&2; exit 1; }

# BreezeLight defeats the "already set" short-circuit so the next apply
# actually writes [Colors:*] back into kdeglobals.
plasma-apply-colorscheme BreezeLight 2>&1 | sed 's/^/    /'
plasma-apply-colorscheme "$SCHEME"     2>&1 | sed 's/^/    /'

if grep -q '^\[Colors:Window\]' "$HOME/.config/kdeglobals" 2>/dev/null; then
    echo "ok  $SCHEME applied — kdeglobals has [Colors:*] sections"
else
    echo "WARNING: ~/.config/kdeglobals has no [Colors:*] — apps may show stale colors." >&2
    echo "         Try logging out and back in." >&2
    exit 1
fi

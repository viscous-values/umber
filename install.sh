#!/bin/bash
# Umber — one-shot installer for the full theme suite on KDE Plasma 6.
# Idempotent: safe to re-run. Manual steps that need sudo or out-of-process
# action (SDDM, Firefox, Chromium) are printed at the end, not auto-executed.
#
# Usage: ./install.sh [--yes]
#   --yes  skip the overwrite confirmation (for non-interactive use)

set -euo pipefail

ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        -y|--yes) ASSUME_YES=1 ;;
        -h|--help)
            sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown argument: $arg" >&2; exit 2 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

ICONS_DIR="$HOME/.local/share/icons"
SCHEMES_DIR="$HOME/.local/share/color-schemes"
LNF_DIR="$HOME/.local/share/plasma/look-and-feel"
KONSOLE_DIR="$HOME/.local/share/konsole"
VSCODE_EXT_DIR="$HOME/.vscode/extensions"

NEWAITA_VARIANT="Newaita-reborn-light-brown-dark"
NEWAITA_REPO="https://github.com/cbrnix/Newaita-reborn"

step() { printf "\n\033[1;33m==>\033[0m %s\n" "$1"; }
ok()   { printf "    \033[0;32mok\033[0m %s\n" "$1"; }
note() { printf "    \033[0;36m..\033[0m %s\n" "$1"; }
err()  { printf "\033[1;31mERROR:\033[0m %s\n" "$1" >&2; }

# ---------------------------------------------------------------------------
# Preflight: required binaries.
require_bin() {
    local bin="$1" pkg="$2"
    if ! command -v "$bin" >/dev/null 2>&1; then
        err "missing required command: $bin"
        printf "       Install it (likely from package: %s) and re-run.\n" "$pkg" >&2
        exit 1
    fi
}
step "Preflight"
require_bin plasma-apply-lookandfeel  "plasma-workspace"
require_bin plasma-apply-colorscheme  "plasma-workspace"
require_bin kbuildsycoca6             "kservice"
require_bin git                       "git"
require_bin python3                   "python"
ok "all required commands present"

# ---------------------------------------------------------------------------
# Overwrite confirmation.
existing=()
[[ -d "$LNF_DIR/com.tyler.hush" ]]   && existing+=("$LNF_DIR/com.tyler.hush")
[[ -d "$ICONS_DIR/Umber-cursor" ]]    && existing+=("$ICONS_DIR/Umber-cursor")
[[ -f "$SCHEMES_DIR/Umber.colors" ]]  && existing+=("$SCHEMES_DIR/Umber.colors")
if (( ${#existing[@]} > 0 )) && (( ASSUME_YES == 0 )); then
    step "Existing Umber install detected"
    for p in "${existing[@]}"; do note "will overwrite: $p"; done
    printf "    Continue? [y/N] "
    read -r reply
    case "$reply" in
        y|Y|yes|YES) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
fi

# ---------------------------------------------------------------------------
step "Newaita icon theme ($NEWAITA_VARIANT)"
if [[ -d "$ICONS_DIR/$NEWAITA_VARIANT" ]]; then
    ok "already installed at $ICONS_DIR/$NEWAITA_VARIANT"
else
    note "missing — cloning $NEWAITA_REPO"
    tmp_clone="$(mktemp -d -t newaita-reborn-XXXXXX)"
    trap 'rm -rf "$tmp_clone"' EXIT
    git clone --depth=1 "$NEWAITA_REPO" "$tmp_clone"
    if [[ ! -d "$tmp_clone/$NEWAITA_VARIANT" ]]; then
        echo "ERROR: variant $NEWAITA_VARIANT not found in upstream repo" >&2
        exit 1
    fi
    mkdir -p "$ICONS_DIR"
    cp -a "$tmp_clone/$NEWAITA_VARIANT" "$ICONS_DIR/$NEWAITA_VARIANT"
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q "$ICONS_DIR/$NEWAITA_VARIANT" || true
    fi
    rm -rf "$tmp_clone"
    trap - EXIT
    ok "installed $NEWAITA_VARIANT"
fi

# ---------------------------------------------------------------------------
step "Umber-cursor"
mkdir -p "$ICONS_DIR"
if [[ ! -d "$REPO_ROOT/cursors/Umber-cursor" ]]; then
    echo "ERROR: cursors/Umber-cursor not found in repo. Run scripts/build-cursor.sh." >&2
    exit 1
fi
rm -rf "$ICONS_DIR/Umber-cursor"
cp -a "$REPO_ROOT/cursors/Umber-cursor" "$ICONS_DIR/Umber-cursor"
ok "installed to $ICONS_DIR/Umber-cursor"

# ---------------------------------------------------------------------------
step "Umber color scheme"
mkdir -p "$SCHEMES_DIR"
cp "$REPO_ROOT/com.tyler.hush/contents/colors/Umber.colors" "$SCHEMES_DIR/Umber.colors"
ok "installed to $SCHEMES_DIR/Umber.colors"

# ---------------------------------------------------------------------------
step "Plasma Look-and-Feel package"
mkdir -p "$LNF_DIR"
rm -rf "$LNF_DIR/com.tyler.hush"
cp -a "$REPO_ROOT/com.tyler.hush" "$LNF_DIR/com.tyler.hush"
ok "installed to $LNF_DIR/com.tyler.hush"

# ---------------------------------------------------------------------------
step "Konsole color scheme"
mkdir -p "$KONSOLE_DIR"
cp "$REPO_ROOT/konsole/Umber.colorscheme" "$KONSOLE_DIR/Umber.colorscheme"
ok "installed to $KONSOLE_DIR/Umber.colorscheme"
note "Konsole: open Settings → Edit Current Profile → Appearance → choose Umber."

# ---------------------------------------------------------------------------
step "VSCode (Microsoft) extension link + cache stub"
if [[ -d "$VSCODE_EXT_DIR" ]] || [[ -d "$HOME/.vscode" ]]; then
    mkdir -p "$VSCODE_EXT_DIR"
    ln -sfn "$REPO_ROOT/hush-vscode" "$VSCODE_EXT_DIR/tyler.hush-1.0.0"
    python3 - <<'PYEOF'
import json, time, pathlib
p = pathlib.Path.home() / ".vscode" / "extensions" / "extensions.json"
if not p.exists():
    p.parent.mkdir(parents=True, exist_ok=True)
    data = []
else:
    try:
        data = json.loads(p.read_text() or "[]")
    except json.JSONDecodeError:
        data = []
if not any(e.get("identifier", {}).get("id") == "tyler.hush" for e in data):
    data.append({
        "identifier": {"id": "tyler.hush"},
        "version": "1.0.0",
        "location": {
            "$mid": 1,
            "path": str(pathlib.Path.home() / ".vscode/extensions/tyler.hush-1.0.0"),
            "scheme": "file",
        },
        "relativeLocation": "tyler.hush-1.0.0",
        "metadata": {
            "installedTimestamp": int(time.time() * 1000),
            "pinned": True,
            "source": "vsix",
        },
    })
    p.write_text(json.dumps(data))
    print("    .. registered tyler.hush in extensions.json")
else:
    print("    .. tyler.hush already registered in extensions.json")
PYEOF
    ok "linked to $VSCODE_EXT_DIR/tyler.hush-1.0.0"
    note "Restart VSCode, then Ctrl+K Ctrl+T → Umber."
else
    note "VSCode (Microsoft) not detected — skipping. For code-oss, ln -sfn $REPO_ROOT/hush-vscode ~/.vscode-oss/extensions/tyler.hush-1.0.0"
fi

# ---------------------------------------------------------------------------
step "Refreshing KDE service cache"
kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
ok "kbuildsycoca6 refreshed"

# ---------------------------------------------------------------------------
step "Applying Global Theme"
# Run from /tmp to avoid kpackagetool6 resolving the source dir as a package path.
( cd /tmp && plasma-apply-lookandfeel -a com.tyler.hush ) || {
    echo "WARNING: plasma-apply-lookandfeel failed — try logging out / back in." >&2
}
# Force-rewrite [WM] inline values by toggling colorscheme.
plasma-apply-colorscheme BreezeLight >/dev/null 2>&1 || true
plasma-apply-colorscheme Umber >/dev/null 2>&1 || true
# plasma-apply-lookandfeel honors [General].ColorScheme but skips [Icons].Theme
# and is unreliable for cursor — apply both explicitly.
changeicons=""
for p in /usr/lib/plasma-changeicons /usr/libexec/plasma-changeicons; do
    [[ -x "$p" ]] && { changeicons="$p"; break; }
done
if [[ -n "$changeicons" ]]; then
    "$changeicons" "$NEWAITA_VARIANT" >/dev/null 2>&1 || true
else
    note "plasma-changeicons helper not found — pick icons manually in System Settings."
fi
plasma-apply-cursortheme Umber-cursor >/dev/null 2>&1 || true
# kscreenlocker_greet resolves its QML from contents/lockscreen/ inside the
# active LookAndFeelPackage (set in kdeglobals by plasma-apply-lookandfeel).
# Each lock spawns a fresh greeter process, so the Umber lockscreen picks up
# the next time the screen locks (no daemon restart needed).
ok "Global Theme applied"

# ---------------------------------------------------------------------------
# SDDM conf.d shadow scan: SDDM's ConfigReader walks /etc/sddm.conf.d/ with
# QDir::entryList(Files|NoDotAndDotDot, LocaleAware) — no extension filter,
# alphabetical merge, last value wins. Any stray file (kde_settings.conf.bak,
# editor swap files, distro leftovers) that defines [Theme]/Current= and
# sorts after kde_settings.conf will silently override Current=hush. Renaming
# inside conf.d cannot fix this; the file must be moved out of the directory.
# This scan is read-only (the dir is world-readable) and builds a tailored
# remediation block printed in the manual-steps section below.
step "Scanning /etc/sddm.conf.d/ for shadow files"
SDDM_CONF_D="/etc/sddm.conf.d"
SDDM_SHADOW_BLOCK=""
if [[ -d "$SDDM_CONF_D" ]]; then
    shadow_files=()
    while IFS= read -r f; do
        [[ -f "$f" ]] || continue
        bn="$(basename "$f")"
        # kde_settings.conf is the canonical file install.sh & the KCM write to.
        [[ "$bn" == "kde_settings.conf" ]] && continue
        # Only flag files that try to set a non-empty theme.
        if grep -qE '^[[:space:]]*Current=[^[:space:]]' "$f" 2>/dev/null; then
            shadow_files+=("$f")
        fi
    done < <(find "$SDDM_CONF_D" -maxdepth 1 -type f 2>/dev/null | LC_ALL=C sort)
    if (( ${#shadow_files[@]} > 0 )); then
        for f in "${shadow_files[@]}"; do
            err "shadow file: $f sets Current= and will override kde_settings.conf"
        done
        SDDM_SHADOW_BLOCK=$'\n\033[1;31m==> SDDM SHADOW FILES DETECTED\033[0m\nSDDM reads every file in /etc/sddm.conf.d/ (no extension filter, alphabetical,\nlast wins). The files below set [Theme]/Current= and will silently override\n/etc/sddm.conf.d/kde_settings.conf. Move them out of the directory to fix\n(content is preserved):\n'
        for f in "${shadow_files[@]}"; do
            SDDM_SHADOW_BLOCK+="    sudo mv \"$f\" \"/etc/$(basename "$f")\""$'\n'
        done
    else
        ok "no shadow files in $SDDM_CONF_D"
    fi
else
    note "$SDDM_CONF_D not present — SDDM may not be installed"
fi

# ---------------------------------------------------------------------------
cat <<EOF
$SDDM_SHADOW_BLOCK
\033[1;33m==> MANUAL STEPS REMAINING\033[0m

These can't be automated by this script (sudo, browser UI, or out-of-process action):

\033[1;36mSDDM (login screen)\033[0m — needs sudo:
    sudo mkdir -p /usr/share/sddm/themes/hush
    sudo cp -r "$REPO_ROOT/hush-sddm/." /usr/share/sddm/themes/hush/
    sudo sed -i 's/^Current=.*/Current=hush/' /etc/sddm.conf.d/kde_settings.conf
  Note: the trailing /. on the source copies contents, so re-running this
  updates an existing install in place (instead of nesting hush-sddm/ inside).
  Any KCM-set background (theme.conf.user, wallpaper png in the theme dir)
  is preserved — only files shipped by Umber are overwritten.
  Heads-up: SDDM reads /etc/sddm.conf.d/ with no extension filter (alphabetical,
  last wins). Don't leave .bak / .orig / editor-swap files in that directory —
  they will silently override Current=hush. The script scans for these above.
  Test windowed first: sddm-greeter-qt6 --test-mode --theme "$REPO_ROOT/hush-sddm"

\033[1;36mLock screen\033[0m — optional, makes kscreenlocker reuse SDDM's wallpaper:
    SDDM_BG="\$(awk -F= '/^background=/{print \$2}' /usr/share/sddm/themes/hush/theme.conf.user 2>/dev/null)"
    [[ -n "\$SDDM_BG" ]] && kwriteconfig6 --file kscreenlockerrc \\
        --group Greeter --group Wallpaper --group org.kde.image --group General \\
        --key Image "/usr/share/sddm/themes/hush/\$SDDM_BG"
  The Umber-styled lock UI (charcoal floor + 0.55 scrim mirroring SDDM) is
  bundled in com.tyler.hush/contents/lockscreen/ and resolved automatically
  by kscreenlocker_greet from the active LookAndFeelPackage in kdeglobals.
  Test it with: loginctl lock-session   (Ctrl+Alt+L on most setups).

\033[1;36mFirefox theme\033[0m — load via about:debugging:
    1. Visit about:debugging#/runtime/this-firefox
    2. "Load Temporary Add-on…" → pick $REPO_ROOT/hush-firefox/manifest.json
  (Stable Firefox unloads unsigned extensions on restart. Sign on AMO or use
   Developer Edition with xpinstall.signatures.required=false for persistence.)

\033[1;36mChromium / Chrome theme\033[0m — load unpacked:
    1. Visit chrome://extensions/
    2. Toggle "Developer mode"
    3. "Load unpacked" → pick $REPO_ROOT/hush-chromium/

EOF

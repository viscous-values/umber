#!/bin/bash
# Hush — one-shot installer for the full theme suite on KDE Plasma 6.
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
[[ -d "$ICONS_DIR/Hush-cursor" ]]    && existing+=("$ICONS_DIR/Hush-cursor")
[[ -f "$SCHEMES_DIR/Hush.colors" ]]  && existing+=("$SCHEMES_DIR/Hush.colors")
if (( ${#existing[@]} > 0 )) && (( ASSUME_YES == 0 )); then
    step "Existing Hush install detected"
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
step "Hush-cursor"
mkdir -p "$ICONS_DIR"
if [[ ! -d "$REPO_ROOT/cursors/Hush-cursor" ]]; then
    echo "ERROR: cursors/Hush-cursor not found in repo. Run scripts/build-cursor.sh." >&2
    exit 1
fi
rm -rf "$ICONS_DIR/Hush-cursor"
cp -a "$REPO_ROOT/cursors/Hush-cursor" "$ICONS_DIR/Hush-cursor"
ok "installed to $ICONS_DIR/Hush-cursor"

# ---------------------------------------------------------------------------
step "Hush color scheme"
mkdir -p "$SCHEMES_DIR"
cp "$REPO_ROOT/com.tyler.hush/contents/colors/Hush.colors" "$SCHEMES_DIR/Hush.colors"
ok "installed to $SCHEMES_DIR/Hush.colors"

# ---------------------------------------------------------------------------
step "Plasma Look-and-Feel package"
mkdir -p "$LNF_DIR"
rm -rf "$LNF_DIR/com.tyler.hush"
cp -a "$REPO_ROOT/com.tyler.hush" "$LNF_DIR/com.tyler.hush"
ok "installed to $LNF_DIR/com.tyler.hush"

# ---------------------------------------------------------------------------
step "Konsole color scheme"
mkdir -p "$KONSOLE_DIR"
cp "$REPO_ROOT/konsole/Hush.colorscheme" "$KONSOLE_DIR/Hush.colorscheme"
ok "installed to $KONSOLE_DIR/Hush.colorscheme"
note "Konsole: open Settings → Edit Current Profile → Appearance → choose Hush."

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
    note "Restart VSCode, then Ctrl+K Ctrl+T → Hush."
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
plasma-apply-colorscheme Hush >/dev/null 2>&1 || true
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
plasma-apply-cursortheme Hush-cursor >/dev/null 2>&1 || true
ok "Global Theme applied"

# ---------------------------------------------------------------------------
cat <<EOF

\033[1;33m==> MANUAL STEPS REMAINING\033[0m

These can't be automated by this script (sudo, browser UI, or out-of-process action):

\033[1;36mSDDM (login screen)\033[0m — needs sudo:
    sudo cp -r "$REPO_ROOT/hush-sddm" /usr/share/sddm/themes/hush
    sudo sed -i 's/^Current=.*/Current=hush/' /etc/sddm.conf.d/kde_settings.conf
  Test windowed first: sddm-greeter-qt6 --test-mode --theme "$REPO_ROOT/hush-sddm"

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

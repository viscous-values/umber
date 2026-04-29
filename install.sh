#!/bin/bash
# Umber — one-shot installer for the full theme suite on KDE Plasma 6.
# Idempotent: safe to re-run. Steps that need root (SDDM theme install,
# /etc/sddm.conf.d/ shadow-file cleanup, /etc/sddm.conf.d/kde_settings.conf
# Current= rewrite, removal of legacy /usr/share/sddm/themes/hush) are
# bundled into a single sudo prompt near the end of the run; the script
# prints the exact commands first and releases the sudo cache (sudo -k)
# as soon as those commands finish.
#
# Usage: ./install.sh [--yes] [--migrate] [--variant NAME] [--no-sudo]
#   --yes         skip the overwrite confirmation (for non-interactive use);
#                 also auto-accepts the sudo offer (sudo itself may still
#                 prompt for the password if no ticket is cached).
#   --migrate     clean up artifacts from the legacy "Hush" install before
#                 installing Umber (refuses to install otherwise if found)
#   --variant N   install variant N instead of canonical Umber.
#                 N ∈ {umber, ash, slate, tide, storm}. Default: umber.
#                 Variants install side-by-side; canonical and any number
#                 of variants can coexist on one machine.
#   --no-sudo     never offer sudo elevation; print all root-needing steps
#                 as manual instructions at the end (legacy behavior).

set -euo pipefail

ASSUME_YES=0
MIGRATE=0
VARIANT="umber"
NO_SUDO=0
while (( $# > 0 )); do
    case "$1" in
        -y|--yes)        ASSUME_YES=1 ;;
        --migrate)       MIGRATE=1 ;;
        --variant)       shift; VARIANT="${1:-}" ;;
        --variant=*)     VARIANT="${1#--variant=}" ;;
        --no-sudo)       NO_SUDO=1 ;;
        -h|--help)
            sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
    shift
done

case "$VARIANT" in
    umber|ash|slate|tide|storm) ;;
    *) echo "ERROR: unknown variant '$VARIANT' (must be one of: umber, ash, slate, tide, storm)" >&2; exit 2 ;;
esac

# ---------------------------------------------------------------------------
# Variant-derived names. For canonical (umber) these collapse to today's
# unsuffixed paths; for variants they pick up the slug everywhere.
if [[ "$VARIANT" == "umber" ]]; then
    SLUG="umber"
    SCHEME="Umber"
    NAME="Umber"
else
    SLUG="umber-$VARIANT"
    SCHEME="Umber-${VARIANT^}"   # Title-case suffix: ash → Ash
    NAME="Umber ${VARIANT^}"
fi
PKG_ID="com.tyler.$SLUG"
SHELL_PKG_ID="$PKG_ID-shell"
SHELL_DIR_NAME="${SLUG}-shell"   # source directory name in repo
SDDM_DIR_NAME="${SLUG}-sddm"
FF_DIR_NAME="${SLUG}-firefox"
CR_DIR_NAME="${SLUG}-chromium"
SCHEME_FILE="${SCHEME}.colors"
KONSOLE_FILE="${SCHEME}.colorscheme"

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

ICONS_DIR="$HOME/.local/share/icons"
SCHEMES_DIR="$HOME/.local/share/color-schemes"
LNF_DIR="$HOME/.local/share/plasma/look-and-feel"
SHELLS_DIR="$HOME/.local/share/plasma/shells"
KONSOLE_DIR="$HOME/.local/share/konsole"
VSCODE_EXT_DIR="$HOME/.vscode/extensions"

NEWAITA_VARIANT="Newaita-reborn-light-brown-dark"
NEWAITA_REPO="https://github.com/cbrnix/Newaita-reborn"

step() { printf "\n\033[1;33m==>\033[0m %s\n" "$1"; }
ok()   { printf "    \033[0;32mok\033[0m %s\n" "$1"; }
note() { printf "    \033[0;36m..\033[0m %s\n" "$1"; }
err()  { printf "\033[1;31mERROR:\033[0m %s\n" "$1" >&2; }

# ---------------------------------------------------------------------------
# Elevated-step orchestration. Every root-needing operation sets a HAS_*
# flag during preflight/scan, then run_pending_elevated() prints the full
# command list, prompts once, acquires sudo, runs everything inline, and
# releases the cache (sudo -k). Result flags (DID_*) drive the post-run
# manual-steps printout — anything that ran is omitted from the tail.
HAS_HUSH_SDDM_REWRITE=0
HAS_HUSH_SDDM_DIR_REMOVE=0
HAS_SHADOW_MOVES=0
HAS_SDDM_INSTALL=0
DID_SDDM_INSTALL=0
DID_SHADOW_MOVES=0
SHADOW_FILES=()
SDDM_THEME_TARGET=""   # filled in after variant resolution
SDDM_KDE_CONF="/etc/sddm.conf.d/kde_settings.conf"

build_elevated_label_list() {
    local labels=()
    local f
    if (( HAS_HUSH_SDDM_REWRITE )); then
        labels+=("sed -i 's/^Current=hush\$/Current=umber/' $SDDM_KDE_CONF")
    fi
    if (( HAS_HUSH_SDDM_DIR_REMOVE )); then
        labels+=("rm -rf /usr/share/sddm/themes/hush")
    fi
    if (( HAS_SHADOW_MOVES )); then
        for f in "${SHADOW_FILES[@]}"; do
            labels+=("mv \"$f\" \"/etc/$(basename "$f")\"")
        done
    fi
    if (( HAS_SDDM_INSTALL )); then
        labels+=("mkdir -p $SDDM_THEME_TARGET")
        labels+=("cp -r \"$REPO_ROOT/$SDDM_DIR_NAME/.\" $SDDM_THEME_TARGET/")
        labels+=("sed -i 's/^Current=.*/Current=$SLUG/' $SDDM_KDE_CONF")
    fi
    printf '%s\n' "${labels[@]}"
}

run_pending_elevated() {
    local total=$(( HAS_HUSH_SDDM_REWRITE + HAS_HUSH_SDDM_DIR_REMOVE \
                    + HAS_SHADOW_MOVES + HAS_SDDM_INSTALL ))
    if (( total == 0 )); then
        return 0
    fi
    step "Elevated steps (sudo)"
    printf "    The following commands need root:\n\n"
    while IFS= read -r label; do
        printf "      $ %s\n" "$label"
    done < <(build_elevated_label_list)
    printf "\n"

    if (( NO_SUDO == 1 )); then
        note "--no-sudo set; skipping. Manual steps printed below."
        return 1
    fi
    if (( ASSUME_YES == 0 )); then
        printf "    Run these with sudo? [y/N] "
        read -r reply
        case "$reply" in
            y|Y|yes|YES) ;;
            *) note "Declined. Manual steps printed below."; return 1 ;;
        esac
    fi
    if ! sudo -v; then
        err "sudo authentication failed; commands above were NOT run."
        return 1
    fi

    local rc=0 f
    if (( HAS_HUSH_SDDM_REWRITE )); then
        if sudo sed -i 's/^Current=hush$/Current=umber/' "$SDDM_KDE_CONF"; then
            ok "rewrote Current=hush -> Current=umber in $SDDM_KDE_CONF"
        else
            err "failed: sed Current=hush -> umber in $SDDM_KDE_CONF"; rc=1
        fi
    fi
    if (( HAS_HUSH_SDDM_DIR_REMOVE )); then
        if sudo rm -rf /usr/share/sddm/themes/hush; then
            ok "removed legacy /usr/share/sddm/themes/hush"
        else
            err "failed: rm -rf /usr/share/sddm/themes/hush"; rc=1
        fi
    fi
    if (( HAS_SHADOW_MOVES )); then
        for f in "${SHADOW_FILES[@]}"; do
            if sudo mv "$f" "/etc/$(basename "$f")"; then
                ok "moved $f -> /etc/$(basename "$f")"
            else
                err "failed: mv $f"; rc=1
            fi
        done
        DID_SHADOW_MOVES=1
    fi
    if (( HAS_SDDM_INSTALL )); then
        if sudo mkdir -p "$SDDM_THEME_TARGET" \
            && sudo cp -r "$REPO_ROOT/$SDDM_DIR_NAME/." "$SDDM_THEME_TARGET/" \
            && sudo sed -i "s/^Current=.*/Current=$SLUG/" "$SDDM_KDE_CONF"; then
            ok "SDDM theme installed at $SDDM_THEME_TARGET; Current=$SLUG"
            DID_SDDM_INSTALL=1
        else
            err "SDDM theme install failed; rerun manually if needed"; rc=1
        fi
    fi

    sudo -k 2>/dev/null || true
    if (( rc == 0 )); then
        ok "all elevated steps complete; sudo cache released"
    else
        note "some elevated steps failed; sudo cache released"
    fi
    return $rc
}

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
step "Preflight (variant: $NAME)"
require_bin plasma-apply-lookandfeel  "plasma-workspace"
require_bin plasma-apply-colorscheme  "plasma-workspace"
require_bin kwriteconfig6             "kconfig"
require_bin kbuildsycoca6             "kservice"
require_bin git                       "git"
require_bin python3                   "python"
ok "all required commands present"

# Warn (don't fail) if any consumer file drifts from its template. Catches a
# forgotten `python scripts/render_palette.py render` after editing a palette.
if python3 "$REPO_ROOT/scripts/render_palette.py" check >/dev/null 2>&1; then
    ok "palette consumer files in sync with palette TOMLs"
else
    note "consumer files differ from palette TOMLs — run: python scripts/render_palette.py render [--palette palettes/<name>.toml]"
fi

# Sanity: the source dirs for THIS variant must exist in the repo.
for src in "$REPO_ROOT/$PKG_ID" "$REPO_ROOT/$SHELL_DIR_NAME" \
           "$REPO_ROOT/$SDDM_DIR_NAME" \
           "$REPO_ROOT/$FF_DIR_NAME" "$REPO_ROOT/$CR_DIR_NAME"; do
    if [[ ! -d "$src" ]]; then
        err "missing variant source directory: $src"
        printf "       Run: python scripts/render_palette.py render --palette palettes/%s.toml\n" "$VARIANT" >&2
        exit 1
    fi
done

# ---------------------------------------------------------------------------
# Overwrite confirmation — scoped to THIS variant's paths so installing
# (e.g.) ash never warns about canonical Umber being present.
existing=()
[[ -d "$LNF_DIR/$PKG_ID" ]]                 && existing+=("$LNF_DIR/$PKG_ID")
[[ -d "$SHELLS_DIR/$SHELL_PKG_ID" ]]        && existing+=("$SHELLS_DIR/$SHELL_PKG_ID")
[[ -d "$ICONS_DIR/Umber-cursor" ]]          && existing+=("$ICONS_DIR/Umber-cursor")
[[ -f "$SCHEMES_DIR/$SCHEME_FILE" ]]        && existing+=("$SCHEMES_DIR/$SCHEME_FILE")
if (( ${#existing[@]} > 0 )) && (( ASSUME_YES == 0 )); then
    step "Existing $NAME install detected"
    for p in "${existing[@]}"; do note "will overwrite: $p"; done
    printf "    Continue? [y/N] "
    read -r reply
    case "$reply" in
        y|Y|yes|YES) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
fi

# ---------------------------------------------------------------------------
# Hush → Umber migration. Variant-agnostic: cleans up artifacts from the
# legacy "Hush" project name on the system regardless of which Umber variant
# is being installed now. Only rewrites configs to canonical "Umber" — the
# variant-specific apply step at the end retargets to $NAME if needed.
hush_artifacts=()
[[ -d "$LNF_DIR/com.tyler.hush" ]]       && hush_artifacts+=("$LNF_DIR/com.tyler.hush")
[[ -f "$SCHEMES_DIR/Hush.colors" ]]      && hush_artifacts+=("$SCHEMES_DIR/Hush.colors")
[[ -d "$ICONS_DIR/Hush-cursor" ]]        && hush_artifacts+=("$ICONS_DIR/Hush-cursor")
[[ -f "$KONSOLE_DIR/Hush.colorscheme" ]] && hush_artifacts+=("$KONSOLE_DIR/Hush.colorscheme")
[[ -e "$VSCODE_EXT_DIR/tyler.hush-1.0.0" ]] && hush_artifacts+=("$VSCODE_EXT_DIR/tyler.hush-1.0.0")

if (( ${#hush_artifacts[@]} > 0 )); then
    if (( MIGRATE == 1 )); then
        step "Migrating from Hush"
        for p in "${hush_artifacts[@]}"; do
            if [[ -L "$p" ]]; then
                unlink "$p"
                ok "unlinked $p"
            else
                rm -rf "$p"
                ok "removed $p"
            fi
        done
        for cfg in "$HOME/.config/kdedefaults/kdeglobals" "$HOME/.config/kdeglobals"; do
            [[ -f "$cfg" ]] || continue
            if grep -q '^ColorScheme=Hush$' "$cfg" 2>/dev/null; then
                sed -i 's/^ColorScheme=Hush$/ColorScheme=Umber/' "$cfg"
                ok "rewrote ColorScheme= in $cfg"
            fi
            if grep -q '^LookAndFeelPackage=com\.tyler\.hush$' "$cfg" 2>/dev/null; then
                sed -i 's|^LookAndFeelPackage=com\.tyler\.hush$|LookAndFeelPackage=com.tyler.umber|' "$cfg"
                ok "rewrote LookAndFeelPackage= in $cfg"
            fi
        done
        if [[ -f "$HOME/.config/plasmarc" ]] && grep -q '^name=com\.tyler\.hush$' "$HOME/.config/plasmarc" 2>/dev/null; then
            sed -i 's|^name=com\.tyler\.hush$|name=com.tyler.umber|' "$HOME/.config/plasmarc"
            ok "rewrote name= in plasmarc"
        fi
        if [[ -f "$HOME/.config/kcminputrc" ]] && grep -q '^cursorTheme=Hush-cursor$' "$HOME/.config/kcminputrc" 2>/dev/null; then
            sed -i 's/^cursorTheme=Hush-cursor$/cursorTheme=Umber-cursor/' "$HOME/.config/kcminputrc"
            ok "rewrote cursorTheme= in kcminputrc"
        fi
        if [[ -f "$VSCODE_EXT_DIR/extensions.json" ]]; then
            python3 - <<'PYEOF'
import json, pathlib
p = pathlib.Path.home() / ".vscode" / "extensions" / "extensions.json"
try:
    data = json.loads(p.read_text() or "[]")
except (FileNotFoundError, json.JSONDecodeError):
    data = []
before = len(data)
data = [e for e in data if e.get("identifier", {}).get("id") != "tyler.hush"]
if len(data) != before:
    p.write_text(json.dumps(data))
    print("    .. removed tyler.hush entry from extensions.json")
PYEOF
        fi
        # SDDM-side leftovers need root; queue for the consolidated sudo block.
        if [[ -f "$SDDM_KDE_CONF" ]] && grep -q '^Current=hush$' "$SDDM_KDE_CONF" 2>/dev/null; then
            HAS_HUSH_SDDM_REWRITE=1
            note "queued: rewrite Current=hush -> Current=umber in $SDDM_KDE_CONF"
        fi
        if [[ -d /usr/share/sddm/themes/hush ]]; then
            HAS_HUSH_SDDM_DIR_REMOVE=1
            note "queued: remove legacy /usr/share/sddm/themes/hush"
        fi
        note "Firefox: remove the old hush@tyler temporary add-on from about:debugging before loading Umber."
        ok "Hush user-space migration complete (any queued root steps run later)"
    else
        step "Existing Hush install detected"
        for p in "${hush_artifacts[@]}"; do note "$p"; done
        cat <<EOF

The previous "Hush" install must be cleaned up before installing Umber.
Re-run with --migrate to do this automatically:

    ./install.sh --migrate

Or remove the artifacts manually:

EOF
        for p in "${hush_artifacts[@]}"; do echo "    rm -rf $p"; done
        cat <<EOF

Plus rewrite these config keys if present:
    ~/.config/kdedefaults/kdeglobals    ColorScheme=Hush             → Umber
                                         LookAndFeelPackage=com.tyler.hush → com.tyler.umber
    ~/.config/plasmarc                  name=com.tyler.hush          → com.tyler.umber
    ~/.config/kcminputrc                cursorTheme=Hush-cursor      → Umber-cursor
    /etc/sddm.conf.d/kde_settings.conf  Current=hush                 → umber  (needs sudo)
    ~/.vscode/extensions/extensions.json   remove tyler.hush entry

Refusing to install on top of existing Hush state to avoid the dual-install
footgun (both themes half-applied across config files).
EOF
        exit 1
    fi
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
step "$NAME color scheme"
mkdir -p "$SCHEMES_DIR"
cp "$REPO_ROOT/$PKG_ID/contents/colors/$SCHEME_FILE" "$SCHEMES_DIR/$SCHEME_FILE"
ok "installed to $SCHEMES_DIR/$SCHEME_FILE"

# ---------------------------------------------------------------------------
step "Plasma Look-and-Feel package ($PKG_ID)"
mkdir -p "$LNF_DIR"
rm -rf "$LNF_DIR/$PKG_ID"
cp -a "$REPO_ROOT/$PKG_ID" "$LNF_DIR/$PKG_ID"
ok "installed to $LNF_DIR/$PKG_ID"

# ---------------------------------------------------------------------------
# Plasma 6's kscreenlocker reads its QML from a Plasma/Shell package selected
# by [Greeter]/Theme in kscreenlockerrc — independent of the LookAndFeel
# package. The shell package ships only contents/lockscreen/ and falls back
# to org.kde.plasma.desktop for everything else.
step "Plasma Shell package ($SHELL_PKG_ID)"
mkdir -p "$SHELLS_DIR"
rm -rf "$SHELLS_DIR/$SHELL_PKG_ID"
cp -a "$REPO_ROOT/$SHELL_DIR_NAME" "$SHELLS_DIR/$SHELL_PKG_ID"
ok "installed to $SHELLS_DIR/$SHELL_PKG_ID"
kwriteconfig6 --file kscreenlockerrc --group Greeter --key Theme "$SHELL_PKG_ID"
ok "kscreenlockerrc [Greeter]/Theme = $SHELL_PKG_ID"

# ---------------------------------------------------------------------------
step "Konsole color scheme"
mkdir -p "$KONSOLE_DIR"
cp "$REPO_ROOT/konsole/$KONSOLE_FILE" "$KONSOLE_DIR/$KONSOLE_FILE"
ok "installed to $KONSOLE_DIR/$KONSOLE_FILE"
note "Konsole: open Settings → Edit Current Profile → Appearance → choose $NAME."

# ---------------------------------------------------------------------------
# VSCode extension is shared across all variants — a single extension dir
# (umber-vscode/) registers all five themes via package.json contributes.
# Theme picker shows: Umber, Umber Ash, Umber Slate, Umber Tide, Umber Storm.
step "VSCode (Microsoft) extension link + cache stub"
if [[ -d "$VSCODE_EXT_DIR" ]] || [[ -d "$HOME/.vscode" ]]; then
    mkdir -p "$VSCODE_EXT_DIR"
    ln -sfn "$REPO_ROOT/umber-vscode" "$VSCODE_EXT_DIR/tyler.umber-1.0.0"
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
if not any(e.get("identifier", {}).get("id") == "tyler.umber" for e in data):
    data.append({
        "identifier": {"id": "tyler.umber"},
        "version": "1.0.0",
        "location": {
            "$mid": 1,
            "path": str(pathlib.Path.home() / ".vscode/extensions/tyler.umber-1.0.0"),
            "scheme": "file",
        },
        "relativeLocation": "tyler.umber-1.0.0",
        "metadata": {
            "installedTimestamp": int(time.time() * 1000),
            "pinned": True,
            "source": "vsix",
        },
    })
    p.write_text(json.dumps(data))
    print("    .. registered tyler.umber in extensions.json")
else:
    print("    .. tyler.umber already registered in extensions.json")
PYEOF
    ok "linked to $VSCODE_EXT_DIR/tyler.umber-1.0.0"
    note "Restart VSCode, then Ctrl+K Ctrl+T → $NAME (or any sibling variant)."
else
    note "VSCode (Microsoft) not detected — skipping. For code-oss, ln -sfn $REPO_ROOT/umber-vscode ~/.vscode-oss/extensions/tyler.umber-1.0.0"
fi

# ---------------------------------------------------------------------------
step "Refreshing KDE service cache"
kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
ok "kbuildsycoca6 refreshed"

# ---------------------------------------------------------------------------
step "Applying Global Theme ($NAME)"
( cd /tmp && plasma-apply-lookandfeel -a "$PKG_ID" ) || {
    echo "WARNING: plasma-apply-lookandfeel failed — try logging out / back in." >&2
}
plasma-apply-colorscheme BreezeLight >/dev/null 2>&1 || true
plasma-apply-colorscheme "$SCHEME" >/dev/null 2>&1 || true
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
ok "Global Theme applied ($NAME)"

# ---------------------------------------------------------------------------
step "Scanning /etc/sddm.conf.d/ for shadow files"
SDDM_CONF_D="/etc/sddm.conf.d"
SDDM_THEME_TARGET="/usr/share/sddm/themes/$SLUG"
if [[ -d "$SDDM_CONF_D" ]]; then
    while IFS= read -r f; do
        [[ -f "$f" ]] || continue
        bn="$(basename "$f")"
        [[ "$bn" == "kde_settings.conf" ]] && continue
        if grep -qE '^[[:space:]]*Current=[^[:space:]]' "$f" 2>/dev/null; then
            SHADOW_FILES+=("$f")
        fi
    done < <(find "$SDDM_CONF_D" -maxdepth 1 -type f 2>/dev/null | LC_ALL=C sort)
    if (( ${#SHADOW_FILES[@]} > 0 )); then
        HAS_SHADOW_MOVES=1
        for f in "${SHADOW_FILES[@]}"; do
            err "shadow file: $f sets Current= and will override kde_settings.conf"
        done
    else
        ok "no shadow files in $SDDM_CONF_D"
    fi
    HAS_SDDM_INSTALL=1
else
    note "$SDDM_CONF_D not present — SDDM may not be installed; skipping SDDM steps"
fi

# ---------------------------------------------------------------------------
# Run all queued elevated work in a single sudo prompt; sudo -k afterward.
run_pending_elevated || true

# ---------------------------------------------------------------------------
# Print only the manual steps that did NOT auto-run.
printf "\n\033[1;33m==> MANUAL STEPS REMAINING (%s)\033[0m\n\n" "$NAME"

if (( HAS_SDDM_INSTALL == 1 )) && (( DID_SDDM_INSTALL == 0 )); then
    cat <<EOF
\033[1;36mSDDM (login screen)\033[0m — root steps not run (declined, --no-sudo, or auth failed):
    sudo mkdir -p $SDDM_THEME_TARGET
    sudo cp -r "$REPO_ROOT/$SDDM_DIR_NAME/." $SDDM_THEME_TARGET/
    sudo sed -i 's/^Current=.*/Current=$SLUG/' $SDDM_KDE_CONF
  Trailing /. copies contents in place so re-running updates instead of nesting.
  Heads-up: SDDM reads $SDDM_CONF_D with no extension filter (alphabetical,
  last wins). Don't leave .bak / .orig / editor-swap files in that directory —
  they silently override Current=$SLUG. The script scans for these above.
  Test windowed first: sddm-greeter-qt6 --test-mode --theme "$REPO_ROOT/$SDDM_DIR_NAME"

EOF
fi

if (( HAS_SHADOW_MOVES == 1 )) && (( DID_SHADOW_MOVES == 0 )); then
    printf "\033[1;36mSDDM shadow files\033[0m — root steps not run; move out of conf.d (content preserved):\n"
    for f in "${SHADOW_FILES[@]}"; do
        printf "    sudo mv \"%s\" \"/etc/%s\"\n" "$f" "$(basename "$f")"
    done
    printf "\n"
fi

cat <<EOF
\033[1;36mLock screen\033[0m — optional, makes kscreenlocker reuse SDDM's wallpaper:
    SDDM_BG="\$(awk -F= '/^background=/{print \$2}' $SDDM_THEME_TARGET/theme.conf.user 2>/dev/null)"
    [[ -n "\$SDDM_BG" ]] && kwriteconfig6 --file kscreenlockerrc \\
        --group Greeter --group Wallpaper --group org.kde.image --group General \\
        --key Image "$SDDM_THEME_TARGET/\$SDDM_BG"
  The $NAME-styled lock UI is bundled as a Plasma/Shell package at
  $SHELL_DIR_NAME/ and activated by setting kscreenlockerrc [Greeter]/Theme =
  $SHELL_PKG_ID (done above). Test with: loginctl lock-session.

\033[1;36mFirefox theme\033[0m — load via about:debugging:
    1. Visit about:debugging#/runtime/this-firefox
    2. "Load Temporary Add-on…" → pick $REPO_ROOT/$FF_DIR_NAME/manifest.json
  (Stable Firefox unloads unsigned extensions on restart. Sign on AMO or use
   Developer Edition with xpinstall.signatures.required=false for persistence.)

\033[1;36mChromium / Chrome theme\033[0m — load unpacked:
    1. Visit chrome://extensions/
    2. Toggle "Developer mode"
    3. "Load unpacked" → pick $REPO_ROOT/$CR_DIR_NAME/

EOF

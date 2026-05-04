#!/bin/bash
# Umber — one-shot installer for the full theme suite on KDE Plasma 6.
# Idempotent: safe to re-run. Steps that need root (SDDM theme install,
# /etc/sddm.conf.d/ shadow-file cleanup, /etc/sddm.conf.d/kde_settings.conf
# Current= rewrite, removal of legacy /usr/share/sddm/themes/hush) are
# bundled into a single sudo prompt that fires AFTER the user-space file
# installs but BEFORE the live Plasma reload — so if plasma-apply-lookandfeel
# wedges the running session, all persistent state is already on disk and a
# logout/login finishes the job. The script prints the exact commands first
# and releases the sudo cache (sudo -k) as soon as those commands finish.
#
# Usage: ./install.sh [--yes] [--migrate] [--variant N] [--all-variants] [--no-sudo]
#   --yes           skip the overwrite confirmation (for non-interactive use);
#                   also auto-accepts the sudo offer (sudo itself may still
#                   prompt for the password if no ticket is cached).
#   --migrate       clean up artifacts from the legacy "Hush" install before
#                   installing Umber (refuses to install otherwise if found)
#   --variant N     install variant N. N ∈ {umber, ash, slate, tide, storm}.
#                   Default: umber. With --all-variants this names the ACTIVE
#                   variant (the one applied to the live session and set as
#                   SDDM Current=); otherwise it's the only variant installed.
#                   Variants install side-by-side; canonical and any number of
#                   variants can coexist on a single machine.
#   --all-variants  install canonical + every variant (umber, ash, slate, tide,
#                   storm) in one run. Live Plasma apply runs once at the end
#                   for the active variant (canonical Umber unless --variant
#                   is also given). One sudo prompt, one apply.
#   --no-sudo       never offer sudo elevation; print all root-needing steps
#                   as manual instructions at the end (legacy behavior).

set -euo pipefail

ASSUME_YES=0
MIGRATE=0
VARIANT="umber"
ALL_VARIANTS=0
NO_SUDO=0
VARIANT_EXPLICIT=0   # tracks whether user passed --variant (for --all-variants combo)
while (( $# > 0 )); do
    case "$1" in
        -y|--yes)         ASSUME_YES=1 ;;
        --migrate)        MIGRATE=1 ;;
        --variant)        shift; VARIANT="${1:-}"; VARIANT_EXPLICIT=1 ;;
        --variant=*)      VARIANT="${1#--variant=}"; VARIANT_EXPLICIT=1 ;;
        --all-variants)   ALL_VARIANTS=1 ;;
        --no-sudo)        NO_SUDO=1 ;;
        -h|--help)
            sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
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
# Variant set + active variant. Without --all-variants exactly one variant
# installs and is also the active one. With --all-variants all five install
# and ACTIVE_VARIANT (live-applied + SDDM Current=) defaults to canonical
# Umber; pass --variant N alongside --all-variants to override.
if (( ALL_VARIANTS == 1 )); then
    VARIANTS_TO_INSTALL=(umber ash slate tide storm)
    if (( VARIANT_EXPLICIT == 1 )); then
        ACTIVE_VARIANT="$VARIANT"
    else
        ACTIVE_VARIANT="umber"
    fi
else
    VARIANTS_TO_INSTALL=("$VARIANT")
    ACTIVE_VARIANT="$VARIANT"
fi

# ---------------------------------------------------------------------------
# Variant-derived names. Sets SLUG/SCHEME/NAME/PKG_ID/SHELL_PKG_ID/etc as
# globals based on the variant passed in. Canonical (umber) collapses to
# unsuffixed paths; everything else picks up the umber-<v> / Umber-<V> slug.
# Per-variant installs re-call this inside their loop; everything else uses
# whatever variant was set last (typically ACTIVE_VARIANT).
set_variant_names() {
    local v="$1"
    if [[ "$v" == "umber" ]]; then
        SLUG="umber"
        SCHEME="Umber"
        NAME="Umber"
    else
        SLUG="umber-$v"
        SCHEME="Umber-${v^}"   # Title-case suffix: ash → Ash
        NAME="Umber ${v^}"
    fi
    PKG_ID="com.tyler.$SLUG"
    SHELL_PKG_ID="$PKG_ID-shell"
    SHELL_DIR_NAME="${SLUG}-shell"     # source dir in repo
    SDDM_DIR_NAME="${SLUG}-sddm"
    FF_DIR_NAME="${SLUG}-firefox"
    CR_DIR_NAME="${SLUG}-chromium"
    SCHEME_FILE="${SCHEME}.colors"
    KONSOLE_FILE="${SCHEME}.colorscheme"
    SDDM_THEME_TARGET="/usr/share/sddm/themes/$SLUG"
}

# Stateless slug resolver — used in spots that build paths without needing
# to mutate the full set of globals (label-list builder, manual-steps tail).
slug_for() {
    if [[ "$1" == "umber" ]]; then echo "umber"; else echo "umber-$1"; fi
}

set_variant_names "$ACTIVE_VARIANT"

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
# Elevated-step orchestration. Hush-migration leftovers and the SDDM shadow
# scan set HAS_* flags; per-variant SDDM theme installs accumulate into the
# SDDM_INSTALL_VARIANTS array (populated only if /etc/sddm.conf.d exists).
# run_pending_elevated() prints the full command list, prompts once,
# acquires sudo, runs everything inline, and releases the cache (sudo -k).
# DID_* flags drive the post-run manual-steps printout — anything that ran
# is omitted from the tail.
HAS_HUSH_SDDM_REWRITE=0
HAS_HUSH_SDDM_DIR_REMOVE=0
HAS_SHADOW_MOVES=0
DID_SDDM_INSTALL=0
DID_SHADOW_MOVES=0
SHADOW_FILES=()
SDDM_INSTALL_VARIANTS=()
SDDM_KDE_CONF="/etc/sddm.conf.d/kde_settings.conf"

build_elevated_label_list() {
    local labels=()
    local f v slug target dir_name active_slug
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
    if (( ${#SDDM_INSTALL_VARIANTS[@]} > 0 )); then
        for v in "${SDDM_INSTALL_VARIANTS[@]}"; do
            slug=$(slug_for "$v")
            dir_name="${slug}-sddm"
            target="/usr/share/sddm/themes/$slug"
            labels+=("mkdir -p $target")
            labels+=("cp -r \"$REPO_ROOT/$dir_name/.\" $target/")
        done
        active_slug=$(slug_for "$ACTIVE_VARIANT")
        labels+=("sed -i 's/^Current=.*/Current=$active_slug/' $SDDM_KDE_CONF")
    fi
    printf '%s\n' "${labels[@]}"
}

run_pending_elevated() {
    local total=$(( HAS_HUSH_SDDM_REWRITE + HAS_HUSH_SDDM_DIR_REMOVE \
                    + HAS_SHADOW_MOVES + ${#SDDM_INSTALL_VARIANTS[@]} ))
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

    local rc=0 f v slug target dir_name active_slug install_rc
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
    if (( ${#SDDM_INSTALL_VARIANTS[@]} > 0 )); then
        install_rc=0
        for v in "${SDDM_INSTALL_VARIANTS[@]}"; do
            slug=$(slug_for "$v")
            dir_name="${slug}-sddm"
            target="/usr/share/sddm/themes/$slug"
            if sudo mkdir -p "$target" \
                && sudo cp -r "$REPO_ROOT/$dir_name/." "$target/"; then
                ok "SDDM theme installed at $target"
            else
                err "SDDM theme install failed for variant $v"; install_rc=1
            fi
        done
        if (( install_rc == 0 )); then
            active_slug=$(slug_for "$ACTIVE_VARIANT")
            if sudo sed -i "s/^Current=.*/Current=$active_slug/" "$SDDM_KDE_CONF"; then
                ok "SDDM Current=$active_slug (active variant)"
                DID_SDDM_INSTALL=1
            else
                err "failed to write Current=$active_slug to $SDDM_KDE_CONF"; rc=1
            fi
        else
            rc=1
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
if (( ALL_VARIANTS == 1 )); then
    step "Preflight (all variants; active: $NAME)"
else
    step "Preflight (variant: $NAME)"
fi
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

# Sanity: every variant we plan to install must have its source dirs in the repo.
for v in "${VARIANTS_TO_INSTALL[@]}"; do
    set_variant_names "$v"
    for src in "$REPO_ROOT/$PKG_ID" "$REPO_ROOT/$SHELL_DIR_NAME" \
               "$REPO_ROOT/$SDDM_DIR_NAME" \
               "$REPO_ROOT/$FF_DIR_NAME" "$REPO_ROOT/$CR_DIR_NAME"; do
        if [[ ! -d "$src" ]]; then
            err "missing variant source directory: $src"
            printf "       Run: python scripts/render_palette.py render --palette palettes/%s.toml\n" "$v" >&2
            exit 1
        fi
    done
done
set_variant_names "$ACTIVE_VARIANT"

# ---------------------------------------------------------------------------
# Overwrite confirmation — combined across every variant being installed,
# plus the shared cursor dir. One prompt covers the whole batch.
existing=()
for v in "${VARIANTS_TO_INSTALL[@]}"; do
    set_variant_names "$v"
    [[ -d "$LNF_DIR/$PKG_ID" ]]           && existing+=("$LNF_DIR/$PKG_ID")
    [[ -d "$SHELLS_DIR/$SHELL_PKG_ID" ]]  && existing+=("$SHELLS_DIR/$SHELL_PKG_ID")
    [[ -f "$SCHEMES_DIR/$SCHEME_FILE" ]]  && existing+=("$SCHEMES_DIR/$SCHEME_FILE")
    [[ -f "$KONSOLE_DIR/$KONSOLE_FILE" ]] && existing+=("$KONSOLE_DIR/$KONSOLE_FILE")
done
[[ -d "$ICONS_DIR/Umber-cursor" ]] && existing+=("$ICONS_DIR/Umber-cursor")
set_variant_names "$ACTIVE_VARIANT"
if (( ${#existing[@]} > 0 )) && (( ASSUME_YES == 0 )); then
    if (( ALL_VARIANTS == 1 )); then
        step "Existing install detected (all variants)"
    else
        step "Existing $NAME install detected"
    fi
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
# legacy "Hush" project name on the system regardless of which Umber variants
# are being installed now. Only rewrites configs to canonical "Umber" — the
# active variant's apply step at the end retargets to $NAME if needed.
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
# Per-variant user-space installs: color scheme + LookAndFeel package +
# Plasma/Shell package + Konsole color scheme. Each variant installs into
# its own paths (com.tyler.umber-ash/, etc.) and they coexist on disk.
# kscreenlockerrc Theme= is set ONCE below for the active variant only —
# it's a global setting, not per-variant.
mkdir -p "$LNF_DIR" "$SHELLS_DIR" "$SCHEMES_DIR" "$KONSOLE_DIR"

install_variant_user_files() {
    local v="$1"
    set_variant_names "$v"

    step "$NAME color scheme"
    cp "$REPO_ROOT/$PKG_ID/contents/colors/$SCHEME_FILE" "$SCHEMES_DIR/$SCHEME_FILE"
    ok "installed to $SCHEMES_DIR/$SCHEME_FILE"

    step "Plasma Look-and-Feel package ($PKG_ID)"
    rm -rf "$LNF_DIR/$PKG_ID"
    cp -a "$REPO_ROOT/$PKG_ID" "$LNF_DIR/$PKG_ID"
    # Strip contents/colors/ from the INSTALLED package. If a LnF package
    # ships a colors/ dir, Plasma 6's plasma-apply-lookandfeel — the same
    # code path System Settings → Global Theme → Apply uses — wipes every
    # [Colors:*] section out of ~/.config/kdeglobals and does NOT
    # repopulate from ~/.local/share/color-schemes/, so KDE apps fall back
    # to compiled-in Breeze Light defaults (white frames, white app bg,
    # blue selection — see Umber-Ash screenshot). The .colors source-of-
    # truth lives in the source dir for the renderer; the user-level copy
    # at $SCHEMES_DIR/$SCHEME_FILE (installed just above) is what
    # plasma-apply-colorscheme reads.
    rm -rf "$LNF_DIR/$PKG_ID/contents/colors"
    ok "installed to $LNF_DIR/$PKG_ID"

    # Plasma 6's kscreenlocker reads its QML from a Plasma/Shell package
    # selected by [Greeter]/Theme in kscreenlockerrc — independent of the
    # LookAndFeel package. The shell package ships only contents/lockscreen/
    # and falls back to org.kde.plasma.desktop for everything else.
    step "Plasma Shell package ($SHELL_PKG_ID)"
    rm -rf "$SHELLS_DIR/$SHELL_PKG_ID"
    cp -a "$REPO_ROOT/$SHELL_DIR_NAME" "$SHELLS_DIR/$SHELL_PKG_ID"
    ok "installed to $SHELLS_DIR/$SHELL_PKG_ID"

    step "$NAME Konsole color scheme"
    cp "$REPO_ROOT/konsole/$KONSOLE_FILE" "$KONSOLE_DIR/$KONSOLE_FILE"
    ok "installed to $KONSOLE_DIR/$KONSOLE_FILE"
}

for v in "${VARIANTS_TO_INSTALL[@]}"; do
    install_variant_user_files "$v"
done

# kscreenlockerrc Theme= → ACTIVE variant's shell package (the loop can't
# set it per-variant since it's a single global key).
set_variant_names "$ACTIVE_VARIANT"
kwriteconfig6 --file kscreenlockerrc --group Greeter --key Theme "$SHELL_PKG_ID"
ok "kscreenlockerrc [Greeter]/Theme = $SHELL_PKG_ID (active variant: $NAME)"
note "Konsole: open Settings → Edit Current Profile → Appearance → choose $NAME (or any installed sibling)."

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
# SDDM scan + elevated steps run BEFORE the live Plasma reload below.
# plasma-apply-lookandfeel can wedge plasmashell/kwin on some setups; if it
# does, every persistent change (file installs + root steps) is already on
# disk and a logout/login finishes the job. Asking for sudo here also means
# the user gets prompted mid-run, not after a long silent tail.
step "Scanning /etc/sddm.conf.d/ for shadow files"
SDDM_CONF_D="/etc/sddm.conf.d"
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
    # Queue every installed variant's SDDM theme for the elevated block.
    SDDM_INSTALL_VARIANTS=("${VARIANTS_TO_INSTALL[@]}")
else
    note "$SDDM_CONF_D not present — SDDM may not be installed; skipping SDDM steps"
fi

# Run all queued elevated work in a single sudo prompt; sudo -k afterward.
run_pending_elevated || true

# ---------------------------------------------------------------------------
# Live Plasma reload last — anything noisy or wedge-prone happens here.
# plasma-apply-lookandfeel's stderr goes to a logfile (matches sibling
# commands' quietness, but keeps the evidence around for triage). We apply
# the active variant only, regardless of how many were just installed.
#
# Plasma 6 quirk: plasma-apply-lookandfeel for any LnF package that ships
# a contents/colors/ dir STRIPS every [Colors:*] section out of
# ~/.config/kdeglobals and does NOT repopulate. We strip contents/colors/
# from the INSTALLED package above to dodge the bug — and still run the
# plasma-apply-colorscheme dance below as defense-in-depth so a re-install
# repopulates kdeglobals if a previous install left it stripped.
#
# Failures here are noisy on purpose: the previous quiet-and-continue mode
# hid the case where one step silently no-op'd and the user saw a wiped
# kdeglobals (no [Colors:*]) with no clue why "window backgrounds didn't
# change". If something fails, we want to see it.
set_variant_names "$ACTIVE_VARIANT"
step "Applying Global Theme ($NAME)"
LNF_APPLY_LOG="$(mktemp -t umber-lnf-apply-XXXXXX.log)"
# IMPORTANT: must run from a directory that has no com.tyler.umber* sibling.
# Run from $REPO_ROOT and KPackage's cwd scanner finds the source dir,
# resolves to "com.tyler.umber-ash/" (note trailing slash), then the binary
# fails to load it: "Unable to find the theme named com.tyler.umber-ash/".
( cd /tmp && plasma-apply-lookandfeel -a "$PKG_ID" ) >"$LNF_APPLY_LOG" 2>&1 \
    && ok "plasma-apply-lookandfeel $PKG_ID" \
    || err "plasma-apply-lookandfeel failed — see $LNF_APPLY_LOG; logout/login may be needed"
if plasma-apply-colorscheme BreezeLight 2>&1 | sed 's/^/    /'; then :; else
    err "plasma-apply-colorscheme BreezeLight failed (intermediate flicker step)"
fi
if plasma-apply-colorscheme "$SCHEME" 2>&1 | sed 's/^/    /'; then :; else
    err "plasma-apply-colorscheme $SCHEME failed — kdeglobals may have stale colors"
fi
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

# Sanity check: did kdeglobals actually get [Colors:Window] populated?
# If not, the apply silently no-op'd and running apps will keep stale
# colors until logout/login. Surface this clearly.
if grep -q '^\[Colors:Window\]' "$HOME/.config/kdeglobals" 2>/dev/null; then
    ok "Global Theme applied ($NAME) — kdeglobals has [Colors:*] sections"
else
    err "Global Theme apply finished but ~/.config/kdeglobals has no [Colors:*] sections."
    note "Running apps will keep stale colors. Try: plasma-apply-colorscheme $SCHEME"
    note "If that says \"already set\", first run: plasma-apply-colorscheme BreezeLight"
    note "Worst case: log out and back in to refresh every running app."
fi

# ---------------------------------------------------------------------------
# Print only the manual steps that did NOT auto-run.
printf "\n\033[1;33m==> MANUAL STEPS REMAINING\033[0m\n\n"

if (( ${#SDDM_INSTALL_VARIANTS[@]} > 0 )) && (( DID_SDDM_INSTALL == 0 )); then
    printf "\033[1;36mSDDM (login screen)\033[0m — root steps not run (declined, --no-sudo, or auth failed):\n"
    for v in "${SDDM_INSTALL_VARIANTS[@]}"; do
        slug=$(slug_for "$v")
        target="/usr/share/sddm/themes/$slug"
        printf "    sudo mkdir -p %s\n" "$target"
        printf "    sudo cp -r \"%s/%s-sddm/.\" %s/\n" "$REPO_ROOT" "$slug" "$target"
    done
    active_slug=$(slug_for "$ACTIVE_VARIANT")
    printf "    sudo sed -i 's/^Current=.*/Current=%s/' %s\n" "$active_slug" "$SDDM_KDE_CONF"
    cat <<EOF
  Trailing /. copies contents in place so re-running updates instead of nesting.
  Heads-up: SDDM reads $SDDM_CONF_D with no extension filter (alphabetical,
  last wins). Don't leave .bak / .orig / editor-swap files in that directory —
  they silently override Current=. The script scans for these above.
EOF
    printf "\n"
fi

if (( HAS_SHADOW_MOVES == 1 )) && (( DID_SHADOW_MOVES == 0 )); then
    printf "\033[1;36mSDDM shadow files\033[0m — root steps not run; move out of conf.d (content preserved):\n"
    for f in "${SHADOW_FILES[@]}"; do
        printf "    sudo mv \"%s\" \"/etc/%s\"\n" "$f" "$(basename "$f")"
    done
    printf "\n"
fi

# Lock screen / Firefox / Chromium block — uses the ACTIVE variant's paths.
# Sibling variants follow the same pattern with their own dir names.
set_variant_names "$ACTIVE_VARIANT"
cat <<EOF
\033[1;36mLock screen\033[0m — optional, makes kscreenlocker reuse SDDM's wallpaper:
    SDDM_BG="\$(awk -F= '/^background=/{print \$2}' $SDDM_THEME_TARGET/theme.conf.user 2>/dev/null)"
    [[ -n "\$SDDM_BG" ]] && kwriteconfig6 --file kscreenlockerrc \\
        --group Greeter --group Wallpaper --group org.kde.image --group General \\
        --key Image "$SDDM_THEME_TARGET/\$SDDM_BG"
  The $NAME-styled lock UI is bundled as a Plasma/Shell package at
  $SHELL_DIR_NAME/ and activated by setting kscreenlockerrc [Greeter]/Theme =
  $SHELL_PKG_ID (done above). Test with: loginctl lock-session.

\033[1;36mFirefox theme\033[0m — load via about:debugging (active: $NAME):
    1. Visit about:debugging#/runtime/this-firefox
    2. "Load Temporary Add-on…" → pick $REPO_ROOT/$FF_DIR_NAME/manifest.json
  Sibling variants live at $REPO_ROOT/umber-{ash,slate,tide,storm}-firefox/.
  (Stable Firefox unloads unsigned extensions on restart. Sign on AMO or use
   Developer Edition with xpinstall.signatures.required=false for persistence.)

\033[1;36mChromium / Chrome theme\033[0m — load unpacked (active: $NAME):
    1. Visit chrome://extensions/
    2. Toggle "Developer mode"
    3. "Load unpacked" → pick $REPO_ROOT/$CR_DIR_NAME/
  Sibling variants live at $REPO_ROOT/umber-{ash,slate,tide,storm}-chromium/.

EOF

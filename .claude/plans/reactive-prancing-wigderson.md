# Umber Variants — Phased Rollout (revised)

## Resume here (2026-04-29)

Paused mid-Phase-1.5. Disk state is consistent and ready to pick up:

- `palette.toml` — **unchanged** (still original warm canonical)
- `palettes/umber-cooled.toml` — proposed cooled-canonical values, approved by user, awaiting promotion
- `palettes/{slate,tide,storm}.toml` — variant palettes, settled and approved
- `mockups/` — all four variant desktops + swatches + thumbs rendered for review
- `scripts/render_previews.py` — already updated this session: palette-aware, `_wallpaper_glow()` derives from palette, accepts `--palette` / `--title` / `--out-swatches` flags. **Not yet committed to git.**
- Nothing else touched on disk. No git commits made for any variant work.

**To resume**: read this plan, then execute Phase 1.5 step-by-step. After Phase 1.5 lands cleanly and is reviewed, ask whether to proceed into Phase 2 (variant consumer pipeline).

## Context

Goal: expand the Umber suite into a Nord/Catppuccin/Gruvbox-style family of variants. The pipeline is favorable — `palette.toml` is the single source of truth, `scripts/render_palette.py` produces all 8 consumer files from templates, `scripts/render_previews.py` produces previews directly from the palette. Tier semantics (Hearth/Glow/Mist/Spark) are project-name-independent (`palette.toml:13-17`), so a variant is a palette swap with constant tier semantics.

After two iterations of mockups, the family settled on a **cool-temperature ramp** rather than a brightness ramp:

| Variant | Hearth character | Glow desat | Mood |
|---|---|---|---|
| **Umber** (canonical) | warmly tinted neutral (R-B ≈ 5) | none | fireside |
| **Umber Slate** | neutral cool (R≈G≈B) | ~6% | overcast |
| **Umber Tide** | teal cool (G≈B>R) | ~12% | dusk |
| **Umber Storm** | slate-blue cool (B>G>R) | ~20% | night sea |

Mist + Spark are identical across all four — semantic accent register stays portable. Selection-pill regression (peach punching through cool grounds) was solved by per-variant Glow desaturation.

The user reviewed mockups for all four and approved the direction. The remaining iteration is on **canonical Umber itself**: current `palette.toml` was tuned for "warm earth, no neighbors" and reads as the loud warm one in family context. User selected option 1 (promote cooled Umber to canonical) to harmonize with the family.

## Phase 1 — Author palettes + mockups (COMPLETE)

Done. State on disk:
- `palettes/slate.toml`, `palettes/tide.toml`, `palettes/storm.toml` — variant palette files
- `palettes/umber-cooled.toml` — sandbox file with the proposed cooled-canonical values; about to be promoted
- `scripts/render_previews.py` — palette-aware (`--palette`, `--title`, `--out-swatches` flags); palette load refactored into `load_palette()`; wallpaper-glow band derived from palette via `_wallpaper_glow()` so cool variants get cool glow bands
- `mockups/{umber,slate,tide,storm,umber-cooled}-{desktop.jpg,thumb.png,swatches.png}` — review artifacts

## Phase 1.5 — Promote cooled Umber to canonical (THIS STEP)

User approved cooled Umber as the new canonical. Execute the promotion.

Concrete actions:

1. **Overwrite `palette.toml`** with the values from `palettes/umber-cooled.toml`:
   - hearth: `#24221F` `#2B2924` `#33302C` `#45413D` (was `#26221E` `#2D2823` `#363029` `#48413A`)
   - glow: `#A6988A` `#D1BB99` `#DECCAA` `#EFE5D4` (was `#A89986` `#D4BC91` `#E1CDA5` `#F0E5D0`)
   - mist + spark: unchanged
   - Update WCAG contrast notes in the header comments to reflect new ratios
2. **Regenerate all 8 templated consumer files**: `python3 scripts/render_palette.py render`. Touches:
   - `com.tyler.umber/contents/colors/Umber.colors`
   - `konsole/Umber.colorscheme`
   - `umber-vscode/themes/Umber-color-theme.json`
   - `umber-firefox/manifest.json`
   - `umber-chromium/manifest.json`
   - `umber-sddm/theme.conf`
   - `com.tyler.umber/contents/splash/Splash.qml`
   - `umber-shell/contents/lockscreen/LockScreenUi.qml`
3. **Verify sync**: `python3 scripts/render_palette.py check` passes
4. **Regenerate the committed package previews** (these ship inside the LookAndFeel package):
   - `python3 scripts/render_previews.py --out-full com.tyler.umber/contents/previews/fullscreenpreview.jpg --out-thumb com.tyler.umber/contents/previews/preview.png`
5. **Re-render the canonical Umber mockup** so `mockups/umber-*.{jpg,png}` reflects the new canonical
6. **Delete the sandbox file**: `rm palettes/umber-cooled.toml` (its values now live in `palette.toml`)
7. **STOP** — confirm canonical promotion landed cleanly. Phase 2 (variant consumer pipeline) and Phase 3 (distribution) remain deferred until separately approved.

No code changes in this phase — only data (palette values + regenerated outputs).

## Phase 2 (deferred) — Wire up the variant consumer pipeline

Only proceed after explicit Phase 1.5 sign-off. Touches every templated consumer.

1. **`scripts/render_palette.py`**
   - Add `--palette FILE` and `--variant NAME` args (variant defaults to a slug from the palette filename)
   - Parameterize `OUTPUTS` on the variant slug. Identifier transformations:
     - Plasma colorscheme `Name=Umber` → `Name=Umber Slate`, filename `Umber-Slate.colors`
     - LookAndFeel `Id: com.tyler.umber` → `com.tyler.umber-slate`, dir `com.tyler.umber-slate/`
     - Plasma Shell `Id: com.tyler.umber-shell` → `com.tyler.umber-slate-shell`, dir `umber-slate-shell/`
     - Konsole filename `Umber.colorscheme` → `Umber-Slate.colorscheme`, `Description=Umber Slate`
     - VSCode display name `Umber` → `Umber Slate`
     - Firefox `id: umber@tyler` → `umber-slate@tyler`, `name: Umber` → `Umber Slate`
     - Chromium `name: Umber` → `Umber Slate`
     - Cursor: `Umber-cursor` stays single across variants
   - Update `check` subcommand to validate canonical + every variant
2. **Per-variant directories**: side-by-side at top level (`com.tyler.umber-slate/`, `umber-slate-shell/`, …) — matches the existing layout convention
3. **Wallpaper**: `scripts/render_wallpaper.py` currently has hardcoded hearth/glow anchors; plumb `--palette` if shipping per-variant wallpapers, otherwise share the canonical wallpaper across variants and note this in the README

## Phase 3 (deferred) — Distribution

1. **`install.sh`** — `--variant NAME` flag (default: `umber`), substitute slug into all paths/identifiers, scan for all known variants in the existing-install detection block
2. **`README.md`** — variant comparison section with mockup screenshots, install snippet `./install.sh --variant slate`
3. **CI** — `render_palette.py check` iterates over `palette.toml` + every `palettes/*.toml`

## Critical files (Phase 1.5)

- `palette.toml` — overwrite with cooled-canonical values
- `palettes/umber-cooled.toml` — delete after promotion
- `scripts/render_palette.py` — used as-is via `render` and `check` subcommands; no edits
- `scripts/render_previews.py` — used as-is; no edits
- 8 consumer files (regenerated, listed in Phase 1.5 step 2)
- `com.tyler.umber/contents/previews/{preview.png,fullscreenpreview.jpg}` — regenerated
- `mockups/umber-*` — regenerated

## Verification (Phase 1.5)

- `python3 scripts/render_palette.py check` → "OK: all consumer files match templates."
- Diff `com.tyler.umber/contents/colors/Umber.colors` vs the prior version: only the hex values inside should change (no structural drift)
- `mockups/umber-desktop.jpg` re-renders to match `mockups/umber-cooled-desktop.jpg` (i.e. the cooled values are now what `palette.toml` produces)
- Visual: open `mockups/umber-desktop.jpg` alongside `mockups/{slate,tide,storm}-desktop.jpg` — Umber should still read as the warm anchor, just less aggressively warm than before

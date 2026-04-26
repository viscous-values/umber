# Hush

A quiet warm-on-charcoal theme suite for KDE Plasma 6 and friends. Originally adapted from [MarianArlt/sddm-sugar-dark](https://github.com/MarianArlt/sddm-sugar-dark), then muted for long-session comfort and built out into a full Nord-style palette.

![Palette preview](palette-preview.svg)

## Palette

16 colors in 4 tiers. Source of truth: [`palette-preview.svg`](palette-preview.svg).

| Tier | Purpose | Colors |
|------|---------|--------|
| **Hearth** | dark surfaces (deepest → elevated) | `#242424` `#2B2B2B` `#333333` `#444444` |
| **Glow**   | warm foregrounds (dim → bright)    | `#A89986` `#D4BC91` `#E1CDA5` `#E1E1E1` |
| **Mist**   | cool accents (counterweight)       | `#7AA8AC` `#88A6C5` `#A8BDD6` |
| **Spark**  | vivid syntax / status hues          | red `#E06C75` · orange `#D19A66` · amber `#E5C07B` · green `#98C379` · violet `#C586B0` |

Semantic conventions: negative = `spark.red`, neutral/warning = `spark.amber`, positive = `spark.green`, visited link = `spark.violet`.

## Components

| Path | What it is | Where it deploys |
|------|------------|------------------|
| `com.tyler.hush/` | Plasma 6 Look-and-Feel package + `Hush.colors` color scheme | `~/.local/share/plasma/look-and-feel/com.tyler.hush/` and `~/.local/share/color-schemes/Hush.colors` |
| `konsole/Hush.colorscheme` | Konsole 16-ANSI palette | `~/.local/share/konsole/Hush.colorscheme` (referenced by a Konsole profile) |
| `hush-sddm/` | SDDM greeter theme — Qt6 port of sddm-sugar-dark with solid charcoal background | `/usr/share/sddm/themes/hush/` (system-wide; needs sudo) |
| `hush-vscode/` | VSCode / code-oss color theme extension | `~/.vscode-oss/extensions/tyler.hush-1.0.0` (or `~/.vscode/extensions/` for Microsoft VSCode) |
| `palette-preview.svg` | Canonical visual reference for the 16-color spec | — |
| `preview.svg` | Small thumbnail for store listings | — |

## Install (per component)

### Plasma colorscheme + Look-and-Feel
```fish
cp -r com.tyler.hush ~/.local/share/plasma/look-and-feel/com.tyler.hush
cp com.tyler.hush/contents/colors/Hush.colors ~/.local/share/color-schemes/Hush.colors
kbuildsycoca6 --noincremental
cd /tmp; plasma-apply-lookandfeel -a com.tyler.hush
# Force-reapply the colorscheme (toggle through BreezeLight to make Plasma rewrite [WM] inline values)
plasma-apply-colorscheme BreezeLight
plasma-apply-colorscheme Hush
```

### Konsole
```fish
cp konsole/Hush.colorscheme ~/.local/share/konsole/Hush.colorscheme
# In Konsole: Settings → Edit Current Profile → Appearance → choose Hush
```

### SDDM (system-wide login)
```fish
# Test first (windowed):
sddm-greeter-qt6 --test-mode --theme $PWD/hush-sddm
# Install + activate:
sudo cp -r hush-sddm /usr/share/sddm/themes/hush
sudo sed -i 's/^Current=.*/Current=hush/' /etc/sddm.conf.d/kde_settings.conf
```

### VSCode / code-oss
```fish
ln -sfn $PWD/hush-vscode ~/.vscode-oss/extensions/tyler.hush-1.0.0
# (or ~/.vscode/extensions/ for Microsoft VSCode)
# Restart code-oss, then Ctrl+K Ctrl+T → Hush
```

## Known gotchas

- **`plasma-apply-colorscheme Hush` says "already set" and is a no-op** when the scheme is already current — Plasma keeps any stale inline `[WM]` values in `~/.config/kdeglobals`. Toggle through another scheme (e.g. `BreezeLight`) first to force the rewrite.
- **Don't run `plasma-apply-lookandfeel -a com.tyler.hush` from the project directory.** `kpackagetool6` resolves the source dir as a package path and the apply fails. Run from `/tmp` or anywhere outside the repo.
- **Existing Konsole tabs hold the old palette** — open a new tab to see scheme changes.
- The look-and-feel package's `metadata.json` needs `KPlugin.ServiceTypes: ["Plasma/LookAndFeel"]` *plus* top-level `X-Plasma-MainScript` and `X-Plasma-APIVersion`, otherwise `plasma-apply-lookandfeel` lists it but cannot apply it.

## Origin

The Sugar Dark SDDM theme by Marian Arlt (2018) inspired the palette. This suite started as a port and grew into its own thing as the palette was muted (`#FFDEAD` navajowhite → `#D4BC91`; pure white `#FFFFFF` → `#E1E1E1`; View bg lifted `#1F1F1F` → `#242424`) and then expanded with cool/vivid accents for syntax highlighting. The original Sugar Dark QML and assets in `hush-sddm/` retain their upstream GPL headers.

Licensed GPL-3.0-or-later.

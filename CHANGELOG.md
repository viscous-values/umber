# Changelog

All notable changes to this project follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- A web export: `umber-web/<variant>.css`, one file per variant that sets `color-scheme: dark` and a `--umber-*` custom property for every role under `[data-theme="<variant>"]` (`--umber-bg`, `--umber-fg-on-accent`, `--umber-syntax-keyword`, …), for web apps to vendor. The README's Web / CSS section gives the naming rule and the surface layering Umber's own themes use. The files are licensed GPL-3.0-or-later or MIT, and the test suite fails if a role in `roles.toml` is missing from them.
- A cursor per variant: `Umber-Ash-cursor`, `Umber-Slate-cursor`, `Umber-Tide-cursor` and `Umber-Storm-cursor` beside `Umber-cursor`. The body takes the variant's ground hue and the outline its text color, spinners and the help badge its signature accent, and the no-entry and copy badges its error and success colors. Each Global Theme selects its own cursor, and `install.sh` installs them all. `scripts/build-cursor.sh` rebuilds all five, and the test suite fails if a committed cursor no longer matches its palette.

### Removed
- `install.sh --migrate`. It cleaned up installs from the pre-release package namespaces (April–May 2026); nothing installed since needs it.

### Fixed
- The Umber cursor's body was still Nordic's slate blue-grey and its no-entry badge grey. The recolor treated Nord's slightly blue body as a blue badge, and mapped one red hue range to blue. It now maps each Nord color Nordic-cursors uses to a palette role.

### Repository
- History was rewritten on 2026-10-19, in two passes, to take the maintainer's personal name, former username and personal email address out of file contents, paths, commit messages, commit identities and images. The second pass changed only images: eleven preview and mockup images from April–October 2026 that showed the name or the address were replaced by versions showing placeholder text. Every commit ID changed; `docs/history-rewrite-2026-10-commit-map.txt` maps the original IDs to the current ones, and the tags `v1.0.0`, `v1.0.1` and `v2.0.0` point at the rewritten commits. Replace any clone made before 2026-10-20 with a fresh one.

## [2.0.0] — 2026-10-12

### Changed
- **Palette redesign.** Every variant now has its own character on a shared lightness ladder: Umber (fireside: raw umber, cream, burnt-sienna signature), Ash (charcoal and sanguine: graphite, paper white, red chalk, graphite-wash selection), Slate (pewter overcast, moss), Tide (sea glass, coral) and Storm (indigo night, lightning). Each has its own ground hue, text temperature, signature accent and syntax key; previously the five differed only in a near-black tint and shared every accent. Measured before/after in `PALETTE-REVISIT.md`.
- Focus rings, active tabs, primary buttons, progress and the splash use the variant's signature; selections are a light tint of it with hue-distinct link / visited / error / warning / success colors on top. Links are blue, visited links violet and info cyan. Input outlines reach 3:1; surface steps are wider; comments sit back from body text; terminal black is visible; red, green and amber stay apart under red-green color blindness.
- Templates name semantic roles from the new `roles.toml` instead of raw palette tiers, so a variant can remap any job (`link`, `focus_ring`, `syntax.type`, …). Chromium new-tab links and the Firefox url-field focus border now follow the link and focus roles like every other consumer.
- SDDM greeter previews and the store thumbnail (`preview.svg`) render from the palette instead of being hand-made; each variant gets its own SDDM preview. Browser-extension icons take their accent line from the signature. The 4K wallpapers, mockups and Plasma theme previews are regenerated from the new palettes, and each desktop preview shows its variant's concept.
- SDDM and the lock screen take text-on-accent and popup colors from new `AccentTextColor` / `PopupColor` theme keys instead of a hard-coded `#444`; typed text in the accent meets 4.5:1 in every variant.
- KDE LookAndFeel + Plasma Shell packages moved from the pre-release namespace to `io.github.viscous-values.<variant>`; `install.sh --migrate` cleaned up installs from it and from the original Hush name.
- VSCode extension moved to the `viscous-values` publisher (`viscous-values.umber`); bumped to `1.1.1`.

### Added
- `scripts/palette_audit.py`: WCAG contrast, OKLab role separation, color-blindness simulation and cross-variant identity checks; `--strict` gates palette changes.
- The Palette Lab (`scripts/render_lab.py` → `mockups/palette-lab.html`): every variant as Plasma, VSCode and Konsole mockups with value, hue, distance and audit views and an OKLCH tuner that exports TOML.
- `palettes/archive/classic/`: the pre-redesign palettes, kept resolvable, as the lab's Classic set and the audit's regression fixture. `v1.0.1` is tagged.
- A stdlib `unittest` suite under `tests/`.
- CONTRIBUTING.md (render pipeline, anti-patterns, commit conventions).
- SECURITY.md (private disclosure path).
- `.github/ISSUE_TEMPLATE/` (bug report skeleton).
- GitHub repo description, topics (kde, plasma6, theme, dark-theme, sddm, konsole, firefox-theme, vscode-theme).

### Removed
- `palette-preview.svg`, a hand-made swatch sheet of the old palette; the README now shows rendered variant thumbnails.

### Fixed
- Choosing Umber Ash, Slate, Tide or Storm in System Settings → Global Theme now switches the window colors too; before, every variant kept the previous scheme (usually Umber's brown). Plasma finds a Global Theme's color scheme by dropping separators from its name, so it looked for `UmberSlate.colors` and never matched `Umber-Slate.colors`. The Plasma color schemes are now `UmberAsh`, `UmberSlate`, `UmberTide` and `UmberStorm`. `install.sh` removes the old hyphenated files, and Konsole and VSCode names are unchanged.
- Plasma `[Colors:Selection]` link / negative / neutral / positive / visited text now meets WCAG AA (4.5:1) on every variant's selection highlight. The old hardcoded values measured 3.2–3.9:1 on Umber/Ash and 2.3–3.7:1 on Slate/Storm/Tide. They now live in per-variant `[accent]` keys (`highlight_link`, `highlight_negative`, `highlight_neutral`, `highlight_positive`, `highlight_visited`) instead of raw template literals, each a darkened version of the original hue.
- `palette.toml` contrast notes corrected: glow.0 on hearth.1 is 5.25:1 (was noted as ≈3.8:1) and spark.red on hearth.0 is 4.94:1 (was ≈4.5:1).

## [1.0.1] — 2026-05-04

### Added
- Per-variant `[accent]` palette tier for variant-aware UI accents (selection backgrounds, focused-field borders, active-tab lines). Cool variants (Slate, Storm, Tide) now get cool selection colors; warm variants (Umber, Ash) keep cream.
- Per-variant Firefox `.xpi` build pipeline (`scripts/build-firefox-xpi.sh`).
- Per-variant browser-extension icons rendered from the palette (`scripts/render_extension_icon.py`).
- Per-variant KRunner / app-launcher `.desktop` entries (`Apply Umber Tide`, etc.) writing to `~/.local/share/applications/`.
- `scripts/apply-variant.sh` wrapper script: `plasma-apply-lookandfeel` + the BreezeLight → real-scheme dance that defeats the `plasma-apply-colorscheme` "already set" short-circuit.
- `--all-variants` flag for `install.sh`.
- `--variant N` flag for `install.sh`.
- `install.sh` gathers its root steps into a single sudo prompt.

### Changed
- Firefox WebExtension gecko ids changed to `<variant>@viscous-values` to dodge an AMO duplicate-id reservation.
- VSCode template selection backgrounds, list/menu highlights, and active-state borders now use `accent.highlight` instead of `glow.1`.
- Firefox manifest highlight/border-focus/tab-line refs now use `accent.highlight`.
- Plasma color scheme `[Colors:Selection]/BackgroundNormal` now uses `accent.highlight`.
- README documents the AMO submission flow, the no-`userChrome.css` anti-pattern, and the variant family.

### Fixed
- Stripped `contents/colors/` from the installed LookAndFeel package. Plasma 6's `plasma-apply-lookandfeel` strips `[Colors:*]` from `kdeglobals` when an LnF package ships its own `colors/` dir and never repopulates — the System Settings KCM tile picker hit this constantly. Source-of-truth `.colors` files stay in the package source for the renderer.
- Identity sweep: removed pre-rebrand author email + handle from manifests, metadata, preview SVGs, and form-field mockups in `render_previews.py`.

## [1.0.0] — 2026-04-29

### Added
- Initial Umber theme suite — five-palette family: canonical Umber + Ash, Slate, Tide, Storm.
- Plasma 6 LookAndFeel package with bundled color scheme, splash, wallpaper.
- Plasma 6 Shell package — overrides only `contents/lockscreen/` to match the SDDM layout.
- Konsole 16-ANSI color schemes.
- VSCode color theme extension (single extension, all five variants).
- Firefox WebExtension theme (manifest v2, per-variant gecko id).
- Chromium / Chrome theme (manifest v3, per-variant).
- SDDM greeter theme — Qt6 port of MarianArlt's sddm-sugar-dark.
- Cursor theme — pixel-by-pixel recolor of Nordic-cursors via `scripts/recolor_nordic_inplace.py`.
- 4K wallpaper — procedural charcoal-to-peach gradient.
- `install.sh` — one-shot installer with `--migrate` flag for Hush → Umber.
- `scripts/render_palette.py` — single-source-of-truth template renderer.
- `scripts/render_previews.py` — generates per-variant mockup PNGs/JPGs.

### Origin
Adapted from [MarianArlt/sddm-sugar-dark](https://github.com/MarianArlt/sddm-sugar-dark), muted for long-session comfort and built out into a full Nord-style palette. Spark accent hexes adapted from Atom One Dark; Mist tier informed by Nord; Newaita-reborn (cbrnix) for icons; Nordic-cursors (EliverLara) as cursor source.

[Unreleased]: https://github.com/viscous-values/umber/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/viscous-values/umber/compare/v1.0.1...v2.0.0
[1.0.1]: https://github.com/viscous-values/umber/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/viscous-values/umber/releases/tag/v1.0.0

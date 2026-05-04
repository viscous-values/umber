# Contributing to Umber

Umber is a generated theme suite — the colors, manifests, metadata files, and QML for every consumer (Plasma, Konsole, VSCode, Firefox, Chromium, SDDM) are rendered from a single palette TOML through templates under `scripts/templates/`. **Do not hand-edit the rendered files** — your changes will be wiped the next time someone runs the renderer.

## The render pipeline

```
palettes/<variant>.toml            ← source of truth
scripts/templates/*.tmpl           ← per-consumer Jinja-style templates
scripts/render_palette.py          ← driver
```

To make a change that should propagate everywhere (e.g. a hex value in the palette, a new sidebar selector in VSCode):

1. Edit the right source file:
   - **Color value** → `palette.toml` (canonical) or `palettes/<variant>.toml`
   - **Per-consumer styling** → the matching `scripts/templates/*.tmpl`
2. Re-render every variant:
   ```
   python3 scripts/render_palette.py render
   for p in palettes/*.toml; do
       python3 scripts/render_palette.py render --palette "$p"
   done
   ```
3. Verify nothing drifted:
   ```
   python3 scripts/render_palette.py check
   ```
   This must exit clean before you commit. CI doesn't enforce it (no CI yet) — running it is on you.
4. Commit the source file change AND the regenerated consumer files together. Reviewers should be able to see what propagated downstream.

## Adding a new variant

1. Drop a TOML in `palettes/<name>.toml` with the same shape as `palettes/tide.toml`. Required tiers: `[hearth]` (4 keys 0–3), `[glow]` (4 keys 0–3), `[mist]` (4 keys 0–3), `[spark]` (red/orange/amber/green/violet), `[accent]` (highlight + highlight\_text).
2. `python3 scripts/render_palette.py render --palette palettes/<name>.toml` — generates every consumer file under `<slug>-firefox/`, `io.github.viscous-values.<slug>/`, etc.
3. Re-render previews via `scripts/render_previews.py`.
4. Wire the variant into `install.sh` — add the slug to `VARIANTS_TO_INSTALL` and the `case` validator.
5. README's Variants table should pick up the new variant.

## Adding a new consumer

If you want Umber to also style some new application (e.g., a tmux palette, an Alacritty theme):

1. Add a template under `scripts/templates/<name>.tmpl` using the placeholder syntax documented in `scripts/render_palette.py`'s docstring.
2. Add an entry in `outputs_for()` (in `render_palette.py`) mapping the template to its output path under each variant's directory.
3. Re-render and commit.

## Anti-patterns to avoid

- **Don't ship a `userChrome.css` overlay for the Firefox theme.** It overrode every WebExtension theme in earlier Hush-era builds and made all variants look identical. The Firefox theme must live entirely inside the WebExtension manifest. See [README §Firefox](README.md#firefox) for the full reasoning.

- **Don't rely on the System Settings → Global Theme tile picker for testing variant switches.** Plasma 6's `plasma-apply-lookandfeel` no-ops the color-scheme transition for third-party LnF packages. Use `./scripts/apply-variant.sh <variant>` (or the per-variant KRunner launchers `install.sh` writes) instead. See [README §Variants](README.md#variants).

- **Don't add new hardcoded `#3A3A3A`-style hex values to the templates.** Use a palette tier reference. The renderer's `--check` won't catch raw hex drift, but a code review will.

## Commit style

The repo uses [Conventional Commits](https://www.conventionalcommits.org/) loosely:

```
feat(palette): introduce mist.4 for hover-state borders
fix(install): strip contents/colors/ from installed LnF packages
chore(version): bump theme suite to 1.0.2
docs: clarify Plasma 6 KCM workaround
```

Scopes seen in `git log`: `palette`, `install`, `apply`, `firefox`, `vscode`, `lockscreen`, `palette`, `version`, `identity`, `amo`, `docs`, `chore`. Pick whichever fits.

## Local sanity-check before opening a PR

```
python3 scripts/render_palette.py check       # must pass
git grep -nE "com\.tyler|tyler\.umber"        # only the 3 hush-migration lines should appear
./scripts/build-firefox-xpi.sh                # smoke-test xpi packaging if you touched browser themes
```

If you touch `install.sh`, also run `./install.sh --migrate --no-sudo --yes` against a clean `~/.local/share/plasma/look-and-feel/` to verify your change doesn't break the migration path.

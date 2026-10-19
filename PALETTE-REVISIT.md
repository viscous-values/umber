# Palette revisit (closed)

Opened 2026-10-12, when the owner found that the variants and the roles inside each variant ran together, and that the WCAG AA selection fix (`2707ee0`) had made it worse. Closed the same month by the redesign on `feat/palette-rework`.

The pre-redesign palettes are kept in [`palettes/archive/classic/`](palettes/archive/classic) and the last release before the redesign is tagged `v1.0.1`.

## What was wrong

- **The variants differed only in what the eye ignores.** Backgrounds were 0.006–0.033 apart in OKLab ΔE (about 0.02 is the smallest difference people notice side by side), all at the same lightness. Body text was 0.004–0.018 apart. The accent and syntax colors were byte-identical in all five, and Slate and Storm shared one selection color. A near-black tint that fills the screen gets white-balanced away within a minute, so the only thing that changed between variants was the thing the eye discards.
- **Roles inside a variant blurred.** Surfaces stepped 1.08:1 and 1.12:1, types and variables shared a hue (ΔE 0.039), comments were as bright as body text, and canonical Umber's focus color was its body-text color.
- **The accessibility fixes pushed everything together.** WCAG only constrains lightness against the background, so each fix moved foregrounds into the same lightness band. Dark text on a light selection forced the on-selection colors dark, where yellow, orange and red all turn brown: selected links became the same color as selected warnings.
- **One pigment did unrelated jobs.** `mist.2` was the focus ring, primary button, info, function names, ANSI blue and markdown links at once; consumers disagreed about which pigment a job used.

## What changed

- **A semantic role layer.** [`roles.toml`](roles.toml) maps each job (`link`, `focus_ring`, `on_selection.neutral`, `syntax.type`, `ansi.black`, …) onto palette pigments, and every template names roles, never pigments. A variant can remap any role.
- **One value ladder, five characters.** All variants share surface lightness steps (.235 / .272 / .312 / .398, hover .465, control outline .555) and text steps (.705 / .835 / .895 / .950). Each variant gets its own ground hue, text temperature, signature accent and syntax key:
  - **Umber**, fireside: raw umber, cream, burnt-sienna signature
  - **Ash**, charcoal and sanguine: graphite, paper white, red-chalk signature, graphite-wash selection
  - **Slate**, pewter overcast: pewter, silver, moss signature
  - **Tide**, sea glass: deep teal, sea-foam, coral signature
  - **Storm**, indigo night: ultramarine, moonlit text, lightning signature
- **Selection is a light tint of the signature**, with its own set of hue-distinct colors for text drawn on it (navy, plum, maroon, olive, forest) instead of darkened browns.
- **Links are blue, visited links violet, info cyan**, so info text never looks clickable. Links are also underlined wherever the consumer allows: a 3:1 link-vs-text contrast is impossible on a dark theme while both stay readable, so the underline is the non-color cue.
- **Red, green and amber sit at different lightnesses** (error is always the darkest) so they stay apart under red-green color blindness, where hue alone fails.
- **The login and lock screens** draw typed text in the signature and text on it in a dark ink, both held to 4.5:1; their popups use the overlay surface instead of a hard-coded grey.

## Before and after

Measured by [`scripts/palette_audit.py`](scripts/palette_audit.py) on all five variants of each set. ΔE is OKLab distance; contrast is the WCAG 2 ratio.

| Measure | Classic (all five) | Redesign (all five) |
|---|---|---|
| Link vs body text, ΔE | 0.049–0.053 | 0.104–0.147 |
| Link vs visited, ΔE | 0.184–0.200 | 0.103–0.180 |
| Selected link vs selected visited, ΔE | 0.026–0.045 | 0.117 |
| Selected link vs selected warning, ΔE | 0.000 | 0.186 |
| Accent vs body text, ΔE | 0.000–0.140 | 0.107–0.220 |
| Plasma focus color vs active text, ΔE | 0.000 | 0.153–0.264 |
| Alternate selected row vs selection, ΔE | 0.039–0.189 | 0.034–0.036 |
| Window vs panel lightness step, ΔL | 0.026–0.029 | 0.036–0.039 |
| Panel vs raised lightness step, ΔL | 0.032–0.033 | 0.039–0.040 |
| Terminal black vs background, contrast | 1.08–1.10:1 | 1.99–2.03:1 |
| Terminal blue vs cyan, ΔE | 0.044 | 0.104–0.122 |
| Success vs warning under protanopia, ΔE | 0.019 | 0.061–0.121 |
| Inactive text on selection, contrast | 3.67–5.45:1 | 5.04–5.96:1 |
| Types vs variables, ΔE | 0.039–0.057 | 0.085–0.111 |
| Comments below body text, ΔL | 0.010–0.014 | 0.189–0.212 |
| Input outline on panels, contrast | 1.45:1 | 3.13–3.15:1 |
| Background between variants, ΔE | 0.006–0.033 | 0.025–0.087 |
| Variant identity, pairwise mean ΔE (background, panel, text, accent, selection) | 0.008–0.077 | 0.061–0.108 |
| Variant syntax key, pairwise mean ΔE | 0.000 | 0.044–0.071 |
| **Audit checks below threshold** | **116** | **0** |

The alternate-selected-row distance went *down* on purpose: it is supposed to be a slightly different tint of the selection, not a different color (classic Slate, Tide and Storm put an amber row next to a blue selection).

## Keeping it this way

- `python3 scripts/palette_audit.py --strict` must pass before a palette change is committed. It checks text contrast on the surfaces each text is drawn on, 3:1 for focus rings and input outlines, surface steps, role separation, colors on the selection, color-blindness simulation, terminal legibility, and cross-variant identity. Its thresholds live in one place and the lab uses the same checks.
- `python3 scripts/render_lab.py` builds the Palette Lab (`mockups/palette-lab.html`), which shows the Classic and current sets side by side as Plasma, VSCode and Konsole mockups, with grayscale and color-blindness views and an OKLCH tuner that exports TOML.
- Propose changes in `palettes/next/<variant>.toml`; the lab shows them as a Draft set, and `render_palette.py` refuses to render them over shipped files.

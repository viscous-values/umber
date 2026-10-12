# Palette revisit (open)

Noted 2026-10-12. The color scheme as a whole needs a hard look before more consumers are built on it. This isn't urgent and isn't scheduled. It's a marker so the next palette change starts here rather than with another spot fix.

Owner's read after reviewing the colors side by side: there isn't enough difference between roles that should look different (links vs visited links and similar), and the scheme overall isn't where it should be. The 2026-10-12 selection-contrast fix (`fix(palette): meet WCAG AA for selection text on every variant`) only made the existing choices readable; it didn't revisit them.

## What the numbers say (canonical Umber; the variants are similar)

Contrast is the WCAG 2.x ratio. "ΔE" is the distance in OKLab, where about 0.02 is the smallest difference most people notice side by side.

| Issue | Measurement | Where it comes from |
|---|---|---|
| Links barely differ from body text | link `glow.2` vs body `glow.1`: ΔE 0.050, only 1.18:1 between them. WCAG 1.4.1 suggests 3:1 when color alone marks a link | `ForegroundLink = glow.2` in every Plasma section |
| Selected links look like selected visited links | on the selection highlight: ΔE 0.045 (Umber), 0.027 (Slate/Storm), 0.026 (Tide); both are dark browns | `[accent] highlight_link` / `highlight_visited` |
| Selected links and warnings are the same color | `highlight_link == highlight_neutral` in every variant | inherited from the old shared literal `139,90,0` |
| Focus outline is just brighter text | `DecorationFocus`/`DecorationHover` = `glow.3`, the same color as active text; there is no distinct accent | `Umber.colors.tmpl`, all sections |
| Alternate selected rows clash on cool variants | `[Colors:Selection] BackgroundAlternate = spark.amber` sits next to a blue or teal highlight on Slate, Storm and Tide | `Umber.colors.tmpl` |
| Window vs panel surfaces nearly identical | `hearth.1` on `hearth.0`: 1.08:1 (ΔE 0.026); `hearth.2`: 1.21:1; `hearth.3`: 1.57:1 | `[hearth]` steps |
| Terminal "black" is invisible | Konsole `Color0 = hearth.1` on `hearth.0`: 1.08:1 | `Umber.colorscheme.tmpl` |
| Terminal blue and cyan are close | `mist.2` vs `mist.1`: ΔE 0.044 | `[mist]` |
| Green and yellow merge for protanopia | simulated ΔE 0.019 (red vs green holds up: 0.195 / 0.092) | `[spark]`, taken from One Dark |
| Inactive text on cool-variant selection | `hearth.3` on the blue/teal highlight: about 3.7:1. WCAG exempts inactive controls, but it reads weak | `ForegroundInactive = hearth.3` |
| Identity | the `[spark]` red/orange/amber/green are One Dark's values verbatim (see README credits) | `[spark]` |

## Questions to answer in the rework

- What does umber's accent want to be? It needs one color that is clearly not body text, for focus, links and selection.
- Should links and visited links differ in hue as well as lightness, and by how much (aim for ΔE > 0.10 and 3:1 against body text)?
- Should the `hearth` ramp have wider steps so windows, panels, raised controls and borders separate?
- Does umber keep One Dark's accents or get its own, tuned to the warm field?
- Should each variant's selection colors (highlight, alternate row, text on highlight) be designed as a set, rather than one amber alternate for everyone?

## How to approach it

Change `palette.toml` and `palettes/*.toml` first, then re-render (see CONTRIBUTING.md) and re-measure everything in the table above. Keep WCAG AA (4.5:1 for text, 3:1 for focus outlines) as the floor for every text-on-background pair the templates actually produce.

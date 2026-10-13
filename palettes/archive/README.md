# Archived palettes

`classic/` holds the five palettes exactly as they stood before the 2026-10
redesign (v1.0.1 plus the unreleased WCAG AA selection-text fix), each with a
`[role]` block appended that restores the role mapping it shipped with. Two
sites can't be restored: Chromium's new-tab links and Firefox's url-field focus
border used the accent in v1.0.1 and now follow the link and focus roles. They are
kept as a record, as the Palette Lab's "Classic" comparison set, and as the
audit's regression fixture: `tests/` checks that `palette_audit.py` still
flags every problem `PALETTE-REVISIT.md` recorded against them.

Nothing renders from this directory. `render_palette.py render` refuses
palettes under `palettes/<subdir>/`, because each file shares its name with a
shipped variant and would overwrite that variant's files.

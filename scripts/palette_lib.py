"""Load an Umber palette TOML and resolve its semantic role layer.

A palette file holds the pigment tiers (hearth / glow / mist / spark /
accent / ansi). roles.toml at the repo root maps semantic jobs (bg, link,
focus_ring, syntax.keyword, ...) onto those tiers. A variant may override
any role in its own [role] table. Role values are either a literal
"#RRGGBB" or a reference to another key ("mist.2", "role.interactive").

    pal = prepare(Path("palettes/slate.toml"))
    pal["role"]["link"]            -> "#94B3E1"
    resolve(pal, "role.syntax.type") -> "#78CFCC"

After prepare(), every role leaf is plain hex, so readers that walk the
dict directly (icon renderer, previews, audit) never see references.
"""

import copy
import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PALETTE_FILE = REPO / "palette.toml"
PALETTES_DIR = REPO / "palettes"
ROLES_FILE = REPO / "roles.toml"

HEX_RE = re.compile(r"#[0-9A-F]{6}")
SLUG_RE = re.compile(r"[a-z][a-z0-9-]*")


def variant_slug(path):
    """Variant slug for a palette file: palette.toml is canonical "umber"; others use the stem.

    Slugs become package ids, directory names and page markup, so they are
    limited to lowercase letters, digits and hyphens.
    """
    stem = Path(path).stem
    slug = "umber" if stem == "palette" else stem
    if not SLUG_RE.fullmatch(slug):
        raise ValueError(f"{path}: palette filenames must be lowercase letters, digits and hyphens")
    return slug


def is_unshipped(path):
    """True for palettes in a subdirectory of palettes/ (drafts in next/, archive/...).

    Those files share their names with shipped variants, so rendering one would
    overwrite that variant's shipped outputs.
    """
    resolved = Path(path).resolve()
    shipped_dir = PALETTES_DIR.resolve()
    return resolved.is_relative_to(shipped_dir) and resolved.parent != shipped_dir


def load_toml(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def deep_merge(defaults, overrides, path="role"):
    """Return defaults with overrides applied. Override keys must exist in defaults."""
    merged = copy.deepcopy(defaults)
    for key, val in overrides.items():
        where = f"{path}.{key}"
        if key not in merged:
            raise ValueError(f"unknown role override: {where}")
        if isinstance(merged[key], dict) != isinstance(val, dict):
            raise ValueError(f"role override {where}: table/value mismatch with roles.toml")
        merged[key] = deep_merge(merged[key], val, where) if isinstance(val, dict) else val
    return merged


def resolve(pal, key, chain=()):
    """Resolve `key` to a #RRGGBB hex, following references. var.* returns verbatim."""
    if key in chain:
        raise ValueError("role cycle: " + " -> ".join(chain + (key,)))
    val = pal
    try:
        for part in key.split("."):
            val = val[part]
    except (KeyError, TypeError):
        raise ValueError("unresolvable key: " + " -> ".join(chain + (key,))) from None
    if key.startswith("var."):
        return val
    if not isinstance(val, str):
        raise ValueError(f"{key} is a table, not a color")
    if val.startswith("#"):
        if not HEX_RE.fullmatch(val):
            raise ValueError(f"{key} = {val!r}: colors must be uppercase #RRGGBB")
        return val
    return resolve(pal, val, chain + (key,))


def _resolve_tree(pal, table, prefix):
    for key, val in table.items():
        full = f"{prefix}.{key}"
        if isinstance(val, dict):
            _resolve_tree(pal, val, full)
        else:
            table[key] = resolve(pal, full)


def prepare(palette_path, roles_path=ROLES_FILE):
    """Load a palette, merge roles.toml defaults with its [role] overrides, resolve to hex."""
    pal = load_toml(palette_path)
    defaults = load_toml(roles_path).get("role", {})
    pal["role"] = deep_merge(defaults, pal.get("role", {}))
    _resolve_tree(pal, pal["role"], "role")
    return pal

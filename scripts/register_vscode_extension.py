#!/usr/bin/env python3
"""Register the Umber VSCode extension in <extensions-dir>/extensions.json.

VSCode does not load a symlinked extension until extensions.json lists it, so
install.sh links umber-vscode/ as viscous-values.umber-<version> and then runs
this. An existing Umber entry (say, from an older version) is replaced rather
than kept, so a version bump moves the registration along with the link. A
malformed extensions.json is left untouched: rewriting it would drop every
other extension the user has installed.

    python3 scripts/register_vscode_extension.py --extensions-dir ~/.vscode/extensions --version 2.0.0
"""

import argparse
import json
import sys
import time
from pathlib import Path

EXT_ID = "viscous-values.umber"


def register(extensions_dir, version):
    extensions_dir = Path(extensions_dir)
    path = extensions_dir / "extensions.json"
    data = []
    if path.exists() and path.read_text().strip():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            sys.exit(f"{path} is not valid JSON ({e}); left it unchanged. Fix or remove it, then re-run.")
    folder = f"{EXT_ID}-{version}"
    data = [e for e in data if e.get("identifier", {}).get("id") != EXT_ID]
    data.append({
        "identifier": {"id": EXT_ID},
        "version": version,
        "location": {"$mid": 1, "path": str(extensions_dir / folder), "scheme": "file"},
        "relativeLocation": folder,
        "metadata": {"installedTimestamp": int(time.time() * 1000), "pinned": True, "source": "vsix"},
    })
    extensions_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return folder


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--extensions-dir", type=Path, required=True)
    ap.add_argument("--version", required=True)
    args = ap.parse_args(argv)
    folder = register(args.extensions_dir, args.version)
    print(f"    .. registered {folder} in {args.extensions_dir / 'extensions.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

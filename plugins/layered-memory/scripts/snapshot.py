"""Pre-write snapshots + op manifests (spec §11). Stdlib only."""
import json
from pathlib import Path

import paths
import locking


def snapshot_theme(mem: Path, slug: str, op_id: str, ts: str):
    """Copy the current theme file (if any) to history/<slug>/<ts>__<op-id>.md.
    Returns the snapshot Path, or None if the theme doesn't exist yet."""
    mem = Path(mem)
    theme = paths.themes_dir(mem) / f"{slug}.md"
    if not theme.exists():
        return None
    dest_dir = paths.history_dir(mem) / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_ts = ts.replace(":", "-")
    dest = dest_dir / f"{safe_ts}__{op_id}.md"
    locking.atomic_write(dest, theme.read_text())
    return dest


def write_manifest(base_mem: Path, op_id: str, entries: list) -> Path:
    """Write the global op manifest history/_ops/<op-id>.json (base scope)."""
    base_mem = Path(base_mem)
    ops = paths.ops_dir(base_mem)
    ops.mkdir(parents=True, exist_ok=True)
    path = ops / f"{op_id}.json"
    locking.atomic_write(path, json.dumps(
        {"op_id": op_id, "themes": entries}, indent=2))
    return path

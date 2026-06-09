#!/usr/bin/env python3
"""Guarded cleanup of layered-memory DATA dirs (spec §14). Stdlib only.

DRY-RUN by default — lists what it WOULD delete. Pass --yes to actually delete.
Only ever deletes directories that look like layered-memory memory dirs.

Usage:
    uninstall_clean.py                 # dry-run: show base (+ any --dir) targets
    uninstall_clean.py --dir <path>    # also consider a per-repo memory dir
    uninstall_clean.py --yes [...]     # actually delete

Run this BEFORE `/plugin uninstall` — this command disappears with the plugin.
"""
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

# A dir is "ours" only if it carries one of these layered-memory artifacts.
_MARKERS = ("index.md", "themes", "history", "processed.log", "complaints.log")


def looks_like_memory_dir(p: Path) -> bool:
    p = Path(p)
    return p.is_dir() and any((p / m).exists() for m in _MARKERS)


def discover_targets(extra_dirs) -> list:
    targets = []
    base = paths.base_memory_dir()
    if base.exists():
        targets.append(base)
    for d in extra_dirs:
        p = Path(d).expanduser()
        if p.exists() and p not in targets:
            targets.append(p)
    return targets


def clean(targets, do_delete: bool):
    """Return (removed, skipped). `removed` = dirs deleted (or would-delete in dry-run);
    `skipped` = [(path, reason)] for anything that didn't look like ours."""
    removed, skipped = [], []
    for p in targets:
        p = Path(p)
        if not looks_like_memory_dir(p):
            skipped.append((p, "not a layered-memory dir (no index.md/themes/history)"))
            continue
        if do_delete:
            shutil.rmtree(p)
        removed.append(p)
    return removed, skipped


def main(argv) -> int:
    do_delete = "--yes" in argv
    extra = []
    it = iter([a for a in argv if a != "--yes"])
    for a in it:
        if a == "--dir":
            extra.append(next(it, ""))
        elif a and not a.startswith("-"):
            extra.append(a)
    extra = [e for e in extra if e]

    targets = discover_targets(extra)
    if not targets:
        print("[memory] nothing to clean — no memory directories found.")
        return 0

    removed, skipped = clean(targets, do_delete=do_delete)
    if do_delete:
        for p in removed:
            print(f"[memory] deleted: {p}")
    else:
        print("[memory] DRY RUN — would delete (re-run with --yes to confirm):")
        for p in removed:
            print(f"  - {p}")
    for p, reason in skipped:
        print(f"[memory] skipped: {p}  ({reason})")
    if not do_delete and removed:
        print("\nRun BEFORE `/plugin uninstall` — this command is gone once the plugin is removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

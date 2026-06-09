#!/usr/bin/env python3
"""SessionStart hook: inject the Tier-0 memory index as reference context.
Read-only, no model call. Stdlib only."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import paths      # noqa: E402
import inject     # noqa: E402
import model      # noqa: E402


def _read(p: Path) -> str:
    try:
        return p.read_text()
    except FileNotFoundError:
        return ""


def main():
    # Recursion guard: never inject during our own internal `claude -p` calls.
    if model.is_internal_call():
        return
    try:
        sys.stdin.read()           # drain stdin so we don't block; contents unused
    except Exception:
        pass

    base_idx = _read(paths.index_path(paths.base_memory_dir()))
    proj_idx = _read(paths.index_path(Path.cwd() / ".claude" / "memory"))
    ctx = inject.build_index_context(base_idx, proj_idx)
    if not ctx:
        return                     # nothing stored yet → inject nothing

    out = {"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx,
    }}
    print(json.dumps(out))


if __name__ == "__main__":
    main()

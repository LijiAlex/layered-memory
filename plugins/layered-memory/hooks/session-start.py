#!/usr/bin/env python3
"""SessionStart hook: inject the Tier-0 memory index as reference context.
Read-only, no model call. Stdlib only."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import paths      # noqa: E402
import inject     # noqa: E402
import formats    # noqa: E402
import model      # noqa: E402
import config     # noqa: E402


def _theme_updated(mem: Path, slug: str) -> str:
    """Read a theme's `updated` timestamp (for recency ranking). '' if missing."""
    tf = paths.themes_dir(mem) / f"{slug}.md"
    try:
        return formats.parse_theme(tf.read_text()).get("updated", "")
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

    base_mem = paths.base_memory_dir()
    cfg = config.load_config(base_mem)

    idx_path = paths.index_path(base_mem)
    if not idx_path.exists():
        return                     # nothing stored yet → inject nothing
    entries = formats.parse_index(idx_path.read_text())   # full index (base; user works from base)
    for e in entries:
        e["updated"] = _theme_updated(base_mem, e["slug"])
    selected = inject.select_recent(entries, cfg.get("index_inject_max", 20))
    ctx = inject.build_index_context(selected, total=len(entries))
    if not ctx:
        return
    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ctx,
        },
        # user-terminal only (not model context): report the index's context cost
        "systemMessage": inject.index_cost_message(ctx, cfg["context_window"]),
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()

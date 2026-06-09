---
description: Delete layered-memory's stored data dirs (~/.claude/memory and any per-repo dirs). Dry-run by default; needs --yes to actually delete. Run BEFORE /plugin uninstall.
argument-hint: "[--dir <repo-memory-path>] [--yes]"
---

Clean up the **data** layered-memory wrote to disk. Uninstalling the plugin removes its
code but leaves the memory files behind; this wipes them.

**Important:** run this BEFORE `/plugin uninstall` — the command disappears with the plugin.

First show the user what WOULD be deleted (dry-run, default):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/uninstall_clean.py" $ARGUMENTS
```

Report the listed directories to the user and **ask for explicit confirmation**. Only the
base dir `~/.claude/memory` is auto-discovered; per-repo dirs must be added with
`--dir <repo>/.claude/memory`. The script refuses to delete anything that doesn't look like
a layered-memory directory (must contain `index.md`/`themes/`/`history/`).

After the user confirms, re-run with `--yes` to actually delete:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/uninstall_clean.py" --yes $ARGUMENTS
```

This is irreversible (no snapshot — it is the deliberate wipe). A repo deleted before
cleanup leaves its `<repo>/.claude/memory/` orphaned; pass its path with `--dir` to remove it.

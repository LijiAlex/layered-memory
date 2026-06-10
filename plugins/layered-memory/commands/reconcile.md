---
description: Consolidate stored memory — merge overlapping/duplicate themes into single coherent themes and rebuild the index. Runs automatically after each build; use this to run it on demand.
---

Run Engine B (global consolidation) over all stored themes. It reads every theme summary
under `~/.claude/memory/themes/`, merges overlapping/duplicate themes into one (preserving
distinct facts), rewrites the themes + `index.md`, and deletes themes that were merged away.
Every theme is snapshotted first (undoable).

Execute:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reconcile.py"
```

Report how many themes there were before vs after and how many were merged. This is the
"clean up fragmentation" pass — safe to run anytime; it only merges/dedups (never splits).

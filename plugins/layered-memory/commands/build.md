---
description: Build/refresh layered memory by distilling your past session transcripts into themes.
---

Run the layered-memory build over all past session transcripts. This reads your
Claude Code transcripts, distils them into per-theme summaries, and writes/updates
`~/.claude/memory/themes/*.md` and `~/.claude/memory/index.md`. Existing summaries are
reconciled (not overwritten blindly); a snapshot is taken before each write.

Execute:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build.py"
```

After it runs, report the number of themes written and where the index lives. If the
user wants to inspect a theme, the files are plain markdown under `~/.claude/memory/themes/`.

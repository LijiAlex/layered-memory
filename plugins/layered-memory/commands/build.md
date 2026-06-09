---
description: Build/refresh layered memory by distilling past session transcripts into themes. Optional --limit N caps how many new transcripts are ingested this run.
argument-hint: "[--limit N]"
---

Run the layered-memory build over your past session transcripts. This reads your
Claude Code transcripts (newest first, skipping ones already ingested), distils them
into per-theme summaries, and writes/updates `~/.claude/memory/themes/*.md` and
`~/.claude/memory/index.md`. Existing summaries are reconciled (not overwritten blindly);
a snapshot is taken before each write.

**Each transcript = one model call (~$0.05).** Use `--limit N` to cap cost on the first
run, e.g. `/memory:build --limit 3` ingests only the 3 newest new transcripts. Re-running
continues where it left off (a `processed.log` ledger skips done sessions).

Execute (forwards any arguments the user passed, e.g. `--limit 3`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build.py" $ARGUMENTS
```

After it runs, report the themes written, the transcript count, any errors, and where the
index lives. Theme files are plain markdown under `~/.claude/memory/themes/` for inspection.

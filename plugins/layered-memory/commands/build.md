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

**[MUST] Run it in the FOREGROUND so the user sees progress.** The script streams live
`[memory] …` milestone lines (scanning, per-transcript reading/distilling, theme counts,
reconcile). Therefore:
- Do **NOT** run it in the background.
- Do **NOT** pipe it to `tail`, `head`, or anything that withholds output until completion.
- Run it as-is and surface its streaming stdout to the user as it appears.

Note for the user: builds take ~10–40s per transcript (one model call each) plus a final
auto-reconcile call, so output appears gradually. For the most direct live view the user can
also run the command themselves with a leading `!` in the prompt, or in a real terminal.

After it exits, report the themes written, the transcript count, any errors, and where the
index lives. Theme files are plain markdown under `~/.claude/memory/themes/` for inspection.

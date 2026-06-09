# layered-memory

File-based, progressive-disclosure memory for Claude Code. Plain markdown on disk — no database, no vector store, no service.

See the design spec for architecture. Plan 1 (this milestone) ships `/memory:build`.

## Building memory

`/memory:build` ingests your past transcripts incrementally — newest first, one model
call per session, skipping sessions already recorded in `~/.claude/memory/processed.log`.
Re-running only ingests new sessions. To force a full rebuild, delete `processed.log`.
Caps live in `~/.claude/memory/config.json` (`build_max_transcripts`,
`build_transcript_char_cap`).

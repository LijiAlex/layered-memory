# layered-memory

A **file-based, progressive-disclosure memory layer for Claude Code** — distills your past sessions into per-theme markdown summaries and surfaces the relevant one automatically in future sessions. Plain markdown on disk: **no database, no vector store, no background service.** Auditable, git-versionable, and removable.

---

## What it does

- **Builds memory** from your past Claude Code session transcripts → per-theme summaries under `~/.claude/memory/themes/` + a tiny `index.md`.
- **Surfaces memory automatically** — a SessionStart hook injects the index into every new session; when your question matches a theme, the assistant loads that theme and answers from it.
- **Consolidates** — overlapping/duplicate themes are merged into coherent ones.
- Everything is reference-framed and **read-only at load time** (memory never overrides you or your guidelines).

---

## Install

```text
/plugin marketplace add LijiAlex/layered-memory
/plugin install layered-memory@layered-memory
```

Then seed memory from your history (start small to control cost — each transcript ≈ one model call):

```text
/layered-memory:build --limit 10
```

Start a new session and ask about something you've worked on — the matching theme surfaces automatically.

> Note: commands are namespaced by plugin → `/layered-memory:build`, etc.

---

## Commands

| Command | What it does |
|---------|--------------|
| `/layered-memory:build [--limit N]` | Distil transcripts → themes + index. Incremental (skips already-ingested), oldest-first, capped. `--limit N` caps transcripts this run. Auto-runs reconcile at the end. |
| `/layered-memory:reconcile` | Merge overlapping/duplicate themes into one; rebuild the index. (Also runs automatically after each build.) |
| `/layered-memory:reload [theme]` | Re-load memory for the current topic, or a named theme; used to correct a wrong recall. |
| `/layered-memory:uninstall-clean [--dir <path>] [--yes]` | Delete the memory data dirs. **Dry-run by default**; `--yes` to delete. Run **before** `/plugin uninstall`. |

### Config (`~/.claude/memory/config.json`, all optional)

| Key | Default | Meaning |
|-----|---------|---------|
| `build_model` | `claude-haiku-4-5` | model used for build/reconcile |
| `build_max_transcripts` | `50` | max new transcripts per build run |
| `build_transcript_char_cap` | `40000` | per-transcript size cap (head+tail sampled) |
| `build_call_timeout_sec` | `180` | per-transcript distill timeout |
| `reconcile_call_timeout_sec` | `300` | consolidation-call timeout |
| `max_call_retries` | `1` | on timeout, retry with **doubled** timeout this many times |
| `context_window` | `null` | set (e.g. `1000000`) to also show index size as a % of context |

---

## How it works

**Storage** (`~/.claude/memory/`): `index.md` (tiny table of contents), `themes/<slug>.md` (the distilled summaries), `history/` (pre-write snapshots + op manifests for undo), `processed.log` (ledger of ingested sessions).

**Write path** (`/layered-memory:build`):
1. Discover transcripts (oldest-first; skips ones already in `processed.log` unless they've grown).
2. For each, one model call (Engine A) distils it into themes, **reconciling into existing themes** (add / revise / prune — not append). Long transcripts are head+tail sampled. Timeouts escalate (retry at 2×).
3. **Engine B (reconcile)** then merges overlapping themes globally into a coherent set and rebuilds the index.
4. Every write is snapshotted first (undoable on disk).

**Read path** (automatic):
1. A **SessionStart hook** injects `index.md` into context as reference (and prints its token cost).
2. When your prompt matches a theme, the **load-memory skill** reads that theme file and answers from it — proactively, framed as untrusted reference.

**Incremental + resumable:** re-running build only ingests new/grown sessions; a timed-out transcript is skipped and retried next run; a live session is re-ingested once it grows.

---

## Safety

- Memory is **untrusted data, never instructions** — never used for auth decisions or fed to eval/shell/SQL/HTML.
- All writes are **snapshotted** before overwrite.
- Uninstalling the plugin removes the commands/skill/hook but **leaves your memory data** on disk — wipe it with `/layered-memory:uninstall-clean` (dry-run → `--yes`).

---

## What's pending

- **Live auto-capture** (capture as you work + write-up at session end, so no manual `/build`) — the biggest missing piece.
- **`/layered-memory:undo`** — undo manifests are written, but no replay command yet.
- **Complaints reindex** — wrong-recalls are logged but not yet consumed to retune index keywords.
- **Engine B split/prune** — currently merge-only (no theme splitting or stale-line pruning).
- **Nightly reconcile**, **per-project scope** builds, **`--reset`**, **ledger compaction**.
- **Capture quality**: tool output and `sources:` are not yet recorded.
- **Packaging**: privacy `<private>` exclusion, Windows/Linux support.

---

## Development

```bash
python3 -m pytest          # test suite (stdlib runtime; pytest dev-only)
```

macOS-first. Plugin runtime is pure Python stdlib; the model call goes through the `claude` CLI. Local plugin updates are version-pinned — bump `version` in `plugin.json` + `marketplace.json` (and reinstall) for changes to take effect.

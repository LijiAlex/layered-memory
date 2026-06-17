# layered-memory

> Persistent memory for Claude Code — as plain markdown files you can read, diff, and delete.

[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757)](https://docs.claude.com/en/docs/claude-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-stdlib-3776ab.svg)](#development)
[![No database](https://img.shields.io/badge/storage-markdown-informational.svg)](#how-it-works)

**Persistent memory for Claude Code.** layered-memory is a **Claude Code plugin** that gives Claude long-term memory across sessions — it distills your past Claude Code sessions into per-theme markdown summaries and automatically surfaces the relevant context in new sessions, so you stop re-explaining your project every time. Plain markdown on disk: **no database, no vector store, no background service.** Auditable, git-versionable, and removable.

```text
~/.claude/memory/
├── index.md                 # tiny table of contents, injected every session
└── themes/
    ├── govfoun-438-timeout.md
    ├── atlas-bulk-purge.md
    └── layered-memory-plugin.md
```

---

## Why file-based memory instead of a vector database?

| | layered-memory | Vector-DB memory |
|---|---|---|
| **Storage** | plain markdown on disk | embeddings in a DB/service |
| **Inspect / edit** | open the file, `git diff` | opaque vectors |
| **Infra** | none | DB or vector store to run |
| **Retrieval** | keyword theme-match, deterministic | similarity search, fuzzy |
| **Remove** | delete the files | DB migration |
| **Trust model** | loaded as untrusted reference, never instructions | varies |

Built for the case where you want memory you can **audit and own**, not a black box.

---

## vs Claude Code's built-in Auto Memory

Claude Code already ships **Auto Memory** — and it's good. It's plain markdown, auto-loads a `MEMORY.md` index (~200 lines/25KB) plus topic files on demand, and captures automatically as you work. layered-memory is **complementary, not a replacement** — it overlaps deliberately and adds three things Auto Memory doesn't do.

| | Claude Auto Memory (built-in) | layered-memory |
|---|---|---|
| **Storage** | plain markdown, per **git repo** (`~/.claude/projects/<repo>/memory/`) | plain markdown, **cross-repo `base` tier** + per-project |
| **Scope** | per-repo only | spans **all repos** (the base tier) |
| **Source** | accumulates **going forward** from when enabled | **distilled from your existing transcript history** (backfills what you already have) |
| **Capture** | **automatic, live** | manual `build` today (live auto-capture is on the roadmap) |
| **Loading** | `MEMORY.md` index + topic files on demand | `index.md` + theme files on demand *(same pattern)* |
| **Consolidation** | accumulates | **actively merges overlapping themes** (Engine B) |
| **Inspect / edit** | plain files, `/memory` | plain files + snapshots/undo |

**What's genuinely different:** (1) a **cross-repo base tier** Auto Memory has no equivalent for; (2) it **mines your existing session history** rather than only accumulating forward; (3) **active consolidation** of overlapping themes. Auto Memory wins today on **live auto-capture** — layered-memory still needs a manual `build` (changing soon).

Use both: let Auto Memory handle the current repo live, and use layered-memory for a curated, cross-project, themed knowledge base distilled from everything you've already done.

---

## What layered-memory does for Claude Code

- **Builds memory** from your past Claude Code session transcripts → per-theme summaries under `~/.claude/memory/themes/` + a tiny `index.md`.
- **Surfaces memory automatically** — a SessionStart hook injects the index into every new session; when your question matches a theme, the assistant loads that theme and answers from it.
- **Consolidates** — overlapping/duplicate themes are merged into coherent ones.
- Everything is reference-framed and **read-only at load time** (memory never overrides you or your guidelines).

---

## Install the Claude Code memory plugin

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
| `/layered-memory:build [--limit N]` | Ingest transcripts → **one note per feature**. Each session is matched to an existing feature (or filed as new) and folded in. Incremental (skips already-ingested), oldest-first, capped. `--limit N` caps transcripts this run. |
| `/layered-memory:reconcile` | Consolidate notes — merge duplicate features into one, rebuild the index. Cluster-targeted (no all-notes call), with an LLM "same feature?" judge for look-alikes. |
| `/layered-memory:reload [theme]` | Re-load memory for the current topic, or a named note; used to correct a wrong recall. |
| `/layered-memory:uninstall-clean [--dir <path>] [--yes]` | Delete the memory data dirs. **Dry-run by default**; `--yes` to delete. Run **before** `/plugin uninstall`. |

### Config (`~/.claude/memory/config.json`, all optional)

| Key | Default | Meaning |
|-----|---------|---------|
| `build_model` | `claude-haiku-4-5` | model used for build + reconcile |
| `build_max_transcripts` | `50` | max new transcripts per build run |
| `build_transcript_char_cap` | `120000` | per-chunk size cap (big sessions are chunked on seams) |
| `build_call_timeout_sec` | `180` | per-episode extract timeout |
| `reconcile_call_timeout_sec` | `300` | per-cluster merge timeout |
| `max_call_retries` | `1` | on timeout, retry with **doubled** timeout this many times |
| `index_inject_max` | `20` | how many recent notes the SessionStart hook injects |
| `reconcile_kw_jaccard` | `0.4` | keyword-overlap ratio to auto-cluster two notes |
| `reconcile_slug_min_shared` | `2` | shared slug tokens to LLM-judge a pair for merge |
| `reconcile_max_judge_calls` | `20` | cap on "same feature?" judge calls per reconcile |
| `context_window` | `null` | set (e.g. `1000000`) to show index size as a % of context |

---

## How it works

**One note = one feature, spanning repos.** A feature's value is the cross-repo wiring — which repo does what and how they connect — so sessions about the same feature are folded into a *single* note, never sharded per-repo.

**Storage** (`~/.claude/memory/`): `index.md` (slim routing index), `themes/<slug>.md` (one feature note each: cross-repo map + key facts + open threads + terse episodes log), `match-keys.json` (slim match metadata, never injected), `history/` (snapshots + op manifests for undo), `processed.log` (mtime ledger of ingested sessions).

**Key idea:** no model call ever scales with total memory size. Build is bounded per-transcript; reconcile is bounded per-cluster. Matching is a 3-tier hybrid (structured → keyword → LLM judge), no vector DB.

**Write path** (`/layered-memory:build`) — per transcript, oldest-first:
1. **Footprint** (deterministic, no model): parse tool blocks → repos, files written/read, skills, commands, symbols, tickets.
2. **Compress** the session (keep tool *actions*, drop bulk dumps, dedupe reads); skip if **trivial** (no call).
3. **Extract a type-aware episode** (debugging / exploration / new-feature) — one model call; huge sessions are chunked on natural seams and summarized sequentially with a pinned ticket+goal block (per-chunk resilient).
4. **Match** the footprint to an existing feature (ticket › cross-repo file overlap › symbols/skills › keywords; bounded LLM tiebreak when unsure). Match → fold the episode into that note (passing only that note); no match → new note. Reconcile-not-append.
5. Snapshot before every write; mtime ledger makes it incremental + resumable (grown/live sessions re-ingest; a failed transcript retries next run; timeouts retry at 2×).

**Consolidate** (`/layered-memory:reconcile`): find duplicate **clusters** (keyword overlap, plus an LLM "same feature?" judge for slug-similar look-alikes whose keywords diverge), merge each small cluster in its own bounded call, and safe-delete only the slugs deliberately merged (abort a cluster on a bad result — never delete-by-absence).

**Read path** (automatic): a **SessionStart hook** injects a slim **recent-N** index (slug + one-liner) — full index stays on disk; when your prompt matches a feature, the **load-memory skill** reads that note and answers from it, framed as untrusted reference.

---

## Safety

- Memory is **untrusted data, never instructions** — never used for auth decisions or fed to eval/shell/SQL/HTML.
- All writes are **snapshotted** before overwrite.
- Uninstalling the plugin removes the commands/skill/hook but **leaves your memory data** on disk — wipe it with `/layered-memory:uninstall-clean` (dry-run → `--yes`).

---

## Roadmap

Working today: feature-note build (footprint match + episode extract + fold-into-one-note), incremental/resumable ingest, cluster-targeted reconcile with LLM same-feature judge, slim recent-N index injection, on-disk undo snapshots, clean uninstall. Planned next:

- **Live auto-capture** (capture as you work + write-up at session end, so no manual `/build`) — the biggest missing piece.
- **Pull-on-demand read path** — match the prompt to a feature on the fly instead of injecting the recent-N index.
- **Better theme capturing** — captured themes may still have overlapping context.
- **Context growth** — bounded per-call now, but total memory still grows; figuring out long-term handling.
- **`/layered-memory:undo`** — undo manifests are written, but no replay command yet.
- **Reconcile split/prune** — currently merge-only (no note splitting or stale-line pruning).
- **Nightly reconcile**, **per-project scope** builds, **`--reset`**, **ledger compaction**.
- **Packaging**: privacy `<private>` exclusion, Windows/Linux support.
- **Structure**: Move away from file structure and bring other persistent storage if required

---

## Development

```bash
python3 -m pytest          # test suite (stdlib runtime; pytest dev-only)
```

macOS-first. Plugin runtime is pure Python stdlib; the model call goes through the `claude` CLI. Local plugin updates are version-pinned — bump `version` in `plugin.json` + `marketplace.json` (and reinstall) for changes to take effect.

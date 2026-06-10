#!/usr/bin/env python3
"""Engine B — global theme consolidation (spec §8.5, focused: merge overlapping + reindex).

Reads ALL current theme summaries, asks the model to merge overlapping/duplicate themes
into one coherent set (preserving distinct facts), then rewrites themes + index and deletes
themes that were merged away. Snapshots everything first; writes an undo manifest.
Stdlib only. `model_caller` is injectable for tests."""
from pathlib import Path

import paths
import formats
import slugs as slugmod
import locking
import snapshot
import model as modelmod
from build import ENGINE_A_SCHEMA, _strip_frontmatter, _load_existing

_SKILL = (Path(__file__).resolve().parent.parent
          / "skills" / "summary-to-summary" / "SKILL.md")


def _reconcile_prompt(bodies: dict) -> str:
    skill = _strip_frontmatter(_SKILL.read_text())
    block = "\n\n".join(f"### THEME: {slug}\n{body}"
                        for slug, body in bodies.items()) or "(none)"
    return (f"{skill}\n\n"
            f"=== CURRENT THEME SUMMARIES (merge/dedup; keep all distinct facts) ===\n"
            f"{block}\n")


def run_reconcile(mem: Path, base_mem: Path, cfg: dict, ts: str, op_id: str,
                  model_caller=None, progress=None) -> dict:
    """Consolidate the theme set. Returns a receipt dict."""
    emit = progress or (lambda *_: None)
    mem = Path(mem); base_mem = Path(base_mem)
    bodies = _load_existing(mem)                 # slug -> body
    if len(bodies) < 2:
        emit(f"reconcile: {len(bodies)} theme(s) — nothing to merge.")
        return {"themes_before": len(bodies), "themes_after": len(bodies),
                "merged": 0, "themes": sorted(bodies), "errors": []}

    if model_caller is None:
        def model_caller(prompt, schema, model, timeout):
            return modelmod.call_model(
                prompt, schema, model, timeout,
                max_retries=cfg.get("max_call_retries", 0),
                on_retry=lambda nt: emit(f"… reconcile timed out — retrying at {nt}s"))

    emit(f"reconcile: consolidating {len(bodies)} themes …")
    result = model_caller(_reconcile_prompt(bodies), ENGINE_A_SCHEMA,
                          cfg.get("build_model") or cfg["writeup_model"],
                          cfg.get("reconcile_call_timeout_sec")
                          or cfg["writeup_call_timeout_sec"])
    new_themes = result.get("themes", [])
    if not new_themes:
        # Safety: never wipe the whole set on a bad/empty model response.
        emit("reconcile: model returned no themes — aborting, kept current set.")
        return {"themes_before": len(bodies), "themes_after": len(bodies),
                "merged": 0, "themes": sorted(bodies), "errors": ["empty result"]}

    with locking.lock(mem, timeout=cfg["writeup_lock_timeout_sec"]):
        current = {f.stem for f in paths.themes_dir(mem).glob("*.md")}
        manifest = {}
        for slug in current:                     # snapshot every current theme first
            snap = snapshot.snapshot_theme(mem, slug, op_id, ts)
            manifest[slug] = {"scope": "base", "scope_dir": str(mem), "slug": slug,
                              "action": "updated", "snapshot": str(snap) if snap else None}

        new_slugs = set()
        index_entries = []
        for t in new_themes:
            slug = slugmod.normalize_slug(t["slug"])
            new_slugs.add(slug)
            theme = {"slug": slug, "scope": "base", "updated": ts,
                     "sources": [], "body": t["merged_markdown"]}
            locking.atomic_write(paths.themes_dir(mem) / f"{slug}.md",
                                 formats.serialize_theme(theme))
            index_entries.append({"slug": slug, "oneliner": t["oneliner"],
                                  "keywords": t.get("keywords", []),
                                  "path": f"themes/{slug}.md"})
            if slug not in current:
                manifest[slug] = {"scope": "base", "scope_dir": str(mem), "slug": slug,
                                  "action": "created", "snapshot": None}

        for slug in current - new_slugs:         # delete merged-away themes
            (paths.themes_dir(mem) / f"{slug}.md").unlink()
            manifest[slug]["action"] = "deleted"

        # index = the consolidated set ONLY (authoritative rewrite)
        locking.atomic_write(paths.index_path(mem),
                             formats.serialize_index(index_entries, "base"))
        snapshot.write_manifest(base_mem, op_id, list(manifest.values()))

    merged = max(0, len(bodies) - len(new_slugs))
    emit(f"reconcile: {len(bodies)} → {len(new_slugs)} themes (merged {merged}).")
    return {"themes_before": len(bodies), "themes_after": len(new_slugs),
            "merged": merged, "themes": sorted(new_slugs), "errors": []}


def main(argv=None):
    import sys
    import config as cfgmod
    base = paths.base_memory_dir()
    cfg = cfgmod.load_config(base)
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    op_id = f"reconcile-{ts.replace(':', '-')}"

    def _log(msg):
        print(f"[memory] {msg}", flush=True)

    rec = run_reconcile(base, base_mem=base, cfg=cfg, ts=ts, op_id=op_id, progress=_log)
    print(f"[memory] /memory:reconcile → {rec['themes_before']}→{rec['themes_after']} "
          f"themes (merged {rec['merged']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

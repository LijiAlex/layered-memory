#!/usr/bin/env python3
"""Engine B — cluster-targeted consolidation (Step 5). Fixes the old all-themes timeout +
delete-by-absence data-loss.

- Find candidate duplicate CLUSTERS deterministically (resolve.score over match-keys).
  Themes in no cluster are NEVER touched.
- Merge one small cluster at a time (bounded model call). Resumable: a failed/garbled
  cluster is aborted (originals kept) and the rest still process.
- Safe-delete: within a processed cluster, delete only the input slugs the model consolidated
  away. Abort the cluster if the result is empty, unparseable, or has MORE notes than went in.
Stdlib only; model_caller injectable.
"""
from pathlib import Path

import paths
import formats
import slugs as slugmod
import locking
import snapshot
import model as modelmod
import footprint as fpmod
import resolve
from build import ENGINE_A_SCHEMA, _strip_frontmatter, _load_existing, reindex_orphans

_SKILL = (Path(__file__).resolve().parent.parent
          / "skills" / "summary-to-summary" / "SKILL.md")


def find_clusters(mk_db: dict, threshold: float = 8.0, max_size: int = 5,
                  kw_jaccard: float = 0.4) -> list:
    """Union notes that look like duplicates: either structured overlap (resolve.score >=
    threshold) OR high keyword-set overlap (Jaccard >= kw_jaccard — the fallback that lets
    footprint-less legacy notes cluster). Returns clusters (>=2 slugs), each capped to max_size."""
    slugs = sorted(mk_db)
    parent = {s: s for s in slugs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(slugs)):
        for j in range(i + 1, len(slugs)):
            a, b = mk_db[slugs[i]], mk_db[slugs[j]]
            if (resolve.score(a, b) >= threshold
                    or resolve.keyword_jaccard(a, b) >= kw_jaccard):
                parent[find(slugs[i])] = find(slugs[j])

    groups = {}
    for s in slugs:
        groups.setdefault(find(s), []).append(s)
    clusters = []
    for g in groups.values():
        if len(g) < 2:
            continue
        g = sorted(g)
        for k in range(0, len(g), max_size):       # cap each cluster's size
            chunk = g[k:k + max_size]
            if len(chunk) >= 2:
                clusters.append(chunk)
    return clusters


def _cluster_prompt(bodies: dict) -> str:
    skill = _strip_frontmatter(_SKILL.read_text())
    block = "\n\n".join(f"### NOTE: {slug}\n{body}" for slug, body in bodies.items())
    return (f"{skill}\n\n"
            f"=== CANDIDATE LOOK-ALIKE NOTES (merge these; keep all distinct facts) ===\n"
            f"{block}\n")


def run_reconcile(mem: Path, base_mem: Path, cfg: dict, ts: str, op_id: str,
                  model_caller=None, progress=None) -> dict:
    emit = progress or (lambda *_: None)
    mem = Path(mem); base_mem = Path(base_mem)

    orphans = reindex_orphans(mem)                  # index any stray theme files first
    if orphans:
        emit(f"reconcile: reindexed {orphans} orphan note(s) (were missing from index).")
    fpmod.write_match_keys(mem)                     # rebuild match-keys from the full index
    mk_db = fpmod.read_match_keys(mem)
    before = len(mk_db)
    if before < 2:
        emit(f"reconcile: {before} note(s) — nothing to merge.")
        return {"themes_before": before, "themes_after": before, "merged": 0, "errors": []}

    clusters = find_clusters(mk_db, cfg.get("reconcile_cluster_threshold", 8.0),
                             cfg.get("reconcile_cluster_max", 5),
                             cfg.get("reconcile_kw_jaccard", 0.4))
    if not clusters:
        emit("reconcile: no duplicate clusters found — nothing to merge.")
        return {"themes_before": before, "themes_after": before, "merged": 0, "errors": []}
    emit(f"reconcile: {len(clusters)} candidate cluster(s) to merge.")

    if model_caller is None:
        def model_caller(prompt, schema, model, timeout):
            return modelmod.call_model(
                prompt, schema, model, timeout,
                max_retries=cfg.get("max_call_retries", 0),
                on_retry=lambda nt: emit(f"… reconcile cluster timed out — retrying at {nt}s"))

    rmodel = cfg.get("build_model") or cfg["writeup_model"]
    rtimeout = cfg.get("reconcile_call_timeout_sec") or cfg["writeup_call_timeout_sec"]

    idx_path = paths.index_path(mem)
    by_slug = {e["slug"]: e for e in
               (formats.parse_index(idx_path.read_text()) if idx_path.exists() else [])}
    fps = {f.stem: formats.parse_theme(f.read_text()).get("footprint", {})
           for f in paths.themes_dir(mem).glob("*.md")}
    manifest = {}
    merged_total = 0
    errors = []

    with locking.lock(mem, timeout=cfg["writeup_lock_timeout_sec"]):
        for cluster in clusters:
            bodies = {}
            for slug in cluster:
                tp = paths.themes_dir(mem) / f"{slug}.md"
                if tp.exists():
                    bodies[slug] = formats.parse_theme(tp.read_text())["body"]
            if len(bodies) < 2:
                continue
            emit(f"reconcile: merging {sorted(bodies)} …")
            try:
                result = model_caller(_cluster_prompt(bodies), ENGINE_A_SCHEMA,
                                      rmodel, rtimeout)
            except Exception as e:                  # noqa: BLE001
                emit(f"reconcile: cluster {sorted(bodies)} errored ({str(e)[:60]}) — kept")
                errors.append({"cluster": sorted(bodies), "error": str(e)[:200]})
                continue
            new = result.get("themes", [])
            if not new or len(new) > len(bodies):    # garbled/expanded → abort, keep originals
                emit(f"reconcile: cluster {sorted(bodies)} bad result — kept (no delete)")
                errors.append({"cluster": sorted(bodies), "error": "bad result"})
                continue

            cluster_fp = {}
            for slug in bodies:
                cluster_fp = fpmod.merge_footprints(cluster_fp, fps.get(slug, {}))
            new_slugs = set()
            for t in new:
                slug = slugmod.normalize_slug(t["slug"])
                new_slugs.add(slug)
                snap = snapshot.snapshot_theme(mem, slug, op_id, ts)
                manifest[slug] = {"scope": "base", "scope_dir": str(mem), "slug": slug,
                                  "action": "updated" if slug in bodies else "created",
                                  "snapshot": str(snap) if snap else None}
                locking.atomic_write(paths.themes_dir(mem) / f"{slug}.md",
                                     formats.serialize_theme(
                                         {"slug": slug, "scope": "base", "updated": ts,
                                          "footprint": cluster_fp, "body": t["merged_markdown"]}))
                by_slug[slug] = {"slug": slug, "oneliner": t["oneliner"],
                                 "keywords": t.get("keywords", []),
                                 "path": f"themes/{slug}.md"}
            for slug in set(bodies) - new_slugs:     # deliberately merged away
                snap = snapshot.snapshot_theme(mem, slug, op_id, ts)
                (paths.themes_dir(mem) / f"{slug}.md").unlink()
                manifest[slug] = {"scope": "base", "scope_dir": str(mem), "slug": slug,
                                  "action": "deleted", "snapshot": str(snap) if snap else None}
                by_slug.pop(slug, None)
            merged_total += len(bodies) - len(new_slugs)

        if manifest:
            locking.atomic_write(idx_path,
                                 formats.serialize_index(list(by_slug.values()), "base"))
            fpmod.write_match_keys(mem)
            snapshot.write_manifest(base_mem, op_id, list(manifest.values()))

    after = len(list(paths.themes_dir(mem).glob("*.md")))
    emit(f"reconcile: {before} → {after} notes (merged {merged_total}).")
    return {"themes_before": before, "themes_after": after,
            "merged": merged_total, "errors": errors}


def main(argv=None):
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
          f"notes (merged {rec['merged']})")
    if rec["errors"]:
        print(f"  ! {len(rec['errors'])} cluster(s) kept un-merged (errored/bad result)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

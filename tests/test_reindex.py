import build
import formats
import footprint as fpmod
import reconcile
import paths


def _theme(mem, slug, body):
    paths.themes_dir(mem).mkdir(parents=True, exist_ok=True)
    (paths.themes_dir(mem) / f"{slug}.md").write_text(formats.serialize_theme(
        {"slug": slug, "scope": "base", "updated": "t", "footprint": {}, "body": body}))


def test_reindex_orphans_adds_missing_with_body_keywords(tmp_path):
    mem = tmp_path / "mem"
    _theme(mem, "daily-recap-scheduled-task",
           "## Purpose\nDaily recap task sends a Slack DM summarizing learnings.\n")
    # index starts empty → both file is an orphan
    added = build.reindex_orphans(mem)
    assert added == 1
    idx = {e["slug"]: e for e in formats.parse_index((mem / "index.md").read_text())}
    assert "daily-recap-scheduled-task" in idx
    kw = idx["daily-recap-scheduled-task"]["keywords"]
    assert "daily" in kw and "recap" in kw and "scheduled" in kw   # slug-derived
    assert "slack" in kw or "learnings" in kw                       # purpose-derived
    assert idx["daily-recap-scheduled-task"]["oneliner"].startswith("Daily recap")


def test_orphan_dups_cluster_after_reindex(tmp_path):
    mem = tmp_path / "mem"
    _theme(mem, "daily-recap-scheduled-task",
           "## Purpose\nDaily automated recap sends Slack DM summarizing learnings spaced repetition.\n")
    _theme(mem, "daily-recap-scheduled-task-execution-blocker",
           "## Purpose\nDaily automated recap Slack DM summarizing learnings; blocked on permissions.\n")
    build.reindex_orphans(mem)
    fpmod.write_match_keys(mem)
    mk = fpmod.read_match_keys(mem)
    clusters = reconcile.find_clusters(mk)
    assert any({"daily-recap-scheduled-task",
                "daily-recap-scheduled-task-execution-blocker"} == set(c) for c in clusters)

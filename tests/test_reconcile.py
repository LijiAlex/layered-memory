import json
from pathlib import Path
import reconcile
import formats
import footprint as fpmod
import config
import paths


def _cfg():
    return dict(config.DEFAULTS)


def _seed_note(mem, slug, footprint=None, body="## Cross-repo map\nx\n"):
    paths.themes_dir(mem).mkdir(parents=True, exist_ok=True)
    (paths.themes_dir(mem) / f"{slug}.md").write_text(formats.serialize_theme(
        {"slug": slug, "scope": "base", "updated": "t",
         "footprint": footprint or {}, "body": body}))


def test_find_clusters_groups_shared_ticket():
    db = {
        "feat-a": {"tickets": ["GOV-1"], "repos": ["r"], "files_written": [],
                   "files_read_recurring": [], "symbols": [], "skills_used": []},
        "feat-a2": {"tickets": ["GOV-1"], "repos": ["r"], "files_written": [],
                    "files_read_recurring": [], "symbols": [], "skills_used": []},
        "unrelated": {"tickets": ["ZZZ-9"], "repos": ["other"], "files_written": [],
                      "files_read_recurring": [], "symbols": [], "skills_used": []},
    }
    clusters = reconcile.find_clusters(db)
    assert any(set(c) == {"feat-a", "feat-a2"} for c in clusters)
    assert all("unrelated" not in c for c in clusters)


def test_find_clusters_via_keyword_jaccard_for_legacy():
    # footprint-less (legacy) notes cluster on keyword overlap ratio, not structured score
    db = {
        "a": {"keywords": ["timeout", "heracles", "workflow", "approval"]},
        "a2": {"keywords": ["timeout", "heracles", "workflow", "guest"]},
        "other": {"keywords": ["purge", "cassandra", "delete"]},
    }
    clusters = reconcile.find_clusters(db, threshold=8.0, kw_jaccard=0.4)
    assert any(set(c) == {"a", "a2"} for c in clusters)
    assert all("other" not in c for c in clusters)


def test_reconcile_merges_cluster_and_deletes_merged_away(tmp_path):
    mem = tmp_path / "mem"
    fp = {"tickets": ["GOV-1"], "repos": ["heracles"]}
    _seed_note(mem, "feat-a", fp, "## Cross-repo map\nA\n")
    _seed_note(mem, "feat-a2", fp, "## Cross-repo map\nA2\n")
    _seed_note(mem, "solo", {"tickets": ["ZZZ-9"], "repos": ["z"]}, "## Cross-repo map\nS\n")
    fpmod.write_match_keys(mem)

    def caller(p, s, m, t):                          # merges the cluster into ONE note
        return {"themes": [{"slug": "feat-a", "oneliner": "merged",
                            "keywords": ["k"], "merged_markdown": "## Cross-repo map\nMERGED"}]}

    r = reconcile.run_reconcile(mem, base_mem=mem, cfg=_cfg(), ts="t2", op_id="rec",
                                model_caller=caller)
    assert not (paths.themes_dir(mem) / "feat-a2.md").exists()    # merged away → deleted
    assert (paths.themes_dir(mem) / "feat-a.md").exists()
    assert "MERGED" in (paths.themes_dir(mem) / "feat-a.md").read_text()
    assert (paths.themes_dir(mem) / "solo.md").exists()           # untouched singleton
    assert r["merged"] == 1
    man = json.loads(next((mem / "history" / "_ops").glob("*.json")).read_text())
    actions = {e["slug"]: e["action"] for e in man["themes"]}
    assert actions["feat-a2"] == "deleted"


def test_reconcile_aborts_cluster_on_empty_result(tmp_path):
    mem = tmp_path / "mem"
    fp = {"tickets": ["GOV-1"], "repos": ["heracles"]}
    _seed_note(mem, "feat-a", fp)
    _seed_note(mem, "feat-a2", fp)
    fpmod.write_match_keys(mem)

    def caller(p, s, m, t):
        return {"themes": []}                        # garbled/empty → must NOT delete

    r = reconcile.run_reconcile(mem, base_mem=mem, cfg=_cfg(), ts="t2", op_id="rec",
                                model_caller=caller)
    assert (paths.themes_dir(mem) / "feat-a.md").exists()         # both kept
    assert (paths.themes_dir(mem) / "feat-a2.md").exists()
    assert r["merged"] == 0 and r["errors"]


def test_reconcile_aborts_when_result_expands(tmp_path):
    mem = tmp_path / "mem"
    fp = {"tickets": ["GOV-1"], "repos": ["heracles"]}
    _seed_note(mem, "feat-a", fp)
    _seed_note(mem, "feat-a2", fp)
    fpmod.write_match_keys(mem)

    def caller(p, s, m, t):                          # 3 out of 2 in → invented → abort
        return {"themes": [{"slug": f"x{i}", "oneliner": "o", "keywords": [],
                            "merged_markdown": "b"} for i in range(3)]}

    r = reconcile.run_reconcile(mem, base_mem=mem, cfg=_cfg(), ts="t2", op_id="rec",
                                model_caller=caller)
    assert (paths.themes_dir(mem) / "feat-a.md").exists()
    assert (paths.themes_dir(mem) / "feat-a2.md").exists()
    assert r["merged"] == 0 and r["errors"]


def test_reconcile_noop_under_two_notes(tmp_path):
    mem = tmp_path / "mem"
    _seed_note(mem, "solo", {"tickets": ["G-1"]})
    fpmod.write_match_keys(mem)
    calls = {"n": 0}

    def caller(p, s, m, t):
        calls["n"] += 1
        return {"themes": []}

    r = reconcile.run_reconcile(mem, base_mem=mem, cfg=_cfg(), ts="t", op_id="rec",
                                model_caller=caller)
    assert calls["n"] == 0 and r["merged"] == 0

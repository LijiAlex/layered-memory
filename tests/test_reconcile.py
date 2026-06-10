import json
from pathlib import Path
import reconcile
import formats
import config
import paths


def _write_theme(mem, slug, body="## Purpose\nx\n"):
    paths.themes_dir(mem).mkdir(parents=True, exist_ok=True)
    (paths.themes_dir(mem) / f"{slug}.md").write_text(
        formats.serialize_theme({"slug": slug, "scope": "base",
                                 "updated": "t", "sources": [], "body": body}))


def _cfg():
    return dict(config.DEFAULTS)


def test_merges_overlapping_themes(tmp_path):
    mem = tmp_path / "mem"
    _write_theme(mem, "layered-memory-plugin", "## Purpose\ncore\n")
    _write_theme(mem, "layered-memory-plugin-setup-and-timeout-tuning", "## Purpose\nsetup\n")

    def caller(prompt, schema, model, timeout):
        # model consolidates the two into one
        return {"themes": [{"slug": "layered-memory-plugin",
                            "oneliner": "the plugin", "keywords": ["plugin"],
                            "merged_markdown": "## Purpose\ncore + setup\n"}]}

    r = reconcile.run_reconcile(mem, base_mem=mem, cfg=_cfg(), ts="t2",
                                op_id="reconcile-x", model_caller=caller)
    assert r["themes_before"] == 2
    assert r["themes_after"] == 1
    assert r["merged"] == 1
    # the merged-away theme file is gone
    assert not (paths.themes_dir(mem) / "layered-memory-plugin-setup-and-timeout-tuning.md").exists()
    assert (paths.themes_dir(mem) / "layered-memory-plugin.md").exists()
    # index rebuilt to the single theme
    idx = formats.parse_index((mem / "index.md").read_text())
    assert [e["slug"] for e in idx] == ["layered-memory-plugin"]
    # manifest records the deletion (undoable)
    man = json.loads(next((mem / "history" / "_ops").glob("*.json")).read_text())
    actions = {e["slug"]: e["action"] for e in man["themes"]}
    assert actions["layered-memory-plugin-setup-and-timeout-tuning"] == "deleted"


def test_noop_under_two_themes(tmp_path):
    mem = tmp_path / "mem"
    _write_theme(mem, "solo")
    calls = {"n": 0}

    def caller(prompt, schema, model, timeout):
        calls["n"] += 1
        return {"themes": []}

    r = reconcile.run_reconcile(mem, base_mem=mem, cfg=_cfg(), ts="t",
                                op_id="op", model_caller=caller)
    assert calls["n"] == 0                       # no model call for <2 themes
    assert r["merged"] == 0
    assert (paths.themes_dir(mem) / "solo.md").exists()


def test_empty_result_aborts_without_deleting(tmp_path):
    mem = tmp_path / "mem"
    _write_theme(mem, "a")
    _write_theme(mem, "b")

    def caller(prompt, schema, model, timeout):
        return {"themes": []}                    # bad/empty response

    r = reconcile.run_reconcile(mem, base_mem=mem, cfg=_cfg(), ts="t",
                                op_id="op", model_caller=caller)
    assert r["errors"]                           # flagged
    # nothing deleted — both themes survive
    assert (paths.themes_dir(mem) / "a.md").exists()
    assert (paths.themes_dir(mem) / "b.md").exists()

from pathlib import Path
import json
import build
import formats
import config


def _fake_model(themes):
    def caller(prompt, schema, model, timeout):
        return {"themes": themes}
    return caller


def test_build_writes_theme_and_index(tmp_path, monkeypatch):
    # transcript dir with one session
    tdir = tmp_path / "tx" / "proj"
    tdir.mkdir(parents=True)
    (tdir / "s1.jsonl").write_text(json.dumps(
        {"message": {"role": "user", "content": "which connectors?"}}) + "\n")
    mem = tmp_path / "mem"
    cfg = dict(config.DEFAULTS)
    cfg["transcript_dir"] = str(tmp_path / "tx")

    fake = _fake_model([{
        "slug": "Connector Inventory",
        "oneliner": "connectors; no Snowflake.",
        "keywords": ["connector", "snowflake"],
        "merged_markdown": "## Key facts & decisions\n- No Snowflake.\n",
    }])
    receipt = build.run_build(mem, base_mem=mem, cfg=cfg,
                              ts="2026-06-09T00:00:00Z", op_id="build-test",
                              model_caller=fake)

    theme_file = mem / "themes" / "connector-inventory.md"
    assert theme_file.exists()                       # slug normalized
    parsed = formats.parse_theme(theme_file.read_text())
    assert "No Snowflake." in parsed["body"]
    assert parsed["scope"] == "base"

    idx = formats.parse_index((mem / "index.md").read_text())
    assert idx[0]["slug"] == "connector-inventory"
    assert idx[0]["keywords"] == ["connector", "snowflake"]

    # manifest written, action=created
    man = json.loads((mem / "history" / "_ops" / "build-test.json").read_text())
    assert man["themes"][0]["action"] == "created"
    assert receipt["themes_written"] == 1


def test_build_no_transcripts_is_noop(tmp_path):
    mem = tmp_path / "mem"
    cfg = dict(config.DEFAULTS)
    cfg["transcript_dir"] = str(tmp_path / "empty")
    receipt = build.run_build(mem, base_mem=mem, cfg=cfg,
                              ts="t", op_id="op", model_caller=_fake_model([]))
    assert receipt["themes_written"] == 0
    assert not (mem / "index.md").exists() or formats.parse_index(
        (mem / "index.md").read_text()) == []


def test_build_second_run_snapshots_prior(tmp_path):
    mem = tmp_path / "mem"
    cfg = dict(config.DEFAULTS); cfg["transcript_dir"] = str(tmp_path / "tx")
    (tmp_path / "tx").mkdir()
    (tmp_path / "tx" / "s.jsonl").write_text(json.dumps(
        {"message": {"role": "user", "content": "x"}}) + "\n")
    t1 = [{"slug": "foo", "oneliner": "v1", "keywords": ["a"],
           "merged_markdown": "## Purpose\nv1\n"}]
    build.run_build(mem, base_mem=mem, cfg=cfg, ts="t1", op_id="op1",
                    model_caller=_fake_model(t1))
    t2 = [{"slug": "foo", "oneliner": "v2", "keywords": ["a"],
           "merged_markdown": "## Purpose\nv2\n"}]
    build.run_build(mem, base_mem=mem, cfg=cfg, ts="t2", op_id="op2",
                    model_caller=_fake_model(t2))
    # a snapshot of v1 exists; manifest op2 records action=updated
    snaps = list((mem / "history" / "foo").glob("*.md"))
    assert snaps and "v1" in snaps[0].read_text()
    man = json.loads((mem / "history" / "_ops" / "op2.json").read_text())
    assert man["themes"][0]["action"] == "updated"

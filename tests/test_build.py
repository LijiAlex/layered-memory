import json
from pathlib import Path
import build
import formats
import config


def _mk_transcript(tdir, name, content="hi"):
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / f"{name}.jsonl").write_text(json.dumps(
        {"message": {"role": "user", "content": content}}) + "\n")


def _cfg(tmp_path, **over):
    c = dict(config.DEFAULTS)
    c["transcript_dir"] = str(tmp_path / "tx")
    c.update(over)
    return c


def test_strip_frontmatter():
    md = "---\nname: x\ndescription: y\n---\n# Body\ntext\n"
    out = build._strip_frontmatter(md)
    assert out.startswith("# Body")
    assert "name: x" not in out


def test_engine_prompt_does_not_start_with_dash():
    # the skill begins with YAML frontmatter (---); the prompt must NOT, or the CLI
    # arg parser treats it as an option flag.
    p = build._engine_prompt("some transcript", {})
    assert not p.lstrip().startswith("-")


def test_one_call_per_transcript_and_themes_written(tmp_path):
    _mk_transcript(tmp_path / "tx" / "p", "s1")
    _mk_transcript(tmp_path / "tx" / "p", "s2")
    mem = tmp_path / "mem"
    calls = {"n": 0}

    def caller(prompt, schema, model, timeout):
        calls["n"] += 1
        return {"themes": [{"slug": f"theme{calls['n']}", "oneliner": "o",
                            "keywords": ["k"], "merged_markdown": "## Purpose\nx\n"}]}

    r = build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path),
                        ts="t", op_id="op", model_caller=caller)
    assert calls["n"] == 2                         # one call per transcript
    assert r["transcripts_processed"] == 2
    assert set(r["themes"]) == {"theme1", "theme2"}
    # ledger records both sessions
    done = (mem / "processed.log").read_text().split()
    assert set(done) == {"s1", "s2"}


def test_rerun_skips_processed(tmp_path):
    _mk_transcript(tmp_path / "tx" / "p", "s1")
    mem = tmp_path / "mem"

    def caller(prompt, schema, model, timeout):
        return {"themes": [{"slug": "foo", "oneliner": "o", "keywords": [],
                            "merged_markdown": "## Purpose\nv\n"}]}

    build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t1", op_id="op1",
                    model_caller=caller)
    calls = {"n": 0}

    def caller2(prompt, schema, model, timeout):
        calls["n"] += 1
        return {"themes": []}

    r = build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t2", op_id="op2",
                        model_caller=caller2)
    assert calls["n"] == 0                          # nothing new → no model calls
    assert r["transcripts_processed"] == 0


def test_max_transcripts_cap(tmp_path):
    for n in ("s1", "s2", "s3"):
        _mk_transcript(tmp_path / "tx" / "p", n)
    mem = tmp_path / "mem"
    calls = {"n": 0}

    def caller(prompt, schema, model, timeout):
        calls["n"] += 1
        return {"themes": []}

    build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path, build_max_transcripts=2),
                    ts="t", op_id="op", model_caller=caller)
    assert calls["n"] == 2                          # capped


def test_char_cap_truncates_prompt(tmp_path):
    big = "A" * 100_000
    _mk_transcript(tmp_path / "tx" / "p", "s1", content=big)
    mem = tmp_path / "mem"
    seen = {}

    def caller(prompt, schema, model, timeout):
        seen["prompt"] = prompt
        return {"themes": []}

    build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path, build_transcript_char_cap=5000),
                    ts="t", op_id="op", model_caller=caller)
    assert "…[truncated]" in seen["prompt"]
    assert seen["prompt"].count("A") <= 5001        # capped well below 100k


def test_snapshot_once_per_slug_and_manifest(tmp_path):
    # two transcripts both yielding slug "foo": first creates, second updates → 1 snapshot
    _mk_transcript(tmp_path / "tx" / "p", "s1")
    _mk_transcript(tmp_path / "tx" / "p", "s2")
    mem = tmp_path / "mem"
    bodies = iter(["## Purpose\nv1\n", "## Purpose\nv2\n"])

    def caller(prompt, schema, model, timeout):
        return {"themes": [{"slug": "foo", "oneliner": "o", "keywords": [],
                            "merged_markdown": next(bodies)}]}

    r = build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t", op_id="op",
                        model_caller=caller)
    # final body is v2
    assert "v2" in (mem / "themes" / "foo.md").read_text()
    # exactly one snapshot taken this op (the create had nothing to snapshot;
    # the second write snapshotted v1)
    snaps = list((mem / "history" / "foo").glob("*.md"))
    assert len(snaps) == 1 and "v1" in snaps[0].read_text()
    man = json.loads((mem / "history" / "_ops" / "op.json").read_text())
    assert man["themes"][0]["slug"] == "foo"
    assert man["themes"][0]["action"] == "created"   # didn't exist at op start


def test_model_error_is_resumable(tmp_path):
    _mk_transcript(tmp_path / "tx" / "p", "s1")
    _mk_transcript(tmp_path / "tx" / "p", "s2")
    mem = tmp_path / "mem"

    def boom(prompt, schema, model, timeout):
        raise RuntimeError("api down")

    r = build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t", op_id="op",
                        model_caller=boom)
    assert r["errors"]                               # error captured, not raised
    assert r["transcripts_processed"] == 0           # none completed
    # nothing marked processed → a later successful run will retry
    assert not (mem / "processed.log").exists() or \
        (mem / "processed.log").read_text().strip() == ""


def test_no_transcripts_is_noop(tmp_path):
    mem = tmp_path / "mem"
    r = build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t", op_id="op",
                        model_caller=lambda *a: {"themes": []})
    assert r["themes_written"] == 0
    assert r["transcripts_processed"] == 0

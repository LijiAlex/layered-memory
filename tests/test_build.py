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


def test_parse_args_limit():
    assert build._parse_args(["--limit", "3"]).limit == 3
    assert build._parse_args([]).limit is None


def test_main_applies_limit(monkeypatch, tmp_path):
    captured = {}

    def fake_run_build(mem, base_mem, cfg, ts, op_id, model_caller=None):
        captured["limit"] = cfg["build_max_transcripts"]
        return {"themes_written": 0, "themes": [], "transcripts_processed": 0,
                "errors": []}

    monkeypatch.setattr(build, "run_build", fake_run_build)
    monkeypatch.setattr(build.paths, "base_memory_dir", lambda: tmp_path)
    build.main(["--limit", "7"])
    assert captured["limit"] == 7


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


def test_head_tail_keeps_start_and_end():
    text = "HEAD" + ("x" * 1000) + "TAIL"
    out = build._head_tail(text, cap=100)
    assert out.startswith("HEAD")                  # start kept
    assert out.endswith("TAIL")                    # end kept (not lost to truncation)
    assert "truncated middle" in out
    # short text is returned untouched
    assert build._head_tail("short", cap=100) == "short"


def test_char_cap_samples_head_and_tail_in_prompt(tmp_path):
    # 'H' marks the session start, 'T' the end; filler 'Z' in between.
    big = "H" * 100 + "Z" * 100_000 + "T" * 100
    _mk_transcript(tmp_path / "tx" / "p", "s1", content=big)
    mem = tmp_path / "mem"
    seen = {}

    def caller(prompt, schema, model, timeout):
        seen["prompt"] = prompt
        return {"themes": []}

    build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path, build_transcript_char_cap=5000),
                    ts="t", op_id="op", model_caller=caller)
    assert "truncated middle" in seen["prompt"]
    assert "HHHH" in seen["prompt"]                 # session START present
    assert "TTTT" in seen["prompt"]                 # session END present (the win)
    assert seen["prompt"].count("Z") <= 5001        # middle still capped


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


def test_one_failure_does_not_abort_the_batch(tmp_path):
    # first model call fails, second succeeds — with `continue` (not `break`) the
    # second transcript must still be ingested, and the failed one stays un-processed.
    _mk_transcript(tmp_path / "tx" / "p", "s1")
    _mk_transcript(tmp_path / "tx" / "p", "s2")
    mem = tmp_path / "mem"
    calls = {"n": 0}

    def caller(prompt, schema, model, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("timeout")
        return {"themes": [{"slug": "ok", "oneliner": "o", "keywords": [],
                            "merged_markdown": "## Purpose\nx\n"}]}

    r = build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t", op_id="op",
                        model_caller=caller)
    assert calls["n"] == 2                       # both attempted (didn't abort after #1)
    assert r["themes_written"] == 1              # the second one still ingested
    assert len(r["errors"]) == 1                 # the first recorded as an error
    assert r["transcripts_processed"] == 1       # only the success marked done
    done = set((mem / "processed.log").read_text().split())
    assert len(done) == 1                         # failed transcript NOT marked → retries later


def test_no_transcripts_is_noop(tmp_path):
    mem = tmp_path / "mem"
    r = build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t", op_id="op",
                        model_caller=lambda *a: {"themes": []})
    assert r["themes_written"] == 0
    assert r["transcripts_processed"] == 0

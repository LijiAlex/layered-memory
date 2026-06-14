import json
import os
from pathlib import Path
import build
import formats
import footprint as fpmod
import config


# ---- helpers -------------------------------------------------------------

def _session(tdir, name, repo="heracles", ticket="", file="store/a.go", text="do work"):
    """Write a non-trivial session: a user turn + an Edit (so footprint has a write)."""
    tdir.mkdir(parents=True, exist_ok=True)
    rows = [
        {"message": {"role": "user", "content": f"{text} {ticket}".strip()}},
        {"message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "1", "name": "Edit",
             "input": {"file_path": f"/Users/x/code/{repo}/{file}"}}]}},
    ]
    (tdir / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return tdir / f"{name}.jsonl"


def _cfg(tmp_path, **over):
    c = dict(config.DEFAULTS)
    c["transcript_dir"] = str(tmp_path / "tx")
    c.update(over)
    return c


def _fake_model(episode=None, note=None):
    """One caller serving both engines; branches on the schema's required keys."""
    episode = episode or {"type": "new-feature", "slug": "feat-x", "oneliner": "feature x",
                          "keywords": ["x"], "episode_markdown": "## What\nbuilt x"}
    note = note or {"slug": "feat-x", "oneliner": "merged x", "keywords": ["x"],
                    "note_markdown": "## Cross-repo map\nheracles does x\n## Episodes\n- t: x"}

    def caller(prompt, schema, model, timeout):
        req = schema.get("required", [])
        if "episode_markdown" in req:
            return episode
        if "note_markdown" in req:
            return note
        return {"choice": "new"}            # tiebreak schema
    return caller


def _sids(mem):
    return {ln.split()[0] for ln in (mem / "processed.log").read_text().splitlines() if ln.strip()}


# ---- trivial pre-filter --------------------------------------------------

def test_trivial_session_skipped_no_model_call(tmp_path):
    # user turn only, no writes, short → trivial → skipped before any call
    tdir = tmp_path / "tx" / "p"; tdir.mkdir(parents=True)
    (tdir / "s1.jsonl").write_text(json.dumps(
        {"message": {"role": "user", "content": "hi"}}) + "\n")
    mem = tmp_path / "mem"
    calls = {"n": 0}

    def caller(p, s, m, t):
        calls["n"] += 1
        return {}

    r = build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t", op_id="op",
                        model_caller=caller)
    assert calls["n"] == 0
    assert r["transcripts_processed"] == 1          # marked processed (trivial)
    assert r["themes_written"] == 0


# ---- new note (no existing → deterministic, no merge call) ---------------

def test_new_note_filed_from_episode(tmp_path):
    _session(tmp_path / "tx" / "p", "s1", ticket="GOV-1")
    mem = tmp_path / "mem"
    r = build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="2026-06-10T00:00:00Z",
                        op_id="op", model_caller=_fake_model())
    assert r["themes_written"] == 1
    assert "feat-x" in r["themes"]
    theme = formats.parse_theme((mem / "themes" / "feat-x.md").read_text())
    assert "built x" in theme["body"]
    assert "heracles" in theme["footprint"]["repos"]      # footprint persisted
    assert "GOV-1" in theme["footprint"]["tickets"]
    # match-keys file written
    assert "feat-x" in fpmod.read_match_keys(mem)
    assert _sids(mem) == {"s1"}


# ---- match → merge into existing note (ticket overlap) -------------------

def test_matched_session_merges_into_existing_note(tmp_path):
    mem = tmp_path / "mem"
    (mem / "themes").mkdir(parents=True)
    # pre-seed a note with a ticket footprint + its match-keys
    (mem / "themes" / "feat-x.md").write_text(formats.serialize_theme({
        "slug": "feat-x", "scope": "base", "updated": "t0",
        "footprint": {"repos": ["heracles"], "tickets": ["GOV-1"]},
        "body": "## Cross-repo map\nold\n"}))
    fpmod.write_match_keys(mem)
    # new session carrying the same ticket → should MATCH and merge
    _session(tmp_path / "tx" / "p", "s2", ticket="GOV-1")
    merged_note = {"slug": "feat-x", "oneliner": "merged", "keywords": ["x"],
                   "note_markdown": "## Cross-repo map\nMERGED CONTENT\n## Episodes\n- t: x"}
    r = build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t1", op_id="op",
                        model_caller=_fake_model(note=merged_note))
    body = (mem / "themes" / "feat-x.md").read_text()
    assert "MERGED CONTENT" in body                 # merge call result written
    assert r["themes_written"] == 1
    # no second duplicate note created
    assert len(list((mem / "themes").glob("*.md"))) == 1


# ---- ledger / ordering / resilience --------------------------------------

def test_ledger_records_sid_and_mtime(tmp_path):
    _session(tmp_path / "tx" / "p", "s1", ticket="GOV-1")
    mem = tmp_path / "mem"
    build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t", op_id="op",
                    model_caller=_fake_model())
    row = (mem / "processed.log").read_text().split()
    assert row[0] == "s1" and float(row[1]) > 0     # sid + mtime


def test_grown_session_reingested(tmp_path):
    f = _session(tmp_path / "tx" / "p", "s1", ticket="GOV-1")
    mem = tmp_path / "mem"
    calls = {"n": 0}

    def caller(p, s, m, t):
        calls["n"] += 1
        return _fake_model()(p, s, m, t)

    build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t1", op_id="op1",
                    model_caller=caller)
    first = calls["n"]
    st = f.stat(); os.utime(f, (st.st_atime + 1000, st.st_mtime + 1000))   # grew
    build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t2", op_id="op2",
                    model_caller=caller)
    assert calls["n"] > first                       # re-ingested, not skipped


def test_episode_error_is_resumable(tmp_path):
    _session(tmp_path / "tx" / "p", "s1", ticket="GOV-1")
    mem = tmp_path / "mem"

    def boom(p, s, m, t):
        raise RuntimeError("timeout")

    r = build.run_build(mem, base_mem=mem, cfg=_cfg(tmp_path), ts="t", op_id="op",
                        model_caller=boom)
    assert r["errors"] and r["transcripts_processed"] == 0
    assert not (mem / "processed.log").exists() or \
        (mem / "processed.log").read_text().strip() == ""


# ---- _parse_args / main wiring (unchanged) -------------------------------

def test_parse_args_limit():
    assert build._parse_args(["--limit", "3"]).limit == 3
    assert build._parse_args([]).limit is None


def test_main_applies_limit(monkeypatch, tmp_path):
    captured = {}

    def fake_run_build(mem, base_mem, cfg, ts, op_id, model_caller=None, progress=None):
        captured["limit"] = cfg["build_max_transcripts"]
        return {"themes_written": 0, "themes": [], "transcripts_processed": 0, "errors": []}

    monkeypatch.setattr(build, "run_build", fake_run_build)
    monkeypatch.setattr(build.paths, "base_memory_dir", lambda: tmp_path)
    build.main(["--limit", "7"])
    assert captured["limit"] == 7

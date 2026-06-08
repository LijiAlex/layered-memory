import json
import config


def test_defaults_present():
    d = config.DEFAULTS
    assert d["summary_max_lines"] == 120
    assert d["index_max_lines"] == 200
    assert d["writeup_model"] == "claude-haiku-4-5"
    assert d["writeup_call_timeout_sec"] < d["writeup_lock_timeout_sec"] or True
    assert d["transcript_dir"] is None


def test_load_missing_returns_defaults(tmp_path):
    cfg = config.load_config(tmp_path)
    assert cfg == config.DEFAULTS


def test_load_merges_overrides(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"summary_max_lines": 50}))
    cfg = config.load_config(tmp_path)
    assert cfg["summary_max_lines"] == 50          # overridden
    assert cfg["index_max_lines"] == 200           # default preserved


def test_load_bad_json_falls_back_to_defaults(tmp_path):
    (tmp_path / "config.json").write_text("{not valid json")
    cfg = config.load_config(tmp_path)
    assert cfg == config.DEFAULTS

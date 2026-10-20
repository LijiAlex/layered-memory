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


def test_load_non_utf8_falls_back_to_defaults(tmp_path):
    (tmp_path / "config.json").write_bytes(b"\xff\xfe\x00\x80 not utf-8 \xc3\x28")
    cfg = config.load_config(tmp_path)
    assert cfg == config.DEFAULTS


def test_load_directory_falls_back_to_defaults(tmp_path):
    (tmp_path / "config.json").mkdir()
    cfg = config.load_config(tmp_path)
    assert cfg == config.DEFAULTS


def test_load_unreadable_falls_back_to_defaults(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text(json.dumps({"summary_max_lines": 50}))

    def deny(self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(config.Path, "read_text", deny)
    cfg = config.load_config(tmp_path)
    assert cfg == config.DEFAULTS


def test_build_caps_present():
    d = config.DEFAULTS
    assert d["build_max_transcripts"] == 50
    assert d["build_transcript_char_cap"] == 120000

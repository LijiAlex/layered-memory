from pathlib import Path
import paths


def test_base_memory_dir_default(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert paths.base_memory_dir() == tmp_path / ".claude" / "memory"


def test_layout_helpers():
    mem = Path("/tmp/mem")
    assert paths.index_path(mem) == mem / "index.md"
    assert paths.themes_dir(mem) == mem / "themes"
    assert paths.history_dir(mem) == mem / "history"
    assert paths.ops_dir(mem) == mem / "history" / "_ops"


def test_transcript_dir_config_override(tmp_path):
    cfg = {"transcript_dir": str(tmp_path / "tx")}
    assert paths.transcript_dir(cfg) == tmp_path / "tx"


def test_transcript_dir_autodetect(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = {"transcript_dir": None}
    assert paths.transcript_dir(cfg) == tmp_path / ".claude" / "projects"


def test_processed_path():
    mem = Path("/tmp/mem")
    assert paths.processed_path(mem) == mem / "processed.log"

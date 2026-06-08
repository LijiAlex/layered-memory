import json
from pathlib import Path
import snapshot


def test_snapshot_existing_theme(tmp_path):
    mem = tmp_path
    (mem / "themes").mkdir()
    theme = mem / "themes" / "foo.md"
    theme.write_text("# foo\nold\n")
    snap = snapshot.snapshot_theme(mem, "foo", op_id="op1", ts="2026-06-09T00:00:00Z")
    assert snap is not None
    assert snap.read_text() == "# foo\nold\n"
    assert "op1" in snap.name


def test_snapshot_missing_theme_returns_none(tmp_path):
    (tmp_path / "themes").mkdir()
    assert snapshot.snapshot_theme(tmp_path, "nope", op_id="op1", ts="t") is None


def test_write_manifest(tmp_path):
    base = tmp_path
    entries = [{"scope": "base", "scope_dir": str(base), "slug": "foo",
                "action": "updated", "snapshot": "history/foo/x.md"}]
    p = snapshot.write_manifest(base, "op1", entries)
    data = json.loads(p.read_text())
    assert data["op_id"] == "op1"
    assert data["themes"][0]["slug"] == "foo"
    assert data["themes"][0]["action"] == "updated"

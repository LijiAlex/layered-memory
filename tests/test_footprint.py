import json
from pathlib import Path
import footprint


def _write(tmp, rows):
    p = tmp / "s.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def _tool(name, inp):
    return {"message": {"role": "assistant",
                        "content": [{"type": "tool_use", "name": name, "input": inp}]}}


def test_repo_of():
    assert footprint.repo_of("/Users/x/code/heracles/store/a.go") == "heracles"
    assert footprint.repo_of("/Users/x/.claude/settings.json") == "claude-config"
    assert footprint.repo_of("/tmp/foo") == "other"


def test_extract_writes_reads_skills_bash_tickets(tmp_path):
    p = _write(tmp_path, [
        {"message": {"role": "user", "content": "fix GOVFOUN-438 please"}},
        _tool("Edit", {"file_path": "/Users/x/code/heracles/store/a.go"}),
        _tool("Read", {"file_path": "/Users/x/code/atlas-metastore/b.java"}),
        _tool("Bash", {"command": "curl -s https://x | jq ."}),
        _tool("Skill", {"skill": "governance-studio"}),
        _tool("Grep", {"pattern": "ApprovalWorkflow", "path": "/Users/x/code/heracles"}),
    ])
    fp = footprint.extract_footprint(p)
    assert set(fp["repos"]) == {"heracles", "atlas-metastore"}
    assert fp["files_written"]["heracles"] == ["store/a.go"]
    assert "b.java" in fp["files_read"]["atlas-metastore"]
    assert fp["tickets"] == ["GOVFOUN-438"]
    assert "governance-studio" in fp["skills_used"]
    assert any("curl" in c for c in fp["commands"])
    assert "ApprovalWorkflow" in fp["symbols"]


def test_merge_accumulates_read_counts_and_caps():
    a = {"files_read": {"r": {"x.go": 1}}, "repos": ["r"]}
    b = {"files_read": {"r": {"x.go": 1, "y.go": 1}}, "repos": ["r"]}
    m = footprint.merge_footprints(a, b)
    assert m["files_read"]["r"]["x.go"] == 2      # recurring across sessions
    assert m["files_read"]["r"]["y.go"] == 1


def test_write_and_read_match_keys(tmp_path):
    import formats
    mem = tmp_path / "mem"
    (mem / "themes").mkdir(parents=True)
    (mem / "themes" / "foo.md").write_text(formats.serialize_theme({
        "slug": "foo", "scope": "base", "updated": "t",
        "footprint": {"repos": ["heracles"], "tickets": ["G-1"],
                      "files_read": {"heracles": {"a.go": 2}}},
        "body": "b\n"}))
    footprint.write_match_keys(mem)
    mk = footprint.read_match_keys(mem)
    assert mk["foo"]["repos"] == ["heracles"]
    assert mk["foo"]["tickets"] == ["G-1"]
    assert "heracles/a.go" in mk["foo"]["files_read_recurring"]


def test_match_keys_filters_reads_to_recurring():
    fp = {
        "repos": ["heracles"],
        "files_written": {"heracles": ["store/a.go"]},
        "files_read": {"heracles": {"recurring.go": 2, "oneoff.go": 1}},
        "symbols": {"Foo": 3}, "skills_used": ["gov"], "tickets": ["G-1"],
    }
    mk = footprint.match_keys(fp)
    assert "heracles/store/a.go" in mk["files_written"]
    assert "heracles/recurring.go" in mk["files_read_recurring"]
    assert "heracles/oneoff.go" not in mk["files_read_recurring"]   # one-off dropped
    assert mk["tickets"] == ["G-1"]

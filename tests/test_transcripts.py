import json
from pathlib import Path
import transcripts


def _write_jsonl(p: Path, rows):
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_discover(tmp_path):
    (tmp_path / "projA").mkdir()
    (tmp_path / "projA" / "s1.jsonl").write_text("{}\n")
    (tmp_path / "projA" / "notes.txt").write_text("ignore")
    found = transcripts.discover_transcripts(tmp_path)
    assert [f.name for f in found] == ["s1.jsonl"]


def test_discover_excludes_subagent_transcripts(tmp_path):
    # subagent transcripts live under a subagents/ dir; the parent session already
    # captures the main agent's summary, so these standalone files just fragment memory.
    (tmp_path / "projA" / "subagents").mkdir(parents=True)
    (tmp_path / "projA" / "s1.jsonl").write_text("{}\n")
    (tmp_path / "projA" / "subagents" / "agent-abc.jsonl").write_text("{}\n")
    found = transcripts.discover_transcripts(tmp_path)
    names = [f.name for f in found]
    assert "s1.jsonl" in names
    assert "agent-abc.jsonl" not in names


def test_read_transcript_extracts_text(tmp_path):
    p = tmp_path / "s1.jsonl"
    _write_jsonl(p, [
        {"message": {"role": "user", "content": "which connectors exist?"}},
        {"message": {"role": "assistant",
                     "content": [{"type": "text", "text": "Power BI, Fabric."},
                                 {"type": "tool_use", "name": "x"}]}},
        {"garbage": True},
    ])
    sid, text = transcripts.read_transcript(p)
    assert sid == "s1"
    assert "which connectors exist?" in text
    assert "Power BI, Fabric." in text
    assert "tool_use" not in text


def test_read_handles_bad_lines(tmp_path):
    p = tmp_path / "s2.jsonl"
    p.write_text("not json\n" + json.dumps(
        {"message": {"role": "user", "content": "hi"}}) + "\n")
    sid, text = transcripts.read_transcript(p)
    assert "hi" in text

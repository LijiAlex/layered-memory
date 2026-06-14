import json
from pathlib import Path
import transcripts as tx
import episode


def _write(tmp, rows):
    p = tmp / "s.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def _asst(blocks):
    return {"message": {"role": "assistant", "content": blocks}}


def _user(blocks):
    return {"message": {"role": "user", "content": blocks}}


def test_compress_keeps_actions_trims_bulk_and_dedupes_reads(tmp_path):
    p = _write(tmp_path, [
        _user("fix the timeout"),
        _asst([{"type": "tool_use", "id": "1", "name": "Read",
                "input": {"file_path": "/c/heracles/a.go"}}]),
        _asst([{"type": "tool_use", "id": "2", "name": "Read",
                "input": {"file_path": "/c/heracles/a.go"}}]),   # duplicate read
        _asst([{"type": "tool_use", "id": "3", "name": "Bash",
                "input": {"command": "go test ./..."}}]),
        _user([{"type": "tool_result", "tool_use_id": "3",
                "content": "ok\nFAIL: TestX timeout\n" + "x" * 5000}]),  # bulky
        _asst([{"type": "tool_use", "id": "4", "name": "Edit",
                "input": {"file_path": "/c/heracles/a.go"}}]),
    ])
    out = tx.compress_session(p)
    assert "[read /c/heracles/a.go]" in out
    assert out.count("[read /c/heracles/a.go]") == 1          # deduped
    assert "[bash] go test" in out
    assert "FAIL: TestX timeout" in out                        # error kept
    assert "x" * 5000 not in out                               # bulky body dropped
    assert "[edit /c/heracles/a.go]" in out


def test_read_events_skips_compaction(tmp_path):
    p = _write(tmp_path, [
        {"isCompactSummary": True, "message": {"role": "user", "content": "OLD SUMMARY"}},
        _user("real turn"),
    ])
    texts = [e["text"] for e in tx.read_events(p) if e["kind"] == "text"]
    assert "real turn" in texts
    assert "OLD SUMMARY" not in texts


def test_chunk_on_seams_splits_on_user_turns():
    text = "\n".join(f"U: q{i}\nA: long answer " + "y" * 200 for i in range(10))
    chunks = tx.chunk_on_seams(text, max_chars=500)
    assert len(chunks) > 1
    assert all(c.lstrip().startswith("U:") for c in chunks)    # each chunk starts at a seam


def test_chunk_returns_single_when_small():
    assert tx.chunk_on_seams("U: hi\nA: yo", max_chars=1000) == ["U: hi\nA: yo"]


def test_is_trivial():
    assert episode.is_trivial({"files_written": {}, "tickets": []}, "short chat")
    assert not episode.is_trivial({"files_written": {"r": ["a.go"]}}, "short")   # had a write
    assert not episode.is_trivial({"tickets": ["G-1"]}, "short")                 # had a ticket


def test_pin_block_has_ticket_and_first_user():
    pb = episode.pin_block({"tickets": ["GOVFOUN-438"]}, "U: fix the broken button\nA: ok")
    assert "GOVFOUN-438" in pb
    assert "fix the broken button" in pb


def test_extract_episode_single_call():
    seen = {}

    def caller(p, s, m, t):
        seen["prompt"] = p
        return {"type": "debugging", "slug": "x", "oneliner": "o",
                "keywords": [], "episode_markdown": "## Problem\ny"}

    out = episode.extract_episode("U: bug\nA: fixed", {"tickets": ["G-1"]},
                                  model_caller=caller)
    assert out["type"] == "debugging"
    assert "PINNED" in seen["prompt"]                          # pinned block injected


def test_extract_episode_long_carries_running():
    calls = []

    def caller(p, s, m, t):
        calls.append(p)
        return {"type": "new-feature", "slug": "f", "oneliner": "o",
                "keywords": [], "episode_markdown": f"step{len(calls)}"}

    out = episode.extract_episode_long(["chunk A", "chunk B", "chunk C"],
                                       "PINNED — ticket: G-1", model_caller=caller)
    assert len(calls) == 3                                     # one call per chunk
    assert "RUNNING EPISODE SO FAR" in calls[1]                # 2nd call carries running
    assert out["episode_markdown"] == "step3"

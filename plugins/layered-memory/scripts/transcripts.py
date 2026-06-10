"""Discover + read CC transcripts (.jsonl → text). Stdlib only."""
import json
from pathlib import Path


def discover_transcripts(tdir: Path) -> list:
    tdir = Path(tdir)
    if not tdir.exists():
        return []
    # Skip subagent transcripts (…/subagents/agent-*.jsonl): the parent session already
    # captures the main agent's summary of a subagent's results, so ingesting these
    # standalone fragments memory with context-free agent sessions.
    return sorted(p for p in tdir.rglob("*.jsonl") if "subagents" not in p.parts)


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def read_transcript(path: Path):
    """Return (session_id, plain_text). session_id = filename stem."""
    path = Path(path)
    sid = path.stem
    out = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = row.get("message")
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        text = _content_to_text(msg.get("content"))
        if text.strip():
            out.append(f"{role}: {text}")
    return sid, "\n".join(out)

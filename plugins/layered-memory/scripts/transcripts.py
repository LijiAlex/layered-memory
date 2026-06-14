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


# --- Step 3: structured events + compression (keeps tool actions, trims bulk) ---

_WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def _blocks(content):
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in _blocks(content) if b.get("type") == "text")
    return ""


def read_events(path) -> list:
    """Stream a transcript into ordered events (text + tool actions with paired results).
    Skips auto-compaction summary rows. Each event: {kind: 'text'|'tool', ...}."""
    rows = []
    for line in Path(path).read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    results = {}                              # pass 1: tool_use_id → result text
    for r in rows:
        msg = r.get("message")
        if isinstance(msg, dict):
            for b in _blocks(msg.get("content")):
                if b.get("type") == "tool_result":
                    results[b.get("tool_use_id", "")] = _result_text(b.get("content"))
    events = []                               # pass 2: ordered events
    for r in rows:
        if r.get("isCompactSummary") or r.get("type") == "summary":
            continue                          # skip compaction summary blocks
        msg = r.get("message")
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        content = msg.get("content")
        if isinstance(content, str):
            if content.strip():
                events.append({"kind": "text", "role": role, "text": content.strip()})
            continue
        for b in _blocks(content):
            t = b.get("type")
            if t == "text" and b.get("text", "").strip():
                events.append({"kind": "text", "role": role, "text": b["text"].strip()})
            elif t == "tool_use":
                events.append({"kind": "tool", "role": role, "name": b.get("name", ""),
                               "input": b.get("input") or {},
                               "result": results.get(b.get("id", ""), "")})
    return events


def _render_tool(e: dict, seen_reads: set) -> str:
    name = e["name"]; inp = e["input"]; res = e.get("result", "") or ""
    if name in _WRITE_TOOLS:
        return f"[edit {inp.get('file_path') or inp.get('notebook_path') or ''}]"
    if name == "Read":
        f = inp.get("file_path") or ""
        if f in seen_reads:
            return ""                         # dedupe repeated reads
        seen_reads.add(f)
        return f"[read {f}]"
    if name in ("Grep", "Glob"):
        return f"[{name.lower()} {inp.get('pattern') or inp.get('path') or ''}]"
    if name == "Bash":
        cmd = (inp.get("command") or "").replace("\n", " ")[:120]
        lines = [l for l in res.strip().splitlines() if l.strip()]
        errs = [l for l in lines if any(k in l.lower()
                for k in ("error", "fail", "exception", "traceback"))][:5]
        head = " ".join(lines[:3])[:200]
        s = f"[bash] {cmd}"
        if head:
            s += f" → {head}"
        if errs:
            s += " ERR: " + " | ".join(errs)[:300]
        return s
    if name in ("Skill", "Task"):
        return f"[skill {inp.get('skill') or inp.get('subagent_type') or ''}]"
    return f"[{name}]"


def compress_session(path) -> str:
    """Compact a transcript for distillation: keep user/assistant text + tool ACTIONS
    (commands, edits, reads) but drop bulky outputs (file dumps, long results) and dedupe
    repeated reads. Often makes chunking unnecessary."""
    out, seen_reads = [], set()
    for e in read_events(path):
        if e["kind"] == "text":
            out.append(f"{'U' if e['role'] == 'user' else 'A'}: {e['text']}")
        else:
            r = _render_tool(e, seen_reads)
            if r:
                out.append(r)
    return "\n".join(out)


def chunk_on_seams(text: str, max_chars: int) -> list:
    """Split a compressed session into few large chunks on natural seams (a new user turn),
    not token offsets. Returns [text] if it already fits."""
    if len(text) <= max_chars:
        return [text]
    chunks, cur, size = [], [], 0
    for ln in text.split("\n"):
        if cur and size >= max_chars * 0.8 and ln.startswith("U: "):
            chunks.append("\n".join(cur)); cur, size = [], 0
        cur.append(ln); size += len(ln) + 1
    if cur:
        chunks.append("\n".join(cur))
    return chunks

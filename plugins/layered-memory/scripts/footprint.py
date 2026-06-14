"""Deterministic session footprint — what a session TOUCHED, parsed from the tool blocks
that `transcripts._content_to_text` discards. This is the match signal (Step 1/2): repos,
files written/read, skills, commands, symbols, ticket refs. No model call. Stdlib only.

Canonical footprint shape (after finalize / as stored):
    {
      "repos": [str],
      "files_written": {repo: [relpath]},          # Edit/Write — strong signal
      "files_read":    {repo: {relpath: count}},    # Read/Grep/Glob — weak; count = #sessions
      "skills_used":   [str],
      "commands":      [str],                        # Bash heads / curls
      "symbols":       {sym: count},                 # recurring identifiers
      "tickets":       [str],                        # Linear-style IDs
    }
"""
import re
import json
from pathlib import Path

_CODE = re.compile(r"/code/([^/]+)")   # matches file paths AND bare dir paths (Grep/Glob)
_TICKET = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{3,}$")

_WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
_READ_TOOLS = {"Read", "Grep", "Glob"}

# top-N caps so headers never grow unbounded
CAPS = {"files_written": 20, "files_read": 15, "skills_used": 15,
        "commands": 15, "symbols": 20, "tickets": 10}


def repo_of(path: str) -> str:
    if not path:
        return "other"
    m = _CODE.search(path)
    if m:
        return m.group(1)
    if "/.claude/" in path:
        return "claude-config"
    return "other"


def _relpath(path: str, repo: str) -> str:
    marker = f"/{repo}/"
    i = path.find(marker)
    return path[i + len(marker):] if i >= 0 else path.lstrip("/")


def _blocks(content):
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def extract_footprint(transcript_path) -> dict:
    """Parse one transcript's tool blocks into a single-session footprint (read counts = 1)."""
    fp = {"repos": set(), "files_written": {}, "files_read": {},
          "skills_used": [], "commands": [], "symbols": {}, "tickets": set()}
    for line in Path(transcript_path).read_text(errors="replace").splitlines():
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
        content = msg.get("content")
        # ticket refs from user turns (and string content)
        text = content if isinstance(content, str) else " ".join(
            b.get("text", "") for b in _blocks(content) if b.get("type") == "text")
        if role == "user":
            fp["tickets"].update(_TICKET.findall(text or ""))
        for b in _blocks(content):
            if b.get("type") != "tool_use":
                continue
            name = b.get("name", "")
            inp = b.get("input") or {}
            if name in _WRITE_TOOLS:
                fpath = inp.get("file_path") or inp.get("notebook_path")
                if fpath:
                    r = repo_of(fpath); fp["repos"].add(r)
                    fp["files_written"].setdefault(r, set()).add(_relpath(fpath, r))
            elif name in _READ_TOOLS:
                fpath = inp.get("file_path") or inp.get("path")
                if fpath:
                    r = repo_of(fpath); fp["repos"].add(r)
                    d = fp["files_read"].setdefault(r, {})
                    rp = _relpath(fpath, r)
                    d[rp] = d.get(rp, 0) + 1
                pat = inp.get("pattern") or ""
                if _IDENT.match(pat):
                    fp["symbols"][pat] = fp["symbols"].get(pat, 0) + 1
            elif name == "Bash":
                cmd = (inp.get("command") or "").strip().replace("\n", " ")
                if cmd:
                    fp["commands"].append(cmd[:80])
            elif name in ("Skill", "Task"):
                s = (inp.get("skill") or inp.get("subagent_type")
                     or inp.get("command") or name)
                if s:
                    fp["skills_used"].append(str(s))
    # finalize → canonical shape
    return {
        "repos": sorted(fp["repos"]),
        "files_written": {r: sorted(v) for r, v in fp["files_written"].items()},
        "files_read": fp["files_read"],
        "skills_used": _dedup(fp["skills_used"]),
        "commands": _dedup(fp["commands"]),
        "symbols": fp["symbols"],
        "tickets": sorted(fp["tickets"]),
    }


def _dedup(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x); out.append(x)
    return out


def merge_footprints(a: dict, b: dict) -> dict:
    """Fold footprint b into a (a theme spanning sessions). Reads accumulate counts;
    everything is capped top-N so headers don't grow. Returns a new dict."""
    a = a or {}; b = b or {}
    out = {}
    out["repos"] = sorted(set(a.get("repos", [])) | set(b.get("repos", [])))
    # writes: union per repo, cap
    out["files_written"] = {}
    for src in (a.get("files_written", {}), b.get("files_written", {})):
        for r, files in src.items():
            cur = set(out["files_written"].get(r, []))
            cur.update(files)
            out["files_written"][r] = sorted(cur)[:CAPS["files_written"]]
    # reads: sum counts per repo, cap by count
    out["files_read"] = {}
    for src in (a.get("files_read", {}), b.get("files_read", {})):
        for r, counts in src.items():
            d = out["files_read"].setdefault(r, {})
            for p, c in counts.items():
                d[p] = d.get(p, 0) + c
    for r, d in out["files_read"].items():
        top = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:CAPS["files_read"]]
        out["files_read"][r] = dict(top)
    # symbols: sum counts, cap
    sym = dict(a.get("symbols", {}))
    for s, c in b.get("symbols", {}).items():
        sym[s] = sym.get(s, 0) + c
    out["symbols"] = dict(sorted(sym.items(), key=lambda kv: (-kv[1], kv[0]))[:CAPS["symbols"]])
    # list fields: dedup + cap
    out["skills_used"] = _dedup(a.get("skills_used", []) + b.get("skills_used", []))[:CAPS["skills_used"]]
    out["commands"] = _dedup(a.get("commands", []) + b.get("commands", []))[:CAPS["commands"]]
    out["tickets"] = sorted(set(a.get("tickets", [])) | set(b.get("tickets", [])))[:CAPS["tickets"]]
    return out


def write_match_keys(mem) -> Path:
    """Scan all theme files → {slug: match_keys(footprint)} → write match-keys.json.
    This is the slim, never-injected file the matcher (resolve.py) reads."""
    import paths
    import formats
    import locking
    mem = Path(mem)
    out = {}
    tdir = paths.themes_dir(mem)
    if tdir.exists():
        for f in tdir.glob("*.md"):
            fp = formats.parse_theme(f.read_text()).get("footprint") or {}
            out[f.stem] = match_keys(fp)
    p = paths.match_keys_path(mem)
    locking.atomic_write(p, json.dumps(out, sort_keys=True, indent=0))
    return p


def read_match_keys(mem) -> dict:
    import paths
    p = paths.match_keys_path(mem)
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def match_keys(fp: dict) -> dict:
    """Slim match projection for resolve.py (Step 2): never injected, read for matching.
    Reads are filtered to RECURRING-only (count >= 2) — one-off reads are weak noise."""
    fp = fp or {}
    written = [f"{r}/{p}" for r, files in fp.get("files_written", {}).items() for p in files]
    reads_recurring = [f"{r}/{p}" for r, d in fp.get("files_read", {}).items()
                       for p, c in d.items() if c >= 2]
    return {
        "repos": fp.get("repos", []),
        "files_written": sorted(written),
        "files_read_recurring": sorted(reads_recurring),
        "symbols": sorted(fp.get("symbols", {}).keys()),
        "skills_used": fp.get("skills_used", []),
        "tickets": fp.get("tickets", []),
    }

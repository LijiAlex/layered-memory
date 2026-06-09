"""config.json defaults + loader. Strict JSON (no comments) at runtime. Stdlib only."""
import json
from pathlib import Path

DEFAULTS = {
    "scopes": ["base", "project"],
    "summary_max_lines": 120,
    "index_max_lines": 200,
    "writeup_model": "claude-haiku-4-5",
    "transcript_dir": None,
    "nudge_idle_turns": 6,
    "writeup_lock_timeout_sec": 30,
    "writeup_call_timeout_sec": 20,
    "writeup_max_themes_inline": 8,
    "build_max_transcripts": 50,
    "build_transcript_char_cap": 40000,
    "context_window": 200000,          # for reporting index injection as a % of context
    "scratch_stale_after_min": 30,
    "reconcile_schedule": "03:30",
    "reconcile_min_interval_hours": 20,
    "history_keep_per_theme": 20,
    "unsorted_soft_cap": 40,
}


def load_config(mem: Path) -> dict:
    """Return DEFAULTS overlaid with any values in mem/config.json. Bad/missing → DEFAULTS."""
    cfg = dict(DEFAULTS)
    path = mem / "config.json"
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            cfg.update(data)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return cfg

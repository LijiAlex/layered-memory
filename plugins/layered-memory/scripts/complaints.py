"""Lock-free complaints.log append (spec §6/§11). Raw rows; folded later by reconcile.
Stdlib only."""
from pathlib import Path
import paths

_HEADER = "# wrong_theme | right_theme | prompt_gist | last_seen\n"


def _clean(s: str) -> str:
    # keep the row single-line and pipe-delimited
    return (s or "").replace("|", "/").replace("\n", " ").strip()


def log_complaint(mem: Path, wrong: str, right: str, gist: str,
                  ts: str = "") -> None:
    p = paths.complaints_path(mem)
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    row = f"{_clean(wrong)} | {_clean(right)} | {_clean(gist)} | {_clean(ts)}\n"
    with open(p, "a") as f:           # O_APPEND, lock-free (mid-conversation safe)
        if new:
            f.write(_HEADER)
        f.write(row)

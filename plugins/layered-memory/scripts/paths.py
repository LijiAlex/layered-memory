"""Path resolution for layered-memory. Stdlib only."""
from pathlib import Path


def base_memory_dir() -> Path:
    return Path.home() / ".claude" / "memory"


def project_memory_dir(repo_root: Path) -> Path:
    return repo_root / ".claude" / "memory"


def index_path(mem: Path) -> Path:
    return mem / "index.md"


def themes_dir(mem: Path) -> Path:
    return mem / "themes"


def history_dir(mem: Path) -> Path:
    return mem / "history"


def ops_dir(mem: Path) -> Path:
    # Op manifests are global (base) per spec §5; callers pass the base mem dir.
    return history_dir(mem) / "_ops"


def transcript_dir(cfg: dict) -> Path:
    override = cfg.get("transcript_dir")
    if override:
        return Path(override).expanduser()
    # macOS/Linux default (spec §15: Windows is Phase 2).
    return Path.home() / ".claude" / "projects"


def ensure_memory_layout(mem: Path) -> None:
    themes_dir(mem).mkdir(parents=True, exist_ok=True)
    history_dir(mem).mkdir(parents=True, exist_ok=True)
    ops_dir(mem).mkdir(parents=True, exist_ok=True)

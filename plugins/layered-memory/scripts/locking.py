"""Atomic writes + coarse flock lock with stale-PID guard (spec §11). POSIX, stdlib only."""
import os
import fcntl
import time
import json
import errno
from pathlib import Path
from contextlib import contextmanager

_STALE_LOCK_SEC = 300


def atomic_write(path: Path, data: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(data)
    os.replace(tmp, path)   # atomic on same filesystem


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as e:
        return e.errno == errno.EPERM   # exists but not ours
    return True


def _lock_meta(lockfile: Path) -> dict:
    try:
        return json.loads(lockfile.read_text())
    except Exception:
        return {}


class LockTimeout(Exception):
    pass


@contextmanager
def lock(mem: Path, timeout: float = 30.0):
    """Coarse per-scope write lock. Blocks up to `timeout`s; reclaims a stale lock
    (dead PID, older than _STALE_LOCK_SEC). Raises LockTimeout on failure."""
    mem = Path(mem)
    mem.mkdir(parents=True, exist_ok=True)
    lockfile = mem / ".lock"
    deadline = time.monotonic() + timeout
    fd = os.open(lockfile, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                os.ftruncate(fd, 0)
                os.write(fd, json.dumps(
                    {"pid": os.getpid(), "ts": time.time()}).encode())
                os.fsync(fd)
                break
            except OSError:
                meta = _lock_meta(lockfile)
                age = time.time() - meta.get("ts", 0)
                if not _is_pid_alive(meta.get("pid", -1)) and age > _STALE_LOCK_SEC:
                    # holder is dead and stale — steal by removing and retrying
                    try:
                        lockfile.unlink()
                    except FileNotFoundError:
                        pass
                if time.monotonic() > deadline:
                    raise LockTimeout(f"could not acquire {lockfile} in {timeout}s")
                time.sleep(0.1)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

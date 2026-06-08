import os
import locking


def test_atomic_write_creates_file(tmp_path):
    p = tmp_path / "sub" / "f.md"
    locking.atomic_write(p, "hello\n")
    assert p.read_text() == "hello\n"


def test_atomic_write_overwrites(tmp_path):
    p = tmp_path / "f.md"
    locking.atomic_write(p, "a")
    locking.atomic_write(p, "b")
    assert p.read_text() == "b"
    # no leftover temp files
    assert list(tmp_path.glob("*.tmp*")) == []


def test_lock_is_reentrant_serial(tmp_path):
    # Acquire, release, re-acquire in the same process — must not deadlock.
    with locking.lock(tmp_path, timeout=2):
        pass
    with locking.lock(tmp_path, timeout=2):
        assert (tmp_path / ".lock").exists()


def test_is_pid_alive_self_true():
    assert locking._is_pid_alive(os.getpid()) is True


def test_is_pid_alive_bogus_false():
    assert locking._is_pid_alive(2_147_483_000) is False

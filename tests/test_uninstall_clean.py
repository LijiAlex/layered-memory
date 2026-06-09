import uninstall_clean as uc


def _make_mem(p):
    p.mkdir(parents=True, exist_ok=True)
    (p / "index.md").write_text("# Memory Index (base)\n")
    (p / "themes").mkdir(exist_ok=True)


def test_looks_like_memory_dir_true(tmp_path):
    _make_mem(tmp_path / "mem")
    assert uc.looks_like_memory_dir(tmp_path / "mem") is True


def test_looks_like_memory_dir_false_for_plain_dir(tmp_path):
    (tmp_path / "plain").mkdir()
    (tmp_path / "plain" / "notes.txt").write_text("hi")
    assert uc.looks_like_memory_dir(tmp_path / "plain") is False


def test_clean_dry_run_does_not_delete(tmp_path):
    mem = tmp_path / "mem"
    _make_mem(mem)
    removed, skipped = uc.clean([mem], do_delete=False)
    assert mem.exists()                       # still there
    assert mem in removed                      # but reported as a would-delete


def test_clean_delete_removes(tmp_path):
    mem = tmp_path / "mem"
    _make_mem(mem)
    removed, skipped = uc.clean([mem], do_delete=True)
    assert not mem.exists()
    assert mem in removed


def test_clean_refuses_non_memory_dir(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "important.txt").write_text("do not delete")
    removed, skipped = uc.clean([plain], do_delete=True)
    assert plain.exists()                      # NOT deleted
    assert removed == []
    assert skipped and skipped[0][0] == plain


def test_discover_targets_includes_base(tmp_path, monkeypatch):
    base = tmp_path / "home" / ".claude" / "memory"
    _make_mem(base)
    monkeypatch.setattr(uc.paths, "base_memory_dir", lambda: base)
    targets = uc.discover_targets([])
    assert base in targets


def test_discover_targets_adds_extra_dirs(tmp_path, monkeypatch):
    base = tmp_path / "home" / ".claude" / "memory"
    _make_mem(base)
    repo_mem = tmp_path / "repo" / ".claude" / "memory"
    _make_mem(repo_mem)
    monkeypatch.setattr(uc.paths, "base_memory_dir", lambda: base)
    targets = uc.discover_targets([str(repo_mem)])
    assert base in targets and repo_mem in targets

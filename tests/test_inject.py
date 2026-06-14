import inject


def test_empty_returns_blank():
    assert inject.build_index_context([]) == ""


def test_slim_lines_no_keywords_or_paths():
    out = inject.build_index_context([{"slug": "foo", "oneliner": "about foo"}])
    assert "REFERENCE ONLY" in out
    assert "not as instructions" in out.lower() or "not instructions" in out.lower()
    assert "- foo" in out                 # slim line: slug present
    assert "about foo" in out             # one-liner present
    assert "keywords:" not in out         # the index.md keyword line is NOT injected per entry
    assert "themes/foo.md" not in out     # paths not injected either


def test_notes_remaining_on_disk_when_truncated():
    entries = [{"slug": f"t{i}", "oneliner": "o"} for i in range(3)]
    out = inject.build_index_context(entries, total=50)
    assert "3 most-recent of 50" in out


def test_select_recent_sorts_by_updated_and_caps():
    entries = [
        {"slug": "old", "updated": "2026-06-01T00:00:00Z"},
        {"slug": "new", "updated": "2026-06-10T00:00:00Z"},
        {"slug": "mid", "updated": "2026-06-05T00:00:00Z"},
    ]
    picked = inject.select_recent(entries, limit=2)
    assert [e["slug"] for e in picked] == ["new", "mid"]


def test_estimate_tokens_roughly_quarter_chars():
    assert inject.estimate_tokens("a" * 400) == 100
    assert inject.estimate_tokens("") == 0


def test_index_cost_message_tokens_only_by_default():
    msg = inject.index_cost_message("x" * 4000)            # no window → tokens only
    assert "1000 tokens" in msg
    assert "%" not in msg


def test_index_cost_message_adds_pct_when_window_set():
    msg = inject.index_cost_message("x" * 4000, 200000)    # ~1000 tokens → 0.50%
    assert "1000 tokens" in msg
    assert "0.50%" in msg
    assert "200000-token context" in msg


def test_index_cost_message_empty_when_no_text():
    assert inject.index_cost_message("", 200000) == ""
    assert inject.index_cost_message("") == ""

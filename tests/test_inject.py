import inject


def test_empty_returns_blank():
    assert inject.build_index_context("", None) == ""
    assert inject.build_index_context("", "") == ""


def test_base_only_wrapped_as_reference():
    out = inject.build_index_context("- **foo** — bar\n  keywords: x\n  → themes/foo.md", None)
    assert "REFERENCE ONLY" in out
    assert "not as instructions" in out.lower() or "not instructions" in out.lower()
    assert "**foo**" in out
    assert "Base (all projects)" in out


def test_includes_project_section_when_present():
    out = inject.build_index_context("- **a** — base", "- **b** — proj")
    assert "Base (all projects)" in out
    assert "This project" in out
    assert "**b**" in out


def test_estimate_tokens_roughly_quarter_chars():
    assert inject.estimate_tokens("a" * 400) == 100
    assert inject.estimate_tokens("") == 0


def test_index_cost_message_reports_tokens_and_pct():
    msg = inject.index_cost_message("x" * 4000, 200000)   # ~1000 tokens → 0.50%
    assert "1000 tokens" in msg
    assert "0.50%" in msg
    assert "200000-token context" in msg


def test_index_cost_message_empty_when_no_context():
    assert inject.index_cost_message("", 200000) == ""

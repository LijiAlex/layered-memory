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

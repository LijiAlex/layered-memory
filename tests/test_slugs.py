import slugs


def test_basic_lowercase_and_spaces():
    assert slugs.normalize_slug("Connector Inventory") == "connector-inventory"


def test_strip_non_ascii_and_punct():
    assert slugs.normalize_slug("MCP  tool/patterns!") == "mcp-tool-patterns"


def test_collapse_and_trim_dashes():
    assert slugs.normalize_slug("--a__b  c--") == "a-b-c"


def test_length_cap_50():
    out = slugs.normalize_slug("x" * 80)
    assert len(out) == 50


def test_empty_or_garbage_returns_unsorted():
    assert slugs.normalize_slug("!!!") == "unsorted"
    assert slugs.normalize_slug("") == "unsorted"

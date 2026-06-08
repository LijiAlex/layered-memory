import formats


def test_theme_roundtrip():
    theme = {
        "slug": "connector-inventory",
        "scope": "base",
        "updated": "2026-06-09T10:00:00Z",
        "sources": ["8a3f", "9b21"],
        "body": "## Key facts\n- No Snowflake.\n",
    }
    text = formats.serialize_theme(theme)
    assert text.startswith("# connector-inventory\n")
    assert "scope: base" in text
    assert "sources: [8a3f, 9b21]" in text
    parsed = formats.parse_theme(text)
    assert parsed["slug"] == "connector-inventory"
    assert parsed["scope"] == "base"
    assert parsed["sources"] == ["8a3f", "9b21"]
    assert "No Snowflake." in parsed["body"]


def test_index_roundtrip():
    entries = [
        {"slug": "connector-inventory", "oneliner": "connectors; no Snowflake.",
         "keywords": ["connector", "snowflake"], "path": "themes/connector-inventory.md"},
    ]
    text = formats.serialize_index(entries, scope_label="base")
    assert "# Memory Index (base)" in text
    assert "**connector-inventory**" in text
    assert "keywords: connector, snowflake" in text
    parsed = formats.parse_index(text)
    assert parsed[0]["slug"] == "connector-inventory"
    assert parsed[0]["keywords"] == ["connector", "snowflake"]
    assert parsed[0]["path"] == "themes/connector-inventory.md"


def test_parse_index_empty():
    assert formats.parse_index("# Memory Index (base)\n") == []

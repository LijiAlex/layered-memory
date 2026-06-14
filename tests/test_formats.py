import formats


def test_theme_roundtrip():
    theme = {
        "slug": "connector-inventory",
        "scope": "base",
        "updated": "2026-06-09T10:00:00Z",
        "footprint": {"repos": ["heracles"], "tickets": ["GOV-1"]},
        "body": "## Key facts\n- No Snowflake.\n",
    }
    text = formats.serialize_theme(theme)
    assert text.startswith("# connector-inventory\n")
    assert "scope: base" in text
    assert '"repos"' in text and "heracles" in text   # footprint stored as JSON line
    parsed = formats.parse_theme(text)
    assert parsed["slug"] == "connector-inventory"
    assert parsed["scope"] == "base"
    assert parsed["footprint"]["repos"] == ["heracles"]
    assert parsed["footprint"]["tickets"] == ["GOV-1"]
    assert "No Snowflake." in parsed["body"]


def test_theme_missing_footprint_defaults_empty():
    text = formats.serialize_theme({"slug": "x", "scope": "base",
                                    "updated": "t", "body": "b\n"})
    assert "footprint: {}" in text
    assert formats.parse_theme(text)["footprint"] == {}


def test_parse_legacy_sources_theme():
    legacy = "# old\nscope: base\nupdated: t\nsources: [a, b]\n\nbody\n"
    parsed = formats.parse_theme(legacy)
    assert parsed["footprint"] == {}      # legacy sources ignored, no crash
    assert parsed["body"] == "body"


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

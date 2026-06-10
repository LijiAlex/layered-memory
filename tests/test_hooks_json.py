import json
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "layered-memory"
HOOKS = PLUGIN / "hooks" / "hooks.json"


def test_hooks_json_has_top_level_hooks_record():
    # CC plugin hooks.json requires a top-level "hooks" object (NOT the bare-event
    # settings.json shape). Missing it → "expected record, received undefined".
    data = json.loads(HOOKS.read_text())
    assert isinstance(data.get("hooks"), dict), "hooks.json must have a top-level 'hooks' object"
    assert "SessionStart" in data["hooks"]


def test_sessionstart_entry_shape():
    data = json.loads(HOOKS.read_text())
    entry = data["hooks"]["SessionStart"][0]
    inner = entry["hooks"][0]
    assert inner["type"] == "command"
    assert "session-start.py" in inner["command"]


def test_plugin_manifest_references_hooks():
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["hooks"] == "./hooks/hooks.json"

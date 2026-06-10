from pathlib import Path

SKILL = (Path(__file__).resolve().parent.parent
         / "plugins" / "layered-memory" / "skills" / "load-memory" / "SKILL.md")


def test_exists():
    assert SKILL.exists()


def test_has_load_rematch_and_safety():
    body = SKILL.read_text().lower()
    assert "index.md" in body                       # reads the index
    assert "reference" in body and ("not instructions" in body or "never overrides" in body)
    assert "reload" in body or "wrong" in body      # re-match path
    assert "complaints" in body or "log_complaint" in body  # misroute logging


def test_skill_is_proactive_not_timid():
    body = SKILL.read_text().lower()
    assert "do not ask" in body or "never ask" in body   # load without asking permission
    assert "proactive" in body

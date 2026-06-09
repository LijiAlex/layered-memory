from pathlib import Path

SKILL = (Path(__file__).resolve().parent.parent
         / "plugins" / "layered-memory" / "skills"
         / "transcript-to-summary" / "SKILL.md")


def test_skill_exists():
    assert SKILL.exists()


def test_skill_has_reconcile_and_safety_rules():
    body = SKILL.read_text().lower()
    # reconcile-not-append (spec §10)
    assert "add" in body and "revise" in body and "prune" in body
    # untrusted-data framing (spec §12)
    assert "untrusted" in body or "not instructions" in body
    # structured output contract (spec §8.2 step 3)
    assert "merged_markdown" in body


def test_skill_pushes_consolidation():
    body = SKILL.read_text().lower()
    # anti-fragmentation: prefer existing themes, abstract to topic level
    assert "existing" in body
    assert "reuse" in body or "consolidat" in body
    assert "near-duplicate" in body or "fragment" in body or "overlapping" in body

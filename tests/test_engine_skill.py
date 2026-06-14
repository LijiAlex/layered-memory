from pathlib import Path

SKILL = (Path(__file__).resolve().parent.parent
         / "plugins" / "layered-memory" / "skills"
         / "transcript-to-summary" / "SKILL.md")


def test_skill_exists():
    assert SKILL.exists()


def test_skill_safety_and_episode_contract():
    body = SKILL.read_text().lower()
    assert "untrusted" in body or "not instructions" in body          # §12 trust
    assert "episode_markdown" in body                                  # output contract
    # reconcile (not blind append) preserved for the sequential-carry path
    assert "add" in body and "revise" in body and "prune" in body


def test_skill_classifies_and_is_cross_repo():
    body = SKILL.read_text().lower()
    for t in ("debugging", "exploration", "new-feature", "trivial"):
        assert t in body                                               # classification types
    assert "cross-repo" in body or "spans multiple repos" in body      # the core idea

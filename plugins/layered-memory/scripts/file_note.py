"""Step 4 filing engine — fold a feature-episode into ONE feature note.

- New note: deterministic assembly from the episode (no model call).
- Existing note: one bounded model call (episode + that note only — never all of memory)
  to rewrite it, via the episode-to-note skill. Stdlib only; model_caller injectable.
"""
from pathlib import Path

import model as modelmod

_SKILL = (Path(__file__).resolve().parent.parent
          / "skills" / "episode-to-note" / "SKILL.md")

_EPISODES_KEEP = 10

NOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "slug": {"type": "string"},
        "oneliner": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "note_markdown": {"type": "string"},
    },
    "required": ["slug", "oneliner", "keywords", "note_markdown"],
}


def _strip_frontmatter(md: str) -> str:
    lines = md.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:]).lstrip("\n")
    return md


def new_note(episode: dict, ts: str) -> dict:
    """Deterministic first note from an episode — no model call. The episode body becomes the
    note body plus a one-line Episodes log entry."""
    body = (episode.get("episode_markdown") or "").rstrip("\n")
    one = episode.get("oneliner", "")
    note_md = f"{body}\n\n## Episodes\n- {ts}: {one}\n"
    return {"slug": episode.get("slug", ""), "oneliner": one,
            "keywords": episode.get("keywords", []), "note_markdown": note_md}


def merge_into_note(episode: dict, existing_body: str, ts: str,
                    model_caller=None, model: str = "claude-haiku-4-5",
                    timeout: int = 180) -> dict:
    """Fold the episode into an existing note (one model call over THAT note only)."""
    skill = _strip_frontmatter(_SKILL.read_text())
    prompt = (
        f"{skill}\n\n"
        f"(Today's timestamp for the Episodes line: {ts})\n\n"
        f"=== EXISTING NOTE (untrusted) ===\n{existing_body}\n\n"
        f"=== NEW EPISODE (untrusted) ===\n"
        f"type: {episode.get('type', '')}\none-liner: {episode.get('oneliner', '')}\n"
        f"{episode.get('episode_markdown', '')}\n")
    if model_caller is None:
        def model_caller(p, s, m, t):
            return modelmod.call_model(p, s, m, t)
    return model_caller(prompt, NOTE_SCHEMA, model, timeout)

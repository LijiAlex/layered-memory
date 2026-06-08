"""Parse/serialize theme files and index.md (spec §6). Stdlib only."""
import re


def serialize_theme(theme: dict) -> str:
    sources = ", ".join(theme.get("sources", []))
    body = theme.get("body", "").rstrip("\n")
    return (
        f"# {theme['slug']}\n"
        f"scope: {theme['scope']}\n"
        f"updated: {theme['updated']}\n"
        f"sources: [{sources}]\n\n"
        f"{body}\n"
    )


def parse_theme(text: str) -> dict:
    lines = text.splitlines()
    slug = lines[0][2:].strip() if lines and lines[0].startswith("# ") else ""
    scope = updated = ""
    sources = []
    body_start = 1
    for i, line in enumerate(lines[1:], start=1):
        if line.startswith("scope:"):
            scope = line.split(":", 1)[1].strip()
        elif line.startswith("updated:"):
            updated = line.split(":", 1)[1].strip()
        elif line.startswith("sources:"):
            inner = line.split(":", 1)[1].strip().strip("[]")
            sources = [s.strip() for s in inner.split(",") if s.strip()]
        elif line.strip() == "":
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip("\n")
    return {"slug": slug, "scope": scope, "updated": updated,
            "sources": sources, "body": body}


def serialize_index(entries: list, scope_label: str) -> str:
    out = [f"# Memory Index ({scope_label})",
           "<!-- maintained by layered-memory; edit via /memory:reconcile -->", ""]
    for e in entries:
        kw = ", ".join(e.get("keywords", []))
        out.append(f"- **{e['slug']}** — {e['oneliner']}")
        out.append(f"  keywords: {kw}")
        out.append(f"  → {e['path']}")
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


_ENTRY_RE = re.compile(r"^- \*\*(?P<slug>[^*]+)\*\* — (?P<oneliner>.*)$")


def parse_index(text: str) -> list:
    entries = []
    cur = None
    for line in text.splitlines():
        m = _ENTRY_RE.match(line)
        if m:
            cur = {"slug": m.group("slug").strip(),
                   "oneliner": m.group("oneliner").strip(),
                   "keywords": [], "path": ""}
            entries.append(cur)
        elif cur is not None and line.strip().startswith("keywords:"):
            kw = line.split(":", 1)[1].strip()
            cur["keywords"] = [k.strip() for k in kw.split(",") if k.strip()]
        elif cur is not None and line.strip().startswith("→"):
            cur["path"] = line.strip()[1:].strip()
    return entries

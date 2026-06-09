#!/usr/bin/env python3
"""CLI wrapper so the load skill can log a misroute. Stdlib only.
Usage: log_complaint.py <wrong_slug> <right_slug> <prompt_gist>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths       # noqa: E402
import complaints  # noqa: E402


def main(argv):
    if len(argv) < 3:
        print("usage: log_complaint.py <wrong> <right> <gist>", file=sys.stderr)
        return 2
    wrong, right, gist = argv[0], argv[1], " ".join(argv[2:])
    complaints.log_complaint(paths.base_memory_dir(), wrong, right, gist)
    print(f"[memory] logged misroute: {wrong} -> {right}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

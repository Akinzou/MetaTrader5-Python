"""Fail when a tracked, hand-written text file exceeds the project's line limit."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MAX_LINES = 300
# Binary or third-party verbatim files; nothing generated is tracked.
EXEMPT_SUFFIXES = {".png", ".jpg", ".ico", ".whl"}
# The owner's call (2026-11-09): the README is the landing page on GitHub and
# PyPI, so it keeps every essential behind a table of contents rather than
# sending readers through several pages. A higher ceiling, not none: an
# unbounded exemption would let a pasted log through. Only the top-level README.
LIMITS = {Path("README.md"): 600}


def tracked_files() -> list[Path]:
    # S603: the command is a constant, no untrusted input reaches the process.
    command = ["git", "ls-files"]
    output = subprocess.run(command, check=True, capture_output=True, text=True).stdout  # noqa: S603
    return [Path(line) for line in output.splitlines() if line]


def main() -> int:
    offenders = []
    for path in tracked_files():
        if path.suffix in EXEMPT_SUFFIXES or not path.is_file():
            continue
        limit = LIMITS.get(path, MAX_LINES)
        count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        if count > limit:
            offenders.append(f"{path}: {count} lines (limit {limit})")
    print("\n".join(offenders) or "all tracked files are within their line limits")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())

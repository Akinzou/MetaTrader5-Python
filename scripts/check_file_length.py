"""Fail when a tracked, hand-written text file exceeds the project's line limit."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MAX_LINES = 300
# Binary or third-party verbatim files; nothing generated is tracked.
EXEMPT_SUFFIXES = {".png", ".jpg", ".ico", ".whl"}


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
        count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        if count > MAX_LINES:
            offenders.append(f"{path}: {count} lines (limit {MAX_LINES})")
    print("\n".join(offenders) or f"all tracked files have <= {MAX_LINES} lines")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())

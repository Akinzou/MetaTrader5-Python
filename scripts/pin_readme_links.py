"""Pin the README's repository links to the release tag at build time (ADR 0012).

Pinned here, not in git: master's README must keep linking documents added
after the last tag. Every refusal fails the publish, because PyPI keeps a
release's README forever and an unpinned link would go stale in silence.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = "https://github.com/Akinzou/MetaTrader5-Python"
# What ends a ref in a URL; `\b` would also stop at `-` and `.` and turn
# `master-old` into `v3.0.1-old`, a link that 404s and passes every check.
_END = r"(?=[/#?)\s\]>\"'`]|$)"
_REF = r"([^/#?)\s\]>\"'`]+)"
# Owner and repository ignore case on GitHub, branch names do not: `blob/Master`
# 404s in git too, and is reported below instead of repaired here.
MASTER_LINK = re.compile(f"(?i:{re.escape(REPO)})" + r"/(blob|tree)/master" + _END)
# Every way a link names a ref of this repository. Only the ref segment is
# read, so `master` in a file name or a badge's query string is no ref.
REF_LINKS = [
    re.compile(f"(?i:{p})" + _REF)
    for p in (
        r"github\.com/akinzou/metatrader5-python/(?:blob|tree|raw|blame|edit|commits)/",
        r"github\.com/akinzou/metatrader5-python/archive/(?:refs/(?:heads|tags)/)?",
        r"raw\.githubusercontent\.com/akinzou/metatrader5-python/",
        r"metatrader5-python\.git@",
    )
]
PROJECT_TABLE = re.compile(r"^\[project\]$(.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL)
VERSION = re.compile(r'^version = "([^"]+)"$', re.MULTILINE)


def project_version(pyproject: Path) -> str | None:
    """`version` of the [project] table; a regex because tomllib is 3.11+."""
    if not pyproject.is_file():
        return None
    table = PROJECT_TABLE.search(pyproject.read_text(encoding="utf-8"))
    found = VERSION.search(table.group(1)) if table else None
    return found.group(1) if found else None


def unpinned(text: str, tag: str) -> list[str]:
    """Links naming any ref but `tag`: master, main, HEAD, a branch, ..."""
    # A tag archive is `<tag>.zip`; everything else names the ref alone.
    return [
        m.group(0)
        for p in REF_LINKS
        for m in p.finditer(text)
        if m.group(1) not in (tag, f"{tag}.zip", f"{tag}.tar.gz")
    ]


def main(argv: list[str]) -> int:
    version = project_version(Path("pyproject.toml"))
    if version is None:
        print("pyproject.toml: no `version` in the [project] table")
        return 1
    tag = f"v{version}"
    # The full ref, not the name: a branch called v3.0.1 must not pass for the tag.
    if argv != [f"refs/tags/{tag}"]:
        print(f"build from refs/tags/{tag}, not {' '.join(argv) or 'nothing'}")
        return 1
    readme = Path("README.md")
    # Bytes: Path.read_text has no newline= before Python 3.13, and text mode
    # would turn LF into CRLF when run on Windows.
    text = readme.read_bytes().decode("utf-8")
    pinned, count = MASTER_LINK.subn(lambda m: f"{REPO}/{m.group(1)}/{tag}", text)
    if count == 0:
        # A renamed repository or a changed link style would otherwise ship
        # master links to PyPI.
        print("README.md: no master links to this repository to pin")
        return 1
    left = unpinned(pinned, tag)
    if left:
        print(f"README.md links not pinned to {tag}: " + ", ".join(left))
        return 1
    readme.write_bytes(pinned.encode("utf-8"))
    print(f"README.md: {count} link(s) pinned to {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

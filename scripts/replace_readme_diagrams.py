"""Swap the README's Mermaid diagrams for links to them on GitHub at publish (ADR 0014).

GitHub and the docs site render Mermaid; PyPI does not, and would show each
diagram as its source. A fence this script cannot swap fails the publish
instead of shipping that source, because PyPI keeps a release's README forever.

The links say `blob/master` and point at the diagram's own section. The publish
workflow runs this before pin_readme_links.py, which pins them to the release
tag, so a release on PyPI links the diagrams of that release. The docs site
follows master and could show a later one.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from mermaid_fences import ANY_FENCE, DIAGRAM, FENCE, code_flags
from pin_readme_links import REPO

# From the pinning step, which must recognise these links to pin them.
README = f"{REPO}/blob/master/README.md"
HEADING = re.compile(r"#{1,6} +(.+?)$")


def anchor(heading: str) -> str:
    """GitHub's anchor for a heading, without the suffix of a repeated one."""
    text = re.sub(r"[ \t]+#+[ \t]*$", "", heading.strip())  # closing hashes
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # a link keeps its text
    kept = re.sub(r"[^\w\- ]", "", text.lower())
    return kept.replace(" ", "-")


def section(text: str, end: int) -> str | None:
    """Anchor of the last heading before `end`; a repeated one gets GitHub's `-1`."""
    # Headings only outside code: a `# comment` in a bash or python block
    # would give a link to a section that does not exist.
    lines = text[:end].splitlines()
    seen: dict[str, int] = {}
    found = None
    for line, in_code in zip(lines, code_flags(lines), strict=True):
        heading = None if in_code else HEADING.match(line)
        if heading:
            base = anchor(heading.group(1))
            repeat = seen.get(base, 0)
            seen[base] = repeat + 1
            found = f"{base}-{repeat}" if repeat else base
    return found


def link(text: str, match: re.Match[str]) -> str:
    # A fence inside the diagram means the match ran past its own closing
    # fence and took other text with it; that text would vanish from PyPI.
    if any(FENCE.match(line) for line in match.group(1).splitlines()):
        raise ValueError(f"a diagram swallowed a code block near: {match.group(0)[:80]!r}")
    anchor_ = section(text, match.start())
    target = f"{README}#{anchor_}" if anchor_ else README
    return f"*This diagram is shown in the [README on GitHub]({target}).*\n"


def main(argv: list[str]) -> int:
    readme = Path("README.md")
    # Bytes: text mode would turn LF into CRLF when run on Windows.
    text = readme.read_bytes().decode("utf-8")
    try:
        replaced, count = DIAGRAM.subn(lambda match: link(text, match), text)
    except ValueError as error:
        print(f"README.md: {error}")
        return 1
    if ANY_FENCE.search(replaced):
        print("README.md: a Mermaid fence this script cannot replace; use ```mermaid")
        return 1
    readme.write_bytes(replaced.encode("utf-8"))
    print(f"README.md: {count} diagram(s) replaced with a link to GitHub")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

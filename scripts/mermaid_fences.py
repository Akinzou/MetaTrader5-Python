"""What counts as a Mermaid diagram, and as code, in the docs (ADR 0014).

One definition for check_diagrams.py (CI) and replace_readme_diagrams.py
(publish): if they disagreed, CI would pass a README that the publish then
refuses on release day, or that reaches PyPI with diagram source in it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

# The one form both scripts extract: a ``` fence at the start of a line. The
# closing fence may be indented up to three spaces and followed by spaces, and
# may end the file (CommonMark); anything stricter would let the lazy match run
# on to a later fence and take the text in between with it.
DIAGRAM = re.compile(
    r"^```mermaid[ \t]*\n(.*?)^ {0,3}`{3,}[ \t]*(?:\n|\Z)", re.MULTILINE | re.DOTALL
)
# Every form GitHub or Material would still render as a diagram: a tilde or a
# longer fence, or one indented inside an admonition or a tab. `[ \t]`, not
# `\s`: a match must not run on to "mermaid" at the start of a later line.
ANY_FENCE = re.compile(r"^[ \t]*(?:`{3,}|~{3,})[ \t]*mermaid\b", re.MULTILINE)
# Any line that opens or closes a fenced code block.
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def code_flags(lines: list[str]) -> Iterator[bool]:
    """For each line, whether it belongs to a fenced code block, fences included.

    A block closes only on a fence of its own character, at least as long and
    with nothing after it, so a ``` example inside a ```` block stays code.
    """
    opener: str | None = None
    for line in lines:
        fence = FENCE.match(line)
        if opener is None:
            if fence:
                opener = fence.group(1)
            yield fence is not None
            continue
        closes = (
            fence is not None
            and fence.group(1)[0] == opener[0]
            and len(fence.group(1)) >= len(opener)
            and not fence.group(2).strip()
        )
        yield True
        if closes:
            opener = None

"""PyPI cannot render Mermaid: the README it gets links the diagrams instead."""

from __future__ import annotations

from pathlib import Path

import pytest
import replace_readme_diagrams as diagrams

ROOT = Path(__file__).resolve().parents[2]
FLOW = "```mermaid\nflowchart LR\n    a --> b\n```\n"


def readme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> Path:
    path = tmp_path / "README.md"
    path.write_bytes(text.encode("utf-8"))
    monkeypatch.chdir(tmp_path)
    return path


def test_each_diagram_links_its_own_section_of_the_readme_on_github(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # blob/master: the publish workflow runs this before pin_readme_links.py,
    # which pins the link to the release tag, so PyPI shows the same diagram
    # as the release it describes.
    text = f"# Title\n\n## Retries\n\n{FLOW}\ntext\n\n### Magic numbers: whose `magic`?\n\n{FLOW}"
    path = readme(tmp_path, monkeypatch, text)
    assert diagrams.main([]) == 0
    text = path.read_bytes().decode("utf-8")
    assert "mermaid" not in text
    assert f"]({diagrams.README}#retries)" in text
    assert f"]({diagrams.README}#magic-numbers-whose-magic)" in text
    assert diagrams.README.endswith("/blob/master/README.md")
    assert text.startswith("# Title\n\n## Retries\n\n")
    assert "\ntext\n" in text


def test_the_rest_of_the_readme_is_byte_for_byte_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = "# Title\n\n```python\nprint('x')\n```\n\nNo diagram here.\n"
    path = readme(tmp_path, monkeypatch, original)
    assert diagrams.main([]) == 0
    assert path.read_bytes().decode("utf-8") == original


def test_a_diagram_fence_it_cannot_replace_fails_the_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A tilde fence or an indented one would reach PyPI as raw source.
    original = "# Title\n\n~~~mermaid\nflowchart LR\n    a --> b\n~~~\n"
    path = readme(tmp_path, monkeypatch, original)
    assert diagrams.main([]) == 1
    assert path.read_bytes().decode("utf-8") == original


def test_the_repository_readme_has_no_diagram_left_after_replacing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = (ROOT / "README.md").read_bytes().decode("utf-8")
    assert "```mermaid" in text, "the README is expected to carry diagrams"
    path = readme(tmp_path, monkeypatch, text)
    assert diagrams.main([]) == 0
    # The word itself may stay, e.g. in the ADR 0014 file name; a fence may not.
    assert diagrams.ANY_FENCE.search(path.read_bytes().decode("utf-8")) is None


def test_a_comment_in_a_code_block_is_not_taken_for_the_section_heading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = f"## Retries\n\n```bash\n# place a limit order\nrun\n```\n\n{FLOW}"
    path = readme(tmp_path, monkeypatch, text)
    assert diagrams.main([]) == 0
    replaced = path.read_bytes().decode("utf-8")
    assert f"]({diagrams.README}#retries)" in replaced
    assert "#place-a-limit-order" not in replaced


def test_a_closing_fence_with_trailing_spaces_ends_the_diagram_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A lazy match would run on to the next bare fence and swallow the text
    # and code in between into the one link.
    text = "## A\n\n```mermaid\nflowchart LR\n  a --> b\n```  \n\nKept.\n\n```\ncode\n```\n"
    path = readme(tmp_path, monkeypatch, text)
    assert diagrams.main([]) == 0
    assert "\nKept.\n\n```\ncode\n```\n" in path.read_bytes().decode("utf-8")


def test_a_diagram_closing_the_file_without_a_newline_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = readme(tmp_path, monkeypatch, "## A\n\n```mermaid\nflowchart LR\n  a --> b\n```")
    assert diagrams.main([]) == 0
    assert "mermaid" not in path.read_bytes().decode("utf-8")


def test_an_indented_closing_fence_does_not_swallow_the_text_after_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = (
        "## A\n\n```mermaid\nflowchart LR\n  a --> b\n  ```\n\n"
        "Prose kept.\n\n```python\nx = 1\n```\n"
    )
    path = readme(tmp_path, monkeypatch, text)
    assert diagrams.main([]) == 0
    assert "\nProse kept.\n\n```python\nx = 1\n```\n" in path.read_bytes().decode("utf-8")


def test_a_fence_inside_a_longer_fence_does_not_end_the_code_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Toggling on every fence line would leave the ```` block at ```bash and
    # read the comment inside it as a heading.
    example = "````markdown\n```bash\n# not a heading\n```\n````\n"
    path = readme(tmp_path, monkeypatch, f"## Real\n\n{example}\n{FLOW}")
    assert diagrams.main([]) == 0
    assert f"]({diagrams.README}#real)" in path.read_bytes().decode("utf-8")


def test_anchors_follow_github_for_closing_hashes_links_and_repeats() -> None:
    assert diagrams.anchor("Retries ##") == "retries"
    assert diagrams.anchor("See [ADR 3](https://x.y/a.md)") == "see-adr-3"
    text = "## Retries\n\ntext\n\n## Retries\n\n"
    assert diagrams.section(text, len(text)) == "retries-1"


def test_a_longer_backtick_fence_closes_a_diagram_as_on_github(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = "## A\n\n```mermaid\nflowchart LR\n  a --> b\n````\n\nKept.\n\n```\ncode\n```\n"
    path = readme(tmp_path, monkeypatch, text)
    assert diagrams.main([]) == 0
    assert "\nKept.\n\n```\ncode\n```\n" in path.read_bytes().decode("utf-8")

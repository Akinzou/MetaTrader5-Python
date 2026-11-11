"""Every Mermaid diagram must parse: the docs build cannot see a broken one."""

from __future__ import annotations

from pathlib import Path

import check_diagrams as check
import pytest

ROOT = Path(__file__).resolve().parents[2]
URL = "https://unpkg.com/mermaid@11.17.2/dist/mermaid.min.js"
TAG = f'<script src="{URL}" integrity="sha384-abc" crossorigin="anonymous"></script>'


def test_diagrams_are_found_with_their_file_and_position(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text(
        "# T\n\n```mermaid\nflowchart LR\n  a --> b\n```\n\n```python\nx = 1\n```\n"
        "\n```mermaid\nsequenceDiagram\n  A->>B: hi\n```\n",
        encoding="utf-8",
    )
    found = check.diagrams([page])
    assert [d["id"] for d in found] == [f"{page}#1", f"{page}#2"]
    assert found[0]["src"] == "flowchart LR\n  a --> b\n"


def test_the_repository_documents_carry_diagrams() -> None:
    found = check.diagrams(check.documents(ROOT))
    assert any(d["id"].startswith(str(ROOT / "README.md")) for d in found)
    assert any("architecture.md" in d["id"] for d in found)


def test_every_document_the_site_includes_is_scanned() -> None:
    # The site includes the changelog and migration guide from the root.
    # docs/CHANGELOG.md and docs/MIGRATION.md are one-line stubs; the text,
    # and any diagram in it, lives in the files at the root.
    scanned = set(check.documents(ROOT))
    expected = {ROOT / name for name in ("README.md", "CHANGELOG.md", "MIGRATION.md")}
    assert expected | {ROOT / "docs" / "architecture.md"} <= scanned


def test_a_diagram_the_checker_cannot_extract_is_reported(tmp_path: Path) -> None:
    # Material renders a tilde or an indented fence too; skipping one would
    # leave it unchecked while the run reports that every diagram parses.
    page = tmp_path / "page.md"
    page.write_text(
        "```mermaid\nflowchart LR\n  a --> b\n```\n\n"
        "!!! note\n\n    ```mermaid\n    flowchart LR\n      c --> d\n    ```\n\n"
        "~~~mermaid\nflowchart LR\n  e --> f\n~~~\n",
        encoding="utf-8",
    )
    assert check.unchecked([page]) == [
        f"{page}:8: a Mermaid fence written in a form not checked",
        f"{page}:13: a Mermaid fence written in a form not checked",
    ]


def test_a_document_with_only_checkable_fences_is_not_reported(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text("```mermaid\nflowchart LR\n  a --> b\n```\n", encoding="utf-8")
    assert check.unchecked([page]) == []


def test_a_multi_line_parse_failure_is_reported_whole() -> None:
    dom = '<html><pre id="out">["OK   a#1", "FAIL b#2: Parse error\\n-&gt;&gt;"]</pre></html>'
    assert check.failures(dom, expected=2) == ["FAIL b#2: Parse error\n->>"]


def test_all_parsed_is_no_failure() -> None:
    dom = '<html><pre id="out">["OK   a#1", "OK   b#2"]</pre></html>'
    assert check.failures(dom, expected=2) == []


def test_mermaid_that_never_loaded_is_a_failure_not_a_pass() -> None:
    # An unreachable CDN leaves the page as it was served: nothing was checked.
    dom = '<html><pre id="out">pending</pre></html>'
    assert check.failures(dom, expected=2) != []


def test_fewer_results_than_diagrams_is_a_failure() -> None:
    dom = '<html><pre id="out">["OK   a#1"]</pre></html>'
    assert check.failures(dom, expected=2) != []


def test_prose_starting_with_mermaid_after_a_fence_is_no_diagram(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text("```\ncode\n```\n\nmermaid-cli is not needed.\n", encoding="utf-8")
    assert check.unchecked([page]) == []


def test_a_browser_that_cannot_start_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("README.md", "CHANGELOG.md", "MIGRATION.md"):
        (tmp_path / name).write_text("```mermaid\nflowchart LR\n  a --> b\n```\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "overrides").mkdir()
    (tmp_path / "overrides" / "main.html").write_text(TAG, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DIAGRAM_BROWSER", str(tmp_path / "no-such-browser"))
    assert check.main([]) == 1
    assert "could not run" in capsys.readouterr().out


def test_an_extra_extracted_fence_cannot_hide_an_unextractable_one(tmp_path: Path) -> None:
    # Counting fences would pair the example inside ```` with the indented
    # diagram and report nothing; each fence is checked where it starts.
    page = tmp_path / "page.md"
    page.write_text(
        "````markdown\n```mermaid\nflowchart LR\n  a --> b\n```\n````\n\n"
        "!!! note\n\n    ```mermaid\n    flowchart LR\n      c --> d\n    ```\n",
        encoding="utf-8",
    )
    assert check.unchecked([page]) == [f"{page}:10: a Mermaid fence written in a form not checked"]


def test_a_closing_script_tag_in_a_label_cannot_break_the_page() -> None:
    diagram = {"id": "a#1", "src": 'flowchart LR\n  a["</script>"] --> b\n'}
    html = check.page([diagram], (URL, "sha384-abc"))
    assert html.count("</script>") == 2


def test_the_checked_mermaid_is_the_one_the_site_loads() -> None:
    pinned = check.site_mermaid(ROOT / "overrides" / "main.html")
    assert pinned is not None
    url, integrity = pinned
    assert url.startswith("https://unpkg.com/mermaid@11.")
    assert url.endswith("/dist/mermaid.min.js")
    assert integrity.startswith("sha384-")


def test_the_check_loads_mermaid_under_the_same_integrity_hash() -> None:
    # A changed file on unpkg is then refused in CI as it is on the site, and
    # the check fails instead of parsing with code nobody reviewed.
    html = check.page([], (URL, "sha384-abc"))
    assert f'<script src="{URL}" integrity="sha384-abc" crossorigin="anonymous">' in html

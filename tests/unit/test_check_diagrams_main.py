"""check_diagrams.main: each way a run ends, without starting a browser."""

from __future__ import annotations

import subprocess
from pathlib import Path

import check_diagrams as check
import pytest

URL = "https://unpkg.com/mermaid@11.17.2/dist/mermaid.min.js"
TAG = f'<script src="{URL}" integrity="sha384-abc" crossorigin="anonymous"></script>'
FLOW = "```mermaid\nflowchart LR\n  a --> b\n```\n"


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("README.md", "CHANGELOG.md", "MIGRATION.md"):
        (tmp_path / name).write_text(FLOW if name == "README.md" else "", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "overrides").mkdir()
    (tmp_path / "overrides" / "main.html").write_text(TAG, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DIAGRAM_BROWSER", "browser")
    return tmp_path


def browser_returns(monkeypatch: pytest.MonkeyPatch, stdout: str, stderr: str = "") -> None:
    def fake(executable: str, content: str) -> subprocess.CompletedProcess[str]:
        assert 'integrity="sha384-abc"' in content
        return subprocess.CompletedProcess([executable], 0, stdout, stderr)

    monkeypatch.setattr(check, "render", fake)


def test_every_diagram_parsing_passes(
    site: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    browser_returns(monkeypatch, '<pre id="out">["OK   README.md#1"]</pre>')
    assert check.main([]) == 0
    assert "all 1 Mermaid diagrams parse" in capsys.readouterr().out


def test_a_page_without_verdicts_reports_the_browser_output(
    site: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    browser_returns(monkeypatch, '<pre id="out">pending</pre>', stderr="sandbox failed")
    assert check.main([]) == 1
    assert "browser exit 0: sandbox failed" in capsys.readouterr().out


def test_a_site_without_a_pinned_mermaid_fails(
    site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (site / "overrides" / "main.html").write_text("<script src='x.js'></script>", encoding="utf-8")
    assert check.main([]) == 1
    assert "no pinned Mermaid" in capsys.readouterr().out


def test_an_unextractable_fence_fails_before_any_browser_runs(
    site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (site / "README.md").write_text("~~~mermaid\nflowchart LR\n  a --> b\n~~~\n", encoding="utf-8")
    assert check.main([]) == 1
    assert "form not checked" in capsys.readouterr().out


def test_no_browser_found_fails(
    site: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DIAGRAM_BROWSER")
    monkeypatch.setattr(check.shutil, "which", lambda name: None)
    monkeypatch.setattr(check, "EDGE", site / "no-edge.exe")
    assert check.main([]) == 1
    assert "set DIAGRAM_BROWSER" in capsys.readouterr().out


def test_edge_is_the_fallback_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    edge = tmp_path / "msedge.exe"
    edge.write_text("", encoding="utf-8")
    monkeypatch.delenv("DIAGRAM_BROWSER", raising=False)
    monkeypatch.setattr(check.shutil, "which", lambda name: None)
    monkeypatch.setattr(check, "EDGE", edge)
    assert check.browser() == str(edge)

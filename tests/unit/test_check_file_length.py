"""The line-limit guard that CI runs over every tracked file."""

from __future__ import annotations

from pathlib import Path

import check_file_length as script
import pytest


def run_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, lines: int) -> int:
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x\n" * lines, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(script, "tracked_files", lambda: [Path(name)])
    return script.main()


def test_a_long_hand_written_file_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_on(tmp_path, monkeypatch, "docs/guide.md", 301)
    assert code == 1
    assert "guide.md: 301 lines" in capsys.readouterr().out


def test_the_readme_may_be_longer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run_on(tmp_path, monkeypatch, "README.md", 600) == 0


def test_the_readme_still_has_a_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_on(tmp_path, monkeypatch, "README.md", 601) == 1
    assert "README.md: 601 lines (limit 600)" in capsys.readouterr().out


def test_only_the_top_level_readme_is_exempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code = run_on(tmp_path, monkeypatch, "docs/README.md", 301)
    assert code == 1

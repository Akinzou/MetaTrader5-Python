"""The README shipped to PyPI must link the documents of its own release."""

from __future__ import annotations

import shutil
from pathlib import Path

import pin_readme_links as pin
import pytest

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/Akinzou/MetaTrader5-Python"
TAG = "refs/tags/v3.0.1"
PYPROJECT = '[project]\nname = "x"\nversion = "3.0.1"\n'


def project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, readme: str, pyproject: str = PYPROJECT
) -> Path:
    (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path / "README.md"


def test_master_file_and_folder_links_point_at_the_release_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readme = project(
        tmp_path,
        monkeypatch,
        f"[a]({REPO}/blob/master/CHANGELOG.md) [b]({REPO}/tree/master/docs/adr)\n",
    )

    assert pin.main([TAG]) == 0
    assert readme.read_text(encoding="utf-8") == (
        f"[a]({REPO}/blob/v3.0.1/CHANGELOG.md) [b]({REPO}/tree/v3.0.1/docs/adr)\n"
    )


def test_links_outside_the_repository_and_the_ci_badge_stay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kept = (
        "[x](https://github.com/other/repo/blob/master/a.md) "
        f"[ci]({REPO}/actions/workflows/ci.yml) [doc]({REPO}/blob/master/a.md)\n"
    )
    readme = project(tmp_path, monkeypatch, kept)

    assert pin.main([TAG]) == 0
    assert readme.read_text(encoding="utf-8") == kept.replace(
        f"{REPO}/blob/master/", f"{REPO}/blob/v3.0.1/"
    )


@pytest.mark.parametrize(
    "written",
    [f"{REPO.lower()}/blob/master/a.md", f"{REPO}/tree/master", f"{REPO}/blob/master#top"],
)
def test_case_and_a_missing_slash_are_still_pinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, written: str
) -> None:
    readme = project(tmp_path, monkeypatch, f"[a]({written})\n")

    assert pin.main([TAG]) == 0
    assert "master" not in readme.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "moving",
    [
        "https://raw.githubusercontent.com/Akinzou/MetaTrader5-Python/master/a.png",
        f"{REPO}/blob/HEAD/a.md",
        f"{REPO}/tree/main/docs",
        f"{REPO}/blob/master-old/a.md",
        "git+https://github.com/Akinzou/MetaTrader5-Python.git@master",
        f"{REPO}/raw/master/docs/img.png",
        f"{REPO}/blame/master/a.md",
        f"{REPO}/edit/master/a.md",
        f"{REPO}/commits/master",
        f"{REPO}/archive/refs/heads/master.zip",
        # Branch names are case-sensitive: a link that 404s on GitHub is
        # reported, not quietly repaired by the pin.
        f"{REPO}/blob/Master/a.md",
    ],
)
def test_a_link_to_a_moving_ref_fails_and_leaves_the_readme(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    moving: str,
) -> None:
    original = f"[a]({REPO}/blob/master/CHANGELOG.md) [b]({moving})\n"
    readme = project(tmp_path, monkeypatch, original)

    assert pin.main([TAG]) == 1
    assert "not pinned to v3.0.1" in capsys.readouterr().out
    assert readme.read_text(encoding="utf-8") == original


def test_master_in_a_file_name_or_query_is_not_a_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readme = project(
        tmp_path,
        monkeypatch,
        f"[a]({REPO}/blob/master/docs/adr/0013-master-account.md) "
        f"[ci]({REPO}/actions/workflows/ci.yml/badge.svg?branch=master)\n",
    )

    assert pin.main([TAG]) == 0
    assert f"{REPO}/blob/v3.0.1/docs/adr/0013-master-account.md" in readme.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("ref", ["refs/heads/master", "refs/heads/v3.0.1", "v3.0.1"])
def test_a_ref_other_than_the_version_tag_refuses_and_leaves_the_readme(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], ref: str
) -> None:
    original = f"[a]({REPO}/blob/master/CHANGELOG.md)\n"
    readme = project(tmp_path, monkeypatch, original)

    assert pin.main([ref]) == 1
    assert TAG in capsys.readouterr().out
    assert readme.read_text(encoding="utf-8") == original


def test_nothing_to_pin_fails_instead_of_publishing_unpinned_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project(tmp_path, monkeypatch, "no links here\n")

    assert pin.main([TAG]) == 1
    assert "no master links" in capsys.readouterr().out


def test_the_version_comes_from_the_project_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject = '[tool.other]\nversion = "9"\n\n[project]\nversion = "3.0.1"\n'
    project(tmp_path, monkeypatch, f"[a]({REPO}/blob/master/a.md)\n", pyproject)

    assert pin.main([TAG]) == 0


@pytest.mark.parametrize(
    "pyproject", ['[project]\nname = "x"\n\n[tool.other]\nversion = "9"\n', None]
)
def test_no_readable_version_is_reported_not_raised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    pyproject: str | None,
) -> None:
    project(tmp_path, monkeypatch, f"[a]({REPO}/blob/master/a.md)\n", pyproject or "")
    if pyproject is None:
        (tmp_path / "pyproject.toml").unlink()

    assert pin.main([TAG]) == 1
    assert "pyproject.toml" in capsys.readouterr().out


def test_the_repository_readme_pins_completely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copy(ROOT / "README.md", tmp_path / "README.md")
    shutil.copy(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    monkeypatch.chdir(tmp_path)
    version = pin.project_version(Path("pyproject.toml"))
    assert version is not None

    assert pin.main([f"refs/tags/v{version}"]) == 0
    pinned = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "/master" not in pinned
    assert pin.unpinned(pinned, f"v{version}") == []
    assert f"{REPO}/blob/v{version}/README.md#contents" in pinned

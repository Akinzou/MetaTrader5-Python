"""The coverage badge is computed from the report of the run, never typed in."""

from __future__ import annotations

import json
from pathlib import Path

import coverage_badge as badge
import pytest


def report(tmp_path: Path, display: str) -> Path:
    path = tmp_path / "coverage.json"
    totals = {"percent_covered_display": display, "percent_covered": float(display)}
    path.write_text(json.dumps({"totals": totals}), encoding="utf-8")
    return path


def test_the_badge_shows_the_report_total(tmp_path: Path) -> None:
    out = tmp_path / "badge.json"
    assert badge.main([str(report(tmp_path, "100")), str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "schemaVersion": 1,
        "label": "coverage",
        "message": "100%",
        "color": "brightgreen",
    }


@pytest.mark.parametrize(
    ("display", "color"),
    [("100", "brightgreen"), ("97", "green"), ("90", "yellow"), ("80", "orange"), ("50", "red")],
)
def test_the_colour_drops_with_the_total(tmp_path: Path, display: str, color: str) -> None:
    out = tmp_path / "badge.json"
    badge.main([str(report(tmp_path, display)), str(out)])
    assert json.loads(out.read_text(encoding="utf-8"))["color"] == color


def test_a_report_without_totals_fails_instead_of_a_made_up_badge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "coverage.json"
    source.write_text("{}", encoding="utf-8")
    out = tmp_path / "badge.json"
    assert badge.main([str(source), str(out)]) == 1
    assert not out.exists()
    assert "no totals" in capsys.readouterr().out


@pytest.mark.parametrize("content", ["[]", '{"totals": {}}'])
def test_a_report_of_another_shape_is_refused_with_a_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str
) -> None:
    source = tmp_path / "coverage.json"
    source.write_text(content, encoding="utf-8")
    assert badge.main([str(source), str(tmp_path / "badge.json")]) == 1
    assert "no totals" in capsys.readouterr().out


def test_a_missing_argument_prints_the_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert badge.main(["coverage.json"]) == 1
    assert "usage:" in capsys.readouterr().out

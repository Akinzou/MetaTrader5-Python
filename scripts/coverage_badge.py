"""Turn coverage.py's JSON report into a shields.io endpoint badge (ADR 0015).

The docs workflow runs the tests on master, writes this next to the site and
the HTML report, and the README badge reads it: the number on the badge is the
number of the last run on master, never one typed in by hand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Lowest total for each colour, highest first.
COLOURS = ((100.0, "brightgreen"), (95.0, "green"), (90.0, "yellow"), (80.0, "orange"))


def colour(percent: float) -> str:
    return next((name for floor, name in COLOURS if percent >= floor), "red")


def main(argv: list[str]) -> int:
    if len(argv) != 2:  # noqa: PLR2004
        print("usage: coverage_badge.py <coverage.json> <badge.json>")
        return 1
    source, target = Path(argv[0]), Path(argv[1])
    report = json.loads(source.read_text(encoding="utf-8"))
    totals = report.get("totals") if isinstance(report, dict) else None
    if not totals:
        print(f"{source}: no totals; refusing to publish a badge without a measurement")
        return 1
    # coverage.py's own display rounding: it never shows 100 for 99.9.
    badge = {
        "schemaVersion": 1,
        "label": "Code Coverage",
        "message": f"{totals['percent_covered_display']}%",
        "color": colour(totals["percent_covered"]),
        # pytest's logo: the tests behind the number run under pytest, which
        # drives coverage.py through pytest-cov; coverage.py has no logo of its
        # own. A coverage service's logo would suggest one this project lacks.
        "namedLogo": "pytest",
        "logoColor": "white",
    }
    target.write_text(json.dumps(badge), encoding="utf-8")
    print(f"{target}: coverage {badge['message']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

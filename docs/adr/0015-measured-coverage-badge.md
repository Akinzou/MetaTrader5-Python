# ADR 0015: A coverage badge measured on master, with the full report

- Status: accepted (unreleased). Asked for by the package owner on 2026-11-12.

## Context

Tests cover 100% of the lines and branches of the library and of the release
scripts in `scripts/`. The owner wants the README to show it. A coverage
number is only worth showing if a reader can trust that it is current, and
check it.

## Decision

- **The docs workflow measures it.** On every run, a `coverage` job in
  `docs.yml` runs the tests with coverage. Its output is all that joins the
  site; the tests and dev tools never run on the machine that uploads it. It
  publishes two files:
  - the HTML report at <https://akinzou.github.io/MetaTrader5-Python/coverage/>;
  - `coverage.json`, written by `scripts/coverage_badge.py` in the shields.io
    endpoint format.

  The badge next to the title of the README and of the site's home page
  reads that file and links to the report, which also has a tab in the site's
  navigation.
- **The number is coverage.py's own.** The badge shows coverage.py's display
  value, which never rounds 99.9 up to 100. A report without totals fails the
  step rather than publish a badge.
- **CI requires 100%** (`fail_under = 100`). A drop fails the pull request, and
  on master it also stops the deploy, so the badge never shows a number that
  the gate let slip.
- **`scripts/` is measured too.** The scripts decide what reaches PyPI (link
  pinning, diagram replacement). Only `if __name__ == "__main__":` lines are
  excluded, together with the existing `TYPE_CHECKING` and
  impossible-state lines.

We chose a self-hosted badge over Codecov or Coveralls. Those need an account,
a token in the repository's secrets, and the source sent to a third party,
for the same badge. They would add history graphs, which this project does
not need.

We chose a measured badge over a static shields.io badge with the number typed
in, because the typed number goes stale at the first change and nothing would
notice.

## Consequences

- The badge shows master, like the CI badge, also on the README of older
  releases on PyPI.
- 100% is a gate, not a target to game. A state the types rule out is written
  so that it has no branch of its own and fails loudly at runtime, rather than
  excluded or skipped quietly.
- The docs workflow runs the tests once more than CI does, which adds about
  half a minute. We kept that over sharing CI's report across workflows,
  because that would couple the deploy to another workflow's artifacts.

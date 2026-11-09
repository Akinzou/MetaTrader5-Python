# ADR 0012: Publish from the tag and pin the README's links there

- Status: accepted (3.0.1). Asked for by the package owner on 2026-11-09.

## Context

PyPI renders the README of each release and keeps it forever. Relative links
break there, so the README links other documents with absolute GitHub URLs.
In 3.0.0 those URLs said `blob/master`: the 3.0.0 page on PyPI shows whatever
master holds today, which may describe a later release.

## Decision

- The README in git keeps `blob/master` / `tree/master` links.
- `scripts/pin_readme_links.py` runs in the publish workflow before the build
  and rewrites them to the tag `v<version>`, taking `version` from the
  `[project]` table of pyproject.toml.
- It refuses to run unless the workflow was dispatched from `refs/tags/v<version>`
  (`gh workflow run python-publish.yml --ref vX.Y.Z`), so the package and the
  documents it links are the same tree.
- The workflow refuses a tag that is not on master, or whose commit has no
  successful `ci.yml` run (an `--admin` merge skips the PR checks).
- It fails, and the release does not publish, when it finds nothing to pin or
  when a `blob`, `tree`, `raw`, `blame`, `edit`, `commits`, `archive`,
  `raw.githubusercontent.com` or `.git@` link to this repository names a ref
  other than the tag. Other forms (`compare/...master`, `releases/latest`)
  are not checked; the README has none. A bare link to the repository (the CI
  badge, the home page) is not a document and stays as it is.
- The upload does not skip files already on PyPI: a re-run for a published
  version fails instead of finishing green with nothing uploaded.

Rejected: publishing on tag push. `gh release create` pushes the tag, so the
upload would stop being a separate, deliberate step; with manual dispatch a
wrong `--ref` fails loudly instead.

Rejected: writing `blob/vX.Y.Z` into the README in git. A document added
after the last tag (the next ADR, say) would 404 from master's README until
the next release, and every release would need a sweep of the links.

## Consequences

- What PyPI shows for a release no longer changes after it ships.
- The README inside the sdist differs from git: only those links.
- Publishing from master now fails. The procedure: merge the release PR,
  wait for the master CI run to finish green, tag the merge commit, then
  dispatch the workflow with `--ref vX.Y.Z`.
- The `Changelog` URL in pyproject.toml stays on master on purpose: the PyPI
  sidebar should lead to the newest CHANGELOG, which also lists every fix
  released after the version a reader is looking at.
- 3.0.0 on PyPI keeps its master links; PyPI does not allow re-uploading it.

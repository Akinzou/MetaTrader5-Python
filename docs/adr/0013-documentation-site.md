# ADR 0013: A documentation site built from the README and the source

- Status: accepted (after 3.0.1, unreleased). Asked for by the package owner on 2026-11-11.

## Context

The README is the complete user guide (the owner's 600-line exemption),
but it has no API reference, and the architecture notes and ADRs are loose
Markdown files on GitHub. The owner wants the project documented to a
professional standard: one site with the guide, a reference generated from the
code, and the reasoning behind it.

Two facts constrain the tooling. The `MetaTrader5` package is Windows-only,
while the docs are built on Linux. And the package root has no static
`__all__`: unknown names resolve lazily through `MetaTrader5` (ADR 0010).

## Decision

- **MkDocs with Material for MkDocs and mkdocstrings**, published to GitHub
  Pages at <https://akinzou.github.io/MetaTrader5-Python/>.
- **The reference is read statically** by griffe, never imported. It lists
  each public name explicitly (`::: PythonMetaTrader5.<name>`), not the
  package, so the `MetaTrader5` namespace never leaks into it.
  `tests/unit/test_api_reference.py` fails when a public name has no entry or
  no docstring, a public method has no docstring, or an `ErrorKind` member does
  not say what it means.
- **The README stays the single source of the guide.** `docs/guide.md`
  includes it between `<!-- --8<-- [start:guide] -->` and `[end:guide]`
  markers, which PyPI and GitHub do not render. `MIGRATION.md` and
  `CHANGELOG.md` are included the same way. The guide is one page so that the
  README's in-page links keep working; its links to other documents still
  point to GitHub, as on PyPI.
- **`mkdocs build --strict` runs on every pull request**, in the workflow
  that deploys, so the build checked on a pull request is the one published.
  A broken link or anchor, a missing include, or a page left out of the
  navigation fails it.
- **The site is deployed from master** by `.github/workflows/docs.yml`, with
  the official Pages actions; GitHub Pages is set to the Actions source.

We chose MkDocs over Sphinx because Sphinx autodoc imports the package: on
Linux that needs `autodoc_mock_imports` for `MetaTrader5`, and `automodule`
would follow the computed `__all__` into hundreds of MT5 names. The Markdown
documents would also need MyST. `sphinx-autoapi` avoids the import, but not
the second toolchain.

We chose including the README over moving its text into the site because two
copies of the guide would drift, and the owner wants PyPI to show the
complete guide.

We chose deploying from master over deploying from the release tag because a
tag-only site could not ship before the next release, and a fix to the docs
would wait for one too. The cost: the site can describe changes not yet on
PyPI. The changelog's `Unreleased` section names them.

Rejected: Zensical, the successor of Material for MkDocs. At 0.1 its
mkdocstrings support is preliminary.

## Consequences

- Material for MkDocs is in maintenance mode and MkDocs 1.6 gets no new
  features. The configuration uses no custom hooks and no plugins besides
  search and mkdocstrings, because Zensical reads `mkdocs.yml` and every extra
  plugin would make moving there harder.
- Docstrings are now user-facing text. They state the contract briefly; the
  semantics and examples stay in the guide. `trader.py` and `broker.py` are
  close to the 300-line limit, and parameter tables there would push them over.
- The `docs` extra installs the toolchain: `pip install -e ".[docs]"`, then
  `mkdocs serve`.
- The 2.x `Broker` is documented as a class only, pointing to the migration
  guide.

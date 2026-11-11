# ADR 0014: Diagrams as Mermaid, checked in CI and replaced on PyPI

- Status: accepted (3.0.2). Asked for by the package owner on 2026-11-11.

## Context

The owner asked for diagrams in the documentation and the README. The README
appears in three places: GitHub, the docs site (ADR 0013) and PyPI, where each
release keeps its README forever (ADR 0012). GitHub and Material for MkDocs
render Mermaid; PyPI does not, and would show a diagram's source.

Material renders Mermaid in the reader's browser, so `mkdocs build --strict`
never sees a diagram that fails to parse: the live page would show its source
in silence. A `;` inside a sequence diagram label did exactly that while this
record was being written. And by default Material loads whatever Mermaid 11.x
is newest, so a diagram that parsed yesterday can break without a commit.

## Decision

- **Diagrams are Mermaid fences in Markdown**, next to the text they explain:
  the README (retries, magic-number scope) and `docs/architecture.md` (layers,
  ports, request flow, concurrency). The site's palette themes them; there is
  no image to regenerate when the code changes.
- **The site pins one Mermaid release with its integrity hash** in
  `overrides/main.html` (11.17.2 from unpkg.com, Subresource Integrity as OWASP
  ASVS requires for externally hosted scripts). A template, because
  `extra_javascript` cannot carry an integrity attribute. Material uses an
  already loaded Mermaid instead of fetching the newest 11.x, so a diagram
  changes only with a commit, and a changed file on unpkg is refused.
- **`scripts/check_diagrams.py` renders every diagram** in the README, the
  changelog, the migration guide and `docs/` with that same file and hash,
  read from the template, in headless Chrome with its sandbox on. Rendering,
  not only parsing: some errors appear only when a diagram is laid out.
  `docs.yml` runs it on every pull request, in a job of its own, apart from
  the site artifact, and the deploy waits for it. It judges every Mermaid fence where it starts, and
  fails when one does not parse, when one is written in a form it cannot
  extract (`~~~`, indented), and when Mermaid never loaded or fewer verdicts
  than diagrams came back, because then nothing was checked.
- **`scripts/replace_readme_diagrams.py` swaps each diagram for a link to its
  section of the README on GitHub** in the publish workflow. It runs before
  the links are pinned (ADR 0012), so the link names the release tag and shows
  the diagram of that release, not the site's, which follows master. It fails
  on a Mermaid fence it cannot swap, and on a diagram whose match ran past its
  own closing fence, rather than ship a README with source in it or text
  missing. The CI hygiene job runs it before `twine check`, so the check covers
  the README that PyPI receives.
- **`scripts/mermaid_fences.py` holds the one definition** of a diagram and of
  a code block that both scripts use, so CI cannot pass a README the publish
  then refuses.

We chose Mermaid over committed SVG or PNG files because an image drifts from
the code it shows, and the regeneration step would need its own check. The
cost is a browser in CI.

We chose a pinned URL over a copy of Mermaid in the repository because it pins
the version without a vendored file of about 3 MB. The cost: readers' browsers
still fetch it from unpkg.com.

We chose replacing the diagrams for PyPI over leaving the source there because
a release's README cannot be fixed once it is on PyPI.

## Consequences

- Moving to a newer Mermaid means a new URL and hash in the template, checked
  like any other pull request: a wrong hash fails the diagram check.
- The diagram check depends on unpkg.com being reachable from CI. When it is
  not, the check fails rather than passing unchecked, and the deploy, which
  waits for it, does not run: a docs fix waits until unpkg is back and the
  run is repeated. We chose that over deploying unchecked diagrams, because
  merges can skip the pull request checks (`--admin`).
- On PyPI each diagram is a one-line link to the same diagram in that
  release's README on GitHub.

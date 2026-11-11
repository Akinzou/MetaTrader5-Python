"""Fail when a Mermaid diagram in the docs does not parse (ADR 0014).

`mkdocs build --strict` cannot catch it: the browser renders the diagrams, and a
broken one shows its source on the live site in silence. This parses each one
with the Mermaid file and hash that overrides/main.html pins for the site, in a headless
Chromium-based browser: Chrome in CI, Edge on Windows.
"""

from __future__ import annotations

import functools
import html
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from mermaid_fences import ANY_FENCE, DIAGRAM

# The tag the site loads (overrides/main.html): CI parses with the same file,
# under the same integrity hash, so a changed file fails here as it would there.
PINNED = re.compile(
    r'<script src="(https://unpkg\.com/mermaid@[0-9.]+/dist/mermaid\.min\.js)"'
    r'\s+integrity="(sha384-[A-Za-z0-9+/=]+)"'
)
OUT = re.compile(r'<pre id="out">(.*?)</pre>', re.DOTALL)
BROWSERS = ("google-chrome", "chromium", "chromium-browser", "msedge")
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
# Parsing is synchronous after the script loads; the budget covers the download.
BUDGET_MS = 20_000
SCRIPT = """
mermaid.initialize({startOnLoad: false});
(async () => {
  const lines = [];
  // render, not parse: some errors only appear when a diagram is laid out.
  for (const [i, d] of DIAGRAMS.entries()) {
    try { await mermaid.render("d" + i, d.src); lines.push("OK   " + d.id); }
    catch (e) { lines.push("FAIL " + d.id + ": " + String(e.message || e)); }
  }
  // JSON: a Mermaid error message spans several lines.
  document.getElementById("out").textContent = JSON.stringify(lines);
})();
"""


def documents(root: Path) -> list[Path]:
    # The site includes CHANGELOG.md and MIGRATION.md from the root; the stubs
    # in docs/ hold only the include line.
    roots = [root / name for name in ("README.md", "CHANGELOG.md", "MIGRATION.md")]
    return [*roots, *sorted((root / "docs").rglob("*.md"))]


def scan(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """The diagrams in a file, and every Mermaid fence written in another form.

    Each fence is judged where it starts: counting them would let an extracted
    example inside a ```` block hide an indented diagram nothing extracts.
    """
    text = path.read_text(encoding="utf-8")
    found: list[dict[str, str]] = []
    problems: list[str] = []
    for fence in ANY_FENCE.finditer(text):
        diagram = DIAGRAM.match(text, fence.start())
        if diagram:
            found.append({"id": f"{path}#{len(found) + 1}", "src": diagram.group(1)})
        else:
            line = text.count("\n", 0, fence.start()) + 1
            problems.append(f"{path}:{line}: a Mermaid fence written in a form not checked")
    return found, problems


def unchecked(paths: list[Path]) -> list[str]:
    return [problem for path in paths for problem in scan(path)[1]]


def diagrams(paths: list[Path]) -> list[dict[str, str]]:
    return [diagram for path in paths for diagram in scan(path)[0]]


def site_mermaid(template: Path) -> tuple[str, str] | None:
    """The pinned Mermaid URL and its integrity hash, as the site loads them."""
    match = PINNED.search(template.read_text(encoding="utf-8"))
    return (match.group(1), match.group(2)) if match else None


def page(found: list[dict[str, str]], mermaid: tuple[str, str]) -> str:
    # "<" escaped: a label holding "</script>" would end the script early.
    data = json.dumps(found).replace("<", "\\u003c")
    script = SCRIPT.replace("DIAGRAMS", data)
    return (
        '<html><body><pre id="out">pending</pre>'
        f'<script src="{mermaid[0]}" integrity="{mermaid[1]}" crossorigin="anonymous">'
        f"</script><script>{script}</script></body></html>"
    )


def failures(dom: str, expected: int) -> list[str]:
    match = OUT.search(dom)
    text = html.unescape(match.group(1)) if match else ""
    try:
        lines = json.loads(text)
    except json.JSONDecodeError:
        lines = [text]
    # Anything but one verdict per diagram (the page left "pending" because
    # Mermaid never loaded, a crash half-way) means nothing was proven.
    verdicts = isinstance(lines, list) and all(
        isinstance(line, str) and line.startswith(("OK ", "FAIL ")) for line in lines
    )
    if not verdicts or len(lines) != expected:
        return [f"expected {expected} results, got: {lines!r}"]
    return [line for line in lines if line.startswith("FAIL ")]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        """One request per run; the verdict is the output that matters."""


def browser() -> str | None:
    named = os.environ.get("DIAGRAM_BROWSER") or next(filter(shutil.which, BROWSERS), None)
    if named:
        return shutil.which(named) or named
    return str(EDGE) if EDGE.is_file() else None


def render(executable: str, content: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        Path(directory, "index.html").write_text(content, encoding="utf-8")
        # Served over HTTP, not file://, where the browser may refuse the script.
        handler = functools.partial(_QuietHandler, directory=directory)
        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = f"http://127.0.0.1:{server.server_address[1]}/index.html"
            # The browser sandbox stays on: the page runs a third-party script.
            command = [
                executable,
                "--headless=new",
                "--disable-gpu",
                f"--virtual-time-budget={BUDGET_MS}",
                "--dump-dom",
                url,
            ]
            try:
                # The verdict is the page, not the exit code: a browser that
                # failed to start leaves no verdicts, which failures() reports.
                # S603: the arguments are this script's own, no untrusted input.
                return subprocess.run(  # noqa: S603
                    command,
                    check=False,
                    capture_output=True,
                    # The DOM is UTF-8 whatever the locale, cp1252 on Windows.
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                )
            finally:
                server.shutdown()


def main(argv: list[str]) -> int:
    paths = documents(Path())
    skipped = unchecked(paths)
    if skipped:
        print("\n".join([*skipped, "write each diagram as a ```mermaid fence at the line start"]))
        return 1
    found = diagrams(paths)
    mermaid = site_mermaid(Path("overrides/main.html"))
    if mermaid is None:
        print("overrides/main.html: no pinned Mermaid with an integrity hash to check with")
        return 1
    executable = browser()
    if executable is None:
        print("no Chrome, Chromium or Edge found; set DIAGRAM_BROWSER")
        return 1
    try:
        done = render(executable, page(found, mermaid))
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"could not run {executable}: {error}")
        return 1
    problems = failures(done.stdout, expected=len(found))
    if problems and not any(problem.startswith("FAIL ") for problem in problems):
        # No verdicts at all: the cause is in the browser's own output.
        problems.append(f"browser exit {done.returncode}: {done.stderr[-2000:]}")
    print("\n".join(problems) or f"all {len(found)} Mermaid diagrams parse")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

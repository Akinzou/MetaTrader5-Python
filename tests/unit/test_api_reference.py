"""The published API reference covers every public name, each with a docstring.

Read through griffe, the library the docs site renders with, so the test sees
what a reader sees: a `#` comment above a member counts for nothing there.
"""

from __future__ import annotations

import re
from pathlib import Path

import griffe

import PythonMetaTrader5

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "docs" / "reference"
DIRECTIVE = re.compile(r"^::: PythonMetaTrader5\.(\w+)\s*$", re.MULTILINE)
# The deprecated 2.x facade is documented as a class only and points readers
# to the migration guide: its 2.x method names are no API to learn anew.
MEMBERS_NOT_DOCUMENTED = {"Broker"}


def documented_names() -> list[str]:
    return [
        name
        for page in sorted(REFERENCE.glob("*.md"))
        for name in DIRECTIVE.findall(page.read_text(encoding="utf-8"))
    ]


def package() -> griffe.Module:
    return griffe.load("PythonMetaTrader5", search_paths=[str(ROOT / "src")])


def test_every_public_name_has_exactly_one_reference_entry() -> None:
    names = documented_names()
    assert sorted(names) == sorted(PythonMetaTrader5._OWN_NAMES)


def test_every_public_name_has_a_docstring() -> None:
    pkg = package()
    missing = [name for name in PythonMetaTrader5._OWN_NAMES if not pkg[name].docstring]
    assert missing == []


def test_every_public_method_has_a_docstring() -> None:
    pkg = package()
    missing = []
    for name in PythonMetaTrader5._OWN_NAMES:
        obj = pkg[name]
        if not obj.is_class or name in MEMBERS_NOT_DOCUMENTED:
            continue
        for member_name, member in obj.members.items():
            callable_ = member.is_function or "property" in member.labels
            if callable_ and not member_name.startswith("_") and not member.docstring:
                missing.append(f"{name}.{member_name}")
    assert missing == []


def test_every_error_kind_says_what_it_means() -> None:
    kinds = package()["ErrorKind"]
    missing = [n for n, m in kinds.members.items() if m.is_attribute and not m.docstring]
    assert missing == []

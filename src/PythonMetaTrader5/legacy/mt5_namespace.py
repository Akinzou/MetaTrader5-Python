"""The MetaTrader5 namespace, re-exported for 2.x scripts (ADR 0010).

2.x ran ``from MetaTrader5 import *`` in its ``__init__``, and its own README
called ``symbol_info("EURUSD")`` after ``from PythonMetaTrader5 import *``.
"""

from __future__ import annotations

import importlib
from collections.abc import Collection
from types import ModuleType


def load() -> ModuleType | None:
    # None, not an error: the package exists only on Windows, and importing this
    # library elsewhere (CI, type checking, docs) must keep working.
    try:
        return importlib.import_module("MetaTrader5")
    except ImportError:
        return None


def public_names(module: ModuleType | None, *, taken: Collection[str]) -> dict[str, object]:
    """Public MT5 names that do not collide with ours; ours win (MT5 has a ``Tick`` too)."""
    if module is None:
        return {}
    return {
        name: getattr(module, name)
        for name in dir(module)
        if not name.startswith("_") and name not in taken
    }
